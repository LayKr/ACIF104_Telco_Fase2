"""Training / evaluation. Use only the official IBM Telco CSV; never substitute synthetic observations."""
from __future__ import annotations
import json, os, time, random, hashlib, sys
from importlib import metadata as package_metadata
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix, roc_curve, precision_recall_curve, ConfusionMatrixDisplay
from imblearn.over_sampling import RandomOverSampler, SMOTENC
from imblearn.under_sampling import RandomUnderSampler
from sklearn.base import clone
from sklearn.inspection import permutation_importance
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import torch
from torch import nn

SEED=42
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data'/'Telco-Customer-Churn.csv'
NUMERIC=['tenure','MonthlyCharges','TotalCharges']
CATEGORICAL=['PhoneService','MultipleLines','InternetService','OnlineSecurity','OnlineBackup','DeviceProtection','TechSupport','StreamingTV','StreamingMovies','Contract','PaperlessBilling','PaymentMethod']
FEATURES=NUMERIC+CATEGORICAL
ARCHS={'DL_MLP_64_32':[64,32], 'DL_MLP_64_32_16':[64,32,16], 'DL_MLP_128_64_32':[128,64,32]}
# Hash de la publicación oficial de IBM. No se aceptan resultados científicos procedentes de datos inventados.
EXPECTED_SHA256='16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91'

def to_json(x, path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:float(v) if isinstance(v,(np.integer,np.floating)) else str(v)),encoding='utf8')

def validate_data(path=DATA):
    if not Path(path).exists():
        raise FileNotFoundError(f'No existe {path}. Descarga el CSV original ejecutando python scripts/download_data.py, o cópialo allí. No se entrena con datos simulados.')
    raw=pd.read_csv(path)
    required=set(FEATURES+['Churn','customerID'])
    missing=sorted(required-set(raw.columns))
    if missing: raise ValueError(f'Faltan columnas del dataset original: {missing}')
    if not set(raw['Churn'].dropna().unique()).issubset({'Yes','No'}):raise ValueError('Churn debe contener Yes/No')
    if raw['customerID'].duplicated().any(): raise ValueError('Se encontraron customerID duplicados: revisar el dataset')
    raw['TotalCharges']=pd.to_numeric(raw['TotalCharges'],errors='coerce')
    raw['MonthlyCharges']=pd.to_numeric(raw['MonthlyCharges'],errors='coerce')
    raw['tenure']=pd.to_numeric(raw['tenure'],errors='coerce')
    # The 11 new subscriptions with tenure=0 have no previous total charge.
    mask=raw.TotalCharges.isna() & raw.tenure.eq(0)
    raw.attrs['source_null_totalcharges']=int(raw.TotalCharges.isna().sum())
    raw.attrs['zero_tenure_imputation']=int(mask.sum())
    raw.loc[mask,'TotalCharges']=0
    return raw

def prep_builder():
    numeric=Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler())])
    categorical=Pipeline([('imputer',SimpleImputer(strategy='most_frequent')),('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))])
    return ColumnTransformer([('num',numeric,NUMERIC),('cat',categorical,CATEGORICAL)],remainder='drop',sparse_threshold=0)

def build_nn(n_inputs,hidden):
    layers=[];last=n_inputs
    for width in hidden:
        layers += [nn.Linear(last,width),nn.ReLU(),nn.Dropout(.15)]
        last=width
    layers.append(nn.Linear(last,1))
    return nn.Sequential(*layers)

def train_nn(x_train,y_train,x_val,y_val,hidden,epochs=35):
    torch.manual_seed(SEED);torch.set_num_threads(2)
    model=build_nn(x_train.shape[1],hidden)
    opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
    lossfn=nn.BCEWithLogitsLoss()
    xt=torch.tensor(x_train,dtype=torch.float32)
    yt=torch.tensor(y_train,dtype=torch.float32).view(-1,1)
    xv=torch.tensor(x_val,dtype=torch.float32)
    yv=torch.tensor(y_val,dtype=torch.float32).view(-1,1)
    history=[];best=float('inf'); patience=6; wait=0;best_state=None
    for epoch in range(epochs):
        model.train();perm=torch.randperm(len(xt));losses=[]
        for idx in perm.split(128):
            opt.zero_grad(); out=model(xt[idx]);l=lossfn(out,yt[idx]);l.backward();opt.step();losses.append(float(l.detach()))
        model.eval()
        with torch.no_grad():vl=float(lossfn(model(xv),yv))
        history.append({'epoch':epoch+1,'train_loss':float(np.mean(losses)),'val_loss':vl})
        if vl+1e-4<best: best=vl;best_state={k:v.detach().clone() for k,v in model.state_dict().items()};wait=0
        else:
            wait+=1
            if wait>=patience:break
    model.load_state_dict(best_state)
    return model,history

def proba(model,x):
    if isinstance(model,nn.Module):
        model.eval()
        with torch.no_grad():return torch.sigmoid(model(torch.tensor(np.asarray(x),dtype=torch.float32))).numpy().ravel()
    return np.asarray(model.predict_proba(x))[:,1]

def scores(y,p,threshold=.5):
    yhat=(np.asarray(p)>=threshold).astype(int)
    return {'accuracy':float(accuracy_score(y,yhat)),'precision':float(precision_score(y,yhat,zero_division=0)),'recall':float(recall_score(y,yhat,zero_division=0)),'f1':float(f1_score(y,yhat,zero_division=0)),'auc_roc':float(roc_auc_score(y,p)),'auc_pr':float(average_precision_score(y,p)),'tn':int(confusion_matrix(y,yhat,labels=[0,1])[0,0]),'fp':int(confusion_matrix(y,yhat,labels=[0,1])[0,1]),'fn':int(confusion_matrix(y,yhat,labels=[0,1])[1,0]),'tp':int(confusion_matrix(y,yhat,labels=[0,1])[1,1])}

def charts(raw,model_preds,y_test,nn_hist,balance,champion_by_split):
    out=ROOT/'results';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'figure.dpi':150})
    fig,ax=plt.subplots(figsize=(6.5,3.5));raw.Churn.value_counts().reindex(['No','Yes']).plot.bar(ax=ax)
    ax.set_title('Distribución de la variable Churn (dataset original)');ax.set_ylabel('Clientes');ax.tick_params(axis='x',rotation=0);fig.tight_layout();fig.savefig(out/'01_clases.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,3.5));
    for label in ['No','Yes']:
        ax.hist(raw.loc[raw.Churn.eq(label),'tenure'],bins=25,alpha=.5,label=label)
    ax.set_title('Antigüedad del cliente y abandono');ax.set_xlabel('Meses');ax.legend(title='Churn');fig.tight_layout();fig.savefig(out/'02_antiguedad.png');plt.close(fig)
    tab=pd.crosstab(raw.Contract,raw.Churn,normalize='index')*100
    fig,ax=plt.subplots(figsize=(6.5,3.5));tab.get('Yes',pd.Series(dtype=float)).sort_values().plot.barh(ax=ax)
    ax.set_title('Abandono por tipo de contrato');ax.set_xlabel('Porcentaje de churn');fig.tight_layout();fig.savefig(out/'03_contrato.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(5.5,4));corr=raw[NUMERIC].corr(numeric_only=True)
    im=ax.imshow(corr,vmin=-1,vmax=1,cmap='coolwarm');ax.set_xticks(range(3),NUMERIC,rotation=25);ax.set_yticks(range(3),NUMERIC)
    for i in range(3):
        for j in range(3):ax.text(j,i,f'{corr.iloc[i,j]:.2f}',ha='center',va='center')
    fig.colorbar(im,ax=ax);fig.tight_layout();fig.savefig(out/'04_correlacion.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,4));
    for name,p in model_preds.items():
        fpr,tpr,_=roc_curve(y_test,p);ax.plot(fpr,tpr,label=f'{name} ({roc_auc_score(y_test,p):.3f})')
    ax.plot([0,1],[0,1],'--',linewidth=.8);ax.set_xlabel('FPR');ax.set_ylabel('TPR');ax.set_title('ROC sobre conjunto test');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(out/'05_roc_test.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharey=True)
    for name,h in nn_hist.items():
        epochs=[e['epoch'] for e in h]
        axes[0].plot(epochs,[e['train_loss'] for e in h],label=name)
        axes[1].plot(epochs,[e['val_loss'] for e in h],label=name)
    axes[0].set_title('Pérdida de entrenamiento MLP');axes[1].set_title('Pérdida de validación MLP')
    for ax in axes:ax.set_xlabel('Época');ax.set_ylabel('BCE loss');ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'06_convergencia.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,4))
    for name,p in model_preds.items():
        prec,rec,_=precision_recall_curve(y_test,p)
        ax.plot(rec,prec,label=f'{name} (AP {average_precision_score(y_test,p):.3f})')
    ax.axhline(float(np.mean(y_test)),ls='--',lw=.8,label='Prevalencia test')
    ax.set_xlabel('Recall');ax.set_ylabel('Precision');ax.set_title('Precisión-recall sobre test');ax.legend(fontsize=7);fig.tight_layout();fig.savefig(out/'10_pr_test.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,3.6));balance.set_index('sampling')['f1_val'].plot.bar(ax=ax)
    ax.set_title('Balanceo: F1 de validación (modelo ganador)');ax.set_ylabel('F1');ax.set_ylim(0,1);ax.tick_params(axis='x',rotation=15);fig.tight_layout();fig.savefig(out/'07_balance.png');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(10.5,3.4))
    for ax,(split,values) in zip(axes,champion_by_split.items()):
        cm=np.array([[values['tn'],values['fp']],[values['fn'],values['tp']]])
        ConfusionMatrixDisplay(cm,display_labels=['No','Sí']).plot(ax=ax,colorbar=False,values_format='d')
        ax.set_title(split.capitalize());ax.set_xlabel('Predicción');ax.set_ylabel('Clase real')
    fig.suptitle('Matrices de confusión del modelo campeón',y=1.02)
    fig.tight_layout();fig.savefig(out/'11_matrices_confusion.png',bbox_inches='tight');plt.close(fig)

def create_eda(raw):
    miss=raw.isna().sum().to_dict()
    outliers={}
    for col in NUMERIC:
        q1,q3=raw[col].quantile([.25,.75]); iqr=q3-q1
        outliers[col]=int(((raw[col]<q1-1.5*iqr)|(raw[col]>q3+1.5*iqr)).sum())
    quality={'rows':len(raw),'columns':len(raw.columns),'source_null_totalcharges':raw.attrs.get('source_null_totalcharges'),'zero_tenure_imputation':raw.attrs.get('zero_tenure_imputation'),'positive':int(raw.Churn.eq('Yes').sum()),'negative':int(raw.Churn.eq('No').sum()),'positive_rate':float(raw.Churn.eq('Yes').mean()),'duplicates_customerID':int(raw.customerID.duplicated().sum()),'missing_after_business_rule':{k:int(v) for k,v in miss.items()},'outliers_iqr':outliers,'numeric_descriptives':raw[NUMERIC].describe().round(3).to_dict(),'categorical_counts':{col:raw[col].value_counts().to_dict() for col in CATEGORICAL}}
    to_json(quality,ROOT/'results'/'data_quality.json')
    return quality

def get_ml():
    return {'ML_LogisticRegression':LogisticRegression(max_iter=1000,random_state=SEED,class_weight=None), 'ML_RandomForest':RandomForestClassifier(n_estimators=180,min_samples_leaf=4,n_jobs=2,random_state=SEED),'ML_HistGradientBoosting':HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=15,l2_regularization=.1,random_state=SEED)}

def fit_candidate(name,xt,yt,xv,yv):
    if name in ARCHS:
        model,h=train_nn(xt,yt,xv,yv,ARCHS[name]);return model,h
    model=clone(get_ml()[name]);model.fit(xt,yt);return model,[]

def explain_shap(model,xb,xsample,feature_names):
    """Genuine SHAP permutation values; no feature importance is mislabeled SHAP."""
    import shap
    xb=np.asarray(xb,dtype=np.float64);xsample=np.asarray(xsample,dtype=np.float64)
    explain=shap.Explainer(lambda x:proba(model,x),shap.maskers.Independent(xb,max_samples=len(xb)),algorithm='permutation',feature_names=list(feature_names))
    result=explain(xsample,max_evals=max(2*xsample.shape[1]+1,100),silent=True)
    arr=np.asarray(result.values)
    avg=np.mean(abs(arr),axis=0)
    table=pd.DataFrame({'feature':feature_names,'mean_abs_shap':avg}).sort_values('mean_abs_shap',ascending=False)
    table.to_csv(ROOT/'results'/'shap_global.csv',index=False)
    fig,ax=plt.subplots(figsize=(8,5));table.head(12).sort_values('mean_abs_shap').plot.barh(x='feature',y='mean_abs_shap',ax=ax,legend=False)
    ax.set_title('SHAP global en prueba');ax.set_xlabel('Cambio en probabilidad');ax.set_ylabel('Variable codificada');fig.tight_layout();fig.savefig(ROOT/'results'/'08_shap.png');plt.close(fig)
    return table

def run(csv_path=DATA, epochs=35):
    t0=time.perf_counter();random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED)
    (ROOT/'models').mkdir(exist_ok=True);(ROOT/'results').mkdir(exist_ok=True)
    raw=validate_data(csv_path)
    if len(raw)<1000:raise ValueError('Se requiere dataset completo original; no se acepta un fragmento de demostración para las métricas finales.')
    data_checksum=hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()
    if data_checksum != EXPECTED_SHA256 or len(raw) != 7043:
        raise ValueError('Los resultados finales requieren el CSV íntegro de IBM (7.043 filas) con SHA-256 verificado. No se publicarán métricas de un archivo diferente.')
    quality=create_eda(raw)
    x=raw[FEATURES].copy();y=raw.Churn.eq('Yes').astype(int)
    x_trainval,x_test,y_trainval,y_test=train_test_split(x,y,test_size=.2,stratify=y,random_state=SEED)
    x_train,x_val,y_train,y_val=train_test_split(x_trainval,y_trainval,test_size=.2,stratify=y_trainval,random_state=SEED)
    split_audit={
        'seed':SEED,
        'rows_total':int(len(raw)),
        'rows_train':int(len(x_train)),
        'rows_validation':int(len(x_val)),
        'rows_test':int(len(x_test)),
        'train_validation_overlap':int(len(set(x_train.index)&set(x_val.index))),
        'train_test_overlap':int(len(set(x_train.index)&set(x_test.index))),
        'validation_test_overlap':int(len(set(x_val.index)&set(x_test.index))),
        'union_rows':int(len(set(x_train.index)|set(x_val.index)|set(x_test.index))),
        'preprocessor_fit_scope':'train_only',
        'resampling_scope':'train_only',
        'model_and_sampling_selection_scope':'validation_only',
        'threshold_selection_scope':'validation_only',
        'test_scope':'final_evaluation_only',
        'positive_rate_train':float(y_train.mean()),
        'positive_rate_validation':float(y_val.mean()),
        'positive_rate_test':float(y_test.mean()),
    }
    assert split_audit['union_rows']==len(raw) and not any(split_audit[k] for k in ('train_validation_overlap','train_test_overlap','validation_test_overlap'))
    prep=prep_builder();xt=np.asarray(prep.fit_transform(x_train),dtype=np.float32);xv=np.asarray(prep.transform(x_val),dtype=np.float32);xte=np.asarray(prep.transform(x_test),dtype=np.float32)
    scaler_seen=int(prep.named_transformers_['num'].named_steps['scaler'].n_samples_seen_)
    split_audit['numeric_preprocessor_fit_rows']=scaler_seen
    assert scaler_seen==len(x_train)
    to_json(split_audit,ROOT/'results'/'leakage_audit.json')
    names=prep.get_feature_names_out().tolist();joblib.dump(prep,ROOT/'models'/'preprocessor.joblib')
    # Unsupervised comparator: clustering on training only, assessed with silhouette.
    clus=MiniBatchKMeans(n_clusters=3,random_state=SEED,n_init=10,batch_size=256).fit(xt)
    memberships=clus.predict(xt)
    clustering={'algorithm':'MiniBatchKMeans','clusters':3,'silhouette_train':float(silhouette_score(xt,memberships,sample_size=min(1000,len(xt)),random_state=SEED)), 'n_per_cluster':{str(i):int(np.sum(memberships==i)) for i in range(3)},'churn_by_cluster_train':{str(i):float(np.asarray(y_train)[memberships==i].mean()) for i in range(3)},'role':'segmentación no supervisada; no compite por AUC con clasificadores'}
    to_json(clustering,ROOT/'results'/'clustering.json')
    xy=PCA(n_components=2,random_state=SEED).fit_transform(xt)
    fig,ax=plt.subplots(figsize=(6.5,4));p=ax.scatter(xy[:,0],xy[:,1],c=memberships,s=9,alpha=.5,cmap='viridis');ax.set_title('Clustering no supervisado, proyección PCA (train)');ax.set_xlabel('PC1');ax.set_ylabel('PC2');fig.colorbar(p,ax=ax,label='Cluster');fig.tight_layout();fig.savefig(ROOT/'results'/'09_clustering.png');plt.close(fig)
    estimators={};histories={};comparison=[];preds={}
    for name in list(get_ml())+list(ARCHS):
        model,h=fit_candidate(name,xt,y_train.to_numpy(),xv,y_val.to_numpy())
        estimators[name]=model
        if h:histories[name]=h
        p_train=proba(model,xt);p_val=proba(model,xv)
        comparison.append({'model':name,'family':'DL' if name in ARCHS else 'ML',**{k+'_train':v for k,v in scores(y_train,p_train).items()},**{k+'_val':v for k,v in scores(y_val,p_val).items()}})
    comparison=pd.DataFrame(comparison).sort_values(['auc_pr_val','f1_val'],ascending=False)
    comparison[['model','family']+[c for c in comparison.columns if c.endswith('_train')]].to_csv(ROOT/'results'/'models_train.csv',index=False)
    comparison.to_csv(ROOT/'results'/'models_validation.csv',index=False)
    best_name=str(comparison.iloc[0]['model']); best_model=estimators[best_name]
    # Three *independent* resampling strategies, fitted on training only; test/validation never resampled.
    # SMOTENC works in original mixed-type space, avoiding fractional one-hot columns.
    cat_indices=[FEATURES.index(c) for c in CATEGORICAL]
    smote_x,smote_y=SMOTENC(categorical_features=cat_indices,random_state=SEED,k_neighbors=5).fit_resample(x_train,y_train)
    strategies={'sin_balanceo':(xt,y_train.to_numpy()),'oversampling':RandomOverSampler(random_state=SEED).fit_resample(xt,y_train),'undersampling':RandomUnderSampler(random_state=SEED).fit_resample(xt,y_train),'SMOTENC':(np.asarray(prep.transform(smote_x),dtype=np.float32),np.asarray(smote_y,dtype=int))}
    balance=[];balance_models={}
    for key,(xb,yb) in strategies.items():
        if key=='sin_balanceo': model=best_model
        else: model,_=fit_candidate(best_name,np.asarray(xb,dtype=np.float32),np.asarray(yb,dtype=int),xv,y_val.to_numpy())
        balance_models[key]=model
        sc=scores(y_val,proba(model,xv))
        balance.append({'sampling':key,'n_train':int(len(yb)),'positive_train':int(np.asarray(yb).sum()),'f1_val':sc['f1'],'recall_val':sc['recall'],'auc_pr_val':sc['auc_pr'],'auc_roc_val':sc['auc_roc']})
    balance=pd.DataFrame(balance).sort_values(['auc_pr_val','f1_val'],ascending=False)
    balance.to_csv(ROOT/'results'/'balance_validation.csv',index=False)
    best_sampler=str(balance.iloc[0]['sampling']);champ=balance_models[best_sampler]
    # Validation-only threshold search; test never used for model or threshold selection.
    pv=proba(champ,xv);thr_scores=[(float(t),f1_score(y_val,pv>=t)) for t in np.arange(.2,.805,.025)]
    threshold=sorted(thr_scores,key=lambda x:x[1],reverse=True)[0][0]
    test_comparison=[]
    for name,m in estimators.items():
        p=proba(m,xte);preds[name]=p;test_comparison.append({'model':name,**scores(y_test,p,threshold=.5)})
    pd.DataFrame(test_comparison).to_csv(ROOT/'results'/'models_test.csv',index=False)
    champion_probs={'train':proba(champ,xt),'validación':proba(champ,xv),'prueba':proba(champ,xte)}
    champion_targets={'train':y_train,'validación':y_val,'prueba':y_test}
    champion_by_split={split:scores(champion_targets[split],p,threshold) for split,p in champion_probs.items()}
    pd.DataFrame([{'split':split,**values} for split,values in champion_by_split.items()]).to_csv(ROOT/'results'/'champion_metrics_by_split.csv',index=False)
    final=champion_by_split['prueba']
    saved={'kind':'torch' if best_name in ARCHS else 'sklearn','model_name':best_name,'sampling':best_sampler,'threshold':threshold,'n_features':len(names),'feature_names':names,'numeric':NUMERIC,'categorical':CATEGORICAL,'provenance':'IBM Telco Customer Churn CSV original','dataset_sha256':data_checksum,'rows':len(raw),'n_train':len(xt),'n_validation':len(xv),'n_test':len(xte),'selection_metric':'auc_pr_val','test_scores':final,'runtime_seconds':round(time.perf_counter()-t0,2),'software_versions':{'python':sys.version.split()[0],**{name:package_metadata.version(name) for name in ('numpy','pandas','scikit-learn','imbalanced-learn','torch','shap','matplotlib')}}}
    if best_name in ARCHS:
        torch.save(champ.state_dict(),ROOT/'models'/'champion.pt');saved['hidden']=ARCHS[best_name]
    else:joblib.dump(champ,ROOT/'models'/'champion.joblib')
    to_json(saved,ROOT/'models'/'metadata.json')
    feature_schema={'numeric':{c:{'min':float(raw[c].min()),'max':float(raw[c].max()),'median':float(raw[c].median())} for c in NUMERIC},'categorical':{c:sorted(raw[c].dropna().astype(str).unique().tolist()) for c in CATEGORICAL}}
    to_json(feature_schema,ROOT/'models'/'input_schema.json')
    # Keep a tiny feature-space background for explainability; never store identifiable records.
    np.save(ROOT/'models'/'shap_background.npy',xt[:24])
    try:
        shap_table=explain_shap(champ,xt[:24],xte[:12],names)
        saved['shap_ok']=True; saved['top_shap_features']=shap_table.head(5).feature.tolist()
    except Exception as e:
        saved['shap_ok']=False;saved['shap_error']=str(e)
    history_rows=[{'model':name,**row} for name,history in histories.items() for row in history]
    pd.DataFrame(history_rows).to_csv(ROOT/'results'/'deep_learning_history.csv',index=False)
    charts(raw,preds,y_test,histories,balance,champion_by_split)
    to_json(saved,ROOT/'models'/'metadata.json')
    to_json({'data_quality':quality,'leakage_audit':split_audit,'champion':saved,'champion_by_split':champion_by_split,'model_selection':comparison.to_dict(orient='records'),'balance_selection':balance.to_dict(orient='records'),'test_benchmark':test_comparison},ROOT/'results'/'summary.json')
    print(json.dumps(saved,ensure_ascii=False,indent=2));return saved

if __name__=='__main__':run()
