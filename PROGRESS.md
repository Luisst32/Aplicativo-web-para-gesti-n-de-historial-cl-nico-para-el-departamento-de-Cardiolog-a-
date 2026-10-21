# Progreso de la reestructuración

## Checklist de Ramas
- [x] Respaldo `backup-antes-estructura` creado
- [x] Respaldo `backup-antes-correccion` creado
- [x] feature/django-setup (Recreada limpia como `feature/django-setup-clean`, original preservada como `feature/django-setup-old`)
- [ ] feature/ui-templates (En proceso: recreación `-clean` con `templates/base.html` y `static/` global)
- [ ] feature/security (Estado: Mezclada - Pendiente recreación -clean en `apps/security/`)
- [ ] feature/catalog (Estado: Mezclada - Pendiente recreación -clean en `apps/catalog/`)
- [ ] feature/clinical (Estado: Mezclada - Pendiente recreación -clean en `apps/clinical/`)
- [ ] feature/audit (Estado: Mezclada - Pendiente recreación -clean en `apps/audit/`)
- [ ] feature/dashboard (Estado: Mezclada - Pendiente recreación -clean en `apps/dashboard/`)
- [ ] feature/chatbot (Estado: Mezclada - Pendiente recreación -clean en `apps/chatbot/`)

## Tabla de Propiedad Exclusiva de Archivos Originales (css/, js/, assets/, templates/)
Cada archivo original de `backup-antes-estructura` está asignado a **UNA sola** rama destino para evitar conflictos de renombrado en la integración final:

| Archivo Original | Rama Destino Exclusiva | Ubicación Final en Rama | Notas |
| :--- | :--- | :--- | :--- |
| `assets/css/base.css` | `feature/ui-templates` | `static/css/global/{variables,reset,typography,utilities}.css` | Dividido por ui-templates en capa global |
| `assets/css/layout.css` | `feature/ui-templates` | `static/css/global/layout.css` | Capa global layout (navbar, sidebar, contenedor) |
| `assets/css/pacientes.css` | `feature/clinical` | `apps/clinical/static/clinical/css/pacientes.css` | Exclusivo de clinical (componentes comunes van a `global/components.css`) |
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
| `feature/ui-templates` | `templates/`, `static/` | 6 | 53 (`config/`, `manage.py`, `assets/`, `css/`, `js/`) | **Mezclada** (En proceso `-clean`) |
| `feature/security` | `apps/security/` | 0 (`security/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |
| `feature/catalog` | `apps/catalog/` | 0 (`catalog/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |
| `feature/clinical` | `apps/clinical/` | 0 (`clinical/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |
| `feature/audit` | `apps/audit/` | 0 (`audit/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |
| `feature/dashboard` | `apps/dashboard/` | 0 (rama recién creada de develop) | 62 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |
| `feature/chatbot` | `apps/chatbot/` | 0 (`chatbot/` está en la raíz) | 67 (raíz con templates, css, js, config) | **Mezclada** (Pendiente) |

## Decisiones tomadas y Respuestas del Usuario
- Creadas ramas de respaldo `backup-antes-estructura` y `backup-antes-correccion` para proteger el historial completo (subidas a GitHub con push normal).
- Reglas de aislamiento estricto activas:
  1. NUNCA `push --force`.
  2. NO `git merge develop` en ramas feature.
  3. No usar `git rm` para limpiar ramas mezcladas; recrear limpio desde `main` (`feature/<rama>-clean`) conservando la original como `-old`.
  4. NO hacer merge a `develop` hasta indicación explícita al final.
  5. Verificación obligatoria con `git diff --name-only main...HEAD | grep -v "^<permitidos>"` que debe resultar vacío.
  6. Subir ramas `-clean` como ramas nuevas con `git push origin <rama>-clean` normal.
- Respuestas confirmadas por el usuario:
  1. `chat-widget.css` y su JS van a `apps/chatbot/static/chatbot/` e inclusión en otras páginas mediante partial `{% include "chatbot/widget.html" %}`. No duplicar CSS en otras apps.
  2. `assets/data/dashboard-cardiounemi-data.js` -> `apps/dashboard/static/dashboard/js/dashboard-data.js` (**TEMPORAL**, mock mientras se conecta al ORM/services).
  3. Librerías vendor: `chart.umd.min.js` y `apexcharts.min.js` a `apps/dashboard/static/dashboard/vendor/`. `marked.min.js` y `katex/` a `apps/chatbot/static/chatbot/vendor/`. Logos a `static/assets/images/`.
  4. De `pacientes.css`: solo pasa a `static/css/global/components.css` lo que se use en 2 o más páginas; lo exclusivo de pacientes permanece en `clinical`.
  5. La rama local `static-templates` es el commit inicial original (commit `9a6b1a8` / merge `6121e64`) creado por Luis antes de iniciar la integración Django; se mantendrá intacta sin tocarla.

## Rama procesada: `feature/django-setup-clean`
- Rama original preservada: `feature/django-setup-old`.
- Base: Creada desde `main`.
- Archivos incluidos: `config/` (settings, urls, asgi, wsgi), `apps/__init__.py`, `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
- Aislamiento: 100% verificado (0 archivos fuera de regla).
- Subida a remoto: `origin/feature/django-setup-clean`.
