from datetime import date
from django.db import migrations


def sanitize_birth_dates(apps, schema_editor):
    Patient = apps.get_model('clinical', 'Patient')
    Visit = apps.get_model('clinical', 'Visit')
    VisitAnswer = apps.get_model('clinical', 'VisitAnswer')

    # Identificar y corregir pacientes con años de nacimiento anómalos (< 1920 o > 2015)
    # derivados de erratas o corrupciones de época (ej. SPSS 1582 epoch o siglo 1775)
    anomalous = Patient.objects.filter(birth_date__isnull=False)
    for p in anomalous:
        if not p.birth_date:
            continue
        year = p.birth_date.year
        if 1920 <= year <= 2015:
            continue

        ans = VisitAnswer.objects.filter(
            visit__patient=p,
            question__code__in=['edad', 'f_edad'],
            numeric_value__isnull=False
        ).order_by('-numeric_value').first()

        visit = Visit.objects.filter(patient=p).order_by('-visit_date').first()
        visit_year = visit.visit_date.year if (visit and visit.visit_date) else 2026

        if ans and ans.numeric_value:
            edad_real = int(ans.numeric_value)
            nuevo_year = visit_year - edad_real
            try:
                nueva_fecha = date(nuevo_year, p.birth_date.month, p.birth_date.day)
            except ValueError:
                nueva_fecha = date(nuevo_year, p.birth_date.month, 28)
            p.birth_date = nueva_fecha
            p.save(update_fields=['birth_date'])


def reverse_sanitize(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0011_nullable_clinical_answers'),
    ]

    operations = [
        migrations.RunPython(sanitize_birth_dates, reverse_sanitize),
    ]
