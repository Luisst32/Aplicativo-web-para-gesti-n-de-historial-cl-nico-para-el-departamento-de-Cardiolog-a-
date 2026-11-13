# Guía de Instalación y Despliegue en Producción
**Sistema Web para Gestión de Historial Clínico - Cardiología (CardioUNEMI)**

Esta guía detalla el paso a paso completo para desplegar la aplicación desde cero en un servidor **AWS EC2 con Amazon Linux 2023**, configurando **Python 3.12**, **PostgreSQL 16**, **Gunicorn**, **Nginx** y **Cloudflare**.

---

## Índice
1. [Requisitos Previos y Paquetes del Sistema](#1-requisitos-previos-y-paquetes-del-sistema)
2. [Instalación y Configuración de PostgreSQL 16](#2-instalación-y-configuración-de-postgresql-16)
3. [Clonación del Repositorio y Entorno Virtual](#3-clonación-del-repositorio-y-entorno-virtual)
4. [Configuración de Variables de Entorno (.env)](#4-configuración-de-variables-de-entorno-env)
5. [Migraciones, Superusuario y Carga de Catálogos](#5-migraciones-superusuario-y-carga-de-catálogos)
6. [Recolección de Archivos Estáticos (Staticfiles)](#6-recolección-de-archivos-estáticos-staticfiles)
7. [Configuración del Servicio Django con Gunicorn (Systemd)](#7-configuración-del-servicio-django-con-gunicorn-systemd)
8. [Configuración del Servidor Web Nginx](#8-configuración-del-servidor-web-nginx)
9. [Configuración del Firewall Interno (firewalld)](#9-configuración-del-firewall-interno-firewalld)
10. [Configuración en AWS Security Group y Cloudflare](#10-configuración-en-aws-security-group-y-cloudflare)
11. [Comandos de Mantenimiento Frecuentes](#11-comandos-de-mantenimiento-frecuentes)

---

## 1. Requisitos Previos y Paquetes del Sistema

Actualizar el sistema e instalar **Git**, **Python 3.12**, herramientas de compilación y **Nginx**:

```bash
# Actualizar lista de paquetes
sudo dnf update -y

# Instalar Git, OpenSSL y utilidades
sudo dnf install -y git openssl

# Instalar Python 3.12 y sus herramientas de desarrollo
sudo dnf install -y python3.12 python3.12-pip python3.12-devel

# Instalar Nginx
sudo dnf install -y nginx
sudo systemctl enable --now nginx
```

---

## 2. Instalación y Configuración de PostgreSQL 16

El proyecto utiliza PostgreSQL 16 como motor de base de datos relacional.

### 2.1. Instalación e inicialización
```bash
# Instalar PostgreSQL 16 y su servidor
sudo dnf install -y postgresql16 postgresql16-server

# Inicializar el clúster de la base de datos (solo la primera vez)
sudo postgresql-setup --initdb

# Iniciar y habilitar el servicio para arranque automático
sudo systemctl enable --now postgresql
```

### 2.2. Configuración de autenticación local (`pg_hba.conf`)
Para permitir que Django se conecte localmente vía TCP (`localhost:5432`), se debe configurar el método `trust` para conexiones locales:

```bash
# Cambiar el método ident a trust para 127.0.0.1 y ::1
sudo sed -i 's/127.0.0.1\/32            ident/127.0.0.1\/32            trust/g' /var/lib/pgsql/data/pg_hba.conf
sudo sed -i 's/::1\/128                 ident/::1\/128                 trust/g' /var/lib/pgsql/data/pg_hba.conf

# Reiniciar PostgreSQL para aplicar cambios
sudo systemctl restart postgresql
```

### 2.3. Crear la base de datos del proyecto
```bash
sudo -u postgres createdb cardiounemi_db
```

---

## 3. Clonación del Repositorio y Entorno Virtual

```bash
# 1. Clonar el repositorio en la rama develop
cd /home/ec2-user
git clone -b develop https://github.com/Luisst32/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-.git

# 2. Entrar a la carpeta del proyecto
cd /home/ec2-user/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-

# 3. Crear el entorno virtual con Python 3.12
python3.12 -m venv venv

# 4. Activar el entorno virtual
source venv/bin/activate

# 5. Instalar dependencias del proyecto y Gunicorn para producción
python -m pip install -r requirements-bootstrap.txt
python -m pip install -r requirements.txt
python -m pip check
```

---

## 4. Configuración de Variables de Entorno (.env)

Para una **instalación nueva**, copiar la plantilla sin secretos y generar dos claves independientes. No ejecutar este bloque sobre una instalación existente: usar el procedimiento de rotación que aparece más abajo.

```bash
cp .env.example .env
python - <<'PY'
import secrets
from cryptography.fernet import Fernet
from dotenv import set_key

set_key('.env', 'SECRET_KEY', secrets.token_urlsafe(64))
set_key('.env', 'FIELD_ENCRYPTION_KEYS', Fernet.generate_key().decode('ascii'))
PY
chmod 600 .env
```

Editar después las variables de conexión y `ALLOWED_HOSTS` de `.env` para ese servidor. El entorno del proceso tiene prioridad sobre `.env`, que se carga exclusivamente desde la raíz de la aplicación.

Para el servidor de esta guía, usar `APP_ENV=production`, `DEBUG=False`, los
dominios reales en `ALLOWED_HOSTS` y, si se necesitan orígenes CSRF adicionales,
sus URLs HTTPS en `CSRF_TRUSTED_ORIGINS`. Con Nginx como único acceso a Gunicorn
y la configuración de la sección 8, activar `TRUST_PROXY_HEADERS=True`.
Para desarrollo local por HTTP, usar `APP_ENV=development`,
`ALLOWED_HOSTS=localhost,127.0.0.1,testserver`, `TRUST_PROXY_HEADERS=False` y
`SECURE_HSTS_SECONDS=0`. DEBUG sólo se activa con `true` o `1`; otros valores,
incluido `release` heredado de herramientas del host, se interpretan como False.

`SECRET_KEY` es obligatoria, privada, de al menos 50 caracteres y no puede comenzar por `django-insecure-`. `FIELD_ENCRYPTION_KEYS` es obligatoria y contiene claves Fernet independientes, separadas por coma. Si falta una clave o tiene formato inválido, la aplicación se detiene con un error de configuración; nunca utiliza un secreto compartido ni deriva el cifrado desde `SECRET_KEY`.

> **Nota:** La clave API de Gemini y el modelo se configuran directamente desde el panel **Ajustes del Sistema** en la interfaz web (almacenados encriptados en `security.system_setting` asociados al rol **Administrador**).

> **Nota:** Reemplaza `milanesa.sbs` por tu dominio correspondiente.

### 4.1. Rotación de claves en una instalación existente

Preparar una copia protegida de la configuración y un respaldo de la BD antes de rotar. No publicar claves, ciphertexts ni respaldos en Git o en logs.

1. Mantener la `SECRET_KEY` actual mientras se rota el cifrado. Configurar temporalmente `FIELD_ENCRYPTION_KEYS` como `NUEVA,ANTERIOR_1,ANTERIOR_2`: la primera clave cifra y las restantes permiten leer datos anteriores.
2. Si la instalación antigua no tenía claves dedicadas, su clave de lectura anterior se obtiene **localmente** de la antigua `SECRET_KEY` con la siguiente expresión. Escribir el resultado directamente en el almacén de secretos; no imprimirlo ni incorporarlo al código:

   ```python
   legacy_read_key = base64.urlsafe_b64encode(
       hashlib.sha256(old_secret_key.encode('utf-8')).digest()
   ).decode('ascii')
   ```

   Requiere `import base64, hashlib`. Esa clave anterior se añade explícitamente al final de la lista temporal. La aplicación nueva no la calcula por su cuenta.

3. Con las claves temporales configuradas, comprobar y rotar todas las credenciales:

   ```bash
   python manage.py rotate_encrypted_settings --check
   python manage.py rotate_encrypted_settings
   ```

   El comando verifica todos los valores antes de escribir, bloquea las filas durante la operación y revierte la transacción si encuentra un valor ilegible. Abarca Gemini, OpenAI, Claude, el secreto Gmail y el refresh token; sólo muestra cantidades.

4. Retirar las claves antiguas de `FIELD_ENCRYPTION_KEYS`, repetir `--check` y reiniciar todos los procesos de la aplicación. Conservar claves antiguas únicamente en los respaldos protegidos que aún las necesiten.
5. Generar una `SECRET_KEY` nueva e independiente y reiniciar los procesos. Esta rotación invalida sesiones y enlaces de restablecimiento previos, pero no afecta al cifrado de credenciales.

Si se migra desde una clave Django de desarrollo, generar la nueva `SECRET_KEY` antes de iniciar la versión nueva y conservar explícitamente la clave de lectura anterior del paso 2 hasta terminar el recifrado. No configurar como fallback la clave de desarrollo comprometida.

---

## 5. Migraciones, Superusuario y Carga de Catálogos

Con el entorno virtual activado (`source venv/bin/activate`):

```bash
# 1. Aplicar las migraciones a PostgreSQL
python manage.py migrate

# 2. Crear el usuario Administrador del sistema
python manage.py createsuperuser

# 3. Cargar los catálogos maestros y datos iniciales requeridos
python manage.py seed_catalog_data
```

---

## 6. Recolección de Archivos Estáticos (Staticfiles)

Para que Nginx pueda servir las hojas de estilo CSS, fuentes y scripts JavaScript en producción, se deben compilar todos los recursos estáticos:

```bash
# Recolectar archivos estáticos en la carpeta staticfiles/
python manage.py collectstatic --noinput

# Dar permisos de lectura/ejecución al directorio home para que Nginx pueda acceder
chmod 755 /home/ec2-user
```

---

## 7. Configuración del Servicio Django con Gunicorn (Systemd)

Crear el servicio de `systemd` para que Django se ejecute en segundo plano las 24/7 y se reinicie automáticamente si falla o si el servidor se reinicia:

```bash
sudo bash -c 'cat > /etc/systemd/system/django_app.service << "EOF"
[Unit]
Description=Gunicorn para Django Aplicativo Cardiologia
After=network.target postgresql.service

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-
ExecStart=/home/ec2-user/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF'
```

Activar e iniciar el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now django_app
```

---

## 8. Configuración del Servidor Web Nginx

### 8.1. Certificado SSL para comunicación segura con Cloudflare

Instalar un certificado vigente que cubra el dominio, emitido por una autoridad
pública o por Cloudflare Origin CA para el tramo Cloudflare → Nginx. Guardar
certificado/cadena en `/etc/nginx/ssl/nginx.crt` y la clave privada con permisos
restringidos en `/etc/nginx/ssl/nginx.key`. El certificado autofirmado genérico
del ejemplo anterior no sirve para la validación de Full (strict).
Consultar los [requisitos de Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/).

### 8.2. Archivo de configuración del Virtual Host
```bash
sudo bash -c 'cat > /etc/nginx/conf.d/cardiounemi.conf << "EOF"
server {
    listen 80;
    server_name milanesa.sbs www.milanesa.sbs;
    return 308 https://milanesa.sbs$request_uri;
}

server {
    listen 443 ssl;
    server_name milanesa.sbs www.milanesa.sbs;

    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;

    client_max_body_size 50M;

    # Servir archivos estáticos recolectados
    location /static/ {
        alias /home/ec2-user/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Servir archivos multimedia (documentos y fotos subidos)
    location /media/ {
        alias /home/ec2-user/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-/media/;
    }

    # Proxy inverso hacia Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $http_cf_connecting_ip;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Sobrescribir siempre el encabezado recibido del cliente.
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF'
```

Verificar la sintaxis y reiniciar Nginx:
```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

## 9. Configuración del Firewall Interno (firewalld)

Por defecto, Amazon Linux 2023 activa `firewalld` bloqueando los puertos web. Es necesario habilitar el tráfico HTTP y HTTPS:

```bash
# Permitir tráfico en los puertos 80 y 443
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# Recargar reglas del firewall
sudo firewall-cmd --reload

# Verificar que los servicios estén activos
sudo firewall-cmd --list-all
```

---

## 10. Configuración en AWS Security Group y Cloudflare

### 10.1. AWS EC2 (Security Group)
En el Security Group asignado a tu instancia (ej. `launch-wizard-1`), asegúrate de tener las siguientes **Reglas de Entrada (Inbound Rules)**:
- **HTTP** | Puerto `80` | Protocolo `TCP` | Origen: `0.0.0.0/0`
- **HTTPS** | Puerto `443` | Protocolo `TCP` | Origen: `0.0.0.0/0`
- **SSH Personalizado** | Puerto `2222` (o `22`) | Protocolo `TCP` | Origen: `0.0.0.0/0`

### 10.2. Cloudflare (DNS y SSL/TLS)
1. **DNS ➔ Records:**
   - Registro Tipo **`A`** ➔ Nombre: `@` ➔ IPv4: `TU_IP_PUBLICA_EC2` ➔ Proxy status: **Proxied** (Nube naranja ☁️).
   - *(Opcional)* Registro Tipo **`CNAME`** ➔ Nombre: `www` ➔ Target: `@` ➔ **Proxied**.
   - **Importante:** Eliminar cualquier registro `AAAA` (IPv6) obsoleto.
2. **SSL/TLS ➔ Overview:**
   - Modo de cifrado: **Full (strict)**, con el certificado del origen validado.
   - No utilizar Flexible: Cloudflare debe comunicarse con el origen por HTTPS.

---

## 11. Comandos de Mantenimiento Frecuentes

- **Ver el estado de la aplicación:**
  ```bash
  sudo systemctl status django_app
  ```

- **Ver los logs de Django/Gunicorn en tiempo real:**
  ```bash
  sudo journalctl -u django_app -f
  ```

- **Reiniciar la aplicación (tras cambios en código o `.env`):**
  ```bash
  sudo systemctl restart django_app
  ```

- **Ver logs de Nginx:**
  ```bash
  sudo tail -f /var/log/nginx/access.log
  sudo tail -f /var/log/nginx/error.log
  ```

- **Actualizar el aplicativo:** usar el workflow de la sección 19. Sustituye el
  procedimiento manual de git pull + migrate + restart sin pruebas previas.
  La rama develop se publica sólo después de validar el commit; un fallo debe
  investigarse antes de reintentar, sin saltarse pasos ni ignorar códigos de salida.

## 12. Autorización clínica de la cohorte (A02)

Los usuarios autorizados pueden trabajar con **todas las instituciones de la cohorte**.
La institución del usuario no concede permisos ni limita las fichas disponibles.
Una cuenta activa, `is_staff` o un rol sin permisos no habilitan acceso clínico.

Después de actualizar el código, ejecutar `python manage.py migrate` antes de
reiniciar los procesos. Se añade la relación `Role.permissions` y los permisos
`clinical.export_clinical_data` / `clinical.import_clinical_data`; no se modifican
registros clínicos ni se otorgan permisos automáticamente a usuarios existentes.

Un superusuario o un usuario activo con asignación activa al rol exacto y activo
`Administrador` tiene todas las capacidades clínicas. Para los demás usuarios,
los permisos se conceden explícitamente desde el administrador de Django:

1. En **Security → Roles**, seleccionar los permisos clínicos del rol y activarlo.
2. En **Security → Users**, asignar ese rol al usuario con estado `ACTIVE`.
3. Para revocar esa vía de acceso, desactivar el rol o su asignación, o retirar sus permisos.

También se aceptan permisos nativos de Django concedidos directamente al usuario
o mediante grupos. Estas son vías independientes: desactivar un rol no revoca
permisos que el usuario conserve por otro rol, un grupo o una asignación directa.
Las comprobaciones consultan los permisos vigentes sin reutilizar la caché de
permisos de `user.has_perm()`.

En la tabla, todos los codenames llevan el prefijo `clinical.`:

| Acción | Permisos requeridos |
| --- | --- |
| Consultar fichas, listado, dashboard y asistente | `view_patient`, `view_visit` |
| Crear paciente y ficha | Consulta + `add_patient`, `add_visit` |
| Guardar cambios en la ficha y sus bloques | Consulta + `change_patient`, `change_visit` |
| Eliminar paciente y ficha | Consulta + `delete_patient`, `delete_visit` |
| Exportar dataset, PDF con datos o ZIP | Consulta + `export_clinical_data` |
| Analizar y ejecutar importaciones | Consulta + `add_patient`, `add_visit`, `change_patient`, `change_visit`, `import_clinical_data` |
| Crear enlaces de descarga y enviarlos | Consulta + `export_clinical_data`, `add_secureshare` |

La plantilla PDF vacía requiere únicamente consulta. El formulario muestra modo
de consulta cuando no hay permiso de edición. Los controles no disponibles se
ocultan, y el servidor vuelve a comprobar los permisos en cada operación.
La exportación de gráficos ya recibidos por el navegador es una función local:
ocultar su botón no impide copiar datos que el usuario puede consultar.

El back-office `/admin/` requiere además `is_staff` y ser administrador activo;
mantiene las comprobaciones nativas de permisos por modelo. No se debe asignar
`Administrador` a usuarios clínicos para concederles acceso ordinario.
El portal de enlaces compartidos continúa siendo público con token, código y
caducidad: su creación exige permiso de compartir. Un enlace ya emitido conserva
su vigencia hasta su revocación o vencimiento.

## 13. Dependencias verificadas (A16)

`requirements.txt` fija las dependencias directas e incorpora `requirements.lock`
como restricciones de versión para las transitivas. El archivo de restricciones
también conserva versiones de paquetes auxiliares del entorno local; no obliga
a instalarlos si no forman parte del árbol requerido. `cryptography`, usado para
las credenciales cifradas y al arrancar la aplicación, está declarado explícitamente.

`requirements-bootstrap.txt` fija pip 26.3. Ejecutar ambos pasos de instalación
indicados en esta guía; no instalar Gunicorn por separado sin versión.
Gunicorn 27.0.1 está incluido en requirements y requiere Linux/Unix para ejecutarse.

Se corrigieron los avisos detectados en pyasn1 0.6.4 mediante 0.6.5 y en pip
26.1.2 mediante 26.3. Referencias de los proyectos:
[pyasn1 0.6.5](https://github.com/pyasn1/pyasn1/blob/main/CHANGES.rst) y
[historial de pip](https://pip.pypa.io/en/stable/news/).

Las restricciones se comprobaron con resolución sin paquetes preinstalados para
Windows/Python 3.14 y Linux x86_64/Python 3.12. La ejecución de la aplicación y las
pruebas se verifican localmente en Windows; la resolución Linux no sustituye las
pruebas ni el arranque de Gunicorn en el servidor.

Para actualizar una dependencia, cambiar conscientemente su versión y las
restricciones afectadas, resolver nuevamente y ejecutar `python -m pip check`,
la auditoría de dependencias y las pruebas antes del despliegue. Estos archivos
fijan versiones, no hashes de artefactos. Los resultados de pip-audit describen
los avisos conocidos en el momento del análisis y deben renovarse al actualizar.

## 14. Concurrencia de enlaces compartidos (A13)

El portal público procesa cada solicitud dentro de una transacción y bloquea
únicamente la fila del enlace mediante `select_for_update(of=('self',))` antes
de comprobar caducidad, revocación, intentos y descargas. Las solicitudes sobre
el mismo enlace se serializan; enlaces diferentes conservan filas independientes.
El bloqueo se mantiene hasta crear la respuesta, incluida la generación de PDF
o ZIP. Una excepción durante esa generación revierte la actualización del contador.

Desbloquear con el código no cuenta como descarga. Cada respuesta de descarga
producida incrementa el contador una vez, incluida la descarga directa tras
introducir el código. Esto registra respuestas generadas por el servidor; no
confirma que el destinatario haya recibido todos los bytes del archivo.
Los enlaces nuevos conservan `max_downloads=None`; si un enlace tiene un límite
numérico, también se aplica frente a solicitudes concurrentes.

Las pruebas de concurrencia requieren PostgreSQL y utilizan conexiones separadas
con registros ficticios. Los generadores de archivos y la auditoría se simulan
en esas pruebas para aislar la carrera; las pruebas existentes de SecureShare
siguen verificando generación real y flujos del portal.

## 15. Uso de credenciales del asistente (A15)

El asistente sólo ejecuta Gemini cuando se cumplen todas estas condiciones:
usuario con acceso clínico y autorización administrativa, rol de configuración
activo, chatbot habilitado, `active_llm_provider=gemini`, `gemini_enabled=True`
y una clave cifrada válida configurada en **Ajustes del Sistema**.

`GEMINI_API_KEY` del entorno ya no se utiliza como respaldo, ni siquiera para un
administrador. Configurar la clave desde Ajustes antes de usar la integración.
La consulta de claves existentes para administrarlas sigue separada de su uso
en ejecución: cambiar el proveedor activo no borra las credenciales guardadas.

Los lectores clínicos autorizados conservan el análisis estadístico local, sin
uso de las credenciales del administrador ni preparación de contexto para el LLM.
Seleccionar OpenAI o Claude tampoco llama a Gemini: este servicio todavía sólo
implementa Gemini y utiliza análisis local cuando el proveedor seleccionado no
tiene integración ejecutable. No se añadieron integraciones nuevas con A15.

Ante fallo al verificar la habilitación global, el asistente se deshabilita para
esa consulta. Ante fallo de consulta/descifrado de credenciales, o de la política
del proveedor, no se realiza una llamada externa ni se busca otra fuente de claves.

## 16. Perfil HTTPS y cookies (A07)

`APP_ENV` acepta `production`, `development` o `test`; si falta, se aplica
production. El perfil de producción rechaza DEBUG activo, hosts vacíos y el
comodín `*`. Exige redirección HTTPS y cookies de sesión/CSRF Secure, conserva
HttpOnly en sesión, SameSite Lax y X-Frame-Options DENY. La cookie CSRF sigue
legible por JavaScript porque los clientes existentes envían X-CSRFToken;
el middleware CSRF continúa validando el token y el origen.

HSTS empieza en 3600 segundos para el host, configurable hacia arriba mediante
`SECURE_HSTS_SECONDS`. No se incluyen subdominios ni se anuncia preload mientras
no se verifique su cobertura HTTPS. Por ello `check --deploy` conserva W005 y
W021; no se silencian. La política elimina W004/W008/W012/W016 en producción.
El error independiente mail.E001 seguirá apareciendo si se usa correo de consola.

La confianza en `X-Forwarded-Proto` está desactivada por defecto. Activar
`TRUST_PROXY_HEADERS=True` únicamente con Gunicorn inaccesible desde clientes
externos y detrás de un proxy controlado que sobrescriba ese encabezado con el
esquema real. El ejemplo conserva Gunicorn en 127.0.0.1 y separa HTTP/HTTPS en
Nginx; Cloudflare debe usar Full (strict) con certificado de origen válido.
Una cadena mal configurada puede causar redirecciones repetidas: verificar
HTTPS público, cabeceras, cookies y origen antes de habilitar el perfil en vivo.

Para desarrollo por HTTP usar el perfil development explícito y HSTS=0; no
desactivar banderas individuales del perfil de producción para simular desarrollo.
`CSRF_TRUSTED_ORIGINS` admite orígenes exactos separados por comas, HTTPS en
producción, sin rutas ni comodines; no hace falta configurarlo para el mismo origen.

Referencias: [Django: configuración del proxy](https://docs.djangoproject.com/en/6.1/ref/settings/#secure-proxy-ssl-header)
y [Django: HSTS](https://docs.djangoproject.com/en/6.1/ref/middleware/#http-strict-transport-security).
Los tests verifican respuestas y configuración en local; no acreditan la cadena
TLS ni la configuración de un servidor que no se ha inspeccionado.

## 17. Tokens y archivos de importación (A05)

Analizar y ejecutar una importación exige un usuario activo con los permisos de
importación de A02. El análisis devuelve un ticket firmado por Django, ligado al
usuario que subió el archivo, con caducidad de una hora. El frontend lo devuelve
sin modificar; ya no se aceptan UUID antiguos, rutas, patrones glob ni tokens de
otro usuario, aunque ese otro usuario también tenga permiso para importar.

Los temporales nuevos se almacenan en `.private_imports/`, fuera de MEDIA y de
Git. No configurar Nginx ni otra ruta pública para servir ese directorio. El
helper admite `IMPORT_TEMP_ROOT` como ajuste Django para pruebas u otro almacén
privado compartido; rechaza ubicarlo dentro de MEDIA_ROOT. En Unix se crean
directorio/archivos con modos 0700/0600; en Windows verificar también las ACL del
directorio. Los workers deben acceder al mismo almacenamiento privado.

Al ejecutar se reclama el archivo por un renombrado atómico a un nombre privado
único que conserva su extensión, protegido previamente con creación exclusiva
de un archivo de bloqueo para arbitrar entre workers. Sólo una solicitud puede
reclamarlo. Se elimina
al terminar, incluso ante errores: si falla la importación, volver a subirlo y
analizarlo. No se restauran tokens consumidos, ni se adivinan extensiones mediante
glob. Un análisis fallido también elimina su archivo.

La caducidad invalida el ticket, pero no borra automáticamente archivos de
análisis abandonados. Incluir ese directorio en la política operativa de limpieza
de temporales, evitando archivos reclamados por importaciones en curso. Los
tokens quedan invalidados también al rotar SECRET_KEY.

Antes de desplegar, retirar `MEDIA_ROOT/temp_imports` de la zona pública:
moverlo a cuarentena privada tras verificar origen/destino, sin mezclarlo con
otros uploads. No hay propietario verificable para recuperar tickets antiguos;
los usuarios deben analizar de nuevo. Localmente se conservaron nueve temporales
antiguos en una carpeta `legacy-*` dentro de `.private_imports/`, sin borrarlos.
Aplicar esta revisión también en producción: la operación local no la reemplaza.

## 18. Renderizado seguro y regresiones XSS (A03)

El dashboard recibe registros como objetos Python y usa `json_script` para
insertarlos en HTML; JavaScript continúa leyéndolos con JSON.parse/textContent.
Las cadenas clínicas se conservan como datos, incluidas comillas, acentos y
caracteres HTML. No se utiliza `|safe` para este contenido ni se construye código
onclick/onchange a partir de nombres, correos o identificadores.

Listado, historial, resumen imprimible, perfil y resultados de envío escapan
texto/atributos HTML o usan textContent. Las acciones dinámicas de borrar,
exportar y copiar se enlazan con addEventListener y valores en closures.
`escapeHtml` no debe usarse para concatenar JavaScript: no es un escape JS.

El Markdown del asistente se procesa con Marked y después con DOMPurify 3.4.17
local, con lista explícita de etiquetas/atributos permitidos. No se admiten HTML
ejecutable, eventos, formularios, SVG del modelo ni URLs javascript. Si falta
Marked o DOMPurify se muestra texto literal. KaTeX se ejecuta después, con
trust=false. Los títulos de gráficos del modelo también usan textContent.
Fuente/licencia/hash del sanitizer: `static/vendor/dompurify/README.md` y
[release de DOMPurify](https://github.com/cure53/DOMPurify/releases/tag/3.4.17).

Se añadieron regresiones Django con una carga XSS guardada en un paciente
ficticio, y pruebas Node/jsdom de los renderizadores reales, eventos, Markdown,
fallos de dependencias y fórmulas. Node 22.23.2 fue el entorno comprobado:

```bash
npm ci --prefix tests/frontend --ignore-scripts
npm test --prefix tests/frontend
python manage.py test dashboard.test_xss dashboard.tests.DashboardServicesAndViewsTestCase security.test_clinical_access
```

Las dependencias npm son herramientas de prueba con versiones/lock propios;
no se necesita Node para ejecutar Django ni se descargan scripts de sanitización
desde un CDN. Al desplegar, ejecutar collectstatic y servir los JS actualizados:
se cambiaron sus versiones de caché. Las pruebas DOM usan jsdom, no constituyen
una prueba de todos los navegadores ni una auditoría exhaustiva de las otras
bibliotecas de terceros de gráficos. No se añadió una política CSP global.

## 19. Verificaciones obligatorias antes del despliegue (A19)

El workflow `.github/workflows/deploy.yml` tiene dos jobs. `verify` ejecuta en
Ubuntu/Python 3.12/PostgreSQL 16 la instalación fijada, pip check, las pruebas del
orquestador, checks Django, detección de migraciones pendientes de generar y cada
módulo test*.py de las apps por nombre explícito. También instala las herramientas
Node fijadas y ejecuta las pruebas DOM. El job deploy necesita que verify termine
correctamente; los PR sólo verifican. Despliegue se permite únicamente desde
develop, con un despliegue de producción simultáneo y sin cancelar el que está activo.

`scripts/verify_backend.py` genera claves efímeras de prueba, usa un nombre único
de BD desechable y aísla media, imports, static, caché y correo. La credencial
PostgreSQL escrita en el workflow es sólo para el contenedor efímero CI; no usarla
en producción. Para ejecutar la validación local con una cuenta de PostgreSQL
que pueda crear bases de prueba:

```bash
python -m unittest discover -s tests -p test_deploy.py -v
python scripts/verify_backend.py
npm ci --prefix tests/frontend --ignore-scripts
npm test --prefix tests/frontend
```

Antes de activar el despliegue configurar en GitHub:

- Los secretos SSH existentes EC2_HOST, EC2_USER, EC2_SSH_KEY y EC2_PORT
  (el workflow conserva sus aliases anteriores).
- El secreto **EC2_HOST_FINGERPRINT**, verificado por un canal confiable con el
  administrador del servidor, para comprobar la identidad del host SSH.
- La variable **DEPLOY_HEALTHCHECK_URL**, por ejemplo
  `https://milanesa.sbs/security/login/`, con URL canónica HTTPS sin redirecciones,
  credenciales ni parámetros. Verificar certificado TLS y acceso desde EC2.

El servidor requiere Python 3.12 para el orquestador, Git, venv/bin/python o
env/bin/python de la aplicación y permisos sudo no interactivos para reiniciar
únicamente django_app. Configurar previamente APP_ENV=production, DEBUG=False,
TLS/proxy de A07 y un backend de correo apto para producción: mail.E001 bloquea
el despliegue; W005/W021 deliberados no se silencian ni se convierten en errores.

El paso SSH ejecuta con parada en errores y obtiene el script desde el SHA exacto
validado. `scripts/deploy.py` rechaza cambios versionados locales del servidor,
verifica que el SHA pertenece a origin/develop y hace checkout detached de ese
commit sin reset --hard. Instala siempre bootstrap/requirements, comprueba pip,
perfil production, check --deploy y migraciones, aplica migrate/collectstatic,
reinicia django_app de forma síncrona y comprueba systemctl is-active. Sólo después
de recibir HTTP 200 del healthcheck HTTPS imprime éxito. No usa pgrep global,
nohup, scripts diferidos ni `|| true` para ocultar errores.

Este despliegue sigue siendo **en el directorio existente**: parar en un fallo no
revierte checkout, instalación parcial de dependencias ni migraciones ya aplicadas.
Preparar backups y un procedimiento de recuperación antes de desplegar; un fallo
de salud después del reinicio requiere intervención. No se implementó despliegue
atómico por releases ni rollback automático. La ejecución real de GitHub Actions,
SSH, systemd y el dominio público debe verificarse en sus entornos; las pruebas
locales del orquestador simulan esos comandos y no despliegan.

## 20. Contratos de datos de importación/exportación y dashboard (A17)

El adaptador DatasetMetadata usado por CSV y R ofrece tanto column_labels como
column_names_to_labels, igual que el contrato consumido del lector SPSS. Una
columna nueva puede generar su pregunta de cuestionario con la etiqueta disponible
o el propio nombre de la columna.

La exportación de EDAD conserva una respuesta explícita si ya está registrada;
en el respaldo relacional calcula años cumplidos a la fecha de evaluación,
considerando mes y día. No consulta Patient.age, que no existe, ni utiliza la
edad actual para una evaluación histórica. Las respuestas seleccionadas usan
AnswerOption.label y se convierten a códigos cuando la especificación declara
sus etiquetas; se conservan también valores numéricos cero del cuestionario.

Echocardiogram no tiene un campo fractional_shortening_percentage: la fracción
de acortamiento sólo se exporta si consta en VisitAnswer para esa variable. Si
no existe esa respuesta, se conserva como dato faltante, sin calcularla ni
inventar un valor. El dashboard también lee label de opciones seleccionadas,
sin exigir el atributo inexistente option_text.

`clinical.test_model_contracts` contiene regresiones con lectores reales CSV/RDS,
importación de columnas nuevas, exportación completa de 342 columnas CSV/SAV,
lectura posterior del SAV y comprobaciones de cumpleaños y respuestas. Usa datos
sintéticos. No equivale a certificar todos los mapeos clínicos ni todos los
datasets existentes; los defaults y las demás políticas pendientes se revisan
en sus hallazgos correspondientes.

## 21. Selección exacta de registros (A04)

Los parámetros de paciente usan exclusivamente la clave primaria de Patient:
entero positivo o texto decimal, con prefijos de interfaz `p123` / `p_123`
opcionales. Los parámetros de visita usan la clave primaria de Visit y admiten
`h123` / `h_123`. Nunca se interpretan como cédula ni código de estudio. Ambos
campos siguen disponibles para buscar en el directorio; no identifican el
registro que se modifica, elimina, comparte o exporta. Los médicos autorizados
conservan acceso a todas las instituciones de la cohorte.

Una selección mal formada responde 400; una clave inexistente o una selección
de documentos incompleta responde 404. Se valida el lote entero antes de borrar,
generar archivos o crear enlaces/enviar correos; no se aceptan resultados parciales.
Los IDs repetidos se deduplican. Guardar requiere una clave explícita y rechaza
selectores contradictorios, sin respaldo por los datos demográficos del formulario.

El PDF cumplimentado requiere paciente o visita; si se proporcionan ambos,
deben corresponder al mismo registro. No existe respaldo a la última ficha de
la base. `blank=1` conserva la plantilla vacía explícita. La interfaz usa los
IDs de visita entregados por el servidor y no fabrica historiales si no existen.
Un PDF de enlace compartido sólo puede seleccionar una visita incluida en ese
enlace; una selección inválida no consume cuota. Con varios documentos se exige
seleccionar uno para PDF; ZIP mantiene el alcance completo del enlace.

`api/export-dataset/` exige `patient_ids` no vacío o `scope=all` (también admite
`scope=todos` enviado por la interfaz). No combinar alcance completo e IDs.
Admite listas JSON y texto con IDs separados por comas; `all`/`todos` dentro de
la lista no son comodines. Sólo exporta pacientes activos con visita; una
selección explícita que incluya un paciente inactivo o sin visita se rechaza
completa. La cohorte activa vacía produce CSV sin filas, nunca registros inactivos.
En el servicio Python, `None` significa alcance completo deliberado y `[]` es
una selección inválida. Los consumidores HTTP antiguos que omitían alcance
deben enviar `scope=all`.

Regresiones: `clinical.test_record_selection` usa dos instituciones ficticias,
claves de paciente distintas de las de visita y colisiones deliberadas entre
clave, cédula y código de estudio. Incluye CSV real, guardado/borrado, PDF y
cuotas de enlaces. `tests/frontend/xss.cjs` verifica también que no se invente
un historial. Estas pruebas no certifican los mapeos de todas las columnas ni
los valores predeterminados pendientes de A06.

## 22. Contexto y fallos de auditoría (A10)

PostgreSQLAuditMiddleware mantiene la ejecución de la vista y sus middleware
internos dentro de una transacción de la conexión default. Define
app.current_user_id y app.client_ip mediante set_config parametrizado y local
a esa transacción. Para visitantes anónimos el usuario es explícitamente vacío.
Restaura el contexto previo, incluso si existe una transacción exterior, y no
deja la identidad de una petición en la siguiente conexión reutilizada.
En autocommit el contexto permanece hasta COMMIT, incluidos triggers diferidos,
y PostgreSQL lo restaura automáticamente. Si existe una transacción exterior,
se restaura su contexto antes de devolver el control; el dueño de esa transacción
es responsable del contexto de sus operaciones diferidas posteriores.

La dirección registrada es REMOTE_ADDR validada: identifica al par de red
(normalmente el proxy en producción). No se confía en X-Forwarded-For arbitrario
ni se presenta esa dirección como la IP original del usuario. Una dirección
ausente o inválida se registra como unknown. El rate limiting de A11 requiere
su propia remediación; no se considera resuelto por este cambio.

register_audit_log devuelve el registro creado o lanza AuditLogError. Un fallo
marca la transacción para rollback y una señal de fallo ligada a la petición;
atrapar el error en una vista o en un savepoint no permite devolver éxito ni
confirmar cambios clínicos. El middleware responde 503 genérico y no-store;
los errores se registran a nivel ERROR sin copiar valores de filas o mensajes
SQL que puedan contener datos sensibles. Una respuesta 5xx también revierte
los cambios de la vista, aunque Django ya haya convertido una excepción en
respuesta. Las respuestas 4xx no revierten automáticamente cambios deliberados,
como los contadores de códigos de acceso fallidos.

En los envíos de fichas se preparan y auditan todos los enlaces antes de enviar
el primer correo. Si falla esa auditoría no se envía ninguno y el lote se
revierte. SMTP no participa en la transacción PostgreSQL: un fallo posterior
al envío, incluido un error al confirmar la transacción, puede dejar correos
ya entregados con enlaces que no llegan a persistirse. No existe outbox ni
rollback del correo. Este cambio tampoco añade triggers de producción ni
eventos a operaciones que actualmente no llaman a register_audit_log.

Los iteradores de StreamingHttpResponse se ejecutan después de la transacción:
no deben realizar escrituras clínicas. Los comandos y tareas fuera de HTTP
deben agrupar su mutación y registro de auditoría en transaction.atomic y
establecer su contexto de actor explícitamente. No se habilita ATOMIC_REQUESTS;
el límite de la transacción lo establece el middleware. Este límite mantiene
la conexión/transacción durante vistas costosas; la optimización de tareas
pesadas sigue pendiente en A18.

`audit.test_transactions` verifica con PostgreSQL real, una tabla y un trigger
temporales sintéticos: contexto en autocommit, restauración, anonimato, IP,
rollback y errores ocultados por callers. `audit.test_clinical_rollback`
comprueba las rutas reales de altas, cambios, borrado, envío y descarga ante
fallos de auditoría. No se usan pacientes reales ni se instala el trigger de
prueba en los esquemas de la aplicación.


## Batch A11 / A14 / A09 (2026-11-13)

A11: RequestLimitMiddleware runs before the audit transaction. PostgreSQL UPSERT
provides an atomic shared fixed-minute quota: chatbot 20/user, login 30/network
peer and 5/peer+identifier, reset requests and confirmation 5/peer. Forwarded
headers do not affect these identities. 429 includes Retry-After; DB failure
returns 503. security.0007_requestquota is required (applied locally). Quota keys
are HMACs; expired windows are replaced for each key. There is no scheduled
cleanup of identities no longer used; plan retention/cleanup for that table.
Behind a proxy, REMOTE_ADDR quotas cover the proxy's users together; provision
limits/proxy policy for the intended traffic before production deployment.

A14: external cohort context now exposes only four whole-cohort binary counts.
Cohorts below 10 have no exact total. Each binary count and its complement must
both be at least 5, otherwise the entire pair is withheld, without percentages.
Other KPI families and means are omitted from that external context. Existing
local clinical analysis and charts remain governed by clinical read permission.
The old summary cache is not consumed. New BotQuery entries store metadata and
content-omitted markers, never raw questions/responses. Chatbot error logging
omits exception content. Historical BotQuery rows were not deleted or rewritten;
review their retention and access separately. This is not a formal differential
privacy guarantee or certification of arbitrary questions as PII-free.

A09: deployment checks security.E009/E010 block an elevated/owner runtime role
or an unverifiable connection, including database/schema CREATE privileges.
Production requires explicit DB_USER. scripts/runtime_role.sql is a psql recipe
for a NEW restricted login and DML/sequence grants on existing application
schemas. Run as the migration owner with ON_ERROR_STOP enabled, using a separate
migration identity; the password is prompted, not stored in the SQL file.
Default privileges apply only to objects created later by that same owner.
Then configure the web process's DB_USER/DB_PASSWORD for that runtime identity.
Use a separate migration process/environment for migrate. Run check --deploy
against the runtime identity before starting the web service.

The SQL recipe has NOT been executed. The existing local identity still fails
security.E009, as intended. PostgreSQL pg_hba.conf trust authentication is NOT
corrected by a Django check: an operator must review actual ordered HBA rules,
replace application trust entries with scram-sha-256, set a password and verify
new connections before retiring old access. Remote role/HBA state is unverified.
A09 therefore remains operationally open. No deployment was performed.

## Correcciones finales de integridad, archivos y arquitectura

- A06: el alta ya no crea antropometría ni signos vitales con valores ficticios.
  Las respuestas JSON entregan null si esas mediciones no existen. El servicio
  `clinical/services/measurements.py` distingue campos omitidos de campos vacíos:
  conserva los omitidos, exige las medidas obligatorias al crear un bloque,
  permite vaciar las opcionales y rechaza números no finitos o fracciones en
  campos enteros. El mapeo de CÓDIGO usa el nombre normalizado de la especificación.
  Los bloques de ECG, eco, laboratorio y estudios sólo se procesan cuando llegan
  sus campos; las banderas omitidas no borran resultados anteriores. No se
  modificaron retrospectivamente datos clínicos: un valor histórico de 70 kg
  podría ser real y no se puede corregir por suposición.
- A08: `/media/` responde 404 en Django, incluso con sesión. Las importaciones
  siguen usando los tickets privados A05. `IMPORT_MAX_BYTES` limita a 50 MiB
  tanto el receptor multipart como la copia por bloques del servicio, con limpieza
  del archivo incompleto. El parser del formato valida el contenido al analizarlo;
  admitir la extensión no acredita que un archivo sea válido. En el proxy se debe
  reemplazar cualquier alias público de MEDIA por `scripts/nginx_private_media.conf`.
  Ese archivo es un fragmento para el bloque server, no una configuración completa.
  No se verificó ni se modificó el Nginx remoto.
- A18: el listado admite `page` y `page_size` (100 por defecto, máximo 200), total
  y next_page; incorpora las relaciones usadas en cada fila y desempates por PK.
  El cliente solicita las páginas para mantener los filtros de la cohorte completa.
  La asignación automática de códigos comparte un advisory lock transaccional;
  guardar bloquea el paciente y vuelve a leerlo antes de modificarlo. Las pruebas
  comprueban paginación y que las consultas no crecen por cada paciente agregado.
  **Siguen pendientes** la cola persistente para trabajos grandes y la medición
  de cargas reales: imports, PDF/ZIP y exportación continúan siendo síncronos.
  No se añadió Celery ni se acreditó rendimiento con todos los datasets.
- A20: `clinical/services/clinical_form.py` concentra la transacción del guardado;
  la vista conserva autenticación, selección, validación de entrada y respuesta.
  Los errores de conversión ya no se ignoran: generan ValidationError y rollback.
  Alta/guardado no devuelven excepciones internas ni imprimen sus valores.
  Las regresiones cubren conservación, datos inválidos, ausencia de mediciones,
  límites de archivos, privacidad de MEDIA, paginación y consultas. Esto reduce
  la deuda del flujo crítico; no certifica todas las reglas clínicas ni elimina
  toda la deuda de las demás vistas.

Para A09, el despliegue usa `scripts/migration_manage.py` únicamente para
makemigrations/migrate. Exige `MIGRATION_ENV_FILE` fuera de la aplicación, con
DB_USER/DB_PASSWORD de la cuenta de migraciones; en Unix rechaza permisos de
grupo/otros. El archivo debe pertenecer al usuario de despliegue y no ser legible
por el usuario del servicio web. Windows requiere comprobar sus ACL aparte.
La variable de GitHub Actions MIGRATION_ENV_FILE debe contener la ruta del
servidor. El proceso web mantiene sólo sus credenciales runtime; nunca carga ese
archivo. Los chequeos de despliegue se ejecutan con el runtime antes de migrar.
El orquestador tiene pruebas que simulan la ejecución; no se contactó al servidor.
Aplicar los roles, comprobar HBA y proteger ese archivo siguen siendo tareas
operativas pendientes; no basta con crear el fragmento SQL.
