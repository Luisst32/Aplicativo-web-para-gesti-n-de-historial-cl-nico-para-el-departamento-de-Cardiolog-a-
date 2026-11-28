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

from .normalizers import normalize_id_card_value, normalize_phone_value, normalize_var_name
from ..reference_matrix import load_unemi_reference_metadata

_STRING_IDENTIFIER_COLS = frozenset({
    'cedula', 'ci', 'id_card', 'identificacion',
    'telefono', 'celular', 'phone', 'num_telefono', 'tlf', 'telefono_contacto',
})
_ID_CARD_COLS = frozenset({
    'cedula', 'ci', 'id_card', 'identificacion',
})
_PHONE_COLS = frozenset({
    'telefono', 'celular', 'phone', 'num_telefono', 'tlf', 'telefono_contacto',
})


def _sanitize_dataset_dict(raw_dict, *, preserve_raw_strings=False):
    """
    Reemplaza NaN, NaT, infinitos y cadenas vacías por None en todas las columnas
    para evitar fallos de casteo a Decimal o enteros en Django, y limpia valores
    numéricos/flotantes en columnas de cédula y teléfono (ej. 991792652.0 -> '0991792652').
    """
    import math
    import pandas as pd
    clean_dict = {}
    for col, values in raw_dict.items():
        norm_col = normalize_var_name(col)
        is_phone_col = norm_col in _PHONE_COLS
        is_id_col = norm_col in _ID_CARD_COLS
        clean_vals = []
        for v in values:
            if v is None:
                clean_vals.append(None)
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_vals.append(None)
            elif is_phone_col and (
                isinstance(v, (int, float))
                or (
                    not preserve_raw_strings
                    and isinstance(v, str)
                    and ('.' in v or 'e+' in v.lower() or (len(v.strip()) == 9 and v.strip().isdigit()))
                )
            ):
                clean_vals.append(normalize_phone_value(v))
            elif is_id_col and (
                isinstance(v, (int, float))
                or (
                    not preserve_raw_strings
                    and isinstance(v, str)
                    and ('.' in v or 'e+' in v.lower() or (len(v.strip()) == 9 and v.strip().isdigit()))
                )
            ):
                clean_vals.append(normalize_id_card_value(v))
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


def _read_xlsx_to_dataframe(temp_path: Path) -> pd.DataFrame:
    """
    Lee la primera hoja de un libro Excel (.xlsx) usando únicamente librerías
    estándar (zipfile + ElementTree), preservando cadenas con ceros iniciales.
    """
    import datetime
    import re
    import zipfile
    import xml.etree.ElementTree as ET

    def _local_tag(tag: str) -> str:
        return tag.split('}', 1)[-1] if '}' in tag else tag

    def _col_letters_to_idx(cell_ref: str):
        letters = []
        for ch in cell_ref:
            if ch.isalpha():
                letters.append(ch.upper())
            else:
                break
        if not letters:
            return None
        idx = 0
        for ch in letters:
            idx = idx * 26 + (ord(ch) - ord('A') + 1)
        return idx - 1

    builtin_date_ids = {14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47}

    with zipfile.ZipFile(str(temp_path), 'r') as zf:
        names = set(zf.namelist())

        shared_strings = []
        if 'xl/sharedStrings.xml' in names:
            ss_root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
            for si in ss_root:
                if _local_tag(si.tag) == 'si':
                    text = ''.join((node.text or '') for node in si.iter() if _local_tag(node.tag) == 't')
                    shared_strings.append(text)

        date_style_indices = set()
        text_style_indices = set()
        if 'xl/styles.xml' in names:
            st_root = ET.fromstring(zf.read('xl/styles.xml'))
            custom_num_fmts = {}
            for elem in st_root.iter():
                if _local_tag(elem.tag) == 'numFmt':
                    fmt_id = elem.attrib.get('numFmtId')
                    fmt_code = elem.attrib.get('formatCode', '')
                    if fmt_id is not None:
                        try:
                            custom_num_fmts[int(fmt_id)] = fmt_code
                        except ValueError:
                            pass
            for elem in st_root:
                if _local_tag(elem.tag) == 'cellXfs':
                    for xf_idx, xf in enumerate(elem):
                        if _local_tag(xf.tag) != 'xf':
                            continue
                        raw_fmt = xf.attrib.get('numFmtId')
                        if raw_fmt is None:
                            continue
                        try:
                            fmt_id = int(raw_fmt)
                        except ValueError:
                            continue
                        if fmt_id == 49 or custom_num_fmts.get(fmt_id) == '@':
                            text_style_indices.add(xf_idx)
                        elif fmt_id in builtin_date_ids:
                            date_style_indices.add(xf_idx)
                        elif fmt_id in custom_num_fmts:
                            cleaned = re.sub(r'\[[^\]]*\]|"[^"]*"', '', custom_num_fmts[fmt_id]).lower()
                            if any(tok in cleaned for tok in ('y', 'd')) and not any(tok in cleaned for tok in ('#', '0')):
                                date_style_indices.add(xf_idx)

        sheet_candidates = sorted(
            n for n in names
            if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')
        )
        if not sheet_candidates:
            raise ValueError('El archivo .xlsx no contiene hojas de cálculo válidas.')

        ws_root = ET.fromstring(zf.read(sheet_candidates[0]))
        parsed_rows = []
        for elem in ws_root.iter():
            if _local_tag(elem.tag) != 'row':
                continue
            row_map = {}
            next_col = 0
            for cell in elem:
                if _local_tag(cell.tag) != 'c':
                    continue
                ref = cell.attrib.get('r', '')
                col_idx = _col_letters_to_idx(ref)
                if col_idx is None:
                    col_idx = next_col
                next_col = col_idx + 1

                c_type = cell.attrib.get('t', '')
                style_attr = cell.attrib.get('s')
                style_idx = int(style_attr) if (style_attr and style_attr.isdigit()) else None

                val = None
                if c_type == 'inlineStr':
                    val = ''.join((n.text or '') for n in cell.iter() if _local_tag(n.tag) == 't')
                else:
                    v_text = None
                    for ch_elem in cell:
                        if _local_tag(ch_elem.tag) == 'v':
                            v_text = ch_elem.text
                            break
                    if v_text is None:
                        val = None
                    elif c_type == 's':
                        idx_ss = int(v_text)
                        val = shared_strings[idx_ss] if 0 <= idx_ss < len(shared_strings) else v_text
                    elif c_type in ('str', 'e'):
                        val = None if c_type == 'e' else v_text
                    elif c_type == 'b':
                        val = (v_text == '1')
                    elif style_idx in text_style_indices:
                        val = str(v_text)
                    elif style_idx in date_style_indices:
                        try:
                            serial = float(v_text)
                            dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=serial)
                            val = dt.date().isoformat() if serial.is_integer() else dt.isoformat(sep=' ')
                        except Exception:
                            val = v_text
                    else:
                        try:
                            num = float(v_text)
                            val = int(num) if num.is_integer() else num
                        except ValueError:
                            val = v_text

                row_map[col_idx] = val

            if row_map:
                max_col = max(row_map.keys())
                parsed_rows.append([row_map.get(c) for c in range(max_col + 1)])

    if not parsed_rows:
        return pd.DataFrame()

    header_raw = parsed_rows[0]
    headers = [
        str(col).strip() if (col is not None and str(col).strip() != '') else f'COL_{idx + 1}'
        for idx, col in enumerate(header_raw)
    ]
    n_cols = len(headers)
    data_rows = []
    for raw_r in parsed_rows[1:]:
        if all(cell is None or (isinstance(cell, str) and cell.strip() == '') for cell in raw_r):
            continue
        padded = list(raw_r[:n_cols]) + [None] * max(0, n_cols - len(raw_r))
        data_rows.append(padded)

    return pd.DataFrame(data_rows, columns=headers)




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

    elif ext == '.xlsx':
        try:
            import pandas as pd
            df = _read_xlsx_to_dataframe(temp_path)
            df_clean = df.astype(object).where(pd.notnull(df), None)
            df_dict = {str(col): df_clean[col].tolist() for col in df_clean.columns}
            df_dict = _sanitize_dataset_dict(df_dict)
            meta = DatasetMetadata(df_clean)
            return df_dict, meta
        except Exception as xlsx_err:
            raise ValueError(f"Error al leer archivo Excel (.xlsx): {str(xlsx_err)}")

    else:
        # SPSS .sav / .zsav
        import sys
        sav_mod = sys.modules.get('apps.clinical.services.sav_importer') or sys.modules.get('clinical.services.sav_importer')
        prs = getattr(sav_mod, 'pyreadstat', pyreadstat) if sav_mod else pyreadstat
        df_dict, meta = prs.read_sav(str(temp_path), output_format="dict")
        df_dict = _sanitize_dataset_dict(df_dict, preserve_raw_strings=True)
        return df_dict, meta



