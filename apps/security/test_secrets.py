import base64
import hashlib
import io
import secrets
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from config.secret_settings import read_encryption_keys, read_secret_key
from security.management.commands.rotate_encrypted_settings import ENCRYPTED_FIELDS
from security.models import (
    SYSTEM_SETTING_CACHE_KEY,
    Role,
    SystemSetting,
    _get_fernet_cipher,
    decrypt_api_key,
    encrypt_api_key,
)


class SecretConfigurationTests(SimpleTestCase):
    def test_secret_is_required(self):
        with self.assertRaises(ImproperlyConfigured):
            read_secret_key({})

    def test_rejects_development_and_weak_signing_keys(self):
        for key in ("", "short", "a" * 64, "django-insecure-" + secrets.token_urlsafe(64)):
            with self.subTest(kind=key[:8]), self.assertRaises(ImproperlyConfigured):
                read_secret_key({"SECRET_KEY": key})

    def test_accepts_external_signing_key(self):
        key = secrets.token_urlsafe(64)
        self.assertEqual(read_secret_key({"SECRET_KEY": key}), key)

    def test_dedicated_encryption_key_is_required(self):
        for environ in ({}, {"FIELD_ENCRYPTION_KEYS": " , "}):
            with self.assertRaises(ImproperlyConfigured):
                read_encryption_keys(environ)

    def test_invalid_key_error_does_not_expose_key(self):
        invalid = "private-invalid-value"
        with self.assertRaises(ImproperlyConfigured) as error:
            read_encryption_keys({"FIELD_ENCRYPTION_KEYS": invalid})
        self.assertNotIn(invalid, str(error.exception))

    def test_validates_every_key_in_rotation_ring(self):
        key = Fernet.generate_key().decode("ascii")
        with self.assertRaises(ImproperlyConfigured):
            read_encryption_keys({"FIELD_ENCRYPTION_KEYS": f"{key},invalid"})

    def test_preserves_key_order_and_deduplicates(self):
        first = Fernet.generate_key().decode("ascii")
        second = Fernet.generate_key().decode("ascii")
        self.assertEqual(
            read_encryption_keys({"FIELD_ENCRYPTION_KEYS": f" {first}, {second}, {first} "}),
            [first, second],
        )

    def test_legacy_singular_environment_name_is_supported(self):
        key = Fernet.generate_key().decode("ascii")
        self.assertEqual(read_encryption_keys({"FIELD_ENCRYPTION_KEY": key}), [key])

    @override_settings(FIELD_ENCRYPTION_KEYS=[])
    def test_runtime_never_falls_back_to_django_secret(self):
        with self.assertRaises(ImproperlyConfigured):
            encrypt_api_key("synthetic-credential")

    def test_signing_key_rotation_does_not_change_field_encryption(self):
        key = Fernet.generate_key().decode("ascii")
        with override_settings(FIELD_ENCRYPTION_KEYS=[key], SECRET_KEY=secrets.token_urlsafe(64)):
            encrypted = encrypt_api_key("synthetic-credential")
        with override_settings(FIELD_ENCRYPTION_KEYS=[key], SECRET_KEY=secrets.token_urlsafe(64)):
            self.assertEqual(decrypt_api_key(encrypted), "synthetic-credential")

    def test_legacy_derived_key_requires_explicit_configuration(self):
        old_secret = secrets.token_urlsafe(64)
        legacy = base64.urlsafe_b64encode(hashlib.sha256(old_secret.encode()).digest())
        encrypted = Fernet(legacy).encrypt(b"synthetic-credential").decode("ascii")
        new = Fernet.generate_key().decode("ascii")
        with override_settings(FIELD_ENCRYPTION_KEYS=[new], SECRET_KEY=old_secret):
            self.assertEqual(decrypt_api_key(encrypted), "")
        with override_settings(FIELD_ENCRYPTION_KEYS=[new, legacy.decode("ascii")]):
            self.assertEqual(decrypt_api_key(encrypted), "synthetic-credential")

    def test_new_ciphertext_uses_first_key_only(self):
        first = Fernet.generate_key().decode("ascii")
        second = Fernet.generate_key().decode("ascii")
        with override_settings(FIELD_ENCRYPTION_KEYS=[first, second]):
            encrypted = encrypt_api_key("synthetic-credential").encode("ascii")
        self.assertEqual(Fernet(first).decrypt(encrypted), b"synthetic-credential")
        with self.assertRaises(InvalidToken):
            Fernet(second).decrypt(encrypted)


class EncryptedSettingsRotationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.old_key = Fernet.generate_key().decode("ascii")
        self.new_key = Fernet.generate_key().decode("ascii")
        self.config = SystemSetting.get_settings()
        self.original = {}
        for field in ENCRYPTED_FIELDS:
            token = Fernet(self.old_key).encrypt(f"synthetic-{field}".encode()).decode("ascii")
            setattr(self.config, field, token)
            self.original[field] = token
        self.config.save(update_fields=list(ENCRYPTED_FIELDS))

    def command(self, *args):
        output = io.StringIO()
        with override_settings(FIELD_ENCRYPTION_KEYS=[self.new_key, self.old_key]):
            call_command("rotate_encrypted_settings", *args, stdout=output)
        return output.getvalue()

    def test_check_does_not_change_ciphertexts(self):
        output = self.command("--check")
        self.config.refresh_from_db()
        self.assertIn("verificadas: 5", output)
        for field, old_token in self.original.items():
            self.assertEqual(getattr(self.config, field), old_token)

    def test_rotates_all_providers_and_preserves_plaintexts(self):
        output = self.command()
        self.config.refresh_from_db()
        self.assertIn("rotadas: 5", output)
        for field in ENCRYPTED_FIELDS:
            token = getattr(self.config, field).encode("ascii")
            self.assertEqual(Fernet(self.new_key).decrypt(token), f"synthetic-{field}".encode())
            with self.assertRaises(InvalidToken):
                Fernet(self.old_key).decrypt(token)
            self.assertNotIn(getattr(self.config, field), output)
        self.assertNotIn("synthetic-", output)

    def test_one_unreadable_value_prevents_all_writes(self):
        self.config.gmail_refresh_token_encrypted = "unreadable-synthetic-token"
        self.config.save(update_fields=["gmail_refresh_token_encrypted"])
        with self.assertRaises(CommandError) as error:
            self.command()
        self.config.refresh_from_db()
        for field in ENCRYPTED_FIELDS[:-1]:
            self.assertEqual(getattr(self.config, field), self.original[field])
        self.assertNotIn("unreadable-synthetic-token", str(error.exception))

    def test_unknown_old_key_is_reported_without_changes(self):
        with override_settings(FIELD_ENCRYPTION_KEYS=[self.new_key]):
            with self.assertRaises(CommandError):
                call_command("rotate_encrypted_settings", stdout=io.StringIO())
        self.config.refresh_from_db()
        for field, token in self.original.items():
            self.assertEqual(getattr(self.config, field), token)

    def test_save_failure_rolls_back_prior_rows(self):
        role = Role.objects.create(name="Audit rotation second role")
        second = SystemSetting.objects.create(
            role=role,
            gemini_api_key_encrypted=Fernet(self.old_key).encrypt(b"second-synthetic").decode("ascii"),
        )
        original_save = SystemSetting.save

        def fail_second(instance, *args, **kwargs):
            if instance.pk == second.pk:
                raise RuntimeError("synthetic-write-failure")
            return original_save(instance, *args, **kwargs)

        with patch.object(SystemSetting, "save", fail_second):
            with self.assertRaisesRegex(RuntimeError, "synthetic-write-failure"):
                self.command()
        self.config.refresh_from_db()
        for field, token in self.original.items():
            self.assertEqual(getattr(self.config, field), token)

    def test_rotation_invalidates_cached_settings_after_commit(self):
        cache.set(SYSTEM_SETTING_CACHE_KEY, self.config)
        with self.captureOnCommitCallbacks(execute=True):
            self.command()
        self.assertIsNone(cache.get(SYSTEM_SETTING_CACHE_KEY))

    def test_empty_fields_remain_empty(self):
        self.config.gmail_refresh_token_encrypted = ""
        self.config.openai_api_key_encrypted = None
        self.config.save(update_fields=["gmail_refresh_token_encrypted", "openai_api_key_encrypted"])
        self.command()
        self.config.refresh_from_db()
        self.assertEqual(self.config.gmail_refresh_token_encrypted, "")
        self.assertIsNone(self.config.openai_api_key_encrypted)
