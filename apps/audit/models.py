from django.db import models


class ChangeLog(models.Model):
    """
    Transversal Audit Change Log (auditoria.RegistroCambio).
    Records row/column level mutations across system schemas.
    """
    change_log_id = models.BigAutoField(primary_key=True, db_column='change_log_id')
    timestamp = models.DateTimeField(auto_now_add=True, db_column='timestamp')
    schema_name = models.CharField(max_length=50, db_column='schema_name')
    table_name = models.CharField(max_length=100, db_column='table_name')
    record_key = models.CharField(max_length=100, db_column='record_key', help_text="Primary key identifier of modified row")
    action = models.CharField(max_length=10, db_column='action', help_text="INSERT, UPDATE, DELETE, I, U, D")
    column_name = models.CharField(max_length=100, blank=True, null=True, db_column='column_name')
    old_value = models.TextField(blank=True, null=True, db_column='old_value')
    new_value = models.TextField(blank=True, null=True, db_column='new_value')
    user = models.ForeignKey(
        'security.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='user_id',
        related_name='audit_change_logs',
        help_text="Authenticated user responsible for mutation"
    )
    db_login = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_column='db_login',
        help_text="Database session user / role"
    )
    machine_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_column='machine_name',
        help_text="Host machine or client IP address"
    )

    class Meta:
        db_table = 'audit"."change_log'
        ordering = ['-timestamp']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action__in=['INSERT', 'UPDATE', 'DELETE', 'I', 'U', 'D']),
                name='ck_change_log_action'
            )
        ]
        verbose_name = "Change Log"
        verbose_name_plural = "Change Logs"

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.schema_name}.{self.table_name} ({self.action}) ID: {self.record_key}"
