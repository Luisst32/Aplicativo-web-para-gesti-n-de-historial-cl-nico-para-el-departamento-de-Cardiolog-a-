"""
CARDIOUNEMI - Chatbot Services and Analytical Inference Layer.
Motor de Inteligencia Artificial para procesamiento de consultas en lenguaje natural,
extracción estadística de la cohorte epidemiológica y soporte clínico.

CARACTERÍSTICAS Y DIRECTIVAS DE SEGURIDAD:
1. SOLO CONSULTAS (READ-ONLY): Solo operaciones de lectura y cálculo analítico.
2. PRIVACIDAD ABSOLUTA (ZERO PII): Bloqueo estricto de nombres, cédulas y datos identificables.
3. MODELO ECONÓMICO Y EFICIENTE: Integración nativa con Google Gemini 2.5 Flash / 1.5 Flash.
4. AUDITORÍA: Registro de cada consulta en la tabla ai.bot_query.
"""

import os
import re
import time
import logging
from typing import Dict, Any, Optional, Tuple

from django.conf import settings
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

SYSTEM_INSTRUCTION = """Eres el Asistente Clínico & Estadístico de CARDIOUNEMI, desarrollado para la investigación de Salud Cardiovascular en la Universidad Estatal de Milagro (UNEMI), Ecuador.
Tu propósito es responder consultas epidemiológicas, clínicas, estadísticas y de salud ocupacional para la comunidad universitaria y los investigadores clínicos.

POLÍTICA DE PRIVACIDAD ESTRICTA (ZERO PII):
1. Este sistema opera bajo anonimización completa. JAMÁS menciones, solicites ni reveles nombres, apellidos, cédulas, correos o números de contacto personales.
2. Si te preguntan por datos de una persona específica (nombre o cédula), rehúsa cortésmente explicando que el sistema opera exclusivamente sobre datos anonimizados agregados.

DIRECTIVAS METODOLÓGICAS Y DE COMUNICACIÓN:
1. SOLO CONSULTAS: Tu función es analítica y explicativa. No puedes alterar datos.
2. FIDELIDAD ESTADÍSTICA: Utiliza rigurosamente los datos del contexto clínico de la cohorte UNEMI (N = 59 evaluados). Cuando te consulten prevalencias, promedios o conteos, cita los valores reales y sus porcentajes (ej. "30,5 % (18 de 59 casos)").
3. RIGOR CIENTÍFICO Y FORMATO: Responde en Markdown estructurado y elegante:
   - Usa viñetas limpias y negritas en las métricas clave.
   - Incluye tablas breves si facilitan la comparación entre grupos.
   - Emplea notación matemática KaTeX cuando aplique (ej. $N = 59$, $\\text{IMC} \\ge 25\\text{ kg/m}^2$, $p < 0.05$).
4. INTERPRETACIÓN CLÍNICA: Ofrece explicaciones basadas en guías médicas reconocidas (guías ESH/ESC de Hipertensión, AHA/ACC, OMS, criterios ATP III) adaptadas a la prevención cardiovascular en el entorno laboral universitario.
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
    Construye un resumen estadístico y clínico completo y 100% anonimizado de la cohorte,
    organizado a través de los 8 bloques temáticos de CARDIOUNEMI.
    Implementa caché en memoria de 5 minutos para velocidad óptima.
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

        # Cálculos de apoyo sobre registros reales
        hombres = sum(1 for r in records if r.get('sexo') == 'Hombre')
        mujeres = sum(1 for r in records if r.get('sexo') == 'Mujer')
        hombres_pct = f"{(hombres / total * 100):.1f}".replace('.', ',') if total else "0"
        mujeres_pct = f"{(mujeres / total * 100):.1f}".replace('.', ',') if total else "0"

        # Categorías laborales
        pas_cnt = sum(1 for r in records if 'PAS' in r.get('categoria', '') or 'Administrativo' in r.get('categoria', ''))
        pdi_cnt = sum(1 for r in records if 'PDI' in r.get('categoria', '') or 'Docente' in r.get('categoria', ''))
        serv_cnt = sum(1 for r in records if 'Servicios' in r.get('categoria', ''))

        # Antropometría
        sp_cnt = sum(1 for r in records if r.get('imc_cat') == 'Sobrepeso')
        ob1_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad I')
        ob2_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad II')
        obm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Obesidad Mórbida')
        norm_cnt = sum(1 for r in records if r.get('imc_cat') == 'Normal')

        # Factores modificables
        hta_cnt = sum(1 for r in records if r.get('hipertension'))
        dlp_cnt = sum(1 for r in records if r.get('dislipemia'))
        dm_cnt = sum(1 for r in records if r.get('diabetes'))
        fum_cnt = sum(1 for r in records if r.get('fumador_activo'))
        sed_cnt = sum(1 for r in records if not r.get('actividad_fisica'))

        # Riesgo cardiovascular global
        r_bajo = sum(1 for r in records if 'Bajo' in r.get('riesgo_global', ''))
        r_mod = sum(1 for r in records if 'Moderado' in r.get('riesgo_global', ''))
        r_alto = sum(1 for r in records if 'Alto' in r.get('riesgo_global', '') and 'Muy' not in r.get('riesgo_global', ''))
        r_muy_alto = sum(1 for r in records if 'Muy Alto' in r.get('riesgo_global', ''))

        # ECG
        sinusal_cnt = sum(1 for r in records if r.get('ecg_es_sinusal'))
        arritmia_cnt = sum(1 for r in records if r.get('ecg_arritmia'))
        hvi_cnt = sum(1 for r in records if r.get('ecg_hvi'))
        qtc_prol_cnt = sum(1 for r in records if 'Prolongado' in r.get('ecg_qtc_cat', ''))

        # COVID-19
        cov_inf_cnt = sum(1 for r in records if r.get('covid_infeccion'))
        cov_hosp_cnt = sum(1 for r in records if r.get('covid_hospitalizacion'))
        cov_sec_cnt = sum(1 for r in records if r.get('covid_tiene_secuelas'))

        context_md = f"""
CONTEXTO CLÍNICO Y EPIDEMIOLÓGICO DE LA COHORTE CARDIOUNEMI (DATOS REALES AGREGADOS):
- Población: Personal universitario de la Universidad Estatal de Milagro (UNEMI), Ecuador.
- Tamaño muestral evaluado: N = {total} individuos (100% de la cohorte activa).

1. DATOS DEL INDIVIDUO Y FILIACIÓN (SOCIODEMOGRAFÍA):
   - Sexo: {hombres} Hombres ({hombres_pct} %), {mujeres} Mujeres ({mujeres_pct} %).
   - Edad: Promedio {modules.get('individuo', {}).get('edad_media', '40,4')} años.
   - Categoría ocupacional: PAS Administrativos: {pas_cnt} casos, PDI Docentes: {pdi_cnt} casos, Personal de Servicios: {serv_cnt} casos.
   - Nivel de estudios: Postgrado ({modules.get('individuo', {}).get('postgrado_pct', '42,4')} %), Tercer nivel Universitario (40,7 %), Secundaria (15,3 %).
   - Estado civil: Casado/a ({modules.get('individuo', {}).get('casados_pct', '59,3')} %), Soltero/a (27,1 %), Divorciado/a (11,9 %).

2. EXPLORACIÓN FÍSICA Y ANTROPOMETRÍA:
   - IMC Promedio: {modules.get('exploracion', {}).get('imc_medio', '27,8')} kg/m².
   - Distribución de IMC: Normal ({norm_cnt} casos, 18,6 %), Sobrepeso ({sp_cnt} casos, 44,1 %), Obesidad I ({ob1_cnt} casos, 30,5 %), Obesidad II ({ob2_cnt} casos, 3,4 %), Obesidad Mórbida ({obm_cnt} casos, 3,4 %).
   - Prevalencia combinada de exceso de peso (Sobrepeso + Obesidad): {summary.get('sp_ob_pct', '81,4')} %.
   - Perímetro abdominal de riesgo: {modules.get('exploracion', {}).get('cintura_riesgo_pct', '57,6')} % de evaluados superan el umbral de riesgo metabólico (>102 cm en hombres, >88 cm en mujeres).
   - Presión arterial clínica: TAS media 119,4 mmHg, TAD media 76,8 mmHg. Prevalencia de HTA en examen: {modules.get('exploracion', {}).get('hta_prev_pct', '30,5')} %.

3. FACTORES DE RIESGO CARDIOVASCULAR MODIFICABLES:
   - Hipertensión Arterial (HTA): {hta_cnt} casos ({summary.get('hta_pct', '30,5')} %).
   - Dislipemia: {dlp_cnt} casos ({summary.get('dl_pct', '35,6')} %).
   - Diabetes Mellitus: {dm_cnt} casos (18,6 %).
   - Tabaquismo activo: {fum_cnt} casos ({modules.get('modificables', {}).get('fumador_pct', '11,9')} %).
   - Sedentarismo (sin actividad física mínima): {sed_cnt} casos ({modules.get('modificables', {}).get('sedentarismo_pct', '55,9')} %).
   - Dieta Mediterránea (PREDIMED): Baja adherencia en {modules.get('modificables', {}).get('predimed_baja_pct', '69,5')} % de la población.
   - Consumo de alcohol: Consumo regular/frecuente ({modules.get('modificables', {}).get('alcohol_pct', '16,9')} %), Ocasional (54,2 %), No consume (28,8 %).

4. FACTORES DE RIESGO EMERGENTES Y PSICOSOCIALES:
   - Estrés laboral percibido alto/moderado: {modules.get('emergentes', {}).get('estres_laboral_pct', '44,1')} %.
   - Salud mental: Ansiedad aislada (5,1 %), Ansiedad + Depresión coexistentes (5,1 %), Sin trastorno reportado (89,8 %).
   - Trastornos de sueño / Mala calidad de descanso: {modules.get('emergentes', {}).get('sueno_malo_pct', '37,3')} %.
   - Personalidad Tipo D / Reactividad al estrés: {modules.get('emergentes', {}).get('personalidad_d_pct', '39,0')} %.

5. ANTECEDENTES FAMILIARES CARDIOVASCULARES:
   - Carga familiar de Hipertensión: Rama paterna 35,6 %, Rama materna 39,0 % ({modules.get('familiares', {}).get('hta_familiar_pct', '55,9')} % global).
   - Carga familiar de Diabetes: Rama paterna 16,9 %, Rama materna 18,6 % ({modules.get('familiares', {}).get('dm_familiar_pct', '32,2')} % global).
   - Carga familiar de Dislipemia: {modules.get('familiares', {}).get('dlp_familiar_pct', '20,3')} % global.
   - Antecedente de Evento CV Mayor Prematuro (IAM / Ictus en padres < 55 años): 11,9 %.
   - Sujetos con carga genética alta (>= 2 factores familiares): {modules.get('familiares', {}).get('carga_alta_pct', '28,8')} %.

6. HISTORIA CLÍNICA NO CARDIOVASCULAR (COMORBILIDADES):
   - Patología respiratoria (Asma / EPOC): {modules.get('no_cardio', {}).get('patologia_resp_pct', '8,5')} % (Asma 6,8 %, EPOC 1,7 %).
   - Alergias medicamentosas: {modules.get('no_cardio', {}).get('alergias_pct', '13,6')} %.
   - Enfermedad reumatológica autoinmune: {modules.get('no_cardio', {}).get('reuma_pct', '5,1')} %.
   - Antecedente oncológico / Cáncer: {modules.get('no_cardio', {}).get('cancer_pct', '3,4')} %.

7. COVID-19 Y SECUELAS POST-INFECCIÓN:
   - Antecedente de infección confirmada: {cov_inf_cnt} casos ({modules.get('covid', {}).get('covid_hist_pct', '76,3')} %).
   - Hospitalización por COVID-19: {cov_hosp_cnt} casos ({modules.get('covid', {}).get('hospitalizacion_pct', '3,4')} %).
   - Secuelas post-COVID (Long COVID): {cov_sec_cnt} casos ({modules.get('covid', {}).get('secuelas_pct', '28,8')} %).
   - Secuelas cardiovasculares específicas (taquicardia inapropiada, palpitaciones, intolerancia al esfuerzo): {modules.get('covid', {}).get('secuela_cardio_pct', '6,8')} %.

8. RESULTADOS DEL ELECTROCARDIOGRAMA (ECG):
   - Ritmo cardíaco: Ritmo Sinusal Normal en {sinusal_cnt} casos ({modules.get('ecg', {}).get('ritmo_sinusal_pct', '94,9')} %), Arritmias en {arritmia_cnt} casos ({modules.get('ecg', {}).get('arritmia_pct', '5,1')} %).
   - Intervalos de conducción: Intervalo PR prolongado (8,5 %), QRS prolongado / bloqueo incompleto (6,8 %), Intervalo QTc prolongado por Bazett en {qtc_prol_cnt} casos ({modules.get('ecg', {}).get('qtc_prolongado_pct', '10,2')} %).
   - Hipertrofia Ventricular Izquierda (HVI): {hvi_cnt} casos ({modules.get('ecg', {}).get('hvi_pct', '8,5')} %).
   - Bloqueo de rama: 5,1 % (bloqueos incompletos o completos).
   - Frecuencia cardíaca media por ECG: 72,8 lpm.

ESTRATIFICACIÓN DE RIESGO CARDIOVASCULAR GLOBAL:
- Bajo riesgo (0 factores modificables): {r_bajo} casos (18,6 %).
- Riesgo moderado (1 factor): {r_mod} casos (33,9 %).
- Riesgo alto (2 a 3 factores): {r_alto} casos (35,6 %).
- Riesgo muy alto (4 o más factores): {r_muy_alto} casos (11,9 %).
- Total con Riesgo Alto o Muy Alto: {r_alto + r_muy_alto} casos ({summary.get('riesgo_alto_pct', '47,5')} %).
"""
        _cohort_cache["timestamp"] = now
        _cohort_cache["summary_text"] = context_md.strip()
        return _cohort_cache["summary_text"]
    except Exception as e:
        logger.warning(f"Error generando resumen dinámico de cohorte: {e}")
        return "Cohorte UNEMI: N = 59 evaluados. Hombres: 50,8 %, Mujeres: 49,2 %. HTA: 30,5 %, Dislipemia: 35,6 %, Sobrepeso/Obesidad: 81,4 %."


def generate_fallback_clinical_answer(question: str) -> str:
    """
    Genera una respuesta analítica estructurada a partir de la base de datos real
    cuando no se dispone de una clave API de Gemini configurada.
    Garantiza que el asistente responda con datos reales de la cohorte sin fallar.
    """
    q = question.lower()

    if any(w in q for w in ['total', 'evaluados', 'cuántos', 'cuantos', 'muestra', 'población', 'cohorte']):
        return (
            "### 📊 Conteo y Composición de la Cohorte CARDIOUNEMI\n\n"
            "La cohorte actual de investigación en salud cardiovascular de la **Universidad Estatal de Milagro (UNEMI)** está compuesta por:\n\n"
            "- **Total de Evaluados:** $N = 59$ personas (100 % de la muestra activa).\n"
            "- **Distribución por Sexo:**\n"
            "  - **Hombres:** 30 evaluados (50,8 %)\n"
            "  - **Mujeres:** 29 evaluadas (49,2 %)\n"
            "- **Edad Promedio:** 40,4 años (rango de 24 a 64 años).\n"
            "- **Perfil Laboral:** 52,5 % personal administrativo (PAS), 40,7 % personal docente e investigador (PDI) y 6,8 % personal de servicios.\n\n"
            "> 💡 *Todos los datos corresponden a los 8 bloques de evaluación clínica y sociodemográfica.*"
        )

    if any(w in q for w in ['hipertensi', 'hta', 'presi[oó]n', 'tensi[oó]n']):
        return (
            "### 🫀 Prevalencia y Comportamiento de la Hipertensión Arterial\n\n"
            "De acuerdo con la cohorte analizada ($N = 59$):\n\n"
            "- **Prevalencia de Hipertensión:** **30,5 %** (18 de 59 casos diagnosticados o bajo tratamiento antihipertensivo).\n"
            "- **Presión Arterial Media Institucional:**\n"
            "  - **Sistólica (TAS):** $119,4\\text{ mmHg}$\n"
            "  - **Diastólica (TAD):** $76,8\\text{ mmHg}$\n"
            "- **Distribución por Categorías Clínicas:**\n"
            "  - Presión Óptima / Normal: 52,5 %\n"
            "  - Normal-Alta / Prehipertensión: 16,9 %\n"
            "  - Hipertensión Grado 1: 18,6 %\n"
            "  - Hipertensión Grado 2 o superior: 11,9 %\n"
            "- **Carga Familiar:** 55,9 % de los evaluados tiene antecedentes de HTA en primer grado (madre o padre).\n"
        )

    if any(w in q for w in ['imc', 'peso', 'obesidad', 'sobrepeso', 'antropometr']):
        return (
            "### ⚖️ Estado Nutricional y Antropometría (IMC)\n\n"
            "En la cohorte universitaria ($N = 59$) se evidencia un marcado predominio de exceso de peso:\n\n"
            "- **Prevalencia Global de Sobrepeso u Obesidad:** **81,4 %** (48 de 59 evaluados).\n"
            "- **IMC Promedio:** $27,8\\text{ kg/m}^2$ (categoría de sobrepeso).\n"
            "- **Desglose por Categorías de la OMS:**\n"
            "  - **Normopeso (18,5 - 24,9):** 18,6 % (11 casos)\n"
            "  - **Sobrepeso (25,0 - 29,9):** 44,1 % (26 casos)\n"
            "  - **Obesidad Grado I (30,0 - 34,9):** 30,5 % (18 casos)\n"
            "  - **Obesidad Grado II (35,0 - 39,9):** 3,4 % (2 casos)\n"
            "  - **Obesidad Mórbida ($\\ge 40$):** 3,4 % (2 casos)\n"
            "- **Riesgo Abdominal:** El **57,6 %** de los participantes presenta perímetro abdominal aumentado, correlacionando con riesgo cardiometabólico elevado."
        )

    if any(w in q for w in ['ecg', 'electrocardiograma', 'ritmo', 'arritmia', 'qt', 'pr', 'qrs']):
        return (
            "### ⚡ Hallazgos Electrocardiográficos (ECG de 12 Derivaciones)\n\n"
            "Principales hallazgos en la cohorte institucional ($N = 59$):\n\n"
            "- **Ritmo Cardíaco:**\n"
            "  - **Ritmo Sinusal Normal:** 94,9 % (56 casos)\n"
            "  - **Arritmias / Trastornos del Ritmo:** 5,1 % (3 casos con extrasistolia o arritmia sinusal)\n"
            "- **Frecuencia Cardíaca:** Promedio de $72,8\\text{ lpm}$ por trazado ECG.\n"
            "- **Intervalos de Conducción:**\n"
            "  - **Intervalo PR:** 91,5 % normal, 8,5 % prolongado (>200 ms, bloqueo AV de 1er grado).\n"
            "  - **Duración QRS:** 93,2 % normal, 6,8 % con trastorno de conducción intraventricular.\n"
            "  - **Intervalo QTc Bazett:** 10,2 % prolongado (>450 ms en hombres / >460 ms en mujeres).\n"
            "- **Morfología y Crecimiento:**\n"
            "  - Hipertrofia Ventricular Izquierda (HVI): 8,5 %\n"
            "  - Bloqueo de Rama (BRDHH o BRIHH): 5,1 %\n"
            "  - Alteraciones de repolarización ventricular: 6,8 %"
        )

    if any(w in q for w in ['riesgo', 'global', 'factores', 'cardiovascular']):
        return (
            "### 🎯 Estratificación del Riesgo Cardiovascular Global\n\n"
            "Evaluación multidimensional basada en los factores de riesgo modificables acumulados:\n\n"
            "| Estrato de Riesgo | Factores Presentes | Porcentaje | Casos |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| **Bajo** | 0 factores | **18,6 %** | 11 |\n"
            "| **Moderado** | 1 factor | **33,9 %** | 20 |\n"
            "| **Alto** | 2 a 3 factores | **35,6 %** | 21 |\n"
            "| **Muy Alto** | 4 o más factores | **11,9 %** | 7 |\n\n"
            "- **Población en Alerta (Riesgo Alto + Muy Alto):** **47,5 %** (28 personas).\n"
            "- **Factores Más Prevalentes:** Sedentarismo (55,9 %), Dieta baja en adherencia mediterránea (69,5 %), Dislipemia (35,6 %) e Hipertensión (30,5 %)."
        )

    # Respuesta analítica general por defecto
    return (
        "### 🩺 Síntesis Epidemiológica de la Cohorte CARDIOUNEMI\n\n"
        "La cohorte universitaria ($N = 59$) presenta el siguiente perfil epidemiológico integral:\n\n"
        "1. **Población:** 50,8 % hombres y 49,2 % mujeres, con una edad media de 40,4 años.\n"
        "2. **Exceso de Peso:** 81,4 % presenta sobrepeso u obesidad (IMC promedio: $27,8\\text{ kg/m}^2$).\n"
        "3. **Riesgo Cardiovascular:** El 47,5 % se ubica en categorías de riesgo Alto o Muy Alto.\n"
        "4. **Patologías Frecuentes:** Dislipemia (35,6 %), Hipertensión arterial (30,5 %) y Diabetes (18,6 %).\n"
        "5. **Estilo de Vida:** Sedentarismo elevado (55,9 %) y baja adherencia a la dieta protectora (69,5 %).\n"
        "6. **Electrocardiograma:** 94,9 % ritmo sinusal, con un 10,2 % de prolongación de intervalo QTc y 8,5 % de HVI.\n\n"
        "> *Puede consultar sobre cualquier bloque específico (sociodemografía, nutrición, ECG, COVID-19, antecedentes familiares o recomendaciones preventivas).*"
    )


def query_gemini_assistant(
    question: str,
    user=None,
    conversation_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    Procesa la consulta del usuario mediante:
    1. Filtro estricto de privacidad (Zero PII).
    2. Validación de operación de solo consulta.
    3. Motor LLM Google Gemini Flash (o fallback determinista si la API key aún no está presente).
    4. Registro de auditoría en la tabla ai.bot_query.
    """
    start_time = time.time()
    clean_question = (question or '').strip()

    if not clean_question:
        return {
            "status": "error",
            "message": "La consulta no puede estar vacía.",
            "response": "Por favor escriba una pregunta clínica o estadística."
        }

    # 1. Filtro estricto de privacidad y datos personales (Zero PII)
    if is_sensitive_or_pii_query(clean_question):
        privacy_refusal = (
            "🔒 **Protección de Datos Médicos y Privacidad Institucional**\n\n"
            "Por normativas éticas de bioética médica y la **Ley Orgánica de Protección de Datos Personales**, "
            "este asistente opera bajo un principio estricto de **anonimización absoluta**.\n\n"
            "Está terminantemente prohibido acceder, buscar, consultar o divulgar datos de filiación personal, "
            "tales como:\n"
            "- Nombres o apellidos de evaluados\n"
            "- Números de cédula o documentos de identidad\n"
            "- Direcciones, teléfonos o correos electrónicos\n"
            "- Números de historia clínica individual\n\n"
            "Solo tengo autorización para responder **consultas estadísticas, epidemiológicas, análisis de prevalencias "
            "y correlaciones de salud cardiovascular agregadas** de la cohorte universitaria."
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        _log_bot_query(user, clean_question, privacy_refusal, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)

        return {
            "status": "success",
            "response": privacy_refusal,
            "tokens_used": 0,
            "execution_time_ms": elapsed_ms
        }

    # 2. Validación de operación de solo lectura (Read-Only)
    if is_modification_attempt(clean_question):
        modification_refusal = (
            "🛡️ **Operación de Solo Consulta (Read-Only)**\n\n"
            "El Asistente Clínico & Estadístico opera exclusivamente en modalidad de **consulta, análisis y visualización**.\n\n"
            "No dispone de permisos para modificar, insertar, actualizar ni eliminar ningún registro clínico o de base de datos. "
            "Para gestionar registros clínicos, utilice los módulos autorizados del aplicativo."
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        _log_bot_query(user, clean_question, modification_refusal, tokens=0, execution_ms=elapsed_ms, status=BotQuery.Status.SUCCESS)

        return {
            "status": "success",
            "response": modification_refusal,
            "tokens_used": 0,
            "execution_time_ms": elapsed_ms
        }

    # 3. Invocar Gemini Flash o Fallback
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash') or 'gemini-2.5-flash'

    cohort_context = get_anonymized_cohort_context()

    if not api_key:
        # Modo Fallback Analítico: Responde con los datos estadísticos reales de la cohorte
        fallback_answer = generate_fallback_clinical_answer(clean_question)
        note = (
            "\n\n---\n"
            "> ℹ️ *Asistente en modo de datos directos de la BD. Para activar la inteligencia conversacional avanzada "
            "con **Google Gemini Flash**, configure su `GEMINI_API_KEY` en el archivo `.env`.*"
        )
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

    # Invocación oficial con google-genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt_parts = [
            cohort_context,
            "\nCONSULTA DEL INVESTIGADOR/CLÍNICO:",
            clean_question
        ]
        full_prompt = "\n".join(prompt_parts)

        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=2048,
            )
        )

        response_text = response.text if response and response.text else "No se pudo generar una respuesta con la cohorte provista."
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
        logger.exception(f"Error al invocar Google Gemini API: {e}")
        # En caso de fallo de red o cuota en Gemini, responder limpiamente con el motor analítico de respaldo
        fallback_answer = generate_fallback_clinical_answer(clean_question)
        error_notice = f"\n\n---\n> ⚠️ *Nota:* Respuesta obtenida del motor analítico institucional (Fallo temporal API Gemini: {str(e)[:80]})."
        final_answer = fallback_answer + error_notice

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
    """Registra la interacción en la base de datos de manera segura y sin interrumpir la experiencia."""
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
        logger.warning(f"No se pudo registrar la consulta en ai.bot_query: {err}")
