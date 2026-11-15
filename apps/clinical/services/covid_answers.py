"""Independent COVID answers; infection never supplies a hospital response."""
import unicodedata
from django.core.exceptions import ValidationError
from .yes_no import nullable_bool, any_known


def resolve_covid(answers):
    def fold(value):
        return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').lower())
                       if not unicodedata.combining(c)).strip()

    history = fold(answers.get('historia_covid'))
    infected = hospital = None
    if 'no ha pasado' in history or 'no paso' in history:
        infected = False
    elif 'sin ingreso' in history or 'sin hospital' in history:
        infected, hospital = True, False
    elif 'con ingreso' in history or 'con hospital' in history:
        infected, hospital = True, True
    elif 'no especifica' in history:
        infected, hospital = True, None
    else:
        try:
            infected = nullable_bool(history)
        except ValidationError:
            pass

    def parse_hospital(val):
        if val is None or str(val).strip() == '':
            return None
        f = fold(val)
        if 'sin ingreso' in f or 'sin hospital' in f:
            return False
        if 'con ingreso' in f or 'con hospital' in f:
            return True
        if 'no ha pasado' in f or 'no paso' in f or 'no especifica' in f:
            return None
        try:
            return nullable_bool(val)
        except ValidationError:
            return None

    def explicit(*codes, fallback=None):
        for code in codes:
            if code in answers:
                try:
                    return nullable_bool(answers[code])
                except ValidationError:
                    return None
        return fallback

    infected = explicit('covid_paso', 'covid_infeccion', fallback=infected)

    has_explicit_hospital = False
    explicit_hospital = None
    for code in ('covid_ingreso', 'covid_hospitalizacion'):
        if code in answers:
            has_explicit_hospital = True
            val = answers[code]
            if val is None or str(val).strip() == '':
                explicit_hospital = None
            else:
                explicit_hospital = parse_hospital(val)
            break

    if has_explicit_hospital:
        hospital = explicit_hospital
    cardio = explicit('covid_cv', 'covid_secuelas_cardio')
    respiratory = explicit('covid_pulm', 'covid_secuelas_resp')
    long = explicit('longcovid', 'long_covid')
    fog = explicit('covid_niebla')
    return {
        'covid_infeccion': infected, 'covid_hospitalizacion': hospital,
        'covid_secuelas_cardio': cardio, 'covid_secuelas_resp': respiratory,
        'covid_fatiga_long': long, 'covid_niebla_mental': fog,
        'covid_tiene_secuelas': any_known(cardio, respiratory, long, fog),
    }
