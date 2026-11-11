import os
import json
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase, Client, override_settings
from django.urls import reverse
from security.models import (
    User,
    Role,
    UserRole,
    SystemSetting,
    encrypt_api_key,
    decrypt_api_key,
)


class SecurityModelStatusTests(SimpleTestCase):
    def test_user_default_status(self):
        user = User(username='doc_test', email='doc@unemi.edu.ec', first_name='Doc', last_name='Cardio')
        self.assertEqual(user.status, User.Status.ACTIVE)

    def test_user_inactive_status_when_account_not_in_use(self):
        user = User(username='retired_user', email='ret@unemi.edu.ec', first_name='Carlos', last_name='Doc')
        user.status = User.Status.INACTIVE
        self.assertEqual(user.status, User.Status.INACTIVE)

    def test_role_and_user_role_status(self):
        role = Role(name='Clinical Cardiologist')
        self.assertEqual(role.status, Role.Status.ACTIVE)

        user = User(username='dr_role', email='dr@unemi.edu.ec', first_name='Luis', last_name='S')
        user_role = UserRole(user=user, role=role)
        self.assertEqual(user_role.status, UserRole.Status.ACTIVE)


class SystemSettingEncryptionTests(TestCase):
    def test_encrypt_and_decrypt_api_key(self):
        raw_key = "AIzaSyD_TEST_ENCRYPTED_KEY_12345"
        encrypted = encrypt_api_key(raw_key)
        self.assertNotEqual(encrypted, raw_key)
        self.assertTrue(len(encrypted) > 20)

        decrypted = decrypt_api_key(encrypted)
        self.assertEqual(decrypted, raw_key)

    def test_get_and_set_gemini_api_key(self):
        test_key = "AIzaSyB_NEW_GLOBAL_KEY_777"
        setting = SystemSetting.set_settings(chatbot_enabled=True, raw_api_key=test_key)
        self.assertIsNotNone(setting)
        self.assertNotEqual(setting.gemini_api_key_encrypted, test_key)

        retrieved_key = SystemSetting.get_gemini_api_key()
        self.assertEqual(retrieved_key, test_key)

    def test_is_and_set_chatbot_enabled(self):
        SystemSetting.set_settings(chatbot_enabled=False)
        self.assertFalse(SystemSetting.is_chatbot_enabled())

        SystemSetting.set_settings(chatbot_enabled=True)
        self.assertTrue(SystemSetting.is_chatbot_enabled())

    def test_system_setting_is_relational_to_admin_role_only(self):
        setting = SystemSetting.set_settings(chatbot_enabled=True, raw_api_key='AIzaSy_ROLE_ONLY_123')
        self.assertIsNotNone(setting.role)
        self.assertEqual(setting.role.name, 'Administrador')

        medico_role = Role.objects.create(name='Médico Evaluador')
        medico_user = User.objects.create_user(
            username='medico_normal',
            email='medico_normal@cardiounemi.edu.ec',
            first_name='Pedro',
            last_name='Ruiz',
            password='Password123!',
        )
        UserRole.objects.create(user=medico_user, role=medico_role, status=UserRole.Status.ACTIVE)

        self.assertFalse(setting.is_role_authorized(medico_user))
        self.assertEqual(SystemSetting.get_gemini_api_key(user=medico_user), '')

        role_admin_user = User.objects.create_user(
            username='admin_por_rol',
            email='adminrol@cardiounemi.edu.ec',
            first_name='Laura',
            last_name='Mora',
            password='Password123!',
        )
        UserRole.objects.create(user=role_admin_user, role=setting.role, status=UserRole.Status.ACTIVE)

        self.assertTrue(setting.is_role_authorized(role_admin_user))
        self.assertEqual(SystemSetting.get_gemini_api_key(user=role_admin_user), 'AIzaSy_ROLE_ONLY_123')

    def test_api_key_never_reads_from_env(self):
        cache.clear()
        SystemSetting.set_settings(chatbot_enabled=True, raw_api_key='')
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'ENV_KEY_SHOULD_BE_IGNORED'}):
            self.assertEqual(SystemSetting.get_gemini_api_key(), '')

    def test_invalid_fernet_token_returns_empty_not_ciphertext(self):
        self.assertEqual(decrypt_api_key('texto-corrupto-no-fernet'), '')

    def test_multifernet_rotation_with_field_encryption_keys(self):
        cache.clear()
        old_key = Fernet.generate_key().decode('utf-8')
        new_key = Fernet.generate_key().decode('utf-8')
        with override_settings(FIELD_ENCRYPTION_KEYS=[old_key]):
            SystemSetting.set_settings(chatbot_enabled=True, raw_api_key='ROTATED_API_KEY_SECRET')
        with override_settings(FIELD_ENCRYPTION_KEYS=[new_key, old_key]):
            self.assertEqual(SystemSetting.get_gemini_api_key(), 'ROTATED_API_KEY_SECRET')

    def test_is_administrator_strict_role_and_is_active_sync(self):
        cache.clear()
        setting = SystemSetting.get_settings()

        # Usuario con username 'admin', is_staff=True y rol similar 'Administrativo' NO debe ser admin
        fake_admin_role = Role.objects.create(name='Administrativo')
        tricky_user = User.objects.create_user(
            username='admin',
            email='tricky@cardiounemi.edu.ec',
            first_name='Fake',
            last_name='Admin',
            password='Password123!',
            is_staff=True,
        )
        UserRole.objects.create(user=tricky_user, role=fake_admin_role, status=UserRole.Status.ACTIVE)

        self.assertFalse(tricky_user.is_administrator)
        self.assertFalse(setting.is_role_authorized(tricky_user))
        with self.assertRaises(PermissionDenied):
            SystemSetting.set_settings(chatbot_enabled=False, user=tricky_user)

        # Sincronización status <-> is_active
        tricky_user.status = User.Status.SUSPENDED
        tricky_user.save()
        tricky_user.refresh_from_db()
        self.assertFalse(tricky_user.is_active)

    def test_is_chatbot_enabled_fails_closed_on_error(self):
        cache.clear()
        with patch.object(SystemSetting, 'get_settings', side_effect=RuntimeError('DB offline')):
            self.assertFalse(SystemSetting.is_chatbot_enabled())


class SecurityApiEndpointsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username='doctor_test',
            email='doctor@cardiounemi.edu.ec',
            first_name='Juan',
            last_name='Pérez',
            password='CurrentPassword123!'
        )
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@cardiounemi.edu.ec',
            first_name='Admin',
            last_name='UNEMI',
            password='AdminPassword123!',
            is_staff=True
        )
        admin_role = SystemSetting.get_admin_role()
        UserRole.objects.create(user=self.admin_user, role=admin_role, status=UserRole.Status.ACTIVE)

    def test_profile_api_requires_login(self):
        response = self.client.get('/security/api/profile/')
        self.assertEqual(response.status_code, 302)

    def test_profile_api_get(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        response = self.client.get('/security/api/profile/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['user']['username'], 'doctor_test')
        self.assertEqual(data['user']['first_name'], 'Juan')

    def test_profile_api_update_success(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        payload = {
            'first_name': 'Juan Carlos',
            'last_name': 'Pérez',
            'second_last_name': 'Gómez',
            'email': 'jc.perez@cardiounemi.edu.ec',
            'current_password': 'CurrentPassword123!'
        }
        response = self.client.post(
            '/security/api/profile/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Juan Carlos')
        self.assertEqual(self.user.second_last_name, 'Gómez')
        self.assertEqual(self.user.email, 'jc.perez@cardiounemi.edu.ec')

    def test_profile_api_update_fails_wrong_password(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        payload = {
            'first_name': 'Hacker',
            'last_name': 'Attempt',
            'email': 'hacker@malicious.com',
            'current_password': 'WrongPassword123'
        }
        response = self.client.post(
            '/security/api/profile/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('incorrecta', data['message'].lower())

    def test_change_password_success(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        payload = {
            'old_password': 'CurrentPassword123!',
            'new_password': 'BrandNewPassword999!',
            'confirm_password': 'BrandNewPassword999!'
        }
        response = self.client.post(
            '/security/api/change-password/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')

        # Test login with new password
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPassword999!'))

    def test_change_password_mismatch_fails(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        payload = {
            'old_password': 'CurrentPassword123!',
            'new_password': 'BrandNewPassword999!',
            'confirm_password': 'DifferentPassword111!'
        }
        response = self.client.post(
            '/security/api/change-password/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('no coinciden', data['message'].lower())

    def test_change_password_short_fails(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        payload = {
            'old_password': 'CurrentPassword123!',
            'new_password': 'short',
            'confirm_password': 'short'
        }
        response = self.client.post(
            '/security/api/change-password/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('8 caracteres', data['message'].lower())

    def test_settings_api_admin_can_view_and_update_api_key(self):
        self.client.login(username='admin_test', password='AdminPassword123!')
        # GET settings
        get_res = self.client.get('/security/api/settings/')
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertEqual(get_data['status'], 'success')
        self.assertTrue(get_data['is_admin'])
        self.assertIn('chatbot_enabled', get_data)

        # POST settings (admin updates key)
        post_payload = {
            'chatbot_enabled': True,
            'gemini_api_key': 'AIzaSy_ADMIN_NEW_KEY_999',
            'gemini_model': 'gemini-3.5-flash-lite'
        }
        post_res = self.client.post(
            '/security/api/settings/',
            data=json.dumps(post_payload),
            content_type='application/json'
        )
        self.assertEqual(post_res.status_code, 200)
        post_data = post_res.json()
        self.assertEqual(post_data['status'], 'success')
        self.assertEqual(SystemSetting.get_gemini_api_key(), 'AIzaSy_ADMIN_NEW_KEY_999')

    def test_settings_api_admin_can_configure_multiple_apis(self):
        self.client.login(username='admin_test', password='AdminPassword123!')

        # POST multiple APIs settings
        payload = {
            'chatbot_enabled': True,
            'active_llm_provider': 'claude',
            'gemini_api_key': 'AIzaSy_GEMINI_SECRET_123',
            'gemini_model': 'gemini-2.5-flash',
            'gemini_enabled': True,
            'openai_api_key': 'sk-proj-OPENAI_SECRET_KEY_456',
            'openai_model': 'gpt-4o',
            'openai_enabled': True,
            'claude_api_key': 'sk-ant-CLAUDE_SECRET_KEY_789',
            'claude_model': 'claude-3-5-sonnet-20241022',
            'claude_enabled': True,
            'gmail_sender_email': 'cardio@unemi.edu.ec',
            'gmail_client_id': 'google-client-id-abc.apps.googleusercontent.com',
            'gmail_client_secret': 'GOCSPX-SECRET-999',
            'gmail_refresh_token': '1//04REFRESH-TOKEN-XYZ',
            'gmail_redirect_uri': 'http://127.0.0.1:8000/security/oauth2/gmail/callback/',
            'gmail_api_enabled': True
        }
        res = self.client.post(
            '/security/api/settings/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)

        # Verify decrypted values on model
        self.assertEqual(SystemSetting.get_gemini_api_key(), 'AIzaSy_GEMINI_SECRET_123')
        self.assertEqual(SystemSetting.get_openai_api_key(), 'sk-proj-OPENAI_SECRET_KEY_456')
        self.assertEqual(SystemSetting.get_claude_api_key(), 'sk-ant-CLAUDE_SECRET_KEY_789')
        self.assertEqual(SystemSetting.get_gmail_client_secret(), 'GOCSPX-SECRET-999')
        self.assertEqual(SystemSetting.get_gmail_refresh_token(), '1//04REFRESH-TOKEN-XYZ')

        cfg = SystemSetting.get_settings()
        self.assertEqual(cfg.active_llm_provider, 'claude')
        self.assertEqual(cfg.openai_model, 'gpt-4o')
        self.assertEqual(cfg.gmail_sender_email, 'cardio@unemi.edu.ec')

        # GET settings and verify masked values returned
        get_res = self.client.get('/security/api/settings/')
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertTrue(get_data['gemini_api_key_configured'])
        self.assertTrue(get_data['openai_api_key_configured'])
        self.assertTrue(get_data['claude_api_key_configured'])
        self.assertTrue(get_data['gmail_secret_configured'])
        self.assertTrue(get_data['gmail_refresh_configured'])
        self.assertIn('***', get_data['openai_api_key_masked'])
        self.assertIn('***', get_data['claude_api_key_masked'])

        # Submitting masked tokens with '***' must NOT overwrite existing secrets
        preserve_payload = {
            'chatbot_enabled': True,
            'active_llm_provider': 'openai',
            'openai_api_key': get_data['openai_api_key_masked'],  # sending masked
            'claude_api_key': get_data['claude_api_key_masked']    # sending masked
        }
        preserve_res = self.client.post(
            '/security/api/settings/',
            data=json.dumps(preserve_payload),
            content_type='application/json'
        )
        self.assertEqual(preserve_res.status_code, 200)
        self.assertEqual(SystemSetting.get_openai_api_key(), 'sk-proj-OPENAI_SECRET_KEY_456')
        self.assertEqual(SystemSetting.get_claude_api_key(), 'sk-ant-CLAUDE_SECRET_KEY_789')
        self.assertEqual(SystemSetting.get_settings().active_llm_provider, 'openai')

    def test_settings_api_non_admin_cannot_view_or_update_api_key(self):
        # Seed an existing key
        SystemSetting.set_settings(chatbot_enabled=True, raw_api_key='ORIGINAL_SECRET_KEY')

        # Non-admin logs in
        self.client.login(username='doctor_test', password='CurrentPassword123!')

        # GET should NOT leak the key or model
        get_res = self.client.get('/security/api/settings/')
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertFalse(get_data['is_admin'])
        self.assertEqual(get_data['api_key_masked'], '')
        self.assertEqual(get_data['gemini_model'], '')

        # POST should be rejected with 403 Forbidden and modify NOTHING
        post_payload = {
            'chatbot_enabled': False,
            'gemini_api_key': 'MALICIOUS_KEY_ATTEMPT',
            'gemini_model': 'gemini-hacker'
        }
        post_res = self.client.post(
            '/security/api/settings/',
            data=json.dumps(post_payload),
            content_type='application/json'
        )
        self.assertEqual(post_res.status_code, 403)

        # Neither chatbot_enabled nor API key was modified
        self.assertTrue(SystemSetting.is_chatbot_enabled())
        self.assertEqual(SystemSetting.get_gemini_api_key(), 'ORIGINAL_SECRET_KEY')


class GlobalLoginRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='doctor_redirect',
            email='redirect@cardiounemi.edu.ec',
            first_name='Ana',
            last_name='López',
            password='Password123!'
        )

    def test_all_unauthenticated_urls_redirect_to_login_never_404(self):
        login_url = reverse('security:login')
        test_paths = [
            '/',
            '/dashboard/',
            '/clinical/',
            '/clinical/listado/',
            '/clinical/formulario/',
            '/chatbot/',
            '/security/',
            '/login/',
            '/accounts/login/',
            '/admin/',
            '/cualquier-ruta-inexistente/',
            '/clinical/pagina-que-no-existe/',
        ]
        for path in test_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response['Location'].startswith(login_url))

    def test_login_page_accessible_without_auth(self):
        response = self.client.get(reverse('security:login'))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_root_aliases_redirect_cleanly(self):
        self.client.login(username='doctor_redirect', password='Password123!')
        home_res = self.client.get(reverse('home'))
        self.assertEqual(home_res.status_code, 200)
        self.assertIn('Directorio de Pacientes', home_res.content.decode('utf-8'))

        dash_res = self.client.get(reverse('dashboard:index'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertEqual(reverse('dashboard:index'), '/dashboard/')

        clinical_res = self.client.get('/clinical/')
        self.assertEqual(clinical_res.status_code, 302)
        self.assertEqual(clinical_res['Location'], reverse('clinical:list'))

        sec_res = self.client.get('/security/')
        self.assertEqual(sec_res.status_code, 302)

    def test_invalid_or_external_next_param_redirects_safely_after_login(self):
        response = self.client.post(
            f"{reverse('security:login')}?next=/ruta-inexistente/",
            data={'email': 'doctor_redirect', 'password': 'Password123!'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('home'))

        response_ext = self.client.post(
            f"{reverse('security:login')}?next=https://evil.example.com/",
            data={'email': 'doctor_redirect', 'password': 'Password123!'}
        )
        self.assertEqual(response_ext.status_code, 302)
        self.assertEqual(response_ext['Location'], reverse('home'))

    def test_valid_next_param_preserved_after_login(self):
        target = reverse('clinical:form')
        response = self.client.post(
            reverse('security:login'),
            data={'email': 'doctor_redirect', 'password': 'Password123!', 'next': target}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], target)


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='doctor_reset',
            email='doctor_reset@cardiounemi.edu.ec',
            first_name='Dr. Carlos',
            last_name='Mendoza',
            password='OldPassword123!',
        )

    def test_password_reset_endpoints_accessible_unauthenticated(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        confirm_url = reverse('security:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Nueva Contraseña', response.content.decode('utf-8'))

    def test_password_reset_request_view_with_valid_email(self):
        from django.core import mail
        response = self.client.post(
            reverse('security:password_reset_request'),
            data=json.dumps({'email': 'doctor_reset@cardiounemi.edu.ec'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('CARDIOUNEMI - Restablecimiento de Contraseña', mail.outbox[0].subject)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_password_reset_request_view_with_username(self):
        from django.core import mail
        response = self.client.post(
            reverse('security:password_reset_request'),
            data=json.dumps({'email': 'doctor_reset'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_confirm_view_updates_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse('security:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})

        # Mismatch passwords
        res_mismatch = self.client.post(
            confirm_url,
            data=json.dumps({'new_password': 'NewPassword123!', 'confirm_password': 'Mismatch123!'}),
            content_type='application/json'
        )
        self.assertEqual(res_mismatch.status_code, 400)

        # Successful update
        res_ok = self.client.post(
            confirm_url,
            data=json.dumps({'new_password': 'NewPassword123!', 'confirm_password': 'NewPassword123!'}),
            content_type='application/json'
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.json()['status'], 'success')

        # Verify old password no longer works
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('OldPassword123!'))
        self.assertTrue(self.user.check_password('NewPassword123!'))

