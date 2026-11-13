"""Patch semantics for measured values: omitted fields never supply defaults."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from clinical.models import Anthropometry, VitalSigns


@transaction.atomic
def save_measurements(visit, data):
    result = []
    for model, mapping in (
        (Anthropometry, {'f_peso':'weight_kg', 'f_talla':'height_cm', 'f_perimetro':'waist_circumference_cm'}),
        (VitalSigns, {'f_tas':'systolic_bp', 'f_tsi':'diastolic_bp', 'f_tad':'diastolic_bp', 'f_sat_o2':'oxygen_saturation', 'f_fc':'heart_rate'}),
    ):
        obj = model.objects.filter(visit=visit).first()
        values = {}
        for key, field in mapping.items():
            if key not in data:
                continue
            value = data[key]
            if obj is None and value in ('', None):
                continue
            if value in ('', None):
                if not model._meta.get_field(field).null:
                    raise ValidationError('Una medida obligatoria no puede quedar vacia: ' + key)
                values[field] = None
            else:
                try:
                    number = Decimal(str(value))
                    if not number.is_finite():
                        raise ValueError
                    if model._meta.get_field(field).get_internal_type() == 'SmallIntegerField' and number != number.to_integral_value():
                        raise ValueError
                    values[field] = number
                except Exception:
                    raise ValidationError('Medida numerica invalida: ' + key)
        if model is VitalSigns:
            if 'soplos' in data:
                values['systolic_murmur'] = data['soplos'] in ('1','Si','sistolico')
                values['diastolic_murmur'] = data['soplos'] in ('2','diastolico')
            for key, field, negative in (
                ('resp_norm','pulmonary_auscultation_normal','No'),
                ('abdom_norm','abdominal_auscultation_normal','No'),
                ('pulsos_sim','pedal_pulses_symmetric','No'),
            ):
                if key in data and data[key] not in ('',None):
                    values[field] = data[key] != negative
            for key, field, truth in (
                ('f_soplo_sistolico','systolic_murmur','Si'),
                ('f_soplo_diastolico','diastolic_murmur','Si'),
                ('f_auscultacion_pulmonar','pulmonary_auscultation_normal','Normal'),
                ('f_auscultacion_abdominal','abdominal_auscultation_normal','Normal'),
                ('f_pulsos_pedios','pedal_pulses_symmetric','Si'),
            ):
                if key in data and data[key] not in ('',None):
                    values[field] = data[key] == truth
            tiene_soplos = values.get('systolic_murmur') or values.get('diastolic_murmur') or (data.get('soplos') in ('1', 'Si', 'si', 'sistolico', 'diastolico'))
            for key in ('soplo_grado','f_grado_soplo'):
                if key in data:
                    raw_val = data[key]
                    if raw_val in ('', None, 'No tiene soplo', 'No', 'no', 'none', 'None', 'ninguno', '0', 'N/A'):
                        value = None
                    elif not tiene_soplos:
                        value = None
                    else:
                        try:
                            import re
                            match = re.search(r'([1-6])', str(raw_val))
                            if match:
                                value = int(match.group(1))
                            else:
                                romans = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6}
                                value = romans.get(str(raw_val).strip().lower())
                                if value is None:
                                    raise ValidationError('Grado de soplo invalido.')
                        except (TypeError, ValueError):
                            raise ValidationError('Grado de soplo invalido.')
                        if value is not None and not 1 <= value <= 6:
                            raise ValidationError('Grado de soplo fuera de rango.')
                    values['murmur_grade'] = value
        if values:
            if obj is None:
                required = [f.name for f in model._meta.fields if not f.null and not f.has_default()
                            and not f.primary_key and not getattr(f,'generated',False)]
                if any(field not in values for field in required):
                    raise ValidationError('Complete las medidas obligatorias antes de crear la evaluacion.')
                obj = model(visit=visit, **values)
            else:
                for field, value in values.items():
                    setattr(obj, field, value)
            obj.save()
        result.append(obj)
    return tuple(result)
