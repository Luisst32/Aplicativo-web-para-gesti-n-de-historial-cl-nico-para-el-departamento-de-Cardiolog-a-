from clinical.services.clinical_form import update_clinical_record, _resolve_canton
from .services.sav_importer import analyze_sav_file, execute_sav_import
import json
import datetime
import secrets
import hashlib
import io
import zipfile
import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.db import models, transaction, connection
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.urls import reverse

from catalog.models import (
    Country, Province, Canton, Institution,
    Sex, Ethnicity, StaffCategory, ProfessionalCategory,
    EducationLevel, IncomeRange, MaritalStatus,
    LivingSituation, HousingType, WorkSchedule,
    EcgRhythm, Question, AnswerOption, QuestionnaireSection
)
from clinical.models import (
    Patient, Visit, Anthropometry, VitalSigns,
    Electrocardiogram, Echocardiogram, Laboratory, OrderedStudies, VisitAnswer,
    SecureShare
)
from clinical.services.measurements import save_measurements
from clinical.validators import validate_ecuadorian_id, validate_clinical_ranges
from clinical.pdf import generate_clinical_sheet_pdf
from audit.services import AuditLogError, register_audit_log
from security.access import clinical_access_required, require_clinical_access

from clinical.services.record_selection import (
    RecordSelectionError, record_id, selected_patients, selected_visits, selection_errors,
)

logger = logging.getLogger(__name__)


from clinical.services.sav_importer import (
    analyze_sav_file, execute_sav_import,
    SPSS_QUESTION_ALIASES, classify_spss_question_section
)

QUESTION_ALIASES = SPSS_QUESTION_ALIASES
REVERSE_QUESTION_ALIASES = {v: k for k, v in QUESTION_ALIASES.items()}
REVERSE_ALIASES = REVERSE_QUESTION_ALIASES


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
            "peso": float(ant.weight_kg) if (ant and ant.weight_kg) else None,
            "talla": float(ant.height_cm) if (ant and ant.height_cm) else None,
            "imc": float(ant.bmi) if (ant and ant.bmi) else None,
            "asc": float(ant.body_surface_area) if (ant and ant.body_surface_area) else None,
            "tas": vs.systolic_bp if (vs and vs.systolic_bp) else None,
            "tsi": vs.diastolic_bp if (vs and vs.diastolic_bp) else None,
            "satO2": vs.oxygen_saturation if (vs and vs.oxygen_saturation) else None,
            "perimetro": float(ant.waist_circumference_cm) if (ant and ant.waist_circumference_cm) else None,
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
        "codigo_estudio": visit.study_code if (visit and visit.study_code) else str(patient.patient_id),
        "cedula": patient.id_card,
        "first_names": patient.first_names,
        "last_name1": patient.last_name1,
        "last_name2": patient.last_name2 or "",
        "nombre": patient.full_name,
        "nombre_completo": patient.full_name,
        "fechaNac": patient.birth_date.isoformat() if patient.birth_date else "",
        "sexo": "H" if (patient.sex and patient.sex.name.lower().startswith('h')) else "M",
        "estamento": visit.staff_category.name if (visit and visit.staff_category) else "PDI",
        "universidad": patient.institution.acronym if (patient.institution and patient.institution.acronym) else "UNEMI",
        "facultad": visit.faculty if visit and visit.faculty else "FACI",
        "ciudad": visit.residence_canton.name if (visit and visit.residence_canton) else (patient.birth_canton.name if patient.birth_canton else "Milagro"),
        "provincia": visit.residence_canton.province.name.upper() if (visit and visit.residence_canton and visit.residence_canton.province) else "GUAYAS",
        "telefono": patient.phone or "",
        "correo": patient.email or "",
        "email": patient.email or "",
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
        "peso": float(ant.weight_kg) if (ant and ant.weight_kg) else None,
        "talla": float(ant.height_cm) if (ant and ant.height_cm) else None,
        "tas": vs.systolic_bp if (vs and vs.systolic_bp) else None,
        "tsi": vs.diastolic_bp if (vs and vs.diastolic_bp) else None,
        "satO2": vs.oxygen_saturation if (vs and vs.oxygen_saturation) else None,
        "perimetro": float(ant.waist_circumference_cm) if (ant and ant.waist_circumference_cm) else None,
        "historiales": historiales
    }


# =============================================================================
# TEMPLATE RENDERING VIEWS
# =============================================================================

@login_required
@clinical_access_required('read')
def form_view(request):
    """
    Renders the clinical evaluation form template.
    Data is populated asynchronously via form_get_api or initial context.
    """
    return render(request, 'clinical/form.html')


@login_required
@clinical_access_required('read')
def list_view(request):
    """
    Renders the patients directory and medical evaluations list.
    Populates dynamic filters for available years and staff categories (HU-15, HU-16).
    """
    total_pacientes = Patient.objects.filter(status=Patient.Status.ACTIVE).count()

    from django.utils import timezone
    from django.db.models.functions import ExtractYear
    from catalog.models import StaffCategory

    # Detección dinámica inteligente: ÚNICAMENTE los años de visitas de pacientes activos existentes
    years_qs = Visit.objects.filter(
        visit_date__isnull=False,
        patient__status=Patient.Status.ACTIVE
    ).annotate(
        v_year=ExtractYear('visit_date')
    ).values_list('v_year', flat=True).distinct()

    years_set = {int(y) for y in years_qs if y is not None and 1900 < int(y) < 2200}
    if not years_set:
        years_set = {timezone.now().year}
    available_years = sorted(list(years_set), reverse=True)

    # Estamentos institucionales presentes en visitas de la cohorte activa
    estamentos_qs = list(
        Visit.objects.filter(
            patient__status=Patient.Status.ACTIVE,
            staff_category__isnull=False
        ).values_list('staff_category__name', flat=True).distinct().order_by('staff_category__name')
    )
    if not estamentos_qs:
        estamentos_qs = list(
            StaffCategory.objects.filter(status=StaffCategory.Status.ACTIVE)
            .values_list('name', flat=True).order_by('name')
        )

    labels_map = {
        'PDI': 'PDI (Docentes)',
        'AD': 'AD (Administrativos)',
        'PAS': 'PAS (Personal de Adm. y Servicios)',
        'SERVICIO': 'SERVICIO (Apoyo)',
        'ESTUDIANTES': 'ESTUDIANTES',
    }
    available_estamentos = [
        {'code': name, 'label': labels_map.get(name.upper(), name)}
        for name in estamentos_qs
    ]

    return render(request, 'clinical/list.html', {
        'total_pacientes': total_pacientes,
        'available_years': available_years,
        'available_estamentos': available_estamentos,
    })


# =============================================================================
# JSON APIS: DIRECTORY, FILTERING, PAGINATION AND QUICK-CREATE (HU-15, HU-16)
# =============================================================================

@login_required
@require_GET
@clinical_access_required('read', api=True)
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
        'sex', 'ethnicity', 'birth_canton', 'birth_canton__province', 'institution',
        'visit', 'visit__staff_category', 'visit__residence_canton', 'visit__residence_canton__province', 'visit__evaluator',
        'visit__anthropometry', 'visit__vital_signs', 'visit__marital_status',
        'visit__living_situation', 'visit__education_level', 'visit__work_schedule',
        'visit__professional_category', 'visit__housing_type', 'visit__income_range'
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
        qs = qs.order_by(f"{prefix}first_names", f"{prefix}last_name1", "patient_id")
    elif ordenar_por == 'fecha':
        qs = qs.order_by(f"{prefix}visit__visit_date", "patient_id")
    elif ordenar_por == 'codigo':
        qs = qs.order_by(f"{prefix}patient_id")
    else:
        qs = qs.order_by(f"{prefix}patient_id")

    try:
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('page_size', 100))
        if page < 1 or not 1 <= size <= 200:
            raise ValueError
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Paginacion invalida.'}, status=400)
    total = qs.count()
    pacientes_list = [_patient_to_dict(p) for p in qs[(page-1)*size:page*size]]
    return JsonResponse({'success': True, 'total': total, 'pacientes': pacientes_list,
                         'next_page': page+1 if page*size < total else None})



@login_required
@require_GET
@clinical_access_required('read', api=True)
@selection_errors
def patient_detail_api(request, patient_id):
    """
    Returns full details for a single patient and their clinical visit.
    """
    patient = selected_patients([patient_id])[0]

    return JsonResponse({
        "success": True,
        "paciente": _patient_to_dict(patient)
    })


@login_required
@require_POST
@clinical_access_required('create', api=True)
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
        universidad_str = data.get('universidad', 'UNEMI').strip().upper()
        facultad = data.get('facultad', 'FACS').strip()
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
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(71342001)')
            # Catálogos base
            inst = (
                Institution.objects.filter(acronym__iexact=universidad_str).first() or
                Institution.objects.filter(name__icontains=universidad_str).first() or
                Institution.objects.first()
            )
            sexo = Sex.objects.filter(name__istartswith=sexo_str[0]).first() or Sex.objects.first()
            mestizo = Ethnicity.objects.filter(name="Mestizo").first() or Ethnicity.objects.first()
            milagro = Canton.objects.filter(name="Milagro").first() or Canton.objects.first()
            pdi = StaffCategory.objects.filter(name__icontains=estamento_str).first() or StaffCategory.objects.first()
            docente = ProfessionalCategory.objects.first()

            # Autogenerar cédula temporal si no vino ninguna
            if not cedula:
                cedula = f"09{Patient.objects.count() + 10000000:08d}"

            paciente = Patient.objects.create(
                institution=inst,
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

            # Código de estudio / N.° Ficha Clínica (manual o autogenerado)
            codigo_suministrado = str(data.get('codigo') or data.get('study_code') or '').strip()
            if codigo_suministrado:
                if Visit.objects.filter(patient__institution=inst, study_code=codigo_suministrado).exists():
                    return JsonResponse({
                        "success": False,
                        "error": f"El N.° de Ficha Clínica '{codigo_suministrado}' ya está asignado a otro paciente de esta institución. Ingrese un número diferente o déjelo en blanco para auto-asignar."
                    }, status=409)
                nuevo_codigo = codigo_suministrado
            else:
                existing_codes = Visit.objects.filter(patient__institution=inst).values_list('study_code', flat=True)
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
        logger.error("Clinical operation failed (%s).", type(e).__name__)
        return JsonResponse({"success": False, "error": "No se pudo completar la operacion."}, status=500)


# =============================================================================
# JSON APIS: FORM POPULATION AND COMPLETE SAVING (HU-11, HU-12, HU-13)
# =============================================================================

def _build_form_datos(patient, visit):
    """
    Constructs a dictionary of all field values matching HTML input/select/radio/checkbox
    names across all 6 clinical modules, with automatic cross-mapping of SPSS and database fields.
    """
    ant = getattr(visit, 'anthropometry', None) if visit else None
    vs = getattr(visit, 'vital_signs', None) if visit else None
    ecg = getattr(visit, 'electrocardiogram', None) if visit else None
    echo = getattr(visit, 'echocardiogram', None) if visit else None
    lab = getattr(visit, 'laboratory', None) if visit else None

    # Cálculo automático de edad si fecha de nacimiento existe
    edad_val = ""
    if patient.birth_date:
        today = datetime.date.today()
        edad_val = str(today.year - patient.birth_date.year - ((today.month, today.day) < (patient.birth_date.month, patient.birth_date.day)))

    # Ritmo ECG normalizado
    ecg_ritmo_val = "RS"
    if ecg and ecg.rhythm:
        r_name = ecg.rhythm.name.upper()
        if "SINUSAL" in r_name or "RS" in r_name:
            ecg_ritmo_val = "RS"
        elif "RL" in r_name:
            ecg_ritmo_val = "RL"
        elif "ACXFA" in r_name or "FA" in r_name or "AURICULAR" in r_name:
            ecg_ritmo_val = "ACXFA"
        else:
            ecg_ritmo_val = ecg.rhythm.name

    datos = {
        # Modulo 1: Ficha
        "f_nombre": patient.first_names,
        "f_apellido1": patient.last_name1,
        "f_apellido2": patient.last_name2 or "",
        "f_cedula": patient.id_card,
        "f_fecha_nac": patient.birth_date.isoformat() if patient.birth_date else "",
        "f_edad": edad_val,
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
        "f_pais_nac": "ECUADOR",

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
        "soplos": "Si" if (vs and (vs.systolic_murmur or vs.diastolic_murmur)) else "No",
        "soplo_grado": str(vs.murmur_grade) if (vs and vs.murmur_grade) else "",
        "soplo_tipo": "Sistólico" if (vs and vs.systolic_murmur) else ("Diastólico" if (vs and vs.diastolic_murmur) else ""),
        "pulsos_palp": "Si" if (vs and vs.pedal_pulses_symmetric is not None) else "Si",
        "pulsos_sim": "Si" if (vs and vs.pedal_pulses_symmetric) else ("No" if (vs and vs.pedal_pulses_symmetric is False) else "Si"),
        "resp_norm": "Si" if (vs and vs.pulmonary_auscultation_normal) else ("No" if (vs and vs.pulmonary_auscultation_normal is False) else "Si"),
        "abdom_norm": "Si" if (vs and vs.abdominal_auscultation_normal) else ("No" if (vs and vs.abdominal_auscultation_normal is False) else "Si"),
        "f_soplo_sistolico": "Si" if (vs and vs.systolic_murmur) else "No",
        "f_soplo_diastolico": "Si" if (vs and vs.diastolic_murmur) else "No",
        "f_grado_soplo": str(vs.murmur_grade) if (vs and vs.murmur_grade) else "",
        "f_pulsos_pedios": "Si" if (vs and vs.pedal_pulses_symmetric) else "No",
        "f_auscultacion_pulmonar": "Normal" if (vs and vs.pulmonary_auscultation_normal) else "Alterada",
        "f_auscultacion_abdominal": "Normal" if (vs and vs.abdominal_auscultation_normal) else "Alterada",

        # Modulo 5: ECG Completo (27 ítems del Cuestionario UNEMI 2026 + normal + comentarios)
        "ecg_ritmo": ecg_ritmo_val,
        "ecg_normal": "Si" if (ecg and ecg.is_normal) else ("No" if ecg else "Si"),
        "ecg_fc": str(ecg.heart_rate) if (ecg and ecg.heart_rate is not None) else "",
        "ecg_eje": str(ecg.qrs_axis_degrees) if (ecg and ecg.qrs_axis_degrees is not None) else "",
        "ecg_rr": str(ecg.rr_interval_sec) if (ecg and ecg.rr_interval_sec is not None) else "",
        "ecg_p_mm": str(ecg.p_wave_mm) if (ecg and ecg.p_wave_mm is not None) else "",
        "ecg_pr": str(ecg.pr_interval_ms) if (ecg and ecg.pr_interval_ms is not None) else "",
        "ecg_qrs": str(ecg.qrs_duration_ms) if (ecg and ecg.qrs_duration_ms is not None) else "",
        "ecg_qt": str(ecg.qt_interval_ms) if (ecg and ecg.qt_interval_ms is not None) else "",
        "ecg_qtc": str(ecg.qtc_bazett_ms) if (ecg and ecg.qtc_bazett_ms is not None) else "",
        "ecg_p_mitral": "Si" if (ecg and ecg.p_mitrale) else "No",
        "ecg_bloqueo_av": "Si" if (ecg and ecg.av_block) else "No",
        "ecg_bloqueo_av_grado": ecg.av_block_grade if (ecg and ecg.av_block_grade) else "",
        "ecg_bloqueo_sa": "Si" if (ecg and ecg.sa_block) else "No",
        "ecg_bloqueo_ia": "Si" if (ecg and ecg.interatrial_block) else "No",
        "ecg_hemibloqueo": "Si" if (ecg and ecg.hemiblock) else "No",
        "ecg_hemibloqueo_cual": ecg.hemiblock_detail if (ecg and ecg.hemiblock_detail) else "",
        "ecg_bloqueo_rama_sn": "Si" if (ecg and (ecg.has_bundle_branch_block or ecg.bundle_branch_block)) else "No",
        "ecg_bloqueo_rama": ecg.bundle_branch_block if (ecg and ecg.bundle_branch_block) else "",
        "ecg_brugada": "Si" if (ecg and ecg.brugada_pattern) else "No",
        "ecg_repolarizacion_precoz": "Si" if (ecg and ecg.early_repolarization) else "No",
        "ecg_hvi": "Si" if (ecg and ecg.left_ventricular_hypertrophy) else "No",
        "ecg_sobrecarga_sistolica": "Si" if (ecg and ecg.systolic_overload) else "No",
        "ecg_sobrecarga_complejos": ecg.systolic_overload_complexes if (ecg and ecg.systolic_overload_complexes) else "",
        "ecg_deflexion_intrinsicoide": str(ecg.intrinsicoid_deflection_sec) if (ecg and ecg.intrinsicoid_deflection_sec is not None) else "",
        "ecg_hvd": "Si" if (ecg and ecg.right_ventricular_hypertrophy) else "No",
        "ecg_onda_delta": "Si" if (ecg and ecg.delta_wave) else "No",
        "ecg_cubeta_digitalica": "Si" if (ecg and ecg.digitalis_effect) else "No",
        "ecg_onda_q": "Si" if (ecg and ecg.pathological_q_wave) else "No",
        "ecg_onda_q_amplitud": ecg.q_wave_amplitude if (ecg and ecg.q_wave_amplitude) else "",
        "ecg_onda_q_voltaje": str(ecg.q_wave_voltage_mv) if (ecg and ecg.q_wave_voltage_mv is not None) else "",
        "ecg_onda_q_complejos": ecg.q_wave_complexes if (ecg and ecg.q_wave_complexes) else "",
        "ecg_t_negativa": "Si" if (ecg and ecg.negative_t_wave) else "No",
        "ecg_t_negativa_complejos": ecg.negative_t_complexes if (ecg and ecg.negative_t_complexes) else "",
        "ecg_t_simetrica": "Si" if (ecg and ecg.negative_t_symmetric) else "No",
        "ecg_t_asimetrica": "Si" if (ecg and ecg.negative_t_asymmetric) else "No",
        "ecg_st_ascenso": "Si" if (ecg and ecg.st_elevation_pathological) else "No",
        "ecg_st_ascenso_mm": str(ecg.st_elevation_mm) if (ecg and ecg.st_elevation_mm is not None) else "",
        "ecg_st_ascenso_complejos": ecg.st_elevation_complexes if (ecg and ecg.st_elevation_complexes) else "",
        "ecg_st_descenso": "Si" if (ecg and ecg.st_depression) else "No",
        "ecg_st_descenso_mm": str(ecg.st_depression_mm) if (ecg and ecg.st_depression_mm is not None) else "",
        "ecg_st_descenso_complejos": ecg.st_depression_complexes if (ecg and ecg.st_depression_complexes) else "",
        "ecg_alt_repolarizacion": "Si" if (ecg and (ecg.repolarization_abnormalities or ecg.early_repolarization)) else "No",
        "ecg_comentario": ecg.ecg_comments if (ecg and ecg.ecg_comments) else "",

        # Modulo 4: Ecocardiograma
        "res_eco_normal": "No" if (echo and (echo.ventricular_hypertrophy or echo.diastolic_dysfunction or echo.aortic_valve_calcification)) else "Si",
        "res_vi_hipertrofico": "Si" if (echo and echo.ventricular_hypertrophy) else "No",
        "res_fdvi": "Alterada" if (echo and echo.diastolic_dysfunction) else "Normal",
        "valvulopatia_tipo_detalle": echo.valvular_regurgitation_detail if (echo and echo.valvular_regurgitation_detail) else "",
        "eco_ddvi": str(echo.lv_dimension_mm) if (echo and echo.lv_dimension_mm) else "",
        "eco_fey": str(echo.lvef_percentage) if (echo and echo.lvef_percentage) else "",

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
        # Bioquímica y Hemograma extendidos
        "hemo_hcm": "",
        "hemo_chcm": "",
        "hemo_neutrofilos": "",
        "hemo_eosinofilos": "",
        "hemo_basofilos": "",
        "hemo_linfocitos": "",
        "hemo_monocitos": "",
        "hemo_tpt": "",
        "hemo_fibrinogeno": "",
        "tiroidea_t4": "",
        "tiroidea_t3": "",
        "renal_filtrado": "",
        "orina_microalbuminuria": "",
        "ion_potasio": "",
        "ion_calcio": "",
        "ion_magnesio": "",
        "ion_sodio": "",
        "diab_hba1c": "",
        "diab_homair": "",
        "diab_insulina": "",
        "riesgo_vldl": "",
        "riesgo_lipoproteina_a": "",
        "riesgo_apo_b": "",
        "emerg_homocisteina": "",
        "emerg_pcr": "",
        "emerg_acido_urico": "",
        "hepatica_fosfatasa": "",
        "hepatica_bilirrubina": "",
        "res_vi_dilatado": "No",
        "res_vi_hipertrofico_tipo": "",
        "res_eco_comentario": "",
        "res_eco_vascular": "Normal",
        "res_eco_vascular_comentario": "",
        "ip_medida_chorro": "",
        "ip_ancho_chorro": "",
        "ip_grado": "",
        "ip_tipo_especificar": "",

        # Factores modificables adicionales (Pág. 3 Cuestionario UNEMI 2026)
        "r_mapa": "No",
        "mapa_resultado": "Normal",
        "r_holter": "No",
        "holter_resultado": "Normal",
        "r_vasc_fem": "No",
        "hta_medicamentos": "",
        "dislip_farmacos": "",

        # Personalidad Tipo A extendida (Cuestionario UNEMI 2026)
        "em_exigente": "",
        "em_perfeccionista": "",
        "em_hiperactivo": "",
        "em_ambicioso": "",
        "em_hostilidad": "",
        "em_aislamiento": "",

        # Drogas detalladas (Cuestionario UNEMI 2026)
        "drogas_dosis_diaria": "",
        "drogas_dosis_semanal": "",
        "drogas_dosis_ocasional": "",
        "chk_ex_drogas": "",

        # Historia Clínica Actual Cardiovascular (ítems 1 al 6 - Cuestionario UNEMI 2026)
        "hc_prob": "No",
        "prob_corazon_detalle": "",
        "hc_isquemica": "No",
        "hc_isquemica_angina": "",
        "hc_isquemica_infarto": "",
        "hc_revasc": "No",
        "hc_revasc_tipo": "",
        "hc_insuf_cardiaca": "No",
        "hc_valvulopatia": "No",
        "hc_valvulopatia_cuales": "",
        "hc_valvulopatia_operado": "No",
        "hc_ingresado": "No",
        "hc_ingresado_cual": "",

        # Historia de Cáncer y Oncología (Cuestionario UNEMI 2026)
        "cancer_pulmon": "",
        "cancer_prostata": "",
        "cancer_colon": "",
        "cancer_mama": "",
        "cancer_vejiga": "",
        "cancer_utero": "",
        "cancer_ovario": "",
        "cancer_otro": "",
        "cancer_otro_detalle": "",
        "cancer_qt": "No",
        "cancer_rt": "No",

        # Estudios que se le han mandado al paciente (Pág. 19 Cuestionario UNEMI 2026)
        "est_analisis_clinicos": "No",
        "est_ergometria_spect": "No",
        "est_tac_cardiaco": "No",
        "est_rnm_cardiaco": "No",
        "est_electrofisiologia": "No",
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

        # Cargar estudios mandados al paciente desde PostgreSQL
        ordered = getattr(visit, 'ordered_studies', None)
        if ordered:
            datos['est_analisis_clinicos'] = "Si" if ordered.clinical_analysis else "No"
            datos['est_ergometria_spect'] = "Si" if ordered.ergometry_spect else "No"
            datos['est_tac_cardiaco'] = "Si" if ordered.cardiac_ct else "No"
            datos['est_rnm_cardiaco'] = "Si" if ordered.cardiac_mri else "No"
            datos['est_electrofisiologia'] = "Si" if ordered.electrophysiology else "No"

        # Cargar todas las respuestas guardadas en VisitAnswer
        ans_dict = {}
        for ans in visit.answers.select_related('question').all():
            q_code = ans.question.code
            if ans.text_value:
                val = ans.text_value
            elif ans.numeric_value is not None:
                if ans.numeric_value % 1 == 0:
                    val = str(int(ans.numeric_value))
                else:
                    val = f"{float(ans.numeric_value):.2f}".rstrip('0').rstrip('.')
            elif ans.selected_option:
                val = ans.selected_option.label
            else:
                val = ""
            if val is not None and str(val).strip() != '':
                ans_dict[q_code] = val
                datos[q_code] = val
                # Sincronizar bidireccionalmente con los identificadores del formulario HTML
                for form_k, spss_k in QUESTION_ALIASES.items():
                    if q_code.lower() == spss_k.lower():
                        datos[form_k] = val
                    elif q_code.lower() == form_k.lower():
                        datos[spss_k] = val

        # Inyecciones y deducciones inteligentes para compatibilidad total con SPSS:
        # 0. Edad real reportada en SPSS/VisitAnswer
        if ans_dict.get('edad'):
            try:
                edad_num = str(ans_dict.get('edad')).split('.')[0].strip()
                if edad_num.isdigit() and int(edad_num) > 0:
                    datos['f_edad'] = edad_num
            except Exception:
                pass

        # 1. Estrés laboral y familiar (ESTRES de SPSS contiene ambos)
        estres = ans_dict.get('estres', '')
        if estres:
            e_up = estres.upper()
            if any(k in e_up for k in ['TRABAJO', 'TREBAJO']) and 'NO EN EL TRABAJO' not in e_up:
                datos['em_estres_trab'] = 'Si'
            else:
                datos['em_estres_trab'] = 'No'
            if 'FAMILIAR' in e_up and 'NO EN LA VIDA FAMILIAR' not in e_up:
                datos['em_estres_fam'] = 'Si'
            else:
                datos['em_estres_fam'] = 'No'

        # 2. Antecedentes familiares (Padre / Madre / Familiares)
        p_ans = ans_dict.get('antecedentes_padres', '') or ans_dict.get('af_padres', '')
        if p_ans:
            p_up = p_ans.upper()
            if 'HTA' in p_up: datos['ant_padre_hta'] = 'Si'
            if 'DIABET' in p_up: datos['ant_padre_dm'] = 'Si'
            if 'DISLIP' in p_up or 'DLP' in p_up: datos['ant_padre_dislip'] = 'Si'
        m_ans = ans_dict.get('antecedentes_madres', '') or ans_dict.get('af_madres', '')
        if m_ans:
            m_up = m_ans.upper()
            if 'HTA' in m_up: datos['ant_madre_hta'] = 'Si'
            if 'DIABET' in m_up: datos['ant_madre_dm'] = 'Si'
            if 'DISLIP' in m_up or 'DLP' in m_up: datos['ant_madre_dislip'] = 'Si'
        fam_ans = ans_dict.get('antecedentes_familiares', '')
        if fam_ans:
            fam_up = fam_ans.upper()
            if 'PADRE' in fam_up:
                if 'HTA' in fam_up: datos['ant_padre_hta'] = 'Si'
                if 'DIABET' in fam_up: datos['ant_padre_dm'] = 'Si'
                if 'DISLIP' in fam_up: datos['ant_padre_dislip'] = 'Si'
            if 'MADRE' in fam_up:
                if 'HTA' in fam_up: datos['ant_madre_hta'] = 'Si'
                if 'DIABET' in fam_up: datos['ant_madre_dm'] = 'Si'
                if 'DISLIP' in fam_up: datos['ant_madre_dislip'] = 'Si'

        # 3. Vasculopatía
        vasc = ans_dict.get('vasculopatia', '')
        if vasc:
            v_up = vasc.upper()
            if 'PERIF' in v_up or 'FEMORAL' in v_up: datos['r_vasc_perif'] = 'Si'
            elif 'NO TIENE' in v_up or v_up == 'NO': datos['r_vasc_perif'] = 'No'
            if 'CAROT' in v_up: datos['r_vasc_carot'] = 'Si'
            elif 'NO TIENE' in v_up or v_up == 'NO': datos['r_vasc_carot'] = 'No'

        # 4. Problemas respiratorios (EPOC / Asma)
        resp_p = ans_dict.get('problemas_respiratorios', '')
        if resp_p:
            r_up = resp_p.upper()
            if 'EPOC' in r_up and 'NO TIENE' not in r_up: datos['nc_epoc'] = 'Si'
            elif 'NO' in r_up: datos['nc_epoc'] = 'No'
            if 'ASMA' in r_up and 'NO TIENE' not in r_up: datos['nc_asma'] = 'Si'
            elif 'NO' in r_up: datos['nc_asma'] = 'No'

        # 5. Salud mental (Depresión / Ansiedad)
        sm = ans_dict.get('salud_mental', '')
        if sm:
            sm_up = sm.upper()
            if 'DEPRESI' in sm_up and 'NO TIENE' not in sm_up: datos['nc_depresion'] = 'Si'
            elif 'NO' in sm_up: datos['nc_depresion'] = 'No'
            if 'ANSIED' in sm_up and 'NO TIENE' not in sm_up: datos['nc_ansiedad'] = 'Si'
            elif 'NO' in sm_up: datos['nc_ansiedad'] = 'No'

        # 6. Alcohol y Drogas
        alc = ans_dict.get('alcohol', '')
        if alc:
            a_up = alc.upper()
            if 'NO CONSUME' in a_up or a_up == 'NO':
                datos['r_alcohol'] = 'No'
            elif 'EX CONSUMIDOR' in a_up:
                datos['r_alcohol'] = 'No'
                datos['chk_ex_alcohol'] = 'Si'
            elif any(k in a_up for k in ['CONSUME', 'DIARIA', 'SEMANAL', 'OCASIONAL']):
                datos['r_alcohol'] = 'Si'
                datos['alcohol_frecuencia'] = alc
        drg = ans_dict.get('drogas', '')
        if drg:
            d_up = drg.upper()
            if 'NO CONSUME' in d_up or d_up == 'NO':
                datos['r_drogas'] = 'No'
            elif 'EX CONSUMIDOR' in d_up:
                datos['r_drogas'] = 'No'
                datos['chk_ex_drogas'] = 'Si'
            elif 'CONSUME' in d_up:
                datos['r_drogas'] = 'Si'
                datos['drogas_frecuencia'] = drg

        # 7. COVID-19 y Secuelas
        hc = ans_dict.get('historia_covid', '')
        if hc:
            h_up = hc.upper()
            if 'PASÓ' in h_up or 'PASO' in h_up or h_up.startswith('S') or h_up == '1':
                datos['covid_paso'] = 'Si'
                datos['covid_ingreso'] = 'Si' if ('INGRESADO' in h_up or 'HOSP' in h_up) else 'No'
            elif 'NO' in h_up or h_up == '0':
                datos['covid_paso'] = 'No'
                datos['covid_ingreso'] = 'No'
        afc = ans_dict.get('afectacion_covid', '')
        if afc:
            af_up = afc.upper()
            if 'CARDIO' in af_up: datos['covid_cv'] = 'Si'
            elif 'NO' in af_up: datos['covid_cv'] = 'No'
            if 'PULMON' in af_up: datos['covid_pulm'] = 'Si'
            elif 'NO' in af_up: datos['covid_pulm'] = 'No'
        lc = ans_dict.get('long_covid', '')
        if lc:
            l_up = lc.upper()
            if l_up.startswith('S') or 'SÍ' in l_up or 'SI' in l_up:
                datos['longcovid'] = 'Si'
                datos['longcovid_sintomas'] = lc
            elif 'NO' in l_up:
                datos['longcovid'] = 'No'

        # 8. Dieta Mediterránea PREDIMED (Aceite, Vino, Lácteos)
        ao = ans_dict.get('usa_usted_aceite_de_oliva', '')
        if ao:
            ao_up = ao.upper()
            if 'DOS O MÁS' in ao_up or 'DO O M' in ao_up or ao_up in ('2', '2.0'):
                datos['pred_q1'] = 'Si'
                datos['pred_q2'] = 'Si'
            elif 'SI' in ao_up or 'SÍ' in ao_up or ao_up in ('1', '1.0'):
                datos['pred_q1'] = 'Si'
                datos['pred_q2'] = 'No'
            elif 'NO' in ao_up or ao_up in ('0', '0.0'):
                datos['pred_q1'] = 'No'
                datos['pred_q2'] = 'No'
        vt = ans_dict.get('usted_consume_vino_tinto', '')
        if vt:
            vt_up = vt.upper()
            if 'TRES O MAS' in vt_up or 'TRES O MÁS' in vt_up or vt_up in ('2', '2.0'):
                datos['pred_q8_bebe'] = 'Si'
                datos['pred_q8'] = 'Si'
            elif 'SI' in vt_up or 'SÍ' in vt_up or vt_up in ('1', '1.0'):
                datos['pred_q8_bebe'] = 'Si'
                datos['pred_q8'] = 'No'
            elif 'NO' in vt_up or vt_up in ('0', '0.0'):
                datos['pred_q8_bebe'] = 'No'
                datos['pred_q8'] = 'No'
        leche = ans_dict.get('usted_consume_leche_de_vaca', '')
        if leche:
            l_up = leche.upper()
            datos['pred_q13_consume'] = 'No' if ('NO' in l_up or l_up in ('0', '0.0')) else 'Si'
        queso = ans_dict.get('usted_consume_queso', '')
        if queso:
            q_up = queso.upper()
            datos['pred_q14_consume'] = 'No' if ('NO' in q_up or q_up in ('0', '0.0')) else 'Si'
        yogurt = ans_dict.get('usted_consume_yogurt', '')
        if yogurt:
            y_up = yogurt.upper()
            datos['pred_q15_consume'] = 'No' if ('NO' in y_up or y_up in ('0', '0.0')) else 'Si'

        # 9. Dolor de pecho / Cuestionario Rose
        dp = ans_dict.get('dolor_pecho', '')
        if dp:
            dp_up = dp.upper()
            if 'NO' in dp_up or dp_up in ('0', '0.0'):
                datos['rose_1'] = 'No'
            elif 'SI' in dp_up or 'SÍ' in dp_up or 'LUGAR' in dp_up or dp_up in [str(i) for i in range(1, 10)]:
                datos['rose_1'] = 'Si'
                for num in range(1, 10):
                    if f"LUGAR {num}" in dp_up or dp_up == str(num):
                        datos[f"rose_zona_{num}"] = "1"

    
    # Evaluación inteligente del estado de Análisis Clínicos:
    has_lab = any([
        datos.get(k) for k in [
            'hemo_hematies', 'hemo_hemoglobina', 'hemo_leucocitos', 'hemo_plaquetas',
            'diab_glucosa', 'renal_urea', 'renal_creatinina', 'riesgo_colesterol',
            'riesgo_trigliceridos', 'tiroidea_tsh', 'hemo_vcm', 'hemo_inr'
        ]
    ])
    if has_lab:
        datos['ac_prueba'] = 'Si'
        alt = False
        try:
            if datos.get('diab_glucosa') and (float(datos['diab_glucosa']) >= 126 or float(datos['diab_glucosa']) < 70):
                alt = True
            if datos.get('riesgo_colesterol') and float(datos['riesgo_colesterol']) >= 200:
                alt = True
            if datos.get('riesgo_trigliceridos') and float(datos['riesgo_trigliceridos']) >= 150:
                alt = True
            if datos.get('hemo_hemoglobina') and (float(datos['hemo_hemoglobina']) < 12 or float(datos['hemo_hemoglobina']) > 18):
                alt = True
        except Exception:
            pass
        datos['ac_resultado'] = 'Alterada' if alt else 'Normal'
    else:
        datos['ac_prueba'] = 'No'
        datos['ac_resultado'] = 'Normal'

    return datos


@login_required
@require_GET
@clinical_access_required('read', api=True)
@selection_errors
def form_get_api(request, patient_id):
    """
    Fetches the full database record for a patient to populate form.html fields.
    """
    patient = selected_patients([patient_id])[0]

    visit = getattr(patient, 'visit', None)
    datos = _build_form_datos(patient, visit)

    return JsonResponse({
        "success": True,
        "paciente": _patient_to_dict(patient, visit),
        "datos": datos
    })




@login_required
@require_POST
@clinical_access_required('change', api=True)
@selection_errors
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
        selectors = [source[key] for source, key in (
            (request.GET, 'paciente'), (raw_data, 'idPaciente'), (raw_data, 'paciente_id')
        ) if key in source]
        if not selectors:
            raise RecordSelectionError('Seleccione un paciente por su clave primaria.')
        ids = {record_id(value) for value in selectors}
        if len(ids) != 1:
            raise RecordSelectionError('Identificadores de paciente contradictorios.')
        # Demographic fields never select a record for update.
        patient = selected_patients(list(ids))[0]

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
        visit = update_clinical_record(patient, raw_data, request.user, getattr(request, 'client_ip', 'unknown'))

        # Generar snapshot completo de todos los datos actualizados
        datos = _build_form_datos(patient, visit)

        return JsonResponse({
            "success": True,
            "message": f"Historial Clínico de {patient.full_name} guardado exitosamente en la base de datos.",
            "paciente": _patient_to_dict(patient, visit),
            "datos": datos
        })

    except ValidationError as error:
        return JsonResponse({'success': False, 'error': ' | '.join(error.messages)}, status=400)
    except RecordSelectionError:
        raise
    except Exception as e:
        logger.error("Clinical operation failed (%s).", type(e).__name__)
        return JsonResponse({"success": False, "error": "No se pudo completar la operacion."}, status=500)


# =============================================================================
# PDF EXPORT VIEW (HU-17)
# =============================================================================

@login_required
@clinical_access_required('read')
@selection_errors
def export_pdf_view(request, visit_id=None):
    """
    Genera y descarga el Cuestionario Clínico Oficial UNEMI en formato PDF (HU-17).
    Soporta descarga de evaluación completa o plantilla en blanco oficial.
    """
    is_blank = request.GET.get('blank') in ('1', 'true', 'True') or request.GET.get('vacio') in ('1', 'true', 'True')

    if is_blank:
        pdf_bytes = generate_clinical_sheet_pdf(None, is_blank=True)
        filename = "CUESTIONARIO_UNEMI_Plantilla_Definitivo_2026.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        disposition = 'attachment' if request.GET.get('download') in ('1', 'true', 'True') else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response

    require_clinical_access(request.user, 'export')
    patient_id_param = request.GET.get('paciente')
    historial_param = request.GET.get('historial')
    target_visit_id = visit_id if visit_id is not None else historial_param
    if target_visit_id is not None:
        visit = Visit.objects.filter(pk=record_id(target_visit_id, 'h')).first()
        if visit is None:
            raise RecordSelectionError('Ficha cl?nica no encontrada.', 404)
        if patient_id_param is not None and visit.patient_id != record_id(patient_id_param):
            raise RecordSelectionError('La ficha no pertenece al paciente seleccionado.', 404)
        if visit_id is not None and historial_param is not None and visit.pk != record_id(historial_param, 'h'):
            raise RecordSelectionError('Identificadores de ficha contradictorios.')
    elif patient_id_param is not None:
        visit = selected_visits([patient_id_param])[0]
    else:
        raise RecordSelectionError('Seleccione un paciente o una ficha cl?nica.')

    pdf_bytes = generate_clinical_sheet_pdf(visit, is_blank=False)
    study_code_clean = (visit.study_code or f"V{visit.visit_id}").replace('/', '-').replace(' ', '_')
    filename = f"Cuestionario_UNEMI_{study_code_clean}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    disposition = 'attachment' if request.GET.get('download') in ('1', 'true', 'True') else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


def _generate_zip_stream(visits):
    """
    Genera en memoria un archivo ZIP con todos los PDFs correspondientes a las visitas indicadas.
    Cada archivo se nombra de forma limpia e inequívoca con su código de estudio y nombre.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        used_names = set()
        for idx, v in enumerate(visits, start=1):
            pdf_bytes = generate_clinical_sheet_pdf(v, is_blank=False)
            code_str = (v.study_code or f"V{v.visit_id}").replace('/', '-').replace(' ', '_')
            p_name = (v.patient.full_name or f"Paciente_{idx}").replace(' ', '_')
            filename = f"Ficha_Clinica_{code_str}_{p_name}.pdf"
            if filename in used_names:
                filename = f"Ficha_Clinica_{code_str}_{p_name}_{idx}.pdf"
            used_names.add(filename)
            zf.writestr(filename, pdf_bytes)
    buffer.seek(0)
    return buffer.getvalue()


@login_required
@clinical_access_required('export', api=True)
@selection_errors
def api_download_batch_pdf(request):
    """
    Descarga masiva de fichas clínicas en PDF seleccionadas por el especialista.
    Si se seleccionó un solo paciente, descarga directamente su PDF oficial.
    Si se seleccionaron varios pacientes, los empaqueta y descarga en un archivo ZIP.
    """
    raw_ids = request.GET.get('patient_ids', '')
    if not raw_ids:
        raw_ids = request.POST.get('patient_ids', '')

    visits_list = selected_visits(raw_ids)

    if len(visits_list) == 1:
        v = visits_list[0]
        pdf_bytes = generate_clinical_sheet_pdf(v, is_blank=False)
        study_code_clean = (v.study_code or f"V{v.visit_id}").replace('/', '-').replace(' ', '_')
        filename = f"Cuestionario_UNEMI_{study_code_clean}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        zip_bytes = _generate_zip_stream(visits_list)
        response = HttpResponse(zip_bytes, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="Fichas_Clinicas_Cardiologia_UNEMI.zip"'
        return response


@login_required
@require_POST
@clinical_access_required('share', api=True)
@selection_errors
def api_send_patient_sheet_email(request):
    """
    Genera un envío seguro individual por cada destinatario especificado (SecureShare).
    Soporta una o múltiples fichas clínicas seleccionadas.
    No adjunta ningún PDF al correo: despacha solo un enlace protegido con caducidad.
    Permite descargas ilimitadas (sin cupo restrictivo) mientras el enlace se mantenga vigente.
    Devuelve los códigos de 6 dígitos una única vez en memoria para entrega fuera de banda.
    Responde con Cache-Control: no-store.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        resp = JsonResponse({"success": False, "error": "Cuerpo de solicitud JSON inválido."}, status=400)
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    patient_ids = data.get('patient_ids', [])
    recipients = data.get('recipients', [])
    raw_duration = data.get('duration_hours', 48)
    subject = (data.get('subject') or 'Documento disponible en portal seguro').strip()
    notes = (data.get('notes') or '').strip()[:300]

    if not patient_ids:
        resp = JsonResponse({"success": False, "error": "Debe seleccionar al menos una ficha clínica para compartir."}, status=400)
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    if not recipients:
        resp = JsonResponse({"success": False, "error": "Debe ingresar al menos una dirección de correo válida."}, status=400)
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    # Validar límite máximo de 5 destinatarios por operación
    if len(recipients) > 5:
        resp = JsonResponse({"success": False, "error": "No puede enviar a más de 5 destinatarios por operación."}, status=400)
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    # Validar formato de cada correo
    cleaned_recipients = []
    for r in recipients:
        email_str = str(r).strip()
        try:
            validate_email(email_str)
            if email_str not in cleaned_recipients:
                cleaned_recipients.append(email_str)
        except ValidationError:
            resp = JsonResponse({"success": False, "error": f"La dirección de correo '{email_str}' no tiene un formato válido."}, status=400)
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return resp

    # Validar caducidad (24h, 48h, 72h, 168h / 7 días)
    try:
        duration_hours = int(raw_duration)
        if duration_hours not in (24, 48, 72, 168):
            duration_hours = 48
    except (ValueError, TypeError):
        duration_hours = 48

    expires_at = timezone.now() + datetime.timedelta(hours=duration_hours)

    # Validar en el servidor que las fichas/visitas seleccionadas existan y sean legítimas
    visits_list = selected_visits(patient_ids)

    primary_visit = visits_list[0]
    results = []
    success_count = 0

    from security.services.email_service import send_secure_share_link_email

    deliveries = []
    for email in cleaned_recipients:
        # 1. Generar token criptoseguro para el enlace (32 bytes URL-safe)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # 2. Generar código numérico de 6 dígitos con secrets.randbelow
        raw_code = f"{secrets.randbelow(1000000):06d}"
        code_hash = make_password(raw_code)

        # 3. Construir URL pública absoluta hacia el portal de descarga
        access_url = request.build_absolute_uri(
            reverse('clinical:public_secure_share', kwargs={'token': raw_token})
        )

        # 4. Crear registro en base de datos (con token_hash, code_hash y sin límite restrictivo de descargas)
        share = SecureShare.objects.create(
            visit=primary_visit,
            recipient_email=email,
            token_hash=token_hash,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
            max_attempts=5,
            download_count=0,
            max_downloads=None,  # Sin límite restrictivo de descargas
            is_revoked=False,
            created_by=request.user,
            note=notes
        )
        share.visits.set(visits_list)

        # Registrar auditoría (NO se registra el código ni el token en texto claro)
        try:
            ip_addr = getattr(request, 'client_ip', 'unknown')
            if ip_addr and ',' in ip_addr:
                ip_addr = ip_addr.split(',')[0].strip()
            register_audit_log(
                user=request.user,
                schema_name='clinical',
                table_name='clinical_secure_share',
                record_key=str(share.share_id),
                action='INSERT',
                new_value={
                    'event': 'SECURE_SHARE_CREATED',
                    'visit_ids': [v.visit_id for v in visits_list],
                    'total_fichas': len(visits_list),
                    'recipient_email': email,
                    'expires_at': expires_at.isoformat(),
                    'duration_hours': duration_hours
                },
                machine_name=ip_addr
            )
        except AuditLogError:
            raise
        except Exception as audit_err:
            logger.warning(f"Error registrando auditoría de SecureShare: {audit_err}")

        deliveries.append((email, share, access_url, raw_code))

    # Prepare and audit the complete batch before sending the first email.
    for email, share, access_url, raw_code in deliveries:
        # 5. Despachar correo electrónico individual genérico (sin PDF adjunto)
        mail_res = send_secure_share_link_email(
            recipient_email=email,
            access_url=access_url,
            expires_at=expires_at,
            note_message=notes,
            subject=subject,
            sender_user=request.user,
            total_docs=len(visits_list)
        )

        if mail_res.get('success'):
            success_count += 1
            results.append({
                "email": email,
                "success": True,
                "code": raw_code,  # Solo se retorna en memoria para esta respuesta
                "total_docs": len(visits_list),
                "expires_at": expires_at.isoformat(),
                "expires_display": expires_at.strftime("%d/%m/%Y a las %H:%M")
            })
        else:
            # Si falla la entrega del correo, revocar el envío y no generar el código
            share.is_revoked = True
            share.revoked_at = timezone.now()
            share.save()
            results.append({
                "email": email,
                "success": False,
                "error": mail_res.get('error', 'Error al despachar correo electrónico.')
            })

    if success_count == 0:
        resp = JsonResponse({
            "success": False,
            "error": "No se pudo entregar el correo a ningún destinatario. Verifique su configuración SMTP.",
            "results": results
        }, status=500)
    else:
        resp = JsonResponse({
            "success": True,
            "message": f"Se generaron y enviaron {success_count} de {len(cleaned_recipients)} enlace(s) seguro(s) para {len(visits_list)} ficha(s) clínica(s).",
            "results": results
        })

    # Cabeceras estrictas de no-cache para proteger los códigos efímeros en tránsito
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
    resp['Pragma'] = 'no-cache'
    return resp


@require_http_methods(['GET', 'POST'])
@csrf_exempt
@transaction.atomic
@selection_errors
def public_secure_share_view(request, token):
    """
    Ruta pública del destinatario para validación de código de acceso y descarga segura.
    - Token verificado por hash SHA-256.
    - Límite de 5 intentos fallidos de código.
    - SIN límite restrictivo de descargas (descargas ilimitadas durante el periodo de caducidad).
    - Descarga de todas las fichas comprimidas en .ZIP o cada una por separado en .PDF.
    """
    clean_token = (token or '').strip()
    if not clean_token:
        raise Http404("Documento no encontrado o enlace inválido.")

    token_hash = hashlib.sha256(clean_token.encode('utf-8')).hexdigest()
    # Serialize checks and counter changes for this token only. Lock the share,
    # not its joined clinical records; release on response creation or rollback.
    share = SecureShare.objects.select_for_update(of=('self',)).select_related('visit', 'visit__patient').prefetch_related('visits', 'visits__patient').filter(token_hash=token_hash).first()

    if not share or not share.is_valid():
        resp = render(request, 'clinical/public_share_error.html', {
            'error_title': 'Enlace no disponible',
            'error_message': 'El enlace solicitado no existe, ha caducado o ha sido bloqueado por superar el límite de intentos fallidos permitidos.'
        }, status=404)
        resp['Referrer-Policy'] = 'no-referrer'
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    visits = share.get_visits()
    if not visits:
        raise Http404("No se encontraron documentos asociados a este enlace seguro.")

    is_unlocked = request.session.get(f'share_unlocked_{share.share_id}', False)
    error_msg = None

    # Manejo de descargas directas cuando la sesión ya está desbloqueada
    descarga_tipo = request.GET.get('descarga') or request.POST.get('descarga')
    target_vid = request.GET.get('visit_id') or request.POST.get('visit_id')

    is_download = descarga_tipo in ('zip', 'pdf') or (descarga_tipo == 'todo' and len(visits) > 1)
    if is_unlocked and is_download:
        target_visit = None
        if descarga_tipo == 'pdf':
            if target_vid is not None:
                pk = record_id(target_vid, 'h')
                target_visit = next((v for v in visits if v.pk == pk), None)
                if target_visit is None:
                    raise RecordSelectionError('Documento no incluido en este enlace.', 404)
            elif len(visits) == 1:
                target_visit = visits[0]
            else:
                raise RecordSelectionError('Seleccione el documento que desea descargar.')
        share.download_count += 1
        share.save(update_fields=['download_count'])

        try:
            ip_addr = getattr(request, 'client_ip', 'unknown')
            if ip_addr and ',' in ip_addr:
                ip_addr = ip_addr.split(',')[0].strip()
            register_audit_log(
                user=None,
                schema_name='clinical',
                table_name='clinical_secure_share',
                record_key=str(share.share_id),
                action='UPDATE',
                new_value={
                    'event': 'SECURE_SHARE_DOWNLOAD',
                    'descarga_tipo': descarga_tipo,
                    'target_vid': target_vid,
                    'recipient_email': share.recipient_email,
                    'download_count': share.download_count
                },
                machine_name=ip_addr
            )
        except AuditLogError:
            raise
        except Exception as audit_err:
            logger.warning(f"Error registrando descarga en auditoría: {audit_err}")

        if descarga_tipo == 'zip' or (descarga_tipo == 'todo' and len(visits) > 1):
            zip_bytes = _generate_zip_stream(visits)
            response = HttpResponse(zip_bytes, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="documentos_clinicos.zip"'
            response['Referrer-Policy'] = 'no-referrer'
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            return response

        elif descarga_tipo == 'pdf':
            pdf_bytes = generate_clinical_sheet_pdf(target_visit, is_blank=False)
            code_str = (target_visit.study_code or f"V{target_visit.visit_id}").replace('/', '-').replace(' ', '_')
            filename = f"Ficha_Clinica_{code_str}.pdf" if len(visits) > 1 else "documento.pdf"

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Referrer-Policy'] = 'no-referrer'
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['X-Content-Type-Options'] = 'nosniff'
            return response

    if request.method == 'POST':
        raw_code = request.POST.get('code', '').strip()

        if not raw_code or len(raw_code) != 6 or not raw_code.isdigit():
            share.attempts += 1
            if share.attempts >= share.max_attempts:
                share.is_revoked = True
                share.revoked_at = timezone.now()
            share.save(update_fields=['attempts', 'is_revoked', 'revoked_at'])
            error_msg = f"Ingrese un código de 6 dígitos numéricos. Le quedan {max(0, share.max_attempts - share.attempts)} intento(s)."
        elif not share.verify_code(raw_code):
            share.attempts += 1
            if share.attempts >= share.max_attempts:
                share.is_revoked = True
                share.revoked_at = timezone.now()
            share.save(update_fields=['attempts', 'is_revoked', 'revoked_at'])

            if share.is_revoked:
                resp = render(request, 'clinical/public_share_error.html', {
                    'error_title': 'Acceso bloqueado',
                    'error_message': 'Ha superado el número máximo de intentos fallidos permitidos. Por seguridad, este enlace ha sido inhabilitado.'
                }, status=404)
                resp['Referrer-Policy'] = 'no-referrer'
                resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                return resp
            else:
                error_msg = f"Código de acceso incorrecto. Le quedan {share.max_attempts - share.attempts} intento(s)."
        else:
            # CÓDIGO VÁLIDO: Marcar sesión desbloqueada y registrar
            request.session[f'share_unlocked_{share.share_id}'] = True
            is_unlocked = True

            try:
                ip_addr = getattr(request, 'client_ip', 'unknown')
                if ip_addr and ',' in ip_addr:
                    ip_addr = ip_addr.split(',')[0].strip()
                register_audit_log(
                    user=None,
                    schema_name='clinical',
                    table_name='clinical_secure_share',
                    record_key=str(share.share_id),
                    action='UPDATE',
                    new_value={
                        'event': 'SECURE_SHARE_UNLOCKED',
                        'recipient_email': share.recipient_email,
                        'total_fichas': len(visits)
                    },
                    machine_name=ip_addr
                )
            except AuditLogError:
                raise
            except Exception as audit_err:
                logger.warning(f"Error registrando desbloqueo en auditoría: {audit_err}")

            # Si el destinatario solicitó descarga directa en el POST
            if request.POST.get('descarga') == 'zip' and len(visits) > 1:
                share.download_count += 1
                share.save(update_fields=['download_count'])
                zip_bytes = _generate_zip_stream(visits)
                response = HttpResponse(zip_bytes, content_type='application/zip')
                response['Content-Disposition'] = 'attachment; filename="documentos_clinicos.zip"'
                response['Referrer-Policy'] = 'no-referrer'
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
                return response
            elif len(visits) == 1 and request.POST.get('direct_download') == '1':
                if target_vid is not None and record_id(target_vid, 'h') != visits[0].pk:
                    raise RecordSelectionError('Documento no incluido en este enlace.', 404)
                share.download_count += 1
                share.save(update_fields=['download_count'])
                pdf_bytes = generate_clinical_sheet_pdf(visits[0], is_blank=False)
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="documento.pdf"'
                response['Referrer-Policy'] = 'no-referrer'
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
                return response

    # Preparar datos de las visitas para renderizar la interfaz
    documentos = []
    for v in visits:
        code_str = v.study_code or f"V{v.visit_id}"
        patient_name = v.patient.full_name if v.patient else "Paciente"
        date_str = v.visit_date.strftime('%d/%m/%Y') if v.visit_date else 'Fecha no registrada'
        documentos.append({
            'visit_id': v.visit_id,
            'code': code_str,
            'patient_name': patient_name,
            'date': date_str,
            'download_url': f"?descarga=pdf&visit_id={v.visit_id}"
        })

    context = {
        'token': clean_token,
        'share': share,
        'is_unlocked': is_unlocked,
        'total_docs': len(visits),
        'documentos': documentos,
        'zip_download_url': "?descarga=zip",
        'single_pdf_url': f"?descarga=pdf&visit_id={visits[0].visit_id}" if visits else "?descarga=pdf",
        'attempts_left': max(0, share.max_attempts - share.attempts),
        'expires_display': share.expires_at.strftime('%d/%m/%Y a las %H:%M'),
        'error_msg': error_msg,
        'safe_note': share.note
    }
    resp = render(request, 'clinical/public_share.html', context)
    resp['Referrer-Policy'] = 'no-referrer'
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


# =============================================================================
# IMPORTACION INTELIGENTE DE ARCHIVOS SPSS (.SAV)
# =============================================================================

@login_required
@require_POST
@clinical_access_required('import', api=True)
def sav_import_analyze_api(request):
    """
    Recibe un archivo .sav / .zsav y realiza un diagnostico inteligente
    de variables, alertas y vista previa sin modificar la base de datos.
    """
    if 'file' not in request.FILES:
        return JsonResponse({"success": False, "error": "No se proporcionó ningún archivo para analizar."}, status=400)

    uploaded_file = request.FILES['file']
    filename = uploaded_file.name.lower()
    valid_exts = ('.sav', '.zsav', '.rds', '.rdata', '.rda', '.csv')
    if not any(filename.endswith(ext) for ext in valid_exts):
        return JsonResponse({"success": False, "error": "Formato de archivo inválido. Debe ser SPSS (.sav, .zsav) o RStudio (.rds, .RData, .rda, .csv)."}, status=400)

    analysis_result = analyze_sav_file(uploaded_file, uploaded_file.name, user=request.user)
    if not analysis_result.get('success'):
        return JsonResponse(analysis_result, status=400)

    return JsonResponse(analysis_result)


@login_required
@require_POST
@clinical_access_required('import', api=True)
def sav_import_execute_api(request):
    """
    Ejecuta transaccionalmente la importacion del archivo previamente analizado,
    creando pacientes, visitas, modulos clinicos y respuestas de encuestas.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST.dict()

        temp_token = data.get('temp_token', '')
        duplicate_action = data.get('duplicate_action', 'update').strip()
        if not isinstance(temp_token, str) or not temp_token or len(temp_token) > 2048:
            return JsonResponse({"success": False, "error": "Token de importación no válido o ausente."}, status=400)

        import_result = execute_sav_import(temp_token, request.user, duplicate_action=duplicate_action)
        if not import_result.get('success'):
            return JsonResponse(import_result, status=400)

        return JsonResponse(import_result)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Error al ejecutar la importación: {str(e)}"}, status=500)



@login_required
@require_POST
@clinical_access_required('delete', api=True)
@selection_errors
def ficha_eliminar_api(request):
    """
    Eliminacion segura y transaccional de Fichas Clinicas (individual o en lote).
    Exige la confirmacion de la contrasena del usuario autenticado para autorizar el borrado.
    Registra el evento en audit.change_log.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST.dict()

        password = (data.get('password') or '').strip()
        raw_ids = data.get('patient_ids') or data.get('ids')
        if not raw_ids:
            single_id = data.get('patient_id') or data.get('idPaciente') or data.get('paciente_id')
            if single_id:
                raw_ids = [single_id]

        # 1. Validar contrasena obligatoria
        if not password:
            return JsonResponse({
                "success": False,
                "error": "Debe ingresar su contraseña de usuario para autorizar la eliminación."
            }, status=400)

        # 2. Verificar contrasena del usuario en sesion
        if not request.user.check_password(password):
            return JsonResponse({
                "success": False,
                "error": "Contraseña incorrecta. Verificación de seguridad fallida."
            }, status=403)

        # 3. Validar identificadores
        if not raw_ids:
            return JsonResponse({
                "success": False,
                "error": "Seleccione al menos una ficha clínica para eliminar."
            }, status=400)

        patients_list = selected_patients(raw_ids)

        deleted_ids = []
        deleted_names = []
        ip_addr = getattr(request, 'client_ip', 'unknown')

        # 4. Transaccion atomica de eliminacion
        with transaction.atomic():
            for pat in patients_list:
                p_id = pat.patient_id
                p_name = pat.full_name
                v = getattr(pat, 'visit', None)
                s_code = v.study_code if v else str(p_id)

                if v:
                    v.delete()
                pat.delete()

                deleted_ids.append(p_id)
                deleted_names.append(p_name)

                register_audit_log(
                    user=request.user,
                    schema_name='clinical',
                    table_name='patient',
                    record_key=str(p_id),
                    action='DELETE',
                    old_value={'patient_name': p_name, 'study_code': s_code, 'batch': len(patients_list) > 1},
                    machine_name=ip_addr
                )

        if len(deleted_ids) == 1:
            msg = f"La ficha clínica de '{deleted_names[0]}' ha sido eliminada permanentemente."
        else:
            msg = f"Se eliminaron {len(deleted_ids)} fichas clínicas seleccionadas exitosamente."

        return JsonResponse({
            "success": True,
            "message": msg,
            "deleted_ids": deleted_ids,
            "deleted_count": len(deleted_ids)
        })

    except RecordSelectionError:
        raise
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"Error al procesar la eliminación: {str(e)}"
        }, status=500)


from .services.sav_exporter import generate_export_dataset


@login_required
@clinical_access_required('export', api=True)
@selection_errors
def export_dataset_api(request):
    """
    Exporta el dataset completo de pacientes y visitas a formato SPSS (.sav) o CSV
    con las 342 columnas completas idénticas a Base_datos_Unemi_CardioUnemi-ACTUALIZADO.sav.
    """
    try:
        if request.method == 'POST':
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST.dict()
        else:
            data = request.GET.dict()

        format_type = data.get('format', 'sav').strip().lower()
        patient_ids = data.get('patient_ids', [])
        if isinstance(patient_ids, str) and patient_ids.lstrip().startswith('['):
            patient_ids = json.loads(patient_ids)

        if data.get('scope') in ('all', 'todos'):
            if patient_ids not in ([], None, ''):
                raise RecordSelectionError('No combine alcance completo con IDs de pacientes.')
            patient_ids = None
        elif not patient_ids:
            raise RecordSelectionError('Indique pacientes o scope=all para exportar la cohorte activa.')

        file_bytes, filename, content_type = generate_export_dataset(
            patient_ids=patient_ids,
            format_type=format_type
        )

        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(file_bytes)
        return response

    except RecordSelectionError:
        raise
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Error al generar exportación: {str(e)}"}, status=500)
