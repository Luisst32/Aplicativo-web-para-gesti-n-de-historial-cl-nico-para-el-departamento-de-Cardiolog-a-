"""Exact primary-key selection; never interpret an ID as a study code or ID card."""
import re
from functools import wraps

from django.http import JsonResponse

from clinical.models import Patient, Visit


class RecordSelectionError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def selection_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except RecordSelectionError as exc:
            response = JsonResponse({'success': False, 'error': str(exc)}, status=exc.status)
            response['Cache-Control'] = 'no-store'
            return response
    return wrapped


def record_id(value, prefix='p'):
    if type(value) not in (str, int):
        raise RecordSelectionError('El identificador debe ser una clave primaria positiva.')
    value = str(value).strip()
    if not re.fullmatch(rf'(?:{prefix}_?)?[1-9][0-9]{{0,18}}', value):
        raise RecordSelectionError('Identificador inválido; use la clave primaria del registro.')
    result = int(value.removeprefix(prefix).removeprefix('_'))
    if result > 9223372036854775807:
        raise RecordSelectionError('Identificador fuera de rango.')
    return result


def patient_ids(values):
    if isinstance(values, str):
        values = values.split(',')
    if not isinstance(values, (list, tuple)) or not values:
        raise RecordSelectionError('Seleccione al menos un paciente por su clave primaria.')
    return list(dict.fromkeys(record_id(value) for value in values))


def selected_patients(values, *, active_only=False):
    ids = patient_ids(values)
    queryset = Patient.objects.filter(pk__in=ids)
    if active_only:
        queryset = queryset.filter(status=Patient.Status.ACTIVE)
    patients = {patient.pk: patient for patient in queryset}
    if len(patients) != len(ids):
        raise RecordSelectionError('No se encontraron todos los pacientes seleccionados.', 404)
    return [patients[pk] for pk in ids]


def selected_visits(values, *, active_only=False):
    patients = selected_patients(values, active_only=active_only)
    visits = {visit.patient_id: visit for visit in
              Visit.objects.filter(patient__in=patients).select_related('patient')}
    if len(visits) != len(patients):
        raise RecordSelectionError('No todos los pacientes seleccionados tienen ficha clínica.', 404)
    return [visits[patient.pk] for patient in patients]
