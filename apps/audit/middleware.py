import logging
from django.db import connection

logger = logging.getLogger('apps.audit')


class PostgreSQLAuditMiddleware:
    """
    Audit Middleware for CARDIOUNEMI.
    Injects SET LOCAL session variables into PostgreSQL:
      - app.current_user_id: Authenticated user primary key
      - app.client_ip: Client IP address
    Allows database-level triggers and application-level logging to record
    exact user context for every transaction (Sprint 4 / HU-14).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract Client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        request.client_ip = client_ip

        # Inject session variables into connection cursor if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                with connection.cursor() as cursor:
                    # Sanitize user_id as integer
                    uid = int(request.user.user_id)
                    cursor.execute(f"SET LOCAL app.current_user_id = '{uid}';")
                    clean_ip = client_ip.replace("'", "")
                    cursor.execute(f"SET LOCAL app.client_ip = '{clean_ip}';")
            except Exception as e:
                logger.debug(f"Audit SET LOCAL notice: {e}")

        response = self.get_response(request)
        return response
