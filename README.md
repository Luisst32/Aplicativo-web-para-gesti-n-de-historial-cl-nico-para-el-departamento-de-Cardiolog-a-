<div align="center">

# CardioUNEMI

**Aplicativo web para la gestión del historial clínico del Departamento de Cardiología**
Universidad Estatal de Milagro (UNEMI)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge)

</div>

---

## Introducción

CardioUNEMI digitaliza el cuestionario clínico cardiovascular del estudio de cohorte de la UNEMI. Permite registrar y consultar las fichas de cada paciente, analizar la cohorte en un dashboard y trabajar con las bases de datos de investigación en SPSS, CSV y R.

**Funcionalidades principales**

- 🩺 **Fichas clínicas:** registro por módulos (sociodemográfico, antropometría, signos vitales, ECG, ecocardiograma, laboratorio, cuestionarios y estudios solicitados) con historial de visitas.
- 📊 **Dashboard:** indicadores y gráficos de la cohorte, con exportación a PDF.
- 📁 **Importación y exportación** de datasets `.sav`, `.zsav`, `.csv`, `.rds` y `.RData`.
- 📄 **Ficha en PDF** y envío por correo mediante enlaces seguros con código de acceso y caducidad.
- 🔒 **Modo de protección de datos:** exportaciones y PDF sin datos personales.
- 🤖 **Asistente con IA** (Google Gemini) para consultas sobre la cohorte.
- 👥 **Roles y permisos** por acción, con registro de auditoría.

---

## Tecnologías

| Área | Tecnologías |
| --- | --- |
| **Backend** | ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![Django](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=white) ![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?logo=gunicorn&logoColor=white) |
| **Base de datos** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white) |
| **Frontend** | ![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black) ![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?logo=chartdotjs&logoColor=white) ![ApexCharts](https://img.shields.io/badge/ApexCharts-008FFB?logoColor=white) |
| **Datos y reportes** | ![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white) ![SPSS](https://img.shields.io/badge/pyreadstat-SPSS-052FAD) ![R](https://img.shields.io/badge/pyreadr-R-276DC3?logo=r&logoColor=white) ![ReportLab](https://img.shields.io/badge/ReportLab-PDF-CC0000) |
| **Inteligencia artificial** | ![Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?logo=googlegemini&logoColor=white) |
| **Infraestructura** | ![AWS](https://img.shields.io/badge/AWS%20EC2-FF9900?logo=amazonwebservices&logoColor=white) ![Nginx](https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white) ![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?logo=cloudflare&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white) |

---

## Instalación

### Requisitos

- Python 3.12 o superior
- PostgreSQL 16
- Git

### 1. Clonar el repositorio

```bash
git clone https://github.com/Luisst32/Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-.git
cd Aplicativo-web-para-gesti-n-de-historial-cl-nico-para-el-departamento-de-Cardiolog-a-
```

### 2. Crear el entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

python -m pip install -r requirements-bootstrap.txt
python -m pip install -r requirements.txt
```

### 3. Crear la base de datos

```bash
createdb -U postgres cardiounemi_db
```

### 4. Configurar las variables de entorno

Copiar la plantilla y generar las claves secretas:

```bash
cp .env.example .env
python -c "import secrets; from cryptography.fernet import Fernet; from dotenv import set_key; set_key('.env','SECRET_KEY',secrets.token_urlsafe(64)); set_key('.env','FIELD_ENCRYPTION_KEYS',Fernet.generate_key().decode())"
```

Después editar `.env` con los datos de conexión a PostgreSQL. Para desarrollo local:

```env
APP_ENV=development
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
SECURE_HSTS_SECONDS=0

DB_NAME=cardiounemi_db
DB_USER=postgres
DB_PASSWORD=tu_contraseña
DB_HOST=localhost
DB_PORT=5432
```

### 5. Preparar la base de datos

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_catalog_data
```

### 6. Ejecutar

```bash
python manage.py runserver
```

Abrir **http://127.0.0.1:8000** e iniciar sesión con el usuario creado.

> La clave de Google Gemini se configura desde **Ajustes del Sistema** dentro del aplicativo, no en `.env`.

---

## Despliegue

Cada push a la rama `develop` ejecuta las pruebas en GitHub Actions y, si pasan, despliega automáticamente en el servidor de producción (AWS EC2 con Nginx y Gunicorn). La configuración está en [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml).

---

## Licencia

Distribuido bajo la licencia MIT. Ver [LICENSE](LICENSE).
