@echo off
setlocal
cd /d "%~dp0"
py -3.11 -m venv .venv
if errorlevel 1 goto error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto error
python scripts\download_data.py
if errorlevel 1 goto error
python -m src.churn.pipeline
if errorlevel 1 goto error
python scripts\generate_report.py
if errorlevel 1 goto error
python -m pytest -q
if errorlevel 1 goto error
echo.
echo Informe actualizado en docs y resultados generados en results.
echo Luego de subir a GitHub, edita config_entrega.json y ejecuta: python scripts\generate_report.py
pause
exit /b 0
:error
echo.
echo ERROR: revisa la linea anterior. No se inventaron resultados del dataset.
pause
exit /b 1
