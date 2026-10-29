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
"""

from datetime import date
from decimal import Decimal
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
    evaluation records for dynamic client-side and server-side aggregation.
    """
    visits = (
        Visit.objects.select_related(
            'patient',
            'patient__sex',
            'patient__institution',
            'staff_category',
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

    for v in visits:
        p = v.patient
        v_date = v.visit_date or date(2024, 1, 1)
        ano = v_date.year
        available_years.add(ano)

        # Sex
        sex_raw = p.sex.name if (p and p.sex) else 'Hombre'
        sexo = 'Mujer' if 'MUJER' in sex_raw.upper() or 'FEM' in sex_raw.upper() else 'Hombre'

        # Age
        edad = get_age(p.birth_date, v_date)
        grupo_edad = get_age_group(edad)

        # Staff Category
        cat_raw = v.staff_category.name if v.staff_category else ''
        categoria = map_category_label(cat_raw)
        available_categories.add(categoria)

        # Questionnaire answers dictionary
        answers_dict = {}
        for a in v.answers.all():
            q_code = a.question.code.lower()
            val = a.selected_option.option_text if a.selected_option else (a.text_value or a.numeric_value)
            answers_dict[q_code] = str(val).strip() if val is not None else ''

        # Vital Signs (Blood Pressure)
        vs = getattr(v, 'vital_signs', None)
        tas = float(vs.systolic_bp) if vs and vs.systolic_bp is not None else 0.0
        tad = float(vs.diastolic_bp) if vs and vs.diastolic_bp is not None else 0.0

        # Hypertension (HTA)
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

        # Anthropometry (Weight, Height, BMI, Waist)
        anth = getattr(v, 'anthropometry', None)
        imc = float(anth.bmi) if anth and anth.bmi is not None else 0.0
        if anth and anth.weight_kg and anth.height_cm and imc == 0:
            h_m = float(anth.height_cm) / 100.0
            if h_m > 0:
                imc = round(float(anth.weight_kg) / (h_m * h_m), 2)

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

        # Laboratory (Glucose, Lipids)
        lab = getattr(v, 'laboratory', None)
        glucosa = float(lab.glucose_mg_dl) if lab and lab.glucose_mg_dl is not None else 0.0
        col_total = float(lab.total_cholesterol_mg_dl) if lab and lab.total_cholesterol_mg_dl is not None else 0.0
        col_ldl = float(lab.ldl_mg_dl) if lab and lab.ldl_mg_dl is not None else 0.0
        triglic = float(lab.triglycerides_mg_dl) if lab and lab.triglycerides_mg_dl is not None else 0.0

        # Diabetes Mellitus
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

        # Dyslipidemia
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

        # Fatty Liver (Esteatosis hepática)
        r_hg_val = (
            answers_dict.get('r_higado', '') or
            answers_dict.get('higado_graso', '') or
            answers_dict.get('res_higado_graso', '')
        )
        higado_graso = 'si' in r_hg_val.lower() or 'sí' in r_hg_val.lower()

        # Smoking
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

        # Alcohol Consumption
        r_alc_val = answers_dict.get('r_alcohol', '') or answers_dict.get('alcohol', '')
        if 'diario' in r_alc_val.lower() or 'diariamente' in r_alc_val.lower():
            alcohol = 'Diario'
        elif 'semanal' in r_alc_val.lower() or 'semanalmente' in r_alc_val.lower():
            alcohol = 'Semanal'
        elif 'ocasional' in r_alc_val.lower():
            alcohol = 'Ocasional'
        else:
            alcohol = 'No consume'

        # Physical Activity
        r_act_val = (
            answers_dict.get('usted_realiza_actividad_fisica', '') or
            answers_dict.get('actividad_fisica', '') or
            answers_dict.get('af_camina', '') or
            answers_dict.get('af_aerobicos', '')
        )
        actividad_fisica = 'si' in r_act_val.lower() or 'sí' in r_act_val.lower()

        # Organized Sports
        r_dep_val = answers_dict.get('af_deporte', '')
        deporte = 'si' in r_dep_val.lower() or 'sí' in r_dep_val.lower()

        # Arrhythmias (ECG)
        ecg = getattr(v, 'electrocardiogram', None)
        arritmias = bool(ecg and ecg.rhythm and 'sinusal' not in ecg.rhythm.name.lower())

        # Stress
        r_est_val = answers_dict.get('estres', '') or answers_dict.get('em_estres_trab', '')
        if 'trabajo' in r_est_val.lower() or 'trebajo' in r_est_val.lower() or 'laboral' in r_est_val.lower():
            estres = 'Laboral'
        elif 'familiar' in r_est_val.lower():
            estres = 'Familiar'
        else:
            estres = 'Sin estrés significativo'

        # Sleep Quality
        r_sue_val = (
            answers_dict.get('calidad_sueno', '') or
            answers_dict.get('sueno_calidad', '') or
            answers_dict.get('cantidad_sueno', '') or
            answers_dict.get('sueno_cantidad', '')
        )
        if 'buena' in r_sue_val.lower():
            calidad_sueno = 'Buena'
        elif 'mala' in r_sue_val.lower():
            calidad_sueno = 'Mala'
        else:
            calidad_sueno = 'No evaluada'

        # Diet (Fruit and Vegetables)
        r_fru_val = answers_dict.get('usted_consume_fruta', '') or answers_dict.get('pred_q4', '')
        r_ver_val = answers_dict.get('usted_consume_verduras', '') or answers_dict.get('pred_q3', '')
        consume_fruta = 'si' in r_fru_val.lower() or 'sí' in r_fru_val.lower()
        consume_verdura = 'si' in r_ver_val.lower() or 'sí' in r_ver_val.lower()

        # Risk Factors Count (HTA, Dislipemia, Obesidad, Diabetes, Fumador Activo, Hígado Graso)
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

        record = {
            'id': v.visit_id,
            'study_code': v.study_code,
            'ano': ano,
            'sexo': sexo,
            'edad': edad,
            'grupo_edad': grupo_edad,
            'categoria': categoria,
            'hipertension': hipertension,
            'hta_desc': hta_desc,
            'tas': tas,
            'tad': tad,
            'diabetes': diabetes,
            'db_desc': db_desc,
            'dislipemia': dislipemia,
            'dl_desc': dl_desc,
            'imc': imc,
            'imc_cat': imc_cat,
            'obesidad': obesidad,
            'sobrepeso_u_obesidad': sobrepeso_u_obesidad,
            'perimetro_abdominal': perimetro_abdominal,
            'abd_riesgo': abd_riesgo,
            'higado_graso': higado_graso,
            'tabaquismo': tabaquismo,
            'fumador_activo': fumador_activo,
            'alcohol': alcohol,
            'actividad_fisica': actividad_fisica,
            'deporte': deporte,
            'arritmias': arritmias,
            'estres': estres,
            'calidad_sueno': calidad_sueno,
            'consume_fruta': consume_fruta,
            'consume_verdura': consume_verdura,
            'factores_riesgo_count': factores_riesgo_count,
            'riesgo_global': riesgo_global,
        }
        records.append(record)

    sorted_years = sorted(list(available_years))
    sorted_categories = sorted(list(available_categories))

    return {
        'records': records,
        'total': len(records),
        'years': sorted_years,
        'categories': sorted_categories,
    }
