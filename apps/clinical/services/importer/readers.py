# -*- coding: utf-8 -*-
"""
readers.py
Lectura inteligente de archivos de datos clínicos en formato SPSS (.sav / .zsav),
RStudio (.rds, .RData, .rda, .r) y CSV con sanitización profunda de tipos y valores nulos.
"""

import os
import math
from pathlib import Path
from decimal import Decimal

import pandas as pd
import pyreadstat

from .normalizers import normalize_phone_value, normalize_var_name
from ..reference_matrix import load_unemi_reference_metadata

_STRING_IDENTIFIER_COLS = frozenset({
    'cedula', 'ci', 'id_card', 'identificacion',
    'telefono', 'celular', 'phone', 'num_telefono', 'tlf', 'telefono_contacto',
})
_PHONE_COLS = frozenset({
    'telefono', 'celular', 'phone', 'num_telefono', 'tlf', 'telefono_contacto',
})


def _sanitize_dataset_dict(raw_dict):
    """
    Reemplaza NaN, NaT, infinitos y cadenas vacías por None en todas las columnas
    para evitar fallos de casteo a Decimal o enteros en Django, y limpia valores
    numéricos/flotantes en columnas telefónicas (ej. 991792652.0 -> '0991792652').
    """
    import math
    import pandas as pd
    clean_dict = {}
    for col, values in raw_dict.items():
        norm_col = normalize_var_name(col)
        is_phone_col = norm_col in _PHONE_COLS
        clean_vals = []
        for v in values:
            if v is None:
                clean_vals.append(None)
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_vals.append(None)
            elif is_phone_col and (isinstance(v, (int, float)) or (isinstance(v, str) and ('.' in v or 'e+' in v.lower()))):
                clean_vals.append(normalize_phone_value(v))
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
    """Load UNEMI value labels from the checked-in, zero-row reference SAV."""
    global _SPEC_VALUE_LABELS
    if _SPEC_VALUE_LABELS is None:
        metadata = load_unemi_reference_metadata()
        _SPEC_VALUE_LABELS = dict(metadata.variable_value_labels or {})
    return _SPEC_VALUE_LABELS


class DatasetMetadata:
    """Metadatos estandarizados para archivos SPSS, RStudio y CSV."""
    def __init__(self, df, variable_value_labels=None, column_labels=None):
        self.number_rows = len(df)
        self.number_columns = len(df.columns)
        self.column_names = [str(c) for c in df.columns]
        reference_labels = load_unemi_reference_metadata().column_names_to_labels or {}
        if column_labels:
            self.column_labels = column_labels
        else:
            self.column_labels = [reference_labels.get(str(c)) or str(c) for c in df.columns]
        self.column_names_to_labels = dict(zip(self.column_names, self.column_labels))

        # Completar etiquetas faltantes desde la matriz vacía de referencia UNEMI.
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
            import csv

            encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
            sample_bytes = b''
            try:
                with open(str(temp_path), 'rb') as f_sample:
                    sample_bytes = f_sample.read(16384)
            except Exception:
                pass

            # Detectar delimitador adecuado (, ; \t |)
            detected_sep = None
            if sample_bytes:
                sample_text = ""
                for enc in encodings:
                    try:
                        sample_text = sample_bytes.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue

                if sample_text:
                    try:
                        dialect = csv.Sniffer().sniff(sample_text[:4096], delimiters=',;\t|')
                        detected_sep = dialect.delimiter
                    except Exception:
                        first_line = sample_text.splitlines()[0] if sample_text.splitlines() else ""
                        c_semi = first_line.count(';')
                        c_comma = first_line.count(',')
                        c_tab = first_line.count('\t')
                        if c_semi > c_comma and c_semi > c_tab:
                            detected_sep = ';'
                        elif c_tab > c_comma and c_tab > c_semi:
                            detected_sep = '\t'
                        else:
                            detected_sep = ','

            df = None
            last_err = None
            for enc in encodings:
                try:
                    read_kwargs = {'encoding': enc}
                    if detected_sep:
                        hdr = pd.read_csv(str(temp_path), sep=detected_sep, encoding=enc, nrows=0)
                        str_dtypes = {
                            c: str for c in hdr.columns
                            if normalize_var_name(c) in _STRING_IDENTIFIER_COLS
                        }
                        df = pd.read_csv(str(temp_path), sep=detected_sep, encoding=enc, dtype=str_dtypes or None)
                    else:
                        hdr = pd.read_csv(str(temp_path), sep=None, engine='python', encoding=enc, nrows=0)
                        str_dtypes = {
                            c: str for c in hdr.columns
                            if normalize_var_name(c) in _STRING_IDENTIFIER_COLS
                        }
                        df = pd.read_csv(str(temp_path), sep=None, engine='python', encoding=enc, dtype=str_dtypes or None)

                    # Si sólo leyó 1 columna pero hay delimitadores comunes en el encabezado, reintentar
                    if len(df.columns) == 1 and (';' in str(df.columns[0]) or ',' in str(df.columns[0])):
                        for alt_sep in (';', ','):
                            if alt_sep in str(df.columns[0]):
                                hdr = pd.read_csv(str(temp_path), sep=alt_sep, encoding=enc, nrows=0)
                                str_dtypes = {
                                    c: str for c in hdr.columns
                                    if normalize_var_name(c) in _STRING_IDENTIFIER_COLS
                                }
                                df = pd.read_csv(str(temp_path), sep=alt_sep, encoding=enc, dtype=str_dtypes or None)
                                break
                    break
                except UnicodeDecodeError as ue:
                    last_err = ue
                    continue
                except Exception as e:
                    last_err = e
                    continue

            if df is None:
                raise last_err or ValueError("No se pudo leer el archivo CSV.")

            # Limpiar espacios en blanco y caracteres de control en nombres de columnas
            df.columns = [str(col).strip() for col in df.columns]

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



