"""Clinical form transaction, independent of HTTP request/response handling."""
import datetime
from collections import Counter
from decimal import Decimal
from django.db import transaction, connection, models
from django.core.exceptions import ValidationError
from catalog.models import (Country, Province, Canton, Sex, Ethnicity,
 StaffCategory, ProfessionalCategory, EducationLevel, IncomeRange, MaritalStatus,
 LivingSituation, HousingType, WorkSchedule, EcgRhythm, Question, AnswerOption,
 QuestionnaireSection)
from catalog.institutions import InstitutionResolutionError, resolve_selectable_institution
from clinical.models import (Patient, Visit, Anthropometry, VitalSigns, Electrocardiogram,
 Echocardiogram, Laboratory, OrderedStudies, VisitAnswer)
from audit.services import register_audit_log
from .measurements import save_measurements
from .yes_no import nullable_bool, RADIO_FIELDS, CHECKBOX_FIELDS
from .sav_importer import SPSS_QUESTION_ALIASES, classify_spss_question_section
from clinical.validators import validate_ecuadorian_id
QUESTION_ALIASES = SPSS_QUESTION_ALIASES
ALIAS_COUNTS = Counter(QUESTION_ALIASES.values())
REVERSE_QUESTION_ALIASES = {v: k for k,v in QUESTION_ALIASES.items() if ALIAS_COUNTS[v] == 1}
REVERSE_ALIASES = REVERSE_QUESTION_ALIASES

def _resolve_canton(canton_name, province_name):
    """
    Busca o crea de forma segura un cantón asociado a su provincia
    garantizando un dpa_code único para evitar colisiones con uq_canton_province_dpa_code.
    Soporta insensibilidad a mayúsculas y acentos (Pujili == Pujilí).
    """
    if not canton_name or not str(canton_name).strip():
        return None
    import unicodedata
    def _fold(s):
        return ''.join(ch for ch in unicodedata.normalize('NFD', str(s)) if unicodedata.category(ch) != 'Mn').lower()

    c_clean = str(canton_name).strip()
    p_clean = str(province_name or '').strip()
    c_fold = _fold(c_clean)
    p_fold = _fold(p_clean)

    # 1. Buscar provincia por coincidencia exacta o con tildes normalizadas
    prov_obj = None
    if p_clean:
        prov_obj = Province.objects.filter(name__iexact=p_clean).first()
        if not prov_obj:
            prov_obj = Province.objects.filter(name__icontains=p_clean).first()
        if not prov_obj:
            for p in Province.objects.all():
                if _fold(p.name) == p_fold or p_fold in _fold(p.name):
                    prov_obj = p
                    break
    if not prov_obj:
        prov_obj = Province.objects.first()

    # 2. Buscar cantón en la provincia identificada (con tildes normalizadas)
    cant_obj = None
    if prov_obj:
        cant_obj = Canton.objects.filter(province=prov_obj, name__iexact=c_clean).first()
        if not cant_obj:
            cant_obj = Canton.objects.filter(province=prov_obj, name__icontains=c_clean).first()
        if not cant_obj:
            for cand in Canton.objects.filter(province=prov_obj):
                if _fold(cand.name) == c_fold or c_fold in _fold(cand.name):
                    cant_obj = cand
                    break

    # 3. Buscar cantón a nivel nacional si no se encontró en la provincia
    if not cant_obj:
        cant_obj = Canton.objects.filter(name__iexact=c_clean).first()
    if not cant_obj:
        cant_obj = Canton.objects.filter(name__icontains=c_clean).first()
    if not cant_obj:
        for cand in Canton.objects.all():
            if _fold(cand.name) == c_fold:
                cant_obj = cand
                break

    # 4. Si aún no existe, crearlo asignándole un dpa_code único dentro de la provincia
    if not cant_obj and prov_obj:
        existing_dpas = set(Canton.objects.filter(province=prov_obj).values_list('dpa_code', flat=True))
        pref = (prov_obj.iso_code or 'EC-99')[-2:].replace('-', '0')
        new_dpa = None
        for i in range(1, 100):
            cand = f"{pref}{i:02d}"[:4]
            if cand not in existing_dpas:
                new_dpa = cand
                break
        cant_obj = Canton.objects.create(
            name=c_clean,
            province=prov_obj,
            dpa_code=new_dpa or f"{pref}99"[:4]
        )

    return cant_obj


def update_clinical_record(patient, raw_data, user, client_ip):
    for key in RADIO_FIELDS | CHECKBOX_FIELDS:
        if key in raw_data:
            nullable_bool(raw_data[key])
    with transaction.atomic():
        patient = Patient.objects.select_for_update().get(pk=patient.pk)
        if not patient.institution_id:
            raise ValidationError('El paciente no tiene una institución asignada.')
        try:
            resolve_selectable_institution(patient.institution.acronym)
        except InstitutionResolutionError as exc:
            raise ValidationError(str(exc)) from exc
        # 1. Actualizar Paciente (Módulo 1)
        f_nom = raw_data.get('f_nombre')
        f_ap1 = raw_data.get('f_apellido1')
        f_ap2 = raw_data.get('f_apellido2')
        f_ced = raw_data.get('f_cedula')
        f_tel = raw_data.get('f_telefono')
        f_cor = raw_data.get('f_correo')
        f_sex = raw_data.get('f_sexo')
        f_fecha_nac = raw_data.get('f_fecha_nac')
        f_raza = raw_data.get('f_raza')
        f_municipio = raw_data.get('f_municipio')

        if f_nom and not f_nom.strip().startswith('Paciente') and '***' not in f_nom: patient.first_names = f_nom.strip()
        if f_ap1 and f_ap1.strip() != '[Protegido]' and not f_ap1.strip().isdigit() and '***' not in f_ap1: patient.last_name1 = f_ap1.strip()
        if f_ap2 is not None and f_ap2.strip() != '[Protegido]' and '***' not in f_ap2: patient.last_name2 = f_ap2.strip()
        if f_ced and '***' not in str(f_ced):
            ced_clean = str(f_ced).strip()
            if (
                ced_clean
                and ced_clean != patient.id_card
                and validate_ecuadorian_id(ced_clean)
                and not Patient.objects.filter(id_card=ced_clean).exclude(pk=patient.pk).exists()
            ):
                patient.id_card = ced_clean
        if f_tel is not None and '***' not in f_tel: patient.phone = f_tel.strip()
        if f_cor is not None and '***' not in f_cor: patient.email = f_cor.strip()
        if f_fecha_nac:
            try: patient.birth_date = datetime.date.fromisoformat(f_fecha_nac.strip())
            except ValueError:
                raise ValidationError('Fecha clinica invalida.')
        if f_sex:
            s_obj = Sex.objects.filter(name__istartswith=f_sex.strip()[0]).first()
            if s_obj: patient.sex = s_obj
        if f_raza:
            eth_map = {'MESTIZO': 'Mestizo', 'BLANCA': 'Blanco', 'AFRICANA': 'Afroecuatoriano', 'INDÍGENA': 'Indígena', 'INDIGENA': 'Indígena', 'MONTUBIA': 'Montuvio', 'OTRA': 'Otro'}
            raza_key = f_raza.upper().strip()
            eth_name = eth_map.get(raza_key, f_raza.strip())
            eth_obj = Ethnicity.objects.filter(name__icontains=eth_name).first()
            if not eth_obj and raza_key in eth_map:
                eth_obj, _ = Ethnicity.objects.get_or_create(name=eth_name)
            if eth_obj: patient.ethnicity = eth_obj

        f_uni = raw_data.get('f_universidad')
        if f_uni:
            try:
                patient.institution = resolve_selectable_institution(f_uni.strip())
            except InstitutionResolutionError as exc:
                raise ValidationError(str(exc)) from exc

        f_prov_nac = raw_data.get('f_provincia_nac')
        if f_municipio:
            cant_obj = _resolve_canton(f_municipio, f_prov_nac)
            if cant_obj:
                patient.birth_canton = cant_obj

        patient.save()

        # 2. Actualizar / Crear Visita (Módulo 1)
        visit = getattr(patient, 'visit', None)
        if not visit:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(71342001)')
            codigo_suministrado = str(raw_data.get('f_codigo') or '').strip()
            if codigo_suministrado and not Visit.objects.filter(patient__institution=patient.institution, study_code=codigo_suministrado).exists():
                auto_codigo = codigo_suministrado
            else:
                existing_codes = Visit.objects.filter(patient__institution=patient.institution).values_list('study_code', flat=True)
                numeric_codes = [int(c) for c in existing_codes if c and c.isdigit()]
                auto_codigo = str((max(numeric_codes) + 1) if numeric_codes else 1)

            visit = Visit.objects.create(
                patient=patient,
                evaluator=user,
                study_code=auto_codigo,
                visit_date=datetime.date.today(),
                residence_canton=patient.birth_canton or Canton.objects.first(),
                status=Visit.Status.COMPLETED
            )
        else:
            f_codigo = raw_data.get('f_codigo')
            if f_codigo and str(f_codigo).strip():
                nuevo_sc = str(f_codigo).strip()
                if visit.study_code != nuevo_sc and not Visit.objects.filter(patient__institution=patient.institution, study_code=nuevo_sc).exclude(pk=visit.pk).exists():
                    visit.study_code = nuevo_sc

        f_visita = raw_data.get('f_visita')
        if f_visita and str(f_visita).strip().isdigit():
            visit.visit_number = int(str(f_visita).strip())

        f_fecha_vis = raw_data.get('f_fecha_visita')
        if f_fecha_vis:
            try:
                visit.visit_date = datetime.date.fromisoformat(f_fecha_vis.strip())
            except ValueError:
                raise ValidationError('Fecha clinica invalida.')

        if 'f_facultad' in raw_data:
            f_fac = raw_data.get('f_facultad')
            visit.faculty = f_fac.strip() if (f_fac and str(f_fac).strip()) else None

        f_estam = raw_data.get('f_estamento')
        if f_estam:
            sc_obj = StaffCategory.objects.filter(name__icontains=f_estam.strip()).first()
            if sc_obj: visit.staff_category = sc_obj

        f_ciudad = raw_data.get('f_ciudad')
        f_prov_res = raw_data.get('f_provincia')
        if f_ciudad:
            res_cant = _resolve_canton(f_ciudad, f_prov_res)
            if res_cant:
                visit.residence_canton = res_cant

        if 'f_hijos' in raw_data or 'f_num_hijos' in raw_data:
            f_hijos = raw_data.get('f_hijos') if 'f_hijos' in raw_data else raw_data.get('f_num_hijos')
            if f_hijos in ('', None):
                visit.num_children = None
            elif str(f_hijos).strip().isdigit():
                visit.num_children = int(str(f_hijos).strip())

        if 'f_convivientes' in raw_data or 'f_num_convivientes' in raw_data:
            f_conviv = raw_data.get('f_convivientes') if 'f_convivientes' in raw_data else raw_data.get('f_num_convivientes')
            if f_conviv in ('', None):
                visit.num_cohabitants = None
            elif str(f_conviv).strip().isdigit():
                visit.num_cohabitants = int(str(f_conviv).strip())

        if 'f_estado_civil' in raw_data:
            f_estado_civil = raw_data.get('f_estado_civil')
            if f_estado_civil:
                ms_map = {'1_soltero': 'Soltero', '2_casado': 'Casado', '3_divorciado': 'Divorciado', '4_viudo': 'Viudo', '5_union_libre': 'Unión de hecho'}
                ms_name = ms_map.get(f_estado_civil.strip(), f_estado_civil.strip())
                ms_obj = MaritalStatus.objects.filter(name__icontains=ms_name).first()
                if ms_obj: visit.marital_status = ms_obj
            else:
                visit.marital_status = None

        if 'f_convive_con' in raw_data:
            f_convive_con = raw_data.get('f_convive_con')
            if f_convive_con:
                ls_map = {'1': 'Solo', '2': 'Con pareja', '3': 'Con pareja', '4': 'Con familia', '5': 'Con familia', '6': 'Con familia', '7': 'Con amigos'}
                ls_name = ls_map.get(f_convive_con.strip(), f_convive_con.strip())
                ls_obj = LivingSituation.objects.filter(name__icontains=ls_name).first()
                if ls_obj: visit.living_situation = ls_obj
            else:
                visit.living_situation = None

        if 'f_estudios' in raw_data:
            f_estudios = raw_data.get('f_estudios')
            if f_estudios:
                ed_map = {'1': 'Primaria', '2': 'Primaria', '3': 'Primaria', '4': 'Secundaria', '5': 'Secundaria', '6': 'Tercer Nivel', '7': 'Cuarto Nivel'}
                ed_name = ed_map.get(f_estudios.strip(), f_estudios.strip())
                ed_obj = EducationLevel.objects.filter(name__icontains=ed_name).first()
                if ed_obj: visit.education_level = ed_obj
            else:
                visit.education_level = None

        if 'f_horario' in raw_data:
            f_horario = raw_data.get('f_horario')
            if f_horario:
                ws_map = {'1': 'Tiempo Completo', '2': 'Tiempo Completo', '3': 'Parcial', '4': 'Turnos'}
                ws_name = ws_map.get(f_horario.strip(), f_horario.strip())
                ws_obj = WorkSchedule.objects.filter(name__icontains=ws_name).first()
                if ws_obj: visit.work_schedule = ws_obj
            else:
                visit.work_schedule = None

        if 'f_profesion' in raw_data:
            f_profesion = raw_data.get('f_profesion')
            if f_profesion:
                pc_map = {'1': 'Docente Titular', '2': 'Docente Ocasional', '3': 'Servidor Público', '4': 'Auxiliar', '5': 'Otro', '6': 'Estudiante', '7': 'Otro'}
                pc_name = pc_map.get(f_profesion.strip(), f_profesion.strip())
                pc_obj = ProfessionalCategory.objects.filter(name__icontains=pc_name).first()
                if pc_obj: visit.professional_category = pc_obj
            else:
                visit.professional_category = None

        if 'f_vivienda' in raw_data:
            f_vivienda = raw_data.get('f_vivienda')
            if f_vivienda:
                ht_map = {'1': 'Propia', '2': 'Arrendada', '3': 'Familiar', '4': 'Prestada'}
                ht_name = ht_map.get(f_vivienda.strip(), f_vivienda.strip())
                ht_obj = HousingType.objects.filter(name__icontains=ht_name).first()
                if ht_obj: visit.housing_type = ht_obj
            else:
                visit.housing_type = None

        if 'f_ingresos' in raw_data:
            f_ingresos = raw_data.get('f_ingresos')
            if f_ingresos:
                ir_map = {'1': 'Menos de $500', '2': '$500 - $1000', '3': '$1001 - $2000', '4': '$1001 - $2000', '5': 'Más de $2000', '6': 'Más de $2000', '7': 'Más de $2000', '8': 'Más de $2000'}
                ir_name = ir_map.get(f_ingresos.strip(), f_ingresos.strip())
                ir_obj = IncomeRange.objects.filter(name__icontains=ir_name).first()
                if ir_obj: visit.income_range = ir_obj
            else:
                visit.income_range = None

        visit.source_row_data = None
        visit.status = Visit.Status.COMPLETED
        visit.save()

        ant, vs = save_measurements(visit, raw_data)

        if hasattr(visit, 'electrocardiogram') or any(key.startswith('ecg_') and value not in ('', None) for key, value in raw_data.items()):
            # 5. Electrocardiograma (Módulo 5 - HU-13 y Cuestionario UNEMI 2026 Completo)
            ecg_ritmo_nom = raw_data.get('ecg_ritmo') or (visit.electrocardiogram.rhythm.name if hasattr(visit, 'electrocardiogram') else '')
            if not ecg_ritmo_nom:
                raise ValidationError('Registre el ritmo antes de crear el ECG.')
            rhythm_obj = EcgRhythm.objects.filter(name__icontains=ecg_ritmo_nom[:10]).first() or EcgRhythm.objects.first()
            ecg, _ = Electrocardiogram.objects.get_or_create(visit=visit, defaults={"rhythm": rhythm_obj})
            ecg.rhythm = rhythm_obj
            for html_key, model_key in (
                ('ecg_fc', 'heart_rate'),
                ('ecg_pr', 'pr_interval_ms'),
                ('ecg_qrs', 'qrs_duration_ms'),
                ('ecg_qt', 'qt_interval_ms'),
                ('ecg_qtc', 'qtc_bazett_ms'),
                ('ecg_eje', 'qrs_axis_degrees'),
            ):
                if html_key in raw_data:
                    raw_v = raw_data.get(html_key)
                    if raw_v in ('', None):
                        setattr(ecg, model_key, None)
                    else:
                        clean_v = str(raw_v).strip().rstrip('°').strip()
                        if clean_v.lstrip('-').isdigit():
                            setattr(ecg, model_key, int(clean_v))

            # Campos exhaustivos del ECG
            if 'ecg_rr' in raw_data:
                if raw_data.get('ecg_rr') in ('', None):
                    ecg.rr_interval_sec = None
                else:
                    try:
                        val_rr = float(raw_data['ecg_rr'])
                        if val_rr > 10.0:  # Ingresado en milisegundos (ej. 800 ms -> 0.800 s)
                            val_rr = val_rr / 1000.0
                        ecg.rr_interval_sec = Decimal(str(round(val_rr, 3)))
                    except (ValueError, TypeError, ArithmeticError):
                        raise ValidationError('Valor numerico clinico invalido.')
            if 'ecg_p_mm' in raw_data:
                if raw_data.get('ecg_p_mm') in ('', None):
                    ecg.p_wave_mm = None
                else:
                    try: ecg.p_wave_mm = Decimal(str(raw_data['ecg_p_mm']))
                    except (ValueError, TypeError, ArithmeticError):
                        raise ValidationError('Valor numerico clinico invalido.')
            if any(key in raw_data for key in ('ecg_p_mitral',)):
                ecg.p_mitrale = nullable_bool(raw_data.get('ecg_p_mitral'))
            if any(key in raw_data for key in ('ecg_bloqueo_av',)):
                ecg.av_block = nullable_bool(raw_data.get('ecg_bloqueo_av'))
            if any(key in raw_data for key in ('ecg_bloqueo_av_grado',)):
                ecg.av_block_grade = raw_data.get('ecg_bloqueo_av_grado') or ''
            if any(key in raw_data for key in ('ecg_bloqueo_sa',)):
                ecg.sa_block = nullable_bool(raw_data.get('ecg_bloqueo_sa'))
            if any(key in raw_data for key in ('ecg_bloqueo_ia',)):
                ecg.interatrial_block = nullable_bool(raw_data.get('ecg_bloqueo_ia'))
            if any(key in raw_data for key in ('ecg_hemibloqueo',)):
                ecg.hemiblock = nullable_bool(raw_data.get('ecg_hemibloqueo'))
            if any(key in raw_data for key in ('ecg_hemibloqueo_cual',)):
                ecg.hemiblock_detail = raw_data.get('ecg_hemibloqueo_cual') or ''
            if any(key in raw_data for key in ('ecg_bloqueo_rama_sn',)):
                ecg.has_bundle_branch_block = nullable_bool(raw_data.get('ecg_bloqueo_rama_sn'))
            if any(key in raw_data for key in ('ecg_bloqueo_rama',)):
                ecg.bundle_branch_block = raw_data.get('ecg_bloqueo_rama', '')
            if any(key in raw_data for key in ('ecg_brugada',)):
                ecg.brugada_pattern = nullable_bool(raw_data.get('ecg_brugada'))
            if any(key in raw_data for key in ('ecg_repolarizacion_precoz',)):
                ecg.early_repolarization = nullable_bool(raw_data.get('ecg_repolarizacion_precoz'))
            if any(key in raw_data for key in ('ecg_hvi',)):
                ecg.left_ventricular_hypertrophy = nullable_bool(raw_data.get('ecg_hvi'))
            if any(key in raw_data for key in ('ecg_sobrecarga_sistolica',)):
                ecg.systolic_overload = nullable_bool(raw_data.get('ecg_sobrecarga_sistolica'))
            if any(key in raw_data for key in ('ecg_sobrecarga_complejos',)):
                ecg.systolic_overload_complexes = raw_data.get('ecg_sobrecarga_complejos') or ''
            if raw_data.get('ecg_deflexion_intrinsicoide'):
                try:
                    val_def = float(raw_data['ecg_deflexion_intrinsicoide'])
                    if val_def > 5.0:  # Ingresado en milisegundos (ej. 45 ms -> 0.045 s)
                        val_def = val_def / 1000.0
                    ecg.intrinsicoid_deflection_sec = Decimal(str(round(val_def, 3)))
                except (ValueError, TypeError, ArithmeticError):
                    raise ValidationError('Valor numerico clinico invalido.')
            if any(key in raw_data for key in ('ecg_hvd',)):
                ecg.right_ventricular_hypertrophy = nullable_bool(raw_data.get('ecg_hvd'))
            if any(key in raw_data for key in ('ecg_onda_delta',)):
                ecg.delta_wave = nullable_bool(raw_data.get('ecg_onda_delta'))
            if any(key in raw_data for key in ('ecg_cubeta_digitalica',)):
                ecg.digitalis_effect = nullable_bool(raw_data.get('ecg_cubeta_digitalica'))
            if any(key in raw_data for key in ('ecg_onda_q',)):
                ecg.pathological_q_wave = nullable_bool(raw_data.get('ecg_onda_q'))
            if any(key in raw_data for key in ('ecg_onda_q_amplitud',)):
                ecg.q_wave_amplitude = raw_data.get('ecg_onda_q_amplitud') or ''
            if raw_data.get('ecg_onda_q_voltaje'):
                try: ecg.q_wave_voltage_mv = Decimal(str(raw_data['ecg_onda_q_voltaje']))
                except (ValueError, TypeError, ArithmeticError):
                    raise ValidationError('Valor numerico clinico invalido.')
            if any(key in raw_data for key in ('ecg_onda_q_complejos',)):
                ecg.q_wave_complexes = raw_data.get('ecg_onda_q_complejos') or ''
            if any(key in raw_data for key in ('ecg_t_negativa',)):
                ecg.negative_t_wave = nullable_bool(raw_data.get('ecg_t_negativa'))
            if any(key in raw_data for key in ('ecg_t_negativa_complejos',)):
                ecg.negative_t_complexes = raw_data.get('ecg_t_negativa_complejos') or ''
            if any(key in raw_data for key in ('ecg_t_simetrica',)):
                ecg.negative_t_symmetric = nullable_bool(raw_data.get('ecg_t_simetrica'))
            if any(key in raw_data for key in ('ecg_t_asimetrica',)):
                ecg.negative_t_asymmetric = nullable_bool(raw_data.get('ecg_t_asimetrica'))
            if any(key in raw_data for key in ('ecg_st_ascenso',)):
                ecg.st_elevation_pathological = nullable_bool(raw_data.get('ecg_st_ascenso'))
            if raw_data.get('ecg_st_ascenso_mm'):
                try: ecg.st_elevation_mm = Decimal(str(raw_data['ecg_st_ascenso_mm']))
                except (ValueError, TypeError, ArithmeticError):
                    raise ValidationError('Valor numerico clinico invalido.')
            if any(key in raw_data for key in ('ecg_st_ascenso_complejos',)):
                ecg.st_elevation_complexes = raw_data.get('ecg_st_ascenso_complejos') or ''
            if any(key in raw_data for key in ('ecg_st_descenso',)):
                ecg.st_depression = nullable_bool(raw_data.get('ecg_st_descenso'))
            if raw_data.get('ecg_st_descenso_mm'):
                try: ecg.st_depression_mm = Decimal(str(raw_data['ecg_st_descenso_mm']))
                except (ValueError, TypeError, ArithmeticError):
                    raise ValidationError('Valor numerico clinico invalido.')
            if any(key in raw_data for key in ('ecg_st_descenso_complejos',)):
                ecg.st_depression_complexes = raw_data.get('ecg_st_descenso_complejos') or ''
            if any(key in raw_data for key in ('ecg_normal',)):
                ecg.is_normal = nullable_bool(raw_data.get('ecg_normal'))
            if any(key in raw_data for key in ('ecg_alt_repolarizacion',)):
                ecg.repolarization_abnormalities = nullable_bool(raw_data.get('ecg_alt_repolarizacion'))
            if any(key in raw_data for key in ('ecg_comentario',)):
                ecg.ecg_comments = raw_data.get('ecg_comentario', '')
            ecg.save()


        if any(key.startswith(('eco_', 'res_', 'ip_', 'valvulopatia_')) for key in raw_data):
            # 6. Ecocardiograma (Módulo 5 - HU-13)
            echo, _ = Echocardiogram.objects.get_or_create(visit=visit)
            eco_val = raw_data.get('eco_ddvi') or raw_data.get('ip_medida_chorro')
            if eco_val:
                try: echo.lv_dimension_mm = Decimal(str(eco_val))
                except (ValueError, TypeError, ArithmeticError):
                    raise ValidationError('Valor numerico clinico invalido.')
            if raw_data.get('eco_fey'):
                try: echo.lvef_percentage = Decimal(str(raw_data['eco_fey']))
                except (ValueError, TypeError, ArithmeticError):
                    raise ValidationError('Valor numerico clinico invalido.')
            if any(key in raw_data for key in ('res_vi_hipertrofico',)):
                echo.ventricular_hypertrophy = nullable_bool(raw_data.get('res_vi_hipertrofico'))
            if any(key in raw_data for key in ('eco_disfuncion_diastolica', 'res_fdvi')):
                echo.diastolic_dysfunction = nullable_bool(raw_data['eco_disfuncion_diastolica']) if 'eco_disfuncion_diastolica' in raw_data else (None if raw_data.get('res_fdvi') in ('', None) else raw_data['res_fdvi'] in ('Si', 'Alterada'))
            if any(key in raw_data for key in ('eco_calcificacion_aortica',)):
                echo.aortic_valve_calcification = nullable_bool(raw_data.get('eco_calcificacion_aortica'))
            if raw_data.get('valvulopatia_tipo_detalle'):
                if any(key in raw_data for key in ('valvulopatia_tipo_detalle',)):
                    echo.valvular_regurgitation_detail = raw_data.get('valvulopatia_tipo_detalle')[:200]
            echo.save()

        if any(key.startswith(('hemo_', 'diab_', 'lab_', 'renal_', 'riesgo_', 'hepatica_', 'tiroidea_')) for key in raw_data):


            # 7. Laboratorio (Módulo 5 - HU-13)
            lab, _ = Laboratory.objects.get_or_create(visit=visit)
            lab_fields = [
                ('hemo_hematies', 'rbc_millions'),
                ('hemo_hemoglobina', 'hemoglobin_g_dl'),
                ('hemo_hematocrito', 'hematocrit_percentage'),
                ('hemo_vcm', 'mcv_fl'),
                ('hemo_leucocitos', 'wbc_thousands'),
                ('hemo_plaquetas', 'platelets_thousands'),
                ('hemo_inr', 'prothrombin_time_sec'),
                ('diab_glucosa', 'glucose_mg_dl'),
                ('renal_urea', 'urea_mg_dl'),
                ('renal_creatinina', 'creatinine_mg_dl'),
                ('riesgo_colesterol', 'total_cholesterol_mg_dl'),
                ('riesgo_hdl', 'hdl_mg_dl'),
                ('riesgo_ldl', 'ldl_mg_dl'),
                ('riesgo_trigliceridos', 'triglycerides_mg_dl'),
                ('hepatica_got', 'ast_got_u_l'),
                ('hepatica_gpt', 'alt_gpt_u_l'),
                ('hepatica_ggt', 'ggt_u_l'),
                ('tiroidea_tsh', 'tsh_u_iu_ml'),
            ]
            for html_key, model_key in lab_fields:
                if html_key in raw_data:
                    val = raw_data.get(html_key)
                    if val in ('', None):
                        setattr(lab, model_key, None)
                    else:
                        try:
                            setattr(lab, model_key, Decimal(str(val)))
                        except (ValueError, TypeError, ArithmeticError):
                            raise ValidationError('Valor de laboratorio invalido.')
            lab.save()

        if any(key.startswith(('est_',)) for key in raw_data):


            # 7.5. Estudios Solicitados / Mandados al Paciente (Pág. 19 Cuestionario UNEMI 2026)
            ordered, _ = OrderedStudies.objects.get_or_create(visit=visit)
            if any(key in raw_data for key in ('est_analisis_clinicos',)):
                ordered.clinical_analysis = nullable_bool(raw_data.get('est_analisis_clinicos'))
            if any(key in raw_data for key in ('est_ergometria_spect',)):
                ordered.ergometry_spect = nullable_bool(raw_data.get('est_ergometria_spect'))
            if any(key in raw_data for key in ('est_tac_cardiaco',)):
                ordered.cardiac_ct = nullable_bool(raw_data.get('est_tac_cardiaco'))
            if any(key in raw_data for key in ('est_rnm_cardiaco',)):
                ordered.cardiac_mri = nullable_bool(raw_data.get('est_rnm_cardiaco'))
            if any(key in raw_data for key in ('est_electrofisiologia',)):
                ordered.electrophysiology = nullable_bool(raw_data.get('est_electrofisiologia'))
            ordered.save()


        # 8. Persistencia Universal y Bidireccional de Todos los Campos del Formulario (VisitAnswer)
        ignore_keys = {'csrfmiddlewaretoken', 'idPaciente', 'paciente_id'}
        sections_by_code = {s.code: s for s in QuestionnaireSection.objects.all()}
        default_section = sections_by_code.get('MOD_3_FACTORES_MOD') or QuestionnaireSection.objects.first()

        for k, v in raw_data.items():
            if k in ignore_keys or not k.strip():
                continue
            val_str = '' if v is None else str(v).strip()
            k_clean = k.strip()
            if k_clean in ('f_nombre', 'f_apellido1', 'f_apellido2', 'f_cedula', 'f_telefono', 'f_correo') and ('***' in val_str or val_str == '[Protegido]'):
                continue

            target_sec_code = classify_spss_question_section(k_clean)
            target_sec = sections_by_code.get(target_sec_code, default_section)

            q = Question.objects.filter(code=k_clean[:30]).first()
            if not q:
                q = Question.objects.create(
                    section=target_sec,
                    code=k_clean[:30],
                    text=f"Campo {k_clean}"[:250],
                    response_type=Question.ResponseType.TEXTO,
                    display_order=999
                )
            elif q and q.section == default_section and q.section != target_sec:
                q.section = target_sec
                q.save(update_fields=['section'])

            if q:
                if val_str != '':
                    VisitAnswer.objects.update_or_create(
                        visit=visit,
                        question=q,
                        defaults={
                            "text_value": val_str[:250],
                            "numeric_value": None,
                            "selected_option": None
                        }
                    )
                else:
                    VisitAnswer.objects.update_or_create(visit=visit, question=q, defaults={'text_value': None, 'numeric_value': None, 'selected_option': None})

            # Sincronización bidireccional de alias (Formulario HTML <-> SPSS)
            raw_alias = QUESTION_ALIASES.get(k_clean) or REVERSE_QUESTION_ALIASES.get(k_clean)
            if raw_alias and ALIAS_COUNTS.get(raw_alias, 0) > 1:
                raw_alias = None
            alias_code = raw_alias[:30] if raw_alias else None
            if alias_code and alias_code != k_clean[:30]:
                alias_sec_code = classify_spss_question_section(alias_code)
                alias_sec = sections_by_code.get(alias_sec_code, default_section)
                q_alias = Question.objects.filter(code=alias_code).first()
                if not q_alias:
                    q_alias = Question.objects.create(
                        section=alias_sec,
                        code=alias_code,
                        text=f"Campo {alias_code}"[:250],
                        response_type=Question.ResponseType.TEXTO,
                        display_order=999
                    )
                elif q_alias and q_alias.section == default_section and q_alias.section != alias_sec:
                    q_alias.section = alias_sec
                    q_alias.save(update_fields=['section'])

                if q_alias:
                    if val_str != '':
                        VisitAnswer.objects.update_or_create(
                            visit=visit,
                            question=q_alias,
                            defaults={
                                "text_value": val_str[:250],
                                "numeric_value": None,
                                "selected_option": None
                            }
                        )
                    else:
                        VisitAnswer.objects.update_or_create(visit=visit, question=q_alias, defaults={'text_value': None, 'numeric_value': None, 'selected_option': None})

            if k_clean == 'f_correo':
                q_email = Question.objects.filter(code='email').first()
                if q_email:
                    VisitAnswer.objects.update_or_create(
                        visit=visit,
                        question=q_email,
                        defaults={'text_value': val_str[:250] if val_str != '' else None, 'numeric_value': None, 'selected_option': None},
                    )

        # 9. Auditoría Automática (HU-14)
        register_audit_log(
            user=user,
            table_name='visit',
            record_key=visit.visit_id,
            action='UPDATE',
            new_value={
                'study_code': visit.study_code,
                'patient': patient.full_name,
                'peso': float(ant.weight_kg) if (ant and ant.weight_kg) else None,
                'tas': vs.systolic_bp if (vs and vs.systolic_bp) else None
            },
            machine_name=client_ip
        )

    return visit
