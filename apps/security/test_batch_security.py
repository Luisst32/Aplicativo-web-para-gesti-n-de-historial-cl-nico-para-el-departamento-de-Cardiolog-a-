from unittest.mock import patch
from django.test import TestCase, SimpleTestCase
from security.request_limits import consume
from security.database_checks import database_runtime_privileges
from chatbot.services import get_anonymized_cohort_context

class QuotaTests(TestCase):
    def test_shared_quota_and_expiration(self):
        for _ in range(20):
            self.assertTrue(consume('synthetic-user',20,now=60))
        self.assertFalse(consume('synthetic-user',20,now=60))
        self.assertTrue(consume('synthetic-user',20,now=120))
    def test_peer_cannot_bypass_login_quota_by_forwarded_header(self):
        for index in range(5):
            self.client.post('/security/login/', {'username':'synthetic', 'password':'bad'}, HTTP_X_FORWARDED_FOR=str(index))
        self.assertEqual(self.client.post('/security/login/', {'username':'synthetic', 'password':'bad'}, HTTP_X_FORWARDED_FOR='changed').status_code,429)
    def test_reset_is_limited(self):
        for _ in range(5):
            self.client.post('/security/password-reset/',{})
        self.assertEqual(self.client.post('/security/password-reset/',{}).status_code,429)

class PrivacyTests(SimpleTestCase):
    databases = {'default'}
    def context(self, records):
        with patch('chatbot.services.get_dashboard_evaluation_data',return_value={'records':records}):
            return get_anonymized_cohort_context()
    def test_small_cohort_never_exposes_total_or_values(self):
        text=self.context([{'hipertension':True,'nombre':'SYNTHETIC_PRIVATE'}]*3)
        self.assertNotIn('3',text)
        self.assertNotIn('SYNTHETIC_PRIVATE',text)
    def test_small_cell_and_complement_suppressed(self):
        for count in (0,1,4,9,10):
            rows=[{'hipertension':i<count} for i in range(10)]
            self.assertIn('HTA: no divulgado',self.context(rows))
    def test_balanced_cell_is_available(self):
        self.assertIn('HTA: 5 de 10',self.context([{'hipertension':i<5} for i in range(10)]))
    def test_deployment_rejects_elevated_or_owner_role(self):
        for elevated,owner in ((True,False),(False,True),(False,False)):
            with patch('security.database_checks.connection.cursor') as cursor:
                cursor.return_value.__enter__.return_value.fetchone.side_effect=[(elevated,),(owner,),(False,)]
                self.assertEqual(bool(database_runtime_privileges(None)),elevated or owner)

    def test_bot_history_does_not_store_request_or_response_content(self):
        from types import SimpleNamespace
        from chatbot.services import _log_bot_query
        with patch('chatbot.services.BotQuery.objects.create') as create:
            _log_bot_query(SimpleNamespace(is_authenticated=True),'PRIVATE_QUESTION','PRIVATE_RESPONSE',0,1,'SUCCESS')
            self.assertNotIn('PRIVATE_QUESTION',str(create.call_args))
            self.assertNotIn('PRIVATE_RESPONSE',str(create.call_args))
