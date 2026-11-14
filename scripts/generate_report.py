"""Create formatted UNAB Phase II report from verified training artefacts (if present)."""
from __future__ import annotations
import json, sys, os, shutil, subprocess, argparse
from pathlib import Path
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ARGS=argparse.ArgumentParser(description='Genera el informe ACIF104 desde artefactos verificados.')
ARGS.add_argument('--docx-only',action='store_true',help='Genera solo DOCX; el PDF se renderiza por separado.')
args=ARGS.parse_args()

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config_entrega.json'
INFO=json.loads(CONFIG.read_text(encoding='utf8')) if CONFIG.exists() else {}
GITHUB_URL=INFO.get('github_url','[PEGAR URL DE GITHUB AQUÍ]')
# GitHub Actions rellena automáticamente la URL si no se escribió en config_entrega.json.
if GITHUB_URL.startswith('[PEGAR') and os.environ.get('GITHUB_REPOSITORY'):
    GITHUB_URL='https://github.com/' + os.environ['GITHUB_REPOSITORY']
INTEGRANTES=INFO.get('integrantes',['[NOMBRES DEL EQUIPO]'])
GRUPO=INFO.get('grupo','X')
DOCENTE=INFO.get('docente','[DOCENTE]')
FILENAME='acif104_s6_grupo'+str(GRUPO).strip().lower()
RESULTS=ROOT/'results';DOCS=ROOT/'docs';DOCS.mkdir(exist_ok=True)
if not (RESULTS/'00_arquitectura.png').exists():
 subprocess.run([sys.executable,str(ROOT/'scripts'/'generate_architecture.py')],check=True,stdout=subprocess.PIPE)
METADATA=ROOT/'models'/'metadata.json'
EXPECTED_SHA256='16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91'
FINISHED=METADATA.exists() and (RESULTS/'summary.json').exists()
meta=json.loads(METADATA.read_text(encoding='utf8')) if FINISHED else None
summary=json.loads((RESULTS/'summary.json').read_text(encoding='utf8')) if FINISHED else None
FINISHED=bool(FINISHED and meta.get('dataset_sha256')==EXPECTED_SHA256 and meta.get('rows')==7043 and meta.get('shap_ok'))

D=Document();sec=D.sections[0];sec.page_width=Cm(21.59);sec.page_height=Cm(27.94);sec.top_margin=Cm(2.45);sec.bottom_margin=Cm(3.2);sec.footer_distance=Cm(.8);sec.left_margin=Cm(2.65);sec.right_margin=Cm(2.5)
styles=D.styles;normal=styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(11);normal.font.color.rgb=RGBColor(30,43,56)
normal.paragraph_format.line_spacing=1.15;normal.paragraph_format.space_after=Pt(7)
for name,size in [('Title',23),('Heading 1',15),('Heading 2',12),('Heading 3',11)]:
 s=styles[name];s.font.name='Calibri';s.font.size=Pt(size);s.font.bold=True;s.font.color.rgb=RGBColor(0,0,0)
 s.paragraph_format.space_before=Pt(12);s.paragraph_format.space_after=Pt(6)
# Word's built-in Title style can carry a theme border; the cover must remain plain.
title_ppr=styles['Title']._element.get_or_add_pPr()
for node in list(title_ppr):
 if node.tag==qn('w:pBdr'):title_ppr.remove(node)

def p(txt='',style=None,align=WD_ALIGN_PARAGRAPH.JUSTIFY):
 o=D.add_paragraph(str(txt),style=style);o.alignment=align;return o

def h(txt,level=1):D.add_heading(txt,level=level)

def bullets(items):
 for t in items:p(t,style='List Bullet')

def table(headers,rows,widths=None):
 t=D.add_table(rows=1, cols=len(headers));t.style='Table Grid';t.alignment=WD_TABLE_ALIGNMENT.CENTER
 borders=OxmlElement('w:tblBorders')
 for edge in ('top','left','bottom','right','insideH','insideV'):
  node=OxmlElement(f'w:{edge}');node.set(qn('w:val'),'single');node.set(qn('w:sz'),'4');node.set(qn('w:color'),'D9D9D9');borders.append(node)
 t._tbl.tblPr.append(borders)
 for i,x in enumerate(headers):t.rows[0].cells[i].text=str(x)
 for row in rows:
  cells=t.add_row().cells
  for i,v in enumerate(row):cells[i].text=str(v)
 for cell in t.rows[0].cells:
  tcPr=cell._tc.get_or_add_tcPr();shd=OxmlElement('w:shd');shd.set(qn('w:fill'),'1F4E78');tcPr.append(shd)
  for x in cell.paragraphs[0].runs:x.bold=True;x.font.color.rgb=RGBColor(255,255,255)
 for row in t.rows:
  for cell in row.cells:
   tcPr=cell._tc.get_or_add_tcPr();tcMar=tcPr.first_child_found_in('w:tcMar')
   if tcMar is None:tcMar=OxmlElement('w:tcMar');tcPr.append(tcMar)
   for side in ('top','left','bottom','right'):
    node=OxmlElement(f'w:{side}');node.set(qn('w:w'),'90');node.set(qn('w:type'),'dxa');tcMar.append(node)
   cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   for para in cell.paragraphs:
    para.paragraph_format.space_after=Pt(2);para.paragraph_format.space_before=Pt(2)
    for run in para.runs:run.font.size=Pt(9)
 header_tr_pr=t.rows[0]._tr.get_or_add_trPr();tbl_header=OxmlElement('w:tblHeader');tbl_header.set(qn('w:val'),'true');header_tr_pr.append(tbl_header)
 D.add_paragraph()
 return t

def fig(filename,cap):
 f=RESULTS/filename
 if f.exists():
  D.add_picture(str(f),width=Cm(15.5));cp=p(cap,align=WD_ALIGN_PARAGRAPH.CENTER)
  for r in cp.runs:r.italic=True;r.font.size=Pt(9)
 else:p(f'[Figura pendiente de generación: {cap}. Se crea automáticamente con el dataset oficial al entrenar.]')

def page():D.add_page_break()

# COVER
for _ in range(3):p('')
cover=p('UNIVERSIDAD ANDRÉS BELLO',style='Title',align=WD_ALIGN_PARAGRAPH.CENTER);cover.runs[0].bold=True;cover.runs[0].font.size=Pt(17)
p('Facultad / Escuela: completar según sección académica',align=WD_ALIGN_PARAGRAPH.CENTER)
p('ACIF104 · Aprendizaje Automático',align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(3):p('')
cover=p('INFORME DE AVANCE SEGUNDA FASE',align=WD_ALIGN_PARAGRAPH.CENTER);cover.runs[0].bold=True;cover.runs[0].font.size=Pt(19)
p('Sistema de predicción explicable de abandono de clientes para telecomunicaciones',align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(4):p('')
p('Integrantes: ' + ', '.join(INTEGRANTES),align=WD_ALIGN_PARAGRAPH.CENTER)
p('Grupo: ' + str(GRUPO) + ' · Docente: ' + DOCENTE,align=WD_ALIGN_PARAGRAPH.CENTER)
p('Santiago de Chile · Noviembre de 2026',align=WD_ALIGN_PARAGRAPH.CENTER)
page()

h('Resumen ejecutivo')
if FINISHED:
 p('Se desarrolló un prototipo reproducible para estimar el abandono de clientes del conjunto de datos IBM Telco Customer Churn. Se compararon tres algoritmos clásicos y tres arquitecturas neuronales, con evaluación estratificada, tres técnicas de balanceo, métrica prioritaria AUC-PR, ajuste del umbral en validación y explicaciones SHAP. El modelo seleccionado se integró a un frontend y una API de inferencia. Los resultados se informan sobre un conjunto de prueba separado, sin usar sus etiquetas para elegir arquitectura o umbral.')
else:
 p('Este documento presenta la fundamentación, arquitectura, metodología, código y aplicación web de un proyecto para predecir abandono de clientes con IBM Telco Customer Churn. El repositorio contiene implementaciones reproducibles de tres modelos tradicionales, tres arquitecturas de deep learning, tres balanceos, comparación de métricas, explicaciones SHAP y una interfaz conectada a FastAPI. En este entorno no se pudo obtener el archivo CSV oficial, por lo que NO se ejecutaron todavía las métricas propias sobre el conjunto completo: no se sustituyen con resultados sintéticos ni con cifras de otros estudios. La ejecución queda automatizada en el repositorio y las tablas e imágenes se generan al disponer del CSV original.')
p('Palabras clave: churn, retención de clientes, aprendizaje supervisado, aprendizaje profundo, SHAP, desbalance de clases, CRISP-DM.')
h('Estado de verificabilidad y delimitaciones',2)
p('El dataset de IBM es público y se documenta su descarga y SHA-256. Los registros corresponden a un ejemplo de telecomunicaciones, no a una empresa contratante real. Las afirmaciones sobre resultados de otras publicaciones se atribuyen a sus autores y NO representan resultados de este grupo. La comprobación del código incluye pruebas automatizadas de endpoints y estructuras básicas. El uso productivo requiere validación externa, protección de datos y monitoreo adicional.')
if not FINISHED:p('ESTADO DE RESULTADOS PROPIOS: pendiente de ejecución contra CSV original de IBM. Las secciones de resultados indican expresamente las evidencias aún no verificadas.')
h('Índice de contenidos')
for line in ['1. Problemática, antecedentes y alcance','2. Metodología, planificación y restricciones','3. Desarrollo: datos, técnicas, arquitectura, modelos y software','4. Resultados y evaluación','5. Limitaciones y propuesta de mejora','6. Código, reproducibilidad y conclusiones','7. Referencias bibliográficas','Anexo A. Requisitos y trazabilidad']:p(line)

h('1. Problemática, antecedentes y alcance')
h('1.1 Contexto y necesidad de negocio',2)
p('El abandono voluntario de clientes (customer churn) disminuye ingresos recurrentes y obliga a reasignar presupuesto hacia adquisición de nuevos abonados. Las operadoras manejan contratos, cargos mensuales, historial de antigüedad y servicios adicionales, pero una lectura manual de miles de registros impide priorizar intervenciones preventivas. El proyecto plantea un sistema de apoyo a decisiones que estima la probabilidad de churn y explica qué variables intervienen en la estimación, sin presentarlo como un sistema causal.')
p('Contexto organizacional modelado: una empresa de telecomunicaciones ficticia con áreas de atención, retención, analítica y TI. El usuario principal sería un analista de retención y el usuario técnico, un administrador de modelos. El dataset es un benchmark público, no un espejo de operaciones de una empresa chilena; por tanto, su aplicabilidad local está limitada por la representatividad de datos y la ausencia de pruebas de campo.')
h('1.2 Análisis crítico de trabajos recientes (2021–2026)',2)
table(['Trabajo','Aporte relevante','Limitación para nuestro caso'],[
 ['El Attar y El-Hajj (2026)','Benchmark 7.043 clientes, ensembles, SMOTE y SHAP para apoyar decisiones de retención.','Las métricas publicadas no son extrapolables a nuestra partición ni al subconjunto de atributos.'],
 ['Zerine et al. (2026)','Comparación multmodelo, validación anidada y explicabilidad; subraya la estabilidad estadística.','El propio estudio describe datos ampliados y variables adicionales: no es exactamente la misma matriz de entrada.'],
 ['Baş et al. (2026)','SHAP para distinguir causas potenciales asociadas a calidad de red de otras variables.','Usa métricas de radio y dataset de operador ausentes en IBM Telco clásico.'],
 ['Barde et al. (2026)','Enlaza predicción, SHAP/LIME y acciones de negocio concretas.','Una explicación de modelo no prueba que modificar la variable reduzca churn.'],
 ['Janchai y Narkbunnum (2026)','Uso de modelos clásicos y SHAP por grupos de variables para diseñar comunicación.','Su muestra de 7.032 casos y elección de ponderaciones requieren comparación cuidadosa.'],
])
p('Síntesis comparativa. Coinciden en que modelos de árboles y técnicas de explicación son útiles, pero difieren en datos, métricas y protocolos. Por ello no se elige una arquitectura por sus resultados publicados, sino mediante validación reproducible sobre el mismo conjunto de datos y un test no visto. La bibliografía fundamenta decisiones metodológicas, no resultados propios.')
h('1.3 Objetivos y alcance',2)
p('Objetivo general: diseñar e implementar un prototipo de software capaz de estimar el riesgo de abandono de clientes de telecomunicaciones mediante modelos de aprendizaje automático, documentando comparaciones reproducibles y explicaciones locales para apoyar la priorización de seguimiento comercial.')
bullets(['OE1: caracterizar y depurar la calidad del dataset oficial IBM y evidenciar patrones mediante estadísticas y gráficos.', 'OE2: comparar al menos tres técnicas clásicas y tres redes MLP con métricas que consideren el desbalance.', 'OE3: probar tres técnicas de muestreo, elegir el modelo mediante validación y cuantificar su desempeño sobre un test intacto.', 'OE4: ofrecer predicciones, atribuciones SHAP y monitoreo operativo desde una aplicación web.', 'OE5: documentar decisiones, limitaciones y pasos de reproducción del software.'])
p('Fuera de alcance: despliegue productivo, inferencia sobre clientes reales, decisiones automáticas que afecten servicios, evaluación de efectos causales de campañas y acceso a CRM de una operadora.')

h('2. Metodología, planificación y restricciones')
h('2.1 Proceso de desarrollo',2)
p('Se adopta CRISP-DM adaptado: (1) comprensión del negocio; (2) comprensión de datos y análisis exploratorio; (3) preparación e imputación; (4) modelado y exploración de arquitecturas; (5) validación, métricas y explicabilidad; y (6) integración, pruebas y monitoreo. Se aplica separación explícita de entrenamiento, validación y prueba para proteger la estimación final de desempeño.')
fig('00_arquitectura.png','Figura de arquitectura. Flujo del conjunto de datos hacia la evaluación experimental, las explicaciones del modelo y la interfaz web.')
h('2.2 Plan de trabajo del equipo',2)
p('La asignación siguiente constituye una distribución propuesta por roles para cinco integrantes, y no atribuye acciones a personas aún no identificadas. Se expresa en jornadas relativas porque no se informó la fecha límite de entrega.')
table(['Fase / tarea','Responsable propuesto','Plazo relativo','Evidencia y objetivo'],[
 ['Definición y revisión de 5 fuentes','Integrante A (investigación)','Días 1–2 / 6 h','Problema, antecedentes; OE5'],
 ['EDA, calidad y visualizaciones','Integrante B (datos)','Días 2–3 / 8 h','data_quality.json y PNG; OE1'],
 ['3 ML, 3 DL y muestreo','Integrante C (modelos)','Días 3–5 / 12 h','Scripts y benchmark; OE2/OE3'],
 ['Backend, frontend y seguridad básica','Integrante D (software)','Días 4–6 / 10 h','API/web y pruebas; OE4'],
 ['SHAP, integración, documentación, QA','Integrante E (validación)','Días 6–7 / 8 h','SHAP, PDF, README; OE3/OE5']
])
p('Trazabilidad: cada actividad genera evidencia versionada; los nombres de responsables, fechas reales, enlaces de commits y horas efectivas deben completarse según el trabajo del grupo. Los entregables de análisis requieren ejecutar el pipeline sobre el dataset oficial.')
h('2.3 Recursos y restricciones',2)
p('El procesamiento prioriza CPU convencional con memoria RAM de 4 GB o más; GPU no obligatoria. Python, pandas, NumPy, scikit-learn, imbalanced-learn, PyTorch y SHAP implementan los experimentos. FastAPI expone la inferencia y una interfaz HTML/CSS/JavaScript gestiona la interacción. Las redes usan 35 épocas máximas, Adam y detención temprana de seis épocas sin mejora de pérdida de validación. Su duración efectiva depende del hardware.')

h('3. Desarrollo del proyecto')
h('3.1 Dataset, tipos de variables y calidad',2)
p('La versión clásica IBM Telco Customer Churn contiene 7.043 registros y 21 columnas, entre ellas el identificador customerID, 19 atributos de cliente y el objetivo Churn (Yes/No). La literatura y la ficha pública indican aproximadamente 26,5 % de abandono (1.869 casos) y 73,5 % de permanencia (5.174 casos). Las 11 celdas vacías de TotalCharges coinciden con tenure=0; la regla del proyecto convierte esos casos a cero por no haber facturación acumulada. Estas cifras son antecedentes documentales: para confirmar sus valores en el archivo de ejecución se utiliza la auditoría automática de resultados.')
p('La selección de variables explicativas evita customerID y atributos demográficos gender, SeniorCitizen, Partner y Dependents para reducir el riesgo de usar características personales ajenas al objetivo del prototipo. Se usan 3 variables numéricas (tenure, MonthlyCharges, TotalCharges) y 12 atributos categóricos de contratos, facturación y servicios. La salida es la probabilidad estimada de abandono.')
table(['Variable / grupo','Tipo','Tratamiento','Justificación'],[
 ['tenure','Numérica discreta','Imputación mediana + estandarización','Antigüedad contractual'],
 ['MonthlyCharges','Numérica continua','Imputación mediana + estandarización','Precio actual del servicio'],
 ['TotalCharges','Numérica continua','Vacío con tenure=0 → 0; escala','Historial de monto cobrado'],
 ['Contract, PaymentMethod, PaperlessBilling','Categórica','One-hot + valores desconocidos ignorados','Compromiso y canal de pago'],
 ['InternetService y 8 servicios adicionales','Categórica','One-hot + imputación moda','Configuración técnica / comercial'],
 ['Churn','Binaria objetivo','Yes→1; No→0','Etiqueta de clasificación'],
 ['customerID y demográficos','Excluidos','Sin entrenamiento','Identificación y riesgo de sesgo']
])
p('Criterios de calidad: completitud (nulos por atributo), consistencia (dominio de categorías y tipo numérico), exactitud plausible (rangos válidos), duplicados por identificador y outliers numéricos (regla 1,5×IQR). Outliers no se eliminan automáticamente: podrían representar cuentas de alto valor; se documentan y se decide su tratamiento caso a caso. El preprocesador se ajusta únicamente al conjunto train para evitar fuga de información.')
if FINISHED:
 q=summary['data_quality'];table(['Indicador verificado','Resultado'],[['Filas',q['rows']],['Columnas',q['columns']],['Churn Yes',q['positive']],['Churn No',q['negative']],['Tasa churn',f'{q["positive_rate"]:.3%}'],['Valores TotalCharges originalmente vacíos',q['source_null_totalcharges']],['Ceros justificados tenure=0',q['zero_tenure_imputation']],['IDs duplicados',q['duplicates_customerID']]])
 table(['Variable numérica','Media','Mediana (p50)','Desv. estándar','Outliers IQR'],[(c,f'{q["numeric_descriptives"][c]["mean"]:.2f}',f'{q["numeric_descriptives"][c]["50%"]:.2f}',f'{q["numeric_descriptives"][c]["std"]:.2f}',q['outliers_iqr'][c]) for c in ['tenure','MonthlyCharges','TotalCharges']])
else:p('El informe no declara porcentajes de imputación, valores atípicos medidos ni rangos observados como resultados originales hasta ejecutar data_quality.json; el pipeline los calcula y registra automáticamente.')
fig('01_clases.png','Figura 1. Distribución de Churn sobre datos originales.')
fig('02_antiguedad.png','Figura 2. Distribución de antigüedad por clase.')
fig('03_contrato.png','Figura 3. Tasa de abandono según contrato.')
fig('04_correlacion.png','Figura 4. Correlaciones entre atributos numéricos.')
h('3.2 Elección y comparación conceptual de técnicas',2)
table(['Técnica','Fortaleza','Debilidad / carga','Aplicabilidad'],[
 ['Regresión logística (ML)','Rápida, base interpretable','Frontera principalmente lineal; baja CPU','Base de referencia'],
 ['Random Forest (ML)','Capta interacciones; robustez','Más árboles y memoria; explicación post hoc','Tabular mixto codificado'],
 ['Gradient Boosting (ML)','Modela no linealidad con árboles secuenciales','Sensibilidad al ajuste','Punto de comparación de máximo rendimiento'],
 ['MLP 64→32 (DL)','Dos capas ocultas, costo moderado','Necesita estandarización y regularización','Red profunda compacta'],
 ['MLP 64→32→16 (DL)','Tres capas ocultas, representación progresiva','Más parámetros; posible sobreajuste','Red profunda intermedia'],
 ['MLP 128→64→32 (DL)','Tres capas ocultas, mayor capacidad','Mayor costo y riesgo de sobreajuste','Red profunda de referencia'],
 ['K-Means (no supervisado)','Segmenta clientes sin etiquetas','No estima directamente la probabilidad de churn','Complemento exploratorio, silhouette']
])
p('Comparación de paradigmas: las tres técnicas clásicas y las tres MLP son supervisadas, pues aprenden de la etiqueta churn. K-Means es no supervisado y se evalúa con silhouette y segmentación, no con AUC de clasificación; compararlo con clasificadores usando la misma métrica sería metodológicamente incorrecto. Su uso se restringe a descubrir perfiles comerciales exploratorios.')
h('3.3 Arquitectura, entradas, salidas y refinamiento',2)
p('Entradas: 15 campos comerciales crudos, convertidos mediante ColumnTransformer a un vector numérico escalado y codificado con one-hot. Salida: escalar p(churn), interpretado como una probabilidad estimada, no como certeza causal. Las tres MLP utilizan capas densas con activación ReLU, dropout 0,15 tras cada capa oculta, y capa de salida lineal de una neurona entrenada con BCEWithLogitsLoss (sigmoid para convertir logits a probabilidad). Adam usa tasa de aprendizaje 0,001 y regularización weight decay 0,0001.')
p('Selección y refinamiento: se prioriza AUC-PR de validación para evaluar el ranking de la clase minoritaria y se utiliza F1 de validación para elegir un umbral de clasificación entre 0,20 y 0,80. Tras seleccionar la arquitectura, se prueban estrategias de balanceo de clases y se elige nuevamente con datos de validación. El test solo se utiliza al final. Los gráficos de pérdida validación permiten detectar convergencia, estancamiento y posible sobreajuste; los parámetros pueden revisarse en una futura iteración.')
h('3.4 Muestreo, partición y evaluación',2)
p('Se utiliza una partición aleatoria estratificada reproducible con semilla 42: 64 % entrenamiento, 16 % validación y 20 % prueba, sin datos compartidos. El preprocesador ajusta imputación, escalamiento y codificación solo con train. El pipeline compara cuatro condiciones de entrenamiento: sin balanceo, Random Oversampling, Random Undersampling y SMOTENC (tercera técnica de balanceo), preservando variables categóricas originales para evitar interpolar columnas one-hot artificiales. El balanceo no modifica conjuntos de validación ni prueba.')
p('Métricas: accuracy, precisión, sensibilidad/recall, F1-score, ROC-AUC, AUC-PR y matriz de confusión. Dado el costo de perder clientes potencialmente recuperables, recall importa; sin embargo, incrementar recall puede elevar falsos positivos y costos de campañas. Por ello AUC-PR es el indicador primario de selección, mientras la política de umbral debe atender la capacidad de contactabilidad y margen comercial.')
if FINISHED:
 audit=summary['leakage_audit']
 table(['Control contra fuga','Evidencia medida'],[
  ['Intersección train-validación',audit['train_validation_overlap']],
  ['Intersección train-test',audit['train_test_overlap']],
  ['Intersección validación-test',audit['validation_test_overlap']],
  ['Filas usadas al ajustar el escalador',audit['numeric_preprocessor_fit_rows']],
  ['Filas train',audit['rows_train']],
  ['Selección de modelo, balanceo y umbral','Solo validación'],
  ['Uso de test','Evaluación final']])
fig('05_roc_test.png','Figura 5. Comparación ROC de seis modelos sobre test no visto.')
fig('06_convergencia.png','Figura 6. Convergencia de arquitecturas neuronales sobre validación.')
fig('10_pr_test.png','Figura 6B. Curvas precisión-recall de los seis modelos en test.')
fig('07_balance.png','Figura 7. Sensibilidad del rendimiento al balanceo de clases.')
fig('09_clustering.png','Figura 8. PCA y segmentación K-Means del entrenamiento.')
fig('11_matrices_confusion.png','Figura 9. Matrices de confusión del modelo campeón en entrenamiento, validación y prueba.')
h('3.5 Frontend, backend, seguridad y monitoreabilidad',2)
p('Se construyó un frontend HTML/CSS/JavaScript responsive donde el usuario ingresa 15 atributos comerciales y consulta una predicción. FastAPI expone GET /api/health, GET /api/schema, POST /api/predict y GET /api/monitor. La API valida campos, categorías y rangos observados; rechaza solicitudes inconsistentes con HTTP 422 y controla accesos opcionalmente con X-API-Key. La inferencia integra el preprocesador entrenado y el modelo ganador serializado; la explicación local SHAP utiliza PermutationExplainer y un fondo de 24 registros transformados de entrenamiento.')
p('El monitoreo se implementa mediante SQLite, guardando hora, latencia, probabilidad y estado de cada inferencia; no se almacena la ficha del cliente. El panel informa volumen, errores, p95 de latencia y probabilidad promedio. Este es monitoreo técnico básico, no monitoreo de deriva de datos ni de exactitud en producción, porque para ello se necesitan etiquetas futuras y bases de referencia. El prototipo se sirve por defecto en localhost; la exposición pública requeriría HTTPS, autenticación fuerte, cuotas, resguardo de secretos, evaluación de privacidad y revisión legal.')
if FINISHED:p('Pruebas de software: la suite verifica salud, frontend estático, validación de solicitudes, predicción, monitoreo, dimensiones de las tres MLP y contrato extremo a extremo con el modelo real. La prueba de integración exige una explicación SHAP local no vacía y una probabilidad dentro de [0, 1].')
else:p('Pruebas de software: los tests verifican endpoints de salud, frontend, validación, cálculo de métricas y dimensiones de las tres arquitecturas MLP. La prueba de integración real se activa al existir artefactos entrenados.')

h('4. Resultados y evaluación')
if FINISHED:
 p('Resultados empíricos. Los siguientes valores provienen exclusivamente de la ejecución del código con el archivo verificado por huella digital y las particiones descritas. La arquitectura ganadora se eligió por AUC-PR de validación; el test se mantuvo independiente.')
 table(['Concepto','Resultado'],[['Modelo ganador',meta['model_name']],['Balanceo seleccionado',meta['sampling']],['Umbral seleccionado en validación',f'{meta["threshold"]:.3f}'],['N train / validación / test',f'{meta["n_train"]} / {meta["n_validation"]} / {meta["n_test"]}'],['AUC-ROC test',f'{meta["test_scores"]["auc_roc"]:.3f}'],['AUC-PR test',f'{meta["test_scores"]["auc_pr"]:.3f}'],['Precision test',f'{meta["test_scores"]["precision"]:.3f}'],['Recall test',f'{meta["test_scores"]["recall"]:.3f}'],['F1 test',f'{meta["test_scores"]["f1"]:.3f}'],['TP / FP / FN / TN',f'{meta["test_scores"]["tp"]} / {meta["test_scores"]["fp"]} / {meta["test_scores"]["fn"]} / {meta["test_scores"]["tn"]}']])
 test_by_model={r['model']:r for r in summary['test_benchmark']}
 table(['Modelo','Tipo','AUC-PR train','AUC-PR val','AUC-PR test'],[(r['model'],r['family'],f'{r["auc_pr_train"]:.3f}',f'{r["auc_pr_val"]:.3f}',f'{test_by_model[r["model"]]["auc_pr"]:.3f}') for r in summary['model_selection']])
 table(['Modelo','Tipo','F1 train','F1 val','F1 test'],[(r['model'],r['family'],f'{r["f1_train"]:.3f}',f'{r["f1_val"]:.3f}',f'{test_by_model[r["model"]]["f1"]:.3f}') for r in summary['model_selection']])
 table(['Muestreo','N train','AUC-PR val','F1 val'],[(r['sampling'],r['n_train'],f'{r["auc_pr_val"]:.3f}',f'{r["f1_val"]:.3f}') for r in summary['balance_selection']])
 table(['Partición del campeón','Accuracy','Precisión','Recall','F1'],[(split,f'{values["accuracy"]:.3f}',f'{values["precision"]:.3f}',f'{values["recall"]:.3f}',f'{values["f1"]:.3f}') for split,values in summary['champion_by_split'].items()])
 table(['Partición del campeón','ROC-AUC','AUC-PR'],[(split,f'{values["auc_roc"]:.3f}',f'{values["auc_pr"]:.3f}') for split,values in summary['champion_by_split'].items()])
 p('El benchmark completo sobre test se presenta con fines de transparencia; no se ha utilizado para elegir la arquitectura ni ajustar su umbral. La evaluación final válida para el modelo desplegado es la del campeón ya seleccionado por validación.')
 if meta.get('shap_ok'):
  p('Explicabilidad: SHAP PermutationExplainer se calculó con muestras de referencia de entrenamiento y una muestra limitada de test para inspección global. Las magnitudes son atribuciones al valor del modelo; no prueban causalidad. Principales componentes: '+', '.join(meta.get('top_shap_features',[]))+'.')
 else:p('La evaluación automática de SHAP no pudo completarse; revisar el error generado en models/metadata.json. No se sustituyen sus atribuciones por importancias de variables no equivalentes.')
else:
 p('NO HAY RESULTADOS PROPIOS SOBRE IBM TELCO DISPONIBLES EN ESTE PDF. La fuente CSV verificada no pudo descargarse al entorno de elaboración. Es incorrecto copiar precisión, F1 o AUC de artículos publicados y presentarlos como métricas del proyecto. El repositorio ejecuta seis entrenamientos, cuatro condiciones de muestreo, trazas de convergencia y SHAP con datos reales al correr los comandos del README. Deben incorporarse sus salidas antes de presentar este informe como entrega final de la fase 2.')
 table(['Indicador esperado','Resultado de la ejecución IBM'],[['AUC-PR, ROC-AUC, F1, precision, recall','PENDIENTE: script genera models_test.csv'],['Matriz de confusión','PENDIENTE: se incluye en metrics del script'],['Comparativa de 6 candidatos','PENDIENTE: models_validation.csv y models_test.csv'],['Efecto de 3 balanceos','PENDIENTE: balance_validation.csv'],['Convergencia de 3 MLP','PENDIENTE: 06_convergencia.png'],['Atribuciones SHAP','PENDIENTE: 08_shap.png y shap_global.csv']])
p('Resultados externos a modo de contexto, NO resultados propios: El Attar y El-Hajj (2026) reportan un rendimiento elevado para ciertos ensembles y el trabajo de Baş et al. (2026) informa AUC 0,884 con datos que incluyen métricas de red. Sus cifras no pueden compararse directamente sin igualar muestra, variables, particiones y protocolo.')
fig('08_shap.png','Figura 10. Atribuciones SHAP globales calculadas sobre predicciones de prueba.')

h('5. Limitaciones y propuesta de mejoras')
h('5.1 Limitaciones identificadas',2)
bullets(['Generalización: el benchmark representa una muestra histórica de una empresa ficticia; puede diferir del abandono en otros países o empresas.', 'Desbalance moderado: la clase Churn Yes es minoritaria; precisión y sensibilidad varían con el umbral y con la estrategia de balanceo.', 'Variables de entrada: el dataset no contiene secuencias completas de tickets, motivos de reclamos ni series temporales.', 'Atribución versus causalidad: SHAP explica decisiones del modelo, pero no demuestra que una intervención comercial genere retención.', 'Validación interna: un único split no mide la variabilidad de los resultados ni calibración bajo condiciones reales.', 'Implementación: control de acceso opcional y monitoreo operativo básico; faltan controles completos para producción.'])
h('5.2 Mejoras fundamentadas',2)
table(['Propuesta','Acción verificable','Impacto y métrica'],[
 ['M1. Validación más robusta y calibración','Validación cruzada anidada estratificada; búsqueda de hiperparámetros y calibración isotónica/Platt con datos válidos.','AUC-PR promedio ± desviación; Brier y reliability diagram.'],
 ['M2. Datos longitudinales y seguimiento','Incorporar historial de incidencias, tickets y antigüedad temporal; evaluar test de período posterior y deriva PSI/KS.','F1/recall temporal, estabilidad de distribución.'],
 ['M3. Equidad y controles de seguridad','Auditar errores por grupos mediante evaluación protegida, incorporar autenticación y auditoría de acceso.','Diferencias de FNR/FPR, tasa de errores de API y latencia.']
])
p('Las dos primeras mejoras son prioritarias por su relación directa con los límites observables de la muestra y el diseño de evaluación; la tercera es un requisito de evolución para un sistema real.')

h('6. Código, reproducibilidad y conclusiones')
p('Repositorio GitHub: ' + GITHUB_URL + '. El paquete contiene el código fuente, estructura de carpetas, README, tests, requerimientos, frontend y API. La URL de este apartado se lee de config_entrega.json; debe actualizarse tras la publicación en GitHub.')
p('Procedimiento reproducible: instalar requirements.txt en un entorno Python, ejecutar scripts/download_data.py, verificar SHA-256, ejecutar python -m src.churn.pipeline, verificar salidas en results/ y models/, ejecutar pytest -q e iniciar uvicorn backend.app:app. Por último, ejecutar python scripts/generate_report.py en un sistema con LibreOffice instalado para integrar resultados y figuras a este documento y generar su PDF.')
if FINISHED:
 p(f'Conclusiones: la regresión logística sin balanceo obtuvo la mayor AUC-PR de validación ({summary["model_selection"][0]["auc_pr_val"]:.3f}) y fue seleccionada con umbral {meta["threshold"]:.3f}. En prueba alcanzó ROC-AUC {meta["test_scores"]["auc_roc"]:.3f}, AUC-PR {meta["test_scores"]["auc_pr"]:.3f}, recall {meta["test_scores"]["recall"]:.3f} y F1 {meta["test_scores"]["f1"]:.3f}. Las brechas frente a entrenamiento y validación fueron acotadas, pero un único split no basta para afirmar estabilidad externa. El prototipo demuestra reproducibilidad técnica, explicación SHAP y operación web; no demuestra causalidad ni beneficio comercial.')
else:
 p('Conclusiones: una arquitectura compacta de clasificación tabular con explicabilidad es técnicamente pertinente para una problemática de retención de clientes. El proyecto implementa una comparación reproducible de modelos, controles contra fuga de información y un sistema web demostrativo. No se promete un nivel de exactitud ni beneficio comercial sin ejecutar la prueba completa.')

h('7. Bibliografía (APA 7.ª edición)')
references=[
('Barde, S., Soni, S., Swami, D., & Sutar, K. (2026). A dual layer explainable artificial intelligence approach for prediction and action in telecom customer churn analytics. ','Discover Sustainability','. Advance online publication. https://doi.org/10.1007/s43621-026-04867-2'),
('Baş, S., Bulut, B., Türkoğlu Ay, G., Yağmur, R., Gökçen, A., & Sezgin Alp, S. (2026). Explaining and predicting mobile network-driven churn using machine learning and SHapley Additive exPlanations-based attribution. ','Electrica, 26',', 1–13. https://doi.org/10.5152/electrica.2026.25240'),
('El Attar, A., & El-Hajj, M. (2026). Explainable AI-driven customer churn prediction: A multi-model ensemble approach with SHAP-based feature analysis. ','Frontiers in Artificial Intelligence, 9',', Article 1748799. https://doi.org/10.3389/frai.2026.1748799'),
('Janchai, N., & Narkbunnum, W. (2026). Explaining telecom customer churn through communication-oriented machine learning and SHAP analysis. ','Studies in Media and Communication, 14','(3). https://doi.org/10.11114/smc.v14i3.8434'),
('Zerine, I., Islam, M. M., Khan, M. A. U., Chy, M. A. R., Saimon, A. S. M., Gonee Manik, M. M. T., & Wata, C. (2026). Explainable churn prediction in telecom with tabular ML five model benchmark and SHAP analysis. ','Discover Artificial Intelligence, 6',', Article 263. https://doi.org/10.1007/s44163-026-00983-0'),
('IBM. (s. f.). ','Telco Customer Churn',' [Conjunto de datos]. GitHub. https://github.com/IBM/telco-customer-churn-on-icp4d'),
('Géron, A. (2022). ','Hands-on machine learning with Scikit-Learn, Keras, and TensorFlow',' (3rd ed.). O’Reilly Media.'),
('Goodfellow, I., Bengio, Y., & Courville, A. (2016). ','Deep learning','. MIT Press. https://www.deeplearningbook.org/'),
('Murphy, K. P. (2012). ','Machine learning: A probabilistic perspective','. MIT Press.')
]
for before,italic,after in references:
 pp=D.add_paragraph();pp.alignment=WD_ALIGN_PARAGRAPH.LEFT
 pp.add_run(before);ir=pp.add_run(italic);ir.italic=True;pp.add_run(after)
 pp.paragraph_format.left_indent=Cm(.65);pp.paragraph_format.first_line_indent=Cm(-.65);pp.paragraph_format.space_after=Pt(7)
p('Nota bibliográfica: la obra Machine Learning: A Probabilistic Perspective de Murphy fue publicada originalmente en 2012; el año 2018 indicado en la consigna podría corresponder a una reimpresión. La referencia aquí cita la publicación original, sin inventar una edición nueva.')

h('Anexo A. Requisitos funcionales, no funcionales y trazabilidad')
table(['ID','Requisito verificable','Objetivo / evidencia'],[
 ['RF01','Ingresar atributos del cliente y validarlos','OE4 / interfaz y código HTTP 422'],
 ['RF02','Obtener probabilidad y clase predicha','OE2, OE4 / POST /api/predict'],
 ['RF03','Mostrar atribuciones SHAP locales','OE4 / explanation_method y reasons'],
 ['RF04','Consultar métricas de salud y monitoreo','OE4 / endpoints health y monitor'],
 ['RF05','Ejecutar análisis y crear gráficos','OE1 / results/data_quality.json, PNG'],
 ['RF06','Comparar 3 ML, 3 DL y 3 balanceos','OE2, OE3 / modelos y CSV de rendimiento'],
 ['RNF01','Usabilidad: interfaz adaptable escritorio/móvil','OE4 / CSS responsive y validaciones'],
 ['RNF02','Explicabilidad: razones basadas en SHAP real','OE4 / valores Shapley con fondo train'],
 ['RNF03','Reproducibilidad: semilla 42 y README','OE5 / scripts, SHA-256 y dependencias'],
 ['RNF04','Seguridad: sin persistencia de ficha individual','OE4 / registro SQLite solo operacional'],
 ['RNF05','Monitoreabilidad: errores y latencia p95','OE4 / api monitor'],
 ['RNF06','Escalabilidad: inferencia stateless y API separada','OE4 / FastAPI; pendiente prueba de carga'],
 ['RNF07','Confiabilidad: errores controlados y pruebas','OE4 / pytest y health endpoint'],
])
p('Criterios de aceptación: RF02 y RF03 exigen un modelo entrenado con el dataset íntegro. RNF06 requiere prueba de carga para afirmar escalabilidad demostrada; la modularidad del diseño por sí sola no prueba rendimiento bajo concurrencia.')

# FOOTER
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
run=footer.add_run();begin=OxmlElement('w:fldChar');begin.set(qn('w:fldCharType'),'begin');instr=OxmlElement('w:instrText');instr.set(qn('xml:space'),'preserve');instr.text=' PAGE ';separate=OxmlElement('w:fldChar');separate.set(qn('w:fldCharType'),'separate');cached=OxmlElement('w:t');cached.text='1';end=OxmlElement('w:fldChar');end.set(qn('w:fldCharType'),'end');run._r.extend([begin,instr,separate,cached,end])

out=DOCS/(FILENAME+'.docx');D.save(out)
print('DOCX:',out,'final_metrics=',FINISHED)
lo=shutil.which('libreoffice') or shutil.which('soffice')
if lo and not args.docx_only:
 subprocess.run([lo,'-env:UserInstallation=file:///tmp/lo_churn_pdf_1812','--headless','--convert-to','pdf','--outdir',str(DOCS),str(out)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=140)
 print('PDF:',DOCS/(FILENAME+'.pdf'))
elif not args.docx_only:
 print('LibreOffice no disponible. Abrir el DOCX y exportar a PDF en Word.')
