from django.db import migrations, models


def seed_institutional_roles(apps, schema_editor):
    Role = apps.get_model('security', 'Role')
    UserRole = apps.get_model('security', 'UserRole')
    Permission = apps.get_model('auth', 'Permission')

    admin_role, _ = Role.objects.get_or_create(
        name='Administrador',
        defaults={
            'description': 'Rol administrativo con acceso total y configuración exclusiva del sistema',
            'status': 'ACTIVE',
        },
    )
    cardiologo_role, _ = Role.objects.get_or_create(
        name='Cardiólogo',
        defaults={
            'description': 'Ver, crear, editar y eliminar fichas/pacientes y enviar por correo (sin importar, exportar ni Dashboard)',
            'status': 'ACTIVE',
        },
    )
    estadistica_role, _ = Role.objects.get_or_create(
        name='Departamento de Estadística',
        defaults={
            'description': 'Ver fichas en solo lectura, Dashboard, importar, exportar y enviar por correo (sin crear, editar ni eliminar fichas)',
            'status': 'ACTIVE',
        },
    )

    cardio_perms = Permission.objects.filter(
        content_type__app_label='clinical',
        codename__in=[
            'view_patient', 'view_visit',
            'add_patient', 'add_visit',
            'change_patient', 'change_visit',
            'delete_patient', 'delete_visit',
            'add_secureshare',
        ],
    )
    if cardio_perms.exists():
        cardiologo_role.permissions.set(cardio_perms)

    stats_perms = Permission.objects.filter(
        content_type__app_label='clinical',
        codename__in=[
            'view_patient', 'view_visit',
            'export_clinical_data',
            'import_clinical_data',
            'add_secureshare',
        ],
    )
    if stats_perms.exists():
        estadistica_role.permissions.set(stats_perms)

    # Migrar asignaciones heredadas de 'Médico Evaluador' al rol oficial 'Cardiólogo'
    legacy_roles = Role.objects.filter(name='Médico Evaluador')
    for legacy_ur in UserRole.objects.filter(role__in=legacy_roles, status='ACTIVE'):
        UserRole.objects.update_or_create(
            user_id=legacy_ur.user_id,
            role=cardiologo_role,
            defaults={'status': 'ACTIVE'},
        )
        legacy_ur.status = 'INACTIVE'
        legacy_ur.save(update_fields=['status'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0007_requestquota'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='role_mode_enabled',
            field=models.BooleanField(
                db_column='role_mode_enabled',
                default=True,
                help_text='Interruptor exclusivo de Administrador para aplicar restricciones por rol (Cardiólogo / Estadística) o permitir acceso clínico libre',
            ),
        ),
        migrations.RunPython(seed_institutional_roles, noop_reverse),
    ]
