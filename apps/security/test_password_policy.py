import json

from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from security.models import User


class PasswordPolicyTests(TestCase):
    def setUp(self):
        self.old_password = 'Original!Credential-73'
        self.user = User.objects.create_user(
            username='UniqueClinicalAccount', email='synthetic@example.invalid',
            first_name='UniqueClinicalAccount', password=self.old_password,
        )
        self.token = default_token_generator.make_token(self.user)
        self.reset_url = reverse('security:password_reset_confirm', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(self.user.pk)), 'token': self.token,
        })

    def submit(self, flow, password):
        if flow == 'change':
            self.client.force_login(self.user)
            # Login updates last_login, which invalidates any earlier reset token.
            self.user.refresh_from_db()
            self.token = default_token_generator.make_token(self.user)
            self.reset_url = reverse('security:password_reset_confirm', kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(self.user.pk)), 'token': self.token,
            })
            url = reverse('security:api_change_password')
        else:
            self.client.logout()
            url = self.reset_url
        return self.client.post(url, json.dumps({
            'old_password': self.old_password,
            'new_password': password, 'confirm_password': password,
        }), content_type='application/json')

    def assert_rejected(self, password):
        for flow in ('change', 'reset'):
            with self.subTest(flow=flow):
                response = self.submit(flow, password)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['status'], 'error')
                self.assertTrue(response.json()['errors'])
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(self.old_password))
                self.assertTrue(default_token_generator.check_token(self.user, self.token))

    def test_rejects_common_password_in_both_flows(self):
        self.assert_rejected('password')

    def test_rejects_numeric_password_in_both_flows(self):
        self.assert_rejected('836194725603')

    def test_rejects_user_similar_password_in_both_flows(self):
        self.assert_rejected('UniqueClinicalAccount')

    def test_rejects_short_password_in_both_flows(self):
        self.assert_rejected('xQ7!a')

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 30},
    }])
    def test_honors_configured_policy_instead_of_hardcoded_length(self):
        self.assert_rejected('Valid!ButLessThan30')

    def test_change_accepts_strong_password_and_preserves_session(self):
        new_password = 'Orbit!Cedar-72!Quartz'
        self.assertEqual(self.submit('change', new_password).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertEqual(self.client.get(reverse('security:api_profile')).status_code, 200)

    def test_reset_accepts_strong_password_and_consumes_token(self):
        new_password = 'Orbit!Cedar-72!Quartz'
        self.assertEqual(self.submit('reset', new_password).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(default_token_generator.check_token(self.user, self.token))
        self.assertEqual(self.submit('reset', 'Another!Strong-Credential-82').status_code, 400)
