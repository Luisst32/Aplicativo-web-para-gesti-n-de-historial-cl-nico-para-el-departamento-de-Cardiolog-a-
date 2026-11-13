from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse


class RequireLoginMiddleware:
    """
    Exige autenticación global en toda la aplicación.
    Cualquier petición de un usuario no autenticado hacia cualquier enlace
    (existente o inexistente) se redirige al login institucional.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.MEDIA_URL and request.path.startswith(settings.MEDIA_URL):
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound()
        if not request.user.is_authenticated:
            path = request.path
            login_url = reverse('security:login')
            logout_url = reverse('security:logout')

            exempt_prefixes = tuple(
                prefix for prefix in (settings.STATIC_URL,) if prefix
            )

            if (
                path == login_url
                or path == logout_url
                or path == '/favicon.ico'
                or any(path.startswith(prefix) for prefix in exempt_prefixes)
            ):
                return self.get_response(request)

            # Rutas públicas para usuarios no autenticados (reset de contraseña y portal de enlace seguro de ficha)
            try:
                match = resolve(path)
                if match.namespace == 'security' and match.url_name in (
                    'login',
                    'logout',
                    'password_reset_request',
                    'password_reset_confirm',
                ):
                    return self.get_response(request)
                if match.namespace == 'clinical' and match.url_name == 'public_secure_share':
                    return self.get_response(request)
            except Resolver404:
                pass

            # Para peticiones asíncronas / API / JSON (ej. fetch desde el frontend),
            # retornar 401 JSON en lugar de redirección 302 que rompería el parser JSON del cliente.
            if (
                request.content_type == 'application/json'
                or request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or path.startswith('/chatbot/query')
                or '/api/' in path
            ):
                from django.http import JsonResponse
                return JsonResponse({
                    'status': 'unauthorized',
                    'message': 'No autenticado. Por favor inicie sesión.',
                    'response': '🔒 Debe iniciar sesión para acceder al sistema.'
                }, status=401)

            # Solo conservar ?next= si la ruta destino existe y es segura.
            try:
                resolve(path)
                if path not in ('/', login_url, logout_url):
                    return redirect_to_login(request.get_full_path(), login_url=login_url)
            except Resolver404:
                pass

            return redirect(login_url)

        return self.get_response(request)

