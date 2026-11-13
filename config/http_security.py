"""Explicit local/production HTTP policy; no secret values are handled here."""
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def _boolean(environ, name, default=False):
    raw = environ.get(name, str(default)).strip().lower()
    if raw not in {'true', 'false', '1', '0'}:
        raise ImproperlyConfigured(f'{name} debe ser true/false o 1/0.')
    return raw in {'true', '1'}


def read_http_security(environ):
    environment = environ.get('APP_ENV', 'production').strip().lower()
    if environment not in {'development', 'test', 'production'}:
        raise ImproperlyConfigured('APP_ENV debe ser development, test o production.')
    production = environment == 'production'
    # Host tooling may set DEBUG=release. Only an explicit true/1 enables it.
    debug = environ.get('DEBUG', 'false').strip().lower() in {'true', '1'}
    if production and debug:
        raise ImproperlyConfigured('DEBUG no puede estar habilitado en production.')
    hosts = [item.strip() for item in environ.get(
        'ALLOWED_HOSTS', '' if production else 'localhost,127.0.0.1,testserver',
    ).split(',') if item.strip()]
    if production and (not hosts or '*' in hosts):
        raise ImproperlyConfigured('Production requiere ALLOWED_HOSTS explícitos sin *.')

    origins = [item.strip() for item in environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if item.strip()]
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in ({'https'} if production else {'http', 'https'})
                or not parsed.hostname or '*' in origin or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS contiene un origen inválido.')

    try:
        hsts = int(environ.get('SECURE_HSTS_SECONDS', '3600' if production else '0'))
    except ValueError:
        raise ImproperlyConfigured('SECURE_HSTS_SECONDS debe ser un entero.') from None
    if hsts < 0 or (production and hsts < 3600):
        raise ImproperlyConfigured('Production requiere SECURE_HSTS_SECONDS de al menos 3600.')

    trust_proxy = _boolean(environ, 'TRUST_PROXY_HEADERS')
    return {
        'APP_ENV': environment,
        'DEBUG': debug,
        'ALLOWED_HOSTS': hosts,
        'CSRF_TRUSTED_ORIGINS': origins,
        'SECURE_SSL_REDIRECT': production,
        'SESSION_COOKIE_SECURE': production,
        'CSRF_COOKIE_SECURE': production,
        'SESSION_COOKIE_HTTPONLY': True,
        # The existing fetch clients read csrftoken to send X-CSRFToken.
        'CSRF_COOKIE_HTTPONLY': False,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'CSRF_COOKIE_SAMESITE': 'Lax',
        'SECURE_HSTS_SECONDS': hsts,
        'SECURE_HSTS_INCLUDE_SUBDOMAINS': False,
        'SECURE_HSTS_PRELOAD': False,
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https') if trust_proxy else None,
        'USE_X_FORWARDED_HOST': False,
        'SECURE_CONTENT_TYPE_NOSNIFF': True,
        'SECURE_REFERRER_POLICY': 'same-origin',
        'X_FRAME_OPTIONS': 'DENY',
    }
