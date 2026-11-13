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
| `static/dashboard/js/sections/*.js` | Sección homónima | Renderizador y gráficas del apartado. |
| `static/dashboard/js/questionnaire.js` | Cuestionario | Dashboard del catálogo de preguntas; permanece independiente. |

## CSS

| Archivo | Responsabilidad |
| --- | --- |
| `static/dashboard/css/dashboard.css` | Estilos compartidos y estilos existentes de las vistas. |
| `static/dashboard/css/questionnaire.css` | Estilos del dashboard del cuestionario; no modificado durante la separación. |

## Datos y servidor

| Archivo | Responsabilidad |
| --- | --- |
| `views.py` | Entrega datos agregados a la plantilla y API. |
| `services.py` | Consulta ORM, normalización y cálculos de los registros del dashboard. |
| `urls.py` | Rutas del dashboard y de su API. |
