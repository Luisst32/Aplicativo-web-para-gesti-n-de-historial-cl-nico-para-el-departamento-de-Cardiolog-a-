# -*- coding: utf-8 -*-
"""
readers.py
Lectura inteligente de archivos de datos clínicos en formato SPSS (.sav / .zsav),
RStudio (.rds, .RData, .rda, .r) y CSV con sanitización profunda de tipos y valores nulos.
"""

import os
import json
import math
from pathlib import Path
from decimal import Decimal

import pandas as pd
import pyreadstat

from .normalizers import normalize_var_name

def _sanitize_dataset_dict(raw_dict):
    """
    Reemplaza NaN, NaT, infinitos y cadenas vacías por None en todas las columnas
    para evitar fallos de casteo a Decimal o enteros en Django.
    """
    import math
    import pandas as pd
    clean_dict = {}
    for col, values in raw_dict.items():
        clean_vals = []
        for v in values:
            if v is None:
                clean_vals.append(None)
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_vals.append(None)
            elif isinstance(v, str):
                s = v.strip()
                if s.lower() in ('', 'nan', 'none', 'null', 'na', '<na>'):
                    clean_vals.append(None)
                else:
                    clean_vals.append(s)
            else:
                try:
                    if pd.isna(v):
                        clean_vals.append(None)
                        continue
                except Exception:
                    pass
                clean_vals.append(v)
        clean_dict[str(col)] = clean_vals
    return clean_dict




_SPEC_VALUE_LABELS = None

def _get_spec_value_labels():
    """Carga de forma perezosa y cacheada el diccionario maestro de value_labels oficial de UNEMI."""
    global _SPEC_VALUE_LABELS
    if _SPEC_VALUE_LABELS is None:
        try:
            # Busca en el directorio actual o en el directorio padre (services/)
            spec_path = Path(__file__).resolve().parent / 'sav_columns_spec.json'
            if not spec_path.exists():
                spec_path = Path(__file__).resolve().parent.parent / 'sav_columns_spec.json'

            if spec_path.exists():
                with open(spec_path, 'r', encoding='utf-8') as f:
                    raw_spec = json.load(f)
                _SPEC_VALUE_LABELS = raw_spec.get('value_labels', {})
            else:
                _SPEC_VALUE_LABELS = {}
        except Exception:
            _SPEC_VALUE_LABELS = {}
    return _SPEC_VALUE_LABELS


class DatasetMetadata:
    """Metadatos estandarizados para archivos SPSS, RStudio y CSV."""
    def __init__(self, df, variable_value_labels=None, column_labels=None):
        self.number_rows = len(df)
        self.number_columns = len(df.columns)
        self.column_names = [str(c) for c in df.columns]
        self.column_labels = column_labels or [str(c) for c in df.columns]
        self.column_names_to_labels = dict(zip(self.column_names, self.column_labels))

        # Combinar value labels provistas con el catálogo oficial de UNEMI (sav_columns_spec.json)
        # Esto permite que archivos exportados desde RStudio o CSV (que no portan etiquetas de SPSS)
        # resuelvan automáticamente los códigos numéricos de estamentos, cantones, etc.
        combined_vl = {}
        spec_vl = _get_spec_value_labels()
        for k, v in spec_vl.items():
            combined_vl[k] = dict(v)
            combined_vl[k.upper()] = dict(v)
            combined_vl[k.lower()] = dict(v)
            combined_vl[normalize_var_name(k)] = dict(v)

        if variable_value_labels:
            for k, v in variable_value_labels.items():
                if k not in combined_vl:
                    combined_vl[k] = {}
                combined_vl[k].update(v)
                norm_k = normalize_var_name(k)
                if norm_k not in combined_vl:
                    combined_vl[norm_k] = {}
                combined_vl[norm_k].update(v)

        self.variable_value_labels = combined_vl




def _read_dataset_file(temp_path: Path, filename: str):
    """
    Lee archivos SPSS (.sav, .zsav) mediante pyreadstat,
    archivos de RStudio (.rds, .RData, .rda, .r) mediante pyreadr,
    o archivos CSV mediante pandas.
    """
    ext = Path(filename).suffix.lower()
    if ext in ('.rds', '.rdata', '.rda', '.r'):
        try:
            import pyreadr
            import pandas as pd
            res = pyreadr.read_r(str(temp_path))
            df = None
            if None in res:
                df = res[None]
            elif res:
                dfs = [v for v in res.values() if hasattr(v, 'columns')]
                if dfs:
                    df = max(dfs, key=lambda d: len(d))
            if df is None:
                raise ValueError("No se encontró ningún DataFrame válido en el archivo de RStudio.")

            df_clean = df.astype(object).where(pd.notnull(df), None)
            df_dict = {str(col): df_clean[col].tolist() for col in df_clean.columns}
            df_dict = _sanitize_dataset_dict(df_dict)
            meta = DatasetMetadata(df_clean)
            return df_dict, meta
        except Exception as r_err:
            err_msg = str(r_err)
            if "Unhandled S-Expression" in err_msg or "Unable to read" in err_msg:
                raise ValueError(
                    "El archivo seleccionado es un script de código o formato no soportado. "
                    "Para importar datos de RStudio, guarda tu DataFrame como .rds o .RData (ej: saveRDS(datos, 'archivo.rds') o save(datos, file='archivo.RData'))."
                )
            raise ValueError(f"Error al leer archivo de RStudio: {err_msg}")

    elif ext == '.csv':
        try:
            import pandas as pd
            df = pd.read_csv(str(temp_path))
            df_clean = df.astype(object).where(pd.notnull(df), None)
            df_dict = {str(col): df_clean[col].tolist() for col in df_clean.columns}
            df_dict = _sanitize_dataset_dict(df_dict)
            meta = DatasetMetadata(df_clean)
            return df_dict, meta
        except Exception as csv_err:
            raise ValueError(f"Error al leer archivo CSV: {str(csv_err)}")

    else:
        # SPSS .sav / .zsav
        import sys
        sav_mod = sys.modules.get('apps.clinical.services.sav_importer') or sys.modules.get('clinical.services.sav_importer')
        prs = getattr(sav_mod, 'pyreadstat', pyreadstat) if sav_mod else pyreadstat
        df_dict, meta = prs.read_sav(str(temp_path), output_format="dict")
        df_dict = _sanitize_dataset_dict(df_dict)
        return df_dict, meta



