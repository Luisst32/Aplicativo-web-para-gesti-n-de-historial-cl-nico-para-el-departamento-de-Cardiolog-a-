import json
import logging
from contextvars import ContextVar
from django.db import connection, transaction
from .models import ChangeLog

logger = logging.getLogger('apps.audit')

audit_request_state = ContextVar('audit_request_state', default=None)


class AuditLogError(RuntimeError):
    """An audited operation cannot succeed without its audit entry."""


def register_audit_log(
    user,
    table_name,
    record_key,
    action,
    schema_name='clinical',
    column_name=None,
    old_value=None,
    new_value=None,
    machine_name='127.0.0.1',
    status=ChangeLog.Status.RECORDED
):
    """
    Registers an audit change log entry in audit.change_log.
    """
    try:
        # Convert dict or complex types to JSON string if needed
        if isinstance(old_value, (dict, list)):
            old_value = json.dumps(old_value, default=str)
        if isinstance(new_value, (dict, list)):
            new_value = json.dumps(new_value, default=str)

        # Handle the error outside the failed SQL savepoint.
        with transaction.atomic():
            log_entry = ChangeLog.objects.create(
                schema_name=schema_name,
                table_name=table_name,
                record_key=str(record_key),
                action=action.upper(),
                column_name=column_name,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                user=user if (user and getattr(user, 'is_authenticated', False)) else None,
                db_login=getattr(user, 'username', 'system'),
                machine_name=machine_name or '127.0.0.1',
                status=status
            )
        return log_entry
    except Exception:
        state = audit_request_state.get()
        if state is not None:
            state['failed'] = True
        if connection.in_atomic_block:
            transaction.set_rollback(True)
        # SQL exceptions may contain patient values; do not copy them to logs.
        logger.error('Audit log write failed; operation must roll back.')
        raise AuditLogError('No se pudo registrar la auditoría de la operación.') from None
