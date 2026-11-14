"""Private, owner-bound, expiring and single-use dataset upload tickets."""
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured

SALT = 'clinical.dataset-import.v1'
MAX_AGE = 3600
EXTENSIONS = {'.sav', '.zsav', '.csv', '.rds', '.rdata', '.rda', '.r'}
ERROR_MESSAGE = 'Importación inválida, ajena, caducada o ya utilizada. Suba el archivo nuevamente.'


class InvalidImportTicket(ValueError):
    pass


def private_root():
    root = Path(getattr(settings, 'IMPORT_TEMP_ROOT', Path(settings.BASE_DIR) / '.private_imports')).resolve()
    media = Path(settings.MEDIA_ROOT).resolve()
    if root == media or media in root.parents:
        raise ImproperlyConfigured('IMPORT_TEMP_ROOT debe estar fuera de MEDIA_ROOT.')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def store_upload(file_obj, filename, user):
    extension = Path(filename).suffix.lower()
    if extension not in EXTENSIONS:
        raise InvalidImportTicket(ERROR_MESSAGE)
    payload = {'id': uuid.uuid4().hex, 'ext': extension, 'owner': user.pk}
    path = private_root() / (payload['id'] + extension)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as destination:
            maximum = int(getattr(settings, 'IMPORT_MAX_BYTES', 50 * 1024 * 1024))
            total = 0
            while True:
                chunk = file_obj.read(min(65536, maximum + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise InvalidImportTicket('El archivo excede el limite de importacion.')
                destination.write(chunk)
        return signing.dumps(payload, salt=SALT), path
    except Exception:
        path.unlink(missing_ok=True)
        raise


@contextmanager
def claim_upload(token, user):
    # Reject malformed/foreign tickets before constructing or touching any path.
    try:
        if not isinstance(token, str) or len(token) > 2048:
            raise ValueError
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        if (not isinstance(payload, dict) or set(payload) != {'id', 'ext', 'owner'}
                or payload['owner'] != user.pk
                or not isinstance(payload['id'], str)
                or re.fullmatch(r'[0-9a-f]{32}', payload['id']) is None
                or payload['ext'] not in EXTENSIONS):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        raise InvalidImportTicket(ERROR_MESSAGE) from None

    root = private_root()
    source = root / (payload['id'] + payload['ext'])
    claimed = root / (payload['id'] + '.claimed-' + uuid.uuid4().hex + payload['ext'])
    lock = root / (payload['id'] + '.lock')
    try:
        # Arbitrate ownership before any rename, including on Windows, where
        # concurrent claims exposed a race in the rename-only implementation.
        # O_EXCL works across processes without stale existence checks.
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        raise InvalidImportTicket(ERROR_MESSAGE) from None
    try:
        if source.is_symlink() or source.resolve().parent != root or not source.is_file():
            raise InvalidImportTicket(ERROR_MESSAGE)
        try:
            source.rename(claimed)
        except OSError:
            raise InvalidImportTicket(ERROR_MESSAGE) from None
        try:
            yield claimed
        finally:
            claimed.unlink(missing_ok=True)
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)
