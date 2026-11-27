from django.db import migrations


FACULTY_CODE = 'FCNA'
FACULTY_NAME = 'FCNA - Facultad de Ciencias Naturales y Agropecuarias'


def prefix_unemi_faculty(apps, schema_editor):
    Institution = apps.get_model('catalog', 'Institution')
    InstitutionFaculty = apps.get_model('catalog', 'InstitutionFaculty')

    unemi = Institution.objects.filter(acronym__iexact='UNEMI').first()
    if not unemi:
        return

    faculty = InstitutionFaculty.objects.filter(
        institution=unemi,
        code__iexact=FACULTY_CODE,
    ).first()
    if not faculty or faculty.name == FACULTY_NAME:
        return

    faculty.name = FACULTY_NAME
    faculty.save(update_fields=['name'])


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0005_add_unemi_facultad_naturales_agropecuarias'),
    ]

    operations = [
        migrations.RunPython(prefix_unemi_faculty, migrations.RunPython.noop),
    ]
