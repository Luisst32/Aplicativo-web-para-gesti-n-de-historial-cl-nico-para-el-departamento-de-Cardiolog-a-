"""Real PostgreSQL concurrency tests; autocommit fixtures are explicitly removed.

SimpleTestCase with DB access permits independent committed connections without
the cross-schema flush problem of this project's TransactionTestCase fixtures.
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.db import close_old_connections, connection, connections
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.utils import timezone

from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity
from clinical.models import Patient, Visit, SecureShare
from security.models import User


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class SecureShareConcurrencyTests(SimpleTestCase):
    databases = {'default'}

    def setUp(self):
        super().setUp()
        # Cleanup in reverse FK order, including if a later fixture fails.
        def create(model, **fields):
            obj = model.objects.create(**fields)
            self.addCleanup(obj.delete)
            return obj

        country = create(Country, iso_alpha3='ZZZ', name='Synthetic concurrency country')
        province = create(Province, country=country, iso_code='ZZ-CON', name='Synthetic province')
        canton = create(Canton, province=province, dpa_code='ZZ99', name='Synthetic canton')
        institution = create(Institution, acronym='LOCKTEST', name='Synthetic concurrency institution')
        # Sex keys are constrained to 0..9; preserve preexisting catalog fixtures.
        sex, created = Sex.objects.get_or_create(sex_id=9, defaults={'name': 'Synthetic sex'})
        if created:
            self.addCleanup(sex.delete)
        ethnicity = create(Ethnicity, name='Synthetic concurrency ethnicity')
        user = create(User, username='synthetic_lock_user', email='lock@example.invalid')
        patient = create(Patient, institution=institution, id_card='LOCK-SYNTH',
                         first_names='Synthetic', last_name1='Lock', birth_date='1990-01-01',
                         birth_canton=canton, sex=sex, ethnicity=ethnicity, created_by=user)
        visit = create(Visit, patient=patient, evaluator=user, study_code='LOCK-ONLY',
                       visit_date='2026-01-01', residence_canton=canton)
        self.url = '/clinical/compartir/synthetic-lock-token/'
        self.share = create(SecureShare, visit=visit, recipient_email='recipient@example.invalid',
                            token_hash=hashlib.sha256(b'synthetic-lock-token').hexdigest(),
                            code_hash=make_password('654321'),
                            expires_at=timezone.now() + timedelta(hours=1))
        session = SessionStore()
        session[f'share_unlocked_{self.share.pk}'] = True
        session.save()
        self.cookie = session.session_key
        for target, replacement in (
            ('clinical.views.render', lambda request, template, context, status=200: HttpResponse(template, status=status)),
            ('clinical.views.generate_clinical_sheet_pdf', lambda *args, **kwargs: b'%PDF-synthetic'),
            ('clinical.views._generate_zip_stream', lambda *args, **kwargs: b'PK-synthetic'),
            ('clinical.views.register_audit_log', lambda *args, **kwargs: None),
        ):
            self.enterContext(patch(target, side_effect=replacement))

    def parallel(self, *, method='post', data=None, unlocked=False, count=8, query=''):
        barrier = Barrier(count)

        def request(_):
            close_old_connections()
            try:
                client = Client()
                if unlocked:
                    client.cookies[settings.SESSION_COOKIE_NAME] = self.cookie
                barrier.wait(timeout=15)
                return getattr(client, method)(self.url + query, data or {}).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(request, range(count)))

    def test_parallel_wrong_codes_stop_exactly_at_attempt_limit(self):
        statuses = self.parallel(data={'code': '000000'})
        self.share.refresh_from_db()
        self.assertEqual(self.share.attempts, self.share.max_attempts)
        self.assertTrue(self.share.is_revoked)
        self.assertIsNotNone(self.share.revoked_at)
        self.assertEqual(statuses.count(200), 4)
        self.assertEqual(statuses.count(404), 4)
        self.assertEqual(Client().post(self.url, {'code': '654321'}).status_code, 404)

    def test_parallel_malformed_codes_do_not_lose_attempts(self):
        self.parallel(data={'code': 'bad'})
        self.share.refresh_from_db()
        self.assertEqual(self.share.attempts, 5)
        self.assertTrue(self.share.is_revoked)

    def test_parallel_downloads_never_exceed_configured_limit(self):
        self.share.max_downloads = 2
        self.share.save(update_fields=['max_downloads'])
        statuses = self.parallel(method='get', unlocked=True, query='?descarga=pdf')
        self.share.refresh_from_db()
        self.assertEqual(statuses.count(200), 2)
        self.assertEqual(statuses.count(404), 6)
        self.assertEqual(self.share.download_count, 2)

    def test_parallel_unlimited_downloads_count_every_response(self):
        statuses = self.parallel(method='get', unlocked=True, query='?descarga=zip')
        self.share.refresh_from_db()
        self.assertEqual(statuses, [200] * 8)
        self.assertEqual(self.share.download_count, 8)

    def test_parallel_direct_downloads_enforce_limit_after_code_verification(self):
        self.share.max_downloads = 1
        self.share.save(update_fields=['max_downloads'])
        statuses = self.parallel(data={'code': '654321', 'direct_download': '1'})
        self.share.refresh_from_db()
        self.assertEqual(statuses.count(200), 1)
        self.assertEqual(statuses.count(404), 7)
        self.assertEqual(self.share.download_count, 1)

    def test_unlocking_does_not_consume_a_download(self):
        self.share.max_downloads = 1
        self.share.save(update_fields=['max_downloads'])
        client = Client()
        self.assertEqual(client.post(self.url, {'code': '654321'}).status_code, 200)
        self.share.refresh_from_db()
        self.assertEqual(self.share.download_count, 0)
        self.assertEqual(client.get(self.url + '?descarga=pdf').status_code, 200)
        self.assertEqual(client.get(self.url + '?descarga=pdf').status_code, 404)

    def test_failed_pdf_generation_rolls_back_download_counter(self):
        client = Client()
        client.cookies[settings.SESSION_COOKIE_NAME] = self.cookie
        with patch('clinical.views.generate_clinical_sheet_pdf', side_effect=RuntimeError('Synthetic failure')):
            with self.assertRaises(RuntimeError):
                client.get(self.url + '?descarga=pdf')
        self.share.refresh_from_db()
        self.assertEqual(self.share.download_count, 0)
        self.assertEqual(client.get(self.url + '?descarga=pdf').status_code, 200)
