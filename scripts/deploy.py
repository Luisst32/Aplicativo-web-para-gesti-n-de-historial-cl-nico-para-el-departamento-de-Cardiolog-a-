"""Fail-fast in-place EC2 deployment, after CI verification of this commit.

Failure stops later steps; completed changes are not automatically rolled back.
"""
import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def check_health(url):
    request = Request(url, headers={'User-Agent': 'CardioUNEMI-DeploymentHealthcheck/1.0', 'Cache-Control': 'no-cache'})
    with build_opener(NoRedirects).open(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError('Health check did not return HTTP 200.')


def deploy(repository, commit, healthcheck_url, *, run=None, healthcheck=check_health):
    parsed = urlsplit(healthcheck_url)
    # Validate the port before changing code/dependencies, not during the probe.
    parsed.port
    if (not re.fullmatch(r'[0-9a-f]{40}', commit) or parsed.scheme != 'https'
            or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('A full commit SHA and credential-free HTTPS healthcheck URL are required.')
    root = Path(repository).resolve()
    python = next((p for p in (root / 'venv/bin/python', root / 'env/bin/python') if p.is_file()), None)
    if python is None:
        raise RuntimeError('Application venv missing; refusing system Python.')
    if run is None:
        def run(command):
            return subprocess.run(command, cwd=root, check=True)

    run(['git', 'diff', '--exit-code'])
    run(['git', 'diff', '--cached', '--exit-code'])
    run(['git', 'fetch', 'origin', 'develop'])
    run(['git', 'merge-base', '--is-ancestor', commit, 'origin/develop'])
    run(['git', 'checkout', '--detach', commit])
    py = str(python)
    run([py, '-m', 'pip', 'install', '-r', 'requirements-bootstrap.txt'])
    run([py, '-m', 'pip', 'install', '-r', 'requirements.txt'])
    run([py, '-m', 'pip', 'check'])
    run([py, 'manage.py', 'shell', '--command',
         "import sys; from django.conf import settings; sys.exit(0 if settings.APP_ENV == 'production' and not settings.DEBUG else 'Production profile required')"])
    run([py, 'manage.py', 'check', '--deploy', '--fail-level', 'ERROR'])
    run([py, 'scripts/migration_manage.py', 'makemigrations', '--check', '--dry-run'])
    run([py, 'scripts/migration_manage.py', 'migrate', '--noinput'])
    run(['sudo', '-n', '-u', 'cardio_app', py, 'manage.py', 'rotate_encrypted_settings'])
    run([py, 'manage.py', 'collectstatic', '--noinput'])
    run(['sudo', '-n', 'systemctl', 'restart', 'django_app'])
    run(['systemctl', 'is-active', '--quiet', 'django_app'])
    healthcheck(healthcheck_url)
    print(f'Deployment verified: {commit}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--healthcheck-url', required=True)
    args = parser.parse_args()
    deploy(args.repository, args.commit, args.healthcheck_url)
