# -*- coding: utf-8 -*-
"""
sav_importer.py
Servicio inteligente de análisis e importación de archivos SPSS (.sav / .zsav).
Diseñado para la base de datos de investigación cardiovascular (UNEMI / ESPOL).
"""

import os
import re
import uuid
import datetime
import unicodedata
from decimal import Decimal
from pathlib import Path

import pyreadstat
from django.conf import settings
from django.db import transaction

from catalog.models import (
    Institution, Sex, Ethnicity, Canton, Province, Country,
    StaffCategory, ProfessionalCategory, MaritalStatus,
    LivingSituation, EducationLevel, WorkSchedule, HousingType,
    IncomeRange, EcgRhythm, Question, QuestionnaireSection
)
from clinical.models import (
    Patient, Visit, Anthropometry, VitalSigns,
    Electrocardiogram, Echocardiogram, Laboratory, VisitAnswer
)

try:
    from audit.models import ChangeLog
except ImportError:
    ChangeLog = None


# -----------------------------------------------------------------------------
# Normalización y búsqueda difusa de nombres de variables SPSS
# -----------------------------------------------------------------------------

def normalize_var_name(name):
    """
    Limpia y normaliza un identificador de variable SPSS:
    - Reemplaza caracteres corruptos / unicode de reemplazo (\ufffd, ?)
    - Remueve acentos y caracteres no alfanuméricos
    - Retorna en minúsculas sin espacios
    """
    if not name:
        return ""
    # Reemplazo de marcas comunes de caracteres corruptos en nombres de columnas SPSS
    s = re.sub(r'[\ufffd\?]+', 'o', str(name))
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9_]+', '', s)
    return s.lower()


# Diccionario de alias clave para detectar columnas clínicas estándar

# -----------------------------------------------------------------------------
# Patrones de errores gramaticales y tipográficos conocidos en columnas SPSS
# Mapeo directo a su destino en la base de datos
# -----------------------------------------------------------------------------

COLUMN_TYPO_RULES = [
    (r'CONVIVE_CON_USTES', 'CONVIVE_CON_USTED', 'Error gramatical: "USTES" corregido a "USTED"', 'Sociodemográfico / Personas Convivientes', 'gramatical'),
    (r'ANTECEDENTRS', 'ANTECEDENTES', 'Error tipográfico: "ANTECEDENTRS" corregido a "ANTECEDENTES"', 'Cuestionario Clínico / Antecedentes Personales', 'tipografico'),
    (r'FACTORES_TIESGO', 'FACTORES_RIESGO', 'Error tipográfico: "TIESGO" corregido a "RIESGO"', 'Cuestionario Clínico / Factores de Riesgo', 'tipografico'),
    (r'TRONTO', 'TRONCO', 'Error tipográfico: "TRONTO" corregido a "TRONCO"', 'Ecocardiograma / Tronco Arteria Pulmonar', 'tipografico'),
    (r'PULMUNAR', 'PULMONAR', 'Error tipográfico: "PULMUNAR" corregido a "PULMONAR"', 'Ecocardiograma / Válvula / Arteria Pulmonar', 'tipografico'),
    (r'CALIFICACION_ANILLO', 'CALCIFICACION_ANILLO', 'Error médico/tipográfico: "CALIFICACION" corregido a "CALCIFICACION"', 'Ecocardiograma / Calcificación de Anillo', 'medico'),
    (r'ESTERNOSIS', 'ESTENOSIS', 'Error tipográfico: "ESTERNOSIS" corregido a "ESTENOSIS"', 'Ecocardiograma / Estenosis Valvular', 'tipografico'),
    (r'AROTICA', 'AORTICA', 'Error tipográfico: "AROTICA" corregido a "AORTICA"', 'Ecocardiograma / Válvula Aórtica', 'tipografico'),
    (r'GRADIANTE', 'GRADIENTE', 'Error tipográfico: "GRADIANTE" corregido a "GRADIENTE"', 'Ecocardiograma / Gradiente Transvalvular', 'tipografico'),
    (r'TRNASVALVULAR', 'TRANSVALVULAR', 'Error tipográfico: "TRNASVALVULAR" corregido a "TRANSVALVULAR"', 'Ecocardiograma / Flujo Transvalvular', 'tipografico'),
    (r'VENA_CONTRTACTA', 'VENA_CONTRACTA', 'Error tipográfico: "CONTRTACTA" corregido a "CONTRACTA"', 'Ecocardiograma / Vena Contracta', 'tipografico'),
    (r'LLENQADO', 'LLENADO', 'Error tipográfico: "LLENQADO" corregido a "LLENADO"', 'Ecocardiograma / Patrón de Llenado Ventricular', 'tipografico'),
    (r'TRICUSPUDE', 'TRICUSPIDE', 'Error tipográfico: "TRICUSPUDE" corregido a "TRICUSPIDE"', 'Ecocardiograma / Válvula Tricúspide', 'tipografico'),
    (r'DISTOLICA', 'DIASTOLICA', 'Error tipográfico: "DISTOLICA" corregido a "DIASTOLICA"', 'Ecocardiograma / Función Diastólica', 'tipografico'),
    (r'ECOCARDIOFRAFIA', 'ECOCARDIOGRAFIA', 'Error tipográfico: "ECOCARDIOFRAFIA" corregido a "ECOCARDIOGRAFIA"', 'Cuestionario Clínico / Estudios Previos: Ecocardiograma', 'tipografico'),
    (r'CCARDIACO', 'CARDIACO', 'Error tipográfico: "CCARDIACO" corregido a "CARDIACO"', 'Cuestionario Clínico / Estudios Previos: RNM Cardíaco', 'tipografico'),
    (r'ANAEROBICOSS', 'ANAEROBICOS', 'Error tipográfico: doble "S" en "ANAEROBICOSS"', 'Cuestionario / Ejercicios Anaeróbicos', 'tipografico'),
    (r'DISPLEMIA', 'DISLIPEMIA', 'Error en etiqueta: "DISPLEMIA" corregido a "DISLIPEMIA"', 'Cuestionario Clínico / Antecedente: Dislipemia', 'etiqueta'),
]

SPSS_QUESTION_ALIASES = {
    # Módulo 1: Ficha / Sociodemográfico
    'f_universidad': 'universidad',
    'f_visita': 'visita',
    'f_estamento': 'categoria_personal',
    'f_codigo': 'codigo',
    'f_fecha_visita': 'fecha',
    'f_nombre': 'nombres',
    'f_apellido1': 'primer_apellido',
    'f_apellido2': 'segundo_apellido',
    'f_cedula': 'cedula',
    'f_ciudad': 'ciudad',
    'f_provincia': 'provincia',
    'f_municipio': 'lugar_de_nacimiento',
    'f_provincia_nac': 'provincia_nac',
    'f_fecha_nac': 'fecha_de_nacimiento',
    'f_edad': 'edad',
    'f_sexo': 'sexo',
    'f_raza': 'raza',
    'f_estado_civil': 'estado_civil',
    'f_hijos': 'cuantos_hijos__tiene',
    'f_convive_con': 'con_quien_vive',
    'f_convivientes': 'cuantas_personas_convive_con_ustes_en_el_hogar',
    'f_estudios': 'nivel_estudios_obtenido',
    'f_horario': 'horario_de_trabajo',
    'f_profesion': 'categoria_profesional',
    'f_vivienda': 'su_vivienda_es',
    'f_ingresos': 'ingresos_totales_mensuales',

    # Módulo 2: Antropometría y Signos Vitales
    'f_peso': 'peso_kg',
    'f_talla': 'talla_cm',
    'f_perimetro': 'perimetro_abdominal_cm',
    'f_imc': 'imc_kgm2',
    'f_asc': 'asc_m2',
    'f_tas': 'tas_ts',
    'f_tsi': 'tas_mmhg',
    'f_sat_o2': 'saturacion_o2',
    'f_fc': 'frecuencia_cardiaca_ipm',
    'soplos': 'soplos_cardiacos',
    'soplo_grado': 'soplos_cardiacos',
    'soplo_tipo': 'soplos_cardiacos',
    'pulsos_palp': 'pulsospedios',
    'pulsos_sim': 'pulsospedios',
    'pulsos_pedios': 'pulsospedios',
    'resp_norm': 'exploracion_respiratoria',
    'abdom_norm': 'exploracion_abdominal',

    # Módulo 3: Factores de Riesgo Modificables
    'r_hta': 'hipertension',
    'r_hta_trat': 'hta_tto',
    'r_dm': 'diabetes_mellitus',
    'r_dm_trat': 'diabetes_tto',
    'r_dislip': 'dislipemia',
    'r_dislip_trat': 'dlp_tto',
    'r_tabaco': 'tabaquismo',
    'r_alcohol': 'alcohol',
    'r_drogas': 'drogas',
    'r_sobrepeso': 'peso_corporal',
    'r_irc': 'insuf_renal_cronica',
    'r_higado': 'higado_graso',
    'res_higado_graso': 'higado_graso',
    'r_apnea': 'apnea_sueno',
    'r_arritmias': 'arritmias',
    'arritmias_tipo': 'arritmias',
    'r_sincopes': 'sincopes',
    'sincopes_tipo': 'sincopes',
    'r_ictus': 'antecedentrs_ictus',
    'r_disfunc': 'disfuncion_erectil',
    'r_vasc_perif': 'vasculopatia',
    'r_vasc_carot': 'vasculopatia',

    # Módulo 3: Factores Emergentes
    'sueno_cantidad': 'cantidad_sueno',
    'sueno_calidad': 'calidad_sueno',
    'em_toxicos': 'trabaja_con_toxicos',
    'em_estrogenos': 'bajos_estrogenos',
    'em_anticonceptivos': 'proteccion_anticonceptivo',
    'em_estres_trab': 'estres',
    'em_estres_fam': 'estres',
    'em_mal_amb': 'mal_ambiente_laboral',
    'em_pers_a': 'personalidad_tipo_a',
    'em_personalidad_a': 'personalidad_tipo_a',
    'em_exigente': 'exigente',
    'em_perfeccionista': 'perfeccionista',
    'em_hiperactivo': 'hiperactivo',
    'em_ambicioso': 'ambicioso',
    'em_hostilidad': 'hostilidad',
    'em_aislamiento': 'aislamiento_social',

    # Módulo 3: Antecedentes Familiares
    'ant_padre_hta': 'af_padre_hta',
    'ant_madre_hta': 'af_madre_hta',
    'ant_padre_dm': 'af_padre_dm',
    'ant_madre_dm': 'af_madre_dm',
    'ant_padre_iam': 'af_padre_iam',
    'ant_madre_iam': 'af_madre_iam',
    'ant_padre_ictus': 'af_padre_ictus',
    'ant_madre_ictus': 'af_madre_ictus',
    'nm_cardiopatia': 'factores_tiesgo_cardiopatia',
    'nm_fallecido': 'af_muerte_subita',

    # Módulo 4: Historia Cardiovascular y Rose
    'nc_cancer': 'historia_cancer',
    'nc_epoc': 'problemas_respiratorios',
    'nc_asma': 'problemas_respiratorios',
    'nc_reuma': 'enfermedad_reumatologicas',
    'nc_depresion': 'salud_mental',
    'nc_ansiedad': 'salud_mental',
    'nc_alergia': 'alergias',
    'rose_1': 'dolor_pecho',
    'rose_2': 'dolor_pecho',
    'rose_3': 'molestia_caminar',
    'rose_4': 'reaccion_dolor_caminar',
    'rose_5': 'tiempo_dolor_clase_nyha',

    # Módulo 4: COVID-19 y Secuelas
    'covid_paso': 'historia_covid',
    'covid_ingreso': 'historia_covid',
    'covid_cv': 'afectacion_covid',
    'covid_pulm': 'afectacion_covid',
    'longcovid': 'long_covid',
    'longcovid_sintomas': 'sintomas_covid',

    # Módulo 5: Laboratorio Clínico
    'hemo_hematies': 'hematies',
    'hemo_hemoglobina': 'hemoglobina',
    'hemo_hematocrito': 'hematocrito',
    'hemo_vcm': 'volumen_corpuscular_medio_vcm',
    'hemo_hcm': 'hemoglobina_corpuscular_medio_hcm',
    'hemo_chcm': 'concentracion_hemoglobina_corpuscular_media_chcm',
    'hemo_leucocitos': 'leucocitos',
    'hemo_neutrofilos': 'neutrofilos',
    'hemo_eosinofilos': 'eosinofilos',
    'hemo_basofilos': 'basofilos',
    'hemo_linfocitos': 'linfocitos',
    'hemo_monocitos': 'monocitos',
    'hemo_plaquetas': 'plaquetas',
    'hemo_inr': 'inr',
    'hemo_tpt': 'tiempo_protombina',
    'hemo_fibrinogeno': 'fibrinogeno',
    'tiroidea_tsh': 'tsh_funcion_tiroidea',
    'tiroidea_t4': 'hormonas_tiroideas_t4',
    'tiroidea_t3': 'hormonas_tiroideas_t3',
    'renal_urea': 'urea_funcion_renal',
    'renal_creatinina': 'creatina_funcion_renal',
    'renal_filtrado': 'filtracion_glomerular_tfg',
    'orina_microalbuminuria': 'orina_microalbuminuria',
    'ion_potasio': 'potasio_iones',
    'ion_calcio': 'calcio_iones',
    'ion_magnesio': 'magnesio_iones',
    'ion_sodio': 'sodio_iones',
    'diab_glucosa': 'glucosa_sangre',
    'diab_hba1c': 'hemoglobina_glicosilada',
    'diab_homair': 'homa_ir',
    'diab_insulina': 'insulina_ayunas',
    'riesgo_colesterol': 'colesterol_total_riesgo_cardiovascular',
    'riesgo_hdl': 'hdl_riesgo_cardiovascular',
    'riesgo_ldl': 'ldl_riesgo_cardiovascular',
    'riesgo_vldl': 'vdl_riesgo_cardiovascular',
    'riesgo_trigliceridos': 'trigliceridos_riesgo_cardiovascular',
    'riesgo_lipoproteina_a': 'lipoproteina_riesgo_cardiovascular',
    'riesgo_apo_b': 'apolipoproteina_b_riesgo_cardiovascular',
    'emerg_homocisteina': 'homocisteina',
    'emerg_pcr': 'pcr_ultrasensible',
    'emerg_acido_urico': 'acido_urico',
    'hepatica_ggt': 'ggt_funcion_hepatica',
    'hepatica_gpt': 'gpt_alt_funcion_hepatica',
    'hepatica_got': 'got_ast_funcion_hepatica',

    # Módulo 5: Electrocardiograma
    'ecg_ritmo': 'ecg_ritmo',
    'ecg_pr': 'intervalo_pr_seg',
    'ecg_qrs': 'complejo_qr_sseg',
    'ecg_qt': 'intervalo_qt_seg',
    'ecg_qtc': 'intervalo_corregido_baset_mseg',
    'ecg_eje': 'eje_electrico_a',
    'ecg_hvi': 'sobrecarga_sistolica',
    'ecg_bloqueo': 'bloqueo_de_rama_cual',
    'ecg_normal': 'ecg_normal',

    # Módulo 4: Ecocardiograma
    'res_eco_normal': 'ecocardiograma',
    'res_vi_hipertrofico': 'ventriculo_izquierdo_hipertrofico',
    'res_vi_dilatado': 'ventriculo_izquierdo_dilatado',
    'res_fdvi': 'funcion_diastolica_ventriculo_izquierdo',
    'eco_ddvi': 'dtdvi',
    'eco_dtsvi': 'dtsvi',
    'eco_fey': 'fraccion_eyeccion_teicholz',
    'valvulopatia_tipo_detalle': 'insuficiencia_mitral',
    'ip_medida_chorro': 'medida_chorro_regurgitante_insuficiencia_pulmonar',

    # Módulo 6: Dieta Mediterránea (PREDIMED)
    'pred_q1': 'usa_usted_aceite_de_oliva',
    'pred_q2': 'cuanto_aceite_de_oliva_consume',
    'pred_q3': 'usted_consume_verduras',
    'pred_q4': 'usted_consume_fruta',
    'pred_q5': 'usted_consume_carne_roja_embutidos',
    'pred_q6': 'usted_consume_mantequilla_margarina_nata',
    'pred_q7': 'usted_consume_bebidas_carbonatadas',
    'pred_q8': 'usted_consume_vino_tinto',
    'pred_q9': 'usted_consume_legumbres',
    'pred_q10': 'usted_consume_pescado_mariscos',
    'pred_q11': 'usted_consume_reposteria',
    'pred_q12': 'usted_consume_frutos_secos',
    'pred_q13': 'usted_consume_pollo_pavo_o_conejo_en_de_ternera',
    'pred_q14': 'usted_consume_alimentos_con_sofrito',

    # Módulo 6: Actividad Física (IPAQ)
    'act_realiza': 'usted_realiza_actividad_fisica',
    'act_aerob': 'usted_realiza_ejercicios_aerobicos',
    'act_aerob_cual': 'cual_ejercicios_realiza',
    'act_aerob_frec': 'cuantas_veces_por_semana',
    'act_aerob_min': 'cuantos_minutos_al_dia',
    'act_anaerob': 'usted_realiza_ejercicios_anaerobicos',
    'act_anaerob_cual': 'cual_ejercicio_anaerobico_realiza',
    'act_anaerob_frec': 'cuantas_veces_por_semana_anaerobicoss',
    'act_anaerob_min': 'cuantos_minutos_al_dia_anaerobicos',
    'act_deporte': 'hace_deporte',
    'act_deporte_tipo': 'que_tipo_de_deporte',
    'act_deporte_frec': 'cuantas_veces_por_semana_hace_deporte',
    'act_deporte_min': 'cuantos_minutos_al_dia_hace_deporte',
    'act_horas_tv': 'horas_tv',
    'act_horas_dormir': 'horas_dormir',
    'act_horas_siesta': 'horas_siesta',
    'act_horas_ocio': 'horas_ocio',
    'act_horas_sent_lv': 'horas_sentadolv',
    'act_horas_sent_sd': 'horas_sentadosd',
}


def classify_spss_question_section(col_name):
    """
    Clasifica con precisión médica cualquier columna SPSS en su QuestionnaireSection exacta de PostgreSQL.
    """
    norm = normalize_var_name(col_name)

    # 1. PREDIMED (Dieta Mediterránea)
    if any(k in norm for k in ['aceite_de_oliva', 'consume_verduras', 'consume_fruta', 'consume_carne', 'mantequilla', 'carbonatadas', 'vino_tinto', 'legumbres', 'pescado', 'reposteria', 'leche_de_vaca', 'queso', 'yogurt', 'frutos_secos', 'huevos', 'cereales', 'pollo_pavo', 'sofrito', 'medas', 'predimed', 'pred_']):
        return 'MOD_6_PREDIMED'

    # 2. Actividad Física / IPAQ
    if any(k in norm for k in ['actividad_fisica', 'ejercicios_aerobicos', 'cual_ejercicios', 'veces_por_semana', 'minutos_al_dia', 'ejercicios_anaerobicos', 'anaerobic', 'deporte', 'horas_tv', 'horas_dormir', 'horas_siesta', 'horas_ocio', 'horas_sentado', 'ipaq', 'act_']):
        return 'MOD_6_ACTIVIDAD_FISICA'

    # 3. COVID-19 y Secuelas
    if 'covid' in norm:
        return 'MOD_4_COVID'

    # 4. Factores Emergentes
    if any(k in norm for k in ['sueno', 'toxicos', 'estrogenos', 'anticonceptivo', 'estres', 'ambiente', 'tipo_a', 'exigente', 'perfeccionista', 'hiperactivo', 'ambicioso', 'hostilidad', 'aislamiento', 'condiciones_ambientales', 'em_']):
        return 'MOD_3_FACTORES_EMERG'

    # 5. Antecedentes Familiares
    if any(k in norm for k in ['antecedentes_familiares', 'antecedentes_padres', 'antecedentes_madres', 'antecedentes_hermanos', 'padre', 'madre', 'af_']):
        return 'MOD_3_ANTECEDENTES_FAM'

    # 6. Historia Cardiovascular y Rose
    if any(k in norm for k in ['problema_corazon', 'revascularizacion', 'insuficiencia_cardiaca', 'ingreso_hospitalario', 'dolor_pecho', 'molestia_caminar', 'reaccion_dolor', 'clase_nyha', 'rose', 'estudios_clinicos', 'estudios_ecocardio', 'estudios_de_mapa', 'estudios_de_ergonometria', 'estudios_de_tac', 'estudios_de_rnm', 'estudios_de_electrofisiologia', 'holter']):
        return 'MOD_4_HISTORIA_CARDIO'

    # 7. Historia No Cardiovascular
    if any(k in norm for k in ['cancer', 'problemas_respiratorios', 'salud_mental', 'alergias', 'otras', 'reumatolog', 'nc_']):
        return 'MOD_4_HISTORIA_NO_CARDIO'

    # 8. Factores Modificables (Predeterminado para factores de riesgo tradicionales)
    return 'MOD_3_FACTORES_MOD'


STANDARD_FIELD_ALIASES = {
    'codigo': ['codigo', 'study_code', 'id_paciente', 'paciente_id', 'id_participante', 'cod', 'id'],
    'cedula': ['cedula', 'ci', 'id_card', 'dni', 'identificacion', 'num_cedula'],
    'nombres': ['nombres', 'nombre', 'first_names', 'nombre_completo', 'paciente'],
    'apellido1': ['primer_apellido', 'apellido1', 'last_name1', 'apellidos'],
    'apellido2': ['segundo_apellido', 'apellido2', 'last_name2'],
    'universidad': ['universidad', 'uni', 'institucion', 'institution'],
    'estamento': ['categoria_personal', 'estamento', 'estamento_unemi', 'tipo_personal'],
    'facultad': ['facultad', 'faculty'],
    'visita': ['visita', 'n_visita', 'num_visita', 'numero_visita'],
    'fecha_visita': ['fecha', 'fecha_visita', 'visit_date', 'f_visita_fecha'],
    'ciudad_res': ['ciudad', 'canton', 'residencia_ciudad', 'residencia_canton', 'ciudad_residencia'],
    'provincia_res': ['provincia', 'provincia_residencia', 'residencia_provincia'],
    'ciudad_nac': ['lugar_de_nacimiento', 'canton_nacimiento', 'municipio_nacimiento', 'ciudad_nacimiento'],
    'provincia_nac': ['provincia_nac', 'provincia_nacimiento'],
    'fecha_nac': ['fecha_de_nacimiento', 'fecha_nac', 'birth_date', 'fnac', 'f_nac'],
    'edad': ['edad', 'age'],
    'sexo': ['sexo', 'genero', 'sex'],
    'raza': ['raza', 'etnia', 'ethnicity'],
    'estado_civil': ['estado_civil', 'marital_status'],
    'hijos': ['cuantos_hijos__tiene', 'hijos', 'num_hijos', 'n_hijos'],
    'convive_con': ['con_quien_vive', 'convive_con', 'convivencia'],
    'convivientes': ['cuantas_personas_convive_con_ustes_en_el_hogar', 'convivientes', 'num_convivientes'],
    'estudios': ['nivel_estudios_obtenido', 'estudios', 'educacion', 'nivel_educativo'],
    'horario': ['horario_de_trabajo', 'horario', 'jornada_laboral'],
    'profesion': ['categoria_profesional', 'profesion', 'ocupacion'],
    'vivienda': ['su_vivienda_es', 'vivienda', 'tipo_vivienda'],
    'ingresos': ['ingresos_totales_mensuales', 'ingresos', 'ingreso_familiar'],
    'anio': ['ao', 'a_o', 'anio', 'year'],

    # Antropometría
    'peso': ['peso_kg', 'peso_corporal', 'peso', 'weight'],
    'talla': ['talla_cm', 'talla', 'estatura', 'height'],
    'perimetro': ['perimetro_abdominal_cm', 'perimetro', 'cintura'],
    'imc': ['imc_kgm2', 'imc', 'bmi'],
    'asc': ['asc_m2', 'asc', 'bsa'],

    # Signos Vitales
    'tas': ['tas_ts', 'tas', 'pa_sistolica', 'sistolica'],
    'tad': ['tas_mmhg', 'tad', 'tsi', 'pa_diastolica', 'diastolica'],
    'sat_o2': ['saturacion_o2', 'sat_o2', 'sato2'],
    'fc': ['frecuencia_cardiaca_ipm', 'fc', 'frecuencia_cardiaca', 'pulso'],
    'soplos': ['soplos_cardiacos', 'soplos', 'soplo'],
    'pulsos': ['pulsospedios', 'pulsos_pedios', 'pulsos'],
    'resp_normal': ['exploracion_respiratoria', 'auscultacion_pulmonar'],
    'abdom_normal': ['exploracion_abdominal', 'auscultacion_abdominal'],
    'extratono': ['extratono_sino_tipo'],

    # ECG
    'ecg_ritmo': ['ecg_ritmo', 'ritmo'],
    'ecg_pr': ['intervalo_pr_seg', 'pr_ms', 'pr'],
    'ecg_qrs': ['complejo_qr_sseg', 'complejo_qrs_seg', 'qrs_ms', 'qrs'],
    'ecg_qt': ['intervalo_qt_seg', 'qt_ms', 'qt'],
    'ecg_qtc': ['intervalo_corregido_baset_mseg', 'qtc_bazett_ms', 'qtc'],
    'ecg_eje': ['eje_electrico_a', 'eje', 'axis'],
    'ecg_hvi': ['sobrecarga_sistolica', 'hvi'],
    'ecg_bloqueo': ['bloqueo_de_rama_cual', 'bloqueo_rama'],
    'ecg_rr': ['intervalo_rr_seg'],
    'ecg_onda_p': ['anchura_onda_p_mm', 'onda_p_mitral'],
    'ecg_bloqueo_av': ['bloqueo_av', 'bloqueo_sinoauricular_interauricular'],
    'ecg_hemibloqueo': ['hemibloqueos'],
    'ecg_patrones': ['patrones', 'deflexion_intrinsicoide_v5v6_seg'],
    'ecg_onda_delta': ['onda_delta'],
    'ecg_cubeta': ['cubeta_digitalica'],
    'ecg_onda_q': ['onda_q_patologica'],
    'ecg_t_negativa': ['t_negativa', 't_negativa_complejos'],
    'ecg_st_ascenso': ['ascenso_st_patologico'],
    'ecg_st_descenso': ['descenso_st_patologico'],
    'ecg_normal': ['ecg_normal'],

    # Laboratorio
    'lab_hematies': ['hematies', 'globulos_rojos'],
    'lab_hemoglobina': ['hemoglobina', 'hb'],
    'lab_hematocrito': ['hematocrito', 'hto'],
    'lab_vcm': ['volumen_corpuscular_medio_vcm', 'vcm'],
    'lab_hcm': ['hemoglobina_corpuscular_medio_hcm', 'hcm'],
    'lab_chcm': ['concentracion_hemoglobina_corpuscular_media_chcm', 'chcm'],
    'lab_leucocitos': ['leucocitos', 'globulos_blancos'],
    'lab_neutrofilos': ['neutrofilos'],
    'lab_eosinofilos': ['eosinofilos'],
    'lab_basofilos': ['basofilos'],
    'lab_linfocitos': ['linfocitos'],
    'lab_monocitos': ['monocitos'],
    'lab_plaquetas': ['plaquetas', 'plt'],
    'lab_tiempo_protombina': ['tiempo_protombina', 'inr'],
    'lab_fibrinogeno': ['fibrinogeno'],
    'lab_glucosa': ['glucosa_sangre', 'glucosa'],
    'lab_hba1c': ['hemoglobina_glicosilada', 'hba1c'],
    'lab_insulina': ['insulina_ayunas', 'insulina'],
    'lab_homair': ['homa_ir', 'homair'],
    'lab_urea': ['urea_funcion_renal', 'urea'],
    'lab_creatinina': ['creatina_funcion_renal', 'creatinina'],
    'lab_tfg': ['filtracion_glomerular_tfg', 'tfg'],
    'lab_colesterol': ['colesterol_total_riesgo_cardiovascular', 'colesterol_total'],
    'lab_hdl': ['hdl_riesgo_cardiovascular', 'hdl'],
    'lab_ldl': ['ldl_riesgo_cardiovascular', 'ldl'],
    'lab_vldl': ['vdl_riesgo_cardiovascular', 'vldl'],
    'lab_trigliceridos': ['trigliceridos_riesgo_cardiovascular', 'trigliceridos'],
    'lab_lipoproteina_a': ['lipoproteina_riesgo_cardiovascular', 'lipoproteina_a'],
    'lab_apo_b': ['apolipoproteina_b_riesgo_cardiovascular', 'apo_b'],
    'lab_got': ['got_ast_funcion_hepatica', 'ast', 'got'],
    'lab_gpt': ['gpt_alt_funcion_hepatica', 'alt', 'gpt'],
    'lab_ggt': ['ggt_funcion_hepatica', 'ggt'],
    'lab_tsh': ['tsh_funcion_tiroidea', 'tsh'],
    'lab_t4': ['hormonas_tiroideas_t4', 't4'],
    'lab_t3': ['hormonas_tiroideas_t3', 't3'],
    'lab_potasio': ['potasio_iones', 'potasio'],
    'lab_calcio': ['calcio_iones', 'calcio'],
    'lab_magnesio': ['magnesio_iones', 'magnesio'],
    'lab_sodio': ['sodio_iones', 'sodio'],
    'lab_homocisteina': ['homocisteina'],
    'lab_pcr': ['pcr_ultrasensible', 'pcr'],
    'lab_acido_urico': ['acido_urico'],
    'lab_orina_microalbuminuria': ['orina_microalbuminuria', 'microalbuminuria'],

    # Ecocardiograma
    'eco_ddvi': ['dtdvi', 'diametro_diastolico_vi', 'ddvi'],
    'eco_dtsvi': ['dtsvi'],
    'eco_fey': ['fraccion_eyeccion_teicholz', 'fey', 'fraccion_eyeccion'],
    'eco_hvi': ['ventriculo_izquierdo_hipertrofico', 'res_vi_hipertrofico'],
    'eco_disfuncion': ['funcion_diastolica_ventriculo_izquierdo', 'eco_disfuncion_diastolica'],
    'eco_calcificacion': ['calcificacion_anillo_aortico', 'calcificacion_anillo_mitral'],
    'eco_gradiente': ['gradiante_transvalvular', 'gradiente_transvalvular', 'gradiente_medio'],
    'eco_insuficiencia_mitral': ['insuficiencia_mitral'],
    'eco_insuficiencia_aortica': ['insuficiencia_aortica'],
    'eco_insuficiencia_pulmonar': ['insuficiencia_pulmonar', 'medida_chorro_regurgitante_insuficiencia_pulmonar'],
    'eco_estenosis_mitral': ['esternosis_mitral', 'estenosis_mitral'],
    'eco_estenosis_aortica': ['estenosis_arotica', 'estenosis_aortica'],
    'eco_estenosis_pulmonar': ['estenosis_pulmonar'],
    'eco_derrame': ['derrame_pericardio'],
    'eco_vi_dilatado': ['ventriculo_izquierdo_dilatado'],
    'eco_vd_dilatado': ['ventriculo_derecho_dilatado'],
    'eco_vd_hipertrofico': ['ventriculo_derecho_hipertrofico'],
    'eco_aorta_dilatada': ['aorta_dilatada'],
}

FIELD_DESTINATIONS = {
    'codigo': ('Identificación Institucional', 'Código de Estudio (study_code)'),
    'cedula': ('Identificación del Paciente', 'Cédula de Identidad (id_card)'),
    'nombres': ('Identificación del Paciente', 'Nombres (first_names)'),
    'apellido1': ('Identificación del Paciente', 'Primer Apellido (last_name1)'),
    'apellido2': ('Identificación del Paciente', 'Segundo Apellido (last_name2)'),
    'universidad': ('Identificación Institucional', 'Institución / Universidad'),
    'estamento': ('Identificación Institucional', 'Estamento UNEMI / Categoría'),
    'facultad': ('Identificación Institucional', 'Facultad'),
    'visita': ('Identificación Institucional', 'N.° de Visita'),
    'fecha_visita': ('Identificación Institucional', 'Fecha de Visita'),
    'anio': ('Identificación Institucional', 'Año de Cohorte'),
    'ciudad_res': ('Sociodemográfico', 'Cantón de Residencia'),
    'provincia_res': ('Sociodemográfico', 'Provincia de Residencia'),
    'ciudad_nac': ('Sociodemográfico', 'Cantón de Nacimiento'),
    'provincia_nac': ('Sociodemográfico', 'Provincia de Nacimiento'),
    'fecha_nac': ('Sociodemográfico', 'Fecha de Nacimiento'),
    'edad': ('Sociodemográfico', 'Edad reportada'),
    'sexo': ('Sociodemográfico', 'Sexo biológico'),
    'raza': ('Sociodemográfico', 'Raza / Etnia'),
    'estado_civil': ('Sociodemográfico', 'Estado Civil'),
    'hijos': ('Sociodemográfico', 'Número de Hijos'),
    'convive_con': ('Sociodemográfico', 'Con quién vive'),
    'convivientes': ('Sociodemográfico', 'Personas convivientes'),
    'estudios': ('Sociodemográfico', 'Nivel de Estudios'),
    'horario': ('Sociodemográfico', 'Horario Laboral'),
    'profesion': ('Sociodemográfico', 'Categoría Profesión'),
    'vivienda': ('Sociodemográfico', 'Tipo de Vivienda'),
    'ingresos': ('Sociodemográfico', 'Ingresos Familiares'),
    'peso': ('Antropometría', 'Peso (kg)'),
    'talla': ('Antropometría', 'Talla (cm)'),
    'perimetro': ('Antropometría', 'Perímetro Abdominal (cm)'),
    'imc': ('Antropometría', 'Índice de Masa Corporal (IMC)'),
    'asc': ('Antropometría', 'Área de Superficie Corporal (ASC)'),
    'tas': ('Signos Vitales', 'Presión Sistólica TAS (mmHg)'),
    'tad': ('Signos Vitales', 'Presión Diastólica TAD (mmHg)'),
    'sat_o2': ('Signos Vitales', 'Saturación O2 (%)'),
    'fc': ('Signos Vitales', 'Frecuencia Cardíaca (lpm)'),
    'soplos': ('Signos Vitales', 'Soplos Cardíacos'),
    'pulsos': ('Signos Vitales', 'Pulsos Pedios'),
    'resp_normal': ('Signos Vitales', 'Auscultación Pulmonar'),
    'abdom_normal': ('Signos Vitales', 'Auscultación Abdominal'),
    'extratono': ('Signos Vitales', 'Extratono / Ritmo de Galope'),
    'ecg_ritmo': ('Electrocardiograma', 'Ritmo ECG'),
    'ecg_pr': ('Electrocardiograma', 'Intervalo PR (ms)'),
    'ecg_qrs': ('Electrocardiograma', 'Duración QRS (ms)'),
    'ecg_qt': ('Electrocardiograma', 'Intervalo QT (ms)'),
    'ecg_qtc': ('Electrocardiograma', 'QTc Corregido Bazett (ms)'),
    'ecg_eje': ('Electrocardiograma', 'Eje QRS (grados)'),
    'ecg_hvi': ('Electrocardiograma', 'Hipertrofia Ventricular Izq.'),
    'ecg_bloqueo': ('Electrocardiograma', 'Bloqueo de Rama'),
    'ecg_rr': ('Electrocardiograma', 'Intervalo RR (seg)'),
    'ecg_onda_p': ('Electrocardiograma', 'Morfología Onda P'),
    'ecg_bloqueo_av': ('Electrocardiograma', 'Bloqueo AV'),
    'ecg_hemibloqueo': ('Electrocardiograma', 'Hemibloqueos'),
    'ecg_patrones': ('Electrocardiograma', 'Patrones de Conducción'),
    'ecg_onda_delta': ('Electrocardiograma', 'Onda Delta (WPW)'),
    'ecg_cubeta': ('Electrocardiograma', 'Cubeta Digitálica'),
    'ecg_onda_q': ('Electrocardiograma', 'Onda Q Patológica'),
    'ecg_t_negativa': ('Electrocardiograma', 'Onda T Negativa'),
    'ecg_st_ascenso': ('Electrocardiograma', 'Ascenso ST Patológico'),
    'ecg_st_descenso': ('Electrocardiograma', 'Descenso ST Patológico'),
    'ecg_normal': ('Electrocardiograma', 'ECG Normal / Patológico'),
    'lab_hematies': ('Laboratorio Clínico', 'Hematíes (millones/µL)'),
    'lab_hemoglobina': ('Laboratorio Clínico', 'Hemoglobina (g/dL)'),
    'lab_hematocrito': ('Laboratorio Clínico', 'Hematocrito (%)'),
    'lab_vcm': ('Laboratorio Clínico', 'VCM (fL)'),
    'lab_hcm': ('Laboratorio Clínico', 'HCM (pg)'),
    'lab_chcm': ('Laboratorio Clínico', 'CHCM (g/dL)'),
    'lab_leucocitos': ('Laboratorio Clínico', 'Leucocitos (miles/µL)'),
    'lab_neutrofilos': ('Laboratorio Clínico', 'Neutrófilos (%)'),
    'lab_eosinofilos': ('Laboratorio Clínico', 'Eosinófilos (%)'),
    'lab_basofilos': ('Laboratorio Clínico', 'Basófilos (%)'),
    'lab_linfocitos': ('Laboratorio Clínico', 'Linfocitos (%)'),
    'lab_monocitos': ('Laboratorio Clínico', 'Monocitos (%)'),
    'lab_plaquetas': ('Laboratorio Clínico', 'Plaquetas (miles/µL)'),
    'lab_tiempo_protombina': ('Laboratorio Clínico', 'Tiempo Protrombina / INR (seg)'),
    'lab_fibrinogeno': ('Laboratorio Clínico', 'Fibrinógeno (mg/dL)'),
    'lab_glucosa': ('Laboratorio Clínico', 'Glucosa (mg/dL)'),
    'lab_hba1c': ('Laboratorio Clínico', 'Hemoglobina Glicosilada (%)'),
    'lab_insulina': ('Laboratorio Clínico', 'Insulina Ayunas (µUI/mL)'),
    'lab_homair': ('Laboratorio Clínico', 'Índice HOMA-IR'),
    'lab_urea': ('Laboratorio Clínico', 'Urea (mg/dL)'),
    'lab_creatinina': ('Laboratorio Clínico', 'Creatinina (mg/dL)'),
    'lab_tfg': ('Laboratorio Clínico', 'Tasa Filtración Glomerular TFG'),
    'lab_colesterol': ('Laboratorio Clínico', 'Colesterol Total (mg/dL)'),
    'lab_hdl': ('Laboratorio Clínico', 'Colesterol HDL (mg/dL)'),
    'lab_ldl': ('Laboratorio Clínico', 'Colesterol LDL (mg/dL)'),
    'lab_vldl': ('Laboratorio Clínico', 'Colesterol VLDL (mg/dL)'),
    'lab_trigliceridos': ('Laboratorio Clínico', 'Triglicéridos (mg/dL)'),
    'lab_lipoproteina_a': ('Laboratorio Clínico', 'Lipoproteína a (mg/dL)'),
    'lab_apo_b': ('Laboratorio Clínico', 'Apolipoproteína B (mg/dL)'),
    'lab_got': ('Laboratorio Clínico', 'Transaminasa GOT/AST (U/L)'),
    'lab_gpt': ('Laboratorio Clínico', 'Transaminasa GPT/ALT (U/L)'),
    'lab_ggt': ('Laboratorio Clínico', 'GGT (U/L)'),
    'lab_tsh': ('Laboratorio Clínico', 'TSH (µUI/mL)'),
    'lab_t4': ('Laboratorio Clínico', 'Hormona T4 libre (ng/dL)'),
    'lab_t3': ('Laboratorio Clínico', 'Hormona T3 total (ng/dL)'),
    'lab_potasio': ('Laboratorio Clínico', 'Potasio K+ (mEq/L)'),
    'lab_calcio': ('Laboratorio Clínico', 'Calcio Ca++ (mg/dL)'),
    'lab_magnesio': ('Laboratorio Clínico', 'Magnesio Mg++ (mg/dL)'),
    'lab_sodio': ('Laboratorio Clínico', 'Sodio Na+ (mEq/L)'),
    'lab_homocisteina': ('Laboratorio Clínico', 'Homocisteína (µmol/L)'),
    'lab_pcr': ('Laboratorio Clínico', 'PCR Ultrasensible (mg/L)'),
    'lab_acido_urico': ('Laboratorio Clínico', 'Ácido Úrico (mg/dL)'),
    'lab_orina_microalbuminuria': ('Laboratorio Clínico', 'Microalbuminuria en Orina (mg/g)'),
    'eco_ddvi': ('Ecocardiograma', 'Diámetro Diastólico VI (mm)'),
    'eco_dtsvi': ('Ecocardiograma', 'Diámetro Sistólico VI (mm)'),
    'eco_fey': ('Ecocardiograma', 'Fracción de Eyección FEy (%)'),
    'eco_hvi': ('Ecocardiograma', 'Hipertrofia Ventricular Izq.'),
    'eco_disfuncion': ('Ecocardiograma', 'Disfunción Diastólica'),
    'eco_calcificacion': ('Ecocardiograma', 'Calcificación Anillo Aórtico / Mitral'),
    'eco_gradiente': ('Ecocardiograma', 'Gradiente Transvalvular (mmHg)'),
    'eco_insuficiencia_mitral': ('Ecocardiograma', 'Insuficiencia Mitral'),
    'eco_insuficiencia_aortica': ('Ecocardiograma', 'Insuficiencia Aórtica'),
    'eco_insuficiencia_pulmonar': ('Ecocardiograma', 'Insuficiencia Pulmonar'),
    'eco_estenosis_mitral': ('Ecocardiograma', 'Estenosis Mitral'),
    'eco_estenosis_aortica': ('Ecocardiograma', 'Estenosis Aórtica'),
    'eco_estenosis_pulmonar': ('Ecocardiograma', 'Estenosis Pulmonar'),
    'eco_derrame': ('Ecocardiograma', 'Derrame Pericárdico'),
    'eco_vi_dilatado': ('Ecocardiograma', 'Ventrículo Izquierdo Dilatado'),
    'eco_vd_dilatado': ('Ecocardiograma', 'Ventrículo Derecho Dilatado'),
    'eco_vd_hipertrofico': ('Ecocardiograma', 'Ventrículo Derecho Hipertrófico'),
    'eco_aorta_dilatada': ('Ecocardiograma', 'Aorta Dilatada'),
}


def _match_column_to_field(col_name):
    """Encuentra qué campo del sistema corresponde a una columna de SPSS dada."""
    norm_c = normalize_var_name(col_name)
    for field_key, aliases in STANDARD_FIELD_ALIASES.items():
        for alias in aliases:
            if norm_c == alias:
                return field_key
    # Búsqueda por contención
    for field_key, aliases in STANDARD_FIELD_ALIASES.items():
        for alias in aliases:
            if len(alias) >= 4 and (alias in norm_c or norm_c in alias):
                return field_key
    return None


def get_column_destination(col_name):
    """Identifica con precisión médica el módulo y campo destino en PostgreSQL para una columna SPSS."""
    matched_field = _match_column_to_field(col_name)
    if matched_field and matched_field in FIELD_DESTINATIONS:
        return FIELD_DESTINATIONS[matched_field]

    norm = normalize_var_name(col_name)

    # 1. Ecocardiograma
    if any(k in norm for k in ['eco', 'mitral', 'aortic', 'tritusp', 'tricusp', 'pulmonar', 'pulmunar', 'ventricul', 'auricul', 'onda_e', 'onda_a', 'onda_s', 'llenado', 'regurgit', 'valvul', 'estenosis', 'esternosis', 'gradiente', 'gradiante', 'tapse', 'mapse', 'dopler', 'biplanar', 'subcostal', 'cayado', 'engrados', 'movilidad', 'prolapso', 'velocidad', 'thp', 'jet_color', 'derrame', 'contractilidad', 'presiones_llenado', 'araesternal', 'area_sistolica', 'area_valvular', 'itv_de_tsvi', 'funcion_sistolica']):
        return ('Ecocardiograma', f'Parámetro Ecocardiográfico ({col_name})')

    # 2. Electrocardiograma
    if any(k in norm for k in ['ecg', 'ritmo', 'qrs', 'qt', 'bazett', 'bloqueo', 'onda_p', 'hemibloqueo', 'onda_delta', 'cubeta', 'onda_q', 't_negativa', 'ascenso_st', 'descenso_st']):
        return ('Electrocardiograma', f'Parámetro ECG ({col_name})')

    # 3. Laboratorio Clínico
    if any(k in norm for k in ['lab', 'hematies', 'hemoglobin', 'hematocrito', 'vcm', 'hcm', 'chcm', 'leucocit', 'neutrofil', 'eosinofil', 'basofil', 'linfocit', 'monocit', 'plaquet', 'inr', 'fibrinogen', 'protombina', 'tromboplastina', 'glucosa', 'glicosilada', 'hba1c', 'insulina', 'homair', 'homa_ir', 'urea', 'creatin', 'filtracion_glomerular', 'tfg', 'colesterol', 'triglic', 'hdl', 'ldl', 'vdl', 'lipoproteina', 'apolipoproteina', 'got', 'gpt', 'ggt', 'tsh', 'tiroide', 'potasio', 'calcio', 'magnesio', 'sodio', 'homocisteina', 'pcr', 'acido_urico', 'orina', 'transferrina', 'ferritina']):
        return ('Laboratorio Clínico', f'Bioquímica / Hematología ({col_name})')

    # 4. Signos Vitales
    if any(k in norm for k in ['tas', 'tad', 'frecuencia', 'saturacion', 'soplo', 'pulso', 'auscult', 'extratono']):
        return ('Signos Vitales', f'Constante Vital ({col_name})')

    # 5. Antropometría
    if any(k in norm for k in ['peso', 'talla', 'imc', 'perimetro', 'asc']):
        return ('Antropometría', f'Medición Antropométrica ({col_name})')

    # 6. Cuestionarios Específicos
    sec_code = classify_spss_question_section(col_name)
    if sec_code == 'MOD_6_PREDIMED':
        return ('Cuestionario Dieta MEDAS', f'Hábito Nutricional ({col_name})')
    if sec_code == 'MOD_6_ACTIVIDAD_FISICA':
        return ('Cuestionario Actividad Física', f'Hábito Actividad Física ({col_name})')
    if sec_code == 'MOD_4_COVID':
        return ('Cuestionario COVID-19', f'Historia COVID / Secuelas ({col_name})')
    if sec_code == 'MOD_3_FACTORES_EMERG':
        return ('Cuestionario Factores Emergentes', f'Factor Emergente ({col_name})')
    if sec_code == 'MOD_3_ANTECEDENTES_FAM':
        return ('Cuestionario Antecedentes Familiares', f'Antecedente Familiar ({col_name})')
    if sec_code == 'MOD_4_HISTORIA_CARDIO':
        return ('Cuestionario Historia Cardiovascular', f'Historia Cardiovascular ({col_name})')
    if sec_code == 'MOD_4_HISTORIA_NO_CARDIO':
        return ('Cuestionario Historia No Cardiovascular', f'Antecedente No Cardiovascular ({col_name})')

    return ('Cuestionario Factores Modificables', f'Factor de Riesgo ({col_name})')


def detect_column_typos(column_names):
    """
    Detecta y clasifica errores gramaticales o tipográficos en los nombres de columnas
    e identifica exactamente en qué módulo y campo de la base de datos va cada dato.
    """
    detected = []
    seen = set()
    for col in column_names:
        current_col = col
        fixes = []
        target_destination = None
        for pattern, replacement, explanation, destination, err_type in COLUMN_TYPO_RULES:
            if re.search(pattern, current_col, re.IGNORECASE):
                current_col = re.sub(pattern, replacement, current_col, flags=re.IGNORECASE)
                fixes.append(explanation)
                if not target_destination:
                    target_destination = destination

        if current_col != col:
            key = (col, current_col)
            if key not in seen:
                seen.add(key)
                if not target_destination:
                    mod, fld = get_column_destination(current_col)
                    target_destination = f"{mod} / {fld}"
                detected.append({
                    "original": col,
                    "corrected": current_col,
                    "explanation": " | ".join(fixes),
                    "destination": target_destination,
                    "type": "correccion"
                })
    return detected



def _resolve_canton_safe(canton_name, province_name=None):
    """Resuelve un cantón de Ecuador ignorando tildes y mayúsculas."""
    if not canton_name:
        return None
    raw_canton = str(canton_name).strip()
    norm_c = unicodedata.normalize('NFKD', raw_canton).encode('ASCII', 'ignore').decode('utf-8').upper()

    cantons = Canton.objects.select_related('province').all()
    for c in cantons:
        c_norm = unicodedata.normalize('NFKD', c.name).encode('ASCII', 'ignore').decode('utf-8').upper()
        if c_norm == norm_c:
            return c

    # Búsqueda parcial
    for c in cantons:
        c_norm = unicodedata.normalize('NFKD', c.name).encode('ASCII', 'ignore').decode('utf-8').upper()
        if c_norm in norm_c or norm_c in c_norm:
            return c

    return Canton.objects.first()


def _get_val_and_label(val, val_labels_dict):
    """Extrae tanto el valor crudo como la etiqueta textual de SPSS si existe."""
    if val is None:
        return None, ""
    lbl = val_labels_dict.get(val) if val_labels_dict else None
    if lbl is None and isinstance(val, (int, float)):
        # Probar versión float/int
        lbl = val_labels_dict.get(float(val)) if val_labels_dict else None
    lbl_str = str(lbl).strip() if lbl is not None else ""
    return val, lbl_str


# -----------------------------------------------------------------------------
# 1. ANÁLISIS INTELIGENTE DEL ARCHIVO .SAV
# -----------------------------------------------------------------------------

def analyze_sav_file(file_obj, filename="archivo.sav"):
    """
    Lee e inspecciona inteligentemente un archivo SPSS .sav.
    Retorna un informe de diagnóstico para que el usuario confirme antes de guardar.
    """
    temp_dir = Path(settings.MEDIA_ROOT) / "temp_imports"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_token = str(uuid.uuid4())
    temp_path = temp_dir / f"{temp_token}.sav"

    # Guardar temporalmente el archivo subido
    with open(temp_path, "wb") as dest:
        for chunk in file_obj.chunks():
            dest.write(chunk)

    try:
        df_dict, meta = pyreadstat.read_sav(str(temp_path), output_format="dict")
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        return {
            "success": False,
            "error": f"No se pudo leer el archivo SPSS: {str(e)}"
        }

    total_rows = meta.number_rows
    total_cols = meta.number_columns
    col_names = list(df_dict.keys())

    # Mapeo de columnas
    field_to_col = {}
    col_to_field = {}
    for col in col_names:
        matched_field = _match_column_to_field(col)
        if matched_field and matched_field not in field_to_col:
            field_to_col[matched_field] = col
            col_to_field[col] = matched_field

    # Diagnóstico de estructura y columnas
    warnings = []
    missing_fields = []

    # 1. Identificadores
    has_names = 'nombres' in field_to_col or 'apellido1' in field_to_col
    has_id_card = 'cedula' in field_to_col
    has_codigo = 'codigo' in field_to_col

    # 2. Comprobación y Mapeo de Columnas (identifica correcciones ortográficas y destino en BD)
    grammatical_errors = detect_column_typos(col_names)

    # Listado estructurado de qué datos van en dónde
    column_mappings = []
    typo_map = {t['original']: t for t in grammatical_errors}
    for col in col_names:
        mod_name, fld_name = get_column_destination(col)
        has_typo = col in typo_map
        column_mappings.append({
            "spss_column": col,
            "corrected_name": typo_map[col]['corrected'] if has_typo else col,
            "has_correction": has_typo,
            "correction_detail": typo_map[col]['explanation'] if has_typo else "",
            "destination_module": mod_name,
            "destination_field": fld_name,
            "destination_label": f"{mod_name} → {fld_name}",
            "status": "Corregido y Mapeado" if has_typo else "Mapeado"
        })

    # 5. Detección de Duplicados Internos en el Archivo
    internal_duplicates = []
    codes_seen_in_file = {}
    if has_codigo:
        cod_col = field_to_col['codigo']
        for idx_row, v in enumerate(df_dict[cod_col]):
            if v is not None:
                c_str = str(int(float(v))) if isinstance(v, (int, float)) else str(v).strip()
                if c_str in codes_seen_in_file:
                    internal_duplicates.append({
                        "code": c_str,
                        "rows": [codes_seen_in_file[c_str] + 1, idx_row + 1]
                    })
                else:
                    codes_seen_in_file[c_str] = idx_row

    if internal_duplicates:
        warnings.append(
            f"Se detectaron {len(internal_duplicates)} código(s) duplicado(s) dentro del mismo archivo SPSS "
            f"(ej: Código {internal_duplicates[0]['code']})."
        )

    # 6. Detección de Duplicados con la Base de Datos
    db_visits = Visit.objects.select_related('patient').all()
    db_codes_map = {
        v.study_code: (v.patient.full_name if v.patient else f"Código {v.study_code}")
        for v in db_visits if v.study_code
    }

    db_duplicates = []
    new_patients_count = 0
    if has_codigo:
        cod_col = field_to_col['codigo']
        for v in df_dict[cod_col]:
            if v is not None:
                c_str = str(int(float(v))) if isinstance(v, (int, float)) else str(v).strip()
                if c_str in db_codes_map:
                    db_duplicates.append({
                        "code": c_str,
                        "patient_name": db_codes_map[c_str]
                    })
                else:
                    new_patients_count += 1
            else:
                new_patients_count += 1
    else:
        new_patients_count = total_rows

    if db_duplicates:
        warnings.append(
            f"Se encontraron {len(db_duplicates)} paciente(s) que ya existen en la base de datos "
            f"(Códigos: {', '.join([d['code'] for d in db_duplicates[:5]])}{'...' if len(db_duplicates) > 5 else ''}). "
            f"Podrá elegir si desea actualizarlos o conservar los datos existentes."
        )

    # Vista previa de los primeros 5 registros
    preview_rows = []
    num_preview = min(5, total_rows)
    for i in range(num_preview):
        row_data = {}
        for f_key in ['codigo', 'sexo', 'edad', 'fecha_visita', 'tas', 'tad', 'peso', 'talla', 'ciudad_res', 'universidad']:
            c_name = field_to_col.get(f_key)
            if c_name:
                raw_val = df_dict[c_name][i]
                vlabels = meta.variable_value_labels.get(c_name, {})
                _, lbl = _get_val_and_label(raw_val, vlabels)
                if lbl:
                    row_data[f_key] = lbl
                elif raw_val is not None:
                    if f_key in ['codigo', 'edad'] and isinstance(raw_val, (int, float)):
                        row_data[f_key] = str(int(raw_val))
                    else:
                        row_data[f_key] = str(raw_val)
                else:
                    row_data[f_key] = "--"
            else:
                row_data[f_key] = "--"

        # Si no hay código explícito
        if row_data.get('codigo') == "--":
            row_data['codigo'] = str(i + 1)

        preview_rows.append(row_data)

    categories_breakdown = {
        "demograficos": len([c for c in field_to_col.keys() if c in ['codigo', 'cedula', 'nombres', 'apellido1', 'sexo', 'edad', 'ciudad_res', 'provincia_res', 'fecha_nac', 'raza', 'estado_civil']]),
        "exploracion_fisica": len([c for c in field_to_col.keys() if c in ['peso', 'talla', 'imc', 'perimetro', 'tas', 'tad', 'sat_o2', 'fc', 'soplos', 'pulsos']]),
        "ecg": len([c for c in field_to_col.keys() if c.startswith('ecg_')]),
        "laboratorio": len([c for c in field_to_col.keys() if c.startswith('lab_')]),
        "ecocardiograma": len([c for c in field_to_col.keys() if c.startswith('eco_')]),
        "cuestionarios_adicionales": total_cols - len(field_to_col)
    }

    return {
        "success": True,
        "file_name": filename,
        "total_rows": total_rows,
        "total_columns": total_cols,
        "mapped_standard_columns": len(field_to_col),
        "unmapped_extra_columns": total_cols - len(field_to_col),
        "categories_breakdown": categories_breakdown,
        "grammatical_errors": grammatical_errors,
        "grammatical_errors_count": len(grammatical_errors),
        "column_mappings": column_mappings,
        "column_mappings_count": len(column_mappings),
        "duplicates": {
            "internal_duplicates": internal_duplicates,
            "internal_duplicates_count": len(internal_duplicates),
            "db_duplicates": db_duplicates,
            "db_duplicates_count": len(db_duplicates),
            "new_patients_count": new_patients_count
        },
        "missing_fields": missing_fields,
        "warnings": warnings,
        "preview_rows": preview_rows,
        "temp_token": temp_token
    }


# -----------------------------------------------------------------------------
# 2. EJECUCIÓN TRANSACCIONAL DE LA IMPORTACIÓN
# -----------------------------------------------------------------------------

def execute_sav_import(temp_token, user, current_year=2026, duplicate_action="update"):
    """
    Importa transaccionalmente todas las filas del archivo SPSS a PostgreSQL.
    Crea Paciente, Visita, Antropometría, Signos Vitales, ECG, Eco, Lab y VisitAnswers.
    """
    temp_dir = Path(settings.MEDIA_ROOT) / "temp_imports"
    temp_path = temp_dir / f"{temp_token}.sav"

    if not temp_path.exists():
        return {
            "success": False,
            "error": "El archivo de importación temporal ha expirado o no fue encontrado. Por favor súbalo nuevamente."
        }

    try:
        df_dict, meta = pyreadstat.read_sav(str(temp_path), output_format="dict")
    except Exception as e:
        return {
            "success": False,
            "error": f"Error al procesar archivo SPSS: {str(e)}"
        }

    total_rows = meta.number_rows
    col_names = list(df_dict.keys())

    # Mapa de columna a campo estándar
    field_to_col = {}
    for col in col_names:
        f_match = _match_column_to_field(col)
        if f_match and f_match not in field_to_col:
            field_to_col[f_match] = col

    # Catálogos pre-cargados para alta eficiencia
    inst_unemi = Institution.objects.filter(acronym__iexact='UNEMI').first() or Institution.objects.first()
    inst_espol = Institution.objects.filter(acronym__iexact='ESPOL').first() or inst_unemi
    sex_hombre = Sex.objects.filter(name__istartswith='H').first()
    sex_mujer = Sex.objects.filter(name__istartswith='M').first()
    ethnicity_default = Ethnicity.objects.filter(name__icontains='Mestizo').first() or Ethnicity.objects.first()
    default_canton = Canton.objects.filter(name__icontains='Milagro').first() or Canton.objects.first()
    sections_by_code = {s.code: s for s in QuestionnaireSection.objects.all()}
    default_section = sections_by_code.get('MOD_3_FACTORES_MOD') or QuestionnaireSection.objects.first()

    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []

    # Mapas de conversión de textos a modelos de catálogo
    staff_map = {
        'PDI': StaffCategory.objects.filter(name__icontains='PDI').first(),
        'PAS': StaffCategory.objects.filter(name__icontains='PAS').first(),
        'SERVICIO': StaffCategory.objects.filter(name__icontains='SERVICIO').first(),
        'ESTUDIANTES': StaffCategory.objects.filter(name__icontains='ESTUDIANTE').first(),
    }
    marital_map = {
        'SOLTERO': MaritalStatus.objects.filter(name__icontains='Soltero').first(),
        'CASADO': MaritalStatus.objects.filter(name__icontains='Casado').first(),
        'DIVORCIADO': MaritalStatus.objects.filter(name__icontains='Divorciado').first(),
        'VIUDO': MaritalStatus.objects.filter(name__icontains='Viudo').first(),
        'UNION': MaritalStatus.objects.filter(name__icontains='Unión').first(),
    }
    living_map = {
        'SOLO': LivingSituation.objects.filter(name__icontains='Solo').first(),
        'PAREJA': LivingSituation.objects.filter(name__icontains='pareja').first(),
        'FAMILIA': LivingSituation.objects.filter(name__icontains='familia').first(),
        'AMIGOS': LivingSituation.objects.filter(name__icontains='amigo').first(),
    }
    education_map = {
        'PRIMARIA': EducationLevel.objects.filter(name__icontains='Primaria').first(),
        'SECUNDARIA': EducationLevel.objects.filter(name__icontains='Secundaria').first(),
        'SUPERIOR': EducationLevel.objects.filter(name__icontains='Tercer').first(),
        'POSTGRADO': EducationLevel.objects.filter(name__icontains='Cuarto').first(),
    }
    work_map = {
        'PARTIDA': WorkSchedule.objects.filter(name__icontains='Completo').first(),
        'CONTINUA': WorkSchedule.objects.filter(name__icontains='Completo').first(),
        'TURNO': WorkSchedule.objects.filter(name__icontains='Turno').first(),
        'PARCIAL': WorkSchedule.objects.filter(name__icontains='Parcial').first(),
    }
    prof_map = {
        'PERMANENTE': ProfessionalCategory.objects.filter(name__icontains='Titular').first(),
        'NO PERMANENTE': ProfessionalCategory.objects.filter(name__icontains='Ocasional').first(),
        'ADMINISTRACION': ProfessionalCategory.objects.filter(name__icontains='Servidor').first(),
        'SERVICIO': ProfessionalCategory.objects.filter(name__icontains='Auxiliar').first(),
        'ESTUDIANTE': ProfessionalCategory.objects.filter(name__icontains='Estudiante').first(),
    }
    housing_map = {
        'PROPIA': HousingType.objects.filter(name__icontains='Propia').first(),
        'ALQUILADA': HousingType.objects.filter(name__icontains='Arrendada').first(),
        'FAMILIAR': HousingType.objects.filter(name__icontains='Familiar').first(),
        'OTRO': HousingType.objects.filter(name__icontains='Prestada').first(),
    }
    income_map = {
        '500': IncomeRange.objects.filter(name__icontains='500').first(),
        '1000': IncomeRange.objects.filter(name__icontains='1000').first(),
        '1500': IncomeRange.objects.filter(name__icontains='1001').first(),
        '2000': IncomeRange.objects.filter(name__icontains='2000').first(),
    }
    rhythm_default = EcgRhythm.objects.first()

    for i in range(total_rows):
        try:
            with transaction.atomic():
                # 1. Determinar Código de Estudio
                raw_cod = None
                if 'codigo' in field_to_col:
                    raw_cod = df_dict[field_to_col['codigo']][i]
                if raw_cod is not None and str(raw_cod).strip() != '':
                    if isinstance(raw_cod, (int, float)):
                        study_code = str(int(raw_cod))
                    else:
                        study_code = str(raw_cod).strip()
                else:
                    study_code = str(i + 1)

                # 2. Institución
                inst = inst_unemi
                if 'universidad' in field_to_col:
                    u_val = df_dict[field_to_col['universidad']][i]
                    _, u_lbl = _get_val_and_label(u_val, meta.variable_value_labels.get(field_to_col['universidad'], {}))
                    if 'ESPOL' in u_lbl.upper() or u_val == 2.0:
                        inst = inst_espol

                # 3. Datos Demográficos
                # Nombres
                first_names = f"Participante {study_code}"
                last_name1 = "Estudio UNEMI"
                last_name2 = ""
                if 'nombres' in field_to_col:
                    v_nom = df_dict[field_to_col['nombres']][i]
                    if v_nom and str(v_nom).strip(): first_names = str(v_nom).strip()
                if 'apellido1' in field_to_col:
                    v_ap1 = df_dict[field_to_col['apellido1']][i]
                    if v_ap1 and str(v_ap1).strip(): last_name1 = str(v_ap1).strip()
                if 'apellido2' in field_to_col:
                    v_ap2 = df_dict[field_to_col['apellido2']][i]
                    if v_ap2 and str(v_ap2).strip(): last_name2 = str(v_ap2).strip()

                # Cédula
                id_card = None
                if 'cedula' in field_to_col:
                    v_ced = df_dict[field_to_col['cedula']][i]
                    if v_ced and str(v_ced).strip():
                        id_card = str(v_ced).strip()
                if not id_card:
                    # Generar serie de 10 dígitos única
                    numeric_num = int(re.sub(r'[^0-9]', '', study_code)) if any(c.isdigit() for c in study_code) else (i + 1)
                    id_card = f"09{str(numeric_num).zfill(8)}"

                # Sexo
                sex = sex_hombre
                if 'sexo' in field_to_col:
                    s_val = df_dict[field_to_col['sexo']][i]
                    _, s_lbl = _get_val_and_label(s_val, meta.variable_value_labels.get(field_to_col['sexo'], {}))
                    if 'MUJER' in s_lbl.upper() or s_val == 2.0:
                        sex = sex_mujer

                # Edad
                edad_val = None
                if 'edad' in field_to_col:
                    raw_edad = df_dict[field_to_col['edad']][i]
                    if raw_edad is not None:
                        try: edad_val = int(float(raw_edad))
                        except Exception: pass

                # Fecha de Nacimiento: conservar el dato exacto tal como está registrado en SPSS
                birth_date = None
                if 'fecha_nac' in field_to_col:
                    raw_dob = df_dict[field_to_col['fecha_nac']][i]
                    if hasattr(raw_dob, 'year'):
                        birth_date = raw_dob.date() if hasattr(raw_dob, 'date') else raw_dob
                    elif isinstance(raw_dob, str) and raw_dob.strip():
                        try: birth_date = datetime.date.fromisoformat(raw_dob.strip())
                        except Exception: pass

                if not birth_date:
                    birth_year = (current_year - edad_val) if edad_val else 1980
                    birth_date = datetime.date(birth_year, 1, 1)

                # Lugar de Nacimiento (Cantón)
                birth_canton = default_canton
                if 'ciudad_nac' in field_to_col:
                    val_cn = df_dict[field_to_col['ciudad_nac']][i]
                    _, lbl_cn = _get_val_and_label(val_cn, meta.variable_value_labels.get(field_to_col['ciudad_nac'], {}))
                    resolved_cn = _resolve_canton_safe(lbl_cn or val_cn)
                    if resolved_cn:
                        birth_canton = resolved_cn

                # Residencia (Cantón)
                residence_canton = default_canton
                if 'ciudad_res' in field_to_col:
                    val_cr = df_dict[field_to_col['ciudad_res']][i]
                    _, lbl_cr = _get_val_and_label(val_cr, meta.variable_value_labels.get(field_to_col['ciudad_res'], {}))
                    resolved_cr = _resolve_canton_safe(lbl_cr or val_cr)
                    if resolved_cr:
                        residence_canton = resolved_cr

                # Buscar paciente existente por código de visita o por cédula
                patient = Patient.objects.filter(visit__study_code=study_code).first()
                if not patient:
                    patient = Patient.objects.filter(id_card=id_card).first()

                # Si el usuario eligió omitir duplicados y ya existe, saltar
                if patient and duplicate_action == "skip":
                    skipped_count += 1
                    continue

                is_new_patient = False
                if not patient:
                    is_new_patient = True
                    patient = Patient(id_card=id_card, created_by=user)

                patient.institution = inst
                if is_new_patient or first_names != f"Participante {study_code}":
                    patient.first_names = first_names
                    patient.last_name1 = last_name1
                    patient.last_name2 = last_name2
                patient.birth_date = birth_date
                patient.sex = sex
                patient.ethnicity = ethnicity_default
                patient.birth_canton = birth_canton
                patient.birth_country = None
                patient.foreign_birth_place = None
                patient.status = Patient.Status.ACTIVE
                patient.save()

                # 4. Crear / Actualizar Visita
                visit = getattr(patient, 'visit', None)
                if not visit:
                    visit = Visit.objects.filter(study_code=study_code).first()

                if not visit:
                    visit = Visit(patient=patient, study_code=study_code)
                    created_count += 1
                else:
                    updated_count += 1

                visit.evaluator = user
                visit.residence_canton = residence_canton

                # Fecha Visita
                visit_date = datetime.date.today()
                if 'fecha_visita' in field_to_col:
                    raw_fv = df_dict[field_to_col['fecha_visita']][i]
                    if hasattr(raw_fv, 'year'):
                        visit_date = raw_fv
                    elif isinstance(raw_fv, str) and raw_fv.strip():
                        try: visit_date = datetime.date.fromisoformat(raw_fv.strip())
                        except Exception: pass
                visit.visit_date = visit_date

                # Estamento institucional
                if 'estamento' in field_to_col:
                    st_val = df_dict[field_to_col['estamento']][i]
                    _, st_lbl = _get_val_and_label(st_val, meta.variable_value_labels.get(field_to_col['estamento'], {}))
                    for k_st, sc_obj in staff_map.items():
                        if k_st in st_lbl.upper():
                            visit.staff_category = sc_obj
                            break

                # Hijos y convivientes
                if 'hijos' in field_to_col:
                    raw_h = df_dict[field_to_col['hijos']][i]
                    if raw_h is not None:
                        try: visit.num_children = int(float(raw_h))
                        except Exception: pass

                if 'convivientes' in field_to_col:
                    raw_cv = df_dict[field_to_col['convivientes']][i]
                    if raw_cv is not None:
                        try: visit.num_cohabitants = int(float(raw_cv))
                        except Exception: pass

                # Mapeo de selectores sociodemográficos
                if 'estado_civil' in field_to_col:
                    ec_val = df_dict[field_to_col['estado_civil']][i]
                    _, ec_lbl = _get_val_and_label(ec_val, meta.variable_value_labels.get(field_to_col['estado_civil'], {}))
                    for k_ec, ms_obj in marital_map.items():
                        if k_ec in ec_lbl.upper():
                            visit.marital_status = ms_obj
                            break

                if 'convive_con' in field_to_col:
                    cc_val = df_dict[field_to_col['convive_con']][i]
                    _, cc_lbl = _get_val_and_label(cc_val, meta.variable_value_labels.get(field_to_col['convive_con'], {}))
                    for k_cc, ls_obj in living_map.items():
                        if k_cc in cc_lbl.upper():
                            visit.living_situation = ls_obj
                            break

                if 'estudios' in field_to_col:
                    ed_val = df_dict[field_to_col['estudios']][i]
                    _, ed_lbl = _get_val_and_label(ed_val, meta.variable_value_labels.get(field_to_col['estudios'], {}))
                    for k_ed, ed_obj in education_map.items():
                        if k_ed in ed_lbl.upper():
                            visit.education_level = ed_obj
                            break

                if 'horario' in field_to_col:
                    ho_val = df_dict[field_to_col['horario']][i]
                    _, ho_lbl = _get_val_and_label(ho_val, meta.variable_value_labels.get(field_to_col['horario'], {}))
                    for k_ho, ws_obj in work_map.items():
                        if k_ho in ho_lbl.upper():
                            visit.work_schedule = ws_obj
                            break

                if 'profesion' in field_to_col:
                    pr_val = df_dict[field_to_col['profesion']][i]
                    _, pr_lbl = _get_val_and_label(pr_val, meta.variable_value_labels.get(field_to_col['profesion'], {}))
                    for k_pr, pf_obj in prof_map.items():
                        if k_pr in pr_lbl.upper():
                            visit.professional_category = pf_obj
                            break

                if 'vivienda' in field_to_col:
                    vi_val = df_dict[field_to_col['vivienda']][i]
                    _, vi_lbl = _get_val_and_label(vi_val, meta.variable_value_labels.get(field_to_col['vivienda'], {}))
                    for k_vi, vi_obj in housing_map.items():
                        if k_vi in vi_lbl.upper():
                            visit.housing_type = vi_obj
                            break

                if 'ingresos' in field_to_col:
                    in_val = df_dict[field_to_col['ingresos']][i]
                    _, in_lbl = _get_val_and_label(in_val, meta.variable_value_labels.get(field_to_col['ingresos'], {}))
                    for k_in, in_obj in income_map.items():
                        if k_in in in_lbl.upper():
                            visit.income_range = in_obj
                            break

                visit.status = Visit.Status.COMPLETED
                visit.save()

                # 5. Antropometría
                peso_val = None
                talla_val = None
                perim_val = None
                if 'peso' in field_to_col:
                    v_p = df_dict[field_to_col['peso']][i]
                    if v_p: peso_val = Decimal(str(round(float(v_p), 2)))
                if 'talla' in field_to_col:
                    v_t = df_dict[field_to_col['talla']][i]
                    if v_t: talla_val = Decimal(str(round(float(v_t), 1)))
                if 'perimetro' in field_to_col:
                    v_pm = df_dict[field_to_col['perimetro']][i]
                    if v_pm: perim_val = Decimal(str(round(float(v_pm), 1)))

                ant, _ = Anthropometry.objects.get_or_create(visit=visit, defaults={
                    "weight_kg": peso_val or Decimal("70.00"),
                    "height_cm": talla_val or Decimal("170.0"),
                    "waist_circumference_cm": perim_val or Decimal("85.0")
                })
                if peso_val: ant.weight_kg = peso_val
                if talla_val: ant.height_cm = talla_val
                if perim_val: ant.waist_circumference_cm = perim_val
                ant.save()

                # 6. Signos Vitales
                tas_val = 120
                tad_val = 80
                sat_val = 98
                fc_val = 72
                if 'tas' in field_to_col:
                    v_tas = df_dict[field_to_col['tas']][i]
                    if v_tas:
                        try: tas_val = int(float(v_tas))
                        except Exception: pass
                if 'tad' in field_to_col:
                    v_tad = df_dict[field_to_col['tad']][i]
                    if v_tad:
                        try: tad_val = int(float(v_tad))
                        except Exception: pass
                if 'sat_o2' in field_to_col:
                    v_sat = df_dict[field_to_col['sat_o2']][i]
                    if v_sat:
                        try: sat_val = int(float(v_sat))
                        except Exception: pass
                if 'fc' in field_to_col:
                    v_fc = df_dict[field_to_col['fc']][i]
                    if v_fc:
                        try: fc_val = int(float(v_fc))
                        except Exception: pass

                vs, _ = VitalSigns.objects.get_or_create(visit=visit, defaults={
                    "systolic_bp": tas_val,
                    "diastolic_bp": tad_val,
                    "oxygen_saturation": sat_val,
                    "heart_rate": fc_val
                })
                vs.systolic_bp = tas_val
                vs.diastolic_bp = tad_val
                vs.oxygen_saturation = sat_val
                vs.heart_rate = fc_val

                # Soplos
                if 'soplos' in field_to_col:
                    v_sop = df_dict[field_to_col['soplos']][i]
                    _, sop_lbl = _get_val_and_label(v_sop, meta.variable_value_labels.get(field_to_col['soplos'], {}))
                    sop_str = sop_lbl.lower()
                    vs.systolic_murmur = 'sist' in sop_str
                    vs.diastolic_murmur = 'diast' in sop_str
                    # Grado
                    m_grade = re.search(r'grado\s*([1-4])', sop_str)
                    if m_grade:
                        vs.murmur_grade = int(m_grade.group(1))

                # Auscultaciones y pulsos
                if 'resp_normal' in field_to_col:
                    v_rn = df_dict[field_to_col['resp_normal']][i]
                    vs.pulmonary_auscultation_normal = (v_rn == 1.0 or v_rn is None)
                if 'abdom_normal' in field_to_col:
                    v_an = df_dict[field_to_col['abdom_normal']][i]
                    vs.abdominal_auscultation_normal = (v_an == 1.0 or v_an is None)
                if 'pulsos' in field_to_col:
                    v_pu = df_dict[field_to_col['pulsos']][i]
                    vs.pedal_pulses_symmetric = (v_pu == 1.0 or v_pu is None)
                vs.save()

                # 7. ECG
                ecg, _ = Electrocardiogram.objects.get_or_create(visit=visit, defaults={"rhythm": rhythm_default})
                ecg.heart_rate = fc_val
                if 'ecg_ritmo' in field_to_col:
                    v_r = df_dict[field_to_col['ecg_ritmo']][i]
                    _, r_lbl = _get_val_and_label(v_r, meta.variable_value_labels.get(field_to_col['ecg_ritmo'], {}))
                    if r_lbl:
                        r_obj = EcgRhythm.objects.filter(name__icontains=r_lbl[:10]).first()
                        if r_obj: ecg.rhythm = r_obj

                if 'ecg_pr' in field_to_col:
                    v_pr = df_dict[field_to_col['ecg_pr']][i]
                    if v_pr:
                        val_num = float(v_pr)
                        ecg.pr_interval_ms = int(val_num * 1000) if val_num < 1.0 else int(val_num)

                if 'ecg_qrs' in field_to_col:
                    v_qrs = df_dict[field_to_col['ecg_qrs']][i]
                    if v_qrs:
                        val_num = float(v_qrs)
                        ecg.qrs_duration_ms = int(val_num * 1000) if val_num < 1.0 else int(val_num)

                if 'ecg_qt' in field_to_col:
                    v_qt = df_dict[field_to_col['ecg_qt']][i]
                    if v_qt:
                        val_num = float(v_qt)
                        ecg.qt_interval_ms = int(val_num * 1000) if val_num < 1.0 else int(val_num)

                if 'ecg_qtc' in field_to_col:
                    v_qtc = df_dict[field_to_col['ecg_qtc']][i]
                    if v_qtc: ecg.qtc_bazett_ms = int(float(v_qtc))

                if 'ecg_eje' in field_to_col:
                    v_eje = df_dict[field_to_col['ecg_eje']][i]
                    if v_eje: ecg.qrs_axis_degrees = int(float(v_eje))

                if 'ecg_hvi' in field_to_col:
                    v_hvi = df_dict[field_to_col['ecg_hvi']][i]
                    ecg.left_ventricular_hypertrophy = (v_hvi == 1.0)

                if 'ecg_bloqueo' in field_to_col:
                    v_bl = df_dict[field_to_col['ecg_bloqueo']][i]
                    _, bl_lbl = _get_val_and_label(v_bl, meta.variable_value_labels.get(field_to_col['ecg_bloqueo'], {}))
                    if bl_lbl: ecg.bundle_branch_block = bl_lbl[:50]
                ecg.save()

                # 8. Laboratorio
                lab, _ = Laboratory.objects.get_or_create(visit=visit)
                lab_mapping_keys = [
                    ('lab_hematies', 'rbc_millions'),
                    ('lab_hemoglobina', 'hemoglobin_g_dl'),
                    ('lab_hematocrito', 'hematocrit_percentage'),
                    ('lab_vcm', 'mcv_fl'),
                    ('lab_leucocitos', 'wbc_thousands'),
                    ('lab_plaquetas', 'platelets_thousands'),
                    ('lab_tiempo_protombina', 'prothrombin_time_sec'),
                    ('lab_glucosa', 'glucose_mg_dl'),
                    ('lab_urea', 'urea_mg_dl'),
                    ('lab_creatinina', 'creatinine_mg_dl'),
                    ('lab_colesterol', 'total_cholesterol_mg_dl'),
                    ('lab_hdl', 'hdl_mg_dl'),
                    ('lab_ldl', 'ldl_mg_dl'),
                    ('lab_trigliceridos', 'triglycerides_mg_dl'),
                    ('lab_got', 'ast_got_u_l'),
                    ('lab_gpt', 'alt_gpt_u_l'),
                    ('lab_ggt', 'ggt_u_l'),
                    ('lab_tsh', 'tsh_u_iu_ml'),
                ]
                for f_lab, model_attr in lab_mapping_keys:
                    if f_lab in field_to_col:
                        val_l = df_dict[field_to_col[f_lab]][i]
                        if val_l is not None:
                            try: setattr(lab, model_attr, Decimal(str(round(float(val_l), 2))))
                            except Exception: pass
                lab.save()

                # 9. Ecocardiograma
                echo, _ = Echocardiogram.objects.get_or_create(visit=visit)
                if 'eco_ddvi' in field_to_col:
                    v_dd = df_dict[field_to_col['eco_ddvi']][i]
                    if v_dd:
                        try: echo.lv_dimension_mm = Decimal(str(round(float(v_dd), 1)))
                        except Exception: pass
                if 'eco_fey' in field_to_col:
                    v_fy = df_dict[field_to_col['eco_fey']][i]
                    if v_fy:
                        try: echo.lvef_percentage = Decimal(str(round(float(v_fy), 1)))
                        except Exception: pass
                if 'eco_hvi' in field_to_col:
                    v_ehvi = df_dict[field_to_col['eco_hvi']][i]
                    echo.ventricular_hypertrophy = (v_ehvi == 1.0)
                if 'eco_disfuncion' in field_to_col:
                    v_dis = df_dict[field_to_col['eco_disfuncion']][i]
                    echo.diastolic_dysfunction = (v_dis == 1.0)
                if 'eco_calcificacion' in field_to_col:
                    v_calc = df_dict[field_to_col['eco_calcificacion']][i]
                    echo.aortic_valve_calcification = (v_calc == 1.0)
                echo.save()

                # 10. Persistencia Universal e Inteligente de TODAS las variables SPSS en VisitAnswer
                # Se asigna cada variable a su QuestionnaireSection exacta y se sincroniza bidireccionalmente con el formulario
                for col_name in col_names:
                    val_raw = df_dict[col_name][i]
                    if val_raw is None or str(val_raw).strip() == '':
                        continue

                    vlabels = meta.variable_value_labels.get(col_name, {})
                    _, text_lbl = _get_val_and_label(val_raw, vlabels)
                    val_str = text_lbl if text_lbl else str(val_raw).strip()

                    clean_code = normalize_var_name(col_name)
                    if not clean_code:
                        continue
                    clean_code = clean_code[:30]

                    target_sec_code = classify_spss_question_section(col_name)
                    target_sec = sections_by_code.get(target_sec_code, default_section)

                    var_label = meta.column_names_to_labels.get(col_name) or col_name
                    q = Question.objects.filter(code=clean_code).first()
                    if not q:
                        q = Question.objects.create(
                            section=target_sec,
                            code=clean_code,
                            text=str(var_label)[:255],
                            response_type=Question.ResponseType.TEXTO,
                            display_order=999
                        )
                    elif q.section != target_sec and q.section == default_section:
                        q.section = target_sec
                        q.save(update_fields=['section'])

                    num_val = None
                    if isinstance(val_raw, (int, float)) and not text_lbl:
                        try:
                            num_val = Decimal(str(round(float(val_raw), 3)))
                            ans_text = None
                        except Exception:
                            num_val = None
                            ans_text = val_str[:250]
                    else:
                        num_val = None
                        ans_text = val_str[:250]

                    VisitAnswer.objects.update_or_create(
                        visit=visit,
                        question=q,
                        defaults={
                            "text_value": ans_text,
                            "numeric_value": num_val,
                            "selected_option": None
                        }
                    )

                    # Sincronización cruzada con identificadores del formulario HTML
                    for form_k, spss_k in SPSS_QUESTION_ALIASES.items():
                        if spss_k == clean_code:
                            q_form = Question.objects.filter(code=form_k).first()
                            if not q_form:
                                q_form = Question.objects.create(
                                    section=target_sec,
                                    code=form_k,
                                    text=f"Campo {form_k}",
                                    response_type=Question.ResponseType.TEXTO,
                                    display_order=999
                                )
                            VisitAnswer.objects.update_or_create(
                                visit=visit,
                                question=q_form,
                                defaults={
                                    "text_value": ans_text,
                                    "numeric_value": num_val,
                                    "selected_option": None
                                }
                            )

                # Descomposición y derivación inteligente de preguntas compuestas para el formulario web:
                def _set_derived_ans(q_code, q_val, sec_cd):
                    sec_obj = sections_by_code.get(sec_cd, default_section)
                    q_d = Question.objects.filter(code=q_code).first()
                    if not q_d:
                        q_d = Question.objects.create(
                            section=sec_obj,
                            code=q_code,
                            text=f"Campo {q_code}",
                            response_type=Question.ResponseType.TEXTO,
                            display_order=999
                        )
                    VisitAnswer.objects.update_or_create(
                        visit=visit,
                        question=q_d,
                        defaults={"text_value": q_val, "numeric_value": None, "selected_option": None}
                    )

                # 1. Estrés laboral y familiar
                estres_raw = str(df_dict.get('ESTRES', [None]*total_rows)[i] or '').upper()
                if 'TRABAJO' in estres_raw:
                    _set_derived_ans('em_estres_trab', 'Si', 'MOD_3_FACTORES_EMERG')
                elif estres_raw and 'NO' in estres_raw:
                    _set_derived_ans('em_estres_trab', 'No', 'MOD_3_FACTORES_EMERG')
                if 'FAMILIAR' in estres_raw or 'FAMILIA' in estres_raw:
                    _set_derived_ans('em_estres_fam', 'Si', 'MOD_3_FACTORES_EMERG')
                elif estres_raw and 'NO' in estres_raw:
                    _set_derived_ans('em_estres_fam', 'No', 'MOD_3_FACTORES_EMERG')

                # 2. Personalidad Tipo A
                pers_raw = str(df_dict.get('PERSONALIDAD_TIPO_A', [None]*total_rows)[i] or '').upper()
                if 'TIPO A' in pers_raw or 'SI' in pers_raw:
                    _set_derived_ans('em_pers_a', 'Si', 'MOD_3_FACTORES_EMERG')
                elif pers_raw and 'NO' in pers_raw:
                    _set_derived_ans('em_pers_a', 'No', 'MOD_3_FACTORES_EMERG')

                # 3. Antecedentes Padres
                padre_raw = str(df_dict.get('ANTECEDENTES_PADRES', [None]*total_rows)[i] or '').upper()
                if padre_raw:
                    _set_derived_ans('ant_padre_hta', 'Si' if 'HTA' in padre_raw else 'No', 'MOD_3_ANTECEDENTES_FAM')
                    _set_derived_ans('ant_padre_dm', 'Si' if ('DIAB' in padre_raw or 'DM' in padre_raw) else 'No', 'MOD_3_ANTECEDENTES_FAM')
                    _set_derived_ans('ant_padre_iam', 'Si' if ('INFARTO' in padre_raw or 'IAM' in padre_raw) else 'No', 'MOD_3_ANTECEDENTES_FAM')
                    _set_derived_ans('ant_padre_ictus', 'Si' if ('ICTUS' in padre_raw or 'ACV' in padre_raw) else 'No', 'MOD_3_ANTECEDENTES_FAM')

                # 4. Antecedentes Madres
                madre_raw = str(df_dict.get('ANTECEDENTES_MADRES', [None]*total_rows)[i] or '').upper()
                if madre_raw:
                    _set_derived_ans('ant_madre_hta', 'Si' if 'HTA' in madre_raw else 'No', 'MOD_3_ANTECEDENTES_FAM')
                    _set_derived_ans('ant_madre_dm', 'Si' if ('DIAB' in madre_raw or 'DM' in madre_raw) else 'No', 'MOD_3_ANTECEDENTES_FAM')
                    _set_derived_ans('ant_madre_iam', 'Si' if ('INFARTO' in madre_raw or 'IAM' in madre_raw) else 'No', 'MOD_3_ANTECEDENTES_FAM')
                    _set_derived_ans('ant_madre_ictus', 'Si' if ('ICTUS' in madre_raw or 'ACV' in madre_raw) else 'No', 'MOD_3_ANTECEDENTES_FAM')

                # 5. COVID-19
                covid_raw = str(df_dict.get('HISTORIA_COVID', [None]*total_rows)[i] or '').upper()
                if covid_raw:
                    _set_derived_ans('covid_paso', 'Si' if ('SI' in covid_raw or covid_raw == '1.0') else 'No', 'MOD_4_COVID')
                hosp_raw = str(df_dict.get('AFECTACION_COVID', [None]*total_rows)[i] or '').upper()
                if 'HOSPITAL' in hosp_raw or 'INGRESO' in hosp_raw:
                    _set_derived_ans('covid_ingreso', 'Si', 'MOD_4_COVID')
                long_raw = str(df_dict.get('LONG_COVID', [None]*total_rows)[i] or '').upper()
                if long_raw:
                    _set_derived_ans('longcovid', 'Si' if ('SI' in long_raw or long_raw == '1.0') else 'No', 'MOD_4_COVID')

                # 6. PREDIMED (Dieta Mediterránea)
                oliva_raw = str(df_dict.get('USA_USTED_ACEITE_DE_OLIVA', [None]*total_rows)[i] or '').upper()
                if oliva_raw:
                    is_ol = 'Si' if ('SI' in oliva_raw or oliva_raw == '1.0') else 'No'
                    _set_derived_ans('pred_q1', is_ol, 'MOD_6_PREDIMED')
                    _set_derived_ans('pred_q2', is_ol, 'MOD_6_PREDIMED')

                # 7. Actividad Física
                act_raw = str(df_dict.get('USTED_REALIZA_ACTIVIDAD_FISICA', [None]*total_rows)[i] or '').upper()
                if act_raw:
                    _set_derived_ans('act_realiza', 'Si' if ('SI' in act_raw or act_raw == '1.0') else 'No', 'MOD_6_ACTIVIDAD_FISICA')

                aer_raw = str(df_dict.get('USTED_REALIZA_EJERCICIOS_AEROBICOS', [None]*total_rows)[i] or '').upper()
                if aer_raw:
                    _set_derived_ans('act_aerob', 'Si' if ('SI' in aer_raw or aer_raw == '1.0') else 'No', 'MOD_6_ACTIVIDAD_FISICA')

                ana_raw = str(df_dict.get('USTED_REALIZA_EJERCICIOS_ANAEROBICOS', [None]*total_rows)[i] or '').upper()
                if ana_raw:
                    _set_derived_ans('act_anaerob', 'Si' if ('SI' in ana_raw or ana_raw == '1.0') else 'No', 'MOD_6_ACTIVIDAD_FISICA')

                dep_raw = str(df_dict.get('HACE_DEPORTE', [None]*total_rows)[i] or '').upper()
                if dep_raw:
                    _set_derived_ans('act_deporte', 'Si' if ('SI' in dep_raw or dep_raw == '1.0') else 'No', 'MOD_6_ACTIVIDAD_FISICA')


        except Exception as e:
            errors.append(f"Fila {i + 1} (Código {study_code if 'study_code' in locals() else i + 1}): {str(e)}")

        # Registrar auditoria global de la importacion
        if ChangeLog and user:
            try:
                import json
                ChangeLog.objects.create(
                    user=user,
                    schema_name='clinical',
                    table_name='visit',
                    record_key='import_sav',
                    action='INSERT',
                    new_value=json.dumps({
                        'event': 'import_sav',
                        'total_rows': total_rows,
                        'created_patients': created_count,
                        'updated_patients': updated_count,
                        'error_count': len(errors)
                    }),
                    status=ChangeLog.Status.RECORDED
                )
            except Exception:
                pass

    # Limpiar archivo temporal
    if temp_path.exists():
        try: temp_path.unlink()
        except Exception: pass

    return {
        "success": True,
        "total_rows": total_rows,
        "imported_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "errors": errors[:10],
        "message": f"Se procesaron con éxito {total_rows} registros ({created_count} nuevos creados, {updated_count} actualizados, {skipped_count} omitidos)."
    }
