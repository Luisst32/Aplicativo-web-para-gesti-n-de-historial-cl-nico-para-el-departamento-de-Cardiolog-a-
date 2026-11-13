"""Shared PostgreSQL quotas; independent of forwarded headers and cache races."""
import hashlib
import hmac
import time
from django.conf import settings
from django.db import connection, DatabaseError
from django.http import JsonResponse


def consume(identity, limit, now=None):
    key = hmac.new(settings.SECRET_KEY.encode(), identity.encode(), hashlib.sha256).hexdigest()
    window = int(time.time() if now is None else now) // 60
    with connection.cursor() as cursor:
        cursor.execute('''INSERT INTO security.request_quota (key, "window", count) VALUES (%s,%s,1)
            ON CONFLICT (key) DO UPDATE SET "window"=EXCLUDED."window",
            count=CASE WHEN request_quota."window"=EXCLUDED."window" THEN request_quota.count+1 ELSE 1 END
            WHERE request_quota."window"<>EXCLUDED."window" OR request_quota.count<%s
            RETURNING count''', [key, window, limit])
        return cursor.fetchone() is not None


class RequestLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST':
            path = request.path
            peer = request.META.get('REMOTE_ADDR', 'unknown')
            quotas = []
            if path == '/chatbot/query/' and request.user.is_authenticated:
                quotas = [(f'chatbot:{request.user.pk}', 20)]
            elif path in ('/security/login/', '/admin/login/'):
                identifier = request.POST.get('email') or request.POST.get('username', '')
                quotas = [(f'login-peer:{peer}', 30), (f'login-account:{peer}:{identifier.strip().casefold()}', 5)]
            elif path.startswith(('/security/password-reset/', '/security/reset/')):
                quotas = [(f'reset:{peer}', 5)]
            try:
                for identity, limit in quotas:
                    if not consume(identity, limit):
                        response = JsonResponse({'status':'rate_limited', 'response':'L\u00edmite de consultas alcanzado. Espere un minuto.'}, status=429)
                        response['Retry-After'] = '60'
                        response['Cache-Control'] = 'no-store'
                        return response
            except DatabaseError:
                return JsonResponse({'status':'unavailable', 'response':'Servicio temporalmente no disponible.'}, status=503)
        return self.get_response(request)
