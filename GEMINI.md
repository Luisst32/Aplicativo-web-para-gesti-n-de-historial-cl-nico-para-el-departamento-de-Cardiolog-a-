Estoy trabajando en un proyecto Django con PostgreSQL y Git Flow.
Las apps, modelos y ramas YA están en inglés. Necesito que dejes la
estructura EXACTA que describo abajo en CADA rama feature (cada app con
sus propios templates y static, y una capa GLOBAL compartida para no
repetir código) y que luego las fusiones a develop, sin perder
historial ni trabajo.

RAMAS
main, develop, feature/django-setup, feature/ui-templates,
feature/security, feature/catalog, feature/clinical, feature/audit,
feature/dashboard (NUEVA, hay que crearla desde develop),
feature/chatbot.

APPS
security, catalog, clinical, audit, dashboard (NUEVA), chatbot.

DÓNDE VA CADA TIPO DE ARCHIVO
- Templates compartidos (base.html, index.html)
    -> templates/
- Templates de una app
    -> apps/<app>/templates/<app>/<archivo>.html
    (SIEMPRE con la subcarpeta del mismo nombre de la app, para evitar
     choques de nombres)
- CSS y JS globales (usados en 2 o más páginas)
    -> static/css/global/ y static/js/global/
- CSS y JS exclusivos de una app
    -> apps/<app>/static/<app>/css/ y apps/<app>/static/<app>/js/
- Imágenes, íconos, logos y fuentes compartidas
    -> static/assets/ (subcarpetas images/, icons/, fonts/)
- Recursos exclusivos de una app
    -> apps/<app>/static/<app>/assets/
- Nunca poner .html dentro de static/.
- Revisa el contenido actual de css/, js/ y assets/ en la raíz y
  clasifica cada archivo por extensión y uso. Si un archivo no está
  claro, pregúntame antes de moverlo.

PRINCIPIO: NO REPETIR CÓDIGO
Todo lo que se use en 2 o más páginas va en la capa global. Los
archivos de cada app solo contienen lo exclusivo de esa app.

ESTILOS GLOBALES (static/css/global/)
- variables.css   -> custom properties (:root): colores, tipografías,
                     tamaños, espaciados, radios, sombras. Los colores
                     y fuentes NO se escriben a mano en otros
                     archivos: se usan con var(--nombre).
- reset.css       -> reset/normalize y box-sizing.
- typography.css  -> títulos, párrafos, enlaces.
- layout.css      -> contenedor, grid/flex comunes, navbar, sidebar,
                     footer, header.
- components.css  -> botones, inputs, selects, labels, formularios,
                     tarjetas, tablas, badges, alertas, modales,
                     paginación.
- utilities.css   -> clases utilitarias.
Orden de carga (en base.html): variables -> reset -> typography ->
layout -> components -> utilities. NO usar @import en los CSS.

SCRIPTS GLOBALES (static/js/global/)
- utils.js -> funciones comunes (fechas, validaciones, helpers DOM).
- api.js   -> wrapper de fetch con token CSRF de Django y manejo de
              errores.
- ui.js    -> comportamientos compartidos (menú/sidebar, modales,
              notificaciones, confirmaciones).

AUDITORÍA DE DUPLICADOS (hacer en feature/ui-templates)
1. Compara los CSS y JS actuales y detecta reglas, variables,
   colores, fuentes y funciones repetidas entre archivos.
2. Muéstrame un resumen de lo que piensas mover a global/ ANTES de
   hacerlo.
3. Muévelo a la capa global y elimina el duplicado de los archivos
   de cada app.
4. Reemplaza colores y fuentes escritos a mano por var(--...).
5. No cambies el aspecto visual: el resultado debe verse igual.

EQUIVALENCIA DE TEMPLATES (nombre actual -> nuevo)
- login-minimalista.html     -> apps/security/templates/security/login.html
- dashboard-cardiounemi.html -> apps/dashboard/templates/dashboard/index.html
- formulario-clinica.html    -> apps/clinical/templates/clinical/form.html
- formularios-listado.html   -> apps/clinical/templates/clinical/list.html
- chat.html                  -> apps/chatbot/templates/chatbot/chat.html
- index.html (si existe)     -> templates/index.html
catalog y audit NO tienen templates ni static.

ESTRUCTURA FINAL DEL PROYECTO
proyecto/
├── config/
├── templates/
│   ├── base.html
│   └── index.html            (si existe)
├── static/
│   ├── css/global/
│   ├── js/global/
│   └── assets/{images,icons,fonts}/
├── apps/
│   ├── security/
│   ├── catalog/
│   ├── clinical/
│   ├── audit/
│   ├── dashboard/            (NUEVA)
│   └── chatbot/
├── manage.py, requirements.txt, .env.example, .gitignore, README.md

ESTRUCTURA QUE DEBE TENER CADA RAMA (lo que esa rama posee y toca)

== feature/django-setup ==
config/
├── __init__.py
├── settings.py   (INSTALLED_APPS con django.contrib.staticfiles y las
│                  6 apps: security, catalog, clinical, audit,
│                  dashboard, chatbot; AUTH_USER_MODEL="security.User",
│                  STATIC_URL="/static/",
│                  STATICFILES_DIRS=[BASE_DIR/"static"],
│                  TEMPLATES: DIRS=[BASE_DIR/"templates"] y
│                  APP_DIRS=True (obligatorio para leer los templates
│                  dentro de las apps), sys.path con BASE_DIR/"apps",
│                  lectura de .env)
├── urls.py       (include de las urls de security, clinical,
│                  dashboard y chatbot)
├── asgi.py
└── wsgi.py
apps/__init__.py
manage.py, requirements.txt, .env.example, .gitignore, README.md

== feature/ui-templates ==
templates/
├── base.html     (carga TODO lo global una sola vez, en el orden
│                  indicado; define {% block title %},
│                  {% block content %}, {% block extra_css %},
│                  {% block extra_js %})
└── index.html    (si existe)
static/
├── css/global/
│   ├── variables.css
│   ├── reset.css
│   ├── typography.css
│   ├── layout.css
│   ├── components.css
│   └── utilities.css
├── js/global/
│   ├── utils.js
│   ├── api.js
│   └── ui.js
└── assets/
    ├── images/
    ├── icons/
    └── fonts/
(esta rama NO contiene templates ni static de las apps)

== feature/security ==
apps/security/
├── __init__.py
├── apps.py       (name = "security")
├── models.py     (User, Role, UserRole)
├── admin.py
├── views.py      (login/logout, render "security/login.html")
├── urls.py
├── templates/security/login.html
├── static/security/
│   ├── css/login.css
│   └── js/login.js
└── migrations/__init__.py

== feature/catalog ==
apps/catalog/
├── __init__.py
├── apps.py       (name = "catalog")
├── models.py     (Country, Province, Canton, Institution, Sex,
│                  Ethnicity, catálogos sociodemográficos y motor de
│                  cuestionarios: Section, Question, AnswerOption)
├── admin.py
└── migrations/__init__.py
(sin views, urls, templates ni static; si models.py crece mucho,
 convertirlo en paquete models/ con __init__.py, geography.py,
 demographics.py y questionnaire.py)

== feature/clinical ==
apps/clinical/
├── __init__.py
├── apps.py       (name = "clinical")
├── models.py     (Patient, Visit, Anthropometry, VitalSigns,
│                  Electrocardiogram, Echocardiogram, Laboratory,
│                  VisitAnswer)
├── admin.py
├── views.py      (usa "clinical/form.html" y "clinical/list.html")
├── urls.py
├── templates/clinical/
│   ├── form.html
│   └── list.html
├── static/clinical/
│   ├── css/{form.css, list.css}
│   └── js/{form.js, list.js}
└── migrations/__init__.py
(el dashboard NO va aquí: pertenece a la app dashboard)

== feature/audit ==
apps/audit/
├── __init__.py
├── apps.py       (name = "audit")
├── models.py     (ChangeLog)
├── admin.py      (solo lectura)
└── migrations/__init__.py
(sin views, urls, templates ni static)

== feature/dashboard (NUEVA) ==
Crear la rama desde develop y la app con
`python manage.py startapp dashboard apps/dashboard`
(crear antes la carpeta apps/dashboard).
apps/dashboard/
├── __init__.py
├── apps.py       (name = "dashboard")
├── views.py      (vista del dashboard: render
│                  "dashboard/index.html"; calcula indicadores y
│                  estadísticas con el ORM sobre los models de
│                  clinical y catalog, por ejemplo totales de
│                  pacientes, visitas, promedios de IMC y presión,
│                  distribución por sexo y por año)
├── services.py   (funciones de consulta/agregación reutilizables,
│                  para no meter lógica pesada en views.py)
├── urls.py       (ruta del dashboard)
├── templates/dashboard/index.html
├── static/dashboard/
│   ├── css/dashboard.css
│   └── js/dashboard.js   (gráficos y lógica propia del dashboard)
└── migrations/__init__.py
Notas:
- Sin models propios: lee los datos de clinical y catalog con
  `from clinical.models import ...`. Por eso depende de esas dos
  apps y debe fusionarse DESPUÉS de ellas.
- Si el dashboard tiene login obligatorio, proteger la vista con
  @login_required.
- Si dashboard.js usa una librería de gráficos (Chart.js u otra),
  cárgala en {% block extra_js %} de este template, no en base.html.
- Si no hay models, `makemigrations` no generará migraciones para
  esta app; es normal.

== feature/chatbot ==
apps/chatbot/
├── __init__.py
├── apps.py       (name = "chatbot")
├── models.py     (BotQuery, esquema "ai")
├── admin.py
├── views.py      (usa "chatbot/chat.html")
├── urls.py
├── services.py   (consultas ORM / lógica del bot)
├── templates/chatbot/chat.html
├── static/chatbot/
│   ├── css/chat.css
│   └── js/chat.js
└── migrations/__init__.py

(Los nombres de CSS/JS de cada app son una guía: usa los nombres
 reales de mis archivos, renombrándolos al inglés cuando haga falta.)

REGLAS DE LOS HTML
- Todo template de app hace {% extends "base.html" %} y {% load static %}.
- Rutas globales: {% static 'css/global/components.css' %}.
- Rutas de app: {% static 'dashboard/css/dashboard.css' %},
  {% static 'chatbot/js/chat.js' %}.
- Cada página carga SOLO su CSS/JS específico en {% block extra_css %}
  y {% block extra_js %}. Lo global se carga solo en base.html.
- Sin estilos ni scripts inline repetidos: si se repiten, van a global/.
- Ningún HTML debe quedar con rutas relativas viejas (../css/...).
- Las rutas url(...) dentro de los CSS deben apuntar a los assets con
  la ruta relativa correcta.

ESQUEMAS POSTGRESQL (db_table = '"esquema"."tabla"')
security, catalog, clinical, audit, ai
(dashboard no crea tablas)

REGLA PRINCIPAL
Cada rama toca SOLO su carpeta apps/<app>/ (incluidos sus templates y
static). Las únicas ramas que tocan templates/ y static/ de la raíz
son django-setup y ui-templates. Si una rama necesita cambiar algo
fuera de sus carpetas (por ejemplo config/settings.py o
config/urls.py), hazlo en un commit aparte y pequeño.

PROCESO
1. Muestra el estado actual: git status, git branch -a y el árbol de
   carpetas de cada rama. Lista el contenido de css/, js/ y assets/
   y dime cómo piensas clasificar cada archivo y qué código repetido
   moverías a global/, ANTES de tocar nada. Avísame si hay cambios
   sin guardar. Crea el respaldo
   `git branch backup-antes-estructura` antes de empezar.
2. Crea la rama feature/dashboard desde develop (si no existe).
3. Procesa las ramas EN ESTE ORDEN (por dependencias):
   django-setup -> ui-templates -> security -> catalog -> clinical
   -> audit -> dashboard -> chatbot.
4. Para cada rama:
   a. git checkout <rama> && git merge develop (traer lo último).
   b. Dejar su estructura idéntica al árbol de arriba, usando
      `git mv` para conservar el historial. Crear los archivos que
      falten (vacíos o con lo mínimo necesario).
   c. Actualizar imports, ForeignKeys ("security.User", etc.), urls,
      rutas de templates, rutas {% static %} y apps.py.
   d. Verificar: python manage.py check y
      python manage.py makemigrations --check. Verifica además que
      no queden rutas rotas a CSS/JS/imágenes
      (grep "href=\|src=" en los templates) y que no haya estilos o
      funciones duplicadas entre global/ y los archivos de las apps.
   e. Commits pequeños con prefijos (feat, refactor, fix, chore).
   f. Hacer merge a develop y verificar que develop sigue sin
      errores antes de pasar a la siguiente rama.
5. Migraciones: cada app genera las suyas en su propia rama. Si hay
   conflictos de migraciones, avísame antes de borrar nada.
6. Al terminar, confirma que cada rama quedó sincronizada con develop
   y dame un resumen: qué se movió, qué se renombró, qué código se
   unificó en global/ y qué falta.

REGLAS
- No uses git push --force.
- No borres ramas, migraciones ni archivos sin preguntarme.
- No modifiques la lógica de negocio ni el diseño visual, solo
  estructura, nombres, rutas y eliminación de código duplicado.
- Si hay un conflicto de merge, explícame la decisión que tomes.
- Si la BD ya tiene migraciones aplicadas con otra estructura,
  avísame: puede ser necesario recrearla (esquemas security, catalog,
  clinical, audit, ai).

Al iniciar cualquier sesión, lee también PROGRESS.md y continúa desde el primer pendiente.
