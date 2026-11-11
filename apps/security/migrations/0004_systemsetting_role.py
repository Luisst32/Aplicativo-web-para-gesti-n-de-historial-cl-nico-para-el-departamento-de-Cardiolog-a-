import django.db.models.deletion
from django.db import migrations, models


def link_settings_and_admins_to_admin_role(apps, schema_editor):
    Role = apps.get_model('security', 'Role')
    User = apps.get_model('security', 'User')
    UserRole = apps.get_model('security', 'UserRole')
    SystemSetting = apps.get_model('security', 'SystemSetting')

    admin_role, _ = Role.objects.get_or_create(
        name='Administrador',
        defaults={
            'description': 'Rol administrativo con acceso exclusivo a credenciales de API y configuración del sistema',
            'status': 'ACTIVE',
        },
    )

    settings_qs = SystemSetting.objects.order_by('setting_id')
    first_setting = settings_qs.first()
    if first_setting:
        if first_setting.role_id is None:
            first_setting.role = admin_role
            first_setting.save(update_fields=['role'])
        # Eliminar duplicados residuales si existieran antes de aplicar la restricción 1:1
        settings_qs.exclude(pk=first_setting.pk).delete()

    for user in User.objects.filter(
        models.Q(is_superuser=True) | models.Q(is_staff=True) | models.Q(username='admin')
    ):
        UserRole.objects.get_or_create(
            user=user,
            role=admin_role,
            defaults={'status': 'ACTIVE'},
        )


def reverse_unlink(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0003_systemsetting'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='role',
            field=models.OneToOneField(
                blank=True,
                db_column='role_id',
                help_text='Rol exclusivo autorizado para administrar y utilizar la API Key del sistema',
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name='system_setting',
                to='security.role',
            ),
        ),
        migrations.RunPython(link_settings_and_admins_to_admin_role, reverse_unlink),
        migrations.AlterField(
            model_name='systemsetting',
            name='role',
            field=models.OneToOneField(
                db_column='role_id',
                help_text='Rol exclusivo autorizado para administrar y utilizar la API Key del sistema',
                on_delete=django.db.models.deletion.RESTRICT,
                related_name='system_setting',
                to='security.role',
            ),
        ),
    ]

