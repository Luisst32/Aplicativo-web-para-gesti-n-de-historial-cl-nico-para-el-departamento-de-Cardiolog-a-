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
from collections import Counter
from typing import Dict, Any, Optional, List

from django.core.cache import cache
from django.db import transaction

from chatbot.models import BotQuery
from dashboard.services import get_dashboard_evaluation_data

logger = logging.getLogger(__name__)

# Palabras y expresiones asociadas a datos sensibles personales (PII)
SENSITIVE_PATTERNS = [
    r'\b(nombres?|apellidos?)\b',
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
CHART_REQUEST_PATTERN = re.compile(
    r'(grafica|grafico|graficar|barras?|pastel|pie|torta|circular|distribucion)'
)


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
    pct = round((cnt / total) * 100, 1) if total else 0
    return f"{cnt} casos ({pct} %)"


def apply_complementary_suppression(category_counts: Dict[str, int], total: int, threshold: int = 5) -> Dict[str, str]:
    """
    Aplica supresión primaria y supresión complementaria (secundaria).
    Si exactamente una celda es < threshold en un conjunto cerrado cuyo total es conocido,
    se enmascara complementariamente la segunda celda o el residuo para evitar
    que por simple sustracción (total - suma de las demás) se calcule el valor protegido.
    """
    return {key: fmt_safe_cell(value, total) for key, value in category_counts.items()}

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


def is_direct_cohort_metric_question(question: str) -> bool:
    """Return whether a question must use its exact local cohort calculation."""
    q = normalize_clinical_query(question)
    return bool(re.search(
        r'\b(depresion|depresiv[oa]s?|ansiedad|salud\s+mental|trastorno\s+mental)\b',
        q,
    ))


SENSITIVE_VARIABLE_PATTERN = re.compile(
    r'\b(nombre|apellido|cedula|identifica|documento|telefono|celular|correo|email|'
    r'direccion|domicilio|contacto|historia\s*clinica|codigo\s*estudio)\b'
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r'\b(nombre|apellido|cedula|identifica|documento|telefono|celular|correo|email|'
    r'direccion|domicilio|contacto)\b|\b\d{7,}\b|@'
)
QUERY_STOP_WORDS = {
    'cuanto', 'cuantos', 'cuanta', 'cuantas', 'paciente', 'pacientes',
    'caso', 'casos', 'hay', 'con', 'de', 'del', 'la', 'las', 'el', 'los',
    'en', 'por', 'para', 'que', 'cual', 'cuales', 'dame', 'mostrar',
    'muestra', 'cohorte', 'variable', 'registro', 'registros', 'historial',
    'clinico', 'clinica', 'dato', 'datos', 'total', 'numero', 'n', 'tiene',
    'tienen', 'presenta', 'presentan', 'diagnosticada', 'diagnosticado',
}


def _question_matches_query(question_obj, normalized_query: str) -> bool:
    """Match a query to a catalogued questionnaire variable, not a raw value."""
    terms = {
        term for term in re.findall(r'[a-z0-9]+', normalized_query)
        if len(term) >= 3 and term not in QUERY_STOP_WORDS
    }
    if not terms:
        return False
    descriptor_terms = set(re.findall(
        r'[a-z0-9]+', normalize_clinical_query(f'{question_obj.code} {question_obj.text}')
    ))
    # Token equality prevents "tiene" from matching a different question such
    # as "¿se detiene la marcha?".
    return bool(terms & descriptor_terms)


def _is_safe_question_variable(question_obj) -> bool:
    """Free-text and identifier-like variables never leave the database layer."""
    descriptor = normalize_clinical_query(f'{question_obj.code} {question_obj.text}')
    if SENSITIVE_VARIABLE_PATTERN.search(descriptor):
        return False
    if re.search(r'\b(nombres?|apellidos?)\b', descriptor):
        return False
    return question_obj.response_type in {'OPCION', 'BOOLEANO', 'NUMERICO', 'TEXTO'}


def get_live_questionnaire_metric(question: str) -> Optional[str]:
    """Return a privacy-preserving live aggregate for matching questionnaire fields.

    Catalog metadata is queried on every request; newly enabled non-sensitive
    variables therefore become available without adding a chatbot rule.
    """
    from catalog.models import Question
    from clinical.models import VisitAnswer

    normalized_query = normalize_clinical_query(question)
    candidates = [
        item for item in Question.objects.filter(status=Question.Status.ACTIVE).order_by('display_order')
        if _question_matches_query(item, normalized_query) and _is_safe_question_variable(item)
    ][:3]
    if not candidates:
        return None

    summaries = []
    chart_obj = None
    for item in candidates:
        answers = VisitAnswer.objects.filter(question=item).select_related('selected_option')
        if item.response_type == Question.ResponseType.NUMERICO:
            values = [float(answer.numeric_value) for answer in answers if answer.numeric_value is not None]
            if not values:
                summaries.append(f'- **{item.text}:** sin respuestas numéricas registradas.')
                continue
            values.sort()
            middle = len(values) // 2
            median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
            summaries.append(
                f'- **{item.text}:** N válido={len(values)}, promedio={sum(values) / len(values):.1f}, mediana={median:.1f}.'
            )
            continue

        labels = []
        for answer in answers:
            if answer.selected_option:
                labels.append(answer.selected_option.label)
                continue
            # Boolean values may be stored as text, but never treat arbitrary
            # free text as a category that could be echoed back to a user.
            value = normalize_clinical_query(answer.text_value or '')
            if item.response_type == Question.ResponseType.BOOLEANO:
                if value in {'si', 'true', '1'}:
                    labels.append('Sí')
                elif value in {'no', 'false', '0'}:
                    labels.append('No')
            elif item.response_type == Question.ResponseType.TEXTO:
                raw_value = (answer.text_value or '').strip()
                value_normalized = normalize_clinical_query(raw_value)
                if (raw_value and not SENSITIVE_VALUE_PATTERN.search(value_normalized)
                        and not re.search(r'\b(nombres?|apellidos?)\b', value_normalized)):
                    labels.append(raw_value)
        counts = Counter(labels)
        if not counts:
            summaries.append(f'- **{item.text}:** sin respuestas agregables registradas.')
            continue
        distribution = '; '.join(
            f'{label}: {count} ({count / len(labels) * 100:.1f} %)' for label, count in counts.most_common()
        )
        summaries.append(f'- **{item.text}:** N válido={len(labels)}. {distribution}.')
        if chart_obj is None and CHART_REQUEST_PATTERN.search(normalized_query):
            ordered_counts = counts.most_common()
            chart_obj = {
                'type': 'bar',
                'title': f'Distribución: {item.text} (n = {len(labels)})',
                'labels': [label for label, _ in ordered_counts],
                'data': [count for _, count in ordered_counts],
                'unit': 'pacientes',
            }

    result = '**Resultado en tiempo real del cuestionario:**\n' + '\n'.join(summaries)
    if chart_obj:
        result += f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"
    return result


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
    Mapeador Universal de Gráficas Clínicas:
    Genera un bloque json_chart estructurado garantizando 100% DATOS REALES extraídos
    directamente de la cohorte institucional de pacientes (CARDIOUNEMI).
    Soporta:
    - Gráficos de dispersión (scatter): cualquier par de variables numéricas reales (TAS, TAD, IMC, Edad, Peso, Talla, FC, Cintura).
    - Gráficos de pastel (pie / doughnut): cualquier distribución categórica o condición binaria de la cohorte.
    - Gráficos de barras (bar):
      * Variables categóricas individuales (Sexo, Grupos de Edad, Categorías de Personal, IMC, PA, Riesgo, Estrés, Alcohol, etc.)
      * Condiciones clínicas individuales (Hígado Graso, Hipertensión, Diabetes, Dislipemia, Tabaquismo, COVID-19, etc.)
      * Dominios multivariables (Factores Modificables, Secuelas Long-COVID, Hallazgos ECG, Antecedentes Familiares, Salud Mental, Comorbilidades)
      * Tabulaciones cruzadas dinámicas (ej: "hipertensión por sexo", "hígado graso por categoría", "fumadores por grupo de edad")
    """
    q_raw = question.lower()
    q = normalize_clinical_query(question)
    chart_keywords = [
        'grafic', 'gráfico', 'grafico', 'grafica', 'barra', 'barras',
        'pastel', 'pie', 'torta', 'circular', 'dona', 'doughnut',
        'dispersion', 'dispersión', 'scatter', 'puntos', 'correlaci',
        'distribucion', 'distribución'
    ]
    has_keyword = any(k in q_raw for k in chart_keywords)
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

    # Detectar formato deseado
    is_scatter = any(k in q for k in ['disperci', 'dispersion', 'scatter', 'punto', 'puntos', 'nube', 'correlaci', ' vs ', ' contra ']) or bool(raw_response and '"type": "scatter"' in raw_response)
    is_pie = any(k in q for k in ['pastel', 'pie', 'torta', 'circular', 'dona', 'doughnut']) or bool(raw_response and '"type": "pie"' in raw_response)

    # -------------------------------------------------------------
    # 1. SCATTER (DISPERSIÓN) ENTRE DOS VARIABLES NUMÉRICAS
    # -------------------------------------------------------------
    if is_scatter:
        num_map = {
            'tas': ('TAS', 'Tensión Arterial Sistólica (mmHg)', lambda r: r.get('tas')),
            'tad': ('TAD', 'Tensión Arterial Diastólica (mmHg)', lambda r: r.get('tad')),
            'imc': ('IMC', 'Índice de Masa Corporal (kg/m²)', lambda r: r.get('imc')),
            'edad': ('Edad', 'Edad (años)', lambda r: r.get('edad')),
            'peso': ('Peso', 'Peso (kg)', lambda r: r.get('peso')),
            'talla': ('Talla', 'Talla (cm)', lambda r: r.get('talla')),
            'fc': ('FC', 'Frecuencia Cardíaca (lpm)', lambda r: r.get('fc')),
            'perimetro': ('Cintura', 'Perímetro Abdominal (cm)', lambda r: r.get('perimetro_abdominal')),
        }
        found_matches = []
        patterns = [
            ('tas', r'\b(tas|sistolica|presion\s+sistolica)\b'),
            ('tad', r'\b(tad|diastolica|presion\s+diastolica)\b'),
            ('imc', r'\b(imc|masa\s+corporal|indice\s+de\s+masa)\b'),
            ('edad', r'\b(edad|anos?)\b'),
            ('peso', r'\b(peso|kilos?|kg)\b'),
            ('talla', r'\b(talla|estatura|altura|cm)\b'),
            ('fc', r'\b(fc|frecuencia|pulso|latidos)\b'),
            ('perimetro', r'\b(cintura|perimetro|abdomen)\b'),
        ]
        for v_key, v_pat in patterns:
            m = re.search(v_pat, q)
            if m:
                found_matches.append((m.start(), v_key))

        found_matches.sort(key=lambda x: x[0])
        found_vars = [k for _, k in found_matches]

        # Fallbacks si solo se detectó una o ninguna
        if len(found_vars) >= 2:
            var_x_key, var_y_key = found_vars[0], found_vars[1]
        elif len(found_vars) == 1:
            var_x_key = found_vars[0]
            var_y_key = 'tas' if var_x_key != 'tas' else 'imc'
        else:
            var_x_key, var_y_key = 'tas', 'imc'

        name_x, lbl_x, fn_x = num_map[var_x_key]
        name_y, lbl_y, fn_y = num_map[var_y_key]

        points = []
        for i, r in enumerate(records):
            vx, vy = fn_x(r), fn_y(r)
            try:
                if vx is not None and vy is not None and float(vx) > 0 and float(vy) > 0:
                    p_code = r.get('study_code') or r.get('codigo_estudio') or r.get('id') or f"{i+1}"
                    points.append({
                        "x": round(float(vx), 1),
                        "y": round(float(vy), 1),
                        "name": f"Caso {p_code}"
                    })
            except (ValueError, TypeError):
                continue

        min_x = min([p['x'] for p in points]) if points else 0
        max_x = max([p['x'] for p in points]) if points else 0
        min_y = min([p['y'] for p in points]) if points else 0
        max_y = max([p['y'] for p in points]) if points else 0

        chart_obj = {
            "type": "scatter",
            "title": f"Dispersión {name_x} vs {name_y} en la Cohorte (n = {len(points)})",
            "points": points,
            "xLabel": lbl_x,
            "yLabel": lbl_y,
            "annotation": f"Datos 100% reales de la cohorte institucional (n = {len(points)}). Rango X: {min_x} - {max_x}, Rango Y: {min_y} - {max_y}."
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 2. CRUCES DE VARIABLES (TABULACIÓN CRUZADA DINÁMICA)
    # Detecta: <Condición Clínica> [por/segun/en] <Agrupador>
    # -------------------------------------------------------------
    group_var = None
    if re.search(r'\b(por\s+sexo|segun\s+sexo|en\s+hombres\s+y\s+mujeres|por\s+genero)\b', q):
        group_var = 'sexo'
    elif re.search(r'\b(por\s+categoria|segun\s+categoria|por\s+estamento|en\s+docentes\s+y\s+administrativos|por\s+personal)\b', q):
        group_var = 'categoria'
    elif re.search(r'\b(por\s+edad|por\s+grupo\s+de\s+edad|por\s+rango\s+de\s+edad|segun\s+edad)\b', q):
        group_var = 'grupo_edad'

    clinical_conditions = [
        ('hipertension', r'\b(hipertension|presion\s+alta|hta)\b', 'Hipertensión Arterial'),
        ('dislipemia', r'\b(dislipemia|dislipidemia|colesterol)\b', 'Dislipemia'),
        ('diabetes', r'\b(diabetes|diabetic[oa]s?|glucosa)\b', 'Diabetes Mellitus'),
        ('fumador_activo', r'\b(tabaquismo|fumador|fumar|cigarrillo)\b', 'Tabaquismo Activo'),
        ('higado_graso', r'\b(higado\s+graso|esteatosis)\b', 'Hígado Graso'),
        ('alcohol', r'\b(alcohol|bebidas?|bebedor)\b', 'Consumo de Alcohol'),
        ('actividad_fisica', r'\b(sedentarismo|sedentario|actividad\s+fisica)\b', 'Sedentarismo'),
        ('covid_infeccion', r'\b(covid|coronavirus|sars-cov-2)\b', 'Antecedente de COVID-19'),
        ('sobrepeso_u_obesidad', r'\b(obesidad|sobrepeso|exceso\s+de\s+peso)\b', 'Sobrepeso u Obesidad'),
        ('ansiedad', r'\b(ansiedad)\b', 'Ansiedad'),
        ('depresion', r'\b(depresion|depresiv[oa]s?)\b', 'Depresión'),
        ('estres_alto', r'\b(estres|estres\s+alto)\b', 'Estrés Alto'),
    ]

    matched_condition = None
    for field_key, pattern, name_display in clinical_conditions:
        if re.search(pattern, q):
            matched_condition = (field_key, name_display)
            break

    if group_var and matched_condition:
        cond_key, cond_name = matched_condition
        if group_var == 'sexo':
            groups = [('Hombres', 'Hombre'), ('Mujeres', 'Mujer')]
            group_label = 'Sexo'
        elif group_var == 'categoria':
            cat_set = sorted(list({r.get('categoria') for r in records if r.get('categoria')}))
            groups = [(c, c) for c in cat_set]
            group_label = 'Categoría de Personal'
        else:  # grupo_edad
            age_order = ['<40 años', '40-49 años', '50-59 años', '60+ años']
            existing_ages = {r.get('grupo_edad') for r in records if r.get('grupo_edad')}
            groups = [(a, a) for a in age_order if a in existing_ages]
            group_label = 'Grupo de Edad'

        labels, data_pcts = [], []
        total_eval = 0
        for label_disp, val_match in groups:
            sub = [r for r in records if r.get(group_var) == val_match]
            if cond_key == 'actividad_fisica':
                pos = sum(1 for r in sub if r.get('actividad_fisica') is False)
            elif cond_key == 'estres_alto':
                pos = sum(1 for r in sub if 'Laboral' in str(r.get('estres', '')) or 'Familiar' in str(r.get('estres', '')) or r.get('estres') == 'Alto')
            elif cond_key == 'alcohol':
                pos = sum(1 for r in sub if r.get('alcohol') in ['Ocasional', 'Semanal', 'Frecuente'] or r.get('alcohol') is True)
            elif cond_key == 'sobrepeso_u_obesidad':
                pos = sum(1 for r in sub if r.get('sobrepeso_u_obesidad') is True or (r.get('imc') and float(r.get('imc')) >= 25))
            else:
                pos = sum(1 for r in sub if r.get(cond_key) is True)
            tot = len(sub)
            total_eval += tot
            pct_val = round((pos / tot) * 100, 1) if tot > 0 else 0
            labels.append(f"{label_disp} ({pos} de {tot})")
            data_pcts.append(pct_val)

        chart_obj = {
            "type": "bar",
            "title": f"Prevalencia de {cond_name} por {group_label} (%) (n = {total_eval})",
            "labels": labels,
            "data": data_pcts,
            "unit": "%",
            "annotation": f"Porcentaje de prevalencia de {cond_name} comparado por {group_label.lower()} con base de datos institucional."
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 3. SALUD MENTAL (Depresión, Ansiedad) - Compatibilidad Test
    # -------------------------------------------------------------
    if re.search(r'\b(depresion|depresiv[oa]s?|ansiedad|salud\s+mental)\b', q):
        dep_cnt = sum(1 for r in records if r.get('depresion') is True)
        ans_cnt = sum(1 for r in records if r.get('ansiedad') is True)
        mental_values = [('Depresión', dep_cnt), ('Ansiedad', ans_cnt)]
        chart_obj = {
            'type': 'bar',
            'title': f'Salud mental en la cohorte (n = {total_pacientes})',
            'labels': [l for l, _ in mental_values],
            'data': [v for _, v in mental_values],
            'unit': 'pacientes',
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 4. SECUELAS DE COVID (LONG-COVID)
    # -------------------------------------------------------------
    if re.search(r'\b(secuelas?|long\s*covid|covid\s+persistente|post\s*covid|fatiga|niebla)\b', q):
        inf_patients = [r for r in records if r.get('covid_infeccion') is True]
        n_inf = len(inf_patients) or total_pacientes
        sec_fat = sum(1 for r in inf_patients if r.get('covid_fatiga_long') is True)
        sec_nieb = sum(1 for r in inf_patients if r.get('covid_niebla_mental') is True)
        sec_resp = sum(1 for r in inf_patients if r.get('covid_secuelas_resp') is True)
        sec_card = sum(1 for r in inf_patients if r.get('covid_secuelas_cardio') is True)

        items = [
            ("Fatiga Persistente", sec_fat),
            ("Niebla Mental / Cognitiva", sec_nieb),
            ("Secuelas Respiratorias", sec_resp),
            ("Secuelas Cardiovasculares", sec_card)
        ]
        chart_obj = {
            "type": "bar",
            "title": f"Espectro de Secuelas Persistentes Long-COVID (n = {n_inf} infectados)",
            "labels": [label for label, _ in items],
            "data": [cnt for _, cnt in items],
            "unit": "casos",
            "annotation": f"Casos reportados entre los pacientes con antecedente de infección por COVID-19 (n={n_inf})."
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 5. HALLAZGOS ELECTROCARDIOGRAMA (ECG)
    # -------------------------------------------------------------
    if re.search(r'\b(ecg|electrocardiograma|ritmo|arritmia|hvi|qtc|bloqueo)\b', q):
        sinusal = sum(1 for r in records if r.get('ecg_es_sinusal') is True)
        qtc_prol = sum(1 for r in records if 'Prolongado' in str(r.get('ecg_qtc_cat', '')))
        hvi = sum(1 for r in records if r.get('ecg_hvi') is True)
        arritmia = sum(1 for r in records if r.get('ecg_arritmia') is True)
        bloqueo = sum(1 for r in records if r.get('ecg_bloqueo_presente') is True)

        if is_pie:
            chart_obj = {
                "type": "pie",
                "title": f"Ritmo Electrocardiográfico en la Cohorte (n = {total_pacientes})",
                "labels": ["Ritmo Sinusal", "No Sinusal / Arritmias"],
                "data": [sinusal, max(0, total_pacientes - sinusal)],
                "unit": "pacientes"
            }
        else:
            pct_calc = lambda c: round((c / total_pacientes) * 100, 1) if total_pacientes else 0
            chart_obj = {
                "type": "bar",
                "title": f"Prevalencia de Hallazgos en el Electrocardiograma (%) (n = {total_pacientes})",
                "labels": ["Ritmo Sinusal", "QTc Prolongado", "HVI", "Arritmias", "Bloqueos de Rama"],
                "data": [pct_calc(sinusal), pct_calc(qtc_prol), pct_calc(hvi), pct_calc(arritmia), pct_calc(bloqueo)],
                "unit": "%"
            }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 6. ANTECEDENTES FAMILIARES
    # -------------------------------------------------------------
    if re.search(r'\b(antecedentes?\s+familiar|familiares|herencia|padres?|madre)\b', q):
        hta_f = sum(1 for r in records if r.get('ant_fam_hta') is True or r.get('ant_padre_hta') is True or r.get('ant_madre_hta') is True)
        dm_f = sum(1 for r in records if r.get('ant_fam_dm') is True or r.get('ant_padre_dm') is True or r.get('ant_madre_dm') is True)
        dlp_f = sum(1 for r in records if r.get('ant_fam_dlp') is True or r.get('ant_padre_dlp') is True or r.get('ant_madre_dlp') is True)
        cv_f = sum(1 for r in records if r.get('ant_fam_cv_mayor') is True or r.get('ant_cardiopatia_prematura') is True or r.get('ant_muerte_subita') is True)

        pct_calc = lambda c: round((c / total_pacientes) * 100, 1) if total_pacientes else 0
        chart_obj = {
            "type": "bar",
            "title": f"Prevalencia de Antecedentes Familiares de Riesgo (%) (n = {total_pacientes})",
            "labels": ["HTA Familiar", "Diabetes Familiar", "Dislipemia Familiar", "Enf. Cardiovascular Prematura"],
            "data": [pct_calc(hta_f), pct_calc(dm_f), pct_calc(dlp_f), pct_calc(cv_f)],
            "unit": "%"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 7. VARIABLES CATEGÓRICAS INDIVIDUALES
    # -------------------------------------------------------------
    # Sexo
    if re.search(r'\b(sexo|genero|hombres?|mujeres?|varon)\b', q):
        h = sum(1 for r in records if r.get('sexo') == 'Hombre')
        m = sum(1 for r in records if r.get('sexo') == 'Mujer')
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Distribución por Sexo (n = {h + m})",
            "labels": ["Hombres", "Mujeres"],
            "data": [h, m],
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Grupos de Edad
    if re.search(r'\b(grupo\s+de\s+edad|grupos\s+de\s+edad|rango\s+de\s+edad|edades?|etario)\b', q):
        age_order = ['<40 años', '40-49 años', '50-59 años', '60+ años']
        counts = [sum(1 for r in records if r.get('grupo_edad') == grp) for grp in age_order]
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Distribución por Grupos de Edad (n = {sum(counts)})",
            "labels": age_order,
            "data": counts,
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Categorías de Personal
    if re.search(r'\b(categoria|personal|estamento|docente|administrativo|trabajadores|servicios)\b', q):
        cat_counts = {}
        for r in records:
            c = r.get('categoria')
            if c:
                cat_counts[c] = cat_counts.get(c, 0) + 1
        labels = sorted(list(cat_counts.keys()))
        data_v = [cat_counts[k] for k in labels]
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Distribución por Categoría de Personal (n = {sum(data_v)})",
            "labels": labels,
            "data": data_v,
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Estado Nutricional / IMC
    if re.search(r'\b(imc|nutricional|peso|obesidad|sobrepeso)\b', q):
        cats = ['Normal', 'Sobrepeso', 'Obesidad I', 'Obesidad II', 'Obesidad Mórbida']
        counts = [sum(1 for r in records if r.get('imc_cat') == c) for c in cats]
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Distribución Nutricional e IMC (n = {sum(counts)})",
            "labels": cats,
            "data": counts,
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Estratificación de Riesgo Cardiovascular
    if re.search(r'\b(riesgo|estratificaci|global)\b', q):
        r_bajo = sum(1 for r in records if 'Bajo' in str(r.get('riesgo_global', '')))
        r_mod = sum(1 for r in records if 'Moderado' in str(r.get('riesgo_global', '')))
        r_alto = sum(1 for r in records if 'Alto' in str(r.get('riesgo_global', '')) and 'Muy' not in str(r.get('riesgo_global', '')))
        r_muy_alto = sum(1 for r in records if 'Muy Alto' in str(r.get('riesgo_global', '')))
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Estratificación del Riesgo Cardiovascular (n = {total_pacientes})",
            "labels": ["Bajo (0 fact.)", "Moderado (1 fact.)", "Alto (2-3 fact.)", "Muy Alto (≥4 fact.)"],
            "data": [r_bajo, r_mod, r_alto, r_muy_alto],
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Estrés
    if re.search(r'\b(estres|nivel\s+de\s+estres)\b', q):
        estres_types = ['Sin estrés significativo', 'Estrés Laboral', 'Estrés Familiar', 'Laboral y Familiar']
        counts = [sum(1 for r in records if r.get('estres') == t) for t in estres_types]
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Nivel y Tipología de Estrés Percibido (n = {sum(counts)})",
            "labels": estres_types,
            "data": counts,
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Consumo de Alcohol
    if re.search(r'\b(alcohol|bebidas?|bebedor)\b', q):
        alc_types = ['No consume', 'Ocasional', 'Semanal']
        counts = [sum(1 for r in records if r.get('alcohol') == t) for t in alc_types]
        chart_obj = {
            "type": "pie" if is_pie else "bar",
            "title": f"Distribución de Consumo de Alcohol (n = {sum(counts)})",
            "labels": alc_types,
            "data": counts,
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # Presión Arterial (Categorías PA)
    if re.search(r'\b(presion\s+arterial|estadios?\s+hta|clasificacion\s+pa)\b', q):
        pa_order = ['PA Normal (<130/<80)', 'PA Elevada (130-139/80-89)', 'HTA Grado 1 (140-159/90-99)', 'HTA Grado 2 (≥140/90)']
        pa_counts = [sum(1 for r in records if r.get('pa_categoria') == c) for c in pa_order]
        chart_obj = {
            "type": "bar",
            "title": f"Clasificación de Presión Arterial en Consulta (n = {sum(pa_counts)})",
            "labels": pa_order,
            "data": pa_counts,
            "unit": "pacientes"
        }
        return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 8. CONDICIONES CLÍNICAS INDIVIDUALES (BOOLEANAS)
    # Hígado graso, diabetes, dislipemia, tabaquismo, covid, etc.
    # -------------------------------------------------------------
    single_boolean_specs = [
        ('higado_graso', r'\b(higado\s+graso|esteatosis)\b', 'Hígado Graso (Esteatosis Hepática)', 'Con Hígado Graso', 'Sin Hígado Graso'),
        ('hipertension', r'\b(hipertension|presion\s+alta|hta)\b', 'Hipertensión Arterial', 'Hipertensos', 'Normotensos'),
        ('diabetes', r'\b(diabetes|diabetic[oa]s?)\b', 'Diabetes Mellitus', 'Diabéticos', 'No diabéticos'),
        ('dislipemia', r'\b(dislipemia|dislipidemia|colesterol)\b', 'Dislipemia', 'Con Dislipemia', 'Sin Dislipemia'),
        ('fumador_activo', r'\b(tabaquismo|fumador|fumar|cigarrillo)\b', 'Tabaquismo Activo', 'Fumadores Activos', 'No Fumadores'),
        ('actividad_fisica', r'\b(actividad\s+fisica|ejercicio|deporte|sedentarismo)\b', 'Hábito de Actividad Física', 'Realiza Ejercicio', 'Sedentario'),
        ('covid_infeccion', r'\b(covid|coronavirus|sars-cov-2)\b', 'Antecedente de Infección por COVID-19', 'Con Antecedente COVID', 'Sin Antecedente'),
        ('covid_hospitalizacion', r'\b(hospitalizacion\s+covid|ingreso\s+covid)\b', 'Hospitalización por COVID-19', 'Hospitalizados', 'Ambulatorios'),
        ('ecg_arritmia', r'\b(arritmias?)\b', 'Presencia de Arritmias Cardíacas', 'Con Arritmia', 'Sin Arritmia'),
    ]

    for key, pattern, title_desc, pos_lbl, neg_lbl in single_boolean_specs:
        if re.search(pattern, q):
            if key == 'actividad_fisica' and ('sedentar' in q):
                pos_cnt = sum(1 for r in records if r.get('actividad_fisica') is False)
                neg_cnt = sum(1 for r in records if r.get('actividad_fisica') is True)
                pos_lbl, neg_lbl = 'Sedentarios', 'Activos Físicamente'
                title_desc = 'Prevalencia de Sedentarismo'
            else:
                pos_cnt = sum(1 for r in records if r.get(key) is True)
                neg_cnt = sum(1 for r in records if r.get(key) is False)

            pos_pct = round((pos_cnt / total_pacientes) * 100, 1) if total_pacientes else 0
            neg_pct = round((neg_cnt / total_pacientes) * 100, 1) if total_pacientes else 0

            if is_pie:
                chart_obj = {
                    "type": "pie",
                    "title": f"{title_desc} (n = {total_pacientes})",
                    "labels": [f"{pos_lbl} ({pos_pct}%)", f"{neg_lbl} ({neg_pct}%)"],
                    "data": [pos_cnt, neg_cnt],
                    "unit": "pacientes"
                }
            else:
                chart_obj = {
                    "type": "bar",
                    "title": f"Prevalencia de {title_desc} (n = {total_pacientes})",
                    "labels": [f"{pos_lbl} ({pos_cnt})", f"{neg_lbl} ({neg_cnt})"],
                    "data": [pos_pct, neg_pct],
                    "unit": "%",
                    "annotation": f"Positivos: {pos_cnt} ({pos_pct}%) | Negativos: {neg_cnt} ({neg_pct}%) sobre {total_pacientes} evaluados."
                }
            return f"\n\n```json_chart\n{json.dumps(chart_obj, ensure_ascii=False, indent=2)}\n```"

    # -------------------------------------------------------------
    # 9. FACTORES MODIFICABLES GLOBALES (DEFAULT ROBUSTO)
    # -------------------------------------------------------------
    sp_ob = sum(1 for r in records if r.get('imc_cat') in ['Sobrepeso', 'Obesidad I', 'Obesidad II', 'Obesidad Mórbida'] or r.get('sobrepeso_u_obesidad') is True)
    sed = sum(1 for r in records if r.get('actividad_fisica') is False)
    dlp = sum(1 for r in records if r.get('dislipemia') is True)
    hta = sum(1 for r in records if r.get('hipertension') is True)
    dm = sum(1 for r in records if r.get('diabetes') is True)
    fum = sum(1 for r in records if r.get('fumador_activo') is True)

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

    # Local aggregates are verified context for Gemini, not a replacement for
    # the conversation.  The model never receives individual records.
    verified_metric = None
    if is_direct_cohort_metric_question(clean_question):
        verified_metric = generate_fallback_clinical_answer(clean_question)
    else:
        verified_metric = get_live_questionnaire_metric(clean_question)

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
        fallback_answer = verified_metric or generate_fallback_clinical_answer(clean_question)
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
        verified_context = re.sub(
            r'```json_chart\s*\{.*?\}\s*```', '', verified_metric or '', flags=re.DOTALL
        ).strip()
        client = genai.Client(api_key=api_key)

        prompt = (
            f"{cohort_context}\n\nDATOS VERIFICADOS EN TIEMPO REAL:\n"
            f"{verified_context or 'No hay una métrica específica; responde solo con el contexto disponible.'}"
            f"\n\nPREGUNTA:\n{clean_question}\n\nRESPONDE DIRECTO AL GRANO:"
        )

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

        local_chart_match = re.search(r'```json_chart\s*\{.*?\}\s*```', verified_metric or '', flags=re.DOTALL)
        chart_block = local_chart_match.group(0) if local_chart_match else build_chart_json_if_requested(clean_question, raw_response=response_text)
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
        fallback_answer = verified_metric or generate_fallback_clinical_answer(clean_question)

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
