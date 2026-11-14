"""Pruebas de contrato de API, sin afirmar resultados empíricos de IBM."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import numpy as np
import pandas as pd
import backend.app as api
from src.churn.pipeline import NUMERIC, CATEGORICAL


def test_api_predict_and_validation(monkeypatch, tmp_path):
    class IdentityPrep:
        def transform(self, df):
            return np.asarray(df[NUMERIC], dtype=np.float32)
    rng = np.random.default_rng(42)
    x = rng.uniform(0, 1, (50, 3))
    y = (x[:, 0] + x[:, 1] > 1).astype(int)
    estimator = LogisticRegression().fit(x, y)
    schema = {
        'numeric': {n: {'min':0.0, 'max':1.0, 'median':0.5} for n in NUMERIC},
        'categorical': {n: ['Yes', 'No'] for n in CATEGORICAL},
    }
    meta = {'model_name': 'QA_logistic', 'threshold': 0.5, 'provenance': 'QA unit test only',
            'test_scores': {}, 'feature_names': NUMERIC}
    # El test simula la carga ya entrenada: no escribe datos en modelos/ de la entrega.
    monkeypatch.setattr(api,'artifacts',lambda: (meta,IdentityPrep(),estimator,schema,None))
    monkeypatch.setattr(api,'DB',tmp_path/'monitor.sqlite3')
    client = TestClient(api.app)
    payload={'features': {**{n:0.6 for n in NUMERIC}, **{n:'Yes' for n in CATEGORICAL}}}
    r=client.post('/api/predict',json=payload)
    assert r.status_code==200,r.text
    result=r.json()
    assert 0<=result['probability']<=1 and result['model']=='QA_logistic'
    assert result['explanation_method']=='not_available' and result['reasons']==[]
    assert client.get('/api/monitor').json()['predictions']==1
    bad=dict(payload['features']);bad['tenure']=4.0
    assert client.post('/api/predict',json={'features':bad}).status_code==422
    missing=dict(payload['features']);missing.pop('Contract')
    assert client.post('/api/predict',json={'features':missing}).status_code==422


def test_real_trained_model_contract_if_available(monkeypatch, tmp_path):
    """Contrato extremo a extremo con artefactos reales, si el pipeline ya fue ejecutado."""
    if not (api.BASE/'metadata.json').exists():
        return
    api.artifacts.cache_clear()
    monkeypatch.setattr(api,'DB',tmp_path/'real_monitor.sqlite3')
    meta,prep,model,schema,background=api.artifacts()
    payload={'features': {
        **{name:spec['median'] for name,spec in schema['numeric'].items()},
        **{name:values[0] for name,values in schema['categorical'].items()},
    }}
    client=TestClient(api.app)
    response=client.post('/api/predict',json=payload)
    assert response.status_code==200,response.text
    result=response.json()
    assert 0<=result['probability']<=1
    assert result['model']==meta['model_name']
    assert result['explanation_method']=='shap_permutation'
    assert 1<=len(result['reasons'])<=5
    monitor=client.get('/api/monitor').json()
    assert monitor['predictions']==1 and monitor['errors']==0
