import os
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase

from chatbot.services import query_gemini_assistant
from security.models import Role, SystemSetting, User, UserRole


class ProviderCredentialPolicyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.admin = User.objects.create_superuser(username='provider_admin', email='admin@example.invalid')
        self.reader = User.objects.create_user(username='provider_reader', email='reader@example.invalid')
        self.reader.user_permissions.set(Permission.objects.filter(
            content_type__app_label='clinical', codename__in=['view_patient', 'view_visit'],
        ))
        self.cfg = SystemSetting.set_settings(
            chatbot_enabled=True, active_llm_provider='gemini', gemini_enabled=True,
            raw_api_key='synthetic-db-credential', model='configured-synthetic-model', user=self.admin,
        )
        self.enterContext(patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-env-must-not-be-used'}))
        self.sdk = self.enterContext(patch('google.genai.Client'))
        self.sdk.return_value.models.generate_content.return_value = SimpleNamespace(
            text='Synthetic answer', usage_metadata=SimpleNamespace(total_token_count=7),
        )
        self.context = self.enterContext(patch('chatbot.services.get_anonymized_cohort_context', return_value='Synthetic cohort'))
        self.enterContext(patch('chatbot.services.generate_fallback_clinical_answer', return_value='Synthetic local answer'))
        self.enterContext(patch('chatbot.services.build_chart_json_if_requested', return_value=''))
        self.enterContext(patch('chatbot.services._log_bot_query'))

    def query(self, user=None):
        return query_gemini_assistant('Distribución de riesgo cardiovascular', user=user or self.admin)

    def assert_local(self, user=None):
        self.assertEqual(self.query(user)['mode'], 'deterministic_fallback')
        self.sdk.assert_not_called()
        self.context.assert_not_called()

    def test_reader_cannot_use_database_or_environment_credentials(self):
        with patch.object(SystemSetting, 'get_gemini_api_key') as getter:
            self.assert_local(self.reader)
            getter.assert_not_called()

    def test_staff_flag_does_not_enable_provider_credentials(self):
        self.reader.is_staff = True
        self.reader.save()
        self.assert_local(self.reader)

    def test_disabled_gemini_does_not_fall_back_to_environment(self):
        SystemSetting.set_settings(gemini_enabled=False, user=self.admin)
        self.assert_local()

    def test_selected_provider_never_silently_switches_to_gemini(self):
        for provider in ('openai', 'claude', '', 'unknown'):
            with self.subTest(provider=provider):
                SystemSetting.set_settings(active_llm_provider=provider, user=self.admin)
                self.assert_local()

    def test_environment_only_credential_is_ignored_even_for_admin(self):
        SystemSetting.set_settings(raw_api_key='', user=self.admin)
        self.assert_local()

    def test_unreadable_database_key_cannot_activate_environment_key(self):
        self.cfg.gemini_api_key_encrypted = 'synthetic-corrupted-ciphertext'
        self.cfg.save()
        self.assert_local()

    def test_runtime_policy_lookup_failure_uses_local_mode(self):
        with (
            patch.object(SystemSetting, 'is_chatbot_enabled', return_value=True),
            patch.object(SystemSetting, 'get_settings', side_effect=RuntimeError('Synthetic lookup failure')),
        ):
            self.assert_local()

    def test_key_lookup_failure_uses_local_mode(self):
        with patch.object(SystemSetting, 'get_gemini_api_key', side_effect=RuntimeError('Synthetic failure')):
            self.assert_local()

    def test_global_disable_or_failure_never_calls_provider(self):
        SystemSetting.set_settings(chatbot_enabled=False, user=self.admin)
        self.assertEqual(self.query()['status'], 'disabled')
        with patch.object(SystemSetting, 'is_chatbot_enabled', side_effect=RuntimeError('Synthetic failure')):
            self.assertEqual(self.query()['status'], 'disabled')
        self.sdk.assert_not_called()
        self.context.assert_not_called()

    def test_active_admin_uses_only_the_database_key_and_configured_model(self):
        result = self.query()
        self.assertEqual(result['mode'], 'gemini_flash')
        self.sdk.assert_called_once_with(api_key='synthetic-db-credential')
        call = self.sdk.return_value.models.generate_content.call_args
        self.assertEqual(call.kwargs['model'], 'configured-synthetic-model')
        self.assertEqual(result['tokens_used'], 7)

    def test_revoked_admin_assignment_cannot_use_provider_credentials(self):
        assignment = UserRole.objects.create(user=self.reader, role=self.cfg.role)
        self.assertEqual(self.query(self.reader)['mode'], 'gemini_flash')
        self.sdk.reset_mock()
        self.context.reset_mock()
        assignment.status = UserRole.Status.INACTIVE
        assignment.save()
        self.assert_local(self.reader)

    def test_inactive_admin_role_prevents_external_calls(self):
        role = self.cfg.role
        role.status = Role.Status.INACTIVE
        role.save()
        self.assert_local()
