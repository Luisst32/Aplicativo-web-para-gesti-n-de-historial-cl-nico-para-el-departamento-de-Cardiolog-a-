"""Recorded questionnaire values, without inferred negatives or patient identity."""
import json
import math
import re
import unicodedata
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from django.db import models
from django.db.models import Prefetch

from clinical.models import Visit, VisitAnswer
from clinical.services.sav_importer import SPSS_QUESTION_ALIASES, normalize_var_name

SENSITIVE = {'first_names', 'last_name1', 'last_name2', 'id_card', 'email', 'phone',
             'created_by', 'evaluator', 'patient', 'created_at', 'birth_date'}
PRIVATE_FORM = {'f_nombre', 'f_apellido1', 'f_apellido2', 'f_cedula', 'f_correo',
                'f_telefono', 'f_direccion', 'f_fecha_nac', 'csrfmiddlewaretoken', 'idPaciente'}
SECTIONS = {
    'patient': 'Cuestionario sociodemográfico', 'visit': 'Datos del individuo y de la visita',
    'anthropometry': 'Exploración física', 'vital_signs': 'Exploración física',
    'electrocardiogram': 'Resultados del electrocardiograma',
    'echocardiogram': 'Resultados del ecocardiograma', 'laboratory': 'Análisis clínicos',
    'ordered_studies': 'Estudios prescritos',
}
LABELS = {
    'birth_country': 'País de nacimiento', 'foreign_birth_place': 'Lugar de nacimiento en el extranjero',
    'status': 'Estado del registro', 'study_year': 'Año de la visita',
    'heart_rate': 'Frecuencia cardíaca (lpm)', 'systolic_murmur': 'Soplo sistólico',
    'diastolic_murmur': 'Soplo diastólico', 'extra_heart_sounds': 'Extratonos cardíacos',
    'physical_findings_detail': 'Otros hallazgos de la exploración física',
    'repolarization_abnormalities': 'Alteraciones de la repolarización',
    'rv_dimension_mm': 'Diámetro del ventrículo derecho (mm)',
    'lv_dimension_mm': 'Diámetro del ventrículo izquierdo (mm)',
    'lvef_percentage': 'Fracción de eyección del ventrículo izquierdo (%)',
    'ventricular_hypertrophy': 'Hipertrofia ventricular',
    'diastolic_dysfunction': 'Disfunción diastólica',
    'aortic_valve_calcification': 'Calcificación de la válvula aórtica',
    'aortic_gradient_max_mmhg': 'Gradiente aórtico máximo (mmHg)',
    'aortic_gradient_mean_mmhg': 'Gradiente aórtico medio (mmHg)',
    'pr_interval_ms': 'Intervalo PR (ms)', 'qrs_duration_ms': 'Duración QRS (ms)',
    'qt_interval_ms': 'Intervalo QT (ms)', 'qtc_bazett_ms': 'QT corregido por Bazett (ms)',
    'rr_interval_sec': 'Intervalo RR (s)',
}
RELATIONS = ('patient__institution', 'patient__sex', 'patient__ethnicity',
             'patient__birth_canton', 'patient__birth_country', 'residence_canton',
             'staff_category', 'professional_category', 'education_level', 'income_range',
             'marital_status', 'living_situation', 'housing_type', 'work_schedule',
             'anthropometry', 'vital_signs', 'electrocardiogram__rhythm',
             'echocardiogram', 'laboratory', 'ordered_studies')


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('questionnaire_catalog.json').read_text(encoding='utf-8'))


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).lower()
                   if not unicodedata.combining(c)).strip()


def section_title(title):
    if title == 'Insuficiencia Pulmonar':
        return 'Ecocardiograma: insuficiencia pulmonar'
    if title in ('Pericardio', 'Resultados'):
        return 'Ecocardiograma: ' + title.lower()
    return title


def safe_value(value, descriptor):
    """Free text contributes coverage only; never ships in the dashboard JSON."""
    if value is None or str(value).strip() == '':
        return None
    if descriptor['kind'] == 'number':
        try:
            result = float(value)
            return result if math.isfinite(result) else None
        except (ValueError, TypeError):
            return None
    if isinstance(value, bool):
        return 'Sí' if value else 'No'
    options = descriptor.get('options', {})
    text = str(value).strip()
    for key, label in options.items():
        if folded(text) in (folded(key), folded(label)):
            return label
    if descriptor['kind'] == 'boolean':
        return {'si': 'Sí', 'true': 'Sí', '1': 'Sí', 'no': 'No', 'false': 'No', '0': 'No'}.get(folded(text))
    if descriptor['kind'] == 'category':
        return text if not options else None
    if descriptor['kind'] == 'date':
        return text
    return True  # recorded free text, contents withheld


def model_descriptor(prefix, field):
    source = catalog()
    form = source['fields'].get(source['bindings'].get(prefix + '.' + field.name), {})
    numeric = isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField))
    kind = 'boolean' if isinstance(field, models.BooleanField) else 'number' if numeric else 'date' if isinstance(field, models.DateField) else 'category' if field.is_relation or field.choices else 'text'
    if field.name in ('faculty', 'study_code'):
        kind = 'category'
    return {'id': 'db:' + prefix + '.' + field.name,
            'label': LABELS.get(field.name) or form.get('label') or str(field.verbose_name),
            'section': SECTIONS[prefix], 'kind': kind,
            'options': dict(field.flatchoices) if field.choices else {}}


def get_questionnaire_dashboard():
    source = catalog()
    fields = {}
    for code, spec in source['fields'].items():
        if code in PRIVATE_FORM:
            continue
        spec = dict(spec)
        spec['section'] = section_title(spec['section'])
        if spec['options'] and {folded(v) for v in spec['options']} <= {'si', 'no', '1', '0', 'true', 'false'}:
            spec.update(kind='boolean', options={})
        fields[code] = {'id': code, **spec}
    alias_groups = {}
    for key, value in SPSS_QUESTION_ALIASES.items():
        alias_groups.setdefault(normalize_var_name(value)[:30], []).append(key)
    # A shared legacy field must not silently overwrite unrelated questions.
    aliases = {key: targets[0] for key, targets in alias_groups.items() if len(targets) == 1}
    visits = Visit.objects.all().select_related(*RELATIONS).prefetch_related(
        Prefetch('answers', queryset=VisitAnswer.objects.select_related('question__section', 'selected_option', 'selected_option__question').prefetch_related('question__options')),
    ).order_by('visit_id')
    records = []
    for visit in visits:
        values = {}
        for prefix in SECTIONS:
            obj = visit.patient if prefix == 'patient' else visit if prefix == 'visit' else getattr(visit, prefix, None)
            if obj is None:
                continue
            for field in obj._meta.concrete_fields:
                if field.primary_key or field.name in SENSITIVE:
                    continue
                code = 'db:' + prefix + '.' + field.name
                descriptor = model_descriptor(prefix, field)
                fields.setdefault(code, descriptor)
                value = getattr(obj, field.name)
                if field.is_relation:
                    value = getattr(value, 'name', None) if value else None
                elif isinstance(value, (date, datetime)):
                    value = value.isoformat()
                values[code] = safe_value(value, descriptor)
        if visit.patient.birth_date and visit.visit_date:
            born, seen = visit.patient.birth_date, visit.visit_date
            age = seen.year - born.year - ((seen.month, seen.day) < (born.month, born.day))
            if age >= 0:
                values['f_edad'] = age
        # Exact stored answers take precedence among aliases for the same form field.
        answers = list(visit.answers.all())
        answers.sort(key=lambda a: a.question.code in source['fields'])
        for answer in answers:
            question = answer.question
            code = question.code
            if code in PRIVATE_FORM or re.search(r'nombre|apellido|cedula|correo|email|telefono|direccion', folded(code)):
                continue
            normalized = normalize_var_name(code)
            raw = answer.selected_option.label if answer.selected_option else answer.numeric_value if answer.numeric_value is not None else answer.text_value
            if normalized == 'historia_covid' and raw is not None:
                description = folded(raw)
                infected = safe_value(raw, {'kind': 'boolean'})
                admitted = None
                if 'no ha pasado' in description or 'no paso' in description:
                    infected = 'No'
                elif 'sin ingreso' in description or 'sin hospital' in description:
                    infected, admitted = 'Sí', 'No'
                elif 'con ingreso' in description or 'con hospital' in description:
                    infected, admitted = 'Sí', 'Sí'
                if infected is not None:
                    values.setdefault('covid_paso', infected)
                if admitted is not None:
                    values.setdefault('covid_ingreso', admitted)
            target = code if code in fields else aliases.get(normalized)
            if target not in fields:
                target = code
                fields.setdefault(target, {'id': target, 'label': question.text,
                    'section': section_title(question.section.name),
                    'kind': 'number' if question.response_type == 'NUMERICO' else 'boolean' if question.response_type == 'BOOLEANO' else 'category' if question.response_type == 'OPCION' else 'text',
                    'options': {str(opt.pk): opt.label for opt in question.options.all()}})
            value = answer.selected_option.label if answer.selected_option else answer.numeric_value if answer.numeric_value is not None else answer.text_value
            if value is not None and str(value).strip() != '':
                values[target] = safe_value(value, fields[target])
        records.append({'id': visit.pk, 'code': visit.study_code or '', 'institution': visit.patient.institution.name,
                        'year': visit.visit_date.year, 'sex': visit.patient.sex.name, 'values': values})
    # Include relational fields even if no row currently exists in that block.
    from clinical.models import Patient, Visit as VisitModel, Anthropometry, VitalSigns, Electrocardiogram, Echocardiogram, Laboratory, OrderedStudies
    for prefix, model in zip(SECTIONS, (Patient, VisitModel, Anthropometry, VitalSigns, Electrocardiogram, Echocardiogram, Laboratory, OrderedStudies)):
        for field in model._meta.concrete_fields:
            if field.primary_key or field.name in SENSITIVE:
                continue
            code = 'db:' + prefix + '.' + field.name
            if code not in fields:
                fields[code] = model_descriptor(prefix, field)
    return {'fields': list(fields.values()), 'records': records}
