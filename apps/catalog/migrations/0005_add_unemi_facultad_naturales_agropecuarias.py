from django.db import migrations


FACULTY_NAME = 'Facultad de Ciencias Naturales y Agropecuarias'
FACULTY_CODE = 'FCNA'


def add_unemi_faculty(apps, schema_editor):
    Institution = apps.get_model('catalog', 'Institution')
    InstitutionFaculty = apps.get_model('catalog', 'InstitutionFaculty')

    unemi = Institution.objects.filter(acronym__iexact='UNEMI').first()
    if not unemi:
        return

    by_name = InstitutionFaculty.objects.filter(
        institution=unemi,
        name__iexact=FACULTY_NAME,
    ).first()
    if by_name:
        if by_name.status != 'ACTIVE':
            by_name.status = 'ACTIVE'
            by_name.save(update_fields=['status'])
        return

    by_code = InstitutionFaculty.objects.filter(
        institution=unemi,
        code__iexact=FACULTY_CODE,
    ).first()
    if by_code:
        if by_code.name != FACULTY_NAME:
            raise RuntimeError('El código FCNA ya pertenece a otra facultad de UNEMI.')
        if by_code.status != 'ACTIVE':
            by_code.status = 'ACTIVE'
            by_code.save(update_fields=['status'])
        return

    InstitutionFaculty.objects.create(
        institution=unemi,
        code=FACULTY_CODE,
        name=FACULTY_NAME,
        status='ACTIVE',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0004_institution_admin_catalog'),
    ]

    operations = [
        migrations.RunPython(add_unemi_faculty, migrations.RunPython.noop),
    ]
