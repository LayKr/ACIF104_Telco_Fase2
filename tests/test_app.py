import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import app
from src.churn.pipeline import ARCHS,prep_builder,build_nn,scores
import numpy as np

def test_health():
    r=TestClient(app).get('/api/health');assert r.status_code==200;assert r.json()['status']=='ok'

def test_model_untrained_gives_503():
    from backend.app import artifacts
    artifacts.cache_clear()
    if not (ROOT/'models'/'metadata.json').exists():
        r=TestClient(app).get('/api/schema');assert r.status_code==503

def test_metrics():
    m=scores([0,0,1,1],[.1,.6,.7,.9]);assert abs(m['f1']-.8)<1e-9

def test_three_network_architectures():
    assert list(ARCHS.values())==[[64,32],[64,32,16],[128,64,32]]
    for widths in ARCHS.values():assert build_nn(32,widths)(__import__('torch').zeros(2,32)).shape==(2,1)

def test_frontend_is_served():
    client=TestClient(app)
    home=client.get('/');assert home.status_code==200;assert 'Retención Inteligente' in home.text
    script=client.get('/assets/app.js');assert script.status_code==200;assert '/api/predict' in script.text
