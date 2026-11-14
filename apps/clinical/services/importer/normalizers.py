# -*- coding: utf-8 -*-
"""
normalizers.py
Funciones de normalización de cadenas, limpieza de valores numéricos/decimales,
resolución geográfica y clasificación diagnóstica de variables clínicas.
"""

import re
import unicodedata
import math
from decimal import Decimal

from catalog.models import Canton
from .constants import (
    COLUMN_TYPO_RULES,
    SPSS_QUESTION_ALIASES,
    STANDARD_FIELD_ALIASES,
    FIELD_DESTINATIONS,
    CIUDAD_CODE_MAP,
)

def normalize_var_name(name):
    """
    Limpia y normaliza un identificador de variable SPSS:
    - Reemplaza caracteres corruptos / unicode de reemplazo (\ufffd, ?)
    - Remueve acentos y caracteres no alfanuméricos
    - Retorna en minúsculas sin espacios
    """
    if not name:
        return ""
    # Reemplazo de marcas comunes de caracteres corruptos en nombres de columnas SPSS
    s = re.sub(r'[\ufffd\?]+', 'o', str(name))
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9_]+', '', s)
    return s.lower()


# Diccionario de alias clave para detectar columnas clínicas estándar

# -----------------------------------------------------------------------------
# Patrones de errores gramaticales y tipográficos conocidos en columnas SPSS
# Mapeo directo a su destino en la base de datos
# -----------------------------------------------------------------------------


def classify_spss_question_section(col_name):
    """
    Clasifica con precisión médica cualquier columna SPSS en su QuestionnaireSection exacta de PostgreSQL.
    """
    norm = normalize_var_name(col_name)

    # 1. PREDIMED (Dieta Mediterránea)
    if any(k in norm for k in ['aceite_de_oliva', 'consume_verduras', 'consume_fruta', 'consume_carne', 'mantequilla', 'carbonatadas', 'vino_tinto', 'legumbres', 'pescado', 'reposteria', 'leche_de_vaca', 'queso', 'yogurt', 'frutos_secos', 'huevos', 'cereales', 'pollo_pavo', 'sofrito', 'medas', 'predimed', 'pred_']):
        return 'MOD_6_PREDIMED'

    # 2. Actividad Física / IPAQ
    if any(k in norm for k in ['actividad_fisica', 'ejercicios_aerobicos', 'cual_ejercicios', 'veces_por_semana', 'minutos_al_dia', 'ejercicios_anaerobicos', 'anaerobic', 'deporte', 'horas_tv', 'horas_dormir', 'horas_siesta', 'horas_ocio', 'horas_sentado', 'ipaq', 'act_']):
        return 'MOD_6_ACTIVIDAD_FISICA'

    # 3. COVID-19 y Secuelas
    if 'covid' in norm:
        return 'MOD_4_COVID'

    # 4. Factores Emergentes
    if any(k in norm for k in ['sueno', 'toxicos', 'estrogenos', 'anticonceptivo', 'estres', 'ambiente', 'tipo_a', 'exigente', 'perfeccionista', 'hiperactivo', 'ambicioso', 'hostilidad', 'aislamiento', 'condiciones_ambientales', 'em_']):
        return 'MOD_3_FACTORES_EMERG'

    # 5. Antecedentes Familiares
    if any(k in norm for k in ['antecedentes_familiares', 'antecedentes_padres', 'antecedentes_madres', 'antecedentes_hermanos', 'padre', 'madre', 'af_']):
        return 'MOD_3_ANTECEDENTES_FAM'

    # 6. Historia Cardiovascular y Rose
    if any(k in norm for k in ['problema_corazon', 'revascularizacion', 'insuficiencia_cardiaca', 'ingreso_hospitalario', 'dolor_pecho', 'molestia_caminar', 'reaccion_dolor', 'clase_nyha', 'rose', 'estudios_clinicos', 'estudios_ecocardio', 'estudios_de_mapa', 'estudios_de_ergonometria', 'estudios_de_tac', 'estudios_de_rnm', 'estudios_de_electrofisiologia', 'holter', 'hc_', 'isquemica', 'revasc', 'valvulopatia', 'ingresado']):
        return 'MOD_4_HISTORIA_CARDIO'

    # 7. Historia No Cardiovascular
    if any(k in norm for k in ['cancer', 'problemas_respiratorios', 'salud_mental', 'alergias', 'otras', 'reumatolog', 'nc_', 'oncolog', 'quimio', 'radioter']):
        return 'MOD_4_HISTORIA_NO_CARDIO'

    # 8. Factores Modificables (Predeterminado para factores de riesgo tradicionales)
    return 'MOD_3_FACTORES_MOD'



def _match_column_to_field(col_name):
    """Encuentra qué campo del sistema corresponde a una columna de SPSS dada."""
    norm_c = normalize_var_name(col_name)
    for field_key, aliases in STANDARD_FIELD_ALIASES.items():
        for alias in aliases:
            if norm_c == alias:
                return field_key
    # Búsqueda por contención
    for field_key, aliases in STANDARD_FIELD_ALIASES.items():
        for alias in aliases:
            if len(alias) >= 4 and (alias in norm_c or norm_c in alias):
                return field_key
    return None



def get_column_destination(col_name):
    """Identifica con precisión médica el módulo y campo destino en PostgreSQL para una columna SPSS."""
    matched_field = _match_column_to_field(col_name)
    if matched_field and matched_field in FIELD_DESTINATIONS:
        return FIELD_DESTINATIONS[matched_field]

    norm = normalize_var_name(col_name)

    # 0. Estudios Solicitados
    if any(k in norm for k in ['usted_se_ha_realizado_estudios', 'estudios_de_mapa', 'estudios_holter_ecg', 'estudios_clinicos', 'estudios_de_ergonometria', 'estudios_de_tac', 'estudios_de_rnm', 'estudios_de_electrofisiologia']):
        return ('Estudios Solicitados', f'Estudio Indicado al Paciente ({col_name})')

    # 1. Ecocardiograma
    if any(k in norm for k in ['eco', 'mitral', 'aortic', 'tritusp', 'tricusp', 'pulmonar', 'pulmunar', 'ventricul', 'auricul', 'onda_e', 'onda_a', 'onda_s', 'llenado', 'regurgit', 'valvul', 'estenosis', 'esternosis', 'gradiente', 'gradiante', 'tapse', 'mapse', 'dopler', 'biplanar', 'subcostal', 'cayado', 'engrados', 'movilidad', 'prolapso', 'velocidad', 'thp', 'jet_color', 'derrame', 'contractilidad', 'presiones_llenado', 'araesternal', 'area_sistolica', 'area_valvular', 'itv_de_tsvi', 'funcion_sistolica']):
        return ('Ecocardiograma', f'Parámetro Ecocardiográfico ({col_name})')

    # 2. Electrocardiograma
    if any(k in norm for k in ['ecg', 'ritmo', 'qrs', 'qt', 'bazett', 'bloqueo', 'onda_p', 'hemibloqueo', 'onda_delta', 'cubeta', 'onda_q', 't_negativa', 'ascenso_st', 'descenso_st']):
        return ('Electrocardiograma', f'Parámetro ECG ({col_name})')

    # 3. Laboratorio Clínico
    if any(k in norm for k in ['lab', 'hematies', 'hemoglobin', 'hematocrito', 'vcm', 'hcm', 'chcm', 'leucocit', 'neutrofil', 'eosinofil', 'basofil', 'linfocit', 'monocit', 'plaquet', 'inr', 'fibrinogen', 'protombina', 'tromboplastina', 'glucosa', 'glicosilada', 'hba1c', 'insulina', 'homair', 'homa_ir', 'urea', 'creatin', 'filtracion_glomerular', 'tfg', 'colesterol', 'triglic', 'hdl', 'ldl', 'vdl', 'lipoproteina', 'apolipoproteina', 'got', 'gpt', 'ggt', 'tsh', 'tiroide', 'potasio', 'calcio', 'magnesio', 'sodio', 'homocisteina', 'pcr', 'acido_urico', 'orina', 'transferrina', 'ferritina']):
        return ('Laboratorio Clínico', f'Bioquímica / Hematología ({col_name})')

    # 4. Signos Vitales
    if any(k in norm for k in ['tas', 'tad', 'frecuencia', 'saturacion', 'soplo', 'pulso', 'auscult', 'extratono']):
        return ('Signos Vitales', f'Constante Vital ({col_name})')

    # 5. Antropometría
    if any(k in norm for k in ['peso', 'talla', 'imc', 'perimetro', 'asc']):
        return ('Antropometría', f'Medición Antropométrica ({col_name})')

    # 6. Cuestionarios Específicos
    sec_code = classify_spss_question_section(col_name)
    if sec_code == 'MOD_6_PREDIMED':
        return ('Cuestionario Dieta MEDAS', f'Hábito Nutricional ({col_name})')
    if sec_code == 'MOD_6_ACTIVIDAD_FISICA':
        return ('Cuestionario Actividad Física', f'Hábito Actividad Física ({col_name})')
    if sec_code == 'MOD_4_COVID':
        return ('Cuestionario COVID-19', f'Historia COVID / Secuelas ({col_name})')
    if sec_code == 'MOD_3_FACTORES_EMERG':
        return ('Cuestionario Factores Emergentes', f'Factor Emergente ({col_name})')
    if sec_code == 'MOD_3_ANTECEDENTES_FAM':
        return ('Cuestionario Antecedentes Familiares', f'Antecedente Familiar ({col_name})')
    if sec_code == 'MOD_4_HISTORIA_CARDIO':
        return ('Cuestionario Historia Cardiovascular', f'Historia Cardiovascular ({col_name})')
    if sec_code == 'MOD_4_HISTORIA_NO_CARDIO':
        return ('Cuestionario Historia No Cardiovascular', f'Antecedente No Cardiovascular ({col_name})')

    return ('Cuestionario Factores Modificables', f'Factor de Riesgo ({col_name})')



def detect_column_typos(column_names):
    """
    Detecta y clasifica errores gramaticales o tipográficos en los nombres de columnas
    e identifica exactamente en qué módulo y campo de la base de datos va cada dato.
    """
    detected = []
    seen = set()
    for col in column_names:
        current_col = col
        fixes = []
        target_destination = None
        for pattern, replacement, explanation, destination, err_type in COLUMN_TYPO_RULES:
            if re.search(pattern, current_col, re.IGNORECASE):
                current_col = re.sub(pattern, replacement, current_col, flags=re.IGNORECASE)
                fixes.append(explanation)
                if not target_destination:
                    target_destination = destination

        if current_col != col:
            key = (col, current_col)
            if key not in seen:
                seen.add(key)
                if not target_destination:
                    mod, fld = get_column_destination(current_col)
                    target_destination = f"{mod} / {fld}"
                detected.append({
                    "original": col,
                    "corrected": current_col,
                    "explanation": " | ".join(fixes),
                    "destination": target_destination,
                    "type": "correccion"
                })
    return detected




_CANTONS_CACHE = None

def _get_cantons_cache():
    global _CANTONS_CACHE
    if _CANTONS_CACHE is None:
        _CANTONS_CACHE = list(Canton.objects.select_related('province').all())
    return _CANTONS_CACHE


def _resolve_canton_safe(canton_name, province_name=None):
    """Resuelve un cantón de Ecuador ignorando tildes y mayúsculas de forma optimizada."""
    if not canton_name:
        return None

    # Manejar códigos numéricos de CIUDAD (ej. 5.0, 5, '5.0', '5')
    try:
        c_num = int(float(canton_name))
        if c_num in CIUDAD_CODE_MAP:
            canton_name = CIUDAD_CODE_MAP[c_num]
    except (ValueError, TypeError):
        pass

    raw_canton = str(canton_name).strip()
    norm_c = unicodedata.normalize('NFKD', raw_canton).encode('ASCII', 'ignore').decode('utf-8').upper()

    cantons = _get_cantons_cache()
    for c in cantons:
        c_norm = unicodedata.normalize('NFKD', c.name).encode('ASCII', 'ignore').decode('utf-8').upper()
        if c_norm == norm_c:
            return c

    # Búsqueda parcial (requiere al menos 4 caracteres para evitar falsos positivos con dígitos o siglas)
    if len(norm_c) >= 4:
        for c in cantons:
            c_norm = unicodedata.normalize('NFKD', c.name).encode('ASCII', 'ignore').decode('utf-8').upper()
            if c_norm in norm_c or norm_c in c_norm:
                return c

    return None



def _is_empty_or_nan(val):
    """Determina si un valor debe considerarse nulo/vacío en la importación."""
    if val is None:
        return True
    if isinstance(val, (float, int)):
        import math
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return True
        return False
    s = str(val).strip()
    if s == '' or s.lower() in ('nan', 'none', 'null', 'na', '<na>'):
        return True
    return False


def _get_val_and_label(val, val_labels_dict):
    """Extrae tanto el valor crudo como la etiqueta textual de SPSS/R si existe."""
    if val is None:
        return None, ""
    if isinstance(val, float):
        import math
        if math.isnan(val) or math.isinf(val):
            return None, ""
    if not val_labels_dict:
        return val, ""

    lbl = None
    candidates = [val]
    if isinstance(val, (int, float)):
        try:
            f = float(val)
            candidates.extend([f, int(f), str(val), f"{f:.1f}", str(int(f))])
        except Exception:
            pass
    elif isinstance(val, str):
        s = val.strip()
        candidates.append(s)
        try:
            f = float(s)
            candidates.extend([f, int(f), f"{f:.1f}", str(int(f))])
        except Exception:
            pass

    for c in candidates:
        if c in val_labels_dict:
            lbl = val_labels_dict[c]
            break

    lbl_str = str(lbl).strip() if lbl is not None else ""
    return val, lbl_str



def _clean_decimal(val, max_digits=5, decimal_places=2):
    """Convierte con seguridad un valor numérico a Decimal respetando max_digits y decimal_places para evitar overflow."""
    if val is None or str(val).strip() == '' or str(val).strip().lower() in ('nan', 'none', 'null', 'na', '<na>'):
        return None
    try:
        import math
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        max_int = max_digits - decimal_places
        limit = (10 ** max_int) - (10 ** -decimal_places)
        if -limit <= f <= limit:
            d = Decimal(str(round(f, decimal_places)))
            if not d.is_nan() and not d.is_infinite():
                return d
        return None
    except Exception:
        return None


# -----------------------------------------------------------------------------
# 1. ANÁLISIS INTELIGENTE DEL ARCHIVO .SAV Y RSTUDIO (.RDS / .RDATA)
# -----------------------------------------------------------------------------

