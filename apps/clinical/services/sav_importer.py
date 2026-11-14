# -*- coding: utf-8 -*-
"""
sav_importer.py
Fachada retrocompatible para el subsistema de importación clínica.
Delega su funcionalidad interna a los submódulos especializados en `clinical.services.importer`.
"""

import pyreadstat

from .importer.constants import (
    COLUMN_TYPO_RULES,
    SPSS_QUESTION_ALIASES,
    STANDARD_FIELD_ALIASES,
    FIELD_DESTINATIONS,
    CIUDAD_CODE_MAP,
)
from .importer.normalizers import (
    normalize_var_name,
    classify_spss_question_section,
    _match_column_to_field,
    get_column_destination,
    detect_column_typos,
    _CANTONS_CACHE,
    _get_cantons_cache,
    _resolve_canton_safe,
    _is_empty_or_nan,
    _clean_decimal,
    _get_val_and_label,
)
from .importer.readers import (
    _SPEC_VALUE_LABELS,
    _get_spec_value_labels,
    DatasetMetadata,
    _sanitize_dataset_dict,
    _read_dataset_file,
)
from .importer.analyzer import (
    _analyze_staged_dataset as _impl_analyze_staged_dataset,
    analyze_sav_file as _impl_analyze_sav_file,
)
from .importer.executor import (
    _execute_staged_dataset as _impl_execute_staged_dataset,
    execute_sav_import as _impl_execute_sav_import,
)

# -----------------------------------------------------------------------------
# Funciones delegadas con resolución dinámica para compatibilidad con mocks y patches
# -----------------------------------------------------------------------------

def _analyze_staged_dataset(temp_path, filename, temp_token=None):
    """Delega el análisis inspeccionando reader_fn en el ámbito de sav_importer."""
    return _impl_analyze_staged_dataset(temp_path, filename, temp_token=temp_token, reader_fn=_read_dataset_file)


def analyze_sav_file(file_obj, filename="archivo.sav", user=None):
    """Inicia el análisis y validación previa de un archivo subido."""
    return _impl_analyze_sav_file(file_obj, filename=filename, user=user)


def _execute_staged_dataset(temp_path, user, current_year=2026, duplicate_action="update"):
    """Delega la ejecución de importación inspeccionando reader_fn en el ámbito de sav_importer."""
    return _impl_execute_staged_dataset(
        temp_path,
        user,
        current_year=current_year,
        duplicate_action=duplicate_action,
        reader_fn=_read_dataset_file
    )


def execute_sav_import(temp_token, user, current_year=2026, duplicate_action="update"):
    """Reclama un archivo analizado previamente y ejecuta la importación a la base de datos."""
    return _impl_execute_sav_import(
        temp_token,
        user,
        current_year=current_year,
        duplicate_action=duplicate_action
    )


__all__ = [
    # Constantes
    'COLUMN_TYPO_RULES',
    'SPSS_QUESTION_ALIASES',
    'STANDARD_FIELD_ALIASES',
    'FIELD_DESTINATIONS',
    'CIUDAD_CODE_MAP',
    # Normalizadores y utilidades
    'normalize_var_name',
    'classify_spss_question_section',
    '_match_column_to_field',
    'get_column_destination',
    'detect_column_typos',
    '_CANTONS_CACHE',
    '_get_cantons_cache',
    '_resolve_canton_safe',
    '_is_empty_or_nan',
    '_clean_decimal',
    '_get_val_and_label',
    # Lectores y metadatos
    '_SPEC_VALUE_LABELS',
    '_get_spec_value_labels',
    'DatasetMetadata',
    '_sanitize_dataset_dict',
    '_read_dataset_file',
    # Diagnóstico y ejecución
    'analyze_sav_file',
    '_analyze_staged_dataset',
    'execute_sav_import',
    '_execute_staged_dataset',
]
