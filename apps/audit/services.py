import json
import logging
from .models import ChangeLog

logger = logging.getLogger('apps.audit')


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
    except Exception as e:
        logger.warning(f"Error registering audit log: {e}")
        return None
