# Retención Inteligente — ACIF104, segunda fase (UNAB)

Prototipo educativo de *customer churn* con dataset público **IBM Telco Customer Churn**. Incluye análisis exploratorio, tres modelos ML, tres arquitecturas de deep learning con PyTorch, tres técnicas de balanceo, métricas en test, interpretación SHAP, API FastAPI y frontend web. **No está aprobado ni validado para producción**.

## Proveniencia y estado

El CSV de IBM no se versiona: se descarga desde la fuente pública y se comprueba su SHA-256. Los artefactos incluidos se generaron mediante una ejecución real sobre las 7.043 filas verificadas; no contienen métricas sintéticas.

- Dataset: https://github.com/IBM/telco-customer-churn-on-icp4d
- CSV directo: https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv
- 7.043 registros, 21 columnas en versión clásica (datos de ejemplo de una empresa ficticia).

## Requisitos

Python 3.11 o 3.12, 4 GB RAM recomendados, conexión a Internet para descargar el dataset y los paquetes. CPU suficiente; GPU opcional.

## Instalación (desde la carpeta raíz)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_data.py
python -m src.churn.pipeline
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

`requirements.txt` define rangos compatibles; `requirements-lock.txt` conserva las versiones exactas usadas en la ejecución final de Windows.

Abre `http://127.0.0.1:8000` y `http://127.0.0.1:8000/docs`.

Si el enlace de IBM no está disponible, descarga el CSV oficial y cópialo en `data/Telco-Customer-Churn.csv`. No cambies columnas, nombres ni valores. Si tu conexión no permite descarga, **no** se genera una muestra sintética para fingir resultados del proyecto.

## Contenidos

- `src/churn/pipeline.py`: limpieza, EDA, partición 64/16/20, entrenamiento de 6 modelos, balanceos de entrenamiento, elección del ganador por AUC-PR de validación, umbral ajustado en validación, evaluación final test, métricas/SHAP/gráficos.
- `backend/app.py`: API de inferencia, explicaciones locales SHAP y monitoreo operativo anónimo SQLite.
- `frontend/`: página web responsive, construida con HTML, CSS y JavaScript.
- `results/`: CSV y PNG de modelos, ROC, balanceo, SHAP y datos de calidad **generados tras ejecución real**.
- `models/`: preprocesador, modelo ganador, metadatos, muestras de referencia para SHAP.
- `tests/`: pruebas automatizadas.
- `docs/`: documentación e informe.

## Diseño metodológico y prevención de fuga de datos

Partición estratificada: 20 % test intocable; del 80 % restante, 20 % validación y 80 % entrenamiento. Imputación y estandarización ajustadas exclusivamente al entrenamiento. OneHotEncoder para atributos categóricos. No se usa `customerID` ni atributos personales de género/edad para predecir. Se prueban Regresión Logística, Random Forest e HistGradientBoosting, junto con MLP [64,32], [64,32,16], [128,64,32]. Después de escoger arquitectura por AUC-PR validación, se comparan RandomOversampler, RandomUnderSampler y SMOTE vs base, únicamente en train. Umbral se optimiza con F1 de validación y las métricas test se calculan una vez al final. Para evitar fuga de información, ninguna etiqueta test influye en preprocesamiento, entrenamiento o selección.

## Seguridad y límites

API destinada a localhost. Para servidor remoto, configurar HTTPS, autenticación (`CHURN_API_KEY`), rate limiting, segregación de acceso, no persistir datos de clientes y revisar exigencias legales de protección de datos. Las solicitudes no se guardan: solo latencia, probabilidad y estado del procesamiento en `results/monitor.sqlite3`. SHAP atribuye factores de predicción, **no causalidad**. Riesgo de sesgos y deriva: debe validarse con datos reales y con diversidad demográfica antes de usarlo.

API protegida opcionalmente con header `X-API-Key` si defines `CHURN_API_KEY` en el entorno. Al activar esa clave debe adaptarse el cliente frontend para enviar el header, o situar la autenticación en un proxy de acceso.

## Pruebas

```bash
pytest -q
```

La revisión final aprobó 7 pruebas, incluida una prueba extremo a extremo del modelo real que exige predicción válida, monitoreo y explicación SHAP local no vacía.

## Resultados reproducidos

La ejecución con semilla 42 seleccionó Regresión Logística sin balanceo por AUC-PR de validación. El umbral 0,350 se eligió exclusivamente en validación. En prueba independiente se obtuvo ROC-AUC 0,842; AUC-PR 0,632; precisión 0,546; recall 0,703; F1 0,614; TN 816; FP 219; FN 111; TP 263. Consulta `results/summary.json` y `results/champion_metrics_by_split.csv` para conservar la precisión completa de los valores.

`results/leakage_audit.json` registra cero intersecciones entre train, validación y test; además confirma que el escalador se ajustó con las 4.507 filas de entrenamiento. El pipeline registra métricas de train, validación y test, las curvas de las tres MLP, las cuatro condiciones de muestreo, matrices de confusión y SHAP real.

## Reproducción del informe

Al terminar el entrenamiento, `results/summary.json`, `results/models_train.csv`, `results/models_validation.csv`, `results/models_test.csv`, `results/champion_metrics_by_split.csv`, `results/balance_validation.csv`, `results/leakage_audit.json` y `results/*.png` contienen las evidencias numéricas y visuales.

## Autoría y licencia

Proyecto preparado como material base de trabajo grupal ACIF104. Revisar y completar nombres, grupo y actividades efectivamente realizadas antes de presentar. Datos: IBM Telco Sample Data; citar y respetar sus condiciones de uso.


## Finalización automática para la entrega (sin editar código)

1. Instala Python 3.11 y LibreOffice (para exportar DOCX a PDF).
2. Windows: ejecuta `terminar_proyecto_windows.bat`. Linux/macOS: ejecuta `bash terminar_proyecto.sh`.
3. Si la descarga automática de IBM está bloqueada, descarga el CSV mediante un navegador desde el [enlace oficial](https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv), guárdalo como `data/Telco-Customer-Churn.csv` y luego ejecuta `python -m src.churn.pipeline` y `python scripts/generate_report.py`.
4. Revisa `results/summary.json`, `results/models_test.csv`, `results/08_shap.png`, `results/11_matrices_confusion.png` y `docs/acif104_s6_grupoX.pdf` (el número depende de `config_entrega.json`). Todos son producidos mediante el CSV **íntegro** verificado por SHA-256; la ejecución se detiene si los datos no coinciden.
5. Abre `config_entrega.json` y completa integrantes, grupo, docente y `github_url`. Ejecuta otra vez `python scripts/generate_report.py` para actualizar portada y URL **sin editar el Word manualmente**.
6. Sube el repositorio a GitHub, incluyendo los scripts y el `README.md`. Si requieres incluir los resultados del entrenamiento, añade los CSV/PNG de `results/` y opcionalmente los pesos de `models/` según permisos del repositorio. El CSV original de IBM se obtiene de su fuente, no debe distribuirse sin revisar sus condiciones.

**Campos deliberadamente editables:** `config_entrega.json` conserva marcadores para integrantes, docente, grupo y URL de GitHub. No se completan sin información del equipo.


## Generación automática al subir a GitHub (recomendado)

El repositorio incluye `.github/workflows/entrega.yml`. Al publicarlo en una rama `main` o `master` con GitHub Actions habilitado, la automatización:

1. Obtiene el dataset de IBM con validación SHA-256;
2. Entrena los seis modelos, compara las tres estrategias y genera SHAP;
3. Regenera el Word/PDF académico usando **métricas reales** y añade automáticamente la URL del repositorio a la sección 6, si `config_entrega.json` aún tiene el marcador de URL;
4. Ejecuta las pruebas y adjunta un ZIP de resultados/modelos al run.

En GitHub abre la pestaña **Actions**, selecciona **Generar entrega ACIF104 desde IBM Telco**, y descarga el artefacto `acif104-informe-resultados-codigo`. Si el flujo no se inicia automáticamente, pulsa **Run workflow**. Los nombres de integrantes, grupo, docente y URL se actualizan en `config_entrega.json` antes de la entrega.
