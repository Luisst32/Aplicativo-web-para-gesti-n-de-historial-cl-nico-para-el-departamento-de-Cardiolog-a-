# -*- coding: utf-8 -*-
"""
analyzer.py
Análisis inteligente, validación de estructura, detección de discrepancias,
duplicados y previsualización de archivos clínicos previo a su persistencia.
"""

import sys
from pathlib import Path

from security.access import require_clinical_access
from clinical.services.import_tickets import store_upload, InvalidImportTicket, ERROR_MESSAGE

from catalog.models import Institution
from clinical.models import Patient, Visit

from .constants import (
    COLUMN_TYPO_RULES,
    SPSS_QUESTION_ALIASES,
    STANDARD_FIELD_ALIASES,
    FIELD_DESTINATIONS,
    CIUDAD_CODE_MAP,
)
from .normalizers import (
    normalize_var_name,
    classify_spss_question_section,
    _match_column_to_field,
    get_column_destination,
    detect_column_typos,
    _resolve_canton_safe,
    _is_empty_or_nan,
    _get_val_and_label,
)
from .readers import _read_dataset_file, DatasetMetadata


def analyze_sav_file(file_obj, filename="archivo.sav", user=None):
    require_clinical_access(user, 'import')
    try:
        temp_token, temp_path = store_upload(file_obj, filename, user)
    except InvalidImportTicket:
        return {'success': False, 'error': ERROR_MESSAGE}
    try:
        import sys
        sav_mod = sys.modules.get('clinical.services.sav_importer') or sys.modules.get('apps.clinical.services.sav_importer')
        analyze_fn = getattr(sav_mod, '_analyze_staged_dataset', _analyze_staged_dataset) if sav_mod else _analyze_staged_dataset
        result = analyze_fn(temp_path, filename, temp_token)
        if not result.get('success'):
            temp_path.unlink(missing_ok=True)
        return result
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _analyze_staged_dataset(temp_path, filename, temp_token=None, reader_fn=None):
    """
    Lee e inspecciona inteligentemente un archivo SPSS .sav o RStudio (.rds/.RData).
    Retorna un informe de diagnóstico para que el usuario confirme antes de guardar.
    """
    if reader_fn is None:
        import sys
        sav_mod = sys.modules.get('clinical.services.sav_importer') or sys.modules.get('apps.clinical.services.sav_importer')
        if sav_mod and hasattr(sav_mod, '_read_dataset_file'):
            reader_fn = sav_mod._read_dataset_file
        else:
            reader_fn = _read_dataset_file
    try:
        df_dict, meta = reader_fn(temp_path, filename)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        return {
            "success": False,
            "error": f"No se pudo leer el archivo de datos: {str(e)}"
        }

    total_rows = meta.number_rows
    total_cols = meta.number_columns
    col_names = list(df_dict.keys())

    # Mapeo de columnas
    field_to_col = {}
    col_to_field = {}
    for col in col_names:
        matched_field = _match_column_to_field(col)
        if matched_field and matched_field not in field_to_col:
            field_to_col[matched_field] = col
            col_to_field[col] = matched_field

    # Diagnóstico de estructura y columnas
    warnings = []
    missing_fields = []

    # 1. Identificadores
    has_names = 'nombres' in field_to_col or 'apellido1' in field_to_col
    has_id_card = 'cedula' in field_to_col
    has_codigo = 'codigo' in field_to_col

    # 2. Comprobación y Mapeo de Columnas (identifica correcciones ortográficas y destino en BD)
    grammatical_errors = detect_column_typos(col_names)

    # Listado estructurado de qué datos van en dónde
    column_mappings = []
    typo_map = {t['original']: t for t in grammatical_errors}
    for col in col_names:
        mod_name, fld_name = get_column_destination(col)
        has_typo = col in typo_map
        column_mappings.append({
            "spss_column": col,
            "corrected_name": typo_map[col]['corrected'] if has_typo else col,
            "has_correction": has_typo,
            "correction_detail": typo_map[col]['explanation'] if has_typo else "",
            "destination_module": mod_name,
            "destination_field": fld_name,
            "destination_label": f"{mod_name} → {fld_name}",
            "status": "Corregido y Mapeado" if has_typo else "Mapeado"
        })

    # 5. Detección de Duplicados Internos en el Archivo y con la Base de Datos
    inst_unemi = Institution.objects.filter(acronym__iexact='UNEMI').first() or Institution.objects.first()
    inst_espol = Institution.objects.filter(acronym__iexact='ESPOL').first() or inst_unemi

    db_visits = Visit.objects.select_related('patient', 'patient__institution').all()
    db_visits_map = {
        (v.patient.institution_id, str(v.study_code)): (v.patient.full_name if v.patient else f"Código {v.study_code}")
        for v in db_visits if v.study_code and v.patient and v.patient.institution_id
    }
    db_patients_map = {
        p.id_card: p.full_name
        for p in Patient.objects.all() if p.id_card
    }

    internal_duplicates = []
    codes_seen_in_file = {}
    db_duplicates = []
    new_patients_count = 0

    for idx_row in range(total_rows):
        row_inst = inst_unemi
        if 'universidad' in field_to_col:
            u_val = df_dict[field_to_col['universidad']][idx_row]
            _, u_lbl = _get_val_and_label(u_val, meta.variable_value_labels.get(field_to_col['universidad'], {}))
            if 'ESPOL' in u_lbl.upper() or u_val == 2.0:
                row_inst = inst_espol

        c_str = None
        if has_codigo:
            raw_c = df_dict[field_to_col['codigo']][idx_row]
            if raw_c is not None:
                c_str = str(int(float(raw_c))) if isinstance(raw_c, (int, float)) else str(raw_c).strip()
        if not c_str:
            c_str = str(idx_row + 1)

        id_c = None
        if has_id_card:
            raw_id = df_dict[field_to_col['cedula']][idx_row]
            if raw_id is not None and str(raw_id).strip():
                id_c = str(raw_id).strip()

        # Duplicados internos dentro del mismo archivo
        file_key = (row_inst.institution_id if row_inst else 1, c_str)
        if file_key in codes_seen_in_file:
            internal_duplicates.append({
                "code": c_str,
                "institution": row_inst.acronym if row_inst else "UNEMI",
                "rows": [codes_seen_in_file[file_key] + 1, idx_row + 1]
            })
        else:
            codes_seen_in_file[file_key] = idx_row

        # Duplicados con la base de datos
        dup_found = False
        dup_name = ""
        if file_key in db_visits_map:
            dup_found = True
            dup_name = db_visits_map[file_key]
        elif id_c and id_c in db_patients_map:
            dup_found = True
            dup_name = db_patients_map[id_c]

        if dup_found:
            db_duplicates.append({
                "row": idx_row + 1,
                "code": c_str,
                "institution": row_inst.acronym if row_inst else "UNEMI",
                "patient_name": dup_name or f"Código {c_str}"
            })
        else:
            new_patients_count += 1

    if internal_duplicates:
        warnings.append(
            f"Se detectaron {len(internal_duplicates)} código(s) duplicado(s) dentro del mismo archivo SPSS "
            f"(ej: Código {internal_duplicates[0]['code']})."
        )

    if db_duplicates:
        warnings.append(
            f"Se encontraron {len(db_duplicates)} paciente(s) que ya existen en la base de datos "
            f"(Códigos: {', '.join([d['code'] for d in db_duplicates[:5]])}{'...' if len(db_duplicates) > 5 else ''}). "
            f"Serán sincronizados y actualizados con los datos del archivo."
        )

    # Vista previa de los primeros 5 registros
    preview_rows = []
    num_preview = min(5, total_rows)
    for i in range(num_preview):
        row_data = {}
        for f_key in ['codigo', 'sexo', 'edad', 'fecha_visita', 'tas', 'tad', 'peso', 'talla', 'ciudad_res', 'universidad']:
            c_name = field_to_col.get(f_key)
            if c_name:
                raw_val = df_dict[c_name][i]
                vlabels = meta.variable_value_labels.get(c_name, {})
                _, lbl = _get_val_and_label(raw_val, vlabels)
                if lbl:
                    row_data[f_key] = lbl
                elif raw_val is not None:
                    if f_key in ['codigo', 'edad'] and isinstance(raw_val, (int, float)):
                        row_data[f_key] = str(int(raw_val))
                    else:
                        row_data[f_key] = str(raw_val)
                else:
                    row_data[f_key] = "--"
            else:
                row_data[f_key] = "--"

        # Si no hay código explícito
        if row_data.get('codigo') == "--":
            row_data['codigo'] = str(i + 1)

        # Determinar si este registro de previsualización es duplicado existente
        prev_sc = row_data.get('codigo')
        prev_u = (row_data.get('universidad') or '').upper()
        prev_inst = inst_espol if 'ESPOL' in prev_u else inst_unemi
        prev_key = (prev_inst.institution_id if prev_inst else 1, prev_sc)
        is_preview_dup = prev_key in db_visits_map
        row_data['is_duplicate'] = is_preview_dup
        row_data['status_label'] = 'Duplicado (Existente)' if is_preview_dup else 'Nuevo'

        preview_rows.append(row_data)

    categories_breakdown = {
        "demograficos": len([c for c in field_to_col.keys() if c in ['codigo', 'cedula', 'nombres', 'apellido1', 'sexo', 'edad', 'ciudad_res', 'provincia_res', 'fecha_nac', 'raza', 'estado_civil']]),
        "exploracion_fisica": len([c for c in field_to_col.keys() if c in ['peso', 'talla', 'imc', 'perimetro', 'tas', 'tad', 'sat_o2', 'fc', 'soplos', 'pulsos']]),
        "ecg": len([c for c in field_to_col.keys() if c.startswith('ecg_')]),
        "laboratorio": len([c for c in field_to_col.keys() if c.startswith('lab_')]),
        "ecocardiograma": len([c for c in field_to_col.keys() if c.startswith('eco_')]),
        "cuestionarios_adicionales": total_cols - len(field_to_col)
    }

    return {
        "success": True,
        "file_name": filename,
        "total_rows": total_rows,
        "total_columns": total_cols,
        "mapped_standard_columns": len(field_to_col),
        "unmapped_extra_columns": total_cols - len(field_to_col),
        "categories_breakdown": categories_breakdown,
        "grammatical_errors": grammatical_errors,
        "grammatical_errors_count": len(grammatical_errors),
        "column_mappings": column_mappings,
        "column_mappings_count": len(column_mappings),
        "duplicates": {
            "internal_duplicates": internal_duplicates,
            "internal_duplicates_count": len(internal_duplicates),
            "db_duplicates": db_duplicates,
            "db_duplicates_count": len(db_duplicates),
            "new_patients_count": new_patients_count
        },
        "missing_fields": missing_fields,
        "warnings": warnings,
        "preview_rows": preview_rows,
        "temp_token": temp_token
    }

