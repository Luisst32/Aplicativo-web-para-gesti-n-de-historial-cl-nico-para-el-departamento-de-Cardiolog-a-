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
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

---

## 4. Configuración de Variables de Entorno (.env)

Crear el archivo `.env` en la raíz del proyecto:

```bash
cat > .env << 'EOF'
# Django Settings
SECRET_KEY=django-insecure-xn=bxnw0_!=zkd*@4a7!hau_wvsbf$+!dh5rp*gnz5+_%m9wpc
DEBUG=True
ALLOWED_HOSTS=milanesa.sbs,www.milanesa.sbs,localhost,127.0.0.1

# Database Configuration (PostgreSQL)
DB_NAME=cardiounemi_db
DB_USER=postgres
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
EOF
```

> **Nota:** La clave API de Gemini y el modelo se configuran directamente desde el panel **Ajustes del Sistema** en la interfaz web (almacenados encriptados en `security.system_setting` asociados al rol **Administrador**).

> **Nota:** Reemplaza `milanesa.sbs` por tu dominio correspondiente.

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
```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt \
  -subj "/CN=milanesa.sbs"
```

### 8.2. Archivo de configuración del Virtual Host
```bash
sudo bash -c 'cat > /etc/nginx/conf.d/cardiounemi.conf << "EOF"
server {
    listen 80;
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
        proxy_set_header X-Forwarded-Proto https;
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
   - Modo de cifrado: **Full** (o **Flexible**).

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

- **Actualizar el proyecto tras un `git pull`:**
  ```bash
  cd /home/ec2-user/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-
  source venv/bin/activate
  git pull origin develop
  pip install -r requirements.txt
  python manage.py migrate
  python manage.py collectstatic --noinput
  sudo systemctl restart django_app
  ```

