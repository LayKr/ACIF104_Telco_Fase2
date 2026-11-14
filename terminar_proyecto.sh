#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/download_data.py
python -m src.churn.pipeline
python scripts/generate_report.py
python -m pytest -q
printf '\nFINALIZADO: informe en docs/, predicciones en models/ y tablas/gráficos en results/.\n'
printf 'Confirma la URL de GitHub en config_entrega.json y vuelve a ejecutar python scripts/generate_report.py.\n'
