from django.db import models
from django.conf import settings


class RegistroCambio(models.Model):
    """
    Bitácora de auditoría transversal que registra inserciones, actualizaciones y eliminaciones.
    Alimentada principalmente por triggers en base de datos.
    Mapeado a auditoria.RegistroCambio.
    """
    ACCION_CHOICES = [
        ('INSERT', 'Inserción'),
        ('UPDATE', 'Actualización'),
        ('DELETE', 'Eliminación'),
    ]

    registro_cambio_id = models.BigAutoField(primary_key=True, db_column='registrocambioid')
    fecha_utc = models.DateTimeField(auto_now_add=True, db_column='fechautc')
    esquema_nombre = models.CharField(max_length=50, db_column='esquemanombre')
    tabla_nombre = models.CharField(max_length=100, db_column='tablanombre')
    clave_registro = models.CharField(max_length=100, db_column='claveregistro')
    accion = models.CharField(max_length=10, choices=ACCION_CHOICES, db_column='accion')
    columna_nombre = models.CharField(max_length=100, blank=True, null=True, db_column='columnanombre')
    valor_anterior = models.TextField(blank=True, null=True, db_column='valoranterior')
    valor_nuevo = models.TextField(blank=True, null=True, db_column='valornuevo')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='usuarioid')
    login_db = models.CharField(max_length=100, blank=True, null=True, db_column='loginsqlserver')
    nombre_maquina = models.CharField(max_length=100, blank=True, null=True, db_column='nombremaquina')

    class Meta:
        db_table = '"auditoria"."registrocambio"'
        verbose_name = "Registro de Cambio"
        verbose_name_plural = "Registros de Cambios"
        ordering = ['-fecha_utc']

    def __str__(self):
        return f"[{self.accion}] {self.esquema_nombre}.{self.tabla_nombre} #{self.clave_registro} ({self.fecha_utc})"
