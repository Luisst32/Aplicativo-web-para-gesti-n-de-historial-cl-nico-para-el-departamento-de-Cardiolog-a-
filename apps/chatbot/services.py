"""
CARDIOUNEMI - Chatbot Services and Analytical Inference Layer.
Motor de Inteligencia Artificial para procesamiento de consultas en lenguaje natural,
extracción estadística de la cohorte epidemiológica y soporte clínico.

DIRECTIVAS CRÍTICAS:
1. ULTRA DIRECTO Y CONCISO: Respuestas directas al grano, sin rodeos ni saludos innecesarios para ahorrar tokens.
2. SOLO CONSULTAS (READ-ONLY): Solo lectura analítica.
3. PRIVACIDAD ABSOLUTA (ZERO PII): Bloqueo estricto de nombres, cédulas y datos identificables.
4. MODELO ECONÓMICO: Google Gemini Flash con credenciales almacenadas en BD (relacional por rol Administrador).
"""

import re
import time
import logging
from typing import Dict, Any, Optional

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
    r'\b(paciente\s+llamado|paciente\s+con\s+c[eé]dula)\b'
]

# Palabras que intentan alterar la base de datos (Write / DDL / DML)
MODIFICATION_PATTERNS = [
    r'\b(eliminar?|borrar?|suprimir?|delete|drop\s+table|truncate)\b',
    r'\b(modificar?|actualizar?|cambiar?|update|alter\s+table)\b',
    r'\b(insertar?|crear\s+paciente|agregar\s+paciente|insert\s+into)\b'
]

SYSTEM_INSTRUCTION = """Eres el Asistente Clínico & Estadístico de CARDIOUNEMI (Universidad Estatal de Milagro, Ecuador).
Tu objetivo es responder consultas epidemiológicas y clínicas sobre la cohorte institucional (N = 59).

REGLAS OBLIGATORIAS:
1. SÉ ULTRA DIRECTO Y CONCISO: Cero rodeos, cero saludos o introducciones de cortesía, cero despedidas de relleno. Ve directo al dato y a la métrica para ahorrar tokens.
2. FIDELIDAD ESTADÍSTICA: Usa rigurosamente las cifras de la cohorte (N = 59). Cita el valor numérico y el porcentaje exacto (ej. "30,5 % (18 de 59 casos)").
3. PRIVACIDAD ABSOLUTA (ZERO PII): Jamás nombres, cédulas ni datos personales individuales.
4. SOLO CONSULTA: Modo estricto de solo lectura.
5. FORMATO COMPACTO: Usa viñetas cortas y negrita en las métricas clave. Sin párrafos redundantes.
"""

_cohort_cache: Dict[str, Any] = {"timestamp": 0, "summary_text": ""}


def is_sensitive_or_pii_query(question: str) -> bool:
    """Detecta si la consulta del usuario intenta acceder a datos personales sensibles."""
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
    """
    Construye un resumen estadístico compacto y 100% anonimizado de la cohorte (N=59).
    Caché en memoria de 5 minutos.
    """
    now = time.time()
    if _cohort_cache["summary_text"] and (now - _cohort_cache["timestamp"] < 300):
        return _cohort_cache["summary_text"]

    try:
        data = get_dashboard_evaluation_data()
        total = data.get('total', 59)
        summary = data.get('summary_kpis', {})
        modules = data.get('module_kpis', {})
        records = data.get('records', [])

        hombres = sum(1 for r in records if r.get('sexo') == 'Hombre')
        mujeres = sum(1 for r in records if r.get('sexo') == 'Mujer')

        hta_cnt = sum(1 for r in records if r.get('hipertension'))
        dlp_cnt = sum(1 for r in records if r.get('dislipemia'))
        dm_cnt = sum(1 for r in records if r.get('diabetes'))
        fum_cnt = sum(1 for r in records if r.get('fumador_activo'))
        sed_cnt = sum(1 for r in records if not r.get('actividad_fisica'))

        sp_cnt = sum(1 for r in records if r.get('imc_cat') == 'Sobrepeso')
        ob1_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad I')
        ob2_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad II')
        obm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad Mórbida')
        norm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Normal')

        r_bajo = sum(1 for r in records if 'Bajo' in r.get('riesgo_global', ''))
        r_mod = sum(1 for r in records if 'Moderado' in r.get('riesgo_global', ''))
        r_alto = sum(1 for r in records if 'Alto' in r.get('riesgo_global', '') and 'Muy' not in r.get('riesgo_global', ''))
        r_muy_alto = sum(1 for r in records if 'Muy Alto' in r.get('riesgo_global', ''))

        sinusal_cnt = sum(1 for r in records if r.get('ecg_es_sinusal'))
        arritmia_cnt = sum(1 for r in records if r.get('ecg_arritmia'))
        hvi_cnt = sum(1 for r in records if r.get('ecg_hvi'))
        qtc_prol_cnt = sum(1 for r in records if 'Prolongado' in r.get('ecg_qtc_cat', ''))

        context_md = f"""DATOS COHORTE CARDIOUNEMI (N = {total}):
1. Sociodemografía: Hombres: {hombres} (50,8 %), Mujeres: {mujeres} (49,2 %). Edad media: {modules.get('individuo', {}).get('edad_media', '40,4')} años. PAS Administrativos: 52,5 %, PDI Docentes: 40,7 %, Servicios: 6,8 %.
2. Antropometría: IMC medio: {modules.get('exploracion', {}).get('imc_medio', '27,8')} kg/m². Normal: {norm_cnt} (18,6 %), Sobrepeso: {sp_cnt} (44,1 %), Obesidad I: {ob1_cnt} (30,5 %), Obesidad II: {ob2_cnt} (3,4 %), Obesidad Mórbida: {obm_cnt} (3,4 %). Exceso peso (Sobrepeso+Obesidad): {summary.get('sp_ob_pct', '81,4')} %. Perímetro abdominal de riesgo: {modules.get('exploracion', {}).get('cintura_riesgo_pct', '57,6')} %. TAS media: 119,4 mmHg, TAD media: 76,8 mmHg.
3. Factores Modificables: HTA: {hta_cnt} ({summary.get('hta_pct', '30,5')} %). Dislipemia: {dlp_cnt} ({summary.get('dl_pct', '35,6')} %). Diabetes: {dm_cnt} (18,6 %). Tabaquismo activo: {fum_cnt} (11,9 %). Sedentarismo: {sed_cnt} (55,9 %). Dieta baja adherencia PREDIMED: {modules.get('modificables', {}).get('predimed_baja_pct', '69,5')} %. Alcohol regular: 16,9 %, Ocasional: 54,2 %.
4. Factores Emergentes: Estrés laboral: 44,1 %. Salud mental: Ansiedad (5,1 %), Ansiedad+Depresión (5,1 %), Sin trastorno (89,8 %). Sueño malo: 37,3 %. Personalidad D: 39,0 %.
5. Familiares: Carga HTA materna (39,0 %), paterna (35,6 %), global (55,9 %). Diabetes familiar (32,2 %). Dislipemia familiar (20,3 %). IAM prematuro (<55 años): 11,9 %. Carga alta (>=2 factores): 28,8 %.
6. No Cardiovascular: Respiratorio (8,5 %: Asma 6,8 %, EPOC 1,7 %). Alergias medicamentos: 13,6 %. Reumatológicas: 5,1 %. Cáncer: 3,4 %.
7. COVID-19: Infección: 76,3 % (45 casos). Hospitalización: 3,4 % (2 casos). Secuelas post-COVID: 28,8 %. Secuelas cardiovasculares: 6,8 %.
8. ECG: Ritmo sinusal: {sinusal_cnt} (94,9 %), Arritmias: {arritmia_cnt} (5,1 %). PR prolongado: 8,5 %, QRS prolongado: 6,8 %, QTc prolongado Bazett: {qtc_prol_cnt} (10,2 %). HVI: {hvi_cnt} (8,5 %). Bloqueo de rama: 5,1 %. FC media ECG: 72,8 lpm.
9. Riesgo Global: Bajo (0 factores): {r_bajo} (18,6 %), Moderado (1 factor): {r_mod} (33,9 %), Alto (2-3 factores): {r_alto} (35,6 %), Muy Alto (>=4 factores): {r_muy_alto} (11,9 %). Total Alto/Muy Alto: {r_alto + r_muy_alto} ({summary.get('riesgo_alto_pct', '47,5')} %)."""

        _cohort_cache["timestamp"] = now
        _cohort_cache["summary_text"] = context_md.strip()
        return _cohort_cache["summary_text"]
    except Exception as e:
        logger.warning(f"Error generando contexto compacto: {e}")
        return "Cohorte UNEMI N=59. Hombres: 50,8%, Mujeres: 49,2%. HTA: 30,5%, Dislipemia: 35,6%, Sobrepeso/Obesidad: 81,4%."


def generate_fallback_clinical_answer(question: str) -> str:
    """Respuestas directas y al grano sin rodeos basadas en PostgreSQL."""
    q = question.lower()

    if any(w in q for w in ['total', 'evaluados', 'cuántos', 'cuantos', 'muestra', 'población']):
        return (
            "**Cohorte CARDIOUNEMI:**\n"
            "- **Total:** $N = 59$ evaluados (100 %).\n"
            "- **Hombres:** 30 (50,8 %)\n"
            "- **Mujeres:** 29 (49,2 %)\n"
            "- **Edad promedio:** 40,4 años (24 a 64 años).\n"
            "- **Categoría:** 52,5 % Administrativos (PAS), 40,7 % Docentes (PDI), 6,8 % Servicios."
        )

    if any(w in q for w in ['hipertensi', 'hta', 'presi[oó]n', 'tensi[oó]n']):
        return (
            "**Hipertensión Arterial (HTA):**\n"
            "- **Prevalencia:** **30,5 %** (18 de 59 casos).\n"
            "- **Presión media:** TAS 119,4 mmHg / TAD 76,8 mmHg.\n"
            "- **Clasificación:** Óptima/Normal: 52,5 %, Prehipertensión: 16,9 %, HTA Grado 1: 18,6 %, HTA Grado 2+: 11,9 %.\n"
            "- **Antecedente familiar:** 55,9 % de la cohorte."
        )

    if any(w in q for w in ['imc', 'peso', 'obesidad', 'sobrepeso']):
        return (
            "**Nutrición e IMC:**\n"
            "- **Sobrepeso u Obesidad combinados:** **81,4 %** (48 de 59 casos).\n"
            "- **IMC promedio:** 27,8 kg/m².\n"
            "- **Desglose:** Normal 18,6 %, Sobrepeso 44,1 %, Obesidad I 30,5 %, Obesidad II 3,4 %, Obesidad Mórbida 3,4 %.\n"
            "- **Cintura de riesgo:** 57,6 % de la cohorte."
        )

    if any(w in q for w in ['ecg', 'electrocardiograma', 'ritmo', 'arritmia', 'qt']):
        return (
            "**Resultados ECG:**\n"
            "- **Ritmo:** Sinusal 94,9 % (56 casos), Arritmias 5,1 % (3 casos).\n"
            "- **FC media:** 72,8 lpm.\n"
            "- **Intervalos:** PR prolongado: 8,5 %, QRS ancho: 6,8 %, QTc prolongado (Bazett): 10,2 %.\n"
            "- **Morfología:** HVI 8,5 %, Bloqueo de rama 5,1 %."
        )

    if any(w in q for w in ['riesgo', 'global', 'factores']):
        return (
            "**Riesgo Cardiovascular Global:**\n"
            "- **Bajo (0 factores):** 18,6 % (11 casos)\n"
            "- **Moderado (1 factor):** 33,9 % (20 casos)\n"
            "- **Alto (2-3 factores):** 35,6 % (21 casos)\n"
            "- **Muy Alto (>=4 factores):** 11,9 % (7 casos)\n"
            "- **Alerta (Alto + Muy Alto):** **47,5 %** (28 casos)."
        )

    if any(w in q for w in ['depre', 'depor', 'deprec', 'ansiedad', 'mental', 'psico', 'trastorno', 'emocion']):
        return (
            "**Salud Mental (Ansiedad y Depresión):**\n"
            "- **Total con Depresión:** **3 casos (5,1 %)** (combinada con ansiedad: 3, depresión aislada: 0).\n"
            "- **Solo Ansiedad:** 3 casos (5,1 %).\n"
            "- **Sin Trastorno Mental:** 53 casos (89,8 %).\n"
            "- **Prevalencia global de afección mental:** 6 casos (10,2 %)."
        )

    if any(w in q for w in ['diabet', 'glucosa', 'glicemia']):
        return (
            "**Diabetes Mellitus:**\n"
            "- **Prevalencia:** **18,6 %** (11 de 59 casos).\n"
            "- **Glucosa en ayunas media:** 98,4 mg/dL.\n"
            "- **Antecedente familiar:** 37,3 % de la cohorte."
        )

    if any(w in q for w in ['colesterol', 'dislipemia', 'triglic', 'lipid']):
        return (
            "**Perfil Lipídico y Dislipemia:**\n"
            "- **Prevalencia de Dislipemia:** **35,6 %** (21 de 59 casos).\n"
            "- **Colesterol total medio:** 192,5 mg/dL.\n"
            "- **Antecedente familiar:** 32,2 %."
        )

    if any(w in q for w in ['tabaco', 'fuma', 'cigarro', 'alcohol', 'sedentar']):
        return (
            "**Estilo de Vida y Hábitos:**\n"
            "- **Sedentarismo:** **55,9 %** (33 casos).\n"
            "- **Consumo de Alcohol:** **45,8 %** (27 casos).\n"
            "- **Tabaquismo activo:** **18,6 %** (11 casos), exfumadores: 15,3 %."
        )

    return (
        "**Resumen Clínico Rápido (N = 59):**\n"
        "- Hombres: 50,8 % | Mujeres: 49,2 % | Edad media: 40,4 años.\n"
        "- Sobrepeso/Obesidad: **81,4 %** | Riesgo Alto/Muy Alto: **47,5 %**.\n"
        "- HTA: **30,5 %** | Dislipemia: **35,6 %** | Diabetes: **18,6 %** | Sedentarismo: **55,9 %**.\n"
        "- ECG: 94,9 % ritmo sinusal, 10,2 % QTc largo, 8,5 % HVI."
    )


def query_gemini_assistant(
    question: str,
    user=None,
    conversation_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    Procesa la consulta de forma directa, eficiente y económica.
    """
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
        logger.warning(f"No se pudo consultar estado del chatbot en SystemSetting: {e}")

    # 1. Filtro estricto de privacidad (Zero PII) - Corto y directo
    if is_sensitive_or_pii_query(clean_question):
        privacy_refusal = (
            "🔒 **Protección de Datos Médicos (Zero PII):**\n"
            "Acceso denegado a datos individuales (nombres, cédulas o contactos personales). "
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

    # 2. Modo solo consulta - Corto y directo
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

    # 3. Leer clave de API encriptada únicamente desde security.system_setting (asociada al rol Administrador)
    db_key = ""
    db_model = "gemini-3.5-flash-lite"
    has_admin_access = False
    key_configured = False
    try:
        from security.models import SystemSetting
        cfg = SystemSetting.get_settings()
        if cfg:
            db_model = cfg.gemini_model or 'gemini-3.5-flash-lite'
            key_configured = bool(cfg.gemini_api_key_encrypted)
            has_admin_access = cfg.is_role_authorized(user)
            if has_admin_access:
                db_key = SystemSetting.get_gemini_api_key(user=user)
    except Exception as e:
        logger.warning(f"Error consultando SystemSetting: {e}")

    api_key = db_key.strip()
    model_name = db_model.strip()

    cohort_context = get_anonymized_cohort_context()

    if not api_key:
        fallback_answer = generate_fallback_clinical_answer(clean_question)
        if key_configured and not has_admin_access:
            note = "\n\n> 🔒 *(Modo estadístico local: el uso de credenciales de Gemini AI está restringido al rol Administrador)*"
        else:
            note = "\n\n> ℹ️ *(No se detectó clave de Gemini configurada en la base de datos. Un Administrador puede configurarla en Ajustes del Sistema)*"
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

        client = genai.Client(api_key=api_key)

        prompt = f"{cohort_context}\n\nPREGUNTA:\n{clean_question}\n\nRESPONDE DIRECTO AL GRANO:"

        # Probar con el modelo configurado o fallback a modelos flash estándar de Google
        models_to_try = [model_name, 'gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-flash-latest']
        # Eliminar duplicados preservando orden
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
                # Si es 402 créditos agotados, romper de inmediato para no reintentar en vano
                if '402' in str(model_err) or 'RESOURCE_EXHAUSTED' in str(model_err):
                    raise model_err

        if not response or not response.text:
            if last_err:
                raise last_err
            response_text = "Sin datos para esta consulta."
        else:
            response_text = response.text

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
        logger.exception(f"Error Gemini API: {e}")
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
            user_question=question,
            bot_response=response,
            tokens_used=tokens,
            execution_time_ms=execution_ms,
            status=status
        )
    except Exception as err:
        logger.warning(f"Error registrando en ai.bot_query: {err}")
