# Progreso de la reestructuración

## Checklist de Ramas
- [x] Respaldo `backup-antes-estructura` creado
- [x] Respaldo `backup-antes-correccion` creado
- [x] Respaldos `backup/feature-*` creados y subidos a GitHub (`audit`, `catalog`, `clinical`, `chatbot`, `security`, `dashboard`, `django-setup`, `ui-templates`)
- [x] feature/django-setup (Recreada limpia como `feature/django-setup-clean`, original preservada como `feature/django-setup-old`)
- [x] feature/ui-templates (Recreada limpia como `feature/ui-templates-clean`, original preservada como `feature/ui-templates-old`)
- [x] feature/security (Recreada limpia como `feature/security-clean`, original preservada como `feature/security-old`)
- [x] feature/catalog (Recreada limpia como `feature/catalog-clean`, original preservada como `feature/catalog-old`)
- [x] feature/clinical (Recreada limpia como `feature/clinical-clean`, original preservada como `feature/clinical-old`)
- [ ] feature/audit (Estado: Mezclada - Siguiente en procesar: recreación `-clean` en `apps/audit/`)
- [ ] feature/dashboard (Estado: Mezclada - Pendiente recreación -clean en `apps/dashboard/`)
- [ ] feature/chatbot (Estado: Mezclada - Pendiente recreación -clean en `apps/chatbot/`)

## Tabla de Propiedad Exclusiva de Archivos Originales (css/, js/, assets/, templates/)
Cada archivo original de `backup-antes-estructura` está asignado a **UNA sola** rama destino para evitar conflictos de renombrado en la integración final:

| Archivo Original | Rama Destino Exclusiva | Ubicación Final en Rama | Notas |
| :--- | :--- | :--- | :--- |
| `assets/css/base.css` | `feature/ui-templates` | `static/css/global/{variables,reset,typography,utilities}.css` | Dividido por ui-templates en capa global |
| `assets/css/layout.css` | `feature/ui-templates` | `static/css/global/layout.css` | Capa global layout (navbar, sidebar, contenedor) |
| `assets/css/pacientes.css` | `feature/clinical` | `apps/clinical/static/clinical/css/pacientes.css` | Exclusivo de clinical (lo común ya fue cubierto en `global/components.css`) |
| `css/formulario.css` | `feature/clinical` | `apps/clinical/static/clinical/css/form.css` | Estilos específicos del formulario clínico |
| `css/formularios-listado.css` | `feature/clinical` | `apps/clinical/static/clinical/css/list.css` | Estilos específicos del listado clínico |
| `css/login.css` | `feature/security` | `apps/security/static/security/css/login.css` | Estilos exclusivos de login |
| `css/dashboard.css` | `feature/dashboard` | `apps/dashboard/static/dashboard/css/dashboard.css` | Estilos exclusivos del dashboard |
| `css/chat.css` | `feature/chatbot` | `apps/chatbot/static/chatbot/css/chat.css` | Estilos exclusivos del chat |
| `css/chat-widget.css` | `feature/chatbot` | `apps/chatbot/static/chatbot/css/chat-widget.css` | Widget flotante del bot |
| `js/menu-usuario.js` | `feature/ui-templates` | `static/js/global/ui.js` | Menú desplegable de usuario y logout común |
| `js/login.js` | `feature/security` | `apps/security/static/security/js/login.js` | Lógica de login |
| `js/formulario.js` | `feature/clinical` | `apps/clinical/static/clinical/js/form.js` | Lógica del formulario clínico |
| `js/formularios-listado.js` | `feature/clinical` | `apps/clinical/static/clinical/js/list.js` | Lógica del listado de pacientes |
| `js/pacientes.js` | `feature/clinical` | `apps/clinical/static/clinical/js/pacientes.js` | Gestión de pacientes y modal de expediente clínico |
| `js/dashboard.js` | `feature/dashboard` | `apps/dashboard/static/dashboard/js/dashboard.js` | Lógica e inicialización de gráficos del dashboard |
| `assets/data/dashboard-cardiounemi-data.js` | `feature/dashboard` | `apps/dashboard/static/dashboard/js/dashboard-data.js` | **TEMPORAL** (mock mientras se conecta al ORM) |
| `js/chat-engine.js` | `feature/chatbot` | `apps/chatbot/static/chatbot/js/chat.js` | Motor y lógica del chat |
| `assets/img/logo-cardiounemi.png` | `feature/ui-templates` | `static/assets/images/logo-cardiounemi.png` | Logo compartido |
| `assets/img/logo-cardiounemi-transparent.png` | `feature/ui-templates` | `static/assets/images/logo-cardiounemi-transparent.png` | Logo compartido transparente |
| `assets/vendor/chart.umd.min.js` | `feature/dashboard` | `apps/dashboard/static/dashboard/vendor/chart.umd.min.js` | Librería vendor exclusiva de gráficos |
| `assets/vendor/apexcharts.min.js` | `feature/dashboard` | `apps/dashboard/static/dashboard/vendor/apexcharts.min.js` | Librería vendor exclusiva de gráficos |
| `assets/vendor/marked.min.js` | `feature/chatbot` | `apps/chatbot/static/chatbot/vendor/marked.min.js` | Librería vendor de Markdown para el chat |
| `assets/vendor/katex/*` | `feature/chatbot` | `apps/chatbot/static/chatbot/vendor/katex/*` | Librería vendor y fuentes KaTeX para fórmulas |
| `templates/login-minimalista.html` | `feature/security` | `apps/security/templates/security/login.html` | Template de login |
| `templates/formulario-clinica.html` | `feature/clinical` | `apps/clinical/templates/clinical/form.html` | Template de ficha clínica |
| `templates/formularios-listado.html` | `feature/clinical` | `apps/clinical/templates/clinical/list.html` | Template de lista de historias |
| `templates/dashboard-cardiounemi.html` | `feature/dashboard` | `apps/dashboard/templates/dashboard/index.html` | Template del dashboard |
| `templates/chat.html` | `feature/chatbot` | `apps/chatbot/templates/chatbot/chat.html` | Template del chat |
| *(nuevo template maestro)* | `feature/ui-templates` | `templates/base.html` | Layout global base HTML5 |

## Diagnóstico y Estado de Aislamiento por Rama (`git diff --name-only main...<rama>`)
| Rama | Carpeta Permitida | Archivos Dentro | Archivos Fuera | Estado |
| :--- | :--- | :---: | :---: | :---: |
| `feature/django-setup-clean` | `config/`, `apps/__init__.py`, `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md` | 10 | 0 | **Completada y 100% Aislada** |
| `feature/ui-templates-clean` | `templates/`, `static/` | 14 | 0 | **Completada y 100% Aislada** |
| `feature/security-clean` | `apps/security/` | 10 | 0 | **Completada y 100% Aislada** |
| `feature/catalog-clean` | `apps/catalog/` | 8 | 0 | **Completada y 100% Aislada** |
| `feature/clinical-clean` | `apps/clinical/` | 19 | 0 | **Completada y 100% Aislada** |
| `feature/audit` | `apps/audit/` | 0 (`audit/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** (Siguiente) |
| `feature/dashboard` | `apps/dashboard/` | 0 (rama recién creada de develop) | 62 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |
| `feature/chatbot` | `apps/chatbot/` | 0 (`chatbot/` está en la raíz) | 67 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |

## Decisiones tomadas y Respuestas del Usuario
- Creadas ramas de respaldo `backup-antes-estructura`, `backup-antes-correccion` y `backup/feature-*` para proteger el historial completo (subidas a GitHub con push normal).
- Reglas de aislamiento estricto activas:
  1. NUNCA `push --force`.
  2. NO `git merge develop` en ramas feature.
  3. No usar `git rm` para limpiar ramas mezcladas; recrear limpio desde `main` (`feature/<rama>-clean`) conservando la original como `-old`.
  4. NO hacer merge a `develop` hasta indicación explícita al final.
  5. Verificación obligatoria con `git diff --name-only main...HEAD | grep -v "^<permitidos>"` que debe resultar vacío.
  6. Subir ramas `-clean` como ramas nuevas con `git push origin <rama>-clean` normal.
  7. Migraciones: no se corren `makemigrations` en ramas feature aisladas por dependencias cruzadas (`catalog.Institution`). Se generarán en `develop` en la integración final en el orden estricto: `catalog -> security -> clinical -> audit -> dashboard -> chatbot`.
- Respuestas confirmadas por el usuario:
  1. `chat-widget.css` y su JS van a `apps/chatbot/static/chatbot/` e inclusión en otras páginas mediante partial `{% include "chatbot/widget.html" %}`. No duplicar CSS en otras apps.
  2. `assets/data/dashboard-cardiounemi-data.js` -> `apps/dashboard/static/dashboard/js/dashboard-data.js` (**TEMPORAL**, mock mientras se conecta al ORM/services).
  3. Librerías vendor: `chart.umd.min.js` y `apexcharts.min.js` a `apps/dashboard/static/dashboard/vendor/`. `marked.min.js` y `katex/` a `apps/chatbot/static/chatbot/vendor/`. Logos a `static/assets/images/`.
  4. De `pacientes.css`: solo pasa a `static/css/global/components.css` lo que se use en 2 o más páginas; la rama `clinical` NO modificará `static/css/global/`, únicamente limpiará de su `pacientes.css` lo ya existente en global.
  5. La rama local `static-templates` es el commit inicial original (commit `9a6b1a8` / merge `6121e64`) creado por Luis antes de iniciar la integración Django; se mantiene intacta sin tocarla.
  6. **Paso final en develop**: Se realizará un commit de limpieza en `develop` que elimina los archivos originales obsoletos de la raíz (`css/`, `js/`, `assets/`, `templates/*.html`), tras integrar todas las ramas y verificar el funcionamiento completo.
  7. **Pendiente en base.html / ui-templates**: `base.html` actual no tiene sidebar estático forzado (envuelve directamente `{% block content %}`), permitiendo que login se renderice centrado sin sidebar. Como mejora opcional se anotó añadir un bloque `{% block sidebar %}`.
  8. **Pendiente en django-setup**: En la integración final, configurar en `config/settings.py`: `LOGIN_URL = 'security:login'`, `LOGIN_REDIRECT_URL = 'dashboard:index'`, `LOGOUT_REDIRECT_URL = 'security:login'`.
  9. **REGLA OBLIGATORIA `db_table`**: En TODOS los modelos de todas las apps, `db_table` usa la sintaxis `'esquema"."tabla'` (sin comillas externas) para que las tablas intermedias M2M de Django (como `groups` y `user_permissions` de `PermissionsMixin`) queden correctamente nombradas en su esquema (`security"."user_groups`, `security"."user_user_permissions`) y no en `public`.
  10. **Paso previo a la integración y migración en develop**: Django no crea esquemas PostgreSQL automáticamente. Antes del primer `makemigrations`/`migrate` en `develop`, se debe ejecutar una sola vez en PostgreSQL:
      ```sql
      CREATE SCHEMA IF NOT EXISTS security;
      CREATE SCHEMA IF NOT EXISTS catalog;
      CREATE SCHEMA IF NOT EXISTS clinical;
      CREATE SCHEMA IF NOT EXISTS audit;
      CREATE SCHEMA IF NOT EXISTS ai;
      ```
  11. **Pendiente de integración - Carga inicial de datos**: NO generar fixtures en ramas aisladas. La carga de datos iniciales (sexo, etnias, provincias, cantones, preguntas y opciones de respuesta de catalog) se realizará tras integrar en develop mediante un script/fixture ordenado.
  12. **REGLA SQL CRUDO Y PALABRAS RESERVADAS**: En consultas SQL crudas o comandos generados a mano, citar siempre `"security"."user"` con comillas dobles. Asimismo, se evitó la palabra reservada de PostgreSQL `order` en todos los modelos renombrándola a `display_order` (en `EducationLevel`, `IncomeRange`, `QuestionnaireSection`, `Question`, `AnswerOption`).
  13. **PENDIENTE DE CONEXIÓN FRONTEND-BACKEND**: En `apps/clinical/`, conectar `form.js` y `pacientes.js` con los endpoints y ORM de Django en `views.py`, ya que actualmente interactúan con datos de prueba/mock locales.
  14. **CONTRATO ENTRE RAMAS (Nombres de URL)**:
      - `security:login`, `security:logout`
      - `clinical:form`, `clinical:list`
      - `dashboard:index`
      - `chatbot:chat`
      Cada aplicación define obligatoriamente `app_name` con el nombre de su app.
  15. **WIDGET DE CHATBOT AUTOSUFICIENTE**: `apps/chatbot/templates/chatbot/widget.html` cargará su propio CSS (`chat-widget.css`), librerías vendor (`marked.min.js`, `katex`) y script del motor JS (`chat.js`). Las demás aplicaciones únicamente incluyen `{% include "chatbot/widget.html" %}`.
  16. **PENDIENTES PARA LA INTEGRACIÓN FINAL EN DEVELOP**:
      - Absorber en la capa global `static/css/global/` las variables de color locales definidas en el `:root` de `list.css`.
      - Migrar las funciones auxiliares `calcIMC` y `calcASC` de `pacientes.js` y `form.js` a `static/js/global/utils.js`.
      - Configurar en `config/settings.py`: `LOGIN_URL = 'security:login'`, `LOGIN_REDIRECT_URL = 'dashboard:index'`.
      - Probar exhaustivamente las columnas generadas en PostgreSQL (`makemigrations`, `sqlmigrate clinical 0001`, `migrate` sobre BD limpia).
      - **Fuente de verdad única**: `bd_final/gemini-code-1792555117056.sql`. El script de `bd/` queda permanentemente descartado.

## Ramas procesadas

### 1. `feature/django-setup-clean`
- Rama original preservada: `feature/django-setup-old`.
- Base: Creada desde `main`.
- Archivos incluidos: `config/` (settings, urls, asgi, wsgi), `apps/__init__.py`, `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
- Aislamiento: 100% verificado (0 archivos fuera de regla).
- Subida a remoto: `origin/feature/django-setup-clean`.

### 2. `feature/ui-templates-clean`
- Rama original preservada: `feature/ui-templates-old`.
- Base: Creada desde `main`, recursos base extraídos de `backup-antes-estructura`.
- Archivos incluidos (14 archivos, 100% en `templates/` y `static/`):
  - `templates/base.html` (template maestro con carga secuencial de CSS/JS y bloques title, content, extra_css, extra_js)
  - `static/css/global/variables.css` (tokens de diseño, colores oficiales CARDIOUNEMI, fuentes, radios, sombras)
  - `static/css/global/reset.css` (reset y box-sizing unificado)
  - `static/css/global/typography.css` (jerarquía tipográfica, encabezados, párrafos, enlaces)
  - `static/css/global/layout.css` (sidebar shell, brand-header, user-menu dropdown y navegación compartida)
  - `static/css/global/components.css` (botones, inputs, selects, field-labels, modales, badges, alertas, tablas, paginación; 0 colores hexadecimales fuera de variables)
  - `static/css/global/utilities.css` (utilidades de layout, flex, grid, texto)
  - `static/js/global/utils.js` (helpers DOM, formateo de fechas y números, cookies CSRF)
  - `static/js/global/api.js` (wrapper fetch con token CSRF de Django y manejo unificado de errores)
  - `static/js/global/ui.js` (inicialización de user menu con avatar, modales, toasts)
  - `static/assets/images/logo-cardiounemi.png` y `logo-cardiounemi-transparent.png`
  - `static/assets/icons/.gitkeep`, `static/assets/fonts/.gitkeep`
- Aislamiento: 100% verificado (0 archivos fuera de `templates/` o `static/`).
- Subida a remoto: `origin/feature/ui-templates-clean`.

### 3. `feature/security-clean`
- Rama original preservada: `feature/security-old`.
- Base: Creada desde `main`.
- Archivos incluidos (10 archivos, 100% en `apps/security/`):
  - `apps/security/__init__.py`
  - `apps/security/apps.py` (`name = "security"`)
  - `apps/security/models.py` (`Role`, `UserManager`, `User` con `AbstractBaseUser` y `PermissionsMixin`, `UserRole` con `UniqueConstraint`, `institution` nullable, `db_table = 'security"."...'`)
  - `apps/security/admin.py` (registro de `UserAdmin` con inlines de `UserRole`, `RoleAdmin`)
  - `apps/security/views.py` (`login_view`, `logout_view` con Django Auth auténtico)
  - `apps/security/urls.py` (`security:login`, `security:logout`)
  - `apps/security/templates/security/login.html` (extiende `base.html`, bloque extra_css/extra_js, form con `{% csrf_token %}`)
  - `apps/security/static/security/css/login.css` (estilos de tarjeta de login con variables CSS)
  - `apps/security/static/security/js/login.js` (toggle de password, validación sin mocks ni credenciales)
  - `apps/security/migrations/__init__.py` (sin migraciones locales hasta integración en develop)
- Aislamiento: 100% verificado (`git diff --name-only main...HEAD | grep -v "^apps/security/"` es vacío).
- Subida a remoto: `origin/feature/security-clean`.

### 4. `feature/catalog-clean`
- Rama original preservada: `feature/catalog-old`.
- Base: Creada desde `main`.
- Archivos incluidos (8 archivos, 100% en `apps/catalog/`):
  - `apps/catalog/__init__.py`
  - `apps/catalog/apps.py` (`name = "catalog"`)
  - `apps/catalog/models/__init__.py` (importa y expone los 18 modelos)
  - `apps/catalog/models/geography.py` (`Country`, `Province`, `Canton`, `Institution`)
  - `apps/catalog/models/demographics.py` (`Sex`, `Ethnicity`, `StaffCategory`, `ProfessionalCategory`, `EducationLevel`, `IncomeRange`, `MaritalStatus`, `LivingSituation`, `HousingType`, `WorkSchedule`, `EcgRhythm`)
  - `apps/catalog/models/questionnaire.py` (`QuestionnaireSection`, `Question`, `AnswerOption`)
  - `apps/catalog/admin.py` (registro de los 18 modelos con inlines de `Question` y `AnswerOption`)
  - `apps/catalog/migrations/__init__.py`
- Reglas aplicadas y correcciones:
  - `db_table = 'catalog"."...'` en todos los modelos.
  - Corrección de palabra reservada PostgreSQL: todos los campos `order` renombrados a `display_order` (en `EducationLevel`, `IncomeRange`, `QuestionnaireSection`, `Question`, `AnswerOption`, constraints, `ordering` y `admin.py`).
  - `Sex.sex_id`: SmallIntegerField manual sin autoincremento (0 a 9) con `CheckConstraint(condition=...)`.
  - `Question.response_type`: Choices `OPTION`, `NUMERIC`, `TEXT`, `BOOLEAN` con `CheckConstraint(condition=...)`.
  - `AnswerOption.scores_predimed`: booleano para puntuación PREDIMED.
  - Relaciones foráneas con `on_delete=models.PROTECT`, salvo `AnswerOption.question` con `CASCADE`.
- Aislamiento: 100% verificado (`git diff --name-only main...HEAD | grep -v "^apps/catalog/"` es vacío).
- Subida a remoto: `origin/feature/catalog-clean` (commit `87ae384`).

### 5. `feature/clinical-clean`
- Rama original preservada: `feature/clinical-old`.
- Base: Creada limpia desde `main`, recursos extraídos de `backup-antes-estructura`.
- Archivos incluidos (19 archivos, 100% en `apps/clinical/`):
  - `apps/clinical/__init__.py`
  - `apps/clinical/apps.py` (`name = "clinical"`, `verbose_name = "Gestión Clínica"`)
  - `apps/clinical/models/__init__.py` (importa y expone los 8 modelos clínicos)
  - `apps/clinical/models/patient.py` (`Patient`, `db_table = 'clinical"."patient'`, jerarquía de nacimiento `ck_patient_birth_hierarchy`, FKs por string a `catalog.Institution`, `catalog.Sex`, `catalog.Ethnicity`, `catalog.Canton`, `catalog.Country`, `security.User`)
  - `apps/clinical/models/visit.py` (`Visit`, `db_table = 'clinical"."visit'`, relación 1:1 con `Patient`, `study_year` como `GeneratedField(ExtractYear('visit_date'), db_persist=True)`, FKs a catálogos sociodemográficos y `security.User`)
  - `apps/clinical/models/exams.py` (5 satélites 1:1 con `Visit` usando `OneToOneField(primary_key=True)`):
    - `Anthropometry`: `weight_kg`, `height_cm`, `waist_circumference_cm`, `bmi` (GeneratedField `Round(F('weight_kg') / Power(F('height_cm') / 100.0, 2), 2)`), `body_surface_area` (GeneratedField Mosteller formula), checks de peso, talla y perímetro.
    - `VitalSigns`: `systolic_bp`, `diastolic_bp`, `oxygen_saturation`, `heart_rate`, soplos, auscultación, checks de rango y orden sistólica/diastólica.
    - `Electrocardiogram`: `rhythm` (FK catalog), FC, intervalos PR/QRS/QT/QTc, eje, hipertrofia ventricular izquierda, bloqueo de rama, alteraciones repolarización.
    - `Echocardiogram`: dimensiones VI/VD, hipertrofia, `lvef_percentage` con check 10-90%, disfunción diastólica, gradientes aórticos.
    - `Laboratory`: perfil hemático, renal, lipídico, glucémico y hepático completo según `bd_final`.
  - `apps/clinical/models/answers.py` (`VisitAnswer`, `db_table = 'clinical"."visit_answer'`, `UniqueConstraint(fields=['visit', 'question'])`, `CheckConstraint` que obliga exactamente un valor: opción, numérico o texto).
  - `apps/clinical/admin.py` (registro de los 8 modelos con inlines apilados/tabulares en `VisitAdmin`).
  - `apps/clinical/views.py` (`form_view` y `list_view` protegidos con `@login_required`).
  - `apps/clinical/urls.py` (`clinical:form`, `clinical:list`).
  - `apps/clinical/templates/clinical/form.html` (extiende `base.html`, bloques `extra_css`, `content`, `extra_js`, widget chatbot incluido mediante `{% include "chatbot/widget.html" %}`).
  - `apps/clinical/templates/clinical/list.html` (extiende `base.html`, bloques `extra_css`, `content`, `extra_js`, widget chatbot incluido mediante `{% include "chatbot/widget.html" %}`).
  - `apps/clinical/static/clinical/css/form.css` (0 colores hexadecimales, uso de variables CSS).
  - `apps/clinical/static/clinical/css/list.css` (0 colores hexadecimales en reglas de estilo, variables CSS locales scoped para badges y estados).
  - `apps/clinical/static/clinical/css/pacientes.css` (depurado de redundancias con `components.css`, 0 colores hexadecimales).
  - `apps/clinical/static/clinical/js/form.js` (lógica de pasos y validación del formulario).
  - `apps/clinical/static/clinical/js/list.js` (lógica de filtros y tabla de listado).
  - `apps/clinical/static/clinical/js/pacientes.js` (modal de paciente y lógica de expediente clínico).
  - `apps/clinical/migrations/__init__.py` (sin migraciones locales hasta integración en develop).
- Aislamiento: 100% verificado (`git diff --name-only main...HEAD | grep -v "^apps/clinical/"` es vacío).
- Subida a remoto: `origin/feature/clinical-clean` (commit `787979c`).

## Siguiente paso (requiere confirmación del usuario)
- Procesar `feature/audit`: Recrear `feature/audit-clean` desde `main`, conservando `feature/audit-old`, ubicando la app en `apps/audit/` (model ChangeLog en esquema `"audit"`, admin de solo lectura, sin templates ni static).

