"""Loader for the zero-row UNEMI SPSS reference matrix shipped with the app."""

from functools import lru_cache
from pathlib import Path

import pyreadstat


UNEMI_REFERENCE_MATRIX_PATH = Path(__file__).with_name('unemi_reference_empty.sav')


@lru_cache(maxsize=1)
def load_unemi_reference_metadata():
    """Read schema metadata only and reject any reference containing cases."""
    if not UNEMI_REFERENCE_MATRIX_PATH.is_file():
        raise RuntimeError(
            f'No se encuentra la matriz de referencia vacía de UNEMI: '
            f'{UNEMI_REFERENCE_MATRIX_PATH.name}'
        )

    empty_frame, metadata = pyreadstat.read_sav(
        str(UNEMI_REFERENCE_MATRIX_PATH),
        metadataonly=True,
        apply_value_formats=False,
    )
    if len(empty_frame) != 0 or getattr(metadata, 'number_rows', None) != 0:
        raise RuntimeError('La matriz de referencia de UNEMI debe estar vacía y sin registros.')
    if not metadata.column_names:
        raise RuntimeError('La matriz de referencia de UNEMI no contiene columnas.')
    return metadata
