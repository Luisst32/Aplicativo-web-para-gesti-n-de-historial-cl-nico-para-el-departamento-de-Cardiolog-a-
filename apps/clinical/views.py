import json
import datetime
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction, connection
from django.core.paginator import Paginator

from catalog.models import (
    Country, Province, Canton, Institution,
    Sex, Ethnicity, StaffCategory, ProfessionalCategory,
    EducationLevel, IncomeRange, MaritalStatus,
    LivingSituation, HousingType, WorkSchedule,
    EcgRhythm, Question, AnswerOption, QuestionnaireSection
)
from clinical.models import (
    Patient, Visit, Anthropometry, VitalSigns,
    Electrocardiogram, Echocardiogram, Laboratory, VisitAnswer
)
from clinical.validators import validate_ecuadorian_id, validate_clinical_ranges
from clinical.pdf import generate_clinical_sheet_pdf
from audit.services import register_audit_log


QUESTION_ALIASES = {
    'r_hta': 'hta',
    'r_hta_trat': 'hta_tto',
    'r_dm': 'dm',
    'r_dislip': 'dlp',
    'r_dislip_trat': 'dlp_tto',
    'r_tabaco': 'tabaco',
    'r_alcohol': 'alcohol',
    'r_drogas': 'drogas',
    'r_sobrepeso': 'sobrepeso',
    'r_irc': 'irc',
    'r_higado': 'higado_graso',
    'r_apnea': 'apnea',
    'em_toxicos': 'toxicos_laboral',
    'em_estres_trab': 'estres_laboral',
    'em_estres_fam': 'estres_familiar',
    'em_pers_a': 'personalidad_tipo_a',
    'nm_cardiopatia': 'af_cardiopatia_prematura',
    'nm_fallecido': 'af_muerte_subita',
    'ant_padre_hta': 'af_padre_hta',
    'ant_madre_hta': 'af_madre_hta',
    'ant_padre_dm': 'af_padre_dm',
    'ant_madre_dm': 'af_madre_dm',
    'ant_padre_dislip': 'af_padre_dlp',
    'ant_madre_dislip': 'af_madre_dlp',
    'nc_cancer': 'ant_cancer',
    'nc_epoc': 'ant_epoc',
    'nc_asma': 'ant_asma',
    'nc_reuma': 'ant_reuma',
    'nc_depresion': 'ant_depresion',
    'nc_ansiedad': 'ant_ansiedad',
    'nc_alergia': 'ant_alergias',
    'covid_paso': 'covid_infeccion',
    'covid_ingreso': 'covid_hosp',
    'covid_cv': 'covid_secuelas_cardio',
    'covid_pulm': 'covid_secuelas_resp',
    'rose_1': 'rose_dolor_pecho',
    'rose_3': 'rose_detenerse',
    'rose_4': 'rose_alivio',
    'rose_5': 'rose_claudicacion',
    'f_num_hijos': 'f_hijos',
    'f_num_convivientes': 'f_convivientes',
}
REVERSE_ALIASES = {v: k for k, v in QUESTION_ALIASES.items()}


def _patient_to_dict(patient, visit=None):
    """
    Serializes a Patient and their active Visit into the structure expected
    by the frontend (compatible with list.js and form.js).
    """
    if visit is None:
        visit = getattr(patient, 'visit', None)

    ant = getattr(visit, 'anthropometry', None) if visit else None
    vs = getattr(visit, 'vital_signs', None) if visit else None

    # Formatted visit / historial
    historiales = []
    if visit:
        historiales.append({
            "id": str(visit.visit_id),
            "numeroVisita": visit.visit_number,
            "codigoEstudio": visit.study_code,
            "fechaVisita": visit.visit_date.isoformat(),
            "tipo": "Historial Clínico",
            "motivo": "Control Anual Cardiovascular & Dieta Mediterránea",
            "medico": visit.evaluator.full_name if visit.evaluator else "Médico Especialista",
            "estado": "Completada" if visit.status == Visit.Status.COMPLETED else "En proceso",
            "peso": float(ant.weight_kg) if (ant and ant.weight_kg) else 70,
            "talla": float(ant.height_cm) if (ant and ant.height_cm) else 170,
            "imc": float(ant.bmi) if (ant and ant.bmi) else 24.2,
            "asc": float(ant.body_surface_area) if (ant and ant.body_surface_area) else 1.82,
            "tas": vs.systolic_bp if (vs and vs.systolic_bp) else 120,
            "tsi": vs.diastolic_bp if (vs and vs.diastolic_bp) else 80,
            "satO2": vs.oxygen_saturation if (vs and vs.oxygen_saturation) else 98,
            "perimetro": float(ant.waist_circumference_cm) if (ant and ant.waist_circumference_cm) else 85,
            "riesgoGlobal": "Bajo"
        })

    ms_val = ""
    if visit and visit.marital_status:
        ms_val_map = {'Soltero/a': '1_soltero', 'Casado/a': '2_casado', 'Divorciado/a': '3_divorciado', 'Viudo/a': '4_viudo', 'Unión de hecho': '5_union_libre'}
        ms_val = ms_val_map.get(visit.marital_status.name, "")

    ls_val = ""
    if visit and visit.living_situation:
        ls_val_map = {'Solo': '1', 'Con pareja': '2', 'Con familia': '4', 'Con amigos/compañeros': '7'}
        ls_val = ls_val_map.get(visit.living_situation.name, "")

    ed_val = ""
    if visit and visit.education_level:
        ed_val_map = {'Primaria': '3', 'Secundaria': '4', 'Tercer Nivel (Grado)': '6', 'Cuarto Nivel (Postgrado)': '7', 'Doctorado (PhD)': '7'}
        ed_val = ed_val_map.get(visit.education_level.name, "")

    ws_val = ""
    if visit and visit.work_schedule:
        ws_val_map = {'Tiempo Completo (40h)': '1', 'Medio Tiempo (20h)': '2', 'Parcial': '3', 'Turnos / Rotativo': '4'}
        ws_val = ws_val_map.get(visit.work_schedule.name, "")

    pc_val = ""
    if visit and visit.professional_category:
        pc_val_map = {'Docente Titular': '1', 'Docente Ocasional': '2', 'Servidor Público': '3', 'Auxiliar de Servicios': '4', 'Estudiante': '6', 'Otro': '5'}
        pc_val = pc_val_map.get(visit.professional_category.name, "")

    ht_val = ""
    if visit and visit.housing_type:
        ht_val_map = {'Propia': '1', 'Arrendada': '2', 'Familiar': '3', 'Prestada': '4'}
        ht_val = ht_val_map.get(visit.housing_type.name, "")

    ir_val = ""
    if visit and visit.income_range:
        ir_val_map = {'Menos de $500': '1', '$500 - $1000': '2', '$1001 - $2000': '3', 'Más de $2000': '5'}
        ir_val = ir_val_map.get(visit.income_range.name, "")

    return {
        "id": str(patient.patient_id),
        "codigo": visit.study_code if (visit and visit.study_code) else str(patient.patient_id),
        "cedula": patient.id_card,
        "nombre": patient.full_name,
        "fechaNac": patient.birth_date.isoformat() if patient.birth_date else "",
        "sexo": "H" if (patient.sex and patient.sex.name.lower().startswith('h')) else "M",
        "estamento": visit.staff_category.name if (visit and visit.staff_category) else "PDI",
        "universidad": patient.institution.acronym if (patient.institution and patient.institution.acronym) else "UNEMI",
        "facultad": visit.faculty if visit and visit.faculty else "FACI",
        "ciudad": visit.residence_canton.name if (visit and visit.residence_canton) else (patient.birth_canton.name if patient.birth_canton else "Milagro"),
        "provincia": visit.residence_canton.province.name.upper() if (visit and visit.residence_canton and visit.residence_canton.province) else "GUAYAS",
        "telefono": patient.phone or "",
        "correo": patient.email or "",
        "municipio": patient.birth_canton.name if patient.birth_canton else "Milagro",
        "provincia_nac": patient.birth_canton.province.name.upper() if (patient.birth_canton and patient.birth_canton.province) else "GUAYAS",
        "numeroVisita": visit.visit_number if (visit and visit.visit_number) else 1,
        "raza": patient.ethnicity.name.upper() if patient.ethnicity else "MESTIZO",
        "estado_civil": ms_val,
        "hijos": str(visit.num_children if (visit and visit.num_children is not None) else 0),
        "convivientes": str(visit.num_cohabitants if (visit and visit.num_cohabitants is not None) else 4),
        "convive_con": ls_val,
        "estudios": ed_val,
        "horario": ws_val,
        "profesion": pc_val,
        "vivienda": ht_val,
        "ingresos": ir_val,
        "peso": float(ant.weight_kg) if (ant and ant.weight_kg) else 70,
        "talla": float(ant.height_cm) if (ant and ant.height_cm) else 170,
        "tas": vs.systolic_bp if (vs and vs.systolic_bp) else 120,
        "tsi": vs.diastolic_bp if (vs and vs.diastolic_bp) else 80,
        "satO2": vs.oxygen_saturation if (vs and vs.oxygen_saturation) else 98,
        "perimetro": float(ant.waist_circumference_cm) if (ant and ant.waist_circumference_cm) else 85,
        "historiales": historiales
    }


# =============================================================================
# TEMPLATE RENDERING VIEWS
# =============================================================================

@login_required
def form_view(request):
    """
    Renders the clinical evaluation form template.
    Data is populated asynchronously via form_get_api or initial context.
    """
    return render(request, 'clinical/form.html')


@login_required
def list_view(request):
    """
    Renders the patients directory and medical evaluations list.
    """
    total_pacientes = Patient.objects.filter(status=Patient.Status.ACTIVE).count()
    return render(request, 'clinical/list.html', {
        'total_pacientes': total_pacientes
    })


# =============================================================================
# JSON APIS: DIRECTORY, FILTERING, PAGINATION AND QUICK-CREATE (HU-15, HU-16)
# =============================================================================

@login_required
@require_GET
def patient_list_api(request):
    """
    JSON endpoint for listing, searching, filtering and sorting patients (HU-15, HU-16).
    Supports:
      - q: query string on id_card, first_names, last_name1, study_code, faculty
      - anio: filter by study year (e.g., 2026, 2025)
      - estamento: filter by staff category (e.g., PDI, AD, SERVICIO)
      - sexo: filter by sex (H / M)
      - ordenar_por: field to order by ('nombre', 'fecha', 'historiales')
      - direccion: 'asc' or 'desc'
    """
    qs = Patient.objects.filter(status=Patient.Status.ACTIVE).select_related(
        'sex', 'ethnicity', 'birth_canton', 'institution',
        'visit', 'visit__staff_category', 'visit__residence_canton', 'visit__evaluator',
        'visit__anthropometry', 'visit__vital_signs'
    )

    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(id_card__icontains=q) |
            Q(first_names__icontains=q) |
            Q(last_name1__icontains=q) |
            Q(last_name2__icontains=q) |
            Q(visit__study_code__icontains=q) |
            Q(visit__faculty__icontains=q)
        )

    anio = request.GET.get('anio', 'all').strip()
    if anio and anio != 'all':
        try:
            anio_int = int(anio)
            qs = qs.filter(visit__study_year=anio_int)
        except ValueError:
            pass

    estamento = request.GET.get('estamento', 'all').strip()
    if estamento and estamento != 'all':
        qs = qs.filter(visit__staff_category__name__iexact=estamento)

    sexo = request.GET.get('sexo', 'all').strip().upper()
    if sexo and sexo != 'all':
        if sexo == 'H':
            qs = qs.filter(sex__name__istartswith='H')
        elif sexo == 'M':
            qs = qs.filter(sex__name__istartswith='M')

    # Sorting
    ordenar_por = request.GET.get('ordenar_por', 'codigo').strip().lower()
    direccion = request.GET.get('direccion', 'asc').strip().lower()
    prefix = '' if direccion == 'asc' else '-'

    if ordenar_por == 'nombre':
        qs = qs.order_by(f"{prefix}first_names", f"{prefix}last_name1")
    elif ordenar_por == 'fecha':
        qs = qs.order_by(f"{prefix}visit__visit_date")
    elif ordenar_por == 'codigo':
        qs = qs.order_by(f"{prefix}patient_id")
    else:
        qs = qs.order_by(f"{prefix}patient_id")

    pacientes_list = [_patient_to_dict(p) for p in qs]

    return JsonResponse({
        "success": True,
        "total": len(pacientes_list),
        "pacientes": pacientes_list
    })


@login_required
@require_GET
def patient_detail_api(request, patient_id):
    """
    Returns full details for a single patient and their clinical visit.
    """
    # patient_id can be 'p1', numeric, or study code
    clean_id = patient_id.replace('p', '') if patient_id.startswith('p') else patient_id

    patient = None
    if clean_id.isdigit():
        patient = Patient.objects.filter(patient_id=int(clean_id)).first()
    if not patient:
        patient = Patient.objects.filter(visit__study_code=patient_id).first()
    if not patient:
        patient = Patient.objects.filter(id_card=patient_id).first()

    if not patient:
        return JsonResponse({"success": False, "error": "Paciente no encontrado"}, status=404)

    return JsonResponse({
        "success": True,
        "paciente": _patient_to_dict(patient)
    })


@login_required
@require_POST
def patient_create_api(request):
    """
    Quick patient registration from modal (HU-15).
    Enforces Ecuadorian ID verification and duplicate prevention.
    Creates Patient, Visit, Anthropometry, and VitalSigns atomically.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST.dict()

        nombre_completo = data.get('nombre', '').strip()
        cedula = data.get('cedula', '').strip()
        fecha_nac = data.get('fecha_nac', '').strip()
        sexo_str = data.get('sexo', 'H').strip().upper()
        estamento_str = data.get('estamento', 'PDI').strip()
        facultad = data.get('facultad', 'UNEMI').strip()
        telefono = data.get('telefono', '').strip()
        correo = data.get('correo', '').strip()

        if not nombre_completo or not fecha_nac:
            return JsonResponse({"success": False, "error": "Nombre y fecha de nacimiento son requeridos."}, status=400)

        # Validar Cédula Ecuatoriana si fue suministrada
        if cedula and not validate_ecuadorian_id(cedula):
            return JsonResponse({
                "success": False,
                "error": f"La cédula '{cedula}' no es válida según el algoritmo oficial ecuatoriano."
            }, status=400)

        # Chequear duplicado por cédula
        if cedula:
            existente = Patient.objects.filter(id_card=cedula).first()
            if existente:
                return JsonResponse({
                    "success": False,
                    "duplicado": True,
                    "error": f"El paciente con cédula {cedula} ya se encuentra registrado.",
                    "existente": _patient_to_dict(existente)
                }, status=409)

        # Partir nombre en nombres y apellidos
        partes = nombre_completo.split()
        if len(partes) == 1:
            first_names = partes[0]
            last_name1 = "N/A"
            last_name2 = ""
        elif len(partes) == 2:
            first_names = partes[0]
            last_name1 = partes[1]
            last_name2 = ""
        elif len(partes) == 3:
            first_names = partes[0]
            last_name1 = partes[1]
            last_name2 = partes[2]
        else:
            first_names = " ".join(partes[:-2])
            last_name1 = partes[-2]
            last_name2 = partes[-1]

        with transaction.atomic():
            # Catálogos base
            unemi = Institution.objects.first()
            sexo = Sex.objects.filter(name__istartswith=sexo_str[0]).first() or Sex.objects.first()
            mestizo = Ethnicity.objects.filter(name="Mestizo").first() or Ethnicity.objects.first()
            milagro = Canton.objects.filter(name="Milagro").first() or Canton.objects.first()
            pdi = StaffCategory.objects.filter(name__icontains=estamento_str).first() or StaffCategory.objects.first()
            docente = ProfessionalCategory.objects.first()

            # Autogenerar cédula temporal si no vino ninguna
            if not cedula:
                cedula = f"09{Patient.objects.count() + 10000000:08d}"

            paciente = Patient.objects.create(
                institution=unemi,
                id_card=cedula,
                first_names=first_names,
                last_name1=last_name1,
                last_name2=last_name2,
                birth_date=datetime.date.fromisoformat(fecha_nac),
                sex=sexo,
                ethnicity=mestizo,
                birth_canton=milagro,
                email=correo,
                phone=telefono,
                status=Patient.Status.ACTIVE,
                created_by=request.user
            )

            # Generar siguiente código de estudio en orden ascendente (1, 2, 3, 4, 5...)
            existing_codes = Visit.objects.values_list('study_code', flat=True)
            numeric_codes = [int(c) for c in existing_codes if c and c.isdigit()]
            siguiente_numero = (max(numeric_codes) + 1) if numeric_codes else 1
            nuevo_codigo = str(siguiente_numero)

            visita = Visit.objects.create(
                patient=paciente,
                evaluator=request.user,
                visit_number=1,
                study_code=nuevo_codigo,
                visit_date=datetime.date.today(),
                staff_category=pdi,
                professional_category=docente,
                residence_canton=milagro,
                faculty=facultad,
                status=Visit.Status.PENDING
            )

            Anthropometry.objects.create(
                visit=visita,
                weight_kg=Decimal("70.00"),
                height_cm=Decimal("170.0"),
                waist_circumference_cm=Decimal("85.0")
            )

            VitalSigns.objects.create(
                visit=visita,
                systolic_bp=120,
                diastolic_bp=80,
                oxygen_saturation=98,
                heart_rate=72,
                pulmonary_auscultation_normal=True,
                abdominal_auscultation_normal=True
            )

            # Registrar auditoría
            register_audit_log(
                user=request.user,
                table_name='patient',
                record_key=paciente.patient_id,
                action='INSERT',
                new_value={'id_card': paciente.id_card, 'nombre': paciente.full_name},
                machine_name=getattr(request, 'client_ip', '127.0.0.1')
            )

        return JsonResponse({
            "success": True,
            "paciente": _patient_to_dict(paciente, visita)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# =============================================================================
# JSON APIS: FORM POPULATION AND COMPLETE SAVING (HU-11, HU-12, HU-13)
# =============================================================================

def _build_form_datos(patient, visit):
    """
    Constructs a dictionary of all field values matching HTML input/select/radio/checkbox
    names across all 6 clinical modules.
    """
    ant = getattr(visit, 'anthropometry', None) if visit else None
    vs = getattr(visit, 'vital_signs', None) if visit else None
    ecg = getattr(visit, 'electrocardiogram', None) if visit else None
    echo = getattr(visit, 'echocardiogram', None) if visit else None
    lab = getattr(visit, 'laboratory', None) if visit else None

    datos = {
        # Modulo 1: Ficha
        "f_nombre": patient.first_names,
        "f_apellido1": patient.last_name1,
        "f_apellido2": patient.last_name2 or "",
        "f_cedula": patient.id_card,
        "f_fecha_nac": patient.birth_date.isoformat() if patient.birth_date else "",
        "f_sexo": "H" if (patient.sex and patient.sex.name.lower().startswith('h')) else "M",
        "f_raza": patient.ethnicity.name.upper() if patient.ethnicity else "MESTIZO",
        "f_telefono": patient.phone or "",
        "f_correo": patient.email or "",
        "f_codigo": visit.study_code if visit else "",
        "f_fecha_visita": visit.visit_date.isoformat() if (visit and visit.visit_date) else "",
        "f_universidad": patient.institution.acronym if (patient.institution and patient.institution.acronym) else "UNEMI",
        "f_facultad": visit.faculty if visit and visit.faculty else "FACI",
        "f_visita": str(visit.visit_number) if (visit and visit.visit_number) else "1",
        "f_estamento": visit.staff_category.name if (visit and visit.staff_category) else "PDI",
        "f_hijos": str(visit.num_children) if (visit and visit.num_children is not None) else "",
        "f_convivientes": str(visit.num_cohabitants) if (visit and visit.num_cohabitants is not None) else "",
        "f_ciudad": visit.residence_canton.name if (visit and visit.residence_canton) else "Milagro",
        "f_provincia": visit.residence_canton.province.name.upper() if (visit and visit.residence_canton and visit.residence_canton.province) else "GUAYAS",
        "f_municipio": patient.birth_canton.name if patient.birth_canton else "Milagro",
        "f_provincia_nac": patient.birth_canton.province.name.upper() if (patient.birth_canton and patient.birth_canton.province) else "GUAYAS",

        # Modulo 2: Exploración física
        "f_peso": str(ant.weight_kg) if (ant and ant.weight_kg) else "",
        "f_talla": str(ant.height_cm) if (ant and ant.height_cm) else "",
        "f_perimetro": str(ant.waist_circumference_cm) if (ant and ant.waist_circumference_cm) else "",
        "f_imc": str(ant.bmi) if (ant and ant.bmi) else "",
        "f_asc": str(ant.body_surface_area) if (ant and ant.body_surface_area) else "",
        "f_tas": str(vs.systolic_bp) if (vs and vs.systolic_bp) else "",
        "f_tsi": str(vs.diastolic_bp) if (vs and vs.diastolic_bp) else "",
        "f_sat_o2": str(vs.oxygen_saturation) if (vs and vs.oxygen_saturation) else "",
        "f_fc": str(vs.heart_rate) if (vs and vs.heart_rate) else "",
        "f_soplo_sistolico": "Si" if (vs and vs.systolic_murmur) else "No",
        "f_soplo_diastolico": "Si" if (vs and vs.diastolic_murmur) else "No",
        "f_grado_soplo": str(vs.murmur_grade) if (vs and vs.murmur_grade) else "",
        "f_pulsos_pedios": "Si" if (vs and vs.pedal_pulses_symmetric) else "No",
        "f_auscultacion_pulmonar": "Normal" if (vs and vs.pulmonary_auscultation_normal) else "Alterada",
        "f_auscultacion_abdominal": "Normal" if (vs and vs.abdominal_auscultation_normal) else "Alterada",

        # Modulo 5: ECG
        "ecg_ritmo": ecg.rhythm.name if (ecg and ecg.rhythm) else "Ritmo Sinusal (RS)",
        "ecg_fc": str(ecg.heart_rate) if (ecg and ecg.heart_rate) else "",
        "ecg_pr": str(ecg.pr_interval_ms) if (ecg and ecg.pr_interval_ms) else "",
        "ecg_qrs": str(ecg.qrs_duration_ms) if (ecg and ecg.qrs_duration_ms) else "",
        "ecg_qt": str(ecg.qt_interval_ms) if (ecg and ecg.qt_interval_ms) else "",
        "ecg_qtc": str(ecg.qtc_bazett_ms) if (ecg and ecg.qtc_bazett_ms) else "",
        "ecg_eje": str(ecg.qrs_axis_degrees) if (ecg and ecg.qrs_axis_degrees) else "",
        "ecg_hvi": "Si" if (ecg and ecg.left_ventricular_hypertrophy) else "No",
        "ecg_comentario": ecg.ecg_comments if (ecg and ecg.ecg_comments) else "",

        # Modulo 5: Laboratorio
        "hemo_hematies": str(lab.rbc_millions) if (lab and lab.rbc_millions) else "",
        "hemo_hemoglobina": str(lab.hemoglobin_g_dl) if (lab and lab.hemoglobin_g_dl) else "",
        "hemo_hematocrito": str(lab.hematocrit_percentage) if (lab and lab.hematocrit_percentage) else "",
        "hemo_vcm": str(lab.mcv_fl) if (lab and lab.mcv_fl) else "",
        "hemo_leucocitos": str(lab.wbc_thousands) if (lab and lab.wbc_thousands) else "",
        "hemo_plaquetas": str(lab.platelets_thousands) if (lab and lab.platelets_thousands) else "",
        "hemo_inr": str(lab.prothrombin_time_sec) if (lab and lab.prothrombin_time_sec) else "",
        "diab_glucosa": str(lab.glucose_mg_dl) if (lab and lab.glucose_mg_dl) else "",
        "renal_urea": str(lab.urea_mg_dl) if (lab and lab.urea_mg_dl) else "",
        "renal_creatinina": str(lab.creatinine_mg_dl) if (lab and lab.creatinine_mg_dl) else "",
        "riesgo_colesterol": str(lab.total_cholesterol_mg_dl) if (lab and lab.total_cholesterol_mg_dl) else "",
        "riesgo_hdl": str(lab.hdl_mg_dl) if (lab and lab.hdl_mg_dl) else "",
        "riesgo_ldl": str(lab.ldl_mg_dl) if (lab and lab.ldl_mg_dl) else "",
        "riesgo_trigliceridos": str(lab.triglycerides_mg_dl) if (lab and lab.triglycerides_mg_dl) else "",
        "hepatica_got": str(lab.ast_got_u_l) if (lab and lab.ast_got_u_l) else "",
        "hepatica_gpt": str(lab.alt_gpt_u_l) if (lab and lab.alt_gpt_u_l) else "",
        "hepatica_ggt": str(lab.ggt_u_l) if (lab and lab.ggt_u_l) else "",
        "tiroidea_tsh": str(lab.tsh_u_iu_ml) if (lab and lab.tsh_u_iu_ml) else "",
    }

    if visit:
        if visit.marital_status:
            ms_val_map = {'Soltero/a': '1_soltero', 'Casado/a': '2_casado', 'Divorciado/a': '3_divorciado', 'Viudo/a': '4_viudo', 'Unión de hecho': '5_union_libre'}
            datos['f_estado_civil'] = ms_val_map.get(visit.marital_status.name, '')
        if visit.living_situation:
            ls_val_map = {'Solo': '1', 'Con pareja': '2', 'Con familia': '4', 'Con amigos/compañeros': '7'}
            datos['f_convive_con'] = ls_val_map.get(visit.living_situation.name, '')
        if visit.education_level:
            ed_val_map = {'Primaria': '3', 'Secundaria': '4', 'Tercer Nivel (Grado)': '6', 'Cuarto Nivel (Postgrado)': '7', 'Doctorado (PhD)': '7'}
            datos['f_estudios'] = ed_val_map.get(visit.education_level.name, '')
        if visit.work_schedule:
            ws_val_map = {'Tiempo Completo (40h)': '1', 'Medio Tiempo (20h)': '2', 'Parcial': '3', 'Turnos / Rotativo': '4'}
            datos['f_horario'] = ws_val_map.get(visit.work_schedule.name, '')
        if visit.professional_category:
            pc_val_map = {'Docente Titular': '1', 'Docente Ocasional': '2', 'Servidor Público': '3', 'Auxiliar de Servicios': '4', 'Estudiante': '6', 'Otro': '5'}
            datos['f_profesion'] = pc_val_map.get(visit.professional_category.name, '')
        if visit.housing_type:
            ht_val_map = {'Propia': '1', 'Arrendada': '2', 'Familiar': '3', 'Prestada': '4'}
            datos['f_vivienda'] = ht_val_map.get(visit.housing_type.name, '')
        if visit.income_range:
            ir_val_map = {'Menos de $500': '1', '$500 - $1000': '2', '$1001 - $2000': '3', 'Más de $2000': '5'}
            datos['f_ingresos'] = ir_val_map.get(visit.income_range.name, '')

        # Cargar todas las respuestas guardadas en VisitAnswer
        for ans in visit.answers.select_related('question').all():
            q_code = ans.question.code
            val = ans.text_value or (str(ans.numeric_value) if ans.numeric_value is not None else (ans.selected_option.label if ans.selected_option else ""))
            if val is not None and str(val).strip() != '':
                datos[q_code] = val
                # Sincronizar alias si no está presente
                alias_code = QUESTION_ALIASES.get(q_code)
                if alias_code and alias_code not in datos:
                    datos[alias_code] = val
                rev_code = REVERSE_ALIASES.get(q_code)
                if rev_code and rev_code not in datos:
                    datos[rev_code] = val

    return datos


@login_required
@require_GET
def form_get_api(request, patient_id):
    """
    Fetches the full database record for a patient to populate form.html fields.
    """
    clean_id = patient_id.replace('p', '') if patient_id.startswith('p') else patient_id

    patient = None
    if clean_id.isdigit():
        patient = Patient.objects.filter(patient_id=int(clean_id)).first()
    if not patient:
        patient = Patient.objects.filter(visit__study_code=patient_id).first()
    if not patient:
        patient = Patient.objects.filter(id_card=patient_id).first()

    if not patient:
        return JsonResponse({"success": False, "error": "Paciente no encontrado"}, status=404)

    visit = getattr(patient, 'visit', None)
    datos = _build_form_datos(patient, visit)

    return JsonResponse({
        "success": True,
        "paciente": _patient_to_dict(patient, visit),
        "datos": datos
    })


@login_required
@require_POST
def form_save_api(request):
    """
    CRUD Ficha Clínica integral (HU-11, HU-12, HU-13, HU-14, HU-18).
    Transactional saving of all 6 clinical modules directly into PostgreSQL.
    Audit log registered in audit.change_log.
    """
    try:
        # Extraer campos de FormData o JSON
        if request.content_type == 'application/json':
            raw_data = json.loads(request.body.decode('utf-8'))
        else:
            raw_data = request.POST.dict()

        # Extraer campos clave
        cedula = raw_data.get('f_cedula', '').strip()
        codigo = raw_data.get('f_codigo', '').strip()
        patient_id_param = request.GET.get('paciente') or raw_data.get('idPaciente') or raw_data.get('paciente_id')

        # Buscar paciente
        patient = None
        if patient_id_param:
            clean_id = str(patient_id_param).replace('p', '')
            if clean_id.isdigit():
                patient = Patient.objects.filter(patient_id=int(clean_id)).first()
        if not patient and cedula:
            patient = Patient.objects.filter(id_card=cedula).first()
        if not patient and codigo:
            patient = Patient.objects.filter(visit__study_code=codigo).first()

        if not patient:
            return JsonResponse({"success": False, "error": "No se encontró el paciente para guardar la ficha."}, status=404)

        # Validaciones de rangos clínicos (HU-18)
        peso_raw = raw_data.get('f_peso')
        talla_raw = raw_data.get('f_talla')
        perimetro_raw = raw_data.get('f_perimetro')
        tas_raw = raw_data.get('f_tas')
        tsi_raw = raw_data.get('f_tsi') or raw_data.get('f_tad')
        sat_raw = raw_data.get('f_sat_o2')
        fc_raw = raw_data.get('f_fc')

        errores_clinicos = validate_clinical_ranges({
            'weight_kg': peso_raw if peso_raw else None,
            'height_cm': talla_raw if talla_raw else None,
            'waist_circumference_cm': perimetro_raw if perimetro_raw else None,
            'systolic_bp': tas_raw if tas_raw else None,
            'diastolic_bp': tsi_raw if tsi_raw else None,
            'oxygen_saturation': sat_raw if sat_raw else None,
            'heart_rate': fc_raw if fc_raw else None,
        })
        if errores_clinicos:
            return JsonResponse({"success": False, "error": " | ".join(errores_clinicos)}, status=400)

        # Transacción Atómica Completa (HU-11, HU-12, HU-13)
        with transaction.atomic():
            # 1. Actualizar Paciente (Módulo 1)
            f_nom = raw_data.get('f_nombre')
            f_ap1 = raw_data.get('f_apellido1')
            f_ap2 = raw_data.get('f_apellido2')
            f_tel = raw_data.get('f_telefono')
            f_cor = raw_data.get('f_correo')
            f_sex = raw_data.get('f_sexo')
            f_fecha_nac = raw_data.get('f_fecha_nac')
            f_raza = raw_data.get('f_raza')
            f_municipio = raw_data.get('f_municipio')

            if f_nom: patient.first_names = f_nom.strip()
            if f_ap1: patient.last_name1 = f_ap1.strip()
            if f_ap2 is not None: patient.last_name2 = f_ap2.strip()
            if f_tel is not None: patient.phone = f_tel.strip()
            if f_cor is not None: patient.email = f_cor.strip()
            if f_fecha_nac:
                try: patient.birth_date = datetime.date.fromisoformat(f_fecha_nac.strip())
                except ValueError: pass
            if f_sex:
                s_obj = Sex.objects.filter(name__istartswith=f_sex.strip()[0]).first()
                if s_obj: patient.sex = s_obj
            if f_raza:
                eth_map = {'MESTIZO': 'Mestizo', 'BLANCA': 'Blanco', 'AFRICANA': 'Afroecuatoriano', 'INDÍGENA': 'Indígena', 'MONTUBIA': 'Montuvio', 'OTRA': 'Otro'}
                eth_name = eth_map.get(f_raza.upper().strip(), f_raza.strip())
                eth_obj = Ethnicity.objects.filter(name__icontains=eth_name).first()
                if eth_obj: patient.ethnicity = eth_obj

            f_uni = raw_data.get('f_universidad')
            if f_uni:
                inst_obj = Institution.objects.filter(acronym__iexact=f_uni.strip()).first()
                if not inst_obj:
                    inst_obj = Institution.objects.filter(name__icontains=f_uni.strip()).first()
                if inst_obj:
                    patient.institution = inst_obj

            f_prov_nac = raw_data.get('f_provincia_nac')
            if f_municipio:
                cant_obj = Canton.objects.filter(name__iexact=f_municipio.strip()).first()
                if not cant_obj:
                    cant_obj = Canton.objects.filter(name__icontains=f_municipio.strip()).first()
                if not cant_obj:
                    prov_obj = None
                    if f_prov_nac:
                        prov_obj = Province.objects.filter(name__icontains=f_prov_nac.strip()).first()
                    if not prov_obj:
                        prov_obj = Province.objects.first()
                    cant_obj = Canton.objects.create(name=f_municipio.strip(), province=prov_obj)
                patient.birth_canton = cant_obj

            patient.save()

            # 2. Actualizar / Crear Visita (Módulo 1)
            visit = getattr(patient, 'visit', None)
            if not visit:
                existing_codes = Visit.objects.values_list('study_code', flat=True)
                numeric_codes = [int(c) for c in existing_codes if c and c.isdigit()]
                auto_codigo = str((max(numeric_codes) + 1) if numeric_codes else 1)

                visit = Visit.objects.create(
                    patient=patient,
                    evaluator=request.user,
                    study_code=auto_codigo,
                    visit_date=datetime.date.today(),
                    residence_canton=patient.birth_canton or Canton.objects.first(),
                    status=Visit.Status.COMPLETED
                )

            f_visita = raw_data.get('f_visita')
            if f_visita and str(f_visita).strip().isdigit():
                visit.visit_number = int(str(f_visita).strip())

            f_fecha_vis = raw_data.get('f_fecha_visita')
            if f_fecha_vis:
                try:
                    visit.visit_date = datetime.date.fromisoformat(f_fecha_vis.strip())
                except ValueError:
                    pass

            f_fac = raw_data.get('f_facultad')
            if f_fac: visit.faculty = f_fac.strip()

            f_estam = raw_data.get('f_estamento')
            if f_estam:
                sc_obj = StaffCategory.objects.filter(name__icontains=f_estam.strip()).first()
                if sc_obj: visit.staff_category = sc_obj

            f_ciudad = raw_data.get('f_ciudad')
            f_prov_res = raw_data.get('f_provincia')
            if f_ciudad:
                res_cant = Canton.objects.filter(name__iexact=f_ciudad.strip()).first()
                if not res_cant:
                    res_cant = Canton.objects.filter(name__icontains=f_ciudad.strip()).first()
                if not res_cant:
                    prov_res = None
                    if f_prov_res:
                        prov_res = Province.objects.filter(name__icontains=f_prov_res.strip()).first()
                    if not prov_res:
                        prov_res = Province.objects.first()
                    res_cant = Canton.objects.create(name=f_ciudad.strip(), province=prov_res)
                visit.residence_canton = res_cant

            f_hijos = raw_data.get('f_hijos') or raw_data.get('f_num_hijos')
            if f_hijos and str(f_hijos).isdigit():
                visit.num_children = int(f_hijos)

            f_conviv = raw_data.get('f_convivientes') or raw_data.get('f_num_convivientes')
            if f_conviv and str(f_conviv).isdigit():
                visit.num_cohabitants = int(f_conviv)

            f_estado_civil = raw_data.get('f_estado_civil')
            if f_estado_civil:
                ms_map = {'1_soltero': 'Soltero', '2_casado': 'Casado', '3_divorciado': 'Divorciado', '4_viudo': 'Viudo', '5_union_libre': 'Unión de hecho'}
                ms_name = ms_map.get(f_estado_civil.strip(), f_estado_civil.strip())
                ms_obj = MaritalStatus.objects.filter(name__icontains=ms_name).first()
                if ms_obj: visit.marital_status = ms_obj

            f_convive_con = raw_data.get('f_convive_con')
            if f_convive_con:
                ls_map = {'1': 'Solo', '2': 'Con pareja', '3': 'Con pareja', '4': 'Con familia', '5': 'Con familia', '6': 'Con familia', '7': 'Con amigos'}
                ls_name = ls_map.get(f_convive_con.strip(), f_convive_con.strip())
                ls_obj = LivingSituation.objects.filter(name__icontains=ls_name).first()
                if ls_obj: visit.living_situation = ls_obj

            f_estudios = raw_data.get('f_estudios')
            if f_estudios:
                ed_map = {'1': 'Primaria', '2': 'Primaria', '3': 'Primaria', '4': 'Secundaria', '5': 'Secundaria', '6': 'Tercer Nivel', '7': 'Cuarto Nivel'}
                ed_name = ed_map.get(f_estudios.strip(), f_estudios.strip())
                ed_obj = EducationLevel.objects.filter(name__icontains=ed_name).first()
                if ed_obj: visit.education_level = ed_obj

            f_horario = raw_data.get('f_horario')
            if f_horario:
                ws_map = {'1': 'Tiempo Completo', '2': 'Tiempo Completo', '3': 'Parcial', '4': 'Turnos'}
                ws_name = ws_map.get(f_horario.strip(), f_horario.strip())
                ws_obj = WorkSchedule.objects.filter(name__icontains=ws_name).first()
                if ws_obj: visit.work_schedule = ws_obj

            f_profesion = raw_data.get('f_profesion')
            if f_profesion:
                pc_map = {'1': 'Docente Titular', '2': 'Docente Ocasional', '3': 'Servidor Público', '4': 'Auxiliar', '5': 'Otro', '6': 'Estudiante', '7': 'Otro'}
                pc_name = pc_map.get(f_profesion.strip(), f_profesion.strip())
                pc_obj = ProfessionalCategory.objects.filter(name__icontains=pc_name).first()
                if pc_obj: visit.professional_category = pc_obj

            f_vivienda = raw_data.get('f_vivienda')
            if f_vivienda:
                ht_map = {'1': 'Propia', '2': 'Arrendada', '3': 'Familiar', '4': 'Prestada'}
                ht_name = ht_map.get(f_vivienda.strip(), f_vivienda.strip())
                ht_obj = HousingType.objects.filter(name__icontains=ht_name).first()
                if ht_obj: visit.housing_type = ht_obj

            f_ingresos = raw_data.get('f_ingresos')
            if f_ingresos:
                ir_map = {'1': 'Menos de $500', '2': '$500 - $1000', '3': '$1001 - $2000', '4': '$1001 - $2000', '5': 'Más de $2000', '6': 'Más de $2000', '7': 'Más de $2000', '8': 'Más de $2000'}
                ir_name = ir_map.get(f_ingresos.strip(), f_ingresos.strip())
                ir_obj = IncomeRange.objects.filter(name__icontains=ir_name).first()
                if ir_obj: visit.income_range = ir_obj

            visit.status = Visit.Status.COMPLETED
            visit.save()

            # 3. Antropometría (Módulo 2 - HU-11)
            peso_dec = Decimal(str(peso_raw)) if peso_raw else Decimal("70.00")
            talla_dec = Decimal(str(talla_raw)) if talla_raw else Decimal("170.0")
            perim_dec = Decimal(str(perimetro_raw)) if perimetro_raw else Decimal("85.0")

            ant, _ = Anthropometry.objects.get_or_create(visit=visit, defaults={
                "weight_kg": peso_dec,
                "height_cm": talla_dec,
                "waist_circumference_cm": perim_dec,
            })
            ant.weight_kg = peso_dec
            ant.height_cm = talla_dec
            ant.waist_circumference_cm = perim_dec
            ant.save()

            # 4. Signos Vitales (Módulo 2 - HU-11)
            tas_int = int(tas_raw) if tas_raw else 120
            tsi_int = int(tsi_raw) if tsi_raw else 80
            sat_int = int(sat_raw) if sat_raw else 98
            fc_int = int(fc_raw) if fc_raw else 72

            vs, _ = VitalSigns.objects.get_or_create(visit=visit, defaults={
                "systolic_bp": tas_int,
                "diastolic_bp": tsi_int,
                "oxygen_saturation": sat_int,
                "heart_rate": fc_int,
            })
            vs.systolic_bp = tas_int
            vs.diastolic_bp = tsi_int
            vs.oxygen_saturation = sat_int
            vs.heart_rate = fc_int
            vs.systolic_murmur = (raw_data.get('f_soplo_sistolico') == 'Si' or raw_data.get('soplos') in ['1', 'Si', 'sistolico'])
            vs.diastolic_murmur = (raw_data.get('f_soplo_diastolico') == 'Si' or raw_data.get('soplos') in ['2', 'diastolico'])
            grado_raw = raw_data.get('f_grado_soplo') or raw_data.get('soplo_grado')
            if grado_raw and str(grado_raw).strip().isdigit():
                vs.murmur_grade = int(grado_raw.strip())
            vs.pulmonary_auscultation_normal = (raw_data.get('f_auscultacion_pulmonar') != 'Alterada' and raw_data.get('resp_norm') != 'No')
            vs.abdominal_auscultation_normal = (raw_data.get('f_auscultacion_abdominal') != 'Alterada' and raw_data.get('abdom_norm') != 'No')
            vs.pedal_pulses_symmetric = (raw_data.get('f_pulsos_pedios') != 'No' and raw_data.get('pulsos_sim') != 'No')
            vs.save()

            # 5. Electrocardiograma (Módulo 5 - HU-13)
            ecg_ritmo_nom = raw_data.get('ecg_ritmo', 'Ritmo Sinusal (RS)')
            rhythm_obj = EcgRhythm.objects.filter(name__icontains=ecg_ritmo_nom[:10]).first() or EcgRhythm.objects.first()
            ecg, _ = Electrocardiogram.objects.get_or_create(visit=visit, defaults={"rhythm": rhythm_obj})
            ecg.rhythm = rhythm_obj
            if raw_data.get('ecg_fc') and raw_data.get('ecg_fc').isdigit():
                ecg.heart_rate = int(raw_data.get('ecg_fc'))
            if raw_data.get('ecg_pr') and raw_data.get('ecg_pr').isdigit():
                ecg.pr_interval_ms = int(raw_data.get('ecg_pr'))
            if raw_data.get('ecg_qrs') and raw_data.get('ecg_qrs').isdigit():
                ecg.qrs_duration_ms = int(raw_data.get('ecg_qrs'))
            if raw_data.get('ecg_qt') and raw_data.get('ecg_qt').isdigit():
                ecg.qt_interval_ms = int(raw_data.get('ecg_qt'))
            if raw_data.get('ecg_qtc') and raw_data.get('ecg_qtc').isdigit():
                ecg.qtc_bazett_ms = int(raw_data.get('ecg_qtc'))
            if raw_data.get('ecg_eje') and raw_data.get('ecg_eje').replace('-', '').isdigit():
                ecg.qrs_axis_degrees = int(raw_data.get('ecg_eje'))
            ecg.left_ventricular_hypertrophy = (raw_data.get('ecg_hvi') == 'Si')
            ecg.bundle_branch_block = raw_data.get('ecg_bloqueo_rama', '')
            ecg.repolarization_abnormalities = (raw_data.get('ecg_alt_repolarizacion') == 'Si')
            ecg.ecg_comments = raw_data.get('ecg_comentario', '')
            ecg.save()

            # 6. Ecocardiograma (Módulo 5 - HU-13)
            echo, _ = Echocardiogram.objects.get_or_create(visit=visit)
            eco_val = raw_data.get('eco_ddvi') or raw_data.get('ip_medida_chorro')
            if eco_val:
                try: echo.lv_dimension_mm = Decimal(str(eco_val))
                except Exception: pass
            if raw_data.get('eco_fey'):
                try: echo.lvef_percentage = Decimal(str(raw_data['eco_fey']))
                except Exception: pass
            echo.ventricular_hypertrophy = (raw_data.get('res_vi_hipertrofico') == 'Si')
            echo.diastolic_dysfunction = (raw_data.get('eco_disfuncion_diastolica') == 'Si' or raw_data.get('res_fdvi') == 'Si')
            echo.aortic_valve_calcification = (raw_data.get('eco_calcificacion_aortica') == 'Si')
            if raw_data.get('valvulopatia_tipo_detalle'):
                echo.valvular_regurgitation_detail = raw_data.get('valvulopatia_tipo_detalle')[:200]
            echo.save()

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
                val = raw_data.get(html_key)
                if val:
                    try:
                        setattr(lab, model_key, Decimal(str(val)))
                    except Exception:
                        pass
            lab.save()

            # 8. Persistencia Universal de Todos los Campos del Formulario (VisitAnswer)
            ignore_keys = {'csrfmiddlewaretoken', 'idPaciente', 'paciente_id', 'f_codigo'}
            default_section = QuestionnaireSection.objects.first()

            for k, v in raw_data.items():
                if k in ignore_keys or not k.strip():
                    continue
                val_str = str(v).strip()
                k_clean = k.strip()

                q = Question.objects.filter(code=k_clean).first()
                if not q and len(k_clean) <= 30:
                    q = Question.objects.create(
                        section=default_section,
                        code=k_clean,
                        text=f"Campo {k_clean}",
                        response_type=Question.ResponseType.TEXTO,
                        display_order=999
                    )

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
                        VisitAnswer.objects.filter(visit=visit, question=q).delete()

                # Sincronizar alias si existe
                alias_code = QUESTION_ALIASES.get(k_clean)
                if alias_code:
                    q_alias = Question.objects.filter(code=alias_code).first()
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
                            VisitAnswer.objects.filter(visit=visit, question=q_alias).delete()

            # 9. Auditoría Automática (HU-14)
            register_audit_log(
                user=request.user,
                table_name='visit',
                record_key=visit.visit_id,
                action='UPDATE',
                new_value={
                    'study_code': visit.study_code,
                    'patient': patient.full_name,
                    'peso': float(ant.weight_kg) if (ant and ant.weight_kg) else None,
                    'tas': vs.systolic_bp if (vs and vs.systolic_bp) else None
                },
                machine_name=getattr(request, 'client_ip', '127.0.0.1')
            )

        # Generar snapshot completo de todos los datos actualizados
        datos = _build_form_datos(patient, visit)

        return JsonResponse({
            "success": True,
            "message": f"Historial Clínico de {patient.full_name} guardado exitosamente en la base de datos.",
            "paciente": _patient_to_dict(patient, visit),
            "datos": datos
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# =============================================================================
# PDF EXPORT VIEW (HU-17)
# =============================================================================

@login_required
def export_pdf_view(request, visit_id=None):
    """
    Generates and downloads the official institutional clinical record PDF (HU-17).
    """
    patient_id_param = request.GET.get('paciente')
    visit = None

    if visit_id:
        clean_vid = str(visit_id).replace('h_', '').replace('h', '')
        if clean_vid.isdigit():
            visit = Visit.objects.filter(visit_id=int(clean_vid)).first()

    if not visit and patient_id_param:
        clean_pid = str(patient_id_param).replace('p', '')
        if clean_pid.isdigit():
            visit = Visit.objects.filter(patient__patient_id=int(clean_pid)).first()
        if not visit:
            visit = Visit.objects.filter(patient__id_card=patient_id_param).first()

    if not visit:
        visit = Visit.objects.first()

    if not visit:
        return HttpResponse("No se encontró ninguna ficha clínica para generar el PDF.", status=404)

    pdf_bytes = generate_clinical_sheet_pdf(visit)
    filename = f"Ficha_Clinica_{visit.study_code.replace('/', '-')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
