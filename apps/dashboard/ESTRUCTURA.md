# Estructura del dashboard

Esta estructura conserva el comportamiento de la plantilla previa; los scripts clásicos
comparten el mismo ámbito global y se cargan en el mismo orden lógico.

## Plantillas

| Archivo | Apartado | Responsabilidad |
| --- | --- | --- |
| `templates/dashboard/index.html` | Compartido | Layout, menú lateral, encabezado, filtros, modal y carga ordenada de scripts. |
| `templates/dashboard/sections/resumen-general.html` | Resumen General | KPIs y gráficas de síntesis. |
| `templates/dashboard/sections/datos-individuo.html` | Datos del Individuo | Visualizaciones sociodemográficas. |
| `templates/dashboard/sections/exploracion-fisica.html` | Exploración Física | Antropometría, vitales y auscultación. |
| `templates/dashboard/sections/factores-modificables.html` | Factores Modificables | Riesgos modificables. |
| `templates/dashboard/sections/factores-emergentes.html` | Factores Emergentes | Riesgos emergentes. |
| `templates/dashboard/sections/antecedentes-familiares.html` | Antecedentes Familiares | Antecedentes y carga familiar. |
| `templates/dashboard/sections/historia-no-cardio.html` | Historia No Cardio | Comorbilidades no cardiovasculares. |
| `templates/dashboard/sections/covid-19.html` | COVID-19 | Infección y secuelas. |
| `templates/dashboard/sections/electrocardiograma.html` | Electrocardiograma | Resultados ECG. |

## JavaScript

| Archivo | Apartado | Responsabilidad |
| --- | --- | --- |
| `static/dashboard/js/core/dashboard-core.js` | Compartido | Datos, filtros, slicers, cálculo de KPIs, helpers y coordinación de gráficas. |
| `static/dashboard/js/core/dashboard-export.js` | Compartido | Modal y exportación de las vistas. |
| `static/dashboard/js/sections/resumen-general.js` | Resumen General | Tendencia, factores modificables globales, categoría de personal y riesgo por sexo. |
| `static/dashboard/js/sections/datos-individuo.js` | Datos del Individuo | Pirámide edad-sexo y distribuciones sociodemográficas. |
| `static/dashboard/js/sections/exploracion-fisica.js` | Exploración Física | IMC, dispersión IMC-cintura, PA y auscultación. |
| `static/dashboard/js/sections/factores-modificables.js` | Factores Modificables | Tratamiento, tóxicos, actividad física y PREDIMED. |
| `static/dashboard/js/sections/factores-emergentes.js` | Factores Emergentes | Sueño, estrés, personalidad y exposición. |
| `static/dashboard/js/sections/antecedentes-familiares.js` | Antecedentes Familiares | Padre/madre, carga, edad y coexistencia. |
| `static/dashboard/js/sections/historia-no-cardio.js` | Historia No Cardio | Comorbilidad, salud mental, respiratorio, reuma y alergias. |
| `static/dashboard/js/sections/covid-19.js` | COVID-19 | Infección, secuelas, categoría y sexo. |
| `static/dashboard/js/sections/electrocardiograma.js` | Electrocardiograma | Ritmo, intervalos, anomalías y frecuencia. |

## Orden de carga de scripts

| Orden | Archivo |
| ---: | --- |
| 1 | `static/dashboard/js/core/dashboard-core.js` |
| 2 | `static/dashboard/js/sections/resumen-general.js` |
| 3 | `static/dashboard/js/sections/datos-individuo.js` |
| 4 | `static/dashboard/js/sections/exploracion-fisica.js` |
| 5 | `static/dashboard/js/sections/factores-modificables.js` |
| 6 | `static/dashboard/js/sections/factores-emergentes.js` |
| 7 | `static/dashboard/js/sections/antecedentes-familiares.js` |
| 8 | `static/dashboard/js/sections/historia-no-cardio.js` |
| 9 | `static/dashboard/js/sections/covid-19.js` |
| 10 | `static/dashboard/js/sections/electrocardiograma.js` |
| 11 | `static/dashboard/js/core/dashboard-export.js` |

## Tests

| Ruta | Cobertura |
| --- | --- |
| `apps/dashboard/tests.py` | Servicio, vista, API, ocho bloques, clasificación y ausencia de defaults clínicos. |
| `apps/dashboard/test_questionnaire.py` | Catálogo, cobertura de controles/modelos, valores registrados, privacidad y alias. |
| `apps/dashboard/test_xss.py` | Serialización JSON segura de valores almacenados para el dashboard. |
| `tests/frontend/questionnaire.cjs` | Renderizado, filtros y exportación del cuestionario no integrado. |

## Definiciones clínicas

| Concepto | Ubicación |
| --- | --- |
| HTA | `apps/dashboard/services.py`: comparaciones TAS/TAD 140/90 y clasificación de PA; disperso, sin constante nombrada. |
| Diabetes | `apps/dashboard/services.py`: `is_dm_lab` con glucosa ≥126; disperso, sin constante nombrada. |
| Dislipemia | `apps/dashboard/services.py`: `is_dl_lab` con total ≥200, LDL ≥130 o TG ≥150; disperso, sin constante nombrada. |
| Riesgo alto | `apps/dashboard/services.py`: `factors`, `factores_riesgo_count` y umbral 2; `dashboard-core.js`: `altoCnt`. |
| Actividad física | `apps/dashboard/services.py`: `r_act_val` y `actividad_fisica`; `dashboard-core.js`: KPI; `sections/factores-modificables.js` y `sections/resumen-general.js`: gráficas. Dispersa, sin constante nombrada. |

## CSS

| Archivo | Responsabilidad |
| --- | --- |
| `static/dashboard/css/dashboard.css` | Estilos compartidos y estilos existentes de las vistas. |
| `static/dashboard/css/questionnaire.css` | Estilos del dashboard del cuestionario; no modificado durante la separación. |

## Datos y servidor

| Archivo | Responsabilidad |
| --- | --- |
| `views.py` | Entrega datos agregados a la plantilla y API. |
| `services.py` | Consulta ORM, normalización y cálculos; porcentajes sobre registros con dato, coincidentes con los KPI filtrados en JS. |
| `urls.py` | Rutas del dashboard y de su API. |
