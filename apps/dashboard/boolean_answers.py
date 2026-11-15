"""Recorded three-state answers for every binary patient form control."""
from django.core.exceptions import ValidationError
from clinical.services.yes_no import RADIO_FIELDS, CHECKBOX_FIELDS, nullable_bool, any_known
from clinical.services.sav_importer import SPSS_QUESTION_ALIASES
from .questionnaire import catalog
from clinical.services.covid_answers import resolve_covid


def descriptors():
    source = catalog()['fields']
    return [{'id': key, 'label': source.get(key, {}).get('label', key),
             'section': source.get(key, {}).get('section', 'Cuestionario')}
            for key in sorted(RADIO_FIELDS | CHECKBOX_FIELDS)]


def recorded_answers(visit):
    values = {}
    for answer in visit.answers.all():
        values[answer.question.code] = (answer.selected_option.label if answer.selected_option_id
            else answer.numeric_value if answer.numeric_value is not None else answer.text_value)
    bindings = dict(catalog()['bindings'])
    bindings['vital_signs.pedal_pulses_symmetric'] = 'pulsos_sim'
    bindings['vital_signs.extra_heart_sounds'] = 'extratonos'
    bindings['electrocardiogram.repolarization_abnormalities'] = 'ecg_alt_repolarizacion'
    result = dict.fromkeys(RADIO_FIELDS | CHECKBOX_FIELDS)
    for path, key in bindings.items():
        if key not in result or key == 'soplos':
            continue
        relation, field = path.split('.')
        obj = getattr(visit, relation, None)
        value = getattr(obj, field, None)
        if value is True or value is False:
            result[key] = value
    vs = getattr(visit, 'vital_signs', None)
    if vs:
        result['soplos'] = any_known(vs.systolic_murmur, vs.diastolic_murmur)
    for key in result:
        alias = SPSS_QUESTION_ALIASES.get(key)
        source = key if key in values else alias if alias in values else None
        if source is not None:
            try:
                result[key] = nullable_bool(values[source])
            except ValidationError:
                result[key] = None
    covid = resolve_covid(values)
    for form, metric in [('covid_paso','covid_infeccion'), ('covid_ingreso','covid_hospitalizacion'), ('covid_cv','covid_secuelas_cardio'), ('covid_pulm','covid_secuelas_resp'), ('longcovid','covid_fatiga_long')]:
        result[form] = covid[metric]
    return result
