import json
from django.test import SimpleTestCase, TestCase, Client
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


class SecurityApiEndpointsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='doctor_test',
            email='doctor@cardiounemi.edu.ec',
            first_name='Juan',
            last_name='Pérez',
            password='CurrentPassword123!'
        )

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

    def test_settings_api_get_and_post(self):
        self.client.login(username='doctor_test', password='CurrentPassword123!')
        # GET settings
        get_res = self.client.get('/security/api/settings/')
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertEqual(get_data['status'], 'success')
        self.assertIn('chatbot_enabled', get_data)

        # POST settings (toggle chatbot and update key)
        post_payload = {
            'chatbot_enabled': False,
            'gemini_api_key': 'AIzaSy_NEW_FROM_AJUSTES_MODAL',
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

        # Verify DB updated
        self.assertFalse(SystemSetting.is_chatbot_enabled())
        self.assertEqual(SystemSetting.get_gemini_api_key(), 'AIzaSy_NEW_FROM_AJUSTES_MODAL')
