"""Three-state clinical answers; storage types and explicit encodings are preserved."""
import json
from pathlib import Path
from django.core.exceptions import ValidationError

FIELDS = json.loads(Path(__file__).with_name('yes_no_fields.json').read_text(encoding='utf-8'))
RADIO_FIELDS = frozenset(FIELDS['radios'])
CHECKBOX_FIELDS = frozenset(FIELDS['checkboxes'])
CHOICE_FIELDS = frozenset(FIELDS.get('choice_radios', []))


import re
import json
from pathlib import Path
from django.core.exceptions import ValidationError

FIELDS = json.loads(Path(__file__).with_name('yes_no_fields.json').read_text(encoding='utf-8'))
RADIO_FIELDS = frozenset(FIELDS['radios'])
CHECKBOX_FIELDS = frozenset(FIELDS['checkboxes'])
CHOICE_FIELDS = frozenset(FIELDS.get('choice_radios', []))


def nullable_bool(value):
    if value is None or str(value).strip() == '':
        return None
    text = str(value).strip().lower()
    if (
        text in ('no', 'false', '0', '0.0', 'negativo', 'sin', 'ninguno', 'ninguna')
        or re.match(r'^(no|false|0(\.0)?|ningun[oa]s?|sin)\b', text)
        or text.startswith((
            'no tiene', 'no presenta', 'no realiza', 'no consume',
            'no ha pasado', 'no presentó', 'no tuvo', 'no fuma', 'no bloqueo',
            'sin antecedentes', 'sin patología', 'sin ingreso', 'sin trastorno'
        ))
    ):
        return False
    if (
        text in ('si', 'sí', 'true', '1', '1.0', 'positivo')
        or re.match(r'^(s[ií]|true|1(\.0)?)\b', text, re.I)
        or text.startswith((
            'si ', 'sí ', 'si,', 'sí,', 'si em', 'si en', 'si realiza',
            'sí tiene', 'si tiene', 'sí pero', 'si pero', 'si tratada',
            'si, y si', 'sí, y sí', 'sí, con', 'si, con'
        ))
    ):
        return True
    raise ValidationError(f'Respuesta Sí/No inválida: {value}')


def yes_no(value, yes='Si', no='No'):
    return None if value is None else yes if value else no


def any_known(*values):
    if any(value is True for value in values):
        return True
    return False if all(value is False for value in values) else None
