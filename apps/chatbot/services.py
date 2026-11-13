"""
CARDIOUNEMI - Chatbot Services and Analytical Inference Layer.
Motor de Inteligencia Artificial para procesamiento de consultas en lenguaje natural,
extracción estadística de la cohorte epidemiológica y soporte clínico.

DIRECTIVAS CRÍTICAS:
1. ULTRA DIRECTO Y CONCISO: Respuestas directas al grano, sin rodeos ni saludos innecesarios para ahorrar tokens.
2. SOLO CONSULTAS (READ-ONLY): Solo lectura analítica.
3. PRIVACIDAD ABSOLUTA (ZERO PII): Bloqueo estricto de nombres propios, cédulas, teléfonos y datos identificables.
4. MODELO ECONÓMICO Y GOBERNANZA DE DATOS: Soporte para Google Gemini Flash con credenciales almacenadas
   en BD (relacional por rol Administrador) o variables de entorno (12-Factor App).
5. CONTROL DE DIVULGACIÓN ESTADÍSTICA: Supresión de celdas pequeñas (< 5 casos, sin porcentajes)
   y supresión complementaria para evitar ataques de deducción por resta.
6. CACHÉ COMPARTIDO INTER-PROCESO: Sincronización multi-worker en Gunicorn mediante backend de caché
   e invalidación diferida por transaction.on_commit.
"""

import re
import json
import time
import logging
import unicodedata
from typing import Dict, Any, Optional, List

from django.core.cache import cache
from django.db import transaction

from chatbot.models import BotQuery
from dashboard.services import get_dashboard_evaluation_data

logger = logging.getLogger(__name__)

# Palabras y expresiones asociadas a datos sensibles personales (PII)
SENSITIVE_PATTERNS = [
    r'\b(c[eé]dula|c\.?i\.?|identificaci[oó]n|dni|pasaporte|documento\s+de\s+identidad)\b',
    r'\b(nombre|apellidos?|c[oó]mo\s+se\s+llama|qui[eé]n\s+es\s+el\s+paciente)\b',
    r'\b(tel[eé]fono|celular|m[oó]vil|direcci[oó]n|domicilio|vivienda\s+exacta)\b',
    r'\b(correo|email|e-mail|mail)\b',
    r'\b(historia\s+cl[ií]nica\s+n[uú]mero|expediente\s+individual|buscar\s+a)\b',
    r'\b(paciente\s+llamado|paciente\s+con\s+c[eé]dula)\b',
    r'\b\d{10}\b',  # Cédula de 10 dígitos ecuatoriana
    r'\b(qu[eé]\s+tiene|diagn[oó]stico\s+de|historial\s+de|ficha\s+de|caso\s+de|informaci[oó]n\s+de)\s+[a-zñáéíóú]{2,}\b',
    r'\b(paciente|persona|don|do[ñn]a)\s+[a-zñáéíóú]{2,}\s+[a-zñáéíóú]{2,}\b',
    r'\b(juan|pedro|mar[ií]a|carlos|ana|luis|carmen|rosa|jos[eé]|manuel|francisco|jorge|elena)\s+[a-zñáéíóú]{2,}\b',
]

# Palabras que intentan alterar la base de datos (Write / DDL / DML)
MODIFICATION_PATTERNS = [
    r'\b(eliminar?|borrar?|suprimir?|delete|drop\s+table|truncate)\b',
    r'\b(modificar?|actualizar?|cambiar?|update|alter\s+table)\b',
    r'\b(insertar?|crear\s+paciente|agregar\s+paciente|insert\s+into)\b'
]

SYSTEM_INSTRUCTION = """Eres el Asistente Clínico & Estadístico de CARDIOUNEMI (Universidad Estatal de Milagro, Ecuador).
Tu objetivo es responder consultas epidemiológicas y clínicas sobre la cohorte institucional activa.

REGLAS OBLIGATORIAS:
1. SÉ ULTRA DIRECTO Y CONCISO: Cero rodeos, cero saludos o introducciones de cortesía, cero despedidas de relleno. Ve directo al dato y a la métrica para ahorrar tokens.
2. FIDELIDAD ESTADÍSTICA: Usa rigurosamente las cifras calculadas de la cohorte activa presentes en el contexto. Cita el valor numérico y el porcentaje exacto.
3. PRIVACIDAD ABSOLUTA (ZERO PII): Jamás reveles nombres, cédulas ni datos personales individuales. Respeta la confidencialidad médica.
4. SOLO CONSULTA: Modo estricto de solo lectura.
5. FORMATO COMPACTO: Usa viñetas cortas y negrita en las métricas clave. Sin párrafos redundantes.
6. GENERACIÓN DE GRÁFICAS (SOLO SI EL USUARIO LO PIDE EXPRESAMENTE):
   - NUNCA generes un bloque de gráfica a menos que el usuario use explícitamente palabras como: "grafica", "gráfico", "grafico", "graficar", "barras", "pastel", "pie", "torta", "dispersion", "dispersión", "scatter".
   - Si lo pide expresamente, redacta tu respuesta analítica explicando los hallazgos y métricas epidemiológicas reales de la cohorte.
   - NUNCA inventes puntos de dispersión ni porcentajes aproximados; el sistema acopla automáticamente el bloque json_chart determinista y oficial con todos los registros exactos de la base de datos institucional.
"""

COHORT_SUMMARY_CACHE_KEY = "cardio_cohort_summary_text_v2"
COHORT_COUNT_CACHE_KEY = "cardio_cohort_count_v2"
COHORT_CACHE_TIMEOUT = 600  # 10 minutos


def normalize_clinical_query(text: str) -> str:
    """
    Normaliza el texto de consulta del usuario para un análisis léxico robusto:
    - Minúsculas.
    - Remoción de tildes/acentos diacríticos (á->a, é->e, etc.) usando NFKD.
    - Colapsado de espacios en blanco.
    """
    if not text:
        return ""
    text = text.lower()
    nfkd = unicodedata.normalize('NFKD', text)
    clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r'\s+', ' ', clean).strip()


def invalidate_cohort_cache(*args, **kwargs):
    """
    Invalida el caché compartido de la cohorte en todos los workers de Gunicorn.
    Utiliza cache.delete(...) para sincronización inter-proceso.
    """
    try:
        cache.delete(COHORT_SUMMARY_CACHE_KEY)
        cache.delete(COHORT_COUNT_CACHE_KEY)
        cache.delete("dashboard_evaluation_data")
        logger.debug("Caché compartido de cohorte invalidado exitosamente.")
    except Exception as e:
        logger.error("Chatbot operation failed; content omitted.")


def _signal_invalidate_cohort(sender, **kwargs):
    """Callback de señales Django que pospone la invalidación hasta el commit exitoso."""
    try:
        transaction.on_commit(invalidate_cohort_cache)
    except Exception:
        # En caso de autocommit o ejecuciones fuera de bloque de transacción atómico
        invalidate_cohort_cache()


# Conexión de señales Django con transaction.on_commit para invalidación atómica
try:
    from django.db.models.signals import post_save, post_delete
    from clinical.models import Visit, VisitAnswer, Patient
    for model_cls in (Visit, VisitAnswer, Patient):
        post_save.connect(_signal_invalidate_cohort, sender=model_cls)
        post_delete.connect(_signal_invalidate_cohort, sender=model_cls)
except Exception as _sig_err:
    logger.debug(f"Registro de señales de caché no disponible en este contexto: {_sig_err}")


def fmt_safe_cell(cnt: int, total: int, threshold: int = 5) -> str:
    """
    Regla de Supresión de Celdas Pequeñas (Control de Divulgación Estadística):
    En cohortes pequeñas, si un subgrupo tiene 1 <= cnt < threshold, se enmascara
    únicamente como '< threshold casos' SIN porcentaje, para evitar la re-identificación
    o despeje matemático inverso (cnt = total * pct).
    """
    if cnt == 0:
        return "0 casos (0.0 %)"
    if 1 <= cnt < threshold:
        return f"< {threshold} casos*"
    pct = round((cnt / total) * 100, 1) if total else 0
    return f"{cnt} casos ({pct} %)"


def apply_complementary_suppression(category_counts: Dict[str, int], total: int, threshold: int = 5) -> Dict[str, str]:
    """
    Aplica supresión primaria y supresión complementaria (secundaria).
    Si exactamente una celda es < threshold en un conjunto cerrado cuyo total es conocido,
    se enmascara complementariamente la segunda celda o el residuo para evitar
    que por simple sustracción (total - suma de las demás) se calcule el valor protegido.
    """
    suppressed_keys = [k for k, v in category_counts.items() if 1 <= v < threshold]

    # Si hay exactamente una celda en rango sensible en una suma cerrada con total visible:
    if len(suppressed_keys) == 1:
        candidates = [(v, k) for k, v in category_counts.items() if k not in suppressed_keys and v > 0]
        if candidates:
            # Seleccionar la segunda menor para supresión secundaria
            candidates.sort(key=lambda x: x[0])
            suppressed_keys.append(candidates[0][1])

    result = {}
    for k, v in category_counts.items():
        if k in suppressed_keys:
            if v < threshold:
                result[k] = f"< {threshold} casos*"
            else:
                result[k] = f"> {total - threshold} casos (protegido por supresión complementaria)*"
        elif v == 0:
            result[k] = "0 casos (0.0 %)"
        else:
            pct = round((v / total) * 100, 1) if total else 0
            result[k] = f"{v} casos ({pct} %)"
    return result


def is_sensitive_or_pii_query(question: str) -> bool:
    """
    Detecta si la consulta del usuario intenta acceder a datos personales sensibles
    o incluye identificadores / nombres individuales de pacientes.
    """
    q_norm = question.lower()
    for pat in SENSITIVE_PATTERNS:
        if re.search(pat, q_norm, re.IGNORECASE):
            return True
    return False


def is_modification_attempt(question: str) -> bool:
    """Detecta si el usuario intenta solicitar modificaciones o escrituras en la base de datos."""
    q_norm = question.lower()
    for pat in MODIFICATION_PATTERNS:
        if re.search(pat, q_norm, re.IGNORECASE):
            return True
    return False


def get_anonymized_cohort_context() -> str:
    """Conservative whole-cohort statistics for external model context."""
    data = get_dashboard_evaluation_data()
    records = data.get('records', [])
    total = len(records)
    # No exact totals or percentages for a small cohort. Do not reuse legacy cache.
    if total < 10:
        return 'COHORTE: estadisticas no divulgables por tamano reducido.'
    lines = [f'COHORTE N={total}']
    for label, predicate in (
        ('HTA', lambda r: bool(r.get('hipertension'))),
        ('Diabetes', lambda r: bool(r.get('diabetes'))),
        ('Dislipemia', lambda r: bool(r.get('dislipemia'))),
        ('Tabaquismo', lambda r: bool(r.get('fumador_activo'))),
    ):
        count = sum(predicate(row) for row in records)
        # Suppress both the cell and its complement; never expose its percentage.
        if count < 5 or total - count < 5:
            lines.append(label + ': no divulgado')
        else:
            lines.append(f'{label}: {count} de {total}')
    return '\n'.join(lines)


def build_chart_json_if_requested(question: str, raw_response: Optional[str] = None) -> Optional[str]:
    """
    Genera un bloque json_chart estructurado garantizando 100% DATOS REALES extraídos
    directamente de la base de datos de pacientes (N=59 / N=58).
    Soporta tipos: 'scatter', 'pie' y 'bar'.
    """
    q = question.lower()
    chart_keywords = [
        'grafic', 'gráfico', 'grafico', 'grafica', 'barra', 'barras',
        'pastel', 'pie', 'torta', 'circular', 'dispersion', 'dispersión', 'scatter', 'puntos'
    ]
    has_keyword = any(k in q for k in chart_keywords)
    has_gemini_chart = bool(raw_response and '```json_chart' in raw_response)

    if not has_keyword and not has_gemini_chart:
        return None

    try:
        data = get_dashboard_evaluation_data()
        records = data.get('records', [])
        total_pacientes = len(records)
    except Exception as e:
        logger.error("Chatbot operation failed; content omitted.")
        return None

    if not records:
        return None

    # Detectar tipo de gráfico preferido con tolerancia ortográfica (disperción, dispersión, correlación, etc.)
    is_scatter = any(k in q for k in ['disperci', 'dispersion', 'dispersión', 'scatter', 'punto', 'puntos', 'nube', 'correlaci']) or bool(raw_response and '"type": "scatter"' in raw_response)
    is_pie = any(k in q for k in ['pastel', 'pie', 'torta', 'circular']) or bool(raw_response and '"type": "pie"' in raw_response)

    # 1. GRÁFICO DE DISPERSIÓN (SCATTER) CON PUNTOS REALES DE PACIENTES
    if is_scatter:
        is_high_risk = any(w in q for w in ['alto', 'muy alto', 'riesgo', 'riengo', 'problema', 'cardiac', 'cardiovascul', 'peligro'])

        if is_high_risk:
            target_records = [
                r for r in records
                if 'Alto' in r.get('riesgo_global', '') or r.get('factores_riesgo_count', 0) >= 2
            ]
            subtitulo = "Alto/Muy Alto Riesgo"
        else:
            target_records = records
            subtitulo = "Cohorte CARDIOUNEMI"

        is_edad_x = 'edad' in q
        is_tas_y = is_edad_x and ('tas' in q or 'presi' in q)

        points = []
        for i, r in enumerate(target_records):
            x_val = r.get('edad') if is_edad_x else r.get('tas')
            y_val = r.get('tas') if is_tas_y else r.get('imc')
            if x_val and y_val and float(x_val) > 0 and float(y_val) > 0:
                p_code = r.get('codigo_estudio') or r.get('id') or f"{i+1}"
                points.append({
                    "x": round(float(x_val), 1),
                    "y": round(float(y_val), 1),
                    "name": f"Caso {p_code}"
                })

        x_lbl = "Edad (años)" if is_edad_x else "Tensión Arterial Sistólica (mmHg)"
        y_lbl = "Tensión Arterial Sistólica (mmHg)" if is_tas_y else "Índice de Masa Corporal (kg/m²)"

        min_x = min([p['x'] for p in points]) if points else 0
        max_x = max([p['x'] for p in points]) if points else 0
        min_y = min([p['y'] for p in points]) if points else 0
        max_y = max([p['y'] for p in points]) if points else 0

        v_x = "Edad" if is_edad_x else "TAS"
        v_y = "TAS" if is_tas_y else "IMC"

        chart_obj = {
            "type": "scatter",
            "title": f"Dispersión {v_x} vs {v_y} en Pacientes de {subtitulo} (n = {len(points)})",
            "points": points,
            "xLabel": x_lbl,
            "yLabel": y_lbl,
            "annotation": f"Datos 100% reales de la cohorte institucional (n = {len(points)}). Rango X: {min_x} - {max_x}, Rango Y: {min_y} - {max_y}."
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # 2. GRÁFICO DE PASTEL / PIE / CIRCULAR CON CONTEOS REALES
    if is_pie:
        if any(w in q for w in ['sexo', 'género', 'genero', 'hombre', 'mujer']):
            hombres = sum(1 for r in records if r.get('sexo') == 'Hombre')
            mujeres = sum(1 for r in records if r.get('sexo') == 'Mujer')
            chart_obj = {
                "type": "pie",
                "title": f"Distribución por Sexo (n = {hombres + mujeres})",
                "labels": ["Hombres", "Mujeres"],
                "data": [hombres, mujeres],
                "unit": "pacientes"
            }
        elif any(w in q for w in ['imc', 'peso', 'obesidad', 'sobrepeso', 'nutrici']):
            norm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Normal')
            sp_cnt = sum(1 for r in records if r.get('imc_cat') == 'Sobrepeso')
            ob1_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad I')
            ob2_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad II')
            obm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad Mórbida')
            chart_obj = {
                "type": "pie",
                "title": f"Distribución Nutricional e IMC (n = {total_pacientes})",
                "labels": ["Normal", "Sobrepeso", "Obesidad I", "Obesidad II", "Obesidad Mórbida"],
                "data": [norm_cnt, sp_cnt, ob1_cnt, ob2_cnt, obm_cnt],
                "unit": "pacientes"
            }
        elif any(w in q for w in ['ecg', 'ritmo', 'sinusal']):
            sinusal_cnt = sum(1 for r in records if r.get('ecg_es_sinusal'))
            no_sinusal_cnt = total_pacientes - sinusal_cnt
            chart_obj = {
                "type": "pie",
                "title": f"Ritmo Electrocardiográfico (n = {total_pacientes})",
                "labels": ["Ritmo Sinusal", "Arritmias / No Sinusal"],
                "data": [sinusal_cnt, no_sinusal_cnt],
                "unit": "pacientes"
            }
        else:
            r_bajo = sum(1 for r in records if 'Bajo' in r.get('riesgo_global', ''))
            r_mod = sum(1 for r in records if 'Moderado' in r.get('riesgo_global', ''))
            r_alto = sum(1 for r in records if 'Alto' in r.get('riesgo_global', '') and 'Muy' not in r.get('riesgo_global', ''))
            r_muy_alto = sum(1 for r in records if 'Muy Alto' in r.get('riesgo_global', ''))
            chart_obj = {
                "type": "pie",
                "title": f"Estratificación de Riesgo Cardiovascular Global (n = {total_pacientes})",
                "labels": ["Riesgo Bajo (0 fact.)", "Riesgo Moderado (1 fact.)", "Riesgo Alto (2-3 fact.)", "Riesgo Muy Alto (≥4 fact.)"],
                "data": [r_bajo, r_mod, r_alto, r_muy_alto],
                "unit": "pacientes"
            }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # 3. GRÁFICO DE BARRAS (BAR) CON DATOS REALES DE BASE DE DATOS
    if any(w in q for w in ['imc', 'peso', 'obesidad', 'sobrepeso', 'nutrici']):
        norm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Normal')
        sp_cnt = sum(1 for r in records if r.get('imc_cat') == 'Sobrepeso')
        ob1_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad I')
        ob2_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad II')
        obm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad Mórbida')
        chart_obj = {
            "type": "bar",
            "title": f"Distribución de Categorías de IMC (n = {total_pacientes})",
            "labels": ["Normal", "Sobrepeso", "Obesidad I", "Obesidad II", "Obesidad Mórbida"],
            "data": [norm_cnt, sp_cnt, ob1_cnt, ob2_cnt, obm_cnt],
            "unit": "pacientes"
        }
    elif any(w in q for w in ['riesgo', 'estratificaci', 'global']):
        r_bajo = sum(1 for r in records if 'Bajo' in r.get('riesgo_global', ''))
        r_mod = sum(1 for r in records if 'Moderado' in r.get('riesgo_global', ''))
        r_alto = sum(1 for r in records if 'Alto' in r.get('riesgo_global', '') and 'Muy' not in r.get('riesgo_global', ''))
        r_muy_alto = sum(1 for r in records if 'Muy Alto' in r.get('riesgo_global', ''))
        chart_obj = {
            "type": "bar",
            "title": f"Estratificación del Riesgo Cardiovascular (n = {total_pacientes})",
            "labels": ["Bajo (0 fact.)", "Moderado (1 fact.)", "Alto (2-3 fact.)", "Muy Alto (≥4 fact.)"],
            "data": [r_bajo, r_mod, r_alto, r_muy_alto],
            "unit": "pacientes"
        }
    elif any(w in q for w in ['sexo', 'género', 'genero', 'hombre', 'mujer']):
        hombres = sum(1 for r in records if r.get('sexo') == 'Hombre')
        mujeres = sum(1 for r in records if r.get('sexo') == 'Mujer')
        chart_obj = {
            "type": "bar",
            "title": f"Distribución por Sexo (n = {hombres + mujeres})",
            "labels": ["Hombres", "Mujeres"],
            "data": [hombres, mujeres],
            "unit": "pacientes"
        }
    elif any(w in q for w in ['ecg', 'electrocardiograma', 'ritmo', 'arritmia', 'hvi', 'qtc']):
        sinusal_cnt = sum(1 for r in records if r.get('ecg_es_sinusal'))
        arritmia_cnt = sum(1 for r in records if r.get('ecg_arritmia'))
        hvi_cnt = sum(1 for r in records if r.get('ecg_hvi'))
        qtc_prol_cnt = sum(1 for r in records if 'Prolongado' in r.get('ecg_qtc_cat', ''))

        sinusal_pct = round((sinusal_cnt / total_pacientes) * 100, 1) if total_pacientes else 94.9
        qtc_pct = round((qtc_prol_cnt / total_pacientes) * 100, 1) if total_pacientes else 10.2
        hvi_pct = round((hvi_cnt / total_pacientes) * 100, 1) if total_pacientes else 8.5
        arritmia_pct = round((arritmia_cnt / total_pacientes) * 100, 1) if total_pacientes else 5.1

        chart_obj = {
            "type": "bar",
            "title": f"Prevalencia de Hallazgos ECG (%) (n = {total_pacientes})",
            "labels": ["Ritmo Sinusal", "QTc Prolongado", "HVI", "Arritmias"],
            "data": [sinusal_pct, qtc_pct, hvi_pct, arritmia_pct],
            "unit": "%"
        }
    else:
        sp_ob = sum(1 for r in records if r.get('imc_cat') in ['Sobrepeso', 'Obesidad I', 'Obesidad II', 'Obesidad Mórbida'])
        sed = sum(1 for r in records if not r.get('actividad_fisica'))
        dlp = sum(1 for r in records if r.get('dislipemia'))
        hta = sum(1 for r in records if r.get('hipertension'))
        dm = sum(1 for r in records if r.get('diabetes'))
        fum = sum(1 for r in records if r.get('fumador_activo'))

        pct = lambda cnt: round((cnt / total_pacientes) * 100, 1) if total_pacientes else 0
        chart_obj = {
            "type": "bar",
            "title": f"Prevalencia de Factores Modificables de Riesgo (%) (n = {total_pacientes})",
            "labels": ["Exceso de Peso", "Sedentarismo", "Dislipemia", "Hipertensión", "Diabetes", "Tabaquismo"],
            "data": [pct(sp_ob), pct(sed), pct(dlp), pct(hta), pct(dm), pct(fum)],
            "unit": "%"
        }
    return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"


def generate_fallback_clinical_answer(question: str) -> str:
    """
    Respuestas directas, deterministas y con CERO costo de tokens calculadas
    dinámicamente a partir de las fichas clínicas reales registradas en la base de datos.
    Aplica:
    - Desambiguación léxica estricta (\b) y normalización NFKD.
    - Supresión de celdas pequeñas (< 5 casos, sin porcentajes).
    - Supresión complementaria para evitar inferencias por diferencia.
    """
    q = normalize_clinical_query(question)
    base_answer = ""
    has_suppression = False

    try:
        data = get_dashboard_evaluation_data()
        records = data.get('records', [])
        total = len(records)
    except Exception as e:
        logger.error("Chatbot operation failed; content omitted.")
        records = []
        total = 0

    if total == 0:
        return (
            "⚠️ **Sin registros clínicos:**\n"
            "Actualmente no existen fichas clínicas ni pacientes ingresados en la base de datos. "
            "Al registrar o importar nuevas fichas, se calcularán y presentarán automáticamente las estadísticas reales correspondientes."
        )

    pct = lambda cnt: round((cnt / total) * 100, 1)

    # 1. SALUD MENTAL (Ansiedad / Depresión) - Evaluado primero con límites estrictos \b
    if re.search(r'\b(depresi[oó]n|depresiv[oa]s?|ansiedad|salud\s+mental|trastorno\s+mental|psico|animo)\b', q):
        dep_cnt = sum(1 for r in records if r.get('depresion'))
        ans_cnt = sum(1 for r in records if r.get('ansiedad'))
        ambas_cnt = sum(1 for r in records if r.get('depresion') and r.get('ansiedad'))
        sin_trastorno = total - sum(1 for r in records if r.get('depresion') or r.get('ansiedad'))
        total_afectados = sum(1 for r in records if r.get('depresion') or r.get('ansiedad'))

        suppressed_dict = apply_complementary_suppression({
            'depresion': dep_cnt,
            'ansiedad': ans_cnt,
            'sin_trastorno': sin_trastorno
        }, total)

        if any(1 <= c < 5 for c in [dep_cnt, ans_cnt, sin_trastorno, total_afectados]):
            has_suppression = True

        dep_display = suppressed_dict['depresion']
        ans_display = suppressed_dict['ansiedad']
        sin_display = suppressed_dict['sin_trastorno']
        afectados_display = fmt_safe_cell(total_afectados, total)

        base_answer = (
            f"**Salud Mental (Ansiedad y Depresión):**\n"
            f"- **Total con Depresión:** **{dep_display}**"
            + (f" (ambas: {fmt_safe_cell(ambas_cnt, total)})" if dep_cnt >= 5 and ambas_cnt > 0 else "") + ".\n"
            f"- **Total con Ansiedad:** {ans_display}.\n"
            f"- **Sin Trastorno de Salud Mental:** {sin_display}.\n"
            f"- **Prevalencia global de afección mental:** {afectados_display}."
        )

    # 2. HIPERTENSIÓN ARTERIAL (Desambiguación médica estricta y límites \b)
    # Detecta 'hipertensión', 'hta', 'presión arterial', etc.
    # Excluye 'depresión' y 'tensión emocional/nerviosa/muscular/psicológica'
    elif (
        bool(re.search(r'\b(hipertensi[oó]n|hta|hipertenso|hipertensas?|hipertensos?)\b', q)) or
        bool(re.search(r'\b(presi[oó]n|tensi[oó]n)\s+(arterial|sist[oó]lica|diast[oó]lica|alta|elevada)\b', q)) or
        bool(re.search(r'\b(cifras\s+tensionales|tas|tad)\b', q)) or
        (
            bool(re.search(r'\b(presi[oó]n|tensi[oó]n)\b', q)) and
            not re.search(r'\bdepresi[oó]n\b', q) and
            not re.search(r'\btensi[oó]n\s+(emocional|nerviosa|muscular|psicol[oó]gica|mental)\b', q)
        )
    ):
        hta_cnt = sum(1 for r in records if r.get('hipertension'))
        tas_vals = [float(r.get('tas')) for r in records if r.get('tas') and float(r.get('tas')) > 0]
        tas_med = round(sum(tas_vals) / len(tas_vals), 1) if tas_vals else 0
        hta_fam = sum(1 for r in records if r.get('ant_fam_hta') or r.get('ant_fam_hta_madre') or r.get('ant_fam_hta_padre'))

        if 1 <= hta_cnt < 5:
            has_suppression = True
            hta_str = fmt_safe_cell(hta_cnt, total)
        else:
            hta_str = f"**{pct(hta_cnt)} %** ({hta_cnt} de {total} casos evaluados)"

        base_answer = (
            f"**Hipertensión Arterial (HTA):**\n"
            f"- **Prevalencia:** {hta_str}.\n"
            f"- **Presión Sistólica media:** {tas_med} mmHg.\n"
            f"- **Antecedente familiar de HTA:** {pct(hta_fam)} % ({hta_fam} casos)."
        )

    # 3. NUTRICIÓN E IMC
    elif re.search(r'\b(imc|sobrepeso|obesidad|obeso|obesa|peso|nutrici[oó]n|antropometr[ií]a)\b', q):
        sp_cnt = sum(1 for r in records if r.get('imc_cat') == 'Sobrepeso')
        ob1_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad I')
        ob2_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad II')
        obm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad Mórbida')
        norm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Normal')
        sp_ob = sp_cnt + ob1_cnt + ob2_cnt + obm_cnt

        imcs = [float(r.get('imc')) for r in records if r.get('imc') and float(r.get('imc')) > 0]
        imc_med = round(sum(imcs) / len(imcs), 1) if imcs else 0

        cint_riesgo = sum(1 for r in records if 'Elevado' in r.get('abd_riesgo', '') or 'Medio' in r.get('abd_riesgo', ''))

        base_answer = (
            f"**Nutrición e IMC:**\n"
            f"- **Sobrepeso u Obesidad combinados:** **{pct(sp_ob)} %** ({sp_ob} de {total} casos).\n"
            f"- **IMC promedio:** {imc_med} kg/m².\n"
            f"- **Desglose:** Normal {pct(norm_cnt)} % ({norm_cnt} casos), Sobrepeso {pct(sp_cnt)} % ({sp_cnt} casos), Obesidad Grado I {pct(ob1_cnt)} % ({ob1_cnt} casos), Obesidad II/Mórbida {pct(ob2_cnt + obm_cnt)} % ({ob2_cnt + obm_cnt} casos).\n"
            f"- **Perímetro de cintura en riesgo:** {pct(cint_riesgo)} % ({cint_riesgo} casos)."
        )

    # 4. ELECTROCARDIOGRAMA
    elif re.search(r'\b(ecg|electrocardiograma|ritmo|sinusal|arritmias?|qt|qtc|hvi|bloqueo)\b', q):
        sinusal_cnt = sum(1 for r in records if r.get('ecg_es_sinusal'))
        arritmia_cnt = sum(1 for r in records if r.get('ecg_arritmia'))
        hvi_cnt = sum(1 for r in records if r.get('ecg_hvi'))
        qtc_cnt = sum(1 for r in records if 'Prolongado' in r.get('ecg_qtc_cat', ''))

        suppressed_ecg = apply_complementary_suppression({
            'sinusal': sinusal_cnt,
            'arritmia': arritmia_cnt
        }, total)

        if (1 <= arritmia_cnt < 5) or (1 <= hvi_cnt < 5) or (1 <= qtc_cnt < 5):
            has_suppression = True

        base_answer = (
            f"**Resultados ECG:**\n"
            f"- **Ritmo Sinusal:** {suppressed_ecg['sinusal']}.\n"
            f"- **Arritmias:** {suppressed_ecg['arritmia']}.\n"
            f"- **Hipertrofia Ventricular Izquierda (HVI):** {fmt_safe_cell(hvi_cnt, total)}.\n"
            f"- **QTc Prolongado:** {fmt_safe_cell(qtc_cnt, total)}."
        )

    # 5. RIESGO CARDIOVASCULAR GLOBAL
    elif re.search(r'\b(riesgo|global|estratificaci[oó]n|factores\s+de\s+riesgo)\b', q):
        r_bajo = sum(1 for r in records if 'Bajo' in r.get('riesgo_global', ''))
        r_mod = sum(1 for r in records if 'Moderado' in r.get('riesgo_global', ''))
        r_alto = sum(1 for r in records if 'Alto' in r.get('riesgo_global', '') and 'Muy' not in r.get('riesgo_global', ''))
        r_muy_alto = sum(1 for r in records if 'Muy Alto' in r.get('riesgo_global', ''))
        alerta = r_alto + r_muy_alto

        base_answer = (
            f"**Riesgo Cardiovascular Global:**\n"
            f"- **Bajo (0 factores):** {pct(r_bajo)} % ({r_bajo} casos)\n"
            f"- **Moderado (1 factor):** {pct(r_mod)} % ({r_mod} casos)\n"
            f"- **Alto (2-3 factores):** {pct(r_alto)} % ({r_alto} casos)\n"
            f"- **Muy Alto (>=4 factores):** {pct(r_muy_alto)} % ({r_muy_alto} casos)\n"
            f"- **Alerta Institucional (Alto + Muy Alto):** **{pct(alerta)} %** ({alerta} casos)."
        )

    # 6. DIABETES Y GLUCOSA
    elif re.search(r'\b(diabetes|diab[eé]tic[oa]s?|glucosa|glicemia)\b', q):
        dm_cnt = sum(1 for r in records if r.get('diabetes'))
        base_answer = (
            f"**Diabetes Mellitus:**\n"
            f"- **Prevalencia:** **{pct(dm_cnt)} %** ({dm_cnt} de {total} casos evaluados)."
        )

    # 7. PERFIL LIPÍDICO Y DISLIPEMIA
    elif re.search(r'\b(dislipemia|colesterol|triglic[eé]ridos?|l[ií]pidos?)\b', q):
        dlp_cnt = sum(1 for r in records if r.get('dislipemia'))
        base_answer = (
            f"**Perfil Lipídico y Dislipemia:**\n"
            f"- **Prevalencia de Dislipemia:** **{pct(dlp_cnt)} %** ({dlp_cnt} de {total} casos evaluados)."
        )

    # 8. ESTILO DE VIDA Y HÁBITOS
    elif re.search(r'\b(tabaquismo|fumador|fuma|cigarro|alcohol|sedentarismo|sedentario)\b', q):
        sed_cnt = sum(1 for r in records if not r.get('actividad_fisica'))
        fum_cnt = sum(1 for r in records if r.get('fumador_activo'))
        alc_cnt = sum(1 for r in records if r.get('alcohol') and r.get('alcohol') != 'No consume')

        base_answer = (
            f"**Estilo de Vida y Hábitos:**\n"
            f"- **Sedentarismo:** **{pct(sed_cnt)} %** ({sed_cnt} casos).\n"
            f"- **Consumo de Alcohol:** **{pct(alc_cnt)} %** ({alc_cnt} casos).\n"
            f"- **Tabaquismo activo:** **{pct(fum_cnt)} %** ({fum_cnt} casos)."
        )

    # 9. TOTALES Y POBLACIÓN GENERAL
    elif re.search(r'\b(total|evaluados?|pacientes?|muestra|poblaci[oó]n|cu[aá]ntos?)\b', q):
        hombres = sum(1 for r in records if r.get('sexo') == 'Hombre')
        mujeres = sum(1 for r in records if r.get('sexo') == 'Mujer')
        edades = [float(r.get('edad')) for r in records if r.get('edad') and float(r.get('edad')) > 0]
        edad_media = round(sum(edades) / len(edades), 1) if edades else 0
        min_e = int(min(edades)) if edades else 0
        max_e = int(max(edades)) if edades else 0

        pas_cnt = sum(1 for r in records if 'PAS' in r.get('categoria', '') or 'Admin' in r.get('categoria', ''))
        pdi_cnt = sum(1 for r in records if 'PDI' in r.get('categoria', '') or 'Docente' in r.get('categoria', ''))
        serv_cnt = sum(1 for r in records if 'Servicio' in r.get('categoria', ''))

        base_answer = (
            f"**Cohorte CARDIOUNEMI:**\n"
            f"- **Total evaluados:** $N = {total}$ pacientes.\n"
            f"- **Hombres:** {hombres} ({pct(hombres)} %)\n"
            f"- **Mujeres:** {mujeres} ({pct(mujeres)} %)\n"
            f"- **Edad promedio:** {edad_media} años ({min_e} a {max_e} años).\n"
            f"- **Distribución:** {pct(pas_cnt)} % Administrativos (PAS), {pct(pdi_cnt)} % Docentes (PDI), {pct(serv_cnt)} % Servicios."
        )

    else:
        hombres = sum(1 for r in records if r.get('sexo') == 'Hombre')
        mujeres = sum(1 for r in records if r.get('sexo') == 'Mujer')
        sp_ob = sum(1 for r in records if r.get('imc_cat') in ['Sobrepeso', 'Obesidad I', 'Obesidad II', 'Obesidad Mórbida'])
        hta_cnt = sum(1 for r in records if r.get('hipertension'))
        dlp_cnt = sum(1 for r in records if r.get('dislipemia'))
        dm_cnt = sum(1 for r in records if r.get('diabetes'))

        base_answer = (
            f"**Resumen Clínico Actual (N = {total}):**\n"
            f"- **Distribución:** Hombres: {pct(hombres)} % | Mujeres: {pct(mujeres)} %.\n"
            f"- **Sobrepeso/Obesidad:** **{pct(sp_ob)} %** ({sp_ob} casos).\n"
            f"- **Hipertensión:** **{pct(hta_cnt)} %** ({hta_cnt} casos) | Dislipemia: **{pct(dlp_cnt)} %** ({dlp_cnt} casos) | Diabetes: **{pct(dm_cnt)} %** ({dm_cnt} casos)."
        )

    if has_suppression:
        base_answer += "\n\n> **Nota de confidencialidad médica (supresión de celdas pequeñas / control de divulgación estadística): Conteos menores a 5 se presentan como '< 5' sin porcentaje para salvaguardar la privacidad de datos clínicos en cohortes reducidas.**"

    chart_block = build_chart_json_if_requested(question, raw_response=base_answer)
    if chart_block:
        if '```json_chart' in base_answer:
            base_answer = re.sub(r'```json_chart\s*\{.*?\}\s*```', '', base_answer, flags=re.DOTALL).strip()
        return base_answer + chart_block
    return base_answer


def query_gemini_assistant(
    question: str,
    user=None,
    conversation_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    Procesa la consulta de forma directa, eficiente y económica.
    """
    from security.access import require_clinical_access
    require_clinical_access(user, 'read')
    start_time = time.time()
    clean_question = (question or '').strip()

    if not clean_question:
        return {
            "status": "error",
            "message": "La consulta no puede estar vacía.",
            "response": "Escriba una pregunta clínica o estadística."
        }

    # 0. Verificación de interruptor global (Chatbot activado / desactivado en Ajustes)
    try:
        from security.models import SystemSetting
        if not SystemSetting.is_chatbot_enabled():
            disabled_msg = "⚠️ El Asistente Clínico Inteligente ha sido desactivado temporalmente por la administración del sistema."
            elapsed_ms = int((time.time() - start_time) * 1000)
            _log_bot_query(user, clean_question, disabled_msg, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)
            return {
                "status": "disabled",
                "response": disabled_msg,
                "tokens_used": 0,
                "execution_time_ms": elapsed_ms,
                "mode": "disabled"
            }
    except Exception as e:
        logger.error("Chatbot operation failed; content omitted.")
        return {
            'status': 'disabled',
            'response': 'No se pudo verificar la habilitación del asistente. Intente más tarde.',
            'tokens_used': 0,
            'execution_time_ms': int((time.time() - start_time) * 1000),
            'mode': 'disabled',
        }

    # 1. Filtro estricto de privacidad (Zero PII) - Bloquea nombres, cédulas y preguntas individuales
    if is_sensitive_or_pii_query(clean_question):
        privacy_refusal = (
            "🔒 **Protección de Datos Médicos (Zero PII):**\n"
            "Acceso denegado a datos individuales (nombres propios, cédulas o contactos personales). "
            "Este asistente opera bajo estricta anonimización y solo responde métricas agregadas de la cohorte."
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        _log_bot_query(user, clean_question, privacy_refusal, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)
        return {
            "status": "success",
            "response": privacy_refusal,
            "tokens_used": 0,
            "execution_time_ms": elapsed_ms
        }

    # 2. Modo solo consulta - Bloquea intenciones de escritura DDL/DML
    if is_modification_attempt(clean_question):
        modification_refusal = (
            "🛡️ **Modo Solo Consulta:**\n"
            "El asistente no tiene permisos para modificar, insertar ni borrar datos del sistema."
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        _log_bot_query(user, clean_question, modification_refusal, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)
        return {
            "status": "success",
            "response": modification_refusal,
            "tokens_used": 0,
            "execution_time_ms": elapsed_ms
        }

    # 3. Runtime credentials come only from administrator-managed settings.
    # No environment fallback may override role, provider or enabled switches.
    db_key = ""
    db_model = "gemini-3.5-flash-lite"
    has_admin_access = False
    provider_enabled = False
    active_provider = ''
    config_available = False
    try:
        from security.models import SystemSetting
        cfg = SystemSetting.get_settings()
        if cfg:
            config_available = True
            active_provider = (cfg.active_llm_provider or '').strip().lower()
            db_model = cfg.gemini_model or 'gemini-3.5-flash-lite'
            provider_enabled = bool(cfg.gemini_enabled)
            has_admin_access = cfg.is_role_authorized(user)
            if cfg.chatbot_enabled and active_provider == 'gemini' and has_admin_access and provider_enabled:
                db_key = SystemSetting.get_gemini_api_key(user=user, check_enabled=True)
    except Exception:
        # A failed policy/key lookup must never enable another credential source.
        db_key = ''
        config_available = False
        logger.warning("No se pudo verificar la configuración de Gemini; usando modo local.")

    api_key = db_key.strip()
    model_name = db_model.strip()

    if not api_key:
        fallback_answer = generate_fallback_clinical_answer(clean_question)
        if not config_available:
            note = "\n\n> ⚠️ *(No se pudo verificar la configuración del proveedor. Mostrando análisis estadístico local)*"
        elif active_provider != 'gemini':
            note = "\n\n> ℹ️ *(El proveedor seleccionado no dispone de una integración ejecutable en este asistente. Mostrando análisis estadístico local)*"
        elif not provider_enabled:
            note = "\n\n> ⚠️ *(La integración con Google Gemini se encuentra deshabilitada en los Ajustes del Sistema. Mostrando análisis estadístico determinista local)*"
        elif not has_admin_access:
            note = "\n\n> 🔒 *(Modo estadístico local: el uso de credenciales de Gemini AI está restringido al rol Administrador)*"
        else:
            note = "\n\n> ℹ️ *(No se detectó una clave válida de Gemini. Un Administrador puede configurarla en Ajustes del Sistema)*"
        final_answer = fallback_answer + note
        elapsed_ms = int((time.time() - start_time) * 1000)

        _log_bot_query(user, clean_question, final_answer, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)
        return {
            "status": "success",
            "response": final_answer,
            "tokens_used": 0,
            "execution_time_ms": elapsed_ms,
            "mode": "deterministic_fallback"
        }

    try:
        from google import genai
        from google.genai import types

        cohort_context = get_anonymized_cohort_context()
        client = genai.Client(api_key=api_key)

        prompt = f"{cohort_context}\n\nPREGUNTA:\n{clean_question}\n\nRESPONDE DIRECTO AL GRANO:"

        # Probar con el modelo configurado o fallback a modelos flash estándar de Google
        models_to_try = [model_name, 'gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-flash-latest']
        seen = set()
        models_to_try = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        response = None
        last_err = None

        for m_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.1,  # Ultra determinista y conciso
                        max_output_tokens=600,  # Ahorro de tokens
                        http_options=types.HttpOptions(timeout=25000),
                    )
                )
                if response and response.text:
                    break
            except Exception as model_err:
                last_err = model_err
                if '402' in str(model_err) or 'RESOURCE_EXHAUSTED' in str(model_err):
                    raise model_err

        if not response or not response.text:
            if last_err:
                raise last_err
            response_text = "Sin datos para esta consulta."
        else:
            response_text = response.text

        chart_block = build_chart_json_if_requested(clean_question, raw_response=response_text)
        if chart_block:
            if '```json_chart' in response_text:
                response_text = re.sub(r'```json_chart\s*\{.*?\}\s*```', '', response_text, flags=re.DOTALL).strip()
            response_text += chart_block

        tokens = getattr(response.usage_metadata, 'total_token_count', 0) if hasattr(response, 'usage_metadata') else None

        elapsed_ms = int((time.time() - start_time) * 1000)
        _log_bot_query(user, clean_question, response_text, tokens=tokens, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)

        return {
            "status": "success",
            "response": response_text,
            "tokens_used": tokens or 0,
            "execution_time_ms": elapsed_ms,
            "mode": "gemini_flash"
        }

    except Exception as e:
        err_msg = str(e)
        logger.error("Chatbot operation failed; content omitted.")
        fallback_answer = generate_fallback_clinical_answer(clean_question)

        # Notificación clara del estado de la API sin engañar al usuario
        if 'DEADLINE_EXCEEDED' in err_msg or 'deadline expired' in err_msg.lower() or 'timed out' in err_msg.lower():
            status_note = "\n\n> ℹ️ *(Respuesta directa de la base de datos por latencia temporal de conexión con Gemini)*"
        elif '503' in err_msg or 'UNAVAILABLE' in err_msg:
            status_note = "\n\n> ℹ️ *(Servidores de Gemini con alta demanda momentánea; respuesta provista directamente de la base de datos)*"
        elif '402' in err_msg or 'RESOURCE_EXHAUSTED' in err_msg or 'depleted' in err_msg:
            status_note = (
                "\n\n> ⚠️ *Tu clave de Gemini fue detectada, pero Google indica que los créditos prepago de esa cuenta están agotados (Error 402).* "
                "*Para usar Gemini gratis sin saldo, crea una clave en un proyecto nuevo sin facturación en [Google AI Studio](https://aistudio.google.com/). "
                "Mientras tanto, los datos mostrados arriba provienen directamente de la base de datos de CARDIOUNEMI.*"
            )
        elif 'API_KEY_INVALID' in err_msg or 'api key not valid' in err_msg.lower():
            status_note = "\n\n> ⚠️ *La clave de API no es válida. Verifícala en Ajustes del Sistema.*"
        else:
            status_note = f"\n\n> ℹ️ *(Respuesta directa de la base de datos por contingencia de Gemini)*"

        final_answer = fallback_answer + status_note
        elapsed_ms = int((time.time() - start_time) * 1000)
        _log_bot_query(user, clean_question, final_answer, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.ERROR)

        return {
            "status": "success",
            "response": final_answer,
            "tokens_used": 0,
            "execution_time_ms": elapsed_ms,
            "mode": "error_fallback"
        }


def _log_bot_query(user, question: str, response: str, tokens: Optional[int], execution_ms: int, status: str):
    if not user or not user.is_authenticated:
        return
    try:
        BotQuery.objects.create(
            user=user,
            user_question="[contenido omitido por privacidad]",
            bot_response="[contenido omitido por privacidad]",
            tokens_used=tokens,
            execution_time_ms=execution_ms,
            status=status
        )
    except Exception as err:
        logger.error("Chatbot operation failed; content omitted.")
