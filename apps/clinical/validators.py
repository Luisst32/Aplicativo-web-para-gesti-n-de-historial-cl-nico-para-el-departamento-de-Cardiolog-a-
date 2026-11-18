import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email


def validate_email_address(email: str) -> bool:
    """
    Valida si una dirección de correo tiene un formato real y sintaxis válida RFC.
    Requiere estructura usuario@dominio.tld con dominio con punto y al menos 2 caracteres de TLD.
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) < 5 or len(email) > 254:
        return False
    # Verificación de sintaxis de dominio real (debe tener @ y al menos un punto en el dominio con TLD >= 2)
    email_regex = re.compile(
        r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$'
    )
    if not email_regex.match(email):
        return False
    try:
        django_validate_email(email)
        return True
    except ValidationError:
        return False


def validate_ecuadorian_phone(phone: str) -> bool:
    """
    Valida un número telefónico (móvil o convencional en Ecuador).
    Móvil: 10 dígitos iniciando con 09 (ej. 0987654321) o formato internacional (+5939xxxxxxxx).
    Fijo / Convencional: 9 dígitos iniciando con 02 a 07 (ej. 042971234) o internacional (+593[2-7]xxxxxxx).
    """
    if not phone or not isinstance(phone, str):
        return False
    clean = re.sub(r'[\s\-\.\(\)]', '', phone.strip())
    # Móvil nacional: 09XXXXXXXX (10 dígitos)
    if re.match(r'^09\d{8}$', clean):
        return True
    # Fijo nacional con código de área provincial: 0[2-7]XXXXXXX (9 dígitos)
    if re.match(r'^0[2-7]\d{7}$', clean):
        return True
    # Móvil internacional Ecuador: +5939XXXXXXXX (13 caracteres)
    if re.match(r'^\+5939\d{8}$', clean):
        return True
    # Fijo internacional Ecuador: +593[2-7]XXXXXXX (12 caracteres)
    if re.match(r'^\+593[2-7]\d{7}$', clean):
        return True
    return False


def validate_ecuadorian_id(cedula: str) -> bool:
    """
    Validates an Ecuadorian 10-digit identification card (Cédula de Identidad)
    using the official modulo 10 checksum algorithm.
    """
    if not cedula or not isinstance(cedula, str):
        return False

    cedula = cedula.strip()
    if len(cedula) != 10 or not cedula.isdigit():
        return False

    # Código de provincia: 01 a 24 o 30
    provincia = int(cedula[:2])
    if not (1 <= provincia <= 24 or provincia == 30):
        return False

    # Tercer dígito debe ser menor a 6 para personas naturales
    tercer_digito = int(cedula[2])
    if tercer_digito >= 6:
        return False

    # Algoritmo Módulo 10
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    for i in range(9):
        val = int(cedula[i]) * coeficientes[i]
        if val >= 10:
            val -= 9
        suma += val

    digito_verificador = (10 - (suma % 10)) % 10
    return digito_verificador == int(cedula[9])


def validate_clinical_ranges(data: dict) -> list:
    """
    Validates clinical ranges for physical examination and vital signs (HU-18).
    Returns a list of human-readable error messages for out-of-range parameters.
    """
    errores = []

    # Peso: 20.0 - 350.0 kg
    if data.get('weight_kg') is not None:
        try:
            w = float(data['weight_kg'])
            if not (20.0 <= w <= 350.0):
                errores.append(f"El peso ({w} kg) debe estar en el rango clínico permitido (20 - 350 kg).")
        except (ValueError, TypeError):
            errores.append("El valor de peso es inválido.")

    # Talla: 50.0 - 250.0 cm
    if data.get('height_cm') is not None:
        try:
            h = float(data['height_cm'])
            if not (50.0 <= h <= 250.0):
                errores.append(f"La talla ({h} cm) debe estar en el rango clínico permitido (50 - 250 cm).")
        except (ValueError, TypeError):
            errores.append("El valor de talla es inválido.")

    # Perímetro abdominal: 35.0 - 220.0 cm
    if data.get('waist_circumference_cm') is not None:
        try:
            p = float(data['waist_circumference_cm'])
            if not (35.0 <= p <= 220.0):
                errores.append(f"El perímetro abdominal ({p} cm) debe estar en el rango clínico (35 - 220 cm).")
        except (ValueError, TypeError):
            errores.append("El valor de perímetro abdominal es inválido.")

    # TAS: 50 - 300 mmHg
    if data.get('systolic_bp') is not None:
        try:
            tas = int(data['systolic_bp'])
            if not (50 <= tas <= 300):
                errores.append(f"La TAS ({tas} mmHg) debe estar en el rango clínico (50 - 300 mmHg).")
        except (ValueError, TypeError):
            errores.append("El valor de TAS es inválido.")

    # TAD: 30 - 200 mmHg
    if data.get('diastolic_bp') is not None:
        try:
            tad = int(data['diastolic_bp'])
            if not (30 <= tad <= 200):
                errores.append(f"La TAD ({tad} mmHg) debe estar en el rango clínico (30 - 200 mmHg).")
        except (ValueError, TypeError):
            errores.append("El valor de TAD es inválido.")

    # SatO2: 40 - 100 %
    if data.get('oxygen_saturation') is not None:
        try:
            sat = int(data['oxygen_saturation'])
            if not (40 <= sat <= 100):
                errores.append(f"La saturación de O2 ({sat}%) debe estar entre 40% y 100%.")
        except (ValueError, TypeError):
            errores.append("El valor de SatO2 es inválido.")

    # FC: 30 - 250 bpm
    if data.get('heart_rate') is not None:
        try:
            fc = int(data['heart_rate'])
            if not (30 <= fc <= 250):
                errores.append(f"La frecuencia cardíaca ({fc} lpm) debe estar entre 30 y 250 lpm.")
        except (ValueError, TypeError):
            errores.append("El valor de FC es inválido.")

    return errores
