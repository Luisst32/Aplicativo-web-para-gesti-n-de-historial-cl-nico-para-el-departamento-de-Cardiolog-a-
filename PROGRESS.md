# Progreso de la reestructuración

## Checklist de Ramas
- [x] Respaldo `backup-antes-estructura` creado
- [x] Respaldo `backup-antes-correccion` creado
- [ ] feature/django-setup (Estado: Mezclada - Pendiente reestructuración limpia)
- [ ] feature/ui-templates (Estado: Mezclada - Pendiente reestructuración limpia)
- [ ] feature/security (Estado: Mezclada - Pendiente recreación -clean en `apps/security/`)
- [ ] feature/catalog (Estado: Mezclada - Pendiente recreación -clean en `apps/catalog/`)
- [ ] feature/clinical (Estado: Mezclada - Pendiente recreación -clean en `apps/clinical/`)
- [ ] feature/audit (Estado: Mezclada - Pendiente recreación -clean en `apps/audit/`)
- [ ] feature/dashboard (Estado: Mezclada - Pendiente recreación -clean en `apps/dashboard/`)
- [ ] feature/chatbot (Estado: Mezclada - Pendiente recreación -clean en `apps/chatbot/`)

## Diagnóstico de Aislamiento por Rama (`git diff --name-only main...<rama>`)
| Rama | Carpeta Permitida | Archivos Dentro | Archivos Fuera | Estado |
| :--- | :--- | :---: | :---: | :---: |
| `feature/django-setup` | `config/`, `apps/__init__.py`, `manage.py`, `requirements.txt`, etc. | 8 | 1 (`templates/.gitkeep`) | **Mezclada** |
| `feature/ui-templates` | `templates/`, `static/` | 6 | 53 (`config/`, `manage.py`, `assets/`, `css/`, `js/`) | **Mezclada** |
| `feature/security` | `apps/security/` | 0 (`security/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** |
| `feature/catalog` | `apps/catalog/` | 0 (`catalog/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** |
| `feature/clinical` | `apps/clinical/` | 0 (`clinical/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** |
| `feature/audit` | `apps/audit/` | 0 (`audit/` está en la raíz) | 68 (raíz con templates, css, js, config) | **Mezclada** |
| `feature/dashboard` | `apps/dashboard/` | 0 (rama recién creada de develop) | 62 (raíz con templates, css, js, config) | **Mezclada** |
| `feature/chatbot` | `apps/chatbot/` | 0 (`chatbot/` está en la raíz) | 67 (raíz con templates, css, js, config) | **Mezclada** |

## Decisiones tomadas
- Creadas ramas de respaldo `backup-antes-estructura` y `backup-antes-correccion` para proteger el historial completo.
- `GEMINI.md` actualizado con las **REGLAS DE AISLAMIENTO ESTRICTO**:
  1. No hacer `git merge develop` en ramas feature.
  2. Cada rama feature contiene SOLO su carpeta permitida (`apps/<app>/`, `templates/` o `static/`), más los archivos base de `main`.
  3. No usar `git rm` para limpiar ramas mezcladas: se recrearán limpias desde `main` (`feature/<app>-clean`) dejando la actual como `-old`.
  4. No hacer merge a `develop` hasta que el usuario lo indique explícitamente.
  5. Verificación obligatoria con `git diff --name-only main...HEAD | grep -v "^<carpeta permitida>"`.
  6. No correr `manage.py check` en ramas aisladas individuales; verificar únicamente la estructura exacta de carpetas.

## Pendientes y dudas para el usuario
1. **Destino de `css/chat-widget.css`**: Se usa como botón flotante en `dashboard`, `form` y `list`. ¿Debe ubicarse dentro de `apps/chatbot/static/chatbot/css/chat-widget.css` (ya que es el widget del bot) o en `static/css/global/`? (Recomendación: `apps/chatbot/static/chatbot/css/chat-widget.css` cargado condicionalmente o en chatbot).
2. **Destino de `assets/data/dashboard-cardiounemi-data.js`**: Son datos mock de prueba del dashboard (193 KB). En la arquitectura final el dashboard consumirá el ORM de Django con `services.py`. ¿Movemos este JS a `apps/dashboard/static/dashboard/js/dashboard-data.js` como respaldo visual temporal?
3. **Librerías de terceros (`assets/vendor/`)**:
   - `chart.umd.min.js` y `apexcharts.min.js`: Son exclusivas de gráficos del dashboard. ¿Se mueven a `apps/dashboard/static/dashboard/vendor/`?
   - `marked.min.js` y `katex/`: Se usan en chat / fórmulas matemáticas. ¿Se mueven a `apps/chatbot/static/chatbot/vendor/`?
