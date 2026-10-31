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
        sex_raw = p.sex.name if (p and p.sex) else 'Hombre'
        sexo = 'Mujer' if 'MUJER' in sex_raw.upper() or 'FEM' in sex_raw.upper() else 'Hombre'

        edad = get_age(p.birth_date, v_date)
        grupo_edad = get_age_group(edad)

        cat_raw = v.staff_category.name if v.staff_category else ''
        categoria = map_category_label(cat_raw)
        available_categories.add(categoria)

        # Respuestas del cuestionario asociadas
        answers_dict = {}
        for a in v.answers.all():
            q_code = a.question.code.lower()
            val = a.selected_option.option_text if a.selected_option else (a.text_value or a.numeric_value)
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
        estudios_val = v.education_level.name if v.education_level else answers_dict.get('f_estudios', 'Superior')
        if 'POST' in estudios_val.upper() or 'CUARTO' in estudios_val.upper() or 'MASTER' in estudios_val.upper() or 'DOCTOR' in estudios_val.upper():
            nivel_estudios = 'Postgrado'
        elif 'SUPERIOR' in estudios_val.upper() or 'TERCER' in estudios_val.upper() or 'UNIVERSIT' in estudios_val.upper():
            nivel_estudios = 'Superior'
        elif 'SECUNDAR' in estudios_val.upper() or 'BACHILLER' in estudios_val.upper():
            nivel_estudios = 'Secundaria'
        else:
            nivel_estudios = 'Primaria/Otros'

        # Tipo de vivienda
        vivienda_val = v.housing_type.name if v.housing_type else answers_dict.get('f_vivienda', 'Propia')
        if 'PROPIA' in vivienda_val.upper():
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
        peso = float(anth.weight_kg) if anth and anth.weight_kg else 0.0
        talla = float(anth.height_cm) if anth and anth.height_cm else 0.0

        imc = float(anth.bmi) if anth and anth.bmi is not None else 0.0
        if anth and peso > 0 and talla > 0 and imc == 0:
            h_m = talla / 100.0
            if h_m > 0:
                imc = round(peso / (h_m * h_m), 2)

        if imc < 18.5:
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

        obesidad = imc >= 30.0
        sobrepeso_u_obesidad = imc >= 25.0

        perimetro_abdominal = float(anth.waist_circumference_cm) if anth and anth.waist_circumference_cm is not None else None
        if perimetro_abdominal:
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
            abd_riesgo = 'No registrado'

        vs = getattr(v, 'vital_signs', None)
        tas = float(vs.systolic_bp) if vs and vs.systolic_bp is not None else 0.0
        tad = float(vs.diastolic_bp) if vs and vs.diastolic_bp is not None else 0.0
        fc = int(vs.heart_rate) if vs and vs.heart_rate is not None else 72
        sat_o2 = int(vs.oxygen_saturation) if vs and vs.oxygen_saturation is not None else 98

        # Clasificación de Presión Arterial
        if tas >= 140.0 or tad >= 90.0:
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
        r_hta_val = (
            answers_dict.get('r_hta', '') or
            answers_dict.get('hta', '') or
            answers_dict.get('hta_tto', '')
        )
        is_hta_ans = 'si' in r_hta_val.lower() or 'sí' in r_hta_val.lower()
        is_hta_bp = tas >= 140.0 or tad >= 90.0
        hipertension = is_hta_ans or is_hta_bp

        if 'tratada con farmacos' in r_hta_val.lower() or 'si tratada' in r_hta_val.lower() or 'si, y si tratada' in r_hta_val.lower():
            hta_desc = 'Tratada'
        elif hipertension:
            hta_desc = 'No tratada'
        else:
            hta_desc = 'Sin Hipertensión'

        # Diabetes Mellitus
        lab = getattr(v, 'laboratory', None)
        glucosa = float(lab.glucose_mg_dl) if lab and lab.glucose_mg_dl is not None else 0.0
        r_dm_val = (
            answers_dict.get('r_dm', '') or
            answers_dict.get('diabetes_mellitus', '') or
            answers_dict.get('dm', '') or
            answers_dict.get('diab_glucosa', '')
        )
        is_dm_ans = 'si' in r_dm_val.lower() or 'sí' in r_dm_val.lower()
        is_dm_lab = glucosa >= 126.0
        diabetes = is_dm_ans or is_dm_lab
        if 'tratada' in r_dm_val.lower():
            db_desc = 'Tipo 2 tratada'
        elif diabetes or glucosa >= 100.0:
            db_desc = 'Diabetes/Prediabetes'
        else:
            db_desc = 'No'

        # Dislipemia
        col_total = float(lab.total_cholesterol_mg_dl) if lab and lab.total_cholesterol_mg_dl is not None else 0.0
        col_ldl = float(lab.ldl_mg_dl) if lab and lab.ldl_mg_dl is not None else 0.0
        triglic = float(lab.triglycerides_mg_dl) if lab and lab.triglycerides_mg_dl is not None else 0.0

        r_dl_val = answers_dict.get('r_dislip', '') or answers_dict.get('dislipemia', '')
        is_dl_ans = 'si' in r_dl_val.lower() or 'sí' in r_dl_val.lower()
        is_dl_lab = col_total >= 200.0 or col_ldl >= 130.0 or triglic >= 150.0
        dislipemia = is_dl_ans or is_dl_lab
        if 'tratada con farmacos' in r_dl_val.lower():
            dl_desc = 'Tratada'
        elif dislipemia:
            dl_desc = 'No tratada'
        else:
            dl_desc = 'No'

        # Tabaquismo
        r_tab_val = answers_dict.get('r_tabaco', '') or answers_dict.get('tabaquismo', '')
        if 'no fuma' in r_tab_val.lower():
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
        r_alc_val = answers_dict.get('r_alcohol', '') or answers_dict.get('alcohol', '')
        if 'diario' in r_alc_val.lower() or 'diariamente' in r_alc_val.lower():
            alcohol = 'Diario'
        elif 'semanal' in r_alc_val.lower() or 'semanalmente' in r_alc_val.lower():
            alcohol = 'Semanal'
        elif 'ocasional' in r_alc_val.lower():
            alcohol = 'Ocasional'
        else:
            alcohol = 'No consume'

        # Actividad Física y Deporte
        r_act_val = (
            answers_dict.get('usted_realiza_actividad_fisica', '') or
            answers_dict.get('actividad_fisica', '') or
            answers_dict.get('af_camina', '') or
            answers_dict.get('af_aerobicos', '')
        )
        actividad_fisica = 'si' in r_act_val.lower() or 'sí' in r_act_val.lower()
        r_dep_val = answers_dict.get('af_deporte', '')
        deporte = 'si' in r_dep_val.lower() or 'sí' in r_dep_val.lower()

        # Hígado Graso
        r_hg_val = (
            answers_dict.get('r_higado', '') or
            answers_dict.get('higado_graso', '') or
            answers_dict.get('res_higado_graso', '')
        )
        higado_graso = 'si' in r_hg_val.lower() or 'sí' in r_hg_val.lower()

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
        r_sue_cal = answers_dict.get('calidad_sueno', '') or answers_dict.get('sueno_calidad', '')
        if 'buena' in r_sue_cal.lower():
            calidad_sueno = 'Buena'
        elif 'mala' in r_sue_cal.lower():
            calidad_sueno = 'Mala'
        else:
            calidad_sueno = 'Normal'

        r_sue_cant = answers_dict.get('cantidad_sueno', '') or answers_dict.get('sueno_cantidad', '')
        if 'buena' in r_sue_cant.lower():
            cantidad_sueno = 'Adecuada (7-8 h)'
        elif 'mala' in r_sue_cant.lower():
            cantidad_sueno = 'Insuficiente (<6 h)'
        else:
            cantidad_sueno = 'Normal'

        apnea_sueno = 'si' in (answers_dict.get('apnea_sueno', '') or answers_dict.get('apnea', '')).lower()

        # Estrés
        r_est_val = answers_dict.get('estres', '') or answers_dict.get('em_estres_trab', '')
        has_estres_trab = 'trabajo' in r_est_val.lower() or 'trebajo' in r_est_val.lower() or 'laboral' in r_est_val.lower()
        has_estres_fam = 'familiar' in r_est_val.lower()
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
        mal_ambiente_laboral = 'si' in (answers_dict.get('mal_ambiente_laboral', '') or answers_dict.get('em_mal_amb', '')).lower()
        personalidad_tipo_a = 'tipo a' in (answers_dict.get('personalidad_tipo_a', '') or answers_dict.get('em_pers_a', '')).lower()
        toxicos_laboral = 'si' in (answers_dict.get('trabaja_con_toxicos', '') or answers_dict.get('em_toxicos', '')).lower()

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

        # -------------------------------------------------------------
        # BLOQUE 6: HISTORIA CLÍNICA NO CARDIOVASCULAR
        # -------------------------------------------------------------
        resp_raw = answers_dict.get('problemas_respiratorios', '')
        asma = 'asma' in resp_raw.lower() or 'si' in answers_dict.get('ant_asma', '').lower() or 'si' in answers_dict.get('nc_asma', '').lower()
        epoc = 'epoc' in resp_raw.lower() or 'si' in answers_dict.get('ant_epoc', '').lower() or 'si' in answers_dict.get('nc_epoc', '').lower()
        if asma and epoc:
            respiratorio_desc = 'Asma y EPOC'
        elif asma:
            respiratorio_desc = 'Asma bronquial'
        elif epoc:
            respiratorio_desc = 'EPOC'
        else:
            respiratorio_desc = 'Sin patología respiratoria'

        mental_raw = answers_dict.get('salud_mental', '')
        ansiedad = 'ansiedad' in mental_raw.lower() or 'si' in answers_dict.get('ant_ansiedad', '').lower() or 'si' in answers_dict.get('nc_ansiedad', '').lower()
        depresion = 'depresi' in mental_raw.lower() or 'si' in answers_dict.get('ant_depresion', '').lower() or 'si' in answers_dict.get('nc_depresion', '').lower()
        if ansiedad and depresion:
            salud_mental_desc = 'Ansiedad y Depresión'
        elif ansiedad:
            salud_mental_desc = 'Ansiedad'
        elif depresion:
            salud_mental_desc = 'Depresión'
        else:
            salud_mental_desc = 'Sin trastorno diagnosticado'

        enfermedad_reumatologica = 'si' in answers_dict.get('enfermedad_reumatologicas', '').lower() or 'tiene' in answers_dict.get('enfermedad_reumatologicas', '').lower() or 'si' in answers_dict.get('ant_reuma', '').lower() or 'si' in answers_dict.get('nc_reuma', '').lower()
        cancer = 'si' in answers_dict.get('historia_cancer', '').lower() or 'si' in answers_dict.get('ant_cancer', '').lower() or 'si' in answers_dict.get('nc_cancer', '').lower()
        alergias_medicamentos = 'si' in answers_dict.get('alergias', '').lower() or 'si' in answers_dict.get('ant_alergias', '').lower() or 'si' in answers_dict.get('nc_alergia', '').lower()
        insuficiencia_renal = 'si' in answers_dict.get('r_irc', '').lower() or 'si' in answers_dict.get('irc', '').lower()

        # -------------------------------------------------------------
        # BLOQUE 7: COVID-19 Y SECUELAS
        # -------------------------------------------------------------
        covid_raw = answers_dict.get('historia_covid', '') or answers_dict.get('covid_paso', '') or answers_dict.get('covid_infeccion', '')
        covid_infeccion = 'si' in covid_raw.lower() or 'pasó' in covid_raw.lower() or 'paso' in covid_raw.lower()
        covid_hospitalizacion = 'con ingreso' in covid_raw.lower() or 'hospital' in covid_raw.lower() or 'si' in answers_dict.get('covid_hosp', '').lower() or 'si' in answers_dict.get('covid_ingreso', '').lower()

        if covid_hospitalizacion:
            covid_historia = 'Pasó COVID-19 con hospitalización'
        elif covid_infeccion:
            covid_historia = 'Pasó COVID-19 sin hospitalización'
        else:
            covid_historia = 'No ha pasado COVID-19'

        covid_secuelas_cardio = 'si' in answers_dict.get('covid_secuelas_cardio', '').lower() or 'si' in answers_dict.get('covid_cv', '').lower()
        covid_secuelas_resp = 'si' in answers_dict.get('covid_secuelas_resp', '').lower() or 'si' in answers_dict.get('covid_pulm', '').lower()
        long_covid_raw = answers_dict.get('long_covid', '') or answers_dict.get('longcovid', '')
        covid_fatiga_long = 'si' in answers_dict.get('covid_fatiga', '').lower() or ('no presentó' not in long_covid_raw.lower() and ('sí' in long_covid_raw.lower() or 'olfato' in long_covid_raw.lower() or 'fatiga' in long_covid_raw.lower()))
        covid_niebla_mental = 'si' in answers_dict.get('covid_niebla', '').lower()
        covid_tiene_secuelas = covid_secuelas_cardio or covid_secuelas_resp or covid_fatiga_long or covid_niebla_mental

        # -------------------------------------------------------------
        # BLOQUE 8: RESULTADOS DEL ELECTROCARDIOGRAMA (ECG)
        # -------------------------------------------------------------
        ecg = getattr(v, 'electrocardiogram', None)
        ecg_ritmo = ecg.rhythm.name if (ecg and ecg.rhythm) else 'Ritmo Sinusal (RS)'
        ecg_es_sinusal = bool('sinusal' in ecg_ritmo.lower())
        ecg_arritmia = bool(ecg and not ecg_es_sinusal)
        arritmias = ecg_arritmia

        ecg_fc = int(ecg.heart_rate) if (ecg and ecg.heart_rate) else fc
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
        ecg_hvi = bool(ecg and ecg.left_ventricular_hypertrophy)
        ecg_bloqueo_rama = str(ecg.bundle_branch_block).strip() if (ecg and ecg.bundle_branch_block) else 'Sin bloqueo'
        ecg_repolarizacion = bool(ecg and ecg.repolarization_abnormalities)

        # -------------------------------------------------------------
        # COMPILACIÓN DEL REGISTRO EVALUADO
        # -------------------------------------------------------------
        record = {
            # Identificación y Filtros Transversales
            'id': v.visit_id,
            'study_code': v.study_code,
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
    fmt_pct = lambda cnt: f"{(cnt / n * 100):.1f}".replace('.', ',') if n > 0 else "0,0"

    # Resumen General KPIs
    hta_cnt = sum(1 for r in records if r['hipertension'])
    dl_cnt = sum(1 for r in records if r['dislipemia'])
    sp_ob_cnt = sum(1 for r in records if r['sobrepeso_u_obesidad'])
    riesgo_alto_cnt = sum(1 for r in records if r['factores_riesgo_count'] >= 2)

    summary_kpis = {
        'total': n,
        'hta_pct': fmt_pct(hta_cnt),
        'dl_pct': fmt_pct(dl_cnt),
        'sp_ob_pct': fmt_pct(sp_ob_cnt),
        'riesgo_alto_pct': fmt_pct(riesgo_alto_cnt),
    }

    # KPIs específicos precalculados para cada bloque temático
    edad_media = f"{(sum(r['edad'] for r in records) / n):.1f}".replace('.', ',') if n > 0 else "0"
    hombres_cnt = sum(1 for r in records if r['sexo'] == 'Hombre')
    mujeres_cnt = sum(1 for r in records if r['sexo'] == 'Mujer')
    postgrado_cnt = sum(1 for r in records if r['nivel_estudios'] == 'Postgrado')
    casados_cnt = sum(1 for r in records if r['estado_civil'] == 'Casado/a')

    valid_imc = [r['imc'] for r in records if r['imc'] > 0]
    imc_medio = f"{(sum(valid_imc) / len(valid_imc)):.1f}".replace('.', ',') if valid_imc else "0,0"
    cintura_riesgo_cnt = sum(1 for r in records if 'Riesgo' in r['abd_riesgo'])
    valid_tas = [r['tas'] for r in records if r['tas'] > 0]
    tas_media = f"{(sum(valid_tas) / len(valid_tas)):.0f}" if valid_tas else "0"
    valid_tad = [r['tad'] for r in records if r['tad'] > 0]
    tad_media = f"{(sum(valid_tad) / len(valid_tad)):.0f}" if valid_tad else "0"
    valid_sato2 = [r['sat_o2'] for r in records if r['sat_o2'] > 0]
    sato2_media = f"{(sum(valid_sato2) / len(valid_sato2)):.0f}" if valid_sato2 else "0"

    dm_cnt = sum(1 for r in records if r['diabetes'])
    tabaco_cnt = sum(1 for r in records if r['fumador_activo'])
    act_fis_cnt = sum(1 for r in records if r['actividad_fisica'])

    sueno_malo_cnt = sum(1 for r in records if r['calidad_sueno'] == 'Mala')
    estres_cnt = sum(1 for r in records if r['estres'] != 'Sin estrés significativo')
    mal_amb_cnt = sum(1 for r in records if r['mal_ambiente_laboral'])
    pers_a_cnt = sum(1 for r in records if r['personalidad_tipo_a'])
    toxicos_cnt = sum(1 for r in records if r['toxicos_laboral'])

    fam_hta_cnt = sum(1 for r in records if r['ant_fam_hta'])
    fam_dm_cnt = sum(1 for r in records if r['ant_fam_dm'])
    fam_dlp_cnt = sum(1 for r in records if r['ant_fam_dlp'])
    fam_cv_mayor_cnt = sum(1 for r in records if r['ant_fam_cv_mayor'])

    resp_cnt = sum(1 for r in records if r['respiratorio_desc'] != 'Sin patología respiratoria')
    mental_cnt = sum(1 for r in records if r['salud_mental_desc'] != 'Sin trastorno diagnosticado')
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
            'hombres_pct': fmt_pct(hombres_cnt),
            'mujeres_pct': fmt_pct(mujeres_cnt),
            'postgrado_pct': fmt_pct(postgrado_cnt),
            'casados_pct': fmt_pct(casados_cnt),
        },
        'exploracion': {
            'imc_medio': imc_medio,
            'cintura_riesgo_pct': fmt_pct(cintura_riesgo_cnt),
            'tas_media': tas_media,
            'tad_media': tad_media,
            'sat_o2_media': sato2_media,
        },
        'modificables': {
            'hta_pct': fmt_pct(hta_cnt),
            'dm_pct': fmt_pct(dm_cnt),
            'dl_pct': fmt_pct(dl_cnt),
            'tabaco_pct': fmt_pct(tabaco_cnt),
            'act_fisica_pct': fmt_pct(act_fis_cnt),
        },
        'emergentes': {
            'sueno_malo_pct': fmt_pct(sueno_malo_cnt),
            'estres_pct': fmt_pct(estres_cnt),
            'mal_ambiente_pct': fmt_pct(mal_amb_cnt),
            'personalidad_a_pct': fmt_pct(pers_a_cnt),
            'toxicos_pct': fmt_pct(toxicos_cnt),
        },
        'familiares': {
            'fam_hta_pct': fmt_pct(fam_hta_cnt),
            'fam_dm_pct': fmt_pct(fam_dm_cnt),
            'fam_dlp_pct': fmt_pct(fam_dlp_cnt),
            'fam_cv_mayor_pct': fmt_pct(fam_cv_mayor_cnt),
        },
        'no_cardio': {
            'respiratorio_pct': fmt_pct(resp_cnt),
            'salud_mental_pct': fmt_pct(mental_cnt),
            'reuma_pct': fmt_pct(reuma_cnt),
            'alergias_pct': fmt_pct(alergias_cnt),
        },
        'covid': {
            'covid_inf_pct': fmt_pct(covid_inf_cnt),
            'covid_hosp_pct': fmt_pct(covid_hosp_cnt),
            'covid_sec_pct': fmt_pct(covid_sec_cnt),
            'covid_fatiga_pct': fmt_pct(covid_fatiga_cnt),
        },
        'ecg': {
            'sinusal_pct': fmt_pct(ecg_sinusal_cnt),
            'arritmia_pct': fmt_pct(ecg_arritmia_cnt),
            'pr_medio': pr_medio,
            'qrs_medio': qrs_medio,
            'qtc_medio': qtc_medio,
        }
    }

    return {
        'records': records,
        'total': n,
        'summary_kpis': summary_kpis,
        'module_kpis': module_kpis,
        'years': sorted_years,
        'categories': sorted_categories,
        'institutions': sorted_institutions,
    }
