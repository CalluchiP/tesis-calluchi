# BACKEND.md — Instrucciones para el agente (v2)

Proyecto: **Asistente inteligente con técnicas de Machine Learning para mejorar la evaluación de riesgos tributarios en Trujillo 2026** (tesis UPAO).
Lee este archivo completo antes de tocar código. Este backend **reemplaza** la v1 (que usaba variables de un dataset de la India sin sentido para un contador).

> **Alcance actual (2026-11-11):** por decisión del autor, el producto ya no expone ni
> almacena los grupos GE/GC. Las menciones al diseño experimental que quedan en este
> documento describen el marco de la tesis, no la API vigente. El backend actual
> calcula T/C/P globales y el CSV no incluye la columna `grupo`. Los endpoints de
> indicadores se conservan solo para análisis interno y no se muestran en la interfaz.

## 1. Qué debe lograr (los 3 indicadores de la tesis)
El asistente mejora la evaluación de riesgos tributarios si, frente al grupo control (GC, trabajo manual), el grupo experimental (GE) logra:
- **P – Productividad:** más casos evaluados por semana.
- **T – Tiempo:** menos tiempo por evaluación.
- **C – Costo:** menor costo por evaluación (C = tiempo × tarifa por hora, corregible por el contador).
Todo el sistema gira en torno a medirlos bien. Diseño: experimental puro, GE vs GC, 30 registros por grupo, pruebas Shapiro-Wilk → t de Student / U de Mann-Whitney (α = 0.05).

## 2. Flujo del usuario (contador)
1. Inicia sesión.
2. Abre un caso → el frontend llama `POST /api/evaluaciones/iniciar` (arranca el cronómetro de T; devuelve `sesion`).
3. Ingresa el caso de **una de dos formas**:
   - **Archivos:** sube Registro de Ventas, PDT 621 y (opcional) Registro de Compras (CSV/Excel; plantillas descargables) + completa unos pocos datos de la empresa.
   - **Formulario guiado:** escribe los montos agregados de 12 meses.
4. El backend valida, procesa, predice y devuelve: **nivel (Bajo/Medio/Alto)**, probabilidades, **alertas explicadas con qué revisar**, variables influyentes, tiempo y costo.
5. El contador puede **corregir el costo** y descargar el reporte.
6. Un administrador/investigador consulta `/api/indicadores` y exporta `/api/indicadores/exportar.csv` para el análisis estadístico.

## 3. Arquitectura (diagrama aprobado)
Interfaz web → Flask { Autenticación → Servicio de evaluación → Gestión de datos (BD) · Reportes · Registro de tiempos } → Módulo ML (preprocesamiento → modelo → nivel de riesgo) · PostgreSQL (SQLite en desarrollo).
Pipeline offline (una sola vez): datos → preprocesamiento → entrenamiento y comparación de **3 modelos (Random Forest, XGBoost, SVM)** → evaluación (Precisión, Recall, F1) → modelo + preprocesamiento guardados en archivo.

```
app/routes.py            endpoints /api/*
app/models.py            Usuario, Evaluacion, RegistroTiempo
app/services/            auth, validacion, archivos (CSV/Excel), alertas (reglas), predictor (ML), reportes
ml/features.py           CONTRATO de variables + construir_features() (misma función en entrenamiento y producción)
ml/generar_dataset.py    dataset sintético a partir de reglas expertas
ml/train.py              entrenamiento offline de los 3 modelos
docs/REGLAS_RIESGO.md    reglas de riesgo (validar con un contador)
models/                  random_forest/xgboost/svm.joblib, modelo_riesgo.joblib (el mejor), metricas.json
```

## 4. Datos de entrenamiento (leer con cuidado)
- No existen datos tributarios reales públicos de contribuyentes peruanos (reserva tributaria, Art. 85 C.T.). Por eso el dataset es **sintético, generado con reglas expertas** (`docs/REGLAS_RIESGO.md`), con ruido que simula el criterio del evaluador. Esto coincide con la limitación ya redactada en la tesis (§2.5).
- **Las métricas actuales (F1 macro ≈ 0.90) miden qué tan bien el modelo aprende esas reglas; NO son desempeño real en Trujillo.** No las presentes como tal. Redáctalas como "validación técnica del prototipo".
- La validez descansa en que **un contador revise y valide las reglas** (juicio de experto). Mejora futura: reemplazar por 30–60 casos reales anonimizados etiquetados por un contador (mismas columnas de `ml/features.CAMPOS` + columna `riesgo` 0/1/2) y reentrenar.
- Preprocesamiento: variables derivadas (brecha de ventas, % compras de riesgo, desviación de margen vs. rubro, etc.), imputación por mediana, estandarización y one-hot, todo **dentro del Pipeline guardado**, de modo que la predicción en línea es idéntica al entrenamiento.
- Selección: mayor F1 macro en validación cruzada de 5 pliegues; los 3 modelos se conservan para comparar en la tesis. `MODELO_ACTIVO` en `.env` fuerza uno.

## 5. API (JSON, prefijo `/api`, `Authorization: Bearer <token>`)
| Ruta | Uso |
|---|---|
| `GET /health` · `GET /opciones` | estado; regímenes, rubros y márgenes de referencia (para selects) |
| `GET /plantillas/{ventas|compras|pdt621}.csv` | plantillas de archivo |
| `POST /auth/registro` · `POST /auth/login` | `{nombre,email,password,tarifa_hora?}` / `{email,password}` |
| `GET/PATCH /usuarios/yo` | perfil; `PATCH {tarifa_hora}` |
| `POST /evaluaciones/iniciar` | → `{sesion}` (cronómetro de T) |
| `POST /evaluaciones` | `{referencia?, sesion?, datos:{…}}` formulario |
| `POST /evaluaciones/archivo` | multipart: `ventas`, `pdt621`, `compras?` + campos del caso + `referencia`, `sesion` |
| `GET /evaluaciones`, `/evaluaciones/<id>`, `/evaluaciones/<id>/reporte` | historial, detalle, reporte HTML |
| `PATCH /evaluaciones/<id>/costo` | `{costo: 12.5}` corrige; `{costo: null}` vuelve al calculado |
| `GET /indicadores` · `GET /indicadores/exportar.csv` | T, C, P globales · datos por caso para estadística |
| `GET /modelo` | métricas de los 3 modelos |

**Campos de `datos` (12 meses, soles):** `regimen` (mype_tributario|regimen_general|regimen_especial), `rubro` (comercio|servicios|manufactura|construccion), `antiguedad_anios`, `ventas_comprobantes`, `ventas_declaradas`, `compras_declaradas`, `compras_proveedores_riesgo`, `gastos_no_deducibles`, `meses_fuera_plazo` (0-12), `multas_previas`, `meses_saldo_favor` (0-12).
**Archivos:** ventas → `periodo, base_imponible, estado`; pdt621 → `periodo, ventas_declaradas, compras_declaradas`; compras → `periodo, base_imponible, estado_proveedor, deducible`. Códigos: 401 sin sesión, 404 ajeno, 422 validación (`detalle` por campo).
**Indicadores:** T = promedio de `duracion_seg` (`metodo: sesion` = desde que abre el caso; `servidor` = solo procesamiento, evitar). C = duración(h) × `tarifa_hora`, o el costo corregido. P = casos por semana.

## 6. Reglas de trabajo
1. Cambios pequeños y dirigidos; no regeneres archivos enteros por un ajuste menor.
2. No cambies variables sin actualizar `ml/features.py`, `generar_dataset.py`, `alertas.py`, reentrenar y ajustar tests.
3. Cada cambio con su prueba; `python -m pytest -q` en verde antes de terminar.
4. Nunca RUC, DNI ni razón social reales: `referencia` es un alias anonimizado.
5. `SECRET_KEY` y credenciales solo en `.env`. Contraseñas solo con hash.
6. La tarifa por hora es un parámetro de la tesis (S/ 35 es un valor de ejemplo): debe sustentarse (p. ej. remuneración promedio de un contador en Trujillo).
7. Si algo es ambiguo, pregunta antes de inventar.

## 7. Ejecución
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m ml.generar_dataset && python -m ml.train
python -m pytest -q
python run.py                                          # http://127.0.0.1:5000/api/health
```
