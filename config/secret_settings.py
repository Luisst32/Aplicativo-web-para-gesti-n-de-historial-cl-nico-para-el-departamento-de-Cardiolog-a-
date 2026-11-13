"""Validate externally provisioned signing and encryption keys."""
from collections.abc import Mapping

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured


def read_secret_key(environ: Mapping[str, str]) -> str:
    key = environ.get("SECRET_KEY", "").strip()
    if len(key) < 50 or len(set(key)) < 5 or key.startswith("django-insecure-"):
        raise ImproperlyConfigured(
            "Configure SECRET_KEY con una clave aleatoria privada de al menos "
            "50 caracteres; no se admite una clave de desarrollo."
        )
    return key


def read_encryption_keys(environ: Mapping[str, str]) -> list[str]:
    raw_keys = environ.get("FIELD_ENCRYPTION_KEYS") or environ.get("FIELD_ENCRYPTION_KEY", "")
    keys = list(dict.fromkeys(key.strip() for key in raw_keys.split(",") if key.strip()))
    if not keys:
        raise ImproperlyConfigured(
            "Configure FIELD_ENCRYPTION_KEYS con al menos una clave Fernet "
            "dedicada; no se deriva del secreto de Django."
        )
    for key in keys:
        try:
            Fernet(key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise ImproperlyConfigured(
                "FIELD_ENCRYPTION_KEYS contiene una clave Fernet inválida."
            ) from None
    return keys
