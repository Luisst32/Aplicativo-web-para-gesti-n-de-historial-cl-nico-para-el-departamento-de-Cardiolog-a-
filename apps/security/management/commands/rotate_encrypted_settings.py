"""Re-encrypt credentials with the first dedicated key without revealing their values."""
from cryptography.fernet import InvalidToken
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from security.models import SYSTEM_SETTING_CACHE_KEY, SystemSetting, _get_fernet_cipher


ENCRYPTED_FIELDS = (
    "gemini_api_key_encrypted",
    "openai_api_key_encrypted",
    "claude_api_key_encrypted",
    "gmail_client_secret_encrypted",
    "gmail_refresh_token_encrypted",
)


class Command(BaseCommand):
    help = "Verifica o rota todas las credenciales usando FIELD_ENCRYPTION_KEYS (primera = nueva)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Comprueba que todas las credenciales se pueden descifrar, sin modificarlas.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cipher = _get_fernet_cipher()
        pending = []
        count = 0
        for row in SystemSetting.objects.select_for_update().order_by("pk"):
            changes = {}
            for field in ENCRYPTED_FIELDS:
                token = getattr(row, field)
                if not token:
                    continue
                try:
                    encoded = token.strip().encode("ascii")
                    if options["check"]:
                        cipher.decrypt(encoded)
                    else:
                        changes[field] = cipher.rotate(encoded).decode("ascii")
                except (InvalidToken, ValueError, UnicodeError):
                    raise CommandError(
                        "No se puede descifrar una credencial; no se aplicó la rotación. "
                        "Compruebe las claves anteriores y los datos almacenados."
                    ) from None
                count += 1
            if changes:
                pending.append((row, changes))

        # Verificar todo antes de escribir; ante cualquier error la transacción revierte.
        for row, changes in pending:
            for field, value in changes.items():
                setattr(row, field, value)
            row.save(update_fields=list(changes))

        if not options["check"]:
            transaction.on_commit(lambda: cache.delete(SYSTEM_SETTING_CACHE_KEY))

        action = "verificadas" if options["check"] else "rotadas"
        self.stdout.write(self.style.SUCCESS(f"Credenciales {action}: {count}."))
