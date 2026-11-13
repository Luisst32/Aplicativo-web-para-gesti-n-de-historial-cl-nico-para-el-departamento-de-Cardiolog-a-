"""Use deploy-only credentials for schema commands, never for the web process."""
import os
from pathlib import Path
import sys
from dotenv import dotenv_values


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('migrate', 'makemigrations'):
        raise RuntimeError('Only migration commands are accepted.')
    root = Path(__file__).resolve().parent.parent
    path = Path(os.environ.get('MIGRATION_ENV_FILE', '')).expanduser().resolve()
    if not path.is_file() or path == root or root in path.parents:
        raise RuntimeError('MIGRATION_ENV_FILE must name a protected file outside the application.')
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise RuntimeError('Migration credentials must not be readable by group or other users.')
    credentials = dotenv_values(path)
    if not credentials.get('DB_USER') or not credentials.get('DB_PASSWORD'):
        raise RuntimeError('Migration credentials require DB_USER and DB_PASSWORD.')
    # Do not print these values or load them in the web process.
    os.environ.update({key: value for key, value in credentials.items()
                       if key in ('DB_USER','DB_PASSWORD','DB_HOST','DB_PORT','DB_NAME') and value is not None})
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    sys.path.insert(0, str(root))
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', *sys.argv[1:]])


if __name__ == '__main__':
    main()
