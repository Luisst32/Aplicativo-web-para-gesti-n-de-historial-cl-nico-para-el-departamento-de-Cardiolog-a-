# -*- coding: utf-8 -*-
"""
Paquete modular de importación clínica para archivos SPSS (.sav / .zsav),
RStudio (.rds, .RData, .rda, .r) y CSV.
"""

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
    _CANTONS_CACHE,
    _get_cantons_cache,
    _resolve_canton_safe,
    _is_empty_or_nan,
    _clean_decimal,
    _get_val_and_label,
)
from .readers import (
    _SPEC_VALUE_LABELS,
    _get_spec_value_labels,
    DatasetMetadata,
    _sanitize_dataset_dict,
    _read_dataset_file,
)
from .analyzer import (
    analyze_sav_file,
    _analyze_staged_dataset,
)
from .executor import (
    execute_sav_import,
    _execute_staged_dataset,
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
    # Lectores
    '_SPEC_VALUE_LABELS',
    '_get_spec_value_labels',
    'DatasetMetadata',
    '_sanitize_dataset_dict',
    '_read_dataset_file',
    # Analizador y Ejecutor
    'analyze_sav_file',
    '_analyze_staged_dataset',
    'execute_sav_import',
    '_execute_staged_dataset',
]
