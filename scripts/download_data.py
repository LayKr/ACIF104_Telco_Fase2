"""Reproducible download from the IBM source repository. No synthetic substitute."""
from pathlib import Path
import hashlib, urllib.request
ROOT=Path(__file__).resolve().parents[1]
URL='https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv'
EXPECTED_SHA256='16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91'
path=ROOT/'data'/'Telco-Customer-Churn.csv'
try:
    path.parent.mkdir(parents=True,exist_ok=True)
    urllib.request.urlretrieve(URL,path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=EXPECTED_SHA256:
        path.unlink(missing_ok=True)
        raise ValueError('La huella SHA256 no coincide con el archivo original esperado. No se puede entrenar con archivo no verificado.')
    print(f'Dataset original verificado: {path} ({path.stat().st_size} bytes)')
except Exception as exc:
    print(f'No se pudo descargar el CSV: {exc}\nDescarga manualmente desde: {URL}\nGuarda el archivo en: {path}')
    raise
