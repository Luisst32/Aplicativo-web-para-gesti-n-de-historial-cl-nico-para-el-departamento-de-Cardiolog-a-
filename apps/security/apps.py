from django.apps import AppConfig


class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'security'
    verbose_name = 'Seguridad y Control de Acceso'

    def ready(self):
        from . import database_checks  # register deployment checks
