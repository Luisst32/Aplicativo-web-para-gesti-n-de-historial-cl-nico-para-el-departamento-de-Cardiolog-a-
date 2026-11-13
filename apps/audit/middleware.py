import ipaddress
import logging

from django.db import DatabaseError, connection, transaction
from django.http import JsonResponse

from .services import AuditLogError, audit_request_state

logger = logging.getLogger('apps.audit')


def audit_unavailable():
    response = JsonResponse(
        {'success': False, 'error': 'Auditoría no disponible. No se guardaron los cambios.'},
        status=503,
    )
    response['Cache-Control'] = 'no-store'
    return response


class PostgreSQLAuditMiddleware:
    """Keep PostgreSQL audit context and request writes in one transaction.

    Streaming iterators run after this transaction and must not write to the DB.
    This middleware does not install database audit triggers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        # Handle the typed failure before Django turns it into an unhandled 500.
        # The request failure flag still forces the outer transaction to roll back.
        if isinstance(exception, AuditLogError):
            return audit_unavailable()
        return None

    def __call__(self, request):
        # Record the network peer; arbitrary X-Forwarded-For is not proof of identity.
        try:
            request.client_ip = str(ipaddress.ip_address(request.META.get('REMOTE_ADDR', '')))
        except ValueError:
            request.client_ip = 'unknown'

        state = {'failed': False}
        token = audit_request_state.set(state)
        had_outer_transaction = connection.in_atomic_block
        try:
            with transaction.atomic():
                user = getattr(request, 'user', None)
                uid = str(user.pk) if user and user.is_authenticated else ''
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_user_id', true), "
                                   "current_setting('app.client_ip', true)")
                    previous = cursor.fetchone()
                    cursor.execute("SELECT set_config('app.current_user_id', %s, true), "
                                   "set_config('app.client_ip', %s, true)", [uid, request.client_ip])

                response = self.get_response(request)
                # Django may convert view exceptions to responses before they get here.
                if state['failed']:
                    transaction.set_rollback(True)
                    response = audit_unavailable()
                elif response.status_code >= 500 or connection.needs_rollback:
                    transaction.set_rollback(True)
                elif had_outer_transaction:
                    # SET LOCAL lasts until the outer commit if the caller already
                    # had a transaction. Restore that caller's original context too.
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT set_config('app.current_user_id', %s, true), "
                                       "set_config('app.client_ip', %s, true)",
                                       [previous[0] or '', previous[1] or ''])
                # In autocommit, leave the context in place until COMMIT so
                # deferred triggers can see it; PostgreSQL then resets SET LOCAL.
            return response
        except (DatabaseError, AuditLogError):
            logger.error('Audit transaction unavailable; request rolled back.')
            return audit_unavailable()
        finally:
            audit_request_state.reset(token)
