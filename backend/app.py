"""Minimal non-PHI churn decision-support API. No commercial-use claims."""
from __future__ import annotations
import json, os, secrets, sqlite3, time
from pathlib import Path
from functools import lru_cache
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from src.churn.pipeline import ROOT, build_nn, proba, CATEGORICAL, NUMERIC

BASE=ROOT/'models'
DB=ROOT/'results'/'monitor.sqlite3'
app=FastAPI(title='Retención Inteligente - ACIF104',description='Prototipo educativo de probabilidad de churn; no desplegar con datos personales sin controles adicionales.',version='1.0')
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='frontend')

class Customer(BaseModel):
    features: dict[str,str|float|int]

@lru_cache(maxsize=1)
def artifacts():
    meta_file=BASE/'metadata.json'
    if not meta_file.exists():raise HTTPException(503,'Modelo no entrenado. Descargue dataset y ejecute el pipeline de entrenamiento.')
    meta=json.loads(meta_file.read_text(encoding='utf8'))
    prep=joblib.load(BASE/'preprocessor.joblib')
    if meta['kind']=='torch':
        import torch
        model=build_nn(meta['n_features'],meta['hidden'])
        model.load_state_dict(torch.load(BASE/'champion.pt',map_location='cpu',weights_only=True));model.eval()
    else:model=joblib.load(BASE/'champion.joblib')
    schema=json.loads((BASE/'input_schema.json').read_text(encoding='utf8'))
    background=np.load(BASE/'shap_background.npy') if (BASE/'shap_background.npy').exists() else None
    return meta,prep,model,schema,background

def authorized(x_api_key: str|None=Header(None)):
    expected=os.environ.get('CHURN_API_KEY')
    if expected and not secrets.compare_digest(x_api_key or '',expected):raise HTTPException(401,'Se requiere X-API-Key')

def log_prediction(elapsed_ms:float, risk:float|None, status:str):
    DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB,timeout=10) as con:
        con.execute('CREATE TABLE IF NOT EXISTS predictions (created_at TEXT, latency_ms REAL, probability REAL, status TEXT)')
        con.execute('INSERT INTO predictions VALUES (?,?,?,?)',(datetime.now(timezone.utc).isoformat(),elapsed_ms,risk,status))

@app.get('/')
def home():return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/api/health')
def health():return {'status':'ok','trained':(BASE/'metadata.json').exists(),'system':'prototype','privacy':'features not persisted'}

@app.get('/api/schema',dependencies=[Depends(authorized)])
def schema():
    meta,prep,model,sch,bg=artifacts();return {'fields':sch,'model':meta['model_name'],'provenance':meta['provenance'],'test_scores':meta['test_scores']}

@app.post('/api/predict',dependencies=[Depends(authorized)])
def predict(payload:Customer):
    start=time.perf_counter()
    try:
        meta,prep,model,sch,bg=artifacts()
        data=payload.features
        expected=set(NUMERIC+CATEGORICAL)
        if set(data)!=expected:raise HTTPException(422,{'missing':sorted(expected-set(data)),'unexpected':sorted(set(data)-expected)})
        clean={}
        for name in NUMERIC:
            try: value=float(data[name])
            except (TypeError,ValueError):raise HTTPException(422,f'{name} debe ser numérico')
            s=sch['numeric'][name]
            if not np.isfinite(value) or value<s['min'] or value>s['max']:
                raise HTTPException(422,f'{name} fuera del rango del dataset: {s["min"]} - {s["max"]}')
            clean[name]=value
        for name in CATEGORICAL:
            val=str(data[name]);valid=sch['categorical'][name]
            if val not in valid:raise HTTPException(422,f'{name} debe ser una de: {valid}')
            clean[name]=val
        transformed=np.asarray(prep.transform(pd.DataFrame([clean])),dtype=np.float32)
        probability=float(proba(model,transformed)[0]);class_pred=int(probability>=meta['threshold'])
        factors=[];explain_status='not_available'
        if bg is not None:
            try:
                import shap
                # Actual per-observation model-agnostic SHAP values with 24 background examples.
                e=shap.Explainer(lambda x:proba(model,x),shap.maskers.Independent(bg,max_samples=len(bg)),algorithm='permutation',feature_names=meta['feature_names'])
                sv=e(transformed,max_evals=max(2*transformed.shape[1]+1,100),silent=True)
                vals=np.asarray(sv.values)[0]
                for i in np.argsort(np.abs(vals))[-5:][::-1]:
                    factors.append({'feature':meta['feature_names'][int(i)],'shap':round(float(vals[i]),5),'direction':'aumenta_riesgo' if vals[i]>0 else 'reduce_riesgo'})
                explain_status='shap_permutation'
            except Exception as e:
                explain_status='error_calculo_shap'
        latency=round((time.perf_counter()-start)*1000,2)
        log_prediction(latency,probability,'success')
        return {'probability':round(probability,4),'prediction':class_pred,'model':meta['model_name'],'threshold':meta['threshold'],'risk':'alto' if probability>=.65 else 'medio' if probability>=.35 else 'bajo','reasons':factors,'explanation_method':explain_status,'latency_ms':latency,'disclaimer':'Resultado académico; no determina causalidad ni debe emplearse automáticamente para decisiones comerciales.'}
    except HTTPException:raise
    except Exception as exc:
        log_prediction((time.perf_counter()-start)*1000,None,'failed')
        raise HTTPException(500,'Error interno al predecir. Consultar logs administrativos.') from exc

@app.get('/api/monitor',dependencies=[Depends(authorized)])
def monitor():
    if not DB.exists():return {'predictions':0,'errors':0,'latency_p95_ms':None,'mean_probability':None}
    with sqlite3.connect(DB,timeout=10) as con:
        rows=con.execute('SELECT latency_ms, probability, status FROM predictions').fetchall()
    successes=[r for r in rows if r[2]=='success']
    return {'predictions':len(rows),'errors':len(rows)-len(successes),'latency_p95_ms':round(float(np.percentile([r[0] for r in rows],95)),1) if rows else None,'mean_probability':round(float(np.mean([r[1] for r in successes])),3) if successes else None,'monitoring_scope':'operativo; evaluación de deriva requiere etiquetas reales posteriores'}
