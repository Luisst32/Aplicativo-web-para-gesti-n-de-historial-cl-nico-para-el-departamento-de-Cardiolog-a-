from .yes_no import any_known
"""
apps/clinical/services/sav_exporter.py
Servicio de exportación de base de datos a formatos oficiales:
- IBM SPSS Statistics (.sav, .zsav)
- RStudio (.rds, .RData)
- Delimitado Excel / CSV (.csv UTF-8 con BOM)
Usa el esquema exacto de la matriz vacía de referencia UNEMI, conservando el
orden de columnas, tipos y metadatos SPSS disponibles.
"""

import os
import re
import tempfile
import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pyreadstat
import pyreadr
from catalog.institutions import (
    InstitutionResolutionError,
    filter_to_selectable_institutions,
    resolve_selectable_institution,
    selectable_institutions,
)
from clinical.services.record_selection import selected_visits
from clinical.models import Patient, Visit, VisitAnswer
from clinical.services.sav_importer import normalize_var_name
from .reference_matrix import load_unemi_reference_metadata

# Catálogo de variables identificativas y sensibles del paciente (condicionadas a Modo Protección de Datos)
SENSITIVE_EXPORT_COLUMNS = [
    ('CEDULA', 'Identificación / Cédula del Paciente', 'object', {}),
    ('NOMBRES', 'Nombres del Paciente', 'object', {}),
    ('APELLIDOS', 'Apellidos del Paciente', 'object', {}),
    ('TELEFONO', 'Teléfono de Contacto', 'object', {}),
    ('EMAIL', 'Correo Electrónico', 'object', {}),
]

# Cache en memoria de la plantilla de columnas y metadatos
_SAV_TEMPLATE_CACHE = None


_NUMERIC_DISPLAY_FORMAT_RE = re.compile(r'^(F|N|E)(\d+)(?:\.(\d+))?$')


def _adaptive_numeric_formats(frame, source_formats=None):
    """Choose an SPSS numeric display format from the values in each column.

    SPSS applies one display format to an entire variable. Therefore an
    integer-only column must use zero decimal places (``F8.0``), while a
    column containing fractional values keeps enough decimal places to show
    those values (for example ``F8.2`` for ``2.43``). This changes only the
    presentation metadata; the dataframe values remain numeric.
    """
    formats = dict(source_formats or {})

    for column in frame.columns:
        series = frame[column]
        if not pd.api.types.is_numeric_dtype(series):
            continue

        current = str(formats.get(column) or '').strip().upper()
        match = _NUMERIC_DISPLAY_FORMAT_RE.match(current)
        if match:
            kind, width_text, source_decimals = match.groups()
            width = int(width_text)
            source_decimals = int(source_decimals or 0)
        else:
            kind = 'F'
            width = 8
            source_decimals = 0

        numeric = pd.to_numeric(series, errors='coerce')
        numeric = numeric[np.isfinite(numeric)]
        if numeric.empty:
            decimals = 0
        else:
            values = numeric.astype(float).tolist()
            has_fraction = any(not np.isclose(value, round(value), atol=1e-12) for value in values)
            if not has_fraction:
                decimals = 0
            else:
                decimals = 0
                for value in values:
                    if np.isclose(value, round(value), atol=1e-12):
                        continue
                    try:
                        decimal_value = Decimal(str(value)).normalize()
                        decimals = max(decimals, max(0, -decimal_value.as_tuple().exponent))
                    except (ArithmeticError, ValueError):
                        decimals = max(decimals, source_decimals, 2)
                decimals = min(max(decimals, 1), 6)

        formats[column] = f'{kind}{width}.{decimals}'

    return formats


def get_sav_template_metadata():
    """Load UNEMI's exact column contract from the empty reference SAV."""
    global _SAV_TEMPLATE_CACHE
    if _SAV_TEMPLATE_CACHE is not None:
        return _SAV_TEMPLATE_CACHE

    meta = load_unemi_reference_metadata()
    cols = list(meta.column_names)
    col_dtypes = {}
    for col in cols:
        readstat_type = meta.readstat_variable_types.get(col)
        original_format = str((meta.original_variable_types or {}).get(col, '')).upper()
        if readstat_type == 'string':
            col_dtypes[col] = 'object'
        elif original_format.startswith(('DATE', 'ADATE', 'EDATE', 'SDATE', 'DATETIME', 'TIME')):
            col_dtypes[col] = 'datetime64[ns]'
        else:
            col_dtypes[col] = 'float64'

    col_value_labels = {
        col: dict(labels or {})
        for col, labels in (meta.variable_value_labels or {}).items()
    }
    col_names_to_labels = dict(meta.column_names_to_labels or {})

    lbl_to_val_map = {}
    for col, value_labels in col_value_labels.items():
        inverse = {}
        for numeric_value, label in value_labels.items():
            normalized_label = str(label).strip().upper()
            inverse[normalized_label] = numeric_value
            normalized_name = normalize_var_name(label)
            if normalized_name:
                inverse[normalized_name.upper()] = numeric_value
            if isinstance(numeric_value, (int, float)) and numeric_value == int(numeric_value):
                inverse[str(int(numeric_value))] = numeric_value
            inverse[str(numeric_value)] = numeric_value
        lbl_to_val_map[col] = inverse

    _SAV_TEMPLATE_CACHE = {
        'columns': cols,
        'dtypes': col_dtypes,
        'value_labels': col_value_labels,
        'labels': col_names_to_labels,
        'lbl_to_val_map': lbl_to_val_map,
        'original_variable_types': dict(meta.original_variable_types or {}),
        'variable_display_width': dict(meta.variable_display_width or {}),
        'variable_measure': dict(meta.variable_measure or {}),
        'missing_ranges': dict(meta.missing_ranges or {}),
        'file_label': meta.file_label,
    }
    return _SAV_TEMPLATE_CACHE

def _institution_export_codes(value_labels):
    """Match admin-enabled institutions to existing SPSS labels, then allocate new codes."""
    updated_labels = dict(value_labels or {})
    university_labels = dict(updated_labels.get('UNIVERSIDAD', {}) or {})
    code_by_institution = {}
    used_codes = set()
    enabled_institutions = list(selectable_institutions())

    for raw_code, label in university_labels.items():
        try:
            number = float(raw_code)
            code = int(number) if number.is_integer() else number
            used_codes.add(code)
        except (TypeError, ValueError):
            continue
        try:
            institution = resolve_selectable_institution(
                label=label,
                institutions=enabled_institutions,
            )
        except InstitutionResolutionError:
            continue
        code_by_institution.setdefault(institution.pk, code)

    next_code = max((code for code in used_codes if isinstance(code, (int, float))), default=0) + 1
    for institution in enabled_institutions:
        if institution.pk in code_by_institution:
            continue
        while next_code in used_codes:
            next_code += 1
        code_by_institution[institution.pk] = next_code
        university_labels[next_code] = institution.acronym
        used_codes.add(next_code)
        next_code += 1

    if 'UNIVERSIDAD' in updated_labels or code_by_institution:
        updated_labels['UNIVERSIDAD'] = university_labels
    return code_by_institution, updated_labels


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


def _restore_value_label_keys(raw_labels):
    """JSON stores dictionary keys as strings; SPSS labels need numeric keys."""
    restored = {}
    for col, labels in (raw_labels or {}).items():
        restored[col] = {}
        for key, label in (labels or {}).items():
            try:
                numeric_key = float(key)
                if numeric_key.is_integer():
                    numeric_key = int(numeric_key)
                restored[col][numeric_key] = label
            except (TypeError, ValueError):
                restored[col][key] = label
    return restored


def _source_snapshot_frame(visits, include_unlinked=False):
    """Return original rows when one lossless source matrix is available.

    A mixed selection (imported rows plus records created in the application,
    or more than one imported matrix) cannot be a byte-for-byte round trip.
    Returning ``None`` lets the caller build the official combined dataset
    instead of failing the whole export.
    """
    raw_count = sum(1 for visit in visits if visit.source_dataset_id and visit.source_row_data is not None)
    if raw_count == 0:
        return None
    if raw_count != len(visits):
        return None

    dataset_ids = {visit.source_dataset_id for visit in visits}
    if len(dataset_ids) != 1:
        return None

    dataset = visits[0].source_dataset
    columns = list(dataset.column_names or [])
    source_rows = list(dataset.rows.all())
    if include_unlinked:
        rows = [source_row.row_data or {} for source_row in source_rows]
    else:
        selected_visit_ids = {visit.visit_id for visit in visits}
        rows = [source_row.row_data or {} for source_row in source_rows if source_row.visit_id in selected_visit_ids]
        if not rows:
            ordered_visits = sorted(visits, key=lambda visit: (visit.source_row_index is None, visit.source_row_index or 0, visit.visit_id))
            rows = [visit.source_row_data or {} for visit in ordered_visits]
    original_types = dataset.original_variable_types or {}

    converted = {}
    for col in columns:
        fmt = str(original_types.get(col, '') or '').upper()
        values = [row.get(col) for row in rows]
        if fmt.startswith('A'):
            converted[col] = ['' if value is None else str(value) for value in values]
        elif fmt.startswith(('DATETIME',)):
            normalized = []
            for value in values:
                if value is None or str(value).strip() == '':
                    normalized.append(None)
                    continue
                try:
                    normalized.append(datetime.datetime.fromisoformat(str(value)))
                except (TypeError, ValueError):
                    normalized.append(None)
            converted[col] = normalized
        elif fmt.startswith(('DATE', 'ADATE', 'EDATE', 'SDATE')):
            normalized = []
            for value in values:
                if value is None or str(value).strip() == '':
                    normalized.append(None)
                    continue
                try:
                    normalized.append(datetime.date.fromisoformat(str(value)[:10]))
                except (TypeError, ValueError):
                    normalized.append(None)
            converted[col] = normalized
        elif fmt.startswith(('TIME',)):
            normalized = []
            for value in values:
                if value is None or str(value).strip() == '':
                    normalized.append(None)
                    continue
                try:
                    normalized.append(datetime.time.fromisoformat(str(value)))
                except (TypeError, ValueError):
                    normalized.append(None)
            converted[col] = normalized
        elif fmt:
            normalized = []
            for value in values:
                if value is None or str(value).strip() == '':
                    normalized.append(np.nan)
                    continue
                try:
                    normalized.append(float(value))
                except (TypeError, ValueError):
                    normalized.append(np.nan)
            converted[col] = normalized
        else:
            converted[col] = values

    return pd.DataFrame(converted, columns=columns), dataset


def _write_export_frame(out_df, format_type, metadata=None):
    """Write a dataframe while retaining source SPSS metadata when available."""
    fecha_str = datetime.date.today().strftime('%Y%m%d')
    fmt = (format_type or 'sav').strip().lower()
    metadata = metadata or {}
    output_columns = set(out_df.columns)
    labels = {
        column: label
        for column, label in (metadata.get('column_labels') or {}).items()
        if column in output_columns
    }
    value_labels = _restore_value_label_keys({
        column: labels_for_values
        for column, labels_for_values in (metadata.get('value_labels') or {}).items()
        if column in output_columns
    })
    original_types = {
        column: variable_type
        for column, variable_type in (metadata.get('original_variable_types') or {}).items()
        if column in output_columns
    }
    numeric_formats = _adaptive_numeric_formats(out_df, original_types)
    display_width = {
        column: width
        for column, width in (metadata.get('variable_display_width') or {}).items()
        if column in output_columns
    }
    measures = {
        column: measure
        for column, measure in (metadata.get('variable_measure') or {}).items()
        if column in output_columns
    }
    missing_ranges = {
        column: ranges
        for column, ranges in (metadata.get('missing_ranges') or {}).items()
        if column in output_columns
    }
    file_label = metadata.get('file_label') or ''

    if fmt == 'csv':
        return out_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'), f'CardioUNEMI_Dataset_{fecha_str}.csv', 'text/csv; charset=utf-8'
    if fmt == 'rds':
        suffix = '.rds'
        content_type = 'application/octet-stream'
        writer = lambda path: pyreadr.write_rds(path, out_df)
    elif fmt in ('rdata', 'rda', 'r'):
        suffix = '.RData'
        content_type = 'application/octet-stream'
        writer = lambda path: pyreadr.write_rdata(path, out_df, df_name='CardioUnemi')
    else:
        suffix = '.zsav' if fmt == 'zsav' else '.sav'
        content_type = 'application/x-spss-sav'
        sav_frame = out_df.copy()
        for column, variable_type in original_types.items():
            string_format = re.match(r'^A(\d+)$', str(variable_type).strip().upper())
            if not string_format or column not in sav_frame.columns:
                continue
            width = int(string_format.group(1))

            def pad_string(value):
                if value is None or (not isinstance(value, str) and pd.isna(value)):
                    value = ''
                value = str(value)
                return value if len(value) >= width else value.ljust(width)

            sav_frame[column] = sav_frame[column].map(pad_string)

        def writer(path):
            pyreadstat.write_sav(
                sav_frame,
                path,
                file_label=file_label,
                compress=(fmt == 'zsav'),
                column_labels=labels,
                variable_value_labels=value_labels,
                missing_ranges=missing_ranges,
                variable_display_width=display_width,
                variable_measure=measures,
                variable_format=numeric_formats,
            )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    try:
        writer(tmp_path)
        with open(tmp_path, 'rb') as output:
            payload = output.read()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return payload, f'CardioUNEMI_Dataset_{fecha_str}{suffix}', content_type


def generate_export_dataset(patient_ids=None, format_type='sav', privacy_mode=False, institution_id=None):
    """
    Genera el dataset con el esquema y orden de la matriz de referencia UNEMI.
    Soporta los mismos formatos de exportación que se admiten en importación:
      - 'sav': IBM SPSS Statistics (.sav)
      - 'zsav': IBM SPSS Comprimido (.zsav)
      - 'rds': RStudio Dataframe serializado (.rds)
      - 'rdata' / 'rda': RStudio Workspace (.RData)
      - 'csv': Archivo delimitado por comas (.csv UTF-8 BOM)

    Control de Privacidad (Modo Protección de Datos):
      - Si privacy_mode=False: exporta el 100% de los datos incluyendo todas las variables sensibles
        (CEDULA, NOMBRES, APELLIDOS, TELEFONO, EMAIL).
      - Si privacy_mode=True: omite/excluye estrictamente todas las columnas sensibles e identificativas.
    Retorna: (file_bytes, filename, content_type)
    """
    tpl = get_sav_template_metadata()
    cols = list(tpl['columns'])
    col_dtypes = dict(tpl['dtypes'])
    col_value_labels = dict(tpl['value_labels'])
    col_names_to_labels = dict(tpl['labels'])
    lbl_to_val_map = tpl['lbl_to_val_map']

    reference_columns = set(tpl['columns'])
    if not privacy_mode and reference_columns.intersection({'C.I', 'NOMBRES', 'APELLIDO1', 'APELLIDO2'}):
        # La matriz oficial ya contiene sus columnas identificativas y su
        # posición exacta. No insertar CEDULA/NOMBRES artificiales.
        pass
    elif not privacy_mode:
        # Se exportan todos los datos sensibles identificativos
        # Ubicar la columna CÓDIGO para insertar los datos sensibles de forma contigua
        codigo_idx = -1
        for idx, c in enumerate(cols):
            if normalize_var_name(c).upper() == 'CODIGO':
                codigo_idx = idx
                break
        insert_pos = (codigo_idx + 1) if codigo_idx >= 0 else 0

        for i, (scol, slbl, sdt, svals) in enumerate(SENSITIVE_EXPORT_COLUMNS):
            if scol not in cols:
                cols.insert(insert_pos + i, scol)
            col_dtypes[scol] = sdt
            col_names_to_labels[scol] = slbl
            if svals:
                col_value_labels[scol] = svals
    else:
        # Modo Protección de Datos ACTIVO: suprimir cualquier columna sensible
        sensitive_col_names = {scol for scol, _, _, _ in SENSITIVE_EXPORT_COLUMNS}
        sensitive_col_names.update({'NOMBRES', 'APELLIDO1', 'APELLIDO2', 'C.I', 'TEL\u00c9FONO', 'CORREO'})
        cols = [c for c in cols if c not in sensitive_col_names]

    # 1. Obtener visitas filtradas
    visits_qs = Visit.objects.filter(patient__status=Patient.Status.ACTIVE).select_related(
        'patient', 'patient__institution', 'patient__birth_canton', 'patient__birth_canton__province',
        'patient__sex', 'patient__ethnicity', 'residence_canton', 'residence_canton__province',
        'staff_category', 'professional_category', 'marital_status', 'living_situation',
        'education_level', 'work_schedule', 'housing_type', 'income_range',
        'anthropometry', 'vital_signs', 'electrocardiogram', 'laboratory', 'echocardiogram',
        'ordered_studies', 'source_dataset'
    ).order_by('visit_id')

    visits_qs = filter_to_selectable_institutions(visits_qs, 'patient__institution')

    if institution_id not in (None, '', 'all'):
        try:
            institution_id = int(institution_id)
        except (TypeError, ValueError):
            raise ValueError('La institución seleccionada no es válida.')

    if institution_id not in (None, '', 'all'):
        if not selectable_institutions().filter(pk=institution_id).exists():
            raise ValueError('La instituciÃ³n seleccionada no está habilitada.')
        visits_qs = visits_qs.filter(patient__institution_id=institution_id)

    if patient_ids is not None:
        visits = selected_visits(patient_ids, active_only=True)
        visits_qs = visits_qs.filter(pk__in=[visit.pk for visit in visits])
    visits = list(visits_qs)

    # Una importación SPSS conserva la fila y el esquema originales. Cuando la
    # selección pertenece a una sola matriz, devolver ese snapshot garantiza la
    # prueba: importar -> exportar conserva columnas, orden, valores y etiquetas.
    if not privacy_mode:
        source_frame = _source_snapshot_frame(visits, include_unlinked=(patient_ids is None))
        if source_frame is not None:
            raw_frame, source_metadata = source_frame
            return _write_export_frame(raw_frame, format_type, {
                'column_labels': source_metadata.column_labels,
                'value_labels': source_metadata.value_labels,
                'original_variable_types': source_metadata.original_variable_types,
                'variable_display_width': source_metadata.variable_display_width,
                'variable_measure': source_metadata.variable_measure,
                'missing_ranges': source_metadata.missing_ranges,
                'file_label': source_metadata.file_label,
            })

    # 2. Cargar todas las respuestas clínicas en bloque
    institution_export_codes, col_value_labels = _institution_export_codes(col_value_labels)
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
            val = _first_recorded(ans, col, col.lower(), clean, clean.lower())
            explicitly_empty = any(key in ans for key in (col, col.lower(), clean, clean.lower())) and val is None

            # Asignación directa prioritaria para variables sensibles identificativas del paciente
            if col in {'CEDULA', 'C.I'}:
                val = (p.id_card if p and p.id_card else '') or val
            elif col == 'NOMBRES':
                val = (p.first_names if p and p.first_names else '') or val
            elif col in {'APELLIDOS', 'APELLIDO1'}:
                val = (p.last_name1 if p and p.last_name1 else '') or val
            elif col == 'APELLIDO2':
                val = (p.last_name2 if p and p.last_name2 else '') or val
            elif col in {'TELEFONO', 'TEL\u00c9FONO'}:
                val = (p.phone if p and p.phone else '') or val
            elif col in {'EMAIL', 'CORREO'}:
                val = (p.email if p and p.email else '') or val
            elif col == 'UNIVERSIDAD':
                val = institution_export_codes.get(p.institution_id, np.nan) if p and p.institution_id else np.nan

            # Mapeo de respaldo desde modelos relacionales de la BD y nuevos campos 2026
            elif not explicitly_empty and (val is None or str(val).strip() == ''):
                c_up = col.upper()
                if clean.upper() in {'CODIGO', 'CODIGONUEV'}:
                    val = v.study_code
                elif col == 'FECHA':
                    val = v.visit_date
                elif col in {'AÑO', 'ANO'}:
                    val = float(v.visit_date.year) if v.visit_date else 2026.0
                elif col == 'VISITA':
                    val = v.visit_number
                elif col == 'FACULTAD':
                    val = v.faculty
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
                    val = 2.0 if (p and p.sex and 'MUJER' in p.sex.name.upper()) else (1.0 if (p and p.sex and 'HOMBRE' in p.sex.name.upper()) else np.nan)
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
                elif col == 'CUANTOS_HIJOS__TIENE':
                    val = float(v.num_children) if v.num_children is not None else np.nan
                elif col == 'CON_QUIEN_VIVE':
                    val = v.living_situation.name if v.living_situation else None
                elif col == 'CUANTAS_PERSONAS_CONVIVE_CON_USTES_EN_EL_HOGAR':
                    val = float(v.num_cohabitants) if v.num_cohabitants is not None else np.nan
                elif col == 'NIVEL_ESTUDIOS_OBTENIDO':
                    val = v.education_level.name if v.education_level else None
                elif col == 'HORARIO_DE_TRABAJO':
                    val = v.work_schedule.name if v.work_schedule else None
                elif col == 'CATEGORIA_PROFESIONAL':
                    val = v.professional_category.name if v.professional_category else None
                elif col == 'SU_VIVIENDA_ES':
                    val = v.housing_type.name if v.housing_type else None
                elif col in {'INGRESOS_TOTALES', 'INGRESOS_TOTALES_MENSUALES'}:
                    val = v.income_range.name if v.income_range else None

                # Antropometría
                elif col == 'PESO_KG' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.weight_kg:
                    val = float(v.anthropometry.weight_kg)
                elif col == 'TALLA_CM' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.height_cm:
                    val = float(v.anthropometry.height_cm)
                elif col == 'IMC_KGM2' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.bmi:
                    val = float(v.anthropometry.bmi)
                elif col in {'PERÍMETRO_ABDOMINAL_CM', 'PER�METRO_ABDOMINAL_CM'} and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.waist_circumference_cm:
                    val = float(v.anthropometry.waist_circumference_cm)
                elif col == 'ASC_M2' and hasattr(v, 'anthropometry') and v.anthropometry and v.anthropometry.body_surface_area:
                    val = float(v.anthropometry.body_surface_area)

                # Signos Vitales
                elif col == 'TAS_TS' and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.systolic_bp:
                    val = float(v.vital_signs.systolic_bp)
                elif col in {'TAS_MMHG', 'TAD_MMHG'} and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.diastolic_bp:
                    val = float(v.vital_signs.diastolic_bp)
                elif col in {'SATURACIÓN_O2', 'SATURACI�N_O2'} and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.oxygen_saturation:
                    val = float(v.vital_signs.oxygen_saturation)
                elif col == 'FRECUENCIA_CARDIACA_IPM' and hasattr(v, 'vital_signs') and v.vital_signs and v.vital_signs.heart_rate:
                    val = float(v.vital_signs.heart_rate)
                elif col == 'SOPLOS_CARDIACOS' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = _export_bool(any_known(v.vital_signs.systolic_murmur, v.vital_signs.diastolic_murmur))
                elif col == 'PULSOSPEDIOS' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = _export_bool(v.vital_signs.pedal_pulses_symmetric)
                elif col == 'EXPLORACION_RESPIRATORIA' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = _export_bool(v.vital_signs.pulmonary_auscultation_normal)
                elif col == 'EXPLORACION_ABDOMINAL' and hasattr(v, 'vital_signs') and v.vital_signs:
                    val = _export_bool(v.vital_signs.abdominal_auscultation_normal)

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
                    lab_map = {
                        'GLUCOSA_SANGRE': lab.glucose_mg_dl,
                        'UREA_FUNCION_RENAL': lab.urea_mg_dl,
                        'CREATINA_FUNCION_RENAL': lab.creatinine_mg_dl,
                        'COLESTEROL_TOTAL_RIESGO_CARDIOVASCULAR': lab.total_cholesterol_mg_dl,
                        'HDL_RIESGO_CARDIOVASCULAR': lab.hdl_mg_dl,
                        'LDL_RIESGO_CARDIOVASCULAR': lab.ldl_mg_dl,
                        'TRIGLICERIDOS_RIESGO_CARDIOVASCULAR': lab.triglycerides_mg_dl,
                        'HEMATIES': lab.rbc_millions,
                        'HEMOGLOBINA': lab.hemoglobin_g_dl,
                        'HEMATOCRITO': lab.hematocrit_percentage,
                        'LEUCOCITOS': lab.wbc_thousands,
                        'PLAQUETAS': lab.platelets_thousands,
                        'GOT_AST_FUNCION_HEPATICA': lab.ast_got_u_l,
                        'GPT_ALT_FUNCION_HEPATICA': lab.alt_gpt_u_l,
                        'GGT_FUNCION_HEPATICA': lab.ggt_u_l,
                        'TSH_FUNCION_TIROIDEA': lab.tsh_u_iu_ml,
                    }
                    if col in lab_map and lab_map[col] is not None:
                        val = float(lab_map[col])

                # Ecocardiograma
                elif hasattr(v, 'echocardiogram') and v.echocardiogram:
                    echo = v.echocardiogram
                    if col == 'FRACCION_EYECCION_TEICHOLZ' and echo.lvef_percentage is not None:
                        val = float(echo.lvef_percentage)

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
                    val = _export_bool(ans.get('hc_isquemica') or ans.get('cardiopatia_isquemica'))
                elif col == 'HC_ISQUEMICA_ANGINA':
                    val = _export_bool(ans.get('hc_isquemica_angina'))
                elif col == 'HC_ISQUEMICA_INFARTO':
                    val = _export_bool(ans.get('hc_isquemica_infarto'))
                elif col == 'HC_REVASC':
                    val = _export_bool(ans.get('hc_revasc') or ans.get('revascularizacion_coronaria'))
                elif col == 'REVASCULARIZACION_TIPO':
                    raw_rev = str(ans.get('revascularizacion_tipo') or ans.get('hc_revasc_tipo') or '').lower()
                    if 'ambas' in raw_rev or '3' in raw_rev: val = 3.0
                    elif 'bypass' in raw_rev or '2' in raw_rev: val = 2.0
                    elif 'angioplastia' in raw_rev or '1' in raw_rev: val = 1.0
                    else: val = np.nan
                elif col == 'HC_INSUF_CARDIACA':
                    val = _export_bool(ans.get('hc_insuf_cardiaca') or ans.get('insuficiencia_cardiaca'))
                elif col == 'HC_VALVULOPATIA':
                    val = _export_bool(ans.get('hc_valvulopatia') or ans.get('valvulopatia'))
                elif col == 'HC_VALVULOPATIA_CUALES':
                    val = ans.get('hc_valvulopatia_cuales') or ans.get('valvulopatia_cuales') or ''
                elif col == 'HC_VALVULOPATIA_OPERADO':
                    val = _export_bool(ans.get('hc_valvulopatia_operado') or ans.get('valvulopatia_operado'))
                elif col == 'HC_HOSPITALIZACION':
                    val = _export_bool(ans.get('hc_ingresado') or ans.get('hc_hospitalizacion') or ans.get('ingreso_hospitalario_problema_cardiaco'))
                elif col == 'HC_HOSPITALIZACION_MOTIVO':
                    val = ans.get('hc_ingresado_cual') or ans.get('hc_hospitalizacion_motivo') or ''

                # Nuevos campos Cuestionario UNEMI 2026: Cáncer
                elif col == 'NC_CANCER':
                    val = _export_bool(ans.get('nc_cancer') or ans.get('historia_cancer'))
                elif col == 'CANCER_PULMON':
                    val = _export_bool(ans.get('cancer_pulmon'))
                elif col == 'CANCER_PROSTATA':
                    val = _export_bool(ans.get('cancer_prostata'))
                elif col == 'CANCER_COLON':
                    val = _export_bool(ans.get('cancer_colon'))
                elif col == 'CANCER_MAMA':
                    val = _export_bool(ans.get('cancer_mama'))
                elif col == 'CANCER_VEJIGA':
                    val = _export_bool(ans.get('cancer_vejiga'))
                elif col == 'CANCER_UTERO':
                    val = _export_bool(ans.get('cancer_utero'))
                elif col == 'CANCER_OVARIO':
                    val = _export_bool(ans.get('cancer_ovario'))
                elif col == 'CANCER_OTRO':
                    val = _export_bool(ans.get('cancer_otro'))
                elif col == 'CANCER_OTRO_DETALLE':
                    val = ans.get('cancer_otro_detalle', '')
                elif col == 'CANCER_QT':
                    val = _export_bool(ans.get('cancer_qt') or ans.get('cancer_quimioterapia'))
                elif col == 'CANCER_RT':
                    val = _export_bool(ans.get('cancer_rt') or ans.get('cancer_radioterapia'))

                # Nuevos campos Cuestionario UNEMI 2026: Estudios Prescritos
                elif col == 'EST_ANALISIS_CLINICOS':
                    val = _export_bool(ans['est_analisis_clinicos'] if 'est_analisis_clinicos' in ans else getattr(studies, 'clinical_analysis', None))
                elif col == 'EST_ERGOMETRIA_SPECT':
                    val = _export_bool(ans['est_ergometria_spect'] if 'est_ergometria_spect' in ans else getattr(studies, 'ergometry_spect', None))
                elif col == 'EST_TAC_CARDIACO':
                    val = _export_bool(ans['est_tac_cardiaco'] if 'est_tac_cardiaco' in ans else getattr(studies, 'cardiac_ct', None))
                elif col == 'EST_RNM_CARDIACO':
                    val = _export_bool(ans['est_rnm_cardiaco'] if 'est_rnm_cardiaco' in ans else getattr(studies, 'cardiac_mri', None))
                elif col == 'EST_ELECTROFISIOLOGIA':
                    val = _export_bool(ans['est_electrofisiologia'] if 'est_electrofisiologia' in ans else getattr(studies, 'electrophysiology', None))
                elif col == 'EST_ECOCARDIOGRAMA':
                    val = _export_bool(ans.get('est_ecocardiograma') or ans.get('est_eco'))
                elif col == 'EST_HOLTER':
                    val = _export_bool(ans.get('est_holter'))
                elif col == 'EST_MAPA':
                    val = _export_bool(ans.get('est_mapa'))
                elif col == 'ESTUDIOS_OBSERVACIONES':
                    val = ans.get('est_otros_detalle') or ans.get('estudios_observaciones') or ''

                # Nuevos campos Cuestionario UNEMI 2026: PREDIMED Lácteos y Sofrito
                elif col == 'PRED_Q13_CONSUME':
                    val = _export_bool(ans.get('pred_q13_consume'))
                elif col == 'PRED_LECHE_VASOS_DIA':
                    val = _to_float(ans.get('pred_leche_vasos_dia'))
                elif col == 'PRED_LECHE_VASOS_SEM':
                    val = _to_float(ans.get('pred_leche_vasos_sem'))
                elif col == 'PRED_LECHE_TIPO':
                    val = ans.get('pred_leche_tipo', '')
                elif col == 'PRED_Q14_CONSUME':
                    val = _export_bool(ans.get('pred_q14_consume'))
                elif col == 'PRED_QUESO_VECES_SEM':
                    val = _to_float(ans.get('pred_queso_veces_sem'))
                elif col == 'PRED_QUESO_GRAMOS':
                    val = _to_float(ans.get('pred_queso_gramos'))
                elif col == 'PRED_Q15_CONSUME':
                    val = _export_bool(ans.get('pred_q15_consume'))
                elif col == 'PRED_YOGURT_CANT_SEM':
                    val = _to_float(ans.get('pred_yogurt_cant_sem'))
                elif col == 'PRED_YOGURT_TIPO':
                    val = ans.get('pred_yogurt_tipo', '')
                elif col == 'PRED_Q19':
                    val = _export_bool(ans.get('pred_q19'))

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
    return _write_export_frame(out_df, format_type, {
        'column_labels': col_names_to_labels,
        'value_labels': col_value_labels,
        'original_variable_types': tpl.get('original_variable_types') or {},
        'variable_display_width': tpl.get('variable_display_width') or {},
        'variable_measure': tpl.get('variable_measure') or {},
        'missing_ranges': tpl.get('missing_ranges') or {},
        'file_label': tpl.get('file_label') or '',
    })


def _first_recorded(values, *keys):
    for key in keys:
        if key in values:
            return values[key]
    return None


def _export_bool(value):
    if value is None or str(value).strip() == '':
        return np.nan
    return 1.0 if _is_yes(value) else 0.0
