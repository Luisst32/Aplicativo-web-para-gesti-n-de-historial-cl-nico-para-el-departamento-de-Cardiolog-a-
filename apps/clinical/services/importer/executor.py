# -*- coding: utf-8 -*-
"""
executor.py
Ejecución transaccional masiva de importación clínica a PostgreSQL.
Crea o sincroniza Paciente, Visita, Antropometría, Signos Vitales,
Electrocardiograma, Ecocardiograma, Laboratorio y Cuestionarios (VisitAnswers).
"""

import os
import re
import datetime
import unicodedata
import math
import sys
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from security.access import require_clinical_access
from clinical.services.import_tickets import claim_upload, InvalidImportTicket, ERROR_MESSAGE

from catalog.models import (
    Institution, Sex, Ethnicity, Canton, Province, Country,
    StaffCategory, ProfessionalCategory, MaritalStatus,
    LivingSituation, EducationLevel, WorkSchedule, HousingType,
    IncomeRange, EcgRhythm, Question, QuestionnaireSection
)
from clinical.models import (
    Patient, Visit, Anthropometry, VitalSigns,
    Electrocardiogram, Echocardiogram, Laboratory, VisitAnswer,
    OrderedStudies
)

try:
    from audit.models import ChangeLog
except ImportError:
    ChangeLog = None

from .constants import (
    SPSS_QUESTION_ALIASES,
    STANDARD_FIELD_ALIASES,
    FIELD_DESTINATIONS,
    CIUDAD_CODE_MAP,
)
from .normalizers import (
    normalize_var_name,
    classify_spss_question_section,
    _match_column_to_field,
    _resolve_canton_safe,
    _is_empty_or_nan,
    _clean_decimal,
    _get_val_and_label,
)
from .readers import _read_dataset_file


def execute_sav_import(temp_token, user, current_year=2026, duplicate_action="update"):
    require_clinical_access(user, 'import')
    try:
        with claim_upload(temp_token, user) as temp_path:
            import sys
            sav_mod = sys.modules.get('clinical.services.sav_importer') or sys.modules.get('apps.clinical.services.sav_importer')
            exec_fn = getattr(sav_mod, '_execute_staged_dataset', _execute_staged_dataset) if sav_mod else _execute_staged_dataset
            return exec_fn(temp_path, user, current_year, duplicate_action)
    except InvalidImportTicket:
        return {'success': False, 'error': ERROR_MESSAGE}


def _execute_staged_dataset(temp_path, user, current_year=2026, duplicate_action="update", reader_fn=None):
    """
    Importa transaccionalmente todas las filas del archivo SPSS a PostgreSQL a máxima velocidad.
    Crea/actualiza Paciente, Visita, Antropometría, Signos Vitales, ECG, Eco, Lab y VisitAnswers
    utilizando bulk_create con ON CONFLICT y pre-indexación en memoria.
    """
    if reader_fn is None:
        import sys
        sav_mod = sys.modules.get('clinical.services.sav_importer') or sys.modules.get('apps.clinical.services.sav_importer')
        if sav_mod and hasattr(sav_mod, '_read_dataset_file'):
            reader_fn = sav_mod._read_dataset_file
        else:
            reader_fn = _read_dataset_file
    try:
        df_dict, meta = reader_fn(temp_path, temp_path.name)
    except Exception as e:
        return {
            "success": False,
            "error": f"Error al procesar archivo de datos: {str(e)}"
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
    default_canton = _resolve_canton_safe('Milagro') or Canton.objects.first()
    sections_by_code = {s.code: s for s in QuestionnaireSection.objects.all()}
    default_section = sections_by_code.get('MOD_3_FACTORES_MOD') or QuestionnaireSection.objects.first()
    if not default_section:
        default_section, _ = QuestionnaireSection.objects.get_or_create(code='GENERAL', defaults={'name': 'General', 'display_order': 1})

    staff_map = {
        'PDI': StaffCategory.objects.filter(name__icontains='PDI').first(),
        'PAS': StaffCategory.objects.filter(name__icontains='PAS').first(),
        'SERVICIO': StaffCategory.objects.filter(name__icontains='SERVICIO').first(),
        'ESTUDIANTES': StaffCategory.objects.filter(name__icontains='ESTUDIANTE').first(),
    }
    staff_num_map = {
        1: staff_map['PDI'],
        2: staff_map['PAS'],
        4: staff_map['SERVICIO'],
        5: staff_map['ESTUDIANTES'],
    }
    marital_map = {
        'SOLTERO': MaritalStatus.objects.filter(name__icontains='Soltero').first(),
        'CASADO': MaritalStatus.objects.filter(name__icontains='Casado').first(),
        'DIVORCIADO': MaritalStatus.objects.filter(name__icontains='Divorciado').first(),
        'VIUDO': MaritalStatus.objects.filter(name__icontains='Viudo').first(),
        'UNION': MaritalStatus.objects.filter(name__icontains='Unión').first(),
    }
    marital_num_map = {
        1: marital_map['SOLTERO'],
        2: marital_map['CASADO'],
        3: marital_map['DIVORCIADO'],
        4: marital_map['VIUDO'],
        5: marital_map['UNION'],
        6: marital_map['CASADO'],
    }
    living_map = {
        'SOLO': LivingSituation.objects.filter(name__icontains='Solo').first(),
        'PAREJA': LivingSituation.objects.filter(name__icontains='pareja').first(),
        'FAMILIA': LivingSituation.objects.filter(name__icontains='familia').first(),
        'AMIGOS': LivingSituation.objects.filter(name__icontains='amigo').first(),
    }
    living_num_map = {
        1: living_map['SOLO'],
        2: living_map['PAREJA'],
        3: living_map['PAREJA'],
        4: living_map['FAMILIA'],
        5: living_map['FAMILIA'],
        6: living_map['FAMILIA'],
        7: living_map['AMIGOS'],
    }
    education_map = {
        'PRIMARIA': EducationLevel.objects.filter(name__icontains='Primaria').first(),
        'SECUNDARIA': EducationLevel.objects.filter(name__icontains='Secundaria').first(),
        'SUPERIOR': EducationLevel.objects.filter(name__icontains='Tercer').first(),
        'POSTGRADO': EducationLevel.objects.filter(name__icontains='Cuarto').first(),
    }
    education_num_map = {
        1: education_map['PRIMARIA'],
        2: education_map['PRIMARIA'],
        3: education_map['PRIMARIA'],
        4: education_map['SECUNDARIA'],
        5: education_map['SECUNDARIA'],
        6: education_map['SUPERIOR'],
        7: education_map['POSTGRADO'],
    }
    work_map = {
        'PARTIDA': WorkSchedule.objects.filter(name__icontains='Completo').first(),
        'CONTINUA': WorkSchedule.objects.filter(name__icontains='Completo').first(),
        'TURNO': WorkSchedule.objects.filter(name__icontains='Turno').first(),
        'PARCIAL': WorkSchedule.objects.filter(name__icontains='Parcial').first(),
    }
    work_num_map = {
        1: work_map['PARTIDA'],
        2: work_map['CONTINUA'],
        3: work_map['PARCIAL'],
        4: work_map['TURNO'],
        5: work_map['TURNO'],
    }
    prof_titular = ProfessionalCategory.objects.filter(name__icontains='Titular').first()
    prof_ocasional = ProfessionalCategory.objects.filter(name__icontains='Ocasional').first()
    prof_publico = ProfessionalCategory.objects.filter(name__icontains='Público').first()
    prof_servicios = ProfessionalCategory.objects.filter(name__icontains='Auxiliar').first()
    prof_estudiante = ProfessionalCategory.objects.filter(name__icontains='Estudiante').first()
    prof_otro = ProfessionalCategory.objects.filter(name__icontains='Otro').first()
    prof_map = {
        'PERMANENTE': prof_titular,
        'TITULAR': prof_titular,
        'NO PERMANENTE': prof_ocasional,
        'OCASIONAL': prof_ocasional,
        'ADMINISTRACION': prof_publico,
        'SERVIDOR': prof_publico,
        'SERVICIO': prof_servicios,
        'AUXILIAR': prof_servicios,
        'ESTUDIANTE': prof_estudiante,
        'OTRO': prof_otro,
    }
    prof_num_map = {
        1: prof_titular,
        2: prof_ocasional,
        3: prof_publico,
        4: prof_servicios,
        5: prof_otro,
        6: prof_estudiante,
    }
    housing_map = {
        'PROPIA': HousingType.objects.filter(name__icontains='Propia').first(),
        'ALQUILADA': HousingType.objects.filter(name__icontains='Arrendada').first(),
        'FAMILIAR': HousingType.objects.filter(name__icontains='Familiar').first(),
        'OTRO': HousingType.objects.filter(name__icontains='Prestada').first(),
    }
    housing_num_map = {
        1: housing_map['PROPIA'],
        2: housing_map['ALQUILADA'],
        3: housing_map['FAMILIAR'],
        4: housing_map['OTRO'],
    }
    income_map = {
        '500': IncomeRange.objects.filter(name__icontains='500').first(),
        '1000': IncomeRange.objects.filter(name__icontains='1000').first(),
        '1500': IncomeRange.objects.filter(name__icontains='1001').first(),
        '2000': IncomeRange.objects.filter(name__icontains='2000').first(),
    }
    income_num_map = {
        1: income_map['500'],
        2: income_map['1000'],
        3: income_map['1500'],
        4: income_map['1500'],
        5: income_map['2000'],
        6: income_map['2000'],
        7: income_map['2000'],
        8: income_map['2000'],
    }
    rhythm_default = EcgRhythm.objects.first()
    if not rhythm_default:
        rhythm_default = EcgRhythm.objects.create(name='Sinusal', status=EcgRhythm.Status.ACTIVE)

    # Pre-cargar y preparar en memoria todas las Preguntas (Questions)
    existing_questions = {q.code: q for q in Question.objects.all()}
    col_code_map = {}
    for col_name in col_names:
        clean = normalize_var_name(col_name)
        if clean:
            clean_30 = clean[:30]
            col_code_map[col_name] = clean_30
            if clean_30 not in existing_questions:
                target_sec_code = classify_spss_question_section(col_name)
                target_sec = sections_by_code.get(target_sec_code) or default_section
                var_label = meta.column_names_to_labels.get(col_name) or col_name
                q = Question.objects.create(
                    section=target_sec,
                    code=clean_30,
                    text=str(var_label)[:255],
                    response_type=Question.ResponseType.TEXTO,
                    display_order=999
                )
                existing_questions[clean_30] = q

    for form_k in SPSS_QUESTION_ALIASES.keys():
        if form_k not in existing_questions:
            q_form = Question.objects.create(
                section=default_section,
                code=form_k,
                text=f"Campo {form_k}",
                response_type=Question.ResponseType.TEXTO,
                display_order=999
            )
            existing_questions[form_k] = q_form

    derived_keys = [
        ('em_estres_trab', 'MOD_3_FACTORES_EMERG'),
        ('em_estres_fam', 'MOD_3_FACTORES_EMERG'),
        ('em_pers_a', 'MOD_3_FACTORES_EMERG'),
        ('ant_padre_hta', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_padre_dm', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_padre_iam', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_padre_ictus', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_madre_hta', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_madre_dm', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_madre_iam', 'MOD_3_ANTECEDENTES_FAM'),
        ('ant_madre_ictus', 'MOD_3_ANTECEDENTES_FAM'),
        ('covid_paso', 'MOD_4_COVID'),
        ('covid_ingreso', 'MOD_4_COVID'),
        ('longcovid', 'MOD_4_COVID'),
        ('pred_q1', 'MOD_6_PREDIMED'),
        ('pred_q2', 'MOD_6_PREDIMED'),
        ('act_realiza', 'MOD_6_ACTIVIDAD_FISICA'),
        ('act_aerob', 'MOD_6_ACTIVIDAD_FISICA'),
        ('act_anaerob', 'MOD_6_ACTIVIDAD_FISICA'),
        ('act_deporte', 'MOD_6_ACTIVIDAD_FISICA'),
        ('r_hta', 'MOD_3_FACTORES_MOD'),
        ('r_hta_farmacos', 'MOD_3_FACTORES_MOD'),
        ('r_dislipemia', 'MOD_3_FACTORES_MOD'),
        ('r_dislip_farmacos', 'MOD_3_FACTORES_MOD'),
        ('r_vasculopatia', 'MOD_3_FACTORES_MOD'),
        ('r_vasc_femoral', 'MOD_3_FACTORES_MOD'),
        ('r_holter', 'MOD_3_FACTORES_MOD'),
        ('holter_resultado', 'MOD_3_FACTORES_MOD'),
        ('r_mapa', 'MOD_3_FACTORES_MOD')
    ]
    for d_k, s_cd in derived_keys:
        if d_k not in existing_questions:
            sec_obj = sections_by_code.get(s_cd, default_section)
            q_d = Question.objects.create(
                section=sec_obj,
                code=d_k,
                text=f"Campo {d_k}",
                response_type=Question.ResponseType.TEXTO,
                display_order=999
            )
            existing_questions[d_k] = q_d

    # Pre-escanear identificadores de todas las filas con diferenciación por institución
    row_meta = []
    for i in range(total_rows):
        raw_cod = None
        if 'codigo' in field_to_col:
            raw_cod = df_dict[field_to_col['codigo']][i]
        if raw_cod is not None and str(raw_cod).strip() != '':
            if isinstance(raw_cod, (int, float)):
                sc = str(int(raw_cod))
            else:
                sc = str(raw_cod).strip()
        else:
            sc = str(i + 1)

        row_inst = inst_unemi
        if 'universidad' in field_to_col:
            u_val = df_dict[field_to_col['universidad']][i]
            _, u_lbl = _get_val_and_label(u_val, meta.variable_value_labels.get(field_to_col['universidad'], {}))
            if 'ESPOL' in u_lbl.upper() or u_val == 2.0:
                row_inst = inst_espol

        id_c = None
        if 'cedula' in field_to_col:
            v_ced = df_dict[field_to_col['cedula']][i]
            if v_ced and str(v_ced).strip():
                id_c = str(v_ced).strip()
        if not id_c:
            numeric_num = int(re.sub(r'[^0-9]', '', sc)) if any(c.isdigit() for c in sc) else (i + 1)
            inst_pfx = "08" if row_inst == inst_espol else "09"
            id_c = f"{inst_pfx}{str(numeric_num).zfill(8)}"

        row_meta.append((sc, id_c, row_inst))

    all_scs = [sc for sc, _, _ in row_meta]
    all_ids = [id_c for _, id_c, _ in row_meta]

    # Pre-indexar visitas por (institución_id, study_code) y pacientes por cédula
    existing_visits = {
        (v.patient.institution_id, v.study_code): v
        for v in Visit.objects.filter(study_code__in=all_scs)
        .select_related('patient', 'anthropometry', 'vital_signs', 'electrocardiogram', 'laboratory', 'echocardiogram', 'ordered_studies')
    }
    existing_patients = {
        p.id_card: p
        for p in Patient.objects.filter(id_card__in=all_ids)
        .select_related('visit', 'visit__anthropometry', 'visit__vital_signs', 'visit__electrocardiogram', 'visit__laboratory', 'visit__echocardiogram', 'visit__ordered_studies')
    }

    created_count = 0
    updated_count = 0
    skipped_count = 0
    duplicate_records = []
    errors = []
    answers_to_upsert = {}

    with transaction.atomic():
        for i in range(total_rows):
            study_code, id_card, inst = row_meta[i]
            row_answers = {}

            try:
                with transaction.atomic():

                    # 2. Datos Demográficos
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

                    sex = sex_hombre
                    if 'sexo' in field_to_col:
                        s_val = df_dict[field_to_col['sexo']][i]
                        vlabels_s = meta.variable_value_labels.get(field_to_col['sexo'], {})
                        if not vlabels_s:
                            vlabels_s = meta.variable_value_labels.get('SEXO', {})
                        _, s_lbl = _get_val_and_label(s_val, vlabels_s)
                        if 'MUJER' in s_lbl.upper() or s_val in [2.0, 2, '2', '2.0', 'F', 'Mujer', 'FEMENINO']:
                            sex = sex_mujer
                        elif 'HOMBRE' in s_lbl.upper() or s_val in [1.0, 1, '1', '1.0', 'M', 'Hombre', 'MASCULINO']:
                            sex = sex_hombre

                    edad_val = None
                    if 'edad' in field_to_col:
                        raw_edad = df_dict[field_to_col['edad']][i]
                        if raw_edad is not None:
                            try: edad_val = int(float(raw_edad))
                            except Exception: pass

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

                    birth_canton = default_canton
                    if 'ciudad_nac' in field_to_col:
                        val_cn = df_dict[field_to_col['ciudad_nac']][i]
                        vlabels_cn = meta.variable_value_labels.get(field_to_col['ciudad_nac'], {})
                        if not vlabels_cn:
                            vlabels_cn = meta.variable_value_labels.get('CIUDAD', {})
                        _, lbl_cn = _get_val_and_label(val_cn, vlabels_cn)
                        rc = _resolve_canton_safe(lbl_cn or val_cn)
                        if rc: birth_canton = rc

                    residence_canton = default_canton
                    if 'ciudad_res' in field_to_col:
                        val_cr = df_dict[field_to_col['ciudad_res']][i]
                        vlabels_cr = meta.variable_value_labels.get(field_to_col['ciudad_res'], {})
                        if not vlabels_cr:
                            vlabels_cr = meta.variable_value_labels.get('CIUDAD', {})
                        _, lbl_cr = _get_val_and_label(val_cr, vlabels_cr)
                        rc = _resolve_canton_safe(lbl_cr or val_cr)
                        if rc: residence_canton = rc

                    # 3. Paciente
                    existing_v = existing_visits.get((inst.institution_id, study_code))
                    patient = existing_v.patient if (existing_v and existing_v.patient) else existing_patients.get(id_card)
                    is_duplicate_case = bool(patient or existing_v)

                    if patient and duplicate_action == "skip":
                        skipped_count += 1
                        duplicate_records.append({
                            "row": i + 1,
                            "code": study_code,
                            "institution": inst.acronym if inst else "UNEMI",
                            "patient_name": patient.full_name or f"Participante {study_code}",
                            "id_card": patient.id_card,
                            "action": "Omitido"
                        })
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
                    existing_patients[id_card] = patient

                    # 4. Visita
                    visit = getattr(patient, 'visit', None) or existing_v
                    if not visit:
                        visit = Visit(patient=patient, study_code=study_code)
                        created_count += 1
                    else:
                        updated_count += 1
                        if is_duplicate_case:
                            duplicate_records.append({
                                "row": i + 1,
                                "code": study_code,
                                "institution": inst.acronym if inst else "UNEMI",
                                "patient_name": patient.full_name or f"Participante {study_code}",
                                "id_card": patient.id_card,
                                "action": "Actualizado en BD"
                            })

                    visit.evaluator = user
                    visit.residence_canton = residence_canton

                    visit_date = datetime.date.today()
                    if 'fecha_visita' in field_to_col:
                        raw_fv = df_dict[field_to_col['fecha_visita']][i]
                        if hasattr(raw_fv, 'year'):
                            visit_date = raw_fv
                        elif isinstance(raw_fv, str) and raw_fv.strip():
                            try: visit_date = datetime.date.fromisoformat(raw_fv.strip())
                            except Exception: pass
                    visit.visit_date = visit_date

                    if 'estamento' in field_to_col:
                        st_val = df_dict[field_to_col['estamento']][i]
                        vlabels_st = meta.variable_value_labels.get(field_to_col['estamento'], {})
                        if not vlabels_st:
                            vlabels_st = meta.variable_value_labels.get('Categoria_Personal', {})
                        _, st_lbl = _get_val_and_label(st_val, vlabels_st)
                        st_found = False
                        if st_lbl:
                            for k_st, sc_obj in staff_map.items():
                                if k_st in st_lbl.upper():
                                    visit.staff_category = sc_obj
                                    st_found = True
                                    break
                        if not st_found and st_val is not None:
                            try:
                                st_int = int(float(st_val))
                                if st_int in staff_num_map:
                                    visit.staff_category = staff_num_map[st_int]
                            except Exception: pass

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

                    if 'estado_civil' in field_to_col:
                        ec_val = df_dict[field_to_col['estado_civil']][i]
                        vlabels_ec = meta.variable_value_labels.get(field_to_col['estado_civil'], {})
                        if not vlabels_ec:
                            vlabels_ec = meta.variable_value_labels.get('ESTADO_CIVIL', {})
                        _, ec_lbl = _get_val_and_label(ec_val, vlabels_ec)
                        ec_found = False
                        if ec_lbl:
                            for k_ec, ms_obj in marital_map.items():
                                if k_ec in ec_lbl.upper():
                                    visit.marital_status = ms_obj
                                    ec_found = True
                                    break
                        if not ec_found and ec_val is not None:
                            try:
                                ec_int = int(float(ec_val))
                                if ec_int in marital_num_map:
                                    visit.marital_status = marital_num_map[ec_int]
                            except Exception: pass

                    if 'convive_con' in field_to_col:
                        cc_val = df_dict[field_to_col['convive_con']][i]
                        vlabels_cc = meta.variable_value_labels.get(field_to_col['convive_con'], {})
                        if not vlabels_cc:
                            vlabels_cc = meta.variable_value_labels.get('CON_QUIEN_VIVE', {})
                        _, cc_lbl = _get_val_and_label(cc_val, vlabels_cc)
                        cc_found = False
                        if cc_lbl:
                            for k_cc, ls_obj in living_map.items():
                                if k_cc in cc_lbl.upper():
                                    visit.living_situation = ls_obj
                                    cc_found = True
                                    break
                        if not cc_found and cc_val is not None:
                            try:
                                cc_int = int(float(cc_val))
                                if cc_int in living_num_map:
                                    visit.living_situation = living_num_map[cc_int]
                            except Exception: pass

                    if 'estudios' in field_to_col:
                        ed_val = df_dict[field_to_col['estudios']][i]
                        vlabels_ed = meta.variable_value_labels.get(field_to_col['estudios'], {})
                        if not vlabels_ed:
                            vlabels_ed = meta.variable_value_labels.get('NIVEL_ESTUDIOS_OBTENIDO', {})
                        _, ed_lbl = _get_val_and_label(ed_val, vlabels_ed)
                        ed_found = False
                        if ed_lbl:
                            for k_ed, ed_obj in education_map.items():
                                if k_ed in ed_lbl.upper():
                                    visit.education_level = ed_obj
                                    ed_found = True
                                    break
                        if not ed_found and ed_val is not None:
                            try:
                                ed_int = int(float(ed_val))
                                if ed_int in education_num_map:
                                    visit.education_level = education_num_map[ed_int]
                            except Exception: pass

                    if 'horario' in field_to_col:
                        ho_val = df_dict[field_to_col['horario']][i]
                        vlabels_ho = meta.variable_value_labels.get(field_to_col['horario'], {})
                        if not vlabels_ho:
                            vlabels_ho = meta.variable_value_labels.get('HORARIO_DE_TRABAJO', {})
                        _, ho_lbl = _get_val_and_label(ho_val, vlabels_ho)
                        ho_found = False
                        if ho_lbl:
                            for k_ho, ws_obj in work_map.items():
                                if k_ho in ho_lbl.upper():
                                    visit.work_schedule = ws_obj
                                    ho_found = True
                                    break
                        if not ho_found and ho_val is not None:
                            try:
                                ho_int = int(float(ho_val))
                                if ho_int in work_num_map:
                                    visit.work_schedule = work_num_map[ho_int]
                            except Exception: pass

                    if 'profesion' in field_to_col:
                        pr_val = df_dict[field_to_col['profesion']][i]
                        vlabels_pr = meta.variable_value_labels.get(field_to_col['profesion'], {})
                        if not vlabels_pr:
                            vlabels_pr = meta.variable_value_labels.get('CATEGORIA_PROFESIONAL', {})
                        _, pr_lbl = _get_val_and_label(pr_val, vlabels_pr)
                        pr_found = False
                        if pr_lbl:
                            pr_upper = pr_lbl.upper()
                            for k_pr, pf_obj in prof_map.items():
                                if k_pr in pr_upper:
                                    visit.professional_category = pf_obj
                                    pr_found = True
                                    break
                        if not pr_found and pr_val is not None:
                            try:
                                pr_int = int(float(pr_val))
                                if pr_int in prof_num_map:
                                    visit.professional_category = prof_num_map[pr_int]
                            except Exception: pass

                    if 'vivienda' in field_to_col:
                        vi_val = df_dict[field_to_col['vivienda']][i]
                        vlabels_vi = meta.variable_value_labels.get(field_to_col['vivienda'], {})
                        if not vlabels_vi:
                            vlabels_vi = meta.variable_value_labels.get('SU_VIVIENDA_ES', {})
                        _, vi_lbl = _get_val_and_label(vi_val, vlabels_vi)
                        vi_found = False
                        if vi_lbl:
                            for k_vi, vi_obj in housing_map.items():
                                if k_vi in vi_lbl.upper():
                                    visit.housing_type = vi_obj
                                    vi_found = True
                                    break
                        if not vi_found and vi_val is not None:
                            try:
                                vi_int = int(float(vi_val))
                                if vi_int in housing_num_map:
                                    visit.housing_type = housing_num_map[vi_int]
                            except Exception: pass

                    if 'ingresos' in field_to_col:
                        in_val = df_dict[field_to_col['ingresos']][i]
                        vlabels_in = meta.variable_value_labels.get(field_to_col['ingresos'], {})
                        if not vlabels_in:
                            vlabels_in = meta.variable_value_labels.get('INGRESOS_TOTALES_MENSUALES', {})
                        _, in_lbl = _get_val_and_label(in_val, vlabels_in)
                        in_found = False
                        if in_lbl:
                            for k_in, in_obj in income_map.items():
                                if k_in in in_lbl.upper():
                                    visit.income_range = in_obj
                                    in_found = True
                                    break
                        if not in_found and in_val is not None:
                            try:
                                in_int = int(float(in_val))
                                if in_int in income_num_map:
                                    visit.income_range = income_num_map[in_int]
                            except Exception: pass

                    # Sincronización cruzada entre staff_category y professional_category
                    if not visit.professional_category and visit.staff_category:
                        sc_code = visit.staff_category.name.upper()
                        if 'PDI' in sc_code:
                            visit.professional_category = prof_map.get('PERMANENTE')
                        elif 'PAS' in sc_code:
                            visit.professional_category = prof_map.get('ADMINISTRACION')
                        elif 'SERVICIO' in sc_code:
                            visit.professional_category = prof_map.get('SERVICIO')
                        elif 'ESTUDIANTE' in sc_code:
                            visit.professional_category = prof_map.get('ESTUDIANTE')

                    if not visit.staff_category and visit.professional_category:
                        pc_name = visit.professional_category.name.upper()
                        if 'DOCENTE' in pc_name or 'PROFESOR' in pc_name or 'TITULAR' in pc_name or 'OCASIONAL' in pc_name:
                            visit.staff_category = staff_map.get('PDI')
                        elif 'SERVIDOR' in pc_name or 'ADMINISTRACI' in pc_name:
                            visit.staff_category = staff_map.get('PAS')
                        elif 'AUXILIAR' in pc_name or 'SERVICIO' in pc_name:
                            visit.staff_category = staff_map.get('SERVICIO')
                        elif 'ESTUDIANTE' in pc_name:
                            visit.staff_category = staff_map.get('ESTUDIANTES')

                    visit.status = Visit.Status.COMPLETED
                    visit.save()
                    existing_visits[(inst.institution_id, study_code)] = visit

                    # 5. Antropometría
                    peso_val = None
                    talla_val = None
                    perim_val = None
                    if 'peso' in field_to_col:
                        v_p = df_dict[field_to_col['peso']][i]
                        if v_p:
                            p_c = _clean_decimal(v_p, 5, 2)
                            if p_c is not None: peso_val = p_c
                    if 'talla' in field_to_col:
                        v_t = df_dict[field_to_col['talla']][i]
                        if v_t:
                            t_c = _clean_decimal(v_t, 5, 1)
                            if t_c is not None: talla_val = t_c
                    if 'perimetro' in field_to_col:
                        v_pm = df_dict[field_to_col['perimetro']][i]
                        if v_pm:
                            pm_c = _clean_decimal(v_pm, 5, 1)
                            if pm_c is not None: perim_val = pm_c

                    ant = getattr(visit, 'anthropometry', None)
                    if not ant:
                        ant = Anthropometry(visit=visit, weight_kg=peso_val or Decimal("70.00"), height_cm=talla_val or Decimal("170.0"), waist_circumference_cm=perim_val or Decimal("85.0"))
                    else:
                        if peso_val: ant.weight_kg = peso_val
                        if talla_val: ant.height_cm = talla_val
                        if perim_val: ant.waist_circumference_cm = perim_val
                    ant.save()
                    visit.anthropometry = ant

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

                    vs = getattr(visit, 'vital_signs', None)
                    if not vs:
                        vs = VitalSigns(visit=visit)
                    vs.systolic_bp = tas_val
                    vs.diastolic_bp = tad_val
                    vs.oxygen_saturation = sat_val
                    vs.heart_rate = fc_val

                    if 'soplos' in field_to_col:
                        v_sop = df_dict[field_to_col['soplos']][i]
                        _, sop_lbl = _get_val_and_label(v_sop, meta.variable_value_labels.get(field_to_col['soplos'], {}))
                        sop_str = sop_lbl.lower()
                        vs.systolic_murmur = 'sist' in sop_str
                        vs.diastolic_murmur = 'diast' in sop_str
                        m_grade = re.search(r'grado\s*([1-4])', sop_str)
                        if m_grade: vs.murmur_grade = int(m_grade.group(1))

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
                    visit.vital_signs = vs

                    # 7. ECG
                    ecg = getattr(visit, 'electrocardiogram', None)
                    if not ecg:
                        ecg = Electrocardiogram(visit=visit, rhythm=rhythm_default)
                    ecg.heart_rate = fc_val

                    if 'ecg_ritmo' in field_to_col:
                        v_r = df_dict[field_to_col['ecg_ritmo']][i]
                        _, r_lbl = _get_val_and_label(v_r, meta.variable_value_labels.get(field_to_col['ecg_ritmo'], {}))
                        if r_lbl:
                            r_obj = EcgRhythm.objects.filter(name__icontains=r_lbl[:10]).first()
                            if r_obj: ecg.rhythm = r_obj

                    if 'ecg_pr' in field_to_col:
                        v_pr = df_dict[field_to_col['ecg_pr']][i]
                        if v_pr and not _is_empty_or_nan(v_pr):
                            try:
                                val_num = float(v_pr)
                                ecg.pr_interval_ms = int(val_num * 1000) if val_num < 1.0 else int(val_num)
                            except Exception: pass

                    if 'ecg_qrs' in field_to_col:
                        v_qrs = df_dict[field_to_col['ecg_qrs']][i]
                        if v_qrs and not _is_empty_or_nan(v_qrs):
                            try:
                                val_num = float(v_qrs)
                                ecg.qrs_duration_ms = int(val_num * 1000) if val_num < 1.0 else int(val_num)
                            except Exception: pass

                    if 'ecg_qt' in field_to_col:
                        v_qt = df_dict[field_to_col['ecg_qt']][i]
                        if v_qt and not _is_empty_or_nan(v_qt):
                            try:
                                val_num = float(v_qt)
                                ecg.qt_interval_ms = int(val_num * 1000) if val_num < 1.0 else int(val_num)
                            except Exception: pass

                    if 'ecg_qtc' in field_to_col:
                        v_qtc = df_dict[field_to_col['ecg_qtc']][i]
                        if v_qtc and not _is_empty_or_nan(v_qtc):
                            try: ecg.qtc_bazett_ms = int(float(v_qtc))
                            except Exception: pass

                    if 'ecg_eje' in field_to_col:
                        v_eje = df_dict[field_to_col['ecg_eje']][i]
                        if v_eje and not _is_empty_or_nan(v_eje):
                            try: ecg.qrs_axis_degrees = int(float(v_eje))
                            except Exception: pass

                    if 'ecg_hvi' in field_to_col:
                        v_hvi = df_dict[field_to_col['ecg_hvi']][i]
                        ecg.left_ventricular_hypertrophy = (v_hvi == 1.0)

                    if 'ecg_bloqueo' in field_to_col:
                        v_bl = df_dict[field_to_col['ecg_bloqueo']][i]
                        _, bl_lbl = _get_val_and_label(v_bl, meta.variable_value_labels.get(field_to_col['ecg_bloqueo'], {}))
                        if bl_lbl:
                            ecg.bundle_branch_block = bl_lbl[:50]
                            ecg.has_bundle_branch_block = True

                    if 'ecg_rr' in field_to_col:
                        v_rr = df_dict[field_to_col['ecg_rr']][i]
                        if v_rr is not None and str(v_rr).strip() != '':
                            try:
                                val_rr = float(v_rr)
                                if val_rr > 50:
                                    val_rr = val_rr / 1000.0
                                rr_dec = _clean_decimal(val_rr, 5, 3)
                                if rr_dec is not None:
                                    ecg.rr_interval_sec = rr_dec
                            except Exception: pass

                    if 'ecg_onda_p' in field_to_col:
                        v_op = df_dict[field_to_col['ecg_onda_p']][i]
                        if v_op is not None and str(v_op).strip() != '':
                            try:
                                val_op = float(v_op)
                                # En SPSS suele registrarse en ms (ej. 80-140 ms). 1 mm = 40 ms a 25 mm/s
                                if val_op > 25.0:
                                    val_op = val_op / 40.0
                                p_dec = _clean_decimal(val_op, 4, 2)
                                if p_dec is not None:
                                    ecg.p_wave_mm = p_dec
                            except Exception: pass

                    if 'ecg_bloqueo_av' in field_to_col:
                        v_bav = df_dict[field_to_col['ecg_bloqueo_av']][i]
                        _, bav_lbl = _get_val_and_label(v_bav, meta.variable_value_labels.get(field_to_col['ecg_bloqueo_av'], {}))
                        if v_bav in [1.0, 2.0, 3.0, '1', '2', '3'] or 'SI' in bav_lbl.upper():
                            ecg.av_block = True
                            ecg.av_block_grade = bav_lbl[:50] if bav_lbl else 'Bloqueo AV'

                    if 'ecg_hemibloqueo' in field_to_col:
                        v_hb = df_dict[field_to_col['ecg_hemibloqueo']][i]
                        _, hb_lbl = _get_val_and_label(v_hb, meta.variable_value_labels.get(field_to_col['ecg_hemibloqueo'], {}))
                        if v_hb in [1.0, '1'] or 'SÍ' in hb_lbl.upper() or 'SI' in hb_lbl.upper():
                            ecg.hemiblock = True
                            ecg.hemiblock_detail = hb_lbl[:100] if hb_lbl else 'Hemibloqueo'

                    if 'ecg_onda_delta' in field_to_col:
                        v_od = df_dict[field_to_col['ecg_onda_delta']][i]
                        ecg.delta_wave = (v_od == 1.0 or v_od == '1')

                    if 'ecg_cubeta' in field_to_col:
                        v_cub = df_dict[field_to_col['ecg_cubeta']][i]
                        ecg.digitalis_effect = (v_cub == 1.0 or v_cub == '1')

                    if 'ecg_onda_q' in field_to_col:
                        v_oq = df_dict[field_to_col['ecg_onda_q']][i]
                        ecg.pathological_q_wave = (v_oq == 1.0 or v_oq == '1' or str(v_oq).strip().upper() == 'SI')

                    if 'ecg_t_negativa' in field_to_col:
                        v_tn = df_dict[field_to_col['ecg_t_negativa']][i]
                        ecg.negative_t_wave = (v_tn == 1.0 or v_tn == '1' or str(v_tn).strip().upper() == 'SI')

                    if 'ecg_st_ascenso' in field_to_col:
                        v_sta = df_dict[field_to_col['ecg_st_ascenso']][i]
                        ecg.st_elevation_pathological = (v_sta == 1.0 or v_sta == '1' or str(v_sta).strip().upper() == 'SI')

                    if 'ecg_st_descenso' in field_to_col:
                        v_std = df_dict[field_to_col['ecg_st_descenso']][i]
                        ecg.st_depression = (v_std == 1.0 or v_std == '1' or str(v_std).strip().upper() == 'SI')

                    if 'ecg_normal' in field_to_col:
                        v_norm = df_dict[field_to_col['ecg_normal']][i]
                        ecg.is_normal = (v_norm == 1.0 or v_norm == '1')

                    ecg.save()
                    visit.electrocardiogram = ecg

                    # 8. Laboratorio
                    lab = getattr(visit, 'laboratory', None)
                    if not lab:
                        lab = Laboratory(visit=visit)
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
                    lab_field_specs = {
                        'rbc_millions': (4, 2),
                        'hemoglobin_g_dl': (4, 2),
                        'hematocrit_percentage': (4, 1),
                        'mcv_fl': (5, 2),
                        'wbc_thousands': (6, 2),
                        'platelets_thousands': (6, 1),
                        'prothrombin_time_sec': (4, 1),
                        'glucose_mg_dl': (5, 2),
                        'urea_mg_dl': (5, 2),
                        'creatinine_mg_dl': (4, 2),
                        'total_cholesterol_mg_dl': (5, 2),
                        'hdl_mg_dl': (5, 2),
                        'ldl_mg_dl': (5, 2),
                        'triglycerides_mg_dl': (6, 2),
                        'ast_got_u_l': (6, 2),
                        'alt_gpt_u_l': (6, 2),
                        'ggt_u_l': (6, 2),
                        'tsh_u_iu_ml': (6, 2),
                    }
                    for f_lab, model_attr in lab_mapping_keys:
                        if f_lab in field_to_col:
                            val_l = df_dict[field_to_col[f_lab]][i]
                            if val_l is not None:
                                max_d, dec_p = lab_field_specs.get(model_attr, (5, 2))
                                clean_l = _clean_decimal(val_l, max_d, dec_p)
                                if clean_l is not None:
                                    setattr(lab, model_attr, clean_l)
                    lab.save()
                    visit.laboratory = lab

                    # 9. Ecocardiograma
                    echo = getattr(visit, 'echocardiogram', None)
                    if not echo:
                        echo = Echocardiogram(visit=visit)
                    if 'eco_ddvi' in field_to_col:
                        v_dd = df_dict[field_to_col['eco_ddvi']][i]
                        if v_dd:
                            dd_clean = _clean_decimal(v_dd, 5, 1)
                            if dd_clean is not None:
                                echo.lv_dimension_mm = dd_clean
                    if 'eco_fey' in field_to_col:
                        v_fy = df_dict[field_to_col['eco_fey']][i]
                        if v_fy:
                            fy_clean = _clean_decimal(v_fy, 5, 1)
                            if fy_clean is not None:
                                echo.lvef_percentage = fy_clean
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
                    visit.echocardiogram = echo

                    # 9.5. Estudios Solicitados al Paciente (OrderedStudies)
                    ordered = getattr(visit, 'ordered_studies', None)
                    if not ordered:
                        ordered = OrderedStudies(visit=visit)

                    def _eval_bool_val(field_key):
                        if field_key in field_to_col:
                            val = df_dict[field_to_col[field_key]][i]
                            if val is not None and str(val).strip() != '':
                                return val in [1.0, 1, '1', '1.0', 'Si', 'SI', 'Sí', True]
                        return False

                    ordered.clinical_analysis = _eval_bool_val('est_analisis_clinicos')
                    ordered.ergometry_spect = _eval_bool_val('est_ergometria_spect')
                    ordered.cardiac_ct = _eval_bool_val('est_tac_cardiaco')
                    ordered.cardiac_mri = _eval_bool_val('est_rnm_cardiaco')
                    ordered.electrophysiology = _eval_bool_val('est_electrofisiologia')
                    ordered.save()
                    visit.ordered_studies = ordered

                    # 10. Persistencia de respuestas de variables SPSS en memoria
                    for col_name in col_names:
                        val_raw = df_dict[col_name][i]
                        if _is_empty_or_nan(val_raw):
                            continue

                        vlabels = meta.variable_value_labels.get(col_name, {})
                        _, text_lbl = _get_val_and_label(val_raw, vlabels)
                        val_str = text_lbl if text_lbl else str(val_raw).strip()

                        clean_code = col_code_map.get(col_name)
                        if not clean_code:
                            continue

                        q = existing_questions.get(clean_code)
                        if not q:
                            continue

                        num_val = None
                        if isinstance(val_raw, (int, float)) and not text_lbl:
                            try:
                                import math
                                f_val = float(val_raw)
                                if not (math.isnan(f_val) or math.isinf(f_val)):
                                    d_val = Decimal(str(round(f_val, 3)))
                                    if not d_val.is_nan() and not d_val.is_infinite():
                                        num_val = d_val
                                        ans_text = None
                                    else:
                                        ans_text = val_str[:250]
                                else:
                                    ans_text = None
                            except Exception:
                                num_val = None
                                ans_text = val_str[:250]
                        else:
                            num_val = None
                            ans_text = val_str[:250]

                        if num_val is None and not ans_text:
                            continue

                        row_answers[(visit.pk, q.pk)] = VisitAnswer(
                            visit=visit,
                            question=q,
                            text_value=ans_text,
                            numeric_value=num_val,
                            selected_option=None
                        )

                        # Form aliases
                        for form_k, spss_k in SPSS_QUESTION_ALIASES.items():
                            if spss_k == clean_code:
                                q_form = existing_questions.get(form_k)
                                if q_form:
                                    row_answers[(visit.pk, q_form.pk)] = VisitAnswer(
                                        visit=visit,
                                        question=q_form,
                                        text_value=ans_text,
                                        numeric_value=num_val,
                                        selected_option=None
                                    )

                    # Derivaciones compuestas
                    def _set_ans(code, val):
                        q_d = existing_questions.get(code)
                        if q_d:
                            row_answers[(visit.pk, q_d.pk)] = VisitAnswer(
                                visit=visit,
                                question=q_d,
                                text_value=val,
                                numeric_value=None,
                                selected_option=None
                            )

                    estres_raw = str(df_dict.get('ESTRES', [None]*total_rows)[i] or '').upper()
                    if 'TRABAJO' in estres_raw: _set_ans('em_estres_trab', 'Si')
                    elif estres_raw and 'NO' in estres_raw: _set_ans('em_estres_trab', 'No')
                    if 'FAMILIAR' in estres_raw or 'FAMILIA' in estres_raw: _set_ans('em_estres_fam', 'Si')
                    elif estres_raw and 'NO' in estres_raw: _set_ans('em_estres_fam', 'No')

                    pers_raw = str(df_dict.get('PERSONALIDAD_TIPO_A', [None]*total_rows)[i] or '').upper()
                    if 'TIPO A' in pers_raw or 'SI' in pers_raw: _set_ans('em_pers_a', 'Si')
                    elif pers_raw and 'NO' in pers_raw: _set_ans('em_pers_a', 'No')

                    padre_raw = str(df_dict.get('ANTECEDENTES_PADRES', [None]*total_rows)[i] or '').upper()
                    if padre_raw:
                        _set_ans('ant_padre_hta', 'Si' if 'HTA' in padre_raw else 'No')
                        _set_ans('ant_padre_dm', 'Si' if ('DIAB' in padre_raw or 'DM' in padre_raw) else 'No')
                        _set_ans('ant_padre_iam', 'Si' if ('INFARTO' in padre_raw or 'IAM' in padre_raw) else 'No')
                        _set_ans('ant_padre_ictus', 'Si' if ('ICTUS' in padre_raw or 'ACV' in padre_raw) else 'No')

                    madre_raw = str(df_dict.get('ANTECEDENTES_MADRES', [None]*total_rows)[i] or '').upper()
                    if madre_raw:
                        _set_ans('ant_madre_hta', 'Si' if 'HTA' in madre_raw else 'No')
                        _set_ans('ant_madre_dm', 'Si' if ('DIAB' in madre_raw or 'DM' in madre_raw) else 'No')
                        _set_ans('ant_madre_iam', 'Si' if ('INFARTO' in madre_raw or 'IAM' in madre_raw) else 'No')
                        _set_ans('ant_madre_ictus', 'Si' if ('ICTUS' in madre_raw or 'ACV' in madre_raw) else 'No')

                    covid_raw = str(df_dict.get('HISTORIA_COVID', [None]*total_rows)[i] or '').upper()
                    if covid_raw: _set_ans('covid_paso', 'Si' if ('SI' in covid_raw or covid_raw == '1.0') else 'No')
                    hosp_raw = str(df_dict.get('AFECTACION_COVID', [None]*total_rows)[i] or '').upper()
                    if 'HOSPITAL' in hosp_raw or 'INGRESO' in hosp_raw: _set_ans('covid_ingreso', 'Si')
                    long_raw = str(df_dict.get('LONG_COVID', [None]*total_rows)[i] or '').upper()
                    if long_raw: _set_ans('longcovid', 'Si' if ('SI' in long_raw or long_raw == '1.0') else 'No')

                    oliva_raw = str(df_dict.get('USA_USTED_ACEITE_DE_OLIVA', [None]*total_rows)[i] or '').upper()
                    if oliva_raw:
                        is_ol = 'Si' if ('SI' in oliva_raw or oliva_raw == '1.0') else 'No'
                        _set_ans('pred_q1', is_ol)
                        _set_ans('pred_q2', is_ol)

                    act_raw = str(df_dict.get('USTED_REALIZA_ACTIVIDAD_FISICA', [None]*total_rows)[i] or '').upper()
                    if act_raw: _set_ans('act_realiza', 'Si' if ('SI' in act_raw or act_raw == '1.0') else 'No')
                    aer_raw = str(df_dict.get('USTED_REALIZA_EJERCICIOS_AEROBICOS', [None]*total_rows)[i] or '').upper()
                    if aer_raw: _set_ans('act_aerob', 'Si' if ('SI' in aer_raw or aer_raw == '1.0') else 'No')
                    ana_raw = str(df_dict.get('USTED_REALIZA_EJERCICIOS_ANAEROBICOS', [None]*total_rows)[i] or '').upper()
                    if ana_raw: _set_ans('act_anaerob', 'Si' if ('SI' in ana_raw or ana_raw == '1.0') else 'No')
                    dep_raw = str(df_dict.get('HACE_DEPORTE', [None]*total_rows)[i] or '').upper()
                    if dep_raw: _set_ans('act_deporte', 'Si' if ('SI' in dep_raw or dep_raw == '1.0') else 'No')

                    # Factores de riesgo modificables sincronizados con el formulario
                    hta_raw = df_dict.get('HIPERTENSION', [None]*total_rows)[i]
                    if hta_raw is not None and str(hta_raw).strip() != '':
                        _set_ans('r_hta', 'Si' if hta_raw in [1.0, 2.0, '1', '2', '1.0', '2.0'] else 'No')
                        _set_ans('r_hta_farmacos', 'Si' if hta_raw in [2.0, '2', '2.0'] else 'No')

                    dislip_raw = df_dict.get('DISLIPEMIA', [None]*total_rows)[i]
                    if dislip_raw is not None and str(dislip_raw).strip() != '':
                        _set_ans('r_dislipemia', 'Si' if dislip_raw in [1.0, 2.0, '1', '2', '1.0', '2.0'] else 'No')
                        _set_ans('r_dislip_farmacos', 'Si' if dislip_raw in [2.0, '2', '2.0'] else 'No')

                    vasc_raw = df_dict.get('VASCULOPATÍA', [None]*total_rows)[i]
                    if vasc_raw is not None and str(vasc_raw).strip() != '':
                        _set_ans('r_vasculopatia', 'Si' if vasc_raw in [1.0, 2.0, 3.0, '1', '2', '3'] else 'No')
                        _set_ans('r_vasc_femoral', 'Si' if vasc_raw in [3.0, '3', '3.0'] else 'No')

                    holter_raw = df_dict.get('PRUEBA_HOLTER', [None]*total_rows)[i]
                    if holter_raw is not None and str(holter_raw).strip() != '':
                        is_h_si = holter_raw in [1.0, 3.0, 4.0, '1', '3', '4', 'SI', 'NORMAL', 'ALTERADA']
                        _set_ans('r_holter', 'Si' if is_h_si else 'No')
                        _set_ans('holter_resultado', 'Alterada' if holter_raw in [4.0, '4', 'ALTERADA'] else 'Normal')

                    mapa_raw = df_dict.get('USTED_SE_HA_REALIZADO_ESTUDIOS_DE_MAPA', [None]*total_rows)[i]
                    if mapa_raw is not None and str(mapa_raw).strip() != '':
                        _set_ans('r_mapa', 'Si' if mapa_raw in [1.0, '1', '1.0', 'SI', 'Si', 'Sí'] else 'No')

                    # Confirmar lote de respuestas de la fila actual
                    answers_to_upsert.update(row_answers)

            except Exception as e:
                errors.append(f"Fila {i + 1} (Código {study_code}): {str(e)}")

        # Bulk create de todas las respuestas acumuladas en PostgreSQL
        if answers_to_upsert:
            VisitAnswer.objects.bulk_create(
                list(answers_to_upsert.values()),
                update_conflicts=True,
                unique_fields=['visit', 'question'],
                update_fields=['text_value', 'numeric_value', 'selected_option'],
                batch_size=2000
            )

        # Registrar auditoría única al finalizar la importación
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
                        'skipped_patients': skipped_count,
                        'duplicate_count': len(duplicate_records),
                        'error_count': len(errors)
                    }),
                    status=ChangeLog.Status.RECORDED
                )
            except Exception:
                pass

        # Invalidar caché compartido de la cohorte tras importación masiva exitosa (bulk_create)
        try:
            from chatbot.services import invalidate_cohort_cache
            transaction.on_commit(invalidate_cohort_cache)
        except Exception:
            pass

    # Limpiar archivo temporal
    if temp_path.exists():
        try: temp_path.unlink()
        except Exception: pass

    dup_summary = f"{len(duplicate_records)} duplicados actualizados en BD" if len(duplicate_records) > 0 else "sin duplicados"
    return {
        "success": True,
        "total_rows": total_rows,
        "imported_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "duplicate_count": len(duplicate_records),
        "duplicate_records": duplicate_records[:200],
        "errors": errors[:10],
        "message": f"Se procesaron con éxito {total_rows} registros ({created_count} nuevos creados, {dup_summary}, {skipped_count} omitidos)."
    }

