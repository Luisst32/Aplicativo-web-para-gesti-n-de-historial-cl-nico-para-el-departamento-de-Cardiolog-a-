from django.contrib import admin
from .models import ChangeLog


@admin.register(ChangeLog)
class ChangeLogAdmin(admin.ModelAdmin):
    list_display = (
        'change_log_id',
        'timestamp',
        'schema_name',
        'table_name',
        'record_key',
        'action',
        'status',
        'is_flagged',
        'column_name',
        'user',
        'db_login',
    )
    list_filter = ('status', 'is_flagged', 'action', 'schema_name', 'table_name', 'timestamp')
    search_fields = (
        'record_key',
        'table_name',
        'column_name',
        'old_value',
        'new_value',
        'db_login',
    )
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
