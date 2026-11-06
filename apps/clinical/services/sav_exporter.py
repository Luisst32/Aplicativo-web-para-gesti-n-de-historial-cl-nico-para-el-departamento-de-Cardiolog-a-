"""
apps/clinical/services/sav_exporter.py
Servicio de exportación de base de datos a formato SPSS Statistics (.sav) y CSV / Excel.
Garantiza la exportación de las 342 columnas completas idénticas a
'Base_datos_Unemi_CardioUnemi-ACTUALIZADO.sav', conservando tipos, diccionarios
de variables, etiquetas de valor (value labels) y respuestas no modeladas.
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
from django.conf import settings

from clinical.models import Patient, Visit, VisitAnswer
from clinical.services.sav_importer import normalize_var_name

# Cache en memoria de la plantilla original de 342 columnas
_SAV_TEMPLATE_CACHE = None

def get_sav_template_metadata():
    """
    Carga e indexa en memoria las 342 columnas y metadatos oficiales de CardioUNEMI.
    Prioriza el archivo de especificación JSON empaquetado ('sav_columns_spec.json')
    para no depender de archivos .sav externos en servidores de producción o EC2.
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

        # Convertir llaves numéricas en value labels (JSON serializa int/float como str)
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
        # Fallback si existiera el archivo binario .sav local
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
            # Versión entera si aplica
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


def generate_export_dataset(patient_ids=None, format_type='sav'):
    """
    Genera el dataset de exportación con las 342 columnas completas.
    Parámetros:
      - patient_ids: lista de IDs de paciente (o None para todos los activos)
      - format_type: 'sav' para SPSS Statistics o 'csv' para Excel / CSV UTF-8 BOM
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
        'anthropometry', 'vital_signs', 'electrocardiogram', 'laboratory', 'echocardiogram'
    ).order_by('visit_id')

    if patient_ids and len(patient_ids) > 0 and 'all' not in patient_ids and 'todos' not in patient_ids:
        # Extraer IDs limpios
        clean_ids = []
        for pid in patient_ids:
            s_pid = str(pid).strip()
            if s_pid.startswith('p'):
                s_pid = s_pid[1:]
            if s_pid.isdigit():
                clean_ids.append(int(s_pid))
            else:
                # Probar por código de estudio
                clean_ids.append(s_pid)

        # Filtrar por patient_id o por study_code
        from django.db.models import Q
        int_ids = [x for x in clean_ids if isinstance(x, int)]
        str_ids = [str(x) for x in clean_ids]
        visits_qs = visits_qs.filter(
            Q(patient__patient_id__in=int_ids) |
            Q(study_code__in=str_ids) |
            Q(patient__id_card__in=str_ids)
        )

    visits = list(visits_qs)
    if not visits:
        # Fallback a todas las visitas si el filtro devolvió vacío
        visits = list(Visit.objects.all().select_related(
            'patient', 'patient__institution', 'patient__birth_canton', 'patient__birth_canton__province',
            'patient__sex', 'patient__ethnicity', 'residence_canton', 'residence_canton__province',
            'staff_category', 'professional_category', 'marital_status', 'living_situation',
            'education_level', 'work_schedule', 'housing_type', 'income_range',
            'anthropometry', 'vital_signs', 'electrocardiogram', 'laboratory', 'echocardiogram'
        ).order_by('visit_id'))

    # 2. Cargar todas las respuestas clínicas en bloque
    answers_by_visit = {}
    va_qs = VisitAnswer.objects.filter(visit__in=visits).select_related('question')
    for va in va_qs:
        v_id = va.visit_id
        if v_id not in answers_by_visit:
            answers_by_visit[v_id] = {}
        code = va.question.code
        val = va.numeric_value if va.numeric_value is not None else va.text_value
        answers_by_visit[v_id][code] = val

    # 3. Construir las 342 columnas para cada visita
    rows_data = []
    for v in visits:
        p = v.patient
        ans = answers_by_visit.get(v.visit_id, {})
        row = {}

        for col in cols:
            clean = normalize_var_name(col)[:30]
            val = ans.get(clean)

            # Mapeo de respaldo desde modelos relacionales de la BD
            if val is None or str(val).strip() == '':
                c_up = col.upper()
                if 'CODIGO' in c_up or 'CDIGO' in col:
                    val = v.study_code
                elif col == 'UNIVERSIDAD':
                    val = 2.0 if (p and p.institution and 'ESPOL' in p.institution.acronym.upper()) else 1.0
                elif col == 'FECHA':
                    val = v.visit_date
                elif 'AO' in c_up or 'AO' in col:
                    val = float(v.visit_date.year) if v.visit_date else 2026.0
                elif col == 'EDAD':
                    if p and p.age:
                        val = float(p.age)
                    elif v.visit_date and p and p.birth_date:
                        val = float(v.visit_date.year - p.birth_date.year)
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
                    elif 'FRACCION_ACORTAMIENTO' in c_up and echo.fractional_shortening_percentage: val = float(echo.fractional_shortening_percentage)

            # 4. Formatear y convertir al tipo de dato exacto de SPSS
            target_dtype = col_dtypes.get(col)
            if target_dtype and str(target_dtype).startswith('float'):
                if val is None or str(val).strip() == '' or str(val).lower() == 'nan':
                    row[col] = np.nan
                else:
                    # Mapear valor textual a código numérico si existe en etiquetas de valor (value labels)
                    col_inv = lbl_to_val_map.get(col, {})
                    val_str = str(val).strip().upper()
                    if val_str in col_inv:
                        row[col] = float(col_inv[val_str])
                    else:
                        norm_v = normalize_var_name(val_str).upper()
                        if norm_v in col_inv:
                            row[col] = float(col_inv[norm_v])
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
                # Columna de texto / string
                if val is None or str(val).lower() == 'nan':
                    row[col] = ''
                else:
                    row[col] = str(val).strip()

        rows_data.append(row)

    out_df = pd.DataFrame(rows_data, columns=cols)
    fecha_str = datetime.date.today().strftime('%Y%m%d')

    if format_type.lower() == 'csv':
        # Exportación en CSV / Excel UTF-8 BOM
        csv_bytes = out_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        filename = f"CardioUNEMI_Dataset_{fecha_str}.csv"
        content_type = "text/csv; charset=utf-8"
        return csv_bytes, filename, content_type

    else:
        # Exportación nativa en IBM SPSS Statistics (.sav)
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
