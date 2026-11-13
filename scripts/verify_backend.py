"""Check all app test modules with disposable data and no external services."""
import base64
import os
from pathlib import Path
import secrets
import sys
import tempfile
import uuid


def main():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    os.environ.update(
        DJANGO_SETTINGS_MODULE='config.settings', APP_ENV='test', DEBUG='False',
        ALLOWED_HOSTS='localhost,127.0.0.1,testserver', TRUST_PROXY_HEADERS='False',
        SECURE_HSTS_SECONDS='0', GEMINI_API_KEY='',
        SECRET_KEY=secrets.token_urlsafe(64),
        FIELD_ENCRYPTION_KEYS=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    )
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.test import override_settings

    labels = sorted(f'{p.parent.name}.{p.stem}' for p in (root / 'apps').glob('*/test*.py'))
    if not labels:
        raise RuntimeError('No test modules discovered; refusing verification.')
    settings.DATABASES['default'].setdefault('TEST', {})['NAME'] = 'test_cardio_release_' + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix='cardio-release-') as scratch:
        with override_settings(
            MEDIA_ROOT=Path(scratch) / 'media', IMPORT_TEMP_ROOT=Path(scratch) / 'imports',
            STATIC_ROOT=Path(scratch) / 'static',
            CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
            MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
        ):
            call_command('check')
            call_command('makemigrations', check=True, dry_run=True, interactive=False)
            print('Explicit test modules:', ', '.join(labels), flush=True)
            call_command('test', *labels, interactive=False, verbosity=2)


if __name__ == '__main__':
    main()
