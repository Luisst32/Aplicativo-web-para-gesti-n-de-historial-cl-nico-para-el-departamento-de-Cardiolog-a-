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
    EcgRhythm, Question, AnswerOption
)
from clinical.models import (
    Patient, Visit, Anthropometry, VitalSigns,
    Electrocardiogram, Echocardiogram, Laboratory, VisitAnswer
)
from clinical.validators import validate_ecuadorian_id, validate_clinical_ranges
from clinical.pdf import generate_clinical_sheet_pdf
from audit.services import register_audit_log


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

    return {
        "id": str(patient.patient_id),
        "codigo": visit.study_code if visit else f"{patient.patient_id:04d}/2026",
        "cedula": patient.id_card,
        "nombre": patient.full_name,
        "fechaNac": patient.birth_date.isoformat() if patient.birth_date else "",
        "sexo": "H" if (patient.sex and patient.sex.name.lower().startswith('h')) else "M",
        "estamento": visit.staff_category.name if (visit and visit.staff_category) else "PDI",
        "facultad": visit.faculty if visit and visit.faculty else "UNEMI",
        "ciudad": visit.residence_canton.name if visit and visit.residence_canton else (patient.birth_canton.name if patient.birth_canton else "Milagro"),
        "provincia": "Guayas",
        "telefono": patient.phone or "",
        "correo": patient.email or "",
        "municipio": "Milagro",
        "raza": patient.ethnicity.name if patient.ethnicity else "Mestizo",
        "convivientes": str(visit.num_cohabitants or 4) if visit else "4",
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
    ordenar_por = request.GET.get('ordenar_por', 'nombre').strip().lower()
    direccion = request.GET.get('direccion', 'asc').strip().lower()
    prefix = '' if direccion == 'asc' else '-'

    if ordenar_por == 'nombre':
        qs = qs.order_by(f"{prefix}first_names", f"{prefix}last_name1")
    elif ordenar_por == 'fecha':
        qs = qs.order_by(f"{prefix}visit__visit_date")
    else:
        qs = qs.order_by(f"{prefix}first_names")

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

            # Generar siguiente código de estudio
            anio_actual = datetime.date.today().year
            total_visitas_anio = Visit.objects.filter(study_year=anio_actual).count()
            nuevo_codigo = f"{total_visitas_anio + 1:04d}/{anio_actual}"

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
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# =============================================================================
# JSON APIS: FORM POPULATION AND COMPLETE SAVING (HU-11, HU-12, HU-13)
# =============================================================================

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
    ant = getattr(visit, 'anthropometry', None) if visit else None
    vs = getattr(visit, 'vital_signs', None) if visit else None
    ecg = getattr(visit, 'electrocardiogram', None) if visit else None
    echo = getattr(visit, 'echocardiogram', None) if visit else None
    lab = getattr(visit, 'laboratory', None) if visit else None

    # Mapeo plano directo hacia los IDs y nombres del formulario HTML
    datos = {
        # Modulo 1: Ficha
        "f_nombre": patient.first_names,
        "f_apellido1": patient.last_name1,
        "f_apellido2": patient.last_name2 or "",
        "f_cedula": patient.id_card,
        "f_fecha_nac": patient.birth_date.isoformat() if patient.birth_date else "",
        "f_sexo": "H" if (patient.sex and patient.sex.name.lower().startswith('h')) else "M",
        "f_raza": patient.ethnicity.name if patient.ethnicity else "Mestizo",
        "f_telefono": patient.phone or "",
        "f_correo": patient.email or "",
        "f_codigo": visit.study_code if visit else "",
        "f_fecha_visita": visit.visit_date.isoformat() if (visit and visit.visit_date) else "",
        "f_facultad": visit.faculty if visit and visit.faculty else "UNEMI",
        "f_estamento": visit.staff_category.name if (visit and visit.staff_category) else "PDI",
        "f_num_hijos": visit.num_children if (visit and visit.num_children is not None) else "",
        "f_num_convivientes": visit.num_cohabitants if (visit and visit.num_cohabitants is not None) else "",

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

    # Cargar respuestas dinámicas guardadas
    if visit:
        for ans in visit.answers.select_related('question', 'selected_option').all():
            q_code = ans.question.code
            if ans.selected_option:
                datos[q_code] = ans.selected_option.label
            elif ans.text_value:
                datos[q_code] = ans.text_value
            elif ans.numeric_value is not None:
                datos[q_code] = str(ans.numeric_value)

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

            if f_nom: patient.first_names = f_nom
            if f_ap1: patient.last_name1 = f_ap1
            if f_ap2 is not None: patient.last_name2 = f_ap2
            if f_tel is not None: patient.phone = f_tel
            if f_cor is not None: patient.email = f_cor
            if f_sex:
                s_obj = Sex.objects.filter(name__istartswith=f_sex[0]).first()
                if s_obj: patient.sex = s_obj
            patient.save()

            # 2. Actualizar / Crear Visita (Módulo 1)
            visit = getattr(patient, 'visit', None)
            if not visit:
                # Generar código si hace falta
                if not codigo:
                    anio_actual = datetime.date.today().year
                    codigo = f"{Visit.objects.count() + 1:04d}/{anio_actual}"

                visit = Visit.objects.create(
                    patient=patient,
                    evaluator=request.user,
                    study_code=codigo,
                    visit_date=datetime.date.today(),
                    residence_canton=patient.birth_canton or Canton.objects.first(),
                    status=Visit.Status.COMPLETED
                )

            f_fecha_vis = raw_data.get('f_fecha_visita')
            if f_fecha_vis:
                try:
                    visit.visit_date = datetime.date.fromisoformat(f_fecha_vis)
                except ValueError:
                    pass

            f_fac = raw_data.get('f_facultad')
            if f_fac: visit.faculty = f_fac

            f_estam = raw_data.get('f_estamento')
            if f_estam:
                sc_obj = StaffCategory.objects.filter(name__icontains=f_estam).first()
                if sc_obj: visit.staff_category = sc_obj

            f_hijos = raw_data.get('f_num_hijos')
            if f_hijos and f_hijos.isdigit():
                visit.num_children = int(f_hijos)

            f_conviv = raw_data.get('f_num_convivientes')
            if f_conviv and f_conviv.isdigit():
                visit.num_cohabitants = int(f_conviv)

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
            vs.systolic_murmur = (raw_data.get('f_soplo_sistolico') == 'Si')
            vs.diastolic_murmur = (raw_data.get('f_soplo_diastolico') == 'Si')
            if raw_data.get('f_grado_soplo') and raw_data.get('f_grado_soplo').isdigit():
                vs.murmur_grade = int(raw_data.get('f_grado_soplo'))
            vs.pulmonary_auscultation_normal = (raw_data.get('f_auscultacion_pulmonar') != 'Alterada')
            vs.abdominal_auscultation_normal = (raw_data.get('f_auscultacion_abdominal') != 'Alterada')
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
            if raw_data.get('eco_ddvi'):
                try: echo.lv_dimension_mm = Decimal(str(raw_data['eco_ddvi']))
                except Exception: pass
            if raw_data.get('eco_fey'):
                try: echo.lvef_percentage = Decimal(str(raw_data['eco_fey']))
                except Exception: pass
            echo.ventricular_hypertrophy = (raw_data.get('res_vi_hipertrofico') == 'Si')
            echo.diastolic_dysfunction = (raw_data.get('eco_disfuncion_diastolica') == 'Si')
            echo.aortic_valve_calcification = (raw_data.get('eco_calcificacion_aortica') == 'Si')
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

            # 8. Guardado dinámico de respuestas en VisitaRespuesta (HU-12, HU-13)
            # Cargar preguntas del catálogo
            preguntas = Question.objects.prefetch_related('options').all()
            for q in preguntas:
                val = raw_data.get(q.code)
                if val is not None and str(val).strip() != '':
                    val_str = str(val).strip()
                    selected_opt = None
                    num_val = None
                    txt_val = None

                    # Buscar si coincide con alguna opción
                    for opt in q.options.all():
                        if opt.label.lower() == val_str.lower():
                            selected_opt = opt
                            break

                    if not selected_opt:
                        if q.response_type == Question.ResponseType.NUMERICO:
                            try:
                                num_val = Decimal(val_str)
                            except Exception:
                                txt_val = val_str
                        else:
                            txt_val = val_str

                    # Upsert VisitAnswer
                    ans, created = VisitAnswer.objects.get_or_create(
                        visit=visit,
                        question=q,
                        defaults={
                            "selected_option": selected_opt,
                            "numeric_value": num_val,
                            "text_value": txt_val
                        }
                    )
                    if not created:
                        ans.selected_option = selected_opt
                        ans.numeric_value = num_val
                        ans.text_value = txt_val
                        ans.save()

            # 9. Auditoría Automática (HU-14)
            register_audit_log(
                user=request.user,
                table_name='visit',
                record_key=visit.visit_id,
                action='UPDATE',
                new_value={
                    'study_code': visit.study_code,
                    'patient': patient.full_name,
                    'peso': float(ant.weight_kg),
                    'tas': vs.systolic_bp
                },
                machine_name=getattr(request, 'client_ip', '127.0.0.1')
            )

        return JsonResponse({
            "success": True,
            "message": f"Historial Clínico de {patient.full_name} guardado exitosamente en la base de datos.",
            "paciente": _patient_to_dict(patient, visit)
        })

    except Exception as e:
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
