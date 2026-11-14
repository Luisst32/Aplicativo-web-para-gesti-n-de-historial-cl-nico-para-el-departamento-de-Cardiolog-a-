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

from datetime import date
from django.db.models import Prefetch

from clinical.models import Visit, VisitAnswer


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
        return 'PAS (Administrativos)'
    if 'SERVICIO' in cat_upper:
        return 'Personal de Servicios'
    if 'ESTUDIANTE' in cat_upper:
        return 'Estudiantes'
    return cat_name


def _es_negativo(texto):
    """Verifica si una respuesta textual clínica expresa un valor negativo o ausencia de patología."""
    if not texto:
        return True
    t = str(texto).strip().lower()
    if t in ('no', '0', 'false', 'negativo', 'sin', 'ninguno', 'ninguna', 'no especificado', 'no registra'):
        return True
    if (
        t.startswith('no ') or
        t.startswith('sin ') or
        t.startswith('ningun') or
        t.startswith('no tiene') or
        t.startswith('no presenta') or
        t.startswith('no realiza') or
        t.startswith('no consume') or
        t.startswith('no ha pasado')
    ):
        return True
    return False


def _answer(answers, *codes):
    """Return the first recorded non-empty answer without inventing a fallback."""
    for code in codes:
        value = answers.get(code)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _affirmative(value):
    """Return True/False for a recorded yes/no answer, otherwise None."""
    if value is None:
        return None
    return not _es_negativo(value) and ('si' in value.lower() or 'sí' in value.lower())


def _any_known(*values):
    """Three-valued OR: unknown remains unknown unless another source is positive."""
    if any(value is True for value in values):
        return True
    if all(value is False for value in values):
        return False
    return None


def _mental_condition(individual_value, summary_value, condition):
    """Resolve one mental-health condition without masking its explicit answer.

    Older records can contain both the combined ``salud_mental`` answer and
    the individual ``nc_depresion`` / ``nc_ansiedad`` fields.  The individual
    field is the more precise clinical datum, so it must take precedence.
    """
    individual = _affirmative(individual_value)
    if individual is not None:
        return individual
    if individual_value is not None and condition in individual_value.lower():
        return not _es_negativo(individual_value)

    if summary_value is None:
        return None
    if _es_negativo(summary_value):
        return False

    summary = summary_value.lower()
    if 'ambas' in summary or condition in summary:
        return True
    # A non-empty combined answer that does not name this condition is not
    # evidence of absence (for example, an incomplete legacy value).
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

    records = []
    available_years = set()
    available_categories = set()
    available_institutions = set()

    for v in visits:
        p = v.patient
        v_date = v.visit_date or date(2024, 1, 1)
        ano = v_date.year
        available_years.add(ano)

        inst_name = p.institution.name if (p and p.institution) else 'Universidad Estatal de Milagro'
        available_institutions.add(inst_name)

        # -------------------------------------------------------------
        # BLOQUE 1: DATOS DEL INDIVIDUO (SOCIODEMOGRAFÍA)
        # -------------------------------------------------------------
        sex_raw = p.sex.name if (p and p.sex) else None
        sexo = ('Mujer' if 'MUJER' in sex_raw.upper() or 'FEM' in sex_raw.upper()
                else 'Hombre') if sex_raw else None

        edad = get_age(p.birth_date, v_date)
        grupo_edad = get_age_group(edad) if edad else 'Sin dato'

        cat_raw = v.staff_category.name if v.staff_category else ''
        categoria = map_category_label(cat_raw)
        available_categories.add(categoria)

        # Respuestas del cuestionario asociadas
        answers_dict = {}
        for a in v.answers.all():
            q_code = a.question.code.lower()
            val = a.selected_option.label if a.selected_option else (a.text_value if a.text_value is not None else a.numeric_value)
            answers_dict[q_code] = str(val).strip() if val is not None else ''

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
        tas = float(vs.systolic_bp) if vs and vs.systolic_bp is not None else None
        tad = float(vs.diastolic_bp) if vs and vs.diastolic_bp is not None else None
        fc = int(vs.heart_rate) if vs and vs.heart_rate is not None else None
        sat_o2 = int(vs.oxygen_saturation) if vs and vs.oxygen_saturation is not None else None

        # Clasificación de Presión Arterial
        if tas is None or tad is None:
            pa_categoria = 'Sin dato'
        elif tas >= 140.0 or tad >= 90.0:
            pa_categoria = 'HTA Grado 2 (≥140/90)' if (tas >= 160.0 or tad >= 100.0) else 'HTA Grado 1 (140-159/90-99)'
        elif tas >= 130.0 or tad >= 80.0:
            pa_categoria = 'PA Elevada (130-139/80-89)'
        elif tas > 0:
            pa_categoria = 'PA Normal (<130/<80)'
        else:
            pa_categoria = 'No registrada'

        # Hallazgos auscultatorios
        soplos = bool(vs and (vs.systolic_murmur or vs.diastolic_murmur or vs.murmur_grade))
        soplo_grado = int(vs.murmur_grade) if vs and vs.murmur_grade else 0
        ausc_pulm_normal = bool(vs.pulmonary_auscultation_normal) if vs else True
        ausc_abdom_normal = bool(vs.abdominal_auscultation_normal) if vs else True

        # -------------------------------------------------------------
        # BLOQUE 3: FACTORES DE RIESGO MODIFICABLES
        # -------------------------------------------------------------
        # Hipertensión (HTA)
        r_hta_val = _answer(answers_dict, 'r_hta', 'hta', 'hta_tto')
        is_hta_ans = _affirmative(r_hta_val)
        is_hta_bp = (tas >= 140.0 or tad >= 90.0) if tas is not None and tad is not None else None
        hipertension = _any_known(is_hta_ans, is_hta_bp)

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
        glucosa = float(lab.glucose_mg_dl) if lab and lab.glucose_mg_dl is not None else None
        r_dm_val = _answer(answers_dict, 'r_dm', 'diabetes_mellitus', 'dm', 'diab_glucosa')
        is_dm_ans = _affirmative(r_dm_val)
        is_dm_lab = glucosa >= 126.0 if glucosa is not None else None
        diabetes = _any_known(is_dm_ans, is_dm_lab)
        if r_dm_val and 'tratada' in r_dm_val.lower():
            db_desc = 'Tipo 2 tratada'
        elif diabetes is True or (glucosa is not None and glucosa >= 100.0):
            db_desc = 'Diabetes/Prediabetes'
        elif diabetes is False:
            db_desc = 'No'
        else:
            db_desc = 'Sin dato'

        # Dislipemia
        col_total = float(lab.total_cholesterol_mg_dl) if lab and lab.total_cholesterol_mg_dl is not None else None
        col_ldl = float(lab.ldl_mg_dl) if lab and lab.ldl_mg_dl is not None else None
        triglic = float(lab.triglycerides_mg_dl) if lab and lab.triglycerides_mg_dl is not None else None

        r_dl_val = _answer(answers_dict, 'r_dislip', 'dislipemia')
        is_dl_ans = _affirmative(r_dl_val)
        lipid_values = (col_total, col_ldl, triglic)
        is_dl_lab = (col_total >= 200.0 or col_ldl >= 130.0 or triglic >= 150.0) if all(value is not None for value in lipid_values) else None
        dislipemia = _any_known(is_dl_ans, is_dl_lab)

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
        vasculopatia_femoral = _affirmative(_answer(answers_dict, 'r_vasc_fem'))
        vasculopatia_values = (vasculopatia_periferica, vasculopatia_carotidea, vasculopatia_femoral)
        vasculopatia_cualquiera = (
            True if any(value is True for value in vasculopatia_values)
            else False if any(value is False for value in vasculopatia_values)
            else None
        )
        disfuncion_erectil = _affirmative(_answer(answers_dict, 'r_disfunc'))

        # Dieta PREDIMED (Adherencia a Dieta Mediterránea)
        r_fru_val = answers_dict.get('usted_consume_fruta', '') or answers_dict.get('pred_q4', '')
        r_ver_val = answers_dict.get('usted_consume_verduras', '') or answers_dict.get('pred_q3', '')
        r_oli_val = answers_dict.get('usa_usted_aceite_de_oliva', '') or answers_dict.get('pred_q1', '')
        consume_fruta = 'si' in r_fru_val.lower() or 'sí' in r_fru_val.lower()
        consume_verdura = 'si' in r_ver_val.lower() or 'sí' in r_ver_val.lower()
        consume_oliva = 'si' in r_oli_val.lower() or 'sí' in r_oli_val.lower()
        predimed_adherencia = 'Buena Adherencia' if (consume_fruta and consume_verdura and consume_oliva) else 'Adherencia Moderada/Baja'

        # Riesgo Global (conteo de factores)
        factors = [hipertension, dislipemia, obesidad, diabetes, fumador_activo, higado_graso]
        factores_riesgo_count = sum(1 for f in factors if f)
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
        mal_ambiente_laboral = not _es_negativo(mal_amb_raw) and ('si' in str(mal_amb_raw).lower() or 'sí' in str(mal_amb_raw).lower())

        pers_a_raw = answers_dict.get('personalidad_tipo_a', '') or answers_dict.get('em_pers_a', '')
        personalidad_tipo_a = not _es_negativo(pers_a_raw) and ('si' in str(pers_a_raw).lower() or 'sí' in str(pers_a_raw).lower() or 'exigente' in str(pers_a_raw).lower())

        tox_raw = answers_dict.get('trabaja_con_toxicos', '') or answers_dict.get('em_toxicos', '')
        toxicos_laboral = not _es_negativo(tox_raw) and ('si' in str(tox_raw).lower() or 'sí' in str(tox_raw).lower())

        # Factores hormonales femeninos
        bajos_estrogenos = 'si' in (answers_dict.get('bajos_estrogenos', '') or answers_dict.get('em_estrogenos', '')).lower() or 'menopausia' in (answers_dict.get('bajos_estrogenos', '') or answers_dict.get('em_estrogenos', '')).lower()
        anticonceptivos_35 = 'si' in (answers_dict.get('proteccion_anticonceptivo', '') or answers_dict.get('em_anticonceptivos', '')).lower()

        # -------------------------------------------------------------
        # BLOQUE 5: ANTECEDENTES FAMILIARES
        # -------------------------------------------------------------
        ant_p_raw = answers_dict.get('antecedentes_padres', '') or ''
        ant_m_raw = answers_dict.get('antecedentes_madres', '') or ''

        ant_padre_hta = 'hta' in ant_p_raw.lower() or 'si' in answers_dict.get('ant_padre_hta', '').lower()
        ant_padre_dm = 'diab' in ant_p_raw.lower() or 'si' in answers_dict.get('ant_padre_dm', '').lower()
        ant_padre_dlp = 'dislip' in ant_p_raw.lower() or 'si' in answers_dict.get('ant_padre_dislip', '').lower()
        ant_padre_iam = 'iam' in ant_p_raw.lower() or 'infarto' in ant_p_raw.lower() or 'si' in answers_dict.get('ant_padre_iam', '').lower()
        ant_padre_acv = 'ictus' in ant_p_raw.lower() or 'acv' in ant_p_raw.lower() or 'si' in answers_dict.get('ant_padre_ictus', '').lower()

        ant_madre_hta = 'hta' in ant_m_raw.lower() or 'si' in answers_dict.get('ant_madre_hta', '').lower()
        ant_madre_dm = 'diab' in ant_m_raw.lower() or 'si' in answers_dict.get('ant_madre_dm', '').lower()
        ant_madre_dlp = 'dislip' in ant_m_raw.lower() or 'si' in answers_dict.get('ant_madre_dislip', '').lower()
        ant_madre_iam = 'iam' in ant_m_raw.lower() or 'infarto' in ant_m_raw.lower() or 'si' in answers_dict.get('ant_madre_iam', '').lower()
        ant_madre_acv = 'ictus' in ant_m_raw.lower() or 'acv' in ant_m_raw.lower() or 'si' in answers_dict.get('ant_madre_ictus', '').lower()

        ant_cardiopatia_prematura = 'si' in answers_dict.get('af_cardiopatia_prematura', '').lower()
        ant_muerte_subita = 'si' in answers_dict.get('af_muerte_subita', '').lower()

        ant_fam_hta = ant_padre_hta or ant_madre_hta
        ant_fam_dm = ant_padre_dm or ant_madre_dm
        ant_fam_dlp = ant_padre_dlp or ant_madre_dlp
        ant_fam_cv_mayor = ant_padre_iam or ant_madre_iam or ant_padre_acv or ant_madre_acv or ant_cardiopatia_prematura or ant_muerte_subita
        ant_fam_cualquiera = ant_fam_hta or ant_fam_dm or ant_fam_dlp or ant_fam_cv_mayor
        family_answered = _answer(
            answers_dict, 'antecedentes_padres', 'antecedentes_madres',
            'ant_padre_hta', 'ant_padre_dm', 'ant_padre_dislip', 'ant_padre_iam',
            'ant_padre_ictus', 'ant_madre_hta', 'ant_madre_dm',
            'ant_madre_dislip', 'ant_madre_iam', 'ant_madre_ictus',
            'af_cardiopatia_prematura', 'af_muerte_subita',
        )
        if family_answered is None:
            ant_padre_hta = ant_padre_dm = ant_padre_dlp = ant_padre_iam = ant_padre_acv = None
            ant_madre_hta = ant_madre_dm = ant_madre_dlp = ant_madre_iam = ant_madre_acv = None
            ant_cardiopatia_prematura = ant_muerte_subita = None
            ant_fam_hta = ant_fam_dm = ant_fam_dlp = ant_fam_cv_mayor = ant_fam_cualquiera = None

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
        covid_raw = (
            answers_dict.get('historia_covid', '') or
            answers_dict.get('covid_ingreso', '') or
            answers_dict.get('covid_paso', '') or
            answers_dict.get('covid_infeccion', '') or
            ''
        ).strip()
        c_low = covid_raw.lower()

        if not covid_raw or _es_negativo(covid_raw) or 'no ha pasado' in c_low:
            covid_infeccion = False
            covid_hospitalizacion = False
            covid_historia = 'No ha pasado COVID-19'
        elif 'con ingreso' in c_low or 'con hospital' in c_low:
            covid_infeccion = True
            covid_hospitalizacion = True
            covid_historia = 'Pasó COVID-19 con hospitalización'
        elif 'sin ingreso' in c_low or 'no especifica' in c_low or 'pasó' in c_low or 'paso' in c_low or 'si' in c_low or 'sí' in c_low:
            covid_infeccion = True
            covid_hospitalizacion = False
            covid_historia = 'Pasó COVID-19 sin hospitalización'
        else:
            covid_infeccion = False
            covid_hospitalizacion = False
            covid_historia = 'No ha pasado COVID-19'

        covid_secuelas_cardio = not _es_negativo(answers_dict.get('covid_secuelas_cardio', '') or answers_dict.get('covid_cv', '')) and ('si' in str(answers_dict.get('covid_secuelas_cardio', '') or answers_dict.get('covid_cv', '')).lower())
        covid_secuelas_resp = not _es_negativo(answers_dict.get('covid_secuelas_resp', '') or answers_dict.get('covid_pulm', '')) and ('si' in str(answers_dict.get('covid_secuelas_resp', '') or answers_dict.get('covid_pulm', '')).lower())

        long_covid_raw = (answers_dict.get('long_covid', '') or answers_dict.get('longcovid', '') or '').strip()
        if _es_negativo(long_covid_raw):
            covid_fatiga_long = False
        else:
            lc_low = long_covid_raw.lower()
            covid_fatiga_long = 'olfato' in lc_low or 'fatiga' in lc_low or lc_low == 'si' or lc_low == 'sí'

        covid_niebla_mental = not _es_negativo(answers_dict.get('covid_niebla', '')) and ('si' in str(answers_dict.get('covid_niebla', '')).lower())
        covid_tiene_secuelas = covid_secuelas_cardio or covid_secuelas_resp or covid_fatiga_long or covid_niebla_mental

        # -------------------------------------------------------------
        # BLOQUE 8: RESULTADOS DEL ELECTROCARDIOGRAMA (ECG)
        # -------------------------------------------------------------
        ecg = getattr(v, 'electrocardiogram', None)
        ecg_ritmo = ecg.rhythm.name if (ecg and ecg.rhythm) else 'Sin ECG'
        ecg_es_sinusal = ('sinusal' in ecg_ritmo.lower()) if ecg else None
        ecg_arritmia = (not ecg_es_sinusal) if ecg_es_sinusal is not None else None
        arritmias = ecg_arritmia

        ecg_fc = int(ecg.heart_rate) if (ecg and ecg.heart_rate) else None
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
        ecg_hvi = bool(ecg.left_ventricular_hypertrophy) if ecg else None
        bbb_raw = str(ecg.bundle_branch_block).strip().upper() if (ecg and ecg.bundle_branch_block) else ''
        if not bbb_raw or bbb_raw in ('NINGUNA', 'NINGUNO', 'NO', 'SIN BLOQUEO', 'NORMAL'):
            ecg_bloqueo_rama = 'Sin bloqueo'
        else:
            ecg_bloqueo_rama = str(ecg.bundle_branch_block).strip()
        ecg_repolarizacion = bool(ecg.repolarization_abnormalities) if ecg else None

        # -------------------------------------------------------------
        # COMPILACIÓN DEL REGISTRO EVALUADO
        # -------------------------------------------------------------
        record = {
            # Identificación y Filtros Transversales
            'id': v.visit_id,
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
            'riesgo_global': riesgo_global,

            # Bloque 1: Datos del Individuo
            'estado_civil': estado_civil,
            'nivel_estudios': nivel_estudios,
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
            'db_desc': db_desc,
            'dislipemia': dislipemia,
            'dl_desc': dl_desc,
            'tabaquismo': tabaquismo,
            'fumador_activo': fumador_activo,
            'alcohol': alcohol,
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
            'ecg_hvi': ecg_hvi,
            'ecg_bloqueo_rama': ecg_bloqueo_rama,
            'ecg_repolarizacion': ecg_repolarizacion,
        }
        records.append(record)

    sorted_years = sorted(list(available_years))
    sorted_categories = sorted(list(available_categories))
    sorted_institutions = sorted(list(available_institutions))

    n = len(records)
    def fmt_pct(cnt, field):
        valid = sum(r[field] is not None and r[field] != 'Sin dato' for r in records)
        return f"{(cnt / valid * 100):.1f}".replace('.', ',') if valid else 'Sin dato'

    # Resumen General KPIs
    hta_cnt = sum(1 for r in records if r['hipertension'])
    dl_cnt = sum(1 for r in records if r['dislipemia'])
    sp_ob_cnt = sum(1 for r in records if r['sobrepeso_u_obesidad'])
    riesgo_alto_cnt = sum(1 for r in records if r['factores_riesgo_count'] >= 2)

    summary_kpis = {
        'total': n,
        'hta_pct': fmt_pct(hta_cnt, 'hipertension'),
        'dl_pct': fmt_pct(dl_cnt, 'dislipemia'),
        'sp_ob_pct': fmt_pct(sp_ob_cnt, 'sobrepeso_u_obesidad'),
        'riesgo_alto_pct': fmt_pct(riesgo_alto_cnt, 'factores_riesgo_count'),
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
    tas_media = f"{(sum(valid_tas) / len(valid_tas)):.0f}" if valid_tas else "0"
    valid_tad = [r['tad'] for r in records if r['tad'] is not None and r['tad'] > 0]
    tad_media = f"{(sum(valid_tad) / len(valid_tad)):.0f}" if valid_tad else "0"
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
        'total': n,
        'summary_kpis': summary_kpis,
        'module_kpis': module_kpis,
        'years': sorted_years,
        'categories': sorted_categories,
        'institutions': sorted_institutions,
        'fichas': unique_fichas,
    }
