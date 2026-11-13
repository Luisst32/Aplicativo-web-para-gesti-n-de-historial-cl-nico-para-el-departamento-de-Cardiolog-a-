from unittest.mock import patch
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie

from config.http_security import read_http_security


@ensure_csrf_cookie
def synthetic_form(request):
    request.session['synthetic'] = True
    return HttpResponse('Synthetic form')


urlpatterns = [path('form/', synthetic_form)]


class HttpSecurityConfigurationTests(SimpleTestCase):
    def production(self, **extra):
        return read_http_security({'ALLOWED_HOSTS': 'clinic.example', **extra})

    def test_production_is_the_default_with_secure_flags(self):
        cfg = self.production()
        for name in ('SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', 'SESSION_COOKIE_HTTPONLY'):
            self.assertTrue(cfg[name])
        self.assertFalse(cfg['DEBUG'])
        self.assertEqual(cfg['SECURE_HSTS_SECONDS'], 3600)
        self.assertFalse(cfg['SECURE_HSTS_INCLUDE_SUBDOMAINS'])
        self.assertFalse(cfg['SECURE_HSTS_PRELOAD'])
        self.assertIsNone(cfg['SECURE_PROXY_SSL_HEADER'])

    def test_production_requires_hosts_and_rejects_debug_or_wildcard(self):
        for env in ({}, {'ALLOWED_HOSTS': '*'}, {'ALLOWED_HOSTS': 'clinic.example', 'DEBUG': 'True'}):
            with self.subTest(env=env), self.assertRaises(ImproperlyConfigured):
                read_http_security(env)

    def test_unknown_environment_or_invalid_boolean_fails_closed(self):
        for env in ({'APP_ENV': 'prod'}, {'TRUST_PROXY_HEADERS': 'sometimes'}):
            with self.subTest(env=env), self.assertRaises(ImproperlyConfigured):
                self.production(**env)

    def test_host_release_mode_cannot_enable_debug(self):
        self.assertFalse(self.production(DEBUG='release')['DEBUG'])

    def test_production_origins_require_exact_https_origins(self):
        for origin in ('http://clinic.example', 'https://*.example', 'https://clinic.example/path',
                       'https://user:password@clinic.example', 'https://clinic.example?x=1'):
            with self.subTest(origin=origin), self.assertRaises(ImproperlyConfigured):
                self.production(CSRF_TRUSTED_ORIGINS=origin)
        self.assertEqual(self.production(CSRF_TRUSTED_ORIGINS='https://clinic.example')['CSRF_TRUSTED_ORIGINS'],
                         ['https://clinic.example'])

    def test_invalid_or_disabled_hsts_is_rejected_for_production(self):
        for seconds in ('0', '-1', '60', 'invalid'):
            with self.subTest(seconds=seconds), self.assertRaises(ImproperlyConfigured):
                self.production(SECURE_HSTS_SECONDS=seconds)

    def test_development_allows_local_http_without_secure_cookies(self):
        cfg = read_http_security({'APP_ENV': 'development', 'DEBUG': 'true'})
        self.assertTrue(cfg['DEBUG'])
        self.assertFalse(cfg['SECURE_SSL_REDIRECT'])
        self.assertFalse(cfg['SESSION_COOKIE_SECURE'])
        self.assertFalse(cfg['CSRF_COOKIE_SECURE'])
        self.assertEqual(cfg['SECURE_HSTS_SECONDS'], 0)
        self.assertIn('localhost', cfg['ALLOWED_HOSTS'])

    def test_production_removes_the_four_original_http_security_warnings(self):
        with patch('security.database_checks.connection') as database, override_settings(**self.production()):
            database.cursor.return_value.__enter__.return_value.fetchone.return_value = (False,)
            warnings = run_checks(tags=['security'], include_deployment_checks=True)
        self.assertFalse({'security.W004', 'security.W008', 'security.W012', 'security.W016'} & {w.id for w in warnings})


@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=[
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ],
    SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
)
class HttpSecurityRequestTests(SimpleTestCase):
    def setUp(self):
        self.policy = read_http_security({'ALLOWED_HOSTS': 'testserver'})
        self.enterContext(override_settings(**self.policy))
        self.client = Client(enforce_csrf_checks=True)

    def test_http_redirects_to_https_with_query_preserved(self):
        response = self.client.get('/form/?page=2')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://testserver/form/?page=2')

    def test_https_sets_hsts_and_browser_security_headers(self):
        response = self.client.get('/form/', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=3600')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    def test_session_and_csrf_cookies_preserve_fetch_compatibility(self):
        response = self.client.get('/form/', secure=True)
        session = response.cookies['sessionid']
        csrf = response.cookies['csrftoken']
        self.assertTrue(session['secure'])
        self.assertTrue(session['httponly'])
        self.assertEqual(session['samesite'], 'Lax')
        self.assertTrue(csrf['secure'])
        self.assertFalse(csrf['httponly'])
        self.assertEqual(csrf['samesite'], 'Lax')

    def test_csrf_token_and_https_origin_are_enforced(self):
        self.assertEqual(self.client.post('/form/', secure=True).status_code, 403)
        response = self.client.get('/form/', secure=True)
        token = response.cookies['csrftoken'].value
        self.assertEqual(self.client.post('/form/', secure=True, HTTP_X_CSRFTOKEN=token,
                                         HTTP_ORIGIN='https://testserver').status_code, 200)
        self.assertEqual(self.client.post('/form/', secure=True, HTTP_X_CSRFTOKEN=token,
                                         HTTP_ORIGIN='https://attacker.invalid').status_code, 403)

    def test_untrusted_forwarded_proto_cannot_skip_redirect(self):
        self.assertEqual(self.client.get('/form/', HTTP_X_FORWARDED_PROTO='https').status_code, 301)

    def test_explicit_trusted_proxy_avoids_https_redirect_loop(self):
        cfg = read_http_security({'ALLOWED_HOSTS': 'testserver', 'TRUST_PROXY_HEADERS': 'true'})
        with override_settings(**cfg):
            response = self.client.get('/form/', HTTP_X_FORWARDED_PROTO='https')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Strict-Transport-Security'], 'max-age=3600')
            self.assertEqual(self.client.get('/form/', HTTP_X_FORWARDED_PROTO='http').status_code, 301)

    def test_development_http_stays_operational(self):
        with override_settings(**read_http_security({'APP_ENV': 'development'})):
            response = self.client.get('/form/')
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('Strict-Transport-Security', response)
            self.assertFalse(response.cookies['csrftoken']['secure'])
