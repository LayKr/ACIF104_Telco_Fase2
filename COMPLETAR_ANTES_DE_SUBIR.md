# Entrega ACIF104 — campos que debe completar el grupo

La carpeta contiene informe final, arquitectura visual, código, README, pruebas, frontend, backend y benchmark real sobre el CSV IBM verificado. La ejecución técnica quedó completa. Solo permanecen pendientes los datos académicos que el equipo debe proporcionar.

1. Abrir `config_entrega.json` y completar integrantes, docente y número de grupo.
2. Publicar el repositorio, pegar su URL en `github_url` y ejecutar `python scripts/generate_report.py` otra vez.
3. Verificar que el nombre final sea `docs/acif104_s6_grupoN.pdf`, donde N es el grupo real.
4. Ejecutar `pytest -q` y revisar que GitHub Actions finalice correctamente antes de entregar.

No reemplazar métricas ni figuras manualmente. El informe las lee de los JSON y CSV generados por el pipeline.

## Estado técnico verificado el 14 de noviembre de 2026

- Dataset IBM: 970.457 bytes, 7.043 filas y SHA-256 `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91`.
- Se ejecutaron 3 modelos ML, 3 MLP y 3 técnicas de balanceo, además de la condición sin balanceo.
- El audit registró cero filas compartidas entre entrenamiento, validación y prueba; el preprocesador se ajustó solo con train.
- Se generaron métricas por partición, curvas, matrices de confusión y SHAP global/local reales.
- Las cinco referencias científicas de 2026 se contrastaron con sus DOI y páginas editoriales.
- Frontend, backend y modelo real aprobaron 7 pruebas automatizadas.
