"""
apps/clinical/services/sav_exporter.py
Servicio de exportación de base de datos a formatos oficiales:
- IBM SPSS Statistics (.sav, .zsav)
- RStudio (.rds, .RData)
- Delimitado Excel / CSV (.csv UTF-8 con BOM)
Garantiza la exportación de las columnas clínicas históricas idénticas a
'Base_datos_Unemi_CardioUnemi-ACTUALIZADO.sav' más todos los nuevos campos
del Cuestionario UNEMI 2026, conservando tipos, diccionarios de variables,
etiquetas de valor (value labels) y respuestas no modeladas.
"""

import os
import re
import tempfile
import datetime
from pathlib import Path
from decimal import Decimal

import numpy as np
import pandas as pd
import pyreadstat
import pyreadr
from django.conf import settings

from clinical.services.record_selection import selected_visits
from clinical.models import Patient, Visit, VisitAnswer
from clinical.services.sav_importer import normalize_var_name

# Catálogo oficial de nuevas variables incorporadas en Cuestionario UNEMI 2026
NEW_2026_EXPORT_COLUMNS = [
    # Módulo Factores de Riesgo Modificables - Drogas (Frecuencia detallada y cesación)
    ('DROGAS_DOSIS_DIARIA', 'Drogas: Consumo con dosis diaria (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('DROGAS_DOSIS_SEMANAL', 'Drogas: Consumo con dosis semanal (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('DROGAS_DOSIS_OCASIONAL', 'Drogas: Consumo con dosis ocasional (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CHK_EX_DROGAS', 'Drogas: Ex-consumidor > 1 año (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('DROGAS_CUALES', 'Drogas: Sustancias que consume o consumió', 'object', {}),
    ('DROGAS_FRECUENCIA', 'Drogas: Frecuencia general de consumo', 'object', {}),

    # Módulo Historia Cardiovascular Actual (Pág. 4-5)
    ('HC_ISQUEMICA', 'Historia cardiovascular: Cardiopatía isquémica (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_ISQUEMICA_ANGINA', 'Cardiopatía isquémica: Angina de pecho (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_ISQUEMICA_INFARTO', 'Cardiopatía isquémica: Infarto de miocardio (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_REVASC', 'Historia cardiovascular: Revascularización coronaria (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('REVASCULARIZACION_TIPO', 'Revascularización coronaria: Tipo (1=Angioplastia, 2=Bypass, 3=Ambas)', 'float64', {1.0: 'Angioplastia', 2.0: 'Bypass', 3.0: 'Ambas'}),
    ('HC_INSUF_CARDIACA', 'Historia cardiovascular: Insuficiencia cardíaca (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_VALVULOPATIA', 'Historia cardiovascular: Valvulopatía (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_VALVULOPATIA_CUALES', 'Valvulopatía: ¿Cuáles válvulas o lesiones?', 'object', {}),
    ('HC_VALVULOPATIA_OPERADO', 'Valvulopatía: Operado por este motivo (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_HOSPITALIZACION', 'Ingreso hospitalario por problema cardíaco (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('HC_HOSPITALIZACION_MOTIVO', 'Ingreso hospitalario: Motivo de internamiento', 'object', {}),

    # Módulo Historia No Cardiovascular - Cáncer
    ('NC_CANCER', 'Historia no cardiovascular: Cáncer (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_PULMON', 'Cáncer: Pulmón (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_PROSTATA', 'Cáncer: Próstata (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_COLON', 'Cáncer: Colon (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_MAMA', 'Cáncer: Mama (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_VEJIGA', 'Cáncer: Vejiga (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_UTERO', 'Cáncer: Útero (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_OVARIO', 'Cáncer: Ovario (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_OTRO', 'Cáncer: Otro tipo tumoral (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_OTRO_DETALLE', 'Cáncer: Especificar otro tipo tumoral', 'object', {}),
    ('CANCER_QT', 'Cáncer: Recibió Quimioterapia (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('CANCER_RT', 'Cáncer: Recibió Radioterapia (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),

    # Módulo Estudios Prescritos (Catálogo Oficial 2026: 8 ítems + Observaciones)
    ('EST_ANALISIS_CLINICOS', 'Estudios prescritos: 1.- Análisis clínicos (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_ERGOMETRIA_SPECT', 'Estudios prescritos: 2.- Ergometría con SPECT (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_TAC_CARDIACO', 'Estudios prescritos: 3.- TAC Cardíaco (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_RNM_CARDIACO', 'Estudios prescritos: 4.- RNM Cardíaco (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_ELECTROFISIOLOGIA', 'Estudios prescritos: 5.- Electrofisiología Cardíaca (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_ECOCARDIOGRAMA', 'Estudios prescritos: 6.- Ecocardiografía (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_HOLTER', 'Estudios prescritos: 7.- Holter ECG (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('EST_MAPA', 'Estudios prescritos: 8.- MAPA (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('ESTUDIOS_OBSERVACIONES', 'Estudios prescritos: Observaciones y otros estudios indicados', 'object', {}),

    # Módulo Estilo de Vida: PREDIMED (Lácteos y Sofrito 2026)
    ('PRED_Q13_CONSUME', 'PREDIMED: 13. Consume leche de vaca (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('PRED_LECHE_VASOS_DIA', 'PREDIMED: Leche de vaca - vasos al día', 'float64', {}),
    ('PRED_LECHE_VASOS_SEM', 'PREDIMED: Leche de vaca - vasos a la semana', 'float64', {}),
    ('PRED_LECHE_TIPO', 'PREDIMED: Leche de vaca - tipo (Entera, Desnatada, etc.)', 'object', {}),
    ('PRED_Q14_CONSUME', 'PREDIMED: 14. Consume queso (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('PRED_QUESO_VECES_SEM', 'PREDIMED: Queso - veces a la semana', 'float64', {}),
    ('PRED_QUESO_GRAMOS', 'PREDIMED: Queso - gramos consumidos', 'float64', {}),
    ('PRED_Q15_CONSUME', 'PREDIMED: 15. Consume yogurt (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
    ('PRED_YOGURT_CANT_SEM', 'PREDIMED: Yogurt - unidades a la semana', 'float64', {}),
    ('PRED_YOGURT_TIPO', 'PREDIMED: Yogurt - tipo', 'object', {}),
    ('PRED_Q19', 'PREDIMED: 19. Consume sofrito casero >= 2 veces/sem (0=No, 1=Sí)', 'float64', {0.0: 'No', 1.0: 'Sí'}),
]

# Cache en memoria de la plantilla de columnas y metadatos
_SAV_TEMPLATE_CACHE = None


def get_sav_template_metadata():
    """
    Carga e indexa en memoria las columnas y metadatos oficiales de CardioUNEMI,
    integrando las 342 columnas de la cohorte histórica más las variables del Cuestionario 2026.
    """
    global _SAV_TEMPLATE_CACHE
    if _SAV_TEMPLATE_CACHE is not None:
        return _SAV_TEMPLATE_CACHE

    spec_json_path = Path(__file__).resolve().parent / 'sav_columns_spec.json'

    cols = []
    col_dtypes = {}
    col_value_labels = {}
    col_names_to_labels = {}

    if spec_json_path.exists():
        import json
        with open(spec_json_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        cols = spec.get('columns', [])
        col_names_to_labels = spec.get('column_labels', {})
        raw_val_labels = spec.get('value_labels', {})
        raw_dtypes = spec.get('dtypes', {})
        col_dtypes = {col: str(dt) for col, dt in raw_dtypes.items()}

        # Convertir llaves numéricas en value labels
        for col, vmap in raw_val_labels.items():
            parsed_vmap = {}
            for k, v in vmap.items():
                try:
                    num_k = float(k)
                    if num_k.is_integer():
                        num_k = int(num_k)
                    parsed_vmap[num_k] = v
                except (ValueError, TypeError):
                    parsed_vmap[k] = v
            col_value_labels[col] = parsed_vmap
    else:
        template_candidates = [
            Path(settings.BASE_DIR) / 'Base_datos_Unemi_CardioUnemi-ACTUALIZADO.sav',
            Path(settings.BASE_DIR) / 'media' / 'Base_datos_Unemi_CardioUnemi-ACTUALIZADO.sav',
        ]
        template_path = None
        for candidate in template_candidates:
            if candidate.exists():
                template_path = candidate
                break

        if template_path and template_path.exists():
            df_orig, meta = pyreadstat.read_sav(str(template_path))
            cols = meta.column_names
            col_dtypes = {col: str(df_orig[col].dtype) for col in cols}
            col_value_labels = meta.variable_value_labels or {}
            col_names_to_labels = meta.column_names_to_labels or {}

    if not cols:
        raise RuntimeError("No se pudieron cargar las especificaciones de las columnas del dataset SPSS.")

    # Incorporar las nuevas columnas del Cuestionario UNEMI 2026
    for col_name, col_label, col_dt, v_labels in NEW_2026_EXPORT_COLUMNS:
        if col_name not in cols:
            cols.append(col_name)
            col_dtypes[col_name] = col_dt
            col_names_to_labels[col_name] = col_label
            if v_labels:
                col_value_labels[col_name] = v_labels

    # Construir mapa inverso de etiquetas a valores numéricos
    lbl_to_val_map = {}
    for col, vmap in col_value_labels.items():
        inv = {}
        for num_v, lbl_str in vmap.items():
            s = str(lbl_str).strip().upper()
            inv[s] = num_v
            norm_lbl = normalize_var_name(lbl_str)
            if norm_lbl:
                inv[norm_lbl.upper()] = num_v
            if isinstance(num_v, (int, float)) and num_v == int(num_v):
                inv[str(int(num_v))] = num_v
            inv[str(num_v)] = num_v
        lbl_to_val_map[col] = inv

    _SAV_TEMPLATE_CACHE = {
        'columns': cols,
        'dtypes': col_dtypes,
        'value_labels': col_value_labels,
        'labels': col_names_to_labels,
        'lbl_to_val_map': lbl_to_val_map
    }
    return _SAV_TEMPLATE_CACHE


def _is_yes(val):
    if val is None or str(val).strip() == '':
        return False
    return str(val).strip().lower() in ('si', 'sí', '1', '1.0', 'true', 'yes')


def _to_float(val):
    if val is None or str(val).strip() == '':
        return np.nan
    try:
        return float(val)
    except (ValueError, TypeError):
        return np.nan


def generate_export_dataset(patient_ids=None, format_type='sav'):
    """
    Genera el dataset de exportación con todas las columnas clínicas oficiales y los nuevos campos 2026.
    Soporta los mismos formatos de exportación que se admiten en importación:
      - 'sav': IBM SPSS Statistics (.sav)
      - 'zsav': IBM SPSS Comprimido (.zsav)
      - 'rds': RStudio Dataframe serializado (.rds)
      - 'rdata' / 'rda': RStudio Workspace (.RData)
      - 'csv': Archivo delimitado por comas (.csv UTF-8 BOM)
    Retorna: (file_bytes, filename, content_type)
    """
    tpl = get_sav_template_metadata()
    cols = tpl['columns']
    col_dtypes = tpl['dtypes']
    col_value_labels = tpl['value_labels']
    col_names_to_labels = tpl['labels']
    lbl_to_val_map = tpl['lbl_to_val_map']

    # 1. Obtener visitas filtradas
    visits_qs = Visit.objects.filter(patient__status=Patient.Status.ACTIVE).select_related(
        'patient', 'patient__institution', 'patient__birth_canton', 'patient__birth_canton__province',
        'patient__sex', 'patient__ethnicity', 'residence_canton', 'residence_canton__province',
        'staff_category', 'professional_category', 'marital_status', 'living_situation',
        'education_level', 'work_schedule', 'housing_type', 'income_range',
        'anthropometry', 'vital_signs', 'electrocardiogram', 'laboratory', 'echocardiogram',
        'ordered_studies'
    ).order_by('visit_id')

    if patient_ids is not None:
        visits = selected_visits(patient_ids, active_only=True)
        visits_qs = visits_qs.filter(pk__in=[visit.pk for visit in visits])
    visits = list(visits_qs)

    # 2. Cargar todas las respuestas clínicas en bloque
    answers_by_visit = {}
    va_qs = VisitAnswer.objects.filter(visit__in=visits).select_related('question', 'selected_option')
    for va in va_qs:
        v_id = va.visit_id
        if v_id not in answers_by_visit:
            answers_by_visit[v_id] = {}
        code = va.question.code
        val = (va.selected_option.label if va.selected_option else
               va.numeric_value if va.numeric_value is not None else va.text_value)
        answers_by_visit[v_id][code] = val
        clean_code = normalize_var_name(code)[:30]
        answers_by_visit[v_id][clean_code] = val
        answers_by_visit[v_id][code.lower()] = val
        answers_by_visit[v_id][clean_code.lower()] = val

    # 3. Construir filas de datos
    rows_data = []
    for v in visits:
        p = v.patient
        ans = answers_by_visit.get(v.visit_id, {})
        studies = getattr(v, 'ordered_studies', None)
        row = {}

        for col in cols:
            clean = normalize_var_name(col)[:30]
            val = ans.get(col) or ans.get(col.lower()) or ans.get(clean) or ans.get(clean.lower())

            # Mapeo de respaldo desde modelos relacionales de la BD y nuevos campos 2026
            if val is None or str(val).strip() == '':
                c_up = col.upper()
                if clean.upper() == 'CODIGO':
                    val = v.study_code
                elif col == 'UNIVERSIDAD':
                    val = 2.0 if (p and p.institution and 'ESPOL' in p.institution.acronym.upper()) else 1.0
                elif col == 'FECHA':
                    val = v.visit_date
                elif 'AO' in c_up or 'AO' in col:
                    val = float(v.visit_date.year) if v.visit_date else 2026.0
                elif col == 'EDAD':
                    if v.visit_date and p and p.birth_date:
                        val = float(v.visit_date.year - p.birth_date.year - (
                            (v.visit_date.month, v.visit_date.day) < (p.birth_date.month, p.birth_date.day)
                        ))
                    else:
                        val = np.nan
                elif col == 'FECHA_DE_NACIMIENTO':
                    val = p.birth_date if p else None
                elif col == 'SEXO':
                    val = 2.0 if (p and p.sex and 'M' in p.sex.name.upper() and not 'H' in p.sex.name.upper()) else 1.0
                elif col == 'CIUDAD':
                    val = v.residence_canton.name if v.residence_canton else (p.birth_canton.name if p and p.birth_canton else 'Milagro')
                elif col == 'PROVINCIA':
                    val = v.residence_canton.province.name if (v.residence_canton and v.residence_canton.province) else 'Guayas'
                elif col == 'LUGAR_DE_NACIMIENTO':
                    val = p.birth_canton.name if (p and p.birth_canton) else 'Milagro'
                elif col == 'PROVINCIA_NAC':
                    val = p.birth_canton.province.name if (p and p.birth_canton and p.birth_canton.province) else 'Guayas'
                elif col == 'RAZA':
                    val = p.ethnicity.name if (p and p.ethnicity) else 'Mestizo'
                elif col == 'ESTADO_CIVIL':
                    val = v.marital_status.name if v.marital_status else None
                elif 'HIJOS' in c_up:
                    val = float(v.num_children) if v.num_children is not None else np.nan
                elif 'CONVIVE_CON' in c_up or 'CON_QUIEN_VIVE' in c_up:
                    val = v.living_situation.name if v.living_situation else None
                elif 'CONVIVIENTES' in c_up or 'CONVIVE_CON_USTES' in c_up or 'CONVIVE_CON_USTED' in c_up:
                    val = float(v.num_cohabitants) if v.num_cohabitants is not None else np.nan
                elif 'ESTUDIOS' in c_up:
                    val = v.education_level.name if v.education_level else None
                elif 'HORARIO' in c_up:
                    val = v.work_schedule.name if v.work_schedule else None
                elif 'PROFESIONAL' in c_up:
                    val = v.professional_category.name if v.professional_category else None
                elif 'VIVIENDA' in c_up:
                    val = v.housing_type.name if v.housing_type else None
                elif 'INGRESOS' in c_up:
                    val = v.income_range.name if v.income_range else None

                # Antropometría
                elif col == 'PESO_KG' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.weight_kg:
                    val = float(v.anthropometry.weight_kg)
                elif col == 'TALLA_CM' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.height_cm:
                    val = float(v.anthropometry.height_cm)
                elif col == 'IMC_KGM2' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.bmi:
                    val = float(v.anthropometry.bmi)
                elif 'PER' in c_up and 'ABDOMINAL' in c_up and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.waist_circumference_cm:
                    val = float(v.anthropometry.waist_circumference_cm)
                elif col == 'ASC_M2' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.body_surface_area:
                    val = float(v.anthropometry.body_surface_area)

                # Signos Vitales
                elif col == 'TAS_TS' and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.systolic_bp:
                    val = float(v.vital_signs.systolic_bp)
                elif col == 'TAS_MMHG' and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.diastolic_bp:
                    val = float(v.vital_signs.diastolic_bp)
                elif 'SATURAC' in c_up and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.oxygen_saturation:
                    val = float(v.vital_signs.oxygen_saturation)
                elif 'FRECUENCIA' in c_up and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.heart_rate:
                    val = float(v.vital_signs.heart_rate)
                elif col == 'SOPLOS_CARDIACOS' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = 1.0 if (v.vital_signs.systolic_murmur or v.vital_signs.diastolic_murmur) else 0.0
                elif col == 'PULSOSPEDIOS' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = 1.0 if v.vital_signs.pedal_pulses_symmetric else 0.0
                elif col == 'EXPLORACION_RESPIRATORIA' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = 1.0 if v.vital_signs.pulmonary_auscultation_normal else 0.0
                elif col == 'EXPLORACION_ABDOMINAL' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = 1.0 if v.vital_signs.abdominal_auscultation_normal else 0.0

                # ECG
                elif col == 'ECG_RITMO' and hasattr(v, 'electrocardiogram') and v.electrocardiogram and v.electrocardiogram.rhythm:
                    val = v.electrocardiogram.rhythm.name
                elif 'INTERVALO_PR' in c_up and hasattr(v, 'electrocardiogram') and v.electrocardiogram and v.electrocardiogram.pr_interval_ms:
                    val = float(v.electrocardiogram.pr_interval_ms) / 1000.0
                elif 'QR' in c_up and hasattr(v, 'electrocardiogram') and v.electrocardiogram and v.electrocardiogram.qrs_duration_ms:
                    val = float(v.electrocardiogram.qrs_duration_ms) / 1000.0
                elif 'QT_SEG' in c_up and hasattr(v, 'electrocardiogram') and v.electrocardiogram and v.electrocardiogram.qt_interval_ms:
                    val = float(v.electrocardiogram.qt_interval_ms) / 1000.0
                elif 'BASET' in c_up and hasattr(v, 'electrocardiogram') and v.electrocardiogram and v.electrocardiogram.qtc_bazett_ms:
                    val = float(v.electrocardiogram.qtc_bazett_ms)
                elif 'EJE_ELECTRICO' in c_up and hasattr(v, 'electrocardiogram') and v.electrocardiogram and v.electrocardiogram.qrs_axis_degrees:
                    val = float(v.electrocardiogram.qrs_axis_degrees)

                # Laboratorio
                elif hasattr(v, 'laboratory') and v.laboratory:
                    lab = v.laboratory
                    if 'GLUCOSA' in c_up and lab.glucose_mg_dl: val = float(lab.glucose_mg_dl)
                    elif 'UREA' in c_up and lab.urea_mg_dl: val = float(lab.urea_mg_dl)
                    elif 'CREATINA' in c_up and lab.creatinine_mg_dl: val = float(lab.creatinine_mg_dl)
                    elif 'COLESTEROL_TOTAL' in c_up and lab.total_cholesterol_mg_dl: val = float(lab.total_cholesterol_mg_dl)
                    elif 'HDL' in c_up and lab.hdl_mg_dl: val = float(lab.hdl_mg_dl)
                    elif 'LDL' in c_up and lab.ldl_mg_dl: val = float(lab.ldl_mg_dl)
                    elif 'TRIGLICERIDOS' in c_up and lab.triglycerides_mg_dl: val = float(lab.triglycerides_mg_dl)
                    elif 'HEMATIES' in c_up and lab.rbc_millions: val = float(lab.rbc_millions)
                    elif 'HEMOGLOBINA' in c_up and lab.hemoglobin_g_dl: val = float(lab.hemoglobin_g_dl)
                    elif 'HEMATOCRITO' in c_up and lab.hematocrit_percentage: val = float(lab.hematocrit_percentage)
                    elif 'LEUCOCITOS' in c_up and lab.wbc_thousands: val = float(lab.wbc_thousands)
                    elif 'PLAQUETAS' in c_up and lab.platelets_thousands: val = float(lab.platelets_thousands)
                    elif 'GOT' in c_up and lab.ast_got_u_l: val = float(lab.ast_got_u_l)
                    elif 'GPT' in c_up and lab.alt_gpt_u_l: val = float(lab.alt_gpt_u_l)
                    elif 'GGT' in c_up and lab.ggt_u_l: val = float(lab.ggt_u_l)
                    elif 'TSH' in c_up and lab.tsh_u_iu_ml: val = float(lab.tsh_u_iu_ml)

                # Ecocardiograma
                elif hasattr(v, 'echocardiogram') and v.echocardiogram:
                    echo = v.echocardiogram
                    if 'FRACCION_EYECCION' in c_up and echo.lvef_percentage: val = float(echo.lvef_percentage)

                # Nuevos campos Cuestionario UNEMI 2026: Drogas
                elif col == 'DROGAS_DOSIS_DIARIA':
                    val = 1.0 if _is_yes(ans.get('drogas_dosis_diaria')) else (0.0 if ans.get('drogas_dosis_diaria') is not None else np.nan)
                elif col == 'DROGAS_DOSIS_SEMANAL':
                    val = 1.0 if _is_yes(ans.get('drogas_dosis_semanal')) else (0.0 if ans.get('drogas_dosis_semanal') is not None else np.nan)
                elif col == 'DROGAS_DOSIS_OCASIONAL':
                    val = 1.0 if _is_yes(ans.get('drogas_dosis_ocasional')) else (0.0 if ans.get('drogas_dosis_ocasional') is not None else np.nan)
                elif col == 'CHK_EX_DROGAS':
                    val = 1.0 if _is_yes(ans.get('chk_ex_drogas')) else (0.0 if ans.get('chk_ex_drogas') is not None else np.nan)
                elif col == 'DROGAS_CUALES':
                    val = ans.get('drogas_cuales', '')
                elif col == 'DROGAS_FRECUENCIA':
                    val = ans.get('drogas_frecuencia', '')

                # Nuevos campos Cuestionario UNEMI 2026: Historia Cardiovascular
                elif col == 'HC_ISQUEMICA':
                    val = 1.0 if _is_yes(ans.get('hc_isquemica') or ans.get('cardiopatia_isquemica')) else 0.0
                elif col == 'HC_ISQUEMICA_ANGINA':
                    val = 1.0 if _is_yes(ans.get('hc_isquemica_angina')) else 0.0
                elif col == 'HC_ISQUEMICA_INFARTO':
                    val = 1.0 if _is_yes(ans.get('hc_isquemica_infarto')) else 0.0
                elif col == 'HC_REVASC':
                    val = 1.0 if _is_yes(ans.get('hc_revasc') or ans.get('revascularizacion_coronaria')) else 0.0
                elif col == 'REVASCULARIZACION_TIPO':
                    raw_rev = str(ans.get('revascularizacion_tipo') or ans.get('hc_revasc_tipo') or '').lower()
                    if 'ambas' in raw_rev or '3' in raw_rev: val = 3.0
                    elif 'bypass' in raw_rev or '2' in raw_rev: val = 2.0
                    elif 'angioplastia' in raw_rev or '1' in raw_rev: val = 1.0
                    else: val = np.nan
                elif col == 'HC_INSUF_CARDIACA':
                    val = 1.0 if _is_yes(ans.get('hc_insuf_cardiaca') or ans.get('insuficiencia_cardiaca')) else 0.0
                elif col == 'HC_VALVULOPATIA':
                    val = 1.0 if _is_yes(ans.get('hc_valvulopatia') or ans.get('valvulopatia')) else 0.0
                elif col == 'HC_VALVULOPATIA_CUALES':
                    val = ans.get('hc_valvulopatia_cuales') or ans.get('valvulopatia_cuales') or ''
                elif col == 'HC_VALVULOPATIA_OPERADO':
                    val = 1.0 if _is_yes(ans.get('hc_valvulopatia_operado') or ans.get('valvulopatia_operado')) else 0.0
                elif col == 'HC_HOSPITALIZACION':
                    val = 1.0 if _is_yes(ans.get('hc_ingresado') or ans.get('hc_hospitalizacion') or ans.get('ingreso_hospitalario_problema_cardiaco')) else 0.0
                elif col == 'HC_HOSPITALIZACION_MOTIVO':
                    val = ans.get('hc_ingresado_cual') or ans.get('hc_hospitalizacion_motivo') or ''

                # Nuevos campos Cuestionario UNEMI 2026: Cáncer
                elif col == 'NC_CANCER':
                    val = 1.0 if _is_yes(ans.get('nc_cancer') or ans.get('historia_cancer')) else 0.0
                elif col == 'CANCER_PULMON':
                    val = 1.0 if _is_yes(ans.get('cancer_pulmon')) else 0.0
                elif col == 'CANCER_PROSTATA':
                    val = 1.0 if _is_yes(ans.get('cancer_prostata')) else 0.0
                elif col == 'CANCER_COLON':
                    val = 1.0 if _is_yes(ans.get('cancer_colon')) else 0.0
                elif col == 'CANCER_MAMA':
                    val = 1.0 if _is_yes(ans.get('cancer_mama')) else 0.0
                elif col == 'CANCER_VEJIGA':
                    val = 1.0 if _is_yes(ans.get('cancer_vejiga')) else 0.0
                elif col == 'CANCER_UTERO':
                    val = 1.0 if _is_yes(ans.get('cancer_utero')) else 0.0
                elif col == 'CANCER_OVARIO':
                    val = 1.0 if _is_yes(ans.get('cancer_ovario')) else 0.0
                elif col == 'CANCER_OTRO':
                    val = 1.0 if _is_yes(ans.get('cancer_otro')) else 0.0
                elif col == 'CANCER_OTRO_DETALLE':
                    val = ans.get('cancer_otro_detalle', '')
                elif col == 'CANCER_QT':
                    val = 1.0 if _is_yes(ans.get('cancer_qt') or ans.get('cancer_quimioterapia')) else 0.0
                elif col == 'CANCER_RT':
                    val = 1.0 if _is_yes(ans.get('cancer_rt') or ans.get('cancer_radioterapia')) else 0.0

                # Nuevos campos Cuestionario UNEMI 2026: Estudios Prescritos
                elif col == 'EST_ANALISIS_CLINICOS':
                    val = 1.0 if (studies and studies.clinical_analysis) or _is_yes(ans.get('est_analisis_clinicos')) else 0.0
                elif col == 'EST_ERGOMETRIA_SPECT':
                    val = 1.0 if (studies and studies.ergometry_spect) or _is_yes(ans.get('est_ergometria_spect')) else 0.0
                elif col == 'EST_TAC_CARDIACO':
                    val = 1.0 if (studies and studies.cardiac_ct) or _is_yes(ans.get('est_tac_cardiaco')) else 0.0
                elif col == 'EST_RNM_CARDIACO':
                    val = 1.0 if (studies and studies.cardiac_mri) or _is_yes(ans.get('est_rnm_cardiaco')) else 0.0
                elif col == 'EST_ELECTROFISIOLOGIA':
                    val = 1.0 if (studies and studies.electrophysiology) or _is_yes(ans.get('est_electrofisiologia')) else 0.0
                elif col == 'EST_ECOCARDIOGRAMA':
                    val = 1.0 if _is_yes(ans.get('est_ecocardiograma') or ans.get('est_eco')) else 0.0
                elif col == 'EST_HOLTER':
                    val = 1.0 if _is_yes(ans.get('est_holter')) else 0.0
                elif col == 'EST_MAPA':
                    val = 1.0 if _is_yes(ans.get('est_mapa')) else 0.0
                elif col == 'ESTUDIOS_OBSERVACIONES':
                    val = ans.get('est_otros_detalle') or ans.get('estudios_observaciones') or ''

                # Nuevos campos Cuestionario UNEMI 2026: PREDIMED Lácteos y Sofrito
                elif col == 'PRED_Q13_CONSUME':
                    val = 1.0 if _is_yes(ans.get('pred_q13_consume')) else 0.0
                elif col == 'PRED_LECHE_VASOS_DIA':
                    val = _to_float(ans.get('pred_leche_vasos_dia'))
                elif col == 'PRED_LECHE_VASOS_SEM':
                    val = _to_float(ans.get('pred_leche_vasos_sem'))
                elif col == 'PRED_LECHE_TIPO':
                    val = ans.get('pred_leche_tipo', '')
                elif col == 'PRED_Q14_CONSUME':
                    val = 1.0 if _is_yes(ans.get('pred_q14_consume')) else 0.0
                elif col == 'PRED_QUESO_VECES_SEM':
                    val = _to_float(ans.get('pred_queso_veces_sem'))
                elif col == 'PRED_QUESO_GRAMOS':
                    val = _to_float(ans.get('pred_queso_gramos'))
                elif col == 'PRED_Q15_CONSUME':
                    val = 1.0 if _is_yes(ans.get('pred_q15_consume')) else 0.0
                elif col == 'PRED_YOGURT_CANT_SEM':
                    val = _to_float(ans.get('pred_yogurt_cant_sem'))
                elif col == 'PRED_YOGURT_TIPO':
                    val = ans.get('pred_yogurt_tipo', '')
                elif col == 'PRED_Q19':
                    val = 1.0 if _is_yes(ans.get('pred_q19')) else 0.0

            # 4. Formatear y convertir al tipo de dato exacto de la plantilla
            target_dtype = col_dtypes.get(col)
            if target_dtype and str(target_dtype).startswith('float'):
                if val is None or str(val).strip() == '' or str(val).lower() == 'nan':
                    row[col] = np.nan
                else:
                    col_inv = lbl_to_val_map.get(col, {})
                    val_str = str(val).strip().upper()
                    if val_str in col_inv:
                        row[col] = float(col_inv[val_str])
                    else:
                        norm_v = normalize_var_name(val_str).upper()
                        if norm_v in col_inv:
                            row[col] = float(col_inv[norm_v])
                        elif val_str in ('SI', 'SÍ', 'TRUE', 'YES'):
                            row[col] = 1.0
                        elif val_str in ('NO', 'FALSE'):
                            row[col] = 0.0
                        else:
                            try:
                                row[col] = float(val)
                            except (ValueError, TypeError):
                                row[col] = np.nan
            elif col in ['FECHA', 'FECHA_DE_NACIMIENTO']:
                if val is None or str(val).strip() == '':
                    row[col] = None
                else:
                    if hasattr(val, 'date'):
                        row[col] = val.date()
                    elif hasattr(val, 'year'):
                        row[col] = val
                    else:
                        try:
                            row[col] = datetime.date.fromisoformat(str(val).strip()[:10])
                        except Exception:
                            row[col] = None
            else:
                if val is None or str(val).lower() == 'nan':
                    row[col] = ''
                else:
                    row[col] = str(val).strip()

        rows_data.append(row)

    out_df = pd.DataFrame(rows_data, columns=cols)
    fecha_str = datetime.date.today().strftime('%Y%m%d')
    fmt = (format_type or 'sav').strip().lower()

    if fmt == 'csv':
        # Exportación en CSV / Excel UTF-8 BOM
        csv_bytes = out_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        filename = f"CardioUNEMI_Dataset_{fecha_str}.csv"
        content_type = "text/csv; charset=utf-8"
        return csv_bytes, filename, content_type

    elif fmt in ('rds',):
        # Exportación en RStudio RDS
        with tempfile.NamedTemporaryFile(suffix='.rds', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            pyreadr.write_rds(tmp_path, out_df)
            with open(tmp_path, 'rb') as f:
                rds_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass
        filename = f"CardioUNEMI_Dataset_{fecha_str}.rds"
        content_type = "application/octet-stream"
        return rds_bytes, filename, content_type

    elif fmt in ('rdata', 'rda', 'r'):
        # Exportación en RStudio Workspace RData
        with tempfile.NamedTemporaryFile(suffix='.RData', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            pyreadr.write_rdata(tmp_path, out_df, df_name='CardioUnemi')
            with open(tmp_path, 'rb') as f:
                rdata_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass
        filename = f"CardioUNEMI_Dataset_{fecha_str}.RData"
        content_type = "application/octet-stream"
        return rdata_bytes, filename, content_type

    elif fmt in ('zsav',):
        # Exportación en IBM SPSS Comprimido (.zsav)
        with tempfile.NamedTemporaryFile(suffix='.zsav', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            pyreadstat.write_sav(
                out_df,
                tmp_path,
                compress=True,
                column_labels=col_names_to_labels,
                variable_value_labels=col_value_labels
            )
            with open(tmp_path, 'rb') as f:
                zsav_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass
        filename = f"CardioUNEMI_Dataset_{fecha_str}.zsav"
        content_type = "application/x-spss-sav"
        return zsav_bytes, filename, content_type

    else:
        # Por defecto: IBM SPSS Statistics estándar (.sav)
        with tempfile.NamedTemporaryFile(suffix='.sav', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            pyreadstat.write_sav(
                out_df,
                tmp_path,
                column_labels=col_names_to_labels,
                variable_value_labels=col_value_labels
            )
            with open(tmp_path, 'rb') as f:
                sav_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except Exception: pass
        filename = f"CardioUNEMI_Dataset_{fecha_str}.sav"
        content_type = "application/x-spss-sav"
        return sav_bytes, filename, content_type
