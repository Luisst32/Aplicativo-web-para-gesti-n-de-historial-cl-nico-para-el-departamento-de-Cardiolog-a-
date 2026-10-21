# Progreso de la reestructuración

## Checklist de Ramas
- [x] Respaldo `backup-antes-estructura` creado
- [x] Respaldo `backup-antes-correccion` creado
- [x] feature/django-setup (Recreada limpia como `feature/django-setup-clean`, original preservada como `feature/django-setup-old`)
- [ ] feature/ui-templates (Estado: Mezclada - Siguiente en procesar: recreación `-clean` con `templates/` y `static/`)
- [ ] feature/security (Estado: Mezclada - Pendiente recreación -clean en `apps/security/`)
- [ ] feature/catalog (Estado: Mezclada - Pendiente recreación -clean en `apps/catalog/`)
- [ ] feature/clinical (Estado: Mezclada - Pendiente recreación -clean en `apps/clinical/`)
- [ ] feature/audit (Estado: Mezclada - Pendiente recreación -clean en `apps/audit/`)
- [ ] feature/dashboard (Estado: Mezclada - Pendiente recreación -clean en `apps/dashboard/`)
- [ ] feature/chatbot (Estado: Mezclada - Pendiente recreación -clean en `apps/chatbot/`)

## Diagnóstico y Estado de Aislamiento por Rama (`git diff --name-only main...<rama>`)
| Rama | Carpeta Permitida | Archivos Dentro | Archivos Fuera | Estado |
| :--- | :--- | :---: | :---: | :---: |
| `feature/django-setup-clean` | `config/`, `apps/__init__.py`, `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md` | 10 | 0 | **Completada y 100% Aislada** |
| `feature/ui-templates` | `templates/`, `static/` | 6 | 53 (`config/`, `manage.py`, `assets/`, `css/`, `js/`) | **Mezclada** (Pendiente) |
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

## Rama procesada: `feature/django-setup-clean`
- Rama original preservada: `feature/django-setup-old`.
- Base: Creada desde `main`.
- Archivos incluidos:
  - `config/__init__.py`
  - `config/settings.py` (con `INSTALLED_APPS` incluyendo las 6 apps, `AUTH_USER_MODEL='security.User'`, `STATIC_URL='/static/'`, `STATICFILES_DIRS=[BASE_DIR / 'static']`, `TEMPLATES` con `APP_DIRS=True`, `sys.path` apuntando a `apps/`, PostgreSQL con variables de entorno `.env`).
  - `config/urls.py` (con includes de `security.urls`, `clinical.urls`, `dashboard.urls`, `chatbot.urls`).
  - `config/asgi.py`, `config/wsgi.py`
  - `apps/__init__.py`
  - `manage.py`
  - `requirements.txt` (con `Django`, `psycopg2-binary`, `python-dotenv`, etc.)
  - `.env.example`
  - `.gitignore`
  - `README.md`
- Verificación de aislamiento: `0` archivos fuera de lo permitido.
- Subida a remoto: `git push -u origin feature/django-setup-clean` ejecutado exitosamente.

## Siguiente paso (requiere confirmación del usuario)
- Procesar `feature/ui-templates`: Recrear `feature/ui-templates-clean` desde `main`, conservando `feature/ui-templates-old`, dejando exclusivamente `templates/` y `static/` (capa global).
