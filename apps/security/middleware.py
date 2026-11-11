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
        if not request.user.is_authenticated:
            path = request.path
            login_url = reverse('security:login')
            logout_url = reverse('security:logout')

            exempt_prefixes = tuple(
                prefix for prefix in (settings.STATIC_URL, settings.MEDIA_URL) if prefix
            )

            if (
                path == login_url
                or path == logout_url
                or path == '/favicon.ico'
                or any(path.startswith(prefix) for prefix in exempt_prefixes)
            ):
                return self.get_response(request)

            # Rutas de restablecimiento de contraseña públicas para usuarios no autenticados
            try:
                match = resolve(path)
                if match.namespace == 'security' and match.url_name in (
                    'login',
                    'logout',
                    'password_reset_request',
                    'password_reset_confirm',
                ):
                    return self.get_response(request)
            except Resolver404:
                pass

            # Solo conservar ?next= si la ruta destino existe y es segura.
            try:
                resolve(path)
                if path not in ('/', login_url, logout_url):
                    return redirect_to_login(request.get_full_path(), login_url=login_url)
            except Resolver404:
                pass

            return redirect(login_url)

        return self.get_response(request)

