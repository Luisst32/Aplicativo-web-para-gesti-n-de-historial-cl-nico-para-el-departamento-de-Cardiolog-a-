"""
Dashboard Analytics and Clinical Aggregation Service Layer.

Computes epidemiological and clinical risk metrics dynamically from PostgreSQL ORM models:
- clinical.models.Visit
- clinical.models.Patient
- clinical.models.Anthropometry
- clinical.models.VitalSigns
- clinical.models.Laboratory
- clinical.models.Electrocardiogram
- clinical.models.VisitAnswer

Incorporates the 8 core clinical modules requested for epidemiological analysis:
1. Datos del individuo (Sociodemografía y filiación)
2. Exploración física (Antropometría, signos vitales y auscultación)
3. Factores de riesgo modificables (HTA, Diabetes, Dislipemia, Hábitos, Dieta)
4. Factores emergentes (Sueño, Estrés, Clima laboral, Personalidad Tipo A, Tóxicos)
5. Antecedentes familiares (Carga genética cardiovascular en padres)
6. Historia clínica no cardiovascular (Respiratorio, Salud mental, Reumatología, Cáncer)
7. COVID-19 y Secuelas (Infección, Gravedad, Secuelas post-COVID)
8. Resultados del electrocardiograma (Ritmo, Arritmias, Intervalos, Bloqueos, Repolarización)
"""

import re
from datetime import date
from django.db.models import Prefetch

from catalog.institutions import filter_to_selectable_institutions, selectable_institutions
from clinical.models import Visit, VisitAnswer
from clinical.services.covid_answers import resolve_covid
from .boolean_answers import recorded_answers, descriptors


def get_age(birth_date, ref_date):
    """Calculates age in years at evaluation date."""
    if not birth_date:
        return 0
    if not ref_date:
        ref_date = date.today()
    return ref_date.year - birth_date.year - ((ref_date.month, ref_date.day) < (birth_date.month, birth_date.day))


def get_age_group(age):
    """Classifies age into standard epidemiological cohorts."""
    if age < 40:
        return '<40 años'
    elif age < 50:
        return '40-49 años'
    elif age < 60:
        return '50-59 años'
    else:
        return '60+ años'


def map_category_label(cat_name):
    """Normalizes staff category into canonical cohort labels."""
    if not cat_name:
        return 'Personal de Servicios'
    cat_upper = cat_name.upper()
    if 'PDI' in cat_upper or 'DOCENTE' in cat_upper:
        return 'PDI (Docentes)'
    if 'PAS' in cat_upper or 'ADMIN' in cat_upper:
        return 'Código de trabajo'
    if 'SERVICIO' in cat_upper:
        return 'Personal de Servicios'
    if 'ESTUDIANTE' in cat_upper:
        return 'Estudiantes'
    return cat_name


def _es_negativo(texto):
    """Verifica si una respuesta textual clínica expresa un valor negativo o ausencia de patología."""
    if texto is None or str(texto).strip() == '':
        return False
    t = str(texto).strip().lower()
    if t in ('no', '0', '0.0', 'false', 'negativo', 'sin', 'ninguno', 'ninguna', 'no fuma', 'no bloqueo'):
        return True
    if (
        re.match(r'^(no|false|0(\.0)?|ningun[oa]s?|sin)\b', t) or
        t.startswith((
            'no tiene', 'no presenta', 'no realiza', 'no consume',
            'no ha pasado', 'no presentó', 'no tuvo', 'no fuma', 'no bloqueo',
            'sin antecedentes', 'sin patología', 'sin ingreso', 'sin trastorno'
        ))
    ):
        return True
    return False


def _answer(answers, *codes):
    """Return the first recorded non-empty answer without inventing a fallback."""
    for code in codes:
        if code in answers and answers[code] in (None, ''):
            return None
        value = answers.get(code)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _numeric_answer(numeric_answers, answers, *codes):
    """Read a numeric questionnaire value without treating blanks as zero."""
    for code in codes:
        if code in numeric_answers:
            return numeric_answers[code]
        value = answers.get(code)
        if value is None or not str(value).strip():
            continue
        try:
            return float(str(value).strip().replace(',', '.'))
        except (TypeError, ValueError):
            continue
    return None


def _affirmative(value):
    """Return True/False for a recorded yes/no answer, otherwise None."""
    if value is None or str(value).strip() == '':
        return None
    text = str(value).strip().lower()
    if text in ('1', '1.0', 'true', 'positivo'):
        return True
    if _es_negativo(text):
        return False
    if (
        re.search(r'^(s[ií]|true|1(\.0)?)\b', text, re.I) or
        text.startswith(('si ', 'sí ', 'si,', 'sí,', 'si em', 'si en', 'si realiza'))
    ):
        return True
    return None



def _any_known(*values):
    """Merge a direct clinical answer with corroborating evidence.

    Positive evidence wins; otherwise an explicit negative remains usable even
    when a secondary measurement was not recorded.
    """
    if any(value is True for value in values):
        return True
    if any(value is False for value in values):
        return False
    return None


def _fully_known_or(*values):
    """Return an OR result only when positive or when every source is negative."""
    if any(value is True for value in values):
        return True
    if values and all(value is False for value in values):
        return False
    return None


def _mental_condition(individual_value, summary_value, condition):
    """Resolve one mental-health condition without masking its explicit answer.

    Older records can contain both the combined ``salud_mental`` answer and
    the individual ``nc_depresion`` / ``nc_ansiedad`` fields.
    """
    individual = _affirmative(individual_value)
    if individual is not None:
        return individual

    val = individual_value or summary_value
    if val is None or str(val).strip() == '':
        return None

    low = str(val).strip().lower()
    if _es_negativo(low) or 'no tiene' in low or 'ningun' in low:
        return False
    if 'ambas' in low:
        return True
    if condition in low:
        return True
    if condition == 'depresi' and 'ansiedad' in low:
        return False
    if condition == 'ansied' and 'depresi' in low:
        return False
    return None


def get_dashboard_evaluation_data():
    """
    Extracts all clinical encounters and generates normalized, calculated
    evaluation records across all 8 clinical blocks for dynamic client-side
    and server-side aggregation.
    """
    visits = (
        Visit.objects.select_related(
            'patient',
            'patient__sex',
            'patient__ethnicity',
            'patient__institution',
            'patient__birth_canton',
            'staff_category',
            'professional_category',
            'education_level',
            'income_range',
            'marital_status',
            'housing_type',
            'living_situation',
            'work_schedule',
            'residence_canton',
            'anthropometry',
            'vital_signs',
            'laboratory',
            'electrocardiogram__rhythm',
            'echocardiogram', 'ordered_studies',
        )
        .prefetch_related(
            Prefetch(
                'answers',
                queryset=VisitAnswer.objects.select_related('question', 'selected_option')
            )
        )
        .all()
        .order_by('visit_id')
    )
    visits = filter_to_selectable_institutions(visits, 'patient__institution')

    records = []
    available_years = set()
    available_categories = set()

    for v in visits:
        p = v.patient
        v_date = v.visit_date or date(2024, 1, 1)
        ano = v_date.year
        available_years.add(ano)

        inst_name = p.institution.name if (p and p.institution) else ''

        # -------------------------------------------------------------
        # BLOQUE 1: DATOS DEL INDIVIDUO (SOCIODEMOGRAFÍA)
        # -------------------------------------------------------------
        sex_raw = p.sex.name if (p and p.sex) else None
        if sex_raw:
            s_upper = sex_raw.upper()
            if 'MUJER' in s_upper or 'FEM' in s_upper:
                sexo = 'Mujer'
            elif 'HOMBRE' in s_upper or 'MASC' in s_upper:
                sexo = 'Hombre'
            else:
                sexo = None
        else:
            sexo = None

        cat_raw = v.staff_category.name if v.staff_category else ''
        categoria = map_category_label(cat_raw)
        available_categories.add(categoria)

        # Respuestas del cuestionario asociadas
        answers_dict = {}
        numeric_answers = {}
        for a in v.answers.all():
            q_code = a.question.code.lower()
            val = a.selected_option.label if a.selected_option else (a.text_value if a.text_value is not None else a.numeric_value)
            answers_dict[q_code] = str(val).strip() if val is not None else ''
            if a.numeric_value is not None:
                try:
                    numeric_answers[q_code] = float(a.numeric_value)
                except (ValueError, TypeError):
                    pass

        # Resolución de edad con validación de plausibilidad biológica (15 - 110 años)
        # y fallback automático a la edad numérica reportada en el cuestionario clínico
        edad_calc = get_age(p.birth_date, v_date)
        edad_ans = numeric_answers.get('edad') or numeric_answers.get('f_edad')
        if edad_calc and 15 <= edad_calc <= 110:
            edad = int(edad_calc)
        elif edad_ans and 15 <= edad_ans <= 110:
            edad = int(edad_ans)
        elif edad_calc > 110 and edad_ans:
            edad = int(edad_ans)
        elif edad_calc:
            edad = int(edad_calc)
        else:
            edad = int(edad_ans) if edad_ans else 0
        grupo_edad = get_age_group(edad) if edad else 'Sin dato'

        # Estado civil
        estado_civil_val = v.marital_status.name if v.marital_status else answers_dict.get('f_estado_civil', 'No especificado')
        if 'CASAD' in estado_civil_val.upper():
            estado_civil = 'Casado/a'
        elif 'SOLTER' in estado_civil_val.upper():
            estado_civil = 'Soltero/a'
        elif 'DIVORC' in estado_civil_val.upper():
            estado_civil = 'Divorciado/a'
        elif 'VIUD' in estado_civil_val.upper():
            estado_civil = 'Viudo/a'
        elif 'UNION' in estado_civil_val.upper() or 'LIBRE' in estado_civil_val.upper():
            estado_civil = 'Unión libre'
        else:
            estado_civil = estado_civil_val or 'No especificado'

        # Nivel educativo
        estudios_val = v.education_level.name if v.education_level else _answer(answers_dict, 'f_estudios')
        if not estudios_val:
            nivel_estudios = 'Sin dato'
        elif 'POST' in estudios_val.upper() or 'CUARTO' in estudios_val.upper() or 'MASTER' in estudios_val.upper() or 'DOCTOR' in estudios_val.upper():
            nivel_estudios = 'Postgrado'
        elif 'SUPERIOR' in estudios_val.upper() or 'TERCER' in estudios_val.upper() or 'UNIVERSIT' in estudios_val.upper():
            nivel_estudios = 'Superior'
        elif 'SECUNDAR' in estudios_val.upper() or 'BACHILLER' in estudios_val.upper():
            nivel_estudios = 'Secundaria'
        else:
            nivel_estudios = 'Primaria/Otros'

        # Tipo de vivienda
        vivienda_val = v.housing_type.name if v.housing_type else _answer(answers_dict, 'f_vivienda')
        if not vivienda_val:
            tipo_vivienda = 'Sin dato'
        elif 'PROPIA' in vivienda_val.upper():
            tipo_vivienda = 'Propia'
        elif 'FAMILIAR' in vivienda_val.upper():
            tipo_vivienda = 'Familiar'
        elif 'ALQUIL' in vivienda_val.upper():
            tipo_vivienda = 'Alquilada'
        else:
            tipo_vivienda = 'Otra'

        # Rango de ingresos
        ingresos_val = v.income_range.name if v.income_range else _answer(answers_dict, 'f_ingresos', 'ingresos_totales_mensuales')
        rango_ingresos = ingresos_val if ingresos_val else None

        canton = v.residence_canton.name if v.residence_canton else (p.birth_canton.name if (p and p.birth_canton) else 'Milagro')
        facultad = v.faculty or 'Salud y Servicios Sociales'

        # -------------------------------------------------------------
        # BLOQUE 2: EXPLORACIÓN FÍSICA (ANTROPOMETRÍA Y SIGNOS VITALES)
        # -------------------------------------------------------------
        anth = getattr(v, 'anthropometry', None)
        peso = float(anth.weight_kg) if anth and anth.weight_kg else None
        talla = float(anth.height_cm) if anth and anth.height_cm else None

        imc = float(anth.bmi) if anth and anth.bmi is not None else None
        if anth and peso and talla and peso > 0 and talla > 0 and not imc:
            h_m = talla / 100.0
            if h_m > 0:
                imc = round(peso / (h_m * h_m), 2)

        if imc is None:
            imc_cat = 'Sin dato'
        elif imc < 18.5:
            imc_cat = 'Bajo peso'
        elif imc < 25.0:
            imc_cat = 'Normal'
        elif imc < 30.0:
            imc_cat = 'Sobrepeso'
        elif imc < 35.0:
            imc_cat = 'Obesidad I'
        elif imc < 40.0:
            imc_cat = 'Obesidad II'
        else:
            imc_cat = 'Obesidad Mórbida'

        obesidad = imc >= 30.0 if imc is not None else None
        sobrepeso_u_obesidad = imc >= 25.0 if imc is not None else None

        perimetro_abdominal = float(anth.waist_circumference_cm) if anth and anth.waist_circumference_cm is not None else None
        if perimetro_abdominal and sexo:
            if sexo == 'Mujer':
                if perimetro_abdominal < 80.0:
                    abd_riesgo = 'Normal (<80)'
                elif perimetro_abdominal <= 88.0:
                    abd_riesgo = 'Riesgo Medio (80-88)'
                else:
                    abd_riesgo = 'Riesgo Elevado (>88)'
            else:
                if perimetro_abdominal < 94.0:
                    abd_riesgo = 'Normal (<94)'
                elif perimetro_abdominal <= 102.0:
                    abd_riesgo = 'Riesgo Medio (94-102)'
                else:
                    abd_riesgo = 'Riesgo Elevado (>102)'
        else:
            abd_riesgo = 'Sin dato'

        vs = getattr(v, 'vital_signs', None)
        tas = (
            float(vs.systolic_bp)
            if vs and vs.systolic_bp is not None
            else _numeric_answer(
                numeric_answers,
                answers_dict,
                'f_tas', 'tas_ts', 'tas', 'pa_sistolica', 'sistolica',
            )
        )
        tad = (
            float(vs.diastolic_bp)
            if vs and vs.diastolic_bp is not None
            else _numeric_answer(
                numeric_answers,
                answers_dict,
                'f_tsi', 'tas_mmhg', 'tad_mmhg', 'tad', 'pa_diastolica', 'presion_diastolica',
            )
        )
        fc = (
            int(vs.heart_rate)
            if vs and vs.heart_rate is not None
            else _numeric_answer(
                numeric_answers,
                answers_dict,
                'f_fc', 'frecuencia_cardiaca_ipm', 'fc', 'frecuencia_cardiaca', 'pulso',
            )
        )
        sat_o2 = int(vs.oxygen_saturation) if vs and vs.oxygen_saturation is not None else None

        # Clasificación de presión: usa ambas medidas cuando existen; si falta
        # una, conserva la estratificación de la medida realmente observada.
        if tas is not None and tas > 0 and tad is not None and tad > 0:
            if tas >= 160.0 or tad >= 100.0:
                pa_categoria = 'HTA Grado 2 (≥160/100)'
            elif tas >= 140.0 or tad >= 90.0:
                pa_categoria = 'HTA Grado 1 (140-159/90-99)'
            elif tas >= 130.0 or tad >= 80.0:
                pa_categoria = 'PA Elevada (130-139/80-89)'
            else:
                pa_categoria = 'PA Normal (<130/<80)'
        elif tas is not None and tas > 0:
            if tas >= 160.0:
                pa_categoria = 'HTA Grado 2 (TAS ≥160)'
            elif tas >= 140.0:
                pa_categoria = 'HTA Grado 1 (TAS 140-159)'
            elif tas >= 130.0:
                pa_categoria = 'PA Elevada (TAS 130-139)'
            else:
                pa_categoria = 'PA Normal (TAS <130)'
        elif tad is not None and tad > 0:
            if tad >= 100.0:
                pa_categoria = 'HTA Grado 2 (TAD ≥100)'
            elif tad >= 90.0:
                pa_categoria = 'HTA Grado 1 (TAD 90-99)'
            elif tad >= 80.0:
                pa_categoria = 'PA Elevada (TAD 80-89)'
            else:
                pa_categoria = 'PA Normal (TAD <80)'
        elif tas is None and tad is None:
            pa_categoria = 'Sin dato'
        else:
            pa_categoria = 'No registrada'

        # Hallazgos auscultatorios
        soplos = _fully_known_or(vs.systolic_murmur, vs.diastolic_murmur) if vs else None
        soplo_grado = int(vs.murmur_grade) if vs and vs.murmur_grade else 0
        ausc_pulm_normal = vs.pulmonary_auscultation_normal if vs else None
        ausc_abdom_normal = vs.abdominal_auscultation_normal if vs else None

        # -------------------------------------------------------------
        # BLOQUE 3: FACTORES DE RIESGO MODIFICABLES
        # -------------------------------------------------------------
        # Hipertensión (HTA)
        r_hta_val = _answer(answers_dict, 'r_hta', 'hipertension', 'hta', 'hta_tto')
        is_hta_ans = _affirmative(r_hta_val)
        if (tas is not None and tas >= 140.0) or (tad is not None and tad >= 90.0):
            is_hta_bp = True
        elif tas is not None and tad is not None:
            is_hta_bp = False
        else:
            is_hta_bp = None
        # Diagnóstico clínico oficial de HTA (anamnesis)
        hipertension = _any_known(is_hta_ans, is_hta_bp)
        # PA elevada en consulta física (variable independiente)
        pa_elevada_consulta = is_hta_bp

        if r_hta_val and 'no tratada' in r_hta_val.lower():
            hta_desc = 'No tratada'
        elif r_hta_val and ('tratada con farmacos' in r_hta_val.lower() or 'si tratada' in r_hta_val.lower() or 'y si tratada' in r_hta_val.lower()):
            hta_desc = 'Tratada'
        elif hipertension is True:
            hta_desc = 'No tratada'
        elif hipertension is False:
            hta_desc = 'Sin Hipertensión'
        else:
            hta_desc = 'Sin dato'

        # Diabetes Mellitus
        lab = getattr(v, 'laboratory', None)
        glucosa = (
            float(lab.glucose_mg_dl)
            if lab and lab.glucose_mg_dl is not None
            else _numeric_answer(
                numeric_answers,
                answers_dict,
                'diab_glucosa', 'lab_glucosa', 'glucosa_sangre', 'glucosa',
            )
        )
        hba1c = _numeric_answer(
            numeric_answers,
            answers_dict,
            'diab_hba1c', 'lab_hba1c', 'hemoglobina_glicosilada', 'hba1c',
        )
        r_dm_val = _answer(answers_dict, 'r_dm', 'diabetes_mellitus', 'dm', 'diab_glucosa')
        is_dm_ans = _affirmative(r_dm_val)
        is_dm_lab = glucosa >= 126.0 if glucosa is not None else None
        # Diagnóstico clínico oficial de DM (anamnesis)
        is_dm_hba1c = hba1c >= 6.5 if hba1c is not None else None
        diabetes_lab = _fully_known_or(is_dm_lab, is_dm_hba1c)
        diabetes = _any_known(is_dm_ans, diabetes_lab)
        if r_dm_val and 'tratada' in r_dm_val.lower():
            db_desc = 'Tipo 2 tratada'
        elif diabetes is True:
            db_desc = 'Diabetes diagnosticada'
        elif diabetes is False:
            db_desc = 'No'
        else:
            db_desc = 'Sin dato'

        # Dislipemia
        col_total = float(lab.total_cholesterol_mg_dl) if lab and lab.total_cholesterol_mg_dl is not None else None
        col_ldl = float(lab.ldl_mg_dl) if lab and lab.ldl_mg_dl is not None else None
        triglic = float(lab.triglycerides_mg_dl) if lab and lab.triglycerides_mg_dl is not None else None

        r_dl_val = _answer(answers_dict, 'r_dislip', 'dislipemia', 'r_dislipemia')
        is_dl_ans = _affirmative(r_dl_val)
        lipid_values = (col_total, col_ldl, triglic)
        available_lipids = [value for value in lipid_values if value is not None]
        if not available_lipids:
            is_dl_lab = None
        elif (
            (col_total is not None and col_total >= 200.0)
            or (col_ldl is not None and col_ldl >= 130.0)
            or (triglic is not None and triglic >= 150.0)
        ):
            is_dl_lab = True
        elif len(available_lipids) == len(lipid_values):
            is_dl_lab = False
        else:
            is_dl_lab = None
        # Diagnóstico clínico oficial de Dislipemia si existe anamnesis; si no fue evaluada, laboratorio
        dislipemia = _any_known(is_dl_ans, is_dl_lab)
        dislipemia_lab = is_dl_lab

        if r_dl_val and 'no tratada' in r_dl_val.lower():
            dl_desc = 'No tratada'
        elif r_dl_val and 'tratada' in r_dl_val.lower():
            dl_desc = 'Tratada'
        elif dislipemia is True:
            dl_desc = 'No tratada'
        elif dislipemia is False:
            dl_desc = 'No'
        else:
            dl_desc = 'Sin dato'

        # Tabaquismo
        r_tab_val = _answer(answers_dict, 'r_tabaco', 'tabaquismo')
        if r_tab_val is None:
            tabaquismo = 'Sin dato'
            fumador_activo = None
        elif 'no fuma' in r_tab_val.lower():
            tabaquismo = 'No fuma'
            fumador_activo = False
        elif 'ex' in r_tab_val.lower():
            tabaquismo = 'Exfumador'
            fumador_activo = False
        elif 'si' in r_tab_val.lower() or 'sí' in r_tab_val.lower() or 'activo' in r_tab_val.lower():
            tabaquismo = 'Fumador Activo'
            fumador_activo = True
        else:
            tabaquismo = 'No fuma'
            fumador_activo = False

        # Alcohol
        r_alc_val = _answer(answers_dict, 'r_alcohol', 'alcohol')
        if r_alc_val is None:
            alcohol = 'Sin dato'
        elif 'diario' in r_alc_val.lower() or 'diariamente' in r_alc_val.lower():
            alcohol = 'Diario'
        elif 'semanal' in r_alc_val.lower() or 'semanalmente' in r_alc_val.lower():
            alcohol = 'Semanal'
        elif 'ocasional' in r_alc_val.lower():
            alcohol = 'Ocasional'
        else:
            alcohol = 'No consume'

        # Consumo de drogas: distinguir uso actual, exconsumo y ausencia.
        r_drogas_val = _answer(answers_dict, 'r_drogas', 'drogas')
        drogas_freq_val = _answer(answers_dict, 'drogas_frecuencia')
        ex_drogas_val = _answer(answers_dict, 'chk_ex_drogas')
        drogas_text = ' '.join(
            str(value).strip().lower()
            for value in (r_drogas_val, drogas_freq_val, ex_drogas_val)
            if value is not None and str(value).strip()
        )
        ex_drogas_text = str(ex_drogas_val or '').strip().lower()
        ex_drogas = (
            'ex consumidor' in drogas_text
            or ex_drogas_text in {'on', 'checked', 'true', '1', '1.0', 'si', 'sí'}
        )
        if _es_negativo(r_drogas_val):
            drogas = 'Ex consumidor' if ex_drogas else 'No consume'
        elif 'diari' in drogas_text:
            drogas = 'Diario'
        elif 'seman' in drogas_text:
            drogas = 'Semanal'
        elif 'ocasional' in drogas_text:
            drogas = 'Ocasional'
        elif ex_drogas:
            drogas = 'Ex consumidor'
        elif _affirmative(r_drogas_val) is True:
            drogas = 'Activo'
        else:
            drogas = None

        # Actividad Física y Deporte
        r_act_val = _answer(answers_dict, 'usted_realiza_actividad_fisica', 'actividad_fisica', 'af_camina', 'af_aerobicos')
        actividad_fisica = _affirmative(r_act_val)
        r_dep_val = _answer(answers_dict, 'af_deporte')
        deporte = _affirmative(r_dep_val)

        # Hígado Graso
        r_hg_val = (
            answers_dict.get('r_higado', '') or
            answers_dict.get('higado_graso', '') or
            answers_dict.get('res_higado_graso', '')
        )
        higado_graso = _affirmative(r_hg_val) if r_hg_val else None
        vasculopatia_periferica = _affirmative(_answer(answers_dict, 'r_vasc_perif'))
        vasculopatia_carotidea = _affirmative(_answer(answers_dict, 'r_vasc_carot'))
        vasculopatia_femoral = _affirmative(_answer(answers_dict, 'r_vasc_fem', 'r_vasc_femoral'))
        vasculopatia_values = (vasculopatia_periferica, vasculopatia_carotidea, vasculopatia_femoral)
        vasculopatia_directa = _answer(answers_dict, 'r_vasculopatia', 'vasculopatia')
        vasculopatia_cualquiera = (
            _affirmative(vasculopatia_directa)
            if vasculopatia_directa is not None
            else _fully_known_or(*vasculopatia_values)
        )
        disfuncion_erectil = _affirmative(_answer(answers_dict, 'r_disfunc'))

        # Dieta PREDIMED (Adherencia a Dieta Mediterránea)
        consume_fruta = _affirmative(_answer(answers_dict, 'pred_q4', 'usted_consume_fruta'))
        consume_verdura = _affirmative(_answer(answers_dict, 'pred_q3', 'usted_consume_verduras'))
        consume_oliva = _affirmative(_answer(answers_dict, 'pred_q1', 'usa_usted_aceite_de_oliva'))
        diet_answers = (consume_fruta, consume_verdura, consume_oliva)
        predimed_adherencia = (None if any(value is None for value in diet_answers) else
            'Buena Adherencia' if all(diet_answers) else 'Adherencia Moderada/Baja')

        # Separar el score exacto del indicador umbral (>=2). Con dos
        # positivos conocidos se sabe que supera el umbral aunque falten
        # otros factores; un score exacto requiere las seis respuestas.
        factors = [hipertension, dislipemia, obesidad, diabetes, fumador_activo, higado_graso]
        known_positive_factors = sum(factor is True for factor in factors)
        factors_complete = all(factor is not None for factor in factors)
        riesgo_alto = (
            True if known_positive_factors >= 2
            else False if factors_complete
            else None
        )
        if not factors_complete:
            factores_riesgo_count = None
            riesgo_global = 'Sin dato'
        else:
            factores_riesgo_count = sum(1 for factor in factors if factor is True)
            if factores_riesgo_count == 0:
                riesgo_global = 'Bajo (0 factores)'
            elif factores_riesgo_count == 1:
                riesgo_global = 'Moderado (1 factor)'
            elif factores_riesgo_count <= 3:
                riesgo_global = 'Alto (2-3 factores)'
            else:
                riesgo_global = 'Muy Alto (4+ factores)'

        # -------------------------------------------------------------
        # BLOQUE 4: FACTORES EMERGENTES
        # -------------------------------------------------------------
        # Sueño
        r_sue_cal = _answer(answers_dict, 'calidad_sueno', 'sueno_calidad')
        if r_sue_cal is None:
            calidad_sueno = 'Sin dato'
        elif 'buena' in r_sue_cal.lower():
            calidad_sueno = 'Buena'
        elif 'mala' in r_sue_cal.lower():
            calidad_sueno = 'Mala'
        else:
            calidad_sueno = 'Normal'

        r_sue_cant = _answer(answers_dict, 'cantidad_sueno', 'sueno_cantidad')
        if r_sue_cant is None:
            cantidad_sueno = 'Sin dato'
        elif 'buena' in r_sue_cant.lower():
            cantidad_sueno = 'Adecuada (7-8 h)'
        elif 'mala' in r_sue_cant.lower():
            cantidad_sueno = 'Insuficiente (<6 h)'
        else:
            cantidad_sueno = 'Normal'

        apnea_sueno = _affirmative(_answer(answers_dict, 'r_apnea', 'apnea_sueno', 'apnea'))

        # Estrés
        r_est_val = _answer(answers_dict, 'estres', 'em_estres_trab', 'em_estres_fam')
        if r_est_val is None:
            estres_desc = 'Sin dato'
            estres_laboral = None
            estres_familiar = None
        elif _es_negativo(r_est_val):
            estres_desc = 'Sin estrés significativo'
            estres_laboral = False
            estres_familiar = False
        else:
            e_low = r_est_val.lower()
            has_estres_trab = (
                ('trabajo' in e_low or 'trebajo' in e_low or 'laboral' in e_low)
                and 'no en el trabajo' not in e_low
                and 'no laboral' not in e_low
            )
            has_estres_fam = (
                'familiar' in e_low
                and 'no en la vida familiar' not in e_low
                and 'no familiar' not in e_low
            )
            if has_estres_trab and has_estres_fam:
                estres_desc = 'Laboral y Familiar'
            elif has_estres_trab:
                estres_desc = 'Estrés Laboral'
            elif has_estres_fam:
                estres_desc = 'Estrés Familiar'
            else:
                estres_desc = 'Sin estrés significativo'
            estres_laboral = has_estres_trab
            estres_familiar = has_estres_fam

        # Ambiente laboral, personalidad Tipo A y tóxicos
        mal_amb_raw = answers_dict.get('mal_ambiente_laboral', '') or answers_dict.get('em_mal_amb', '')
        mal_ambiente_laboral = (not _es_negativo(mal_amb_raw) and ('si' in str(mal_amb_raw).lower() or 'sí' in str(mal_amb_raw).lower())) if mal_amb_raw else None

        pers_a_raw = answers_dict.get('personalidad_tipo_a', '') or answers_dict.get('em_pers_a', '')
        personalidad_tipo_a = (not _es_negativo(pers_a_raw) and ('si' in str(pers_a_raw).lower() or 'sí' in str(pers_a_raw).lower() or 'exigente' in str(pers_a_raw).lower())) if pers_a_raw else None

        tox_raw = answers_dict.get('trabaja_con_toxicos', '') or answers_dict.get('em_toxicos', '')
        toxicos_laboral = (not _es_negativo(tox_raw) and ('si' in str(tox_raw).lower() or 'sí' in str(tox_raw).lower())) if tox_raw else None

        # Factores hormonales femeninos
        bajos_estrogenos = None if _answer(answers_dict, 'em_estrogenos', 'bajos_estrogenos') is None else 'si' in (answers_dict.get('bajos_estrogenos', '') or answers_dict.get('em_estrogenos', '')).lower() or 'menopausia' in (answers_dict.get('bajos_estrogenos', '') or answers_dict.get('em_estrogenos', '')).lower()
        anticonceptivos_35 = None if _answer(answers_dict, 'em_anticonceptivos', 'proteccion_anticonceptivo') is None else 'si' in (answers_dict.get('proteccion_anticonceptivo', '') or answers_dict.get('em_anticonceptivos', '')).lower()

        # -------------------------------------------------------------
        # BLOQUE 5: ANTECEDENTES FAMILIARES
        # -------------------------------------------------------------
        ant_p_raw = answers_dict.get('antecedentes_padres', '') or ''
        ant_m_raw = answers_dict.get('antecedentes_madres', '') or ''

        def family_value(code, summary, *terms):
            individual = _affirmative(_answer(answers_dict, code))
            if individual is True:
                return True
            summary_val = _answer(answers_dict, summary)
            if summary_val is not None:
                if _es_negativo(summary_val):
                    return False
                if any(term in summary_val.lower() for term in terms):
                    return True
            return individual

        ant_padre_hta = family_value('ant_padre_hta', 'antecedentes_padres', 'hta')
        ant_padre_dm = family_value('ant_padre_dm', 'antecedentes_padres', 'diab')
        ant_padre_dlp = family_value('ant_padre_dislip', 'antecedentes_padres', 'dislip')
        ant_padre_iam = family_value('ant_padre_iam', 'antecedentes_padres', 'iam', 'infarto')
        ant_padre_acv = family_value('ant_padre_ictus', 'antecedentes_padres', 'ictus', 'acv')
        ant_madre_hta = family_value('ant_madre_hta', 'antecedentes_madres', 'hta')
        ant_madre_dm = family_value('ant_madre_dm', 'antecedentes_madres', 'diab')
        ant_madre_dlp = family_value('ant_madre_dislip', 'antecedentes_madres', 'dislip')
        ant_madre_iam = family_value('ant_madre_iam', 'antecedentes_madres', 'iam', 'infarto')
        ant_madre_acv = family_value('ant_madre_ictus', 'antecedentes_madres', 'ictus', 'acv')
        ant_cardiopatia_prematura = _affirmative(_answer(answers_dict, 'af_cardiopatia_prematura'))
        ant_muerte_subita = _affirmative(_answer(answers_dict, 'af_muerte_subita'))
        ant_fam_hta = _fully_known_or(ant_padre_hta, ant_madre_hta)
        ant_fam_dm = _fully_known_or(ant_padre_dm, ant_madre_dm)
        ant_fam_dlp = _fully_known_or(ant_padre_dlp, ant_madre_dlp)
        ant_fam_cv_mayor = _fully_known_or(ant_padre_iam, ant_madre_iam, ant_padre_acv, ant_madre_acv, ant_cardiopatia_prematura, ant_muerte_subita)
        ant_fam_cualquiera = _fully_known_or(ant_fam_hta, ant_fam_dm, ant_fam_dlp, ant_fam_cv_mayor)

        # -------------------------------------------------------------
        # BLOQUE 6: HISTORIA CLÍNICA NO CARDIOVASCULAR
        # -------------------------------------------------------------
        # Respiratorio (Asma / EPOC)
        resp_raw = (answers_dict.get('problemas_respiratorios', '') or answers_dict.get('nc_asma', '') or answers_dict.get('nc_epoc', '') or '').strip()
        if not resp_raw:
            asma = epoc = None
        elif _es_negativo(resp_raw):
            asma = False
            epoc = False
        else:
            asma = 'asma' in resp_raw.lower()
            epoc = 'epoc' in resp_raw.lower()

        if asma is None:
            respiratorio_desc = 'Sin dato'
        elif asma and epoc:
            respiratorio_desc = 'Asma y EPOC'
        elif asma:
            respiratorio_desc = 'Asma bronquial'
        elif epoc:
            respiratorio_desc = 'EPOC'
        else:
            respiratorio_desc = 'Sin patología respiratoria'

        # Salud Mental (Ansiedad / Depresión)
        mental_raw = _answer(answers_dict, 'salud_mental')
        depresion = _mental_condition(_answer(answers_dict, 'nc_depresion'), mental_raw, 'depresi')
        ansiedad = _mental_condition(_answer(answers_dict, 'nc_ansiedad'), mental_raw, 'ansied')
        if depresion is None and ansiedad is None:
            salud_mental_desc = 'Sin dato'
        elif depresion is False and ansiedad is False:
            salud_mental_desc = 'Sin trastorno diagnosticado'
        elif depresion is True and ansiedad is True:
            salud_mental_desc = 'Ansiedad y Depresión'
        elif depresion is True:
            salud_mental_desc = 'Depresión'
        elif ansiedad is True:
            salud_mental_desc = 'Ansiedad'
        else:
            salud_mental_desc = 'Sin dato'

        # Reumatología / Cáncer / Alergias / Insuficiencia Renal
        reuma_raw = (answers_dict.get('enfermedad_reumatologicas', '') or answers_dict.get('nc_reuma', '') or '').strip()
        enfermedad_reumatologica = (not _es_negativo(reuma_raw) and ('tiene' in reuma_raw.lower() or 'si' in reuma_raw.lower() or 'sí' in reuma_raw.lower())) if reuma_raw else None

        cancer_raw = (answers_dict.get('historia_cancer', '') or answers_dict.get('nc_cancer', '') or '').strip()
        cancer = (not _es_negativo(cancer_raw) and ('tiene' in cancer_raw.lower() or 'si' in cancer_raw.lower() or 'sí' in cancer_raw.lower())) if cancer_raw else None

        alergia_raw = (answers_dict.get('alergias', '') or answers_dict.get('nc_alergia', '') or '').strip()
        alergias_medicamentos = (not _es_negativo(alergia_raw) and ('tiene' in alergia_raw.lower() or 'si' in alergia_raw.lower() or 'sí' in alergia_raw.lower())) if alergia_raw else None

        irc_raw = _answer(answers_dict, 'r_irc', 'irc')
        insuficiencia_renal = _affirmative(irc_raw)

        # -------------------------------------------------------------
        # BLOQUE 7: COVID-19 Y SECUELAS
        # -------------------------------------------------------------
        covid_values = resolve_covid(answers_dict)
        covid_infeccion = covid_values['covid_infeccion']
        covid_hospitalizacion = covid_values['covid_hospitalizacion']
        covid_secuelas_cardio = covid_values['covid_secuelas_cardio']
        covid_secuelas_resp = covid_values['covid_secuelas_resp']
        covid_fatiga_long = covid_values['covid_fatiga_long']
        covid_niebla_mental = covid_values['covid_niebla_mental']
        covid_tiene_secuelas = covid_values['covid_tiene_secuelas']
        covid_historia = ('Sin dato' if covid_infeccion is None else
            'No ha pasado COVID-19' if covid_infeccion is False else
            'COVID-19; hospitalizacion sin responder' if covid_hospitalizacion is None else
            'Pas\u00f3 COVID-19 con hospitalizaci\u00f3n' if covid_hospitalizacion else 'Pas\u00f3 COVID-19 sin hospitalizaci\u00f3n')

        # -------------------------------------------------------------
        # BLOQUE 8: RESULTADOS DEL ELECTROCARDIOGRAMA (ECG)
        # -------------------------------------------------------------
        ecg = getattr(v, 'electrocardiogram', None)
        ecg_ritmo = ecg.rhythm.name if (ecg and ecg.rhythm) else 'Sin ECG'
        ecg_es_sinusal = ('sinusal' in ecg_ritmo.lower()) if ecg else None
        ecg_arritmia = (not ecg_es_sinusal) if ecg_es_sinusal is not None else None
        arritmias = ecg_arritmia

        ecg_fc_model = float(ecg.heart_rate) if ecg and ecg.heart_rate is not None else None
        ecg_fc_answer = _numeric_answer(numeric_answers, answers_dict, 'ecg_fc')
        # Las importaciones antiguas copiaban la FC clínica al campo ECG.
        # Si no hay respuesta ECG explícita y coincide con el pulso, no es una
        # medición independiente del trazado y se excluye de esta comparación.
        ecg_fc = (
            ecg_fc_answer
            if ecg_fc_answer is not None
            else ecg_fc_model
            if ecg_fc_model is not None and (fc is None or ecg_fc_model != fc)
            else None
        )
        ecg_pr_ms = int(ecg.pr_interval_ms) if (ecg and ecg.pr_interval_ms) else None
        if ecg_pr_ms is not None:
            if ecg_pr_ms < 120:
                ecg_pr_cat = 'PR Corto (<120 ms)'
            elif ecg_pr_ms <= 200:
                ecg_pr_cat = 'Normal (120-200 ms)'
            else:
                ecg_pr_cat = 'Bloqueo AV 1° (>200 ms)'
        else:
            ecg_pr_cat = 'No medido'

        ecg_qrs_ms = int(ecg.qrs_duration_ms) if (ecg and ecg.qrs_duration_ms) else None
        if ecg_qrs_ms is not None:
            if ecg_qrs_ms < 100:
                ecg_qrs_cat = 'Estrecho Normal (<100 ms)'
            elif ecg_qrs_ms < 120:
                ecg_qrs_cat = 'Incompleto (100-119 ms)'
            else:
                ecg_qrs_cat = 'Bloqueo Completo (≥120 ms)'
        else:
            ecg_qrs_cat = 'No medido'

        ecg_qt_ms = int(ecg.qt_interval_ms) if (ecg and ecg.qt_interval_ms) else None
        ecg_qtc_ms = int(ecg.qtc_bazett_ms) if (ecg and ecg.qtc_bazett_ms) else None
        if ecg_qtc_ms is not None:
            corte_qtc = 440 if sexo == 'Hombre' else 460
            ecg_qtc_cat = f'Normal (<{corte_qtc} ms)' if ecg_qtc_ms < corte_qtc else f'Prolongado (≥{corte_qtc} ms)'
        else:
            ecg_qtc_cat = 'No medido'

        ecg_eje_grados = int(ecg.qrs_axis_degrees) if (ecg and ecg.qrs_axis_degrees is not None) else None
        ecg_normal = ecg.is_normal if ecg else None
        ecg_anormal = (not ecg.is_normal) if (ecg and ecg.is_normal is not None) else None
        ecg_hvi = ecg.left_ventricular_hypertrophy if ecg else None
        bbb_raw = str(ecg.bundle_branch_block).strip().upper() if (ecg and ecg.bundle_branch_block) else ''
        if not bbb_raw and (not ecg or ecg.has_bundle_branch_block is None):
            ecg_bloqueo_rama = None
            ecg_bloqueo_presente = None
        elif not bbb_raw or bbb_raw in ('NINGUNA', 'NINGUNO', 'NO', 'SIN BLOQUEO', 'NORMAL'):
            ecg_bloqueo_rama = 'Sin bloqueo'
            ecg_bloqueo_presente = False
        else:
            ecg_bloqueo_rama = str(ecg.bundle_branch_block).strip()
            ecg_bloqueo_presente = True
        ecg_repolarizacion = ecg.repolarization_abnormalities if ecg else None

        # -------------------------------------------------------------
        # COMPILACIÓN DEL REGISTRO EVALUADO
        # -------------------------------------------------------------
        record = {
            # Identificación y Filtros Transversales
            'id': v.visit_id,
            'binary_answers': recorded_answers(v),
            'study_code': v.study_code,
            'patient_id': p.patient_id if p else None,
            'id_card': p.id_card if p else '',
            'nombre': f"{p.first_names} {p.last_name1}" if p else '',
            'ano': ano,
            'institucion': inst_name,
            'sexo': sexo,
            'edad': edad,
            'grupo_edad': grupo_edad,
            'categoria': categoria,
            'factores_riesgo_count': factores_riesgo_count,
            'riesgo_alto': riesgo_alto,
            'riesgo_global': riesgo_global,

            # Bloque 1: Datos del Individuo
            'estado_civil': estado_civil,
            'nivel_estudios': nivel_estudios,
            'rango_ingresos': rango_ingresos,
            'tipo_vivienda': tipo_vivienda,
            'canton': canton,
            'facultad': facultad,

            # Bloque 2: Exploración Física
            'peso': peso,
            'talla': talla,
            'imc': imc,
            'imc_cat': imc_cat,
            'obesidad': obesidad,
            'sobrepeso_u_obesidad': sobrepeso_u_obesidad,
            'perimetro_abdominal': perimetro_abdominal,
            'abd_riesgo': abd_riesgo,
            'tas': tas,
            'tad': tad,
            'pa_categoria': pa_categoria,
            'pa_elevada_consulta': pa_elevada_consulta,
            'fc': fc,
            'sat_o2': sat_o2,
            'soplos': soplos,
            'soplo_grado': soplo_grado,
            'ausc_pulm_normal': ausc_pulm_normal,
            'ausc_abdom_normal': ausc_abdom_normal,

            # Bloque 3: Factores Modificables
            'hipertension': hipertension,
            'hta_desc': hta_desc,
            'diabetes': diabetes,
            'diabetes_lab': diabetes_lab,
            'db_desc': db_desc,
            'dislipemia': dislipemia,
            'dislipemia_lab': dislipemia_lab,
            'dl_desc': dl_desc,
            'tabaquismo': tabaquismo,
            'fumador_activo': fumador_activo,
            'alcohol': alcohol,
            'drogas': drogas,
            'actividad_fisica': actividad_fisica,
            'deporte': deporte,
            'higado_graso': higado_graso,
            'vasculopatia_periferica': vasculopatia_periferica,
            'vasculopatia_carotidea': vasculopatia_carotidea,
            'vasculopatia_femoral': vasculopatia_femoral,
            'vasculopatia_cualquiera': vasculopatia_cualquiera,
            'disfuncion_erectil': disfuncion_erectil,
            'consume_fruta': consume_fruta,
            'consume_verdura': consume_verdura,
            'predimed_adherencia': predimed_adherencia,

            # Bloque 4: Factores Emergentes
            'calidad_sueno': calidad_sueno,
            'cantidad_sueno': cantidad_sueno,
            'apnea_sueno': apnea_sueno,
            'estres': estres_desc,
            'estres_laboral': estres_laboral,
            'estres_familiar': estres_familiar,
            'mal_ambiente_laboral': mal_ambiente_laboral,
            'personalidad_tipo_a': personalidad_tipo_a,
            'toxicos_laboral': toxicos_laboral,
            'bajos_estrogenos': bajos_estrogenos,
            'anticonceptivos_35': anticonceptivos_35,

            # Bloque 5: Antecedentes Familiares
            'ant_padre_hta': ant_padre_hta,
            'ant_padre_dm': ant_padre_dm,
            'ant_padre_dlp': ant_padre_dlp,
            'ant_padre_iam': ant_padre_iam,
            'ant_padre_acv': ant_padre_acv,
            'ant_madre_hta': ant_madre_hta,
            'ant_madre_dm': ant_madre_dm,
            'ant_madre_dlp': ant_madre_dlp,
            'ant_madre_iam': ant_madre_iam,
            'ant_madre_acv': ant_madre_acv,
            'ant_cardiopatia_prematura': ant_cardiopatia_prematura,
            'ant_muerte_subita': ant_muerte_subita,
            'ant_fam_hta': ant_fam_hta,
            'ant_fam_dm': ant_fam_dm,
            'ant_fam_dlp': ant_fam_dlp,
            'ant_fam_cv_mayor': ant_fam_cv_mayor,
            'ant_fam_cualquiera': ant_fam_cualquiera,

            # Bloque 6: Historia No Cardiovascular
            'respiratorio_desc': respiratorio_desc,
            'asma': asma,
            'epoc': epoc,
            'salud_mental_desc': salud_mental_desc,
            'ansiedad': ansiedad,
            'depresion': depresion,
            'enfermedad_reumatologica': enfermedad_reumatologica,
            'cancer': cancer,
            'alergias_medicamentos': alergias_medicamentos,
            'insuficiencia_renal': insuficiencia_renal,

            # Bloque 7: COVID-19 y Secuelas
            'covid_historia': covid_historia,
            'covid_infeccion': covid_infeccion,
            'covid_hospitalizacion': covid_hospitalizacion,
            'covid_secuelas_cardio': covid_secuelas_cardio,
            'covid_secuelas_resp': covid_secuelas_resp,
            'covid_fatiga_long': covid_fatiga_long,
            'covid_niebla_mental': covid_niebla_mental,
            'covid_tiene_secuelas': covid_tiene_secuelas,

            # Bloque 8: Electrocardiograma
            'ecg_ritmo': ecg_ritmo,
            'ecg_es_sinusal': ecg_es_sinusal,
            'ecg_arritmia': ecg_arritmia,
            'arritmias': arritmias,
            'ecg_fc': ecg_fc,
            'ecg_pr_ms': ecg_pr_ms,
            'ecg_pr_cat': ecg_pr_cat,
            'ecg_qrs_ms': ecg_qrs_ms,
            'ecg_qrs_cat': ecg_qrs_cat,
            'ecg_qt_ms': ecg_qt_ms,
            'ecg_qtc_ms': ecg_qtc_ms,
            'ecg_qtc_cat': ecg_qtc_cat,
            'ecg_eje_grados': ecg_eje_grados,
            'ecg_normal': ecg_normal,
            'ecg_anormal': ecg_anormal,
            'ecg_hvi': ecg_hvi,
            'ecg_bloqueo_presente': ecg_bloqueo_presente,
            'ecg_bloqueo_rama': ecg_bloqueo_rama,
            'ecg_repolarizacion': ecg_repolarizacion,
        }
        for metric, code in {
            'asma': 'nc_asma', 'epoc': 'nc_epoc', 'enfermedad_reumatologica': 'nc_reuma',
            'cancer': 'nc_cancer', 'alergias_medicamentos': 'nc_alergia', 'mal_ambiente_laboral': 'em_mal_amb',
            'personalidad_tipo_a': 'em_pers_a', 'toxicos_laboral': 'em_toxicos', 'bajos_estrogenos': 'em_estrogenos',
            'anticonceptivos_35': 'em_anticonceptivos', 'estres_laboral': 'em_estres_trab', 'estres_familiar': 'em_estres_fam'
        }.items():
            if record.get(metric) is None and code in answers_dict:
                record[metric] = _affirmative(_answer(answers_dict, code))
        records.append(record)

    sorted_years = sorted(list(available_years))
    sorted_categories = sorted(list(available_categories))
    sorted_institutions = list(
        selectable_institutions().values_list('name', flat=True).order_by('name')
    )

    n = len(records)
    def fmt_pct(cnt, field):
        valid = sum(r[field] is not None and r[field] != 'Sin dato' for r in records)
        return f"{(cnt / valid * 100):.1f}".replace('.', ',') if valid else 'Sin dato'

    # Resumen General KPIs
    hta_cnt = sum(1 for r in records if r['hipertension'])
    dl_cnt = sum(1 for r in records if r['dislipemia'])
    sp_ob_cnt = sum(1 for r in records if r['sobrepeso_u_obesidad'])
    riesgo_alto_cnt = sum(1 for r in records if r['riesgo_alto'] is True)

    summary_kpis = {
        'total': n,
        'hta_pct': fmt_pct(hta_cnt, 'hipertension'),
        'dl_pct': fmt_pct(dl_cnt, 'dislipemia'),
        'sp_ob_pct': fmt_pct(sp_ob_cnt, 'sobrepeso_u_obesidad'),
        'riesgo_alto_pct': fmt_pct(riesgo_alto_cnt, 'riesgo_alto'),
    }

    # KPIs específicos precalculados para cada bloque temático
    edad_media = f"{(sum(r['edad'] for r in records) / n):.1f}".replace('.', ',') if n > 0 else "0"
    hombres_cnt = sum(1 for r in records if r['sexo'] == 'Hombre')
    mujeres_cnt = sum(1 for r in records if r['sexo'] == 'Mujer')
    postgrado_cnt = sum(1 for r in records if r['nivel_estudios'] == 'Postgrado')
    casados_cnt = sum(1 for r in records if r['estado_civil'] == 'Casado/a')

    valid_imc = [r['imc'] for r in records if r['imc'] is not None and r['imc'] > 0]
    imc_medio = f"{(sum(valid_imc) / len(valid_imc)):.1f}".replace('.', ',') if valid_imc else "0,0"
    cintura_riesgo_cnt = sum(1 for r in records if 'Riesgo' in r['abd_riesgo'])
    valid_tas = [r['tas'] for r in records if r['tas'] is not None and r['tas'] > 0]
    tas_media = f"{(sum(valid_tas) / len(valid_tas)):.0f}" if valid_tas else "—"
    valid_tad = [r['tad'] for r in records if r['tad'] is not None and r['tad'] > 0]
    tad_media = f"{(sum(valid_tad) / len(valid_tad)):.0f}" if valid_tad else "—"
    valid_sato2 = [r['sat_o2'] for r in records if r['sat_o2'] is not None and r['sat_o2'] > 0]
    sato2_media = f"{(sum(valid_sato2) / len(valid_sato2)):.0f}" if valid_sato2 else "0"

    dm_cnt = sum(1 for r in records if r['diabetes'])
    tabaco_cnt = sum(1 for r in records if r['fumador_activo'])
    act_fis_cnt = sum(1 for r in records if r['actividad_fisica'])

    sueno_malo_cnt = sum(1 for r in records if r['calidad_sueno'] == 'Mala')
    estres_cnt = sum(1 for r in records if r['estres'] not in (None, 'Sin dato', 'Sin estrés significativo'))
    mal_amb_cnt = sum(1 for r in records if r['mal_ambiente_laboral'])
    pers_a_cnt = sum(1 for r in records if r['personalidad_tipo_a'])
    toxicos_cnt = sum(1 for r in records if r['toxicos_laboral'])

    fam_hta_cnt = sum(1 for r in records if r['ant_fam_hta'])
    fam_dm_cnt = sum(1 for r in records if r['ant_fam_dm'])
    fam_dlp_cnt = sum(1 for r in records if r['ant_fam_dlp'])
    fam_cv_mayor_cnt = sum(1 for r in records if r['ant_fam_cv_mayor'])

    resp_cnt = sum(1 for r in records if r['respiratorio_desc'] not in (None, 'Sin dato', 'Sin patología respiratoria'))
    mental_cnt = sum(1 for r in records if r['salud_mental_desc'] not in (None, 'Sin dato', 'Sin trastorno diagnosticado'))
    reuma_cnt = sum(1 for r in records if r['enfermedad_reumatologica'])
    alergias_cnt = sum(1 for r in records if r['alergias_medicamentos'])

    covid_inf_cnt = sum(1 for r in records if r['covid_infeccion'])
    covid_hosp_cnt = sum(1 for r in records if r['covid_hospitalizacion'])
    covid_sec_cnt = sum(1 for r in records if r['covid_tiene_secuelas'])
    covid_fatiga_cnt = sum(1 for r in records if r['covid_fatiga_long'])

    ecg_sinusal_cnt = sum(1 for r in records if r['ecg_es_sinusal'])
    ecg_arritmia_cnt = sum(1 for r in records if r['ecg_arritmia'])
    valid_pr = [r['ecg_pr_ms'] for r in records if r['ecg_pr_ms'] is not None]
    pr_medio = f"{(sum(valid_pr) / len(valid_pr)):.0f}" if valid_pr else "0"
    valid_qrs = [r['ecg_qrs_ms'] for r in records if r['ecg_qrs_ms'] is not None]
    qrs_medio = f"{(sum(valid_qrs) / len(valid_qrs)):.0f}" if valid_qrs else "0"
    valid_qtc = [r['ecg_qtc_ms'] for r in records if r['ecg_qtc_ms'] is not None]
    qtc_medio = f"{(sum(valid_qtc) / len(valid_qtc)):.0f}" if valid_qtc else "0"

    module_kpis = {
        'individuo': {
            'edad_media': edad_media,
            'hombres_pct': fmt_pct(hombres_cnt, 'sexo'),
            'mujeres_pct': fmt_pct(mujeres_cnt, 'sexo'),
            'postgrado_pct': fmt_pct(postgrado_cnt, 'nivel_estudios'),
            'casados_pct': fmt_pct(casados_cnt, 'estado_civil'),
        },
        'exploracion': {
            'imc_medio': imc_medio,
            'cintura_riesgo_pct': fmt_pct(cintura_riesgo_cnt, 'abd_riesgo'),
            'tas_media': tas_media,
            'tad_media': tad_media,
            'sat_o2_media': sato2_media,
        },
        'modificables': {
            'hta_pct': fmt_pct(hta_cnt, 'hipertension'),
            'dm_pct': fmt_pct(dm_cnt, 'diabetes'),
            'dl_pct': fmt_pct(dl_cnt, 'dislipemia'),
            'tabaco_pct': fmt_pct(tabaco_cnt, 'fumador_activo'),
            'act_fisica_pct': fmt_pct(act_fis_cnt, 'actividad_fisica'),
        },
        'emergentes': {
            'sueno_malo_pct': fmt_pct(sueno_malo_cnt, 'calidad_sueno'),
            'estres_pct': fmt_pct(estres_cnt, 'estres'),
            'mal_ambiente_pct': fmt_pct(mal_amb_cnt, 'mal_ambiente_laboral'),
            'personalidad_a_pct': fmt_pct(pers_a_cnt, 'personalidad_tipo_a'),
            'toxicos_pct': fmt_pct(toxicos_cnt, 'toxicos_laboral'),
        },
        'familiares': {
            'fam_hta_pct': fmt_pct(fam_hta_cnt, 'ant_fam_hta'),
            'fam_dm_pct': fmt_pct(fam_dm_cnt, 'ant_fam_dm'),
            'fam_dlp_pct': fmt_pct(fam_dlp_cnt, 'ant_fam_dlp'),
            'fam_cv_mayor_pct': fmt_pct(fam_cv_mayor_cnt, 'ant_fam_cv_mayor'),
        },
        'no_cardio': {
            'respiratorio_pct': fmt_pct(resp_cnt, 'respiratorio_desc'),
            'salud_mental_pct': fmt_pct(mental_cnt, 'salud_mental_desc'),
            'reuma_pct': fmt_pct(reuma_cnt, 'enfermedad_reumatologica'),
            'alergias_pct': fmt_pct(alergias_cnt, 'alergias_medicamentos'),
        },
        'covid': {
            'covid_inf_pct': fmt_pct(covid_inf_cnt, 'covid_infeccion'),
            'covid_hosp_pct': fmt_pct(covid_hosp_cnt, 'covid_hospitalizacion'),
            'covid_sec_pct': fmt_pct(covid_sec_cnt, 'covid_tiene_secuelas'),
            'covid_fatiga_pct': fmt_pct(covid_fatiga_cnt, 'covid_fatiga_long'),
        },
        'ecg': {
            'sinusal_pct': fmt_pct(ecg_sinusal_cnt, 'ecg_es_sinusal'),
            'arritmia_pct': fmt_pct(ecg_arritmia_cnt, 'ecg_arritmia'),
            'pr_medio': pr_medio,
            'qrs_medio': qrs_medio,
            'qtc_medio': qtc_medio,
        }
    }

    unique_fichas = sorted(
        list({str(r['study_code']) for r in records if r.get('study_code')}),
        key=lambda x: int(x) if x.isdigit() else 999999
    )

    return {
        'records': records,
        'boolean_fields': descriptors(),
        'total': n,
        'summary_kpis': summary_kpis,
        'module_kpis': module_kpis,
        'years': sorted_years,
        'categories': sorted_categories,
        'institutions': sorted_institutions,
        'fichas': unique_fichas,
    }
