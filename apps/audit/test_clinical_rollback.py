"""Audit failures cannot leave clinical mutations or deliver unaudited shares."""
import hashlib
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from audit.models import ChangeLog
from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity, EcgRhythm, QuestionnaireSection
from clinical.models import Patient, Visit, SecureShare
from security.models import User


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuditedClinicalRollbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='a10_actor', password='Synthetic-A10!', email='a10@example.invalid')
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        province, _ = Province.objects.get_or_create(country=country, iso_code='EC-G', defaults={'name': 'Guayas'})
        canton, _ = Canton.objects.get_or_create(province=province, dpa_code='0910', defaults={'name': 'Milagro'})
        institution = Institution.objects.create(acronym='A10_TEST', name='Synthetic audit institution')
        sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        EcgRhythm.objects.get_or_create(name='Ritmo Sinusal (RS)')
        QuestionnaireSection.objects.create(code='A10_TEST', name='Synthetic audit section', display_order=1)
        cls.patient = Patient.objects.create(institution=institution, id_card='A10_SYNTHETIC',
            first_names='Synthetic', last_name1='Audit', birth_date=date(1990, 1, 1),
            birth_canton=canton, sex=sex, ethnicity=ethnicity, created_by=cls.user)
        cls.visit = Visit.objects.create(patient=cls.patient, evaluator=cls.user, study_code='A10_ONLY',
                                         visit_date=date(2026, 1, 1), residence_canton=canton)

    def setUp(self):
        self.client.force_login(self.user)

    def fail_audit(self):
        return patch('audit.services.ChangeLog.objects.create', side_effect=DatabaseError('SYNTHETIC_PRIVATE'))

    def assert_unavailable(self, response):
        self.assertEqual(response.status_code, 503, response.content)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn(b'SYNTHETIC_PRIVATE', response.content)
        self.assertFalse(ChangeLog.objects.exists())

    def test_create_rolls_back_patient_visit_and_measurements_when_audit_fails(self):
        before = Patient.objects.count(), Visit.objects.count()
        with self.fail_audit(), self.assertLogs('apps.audit', level='ERROR'):
            response = self.client.post('/clinical/api/pacientes/crear/',
                {'nombre': 'Synthetic New Patient', 'fecha_nac': '1995-01-01', 'universidad': 'A10_TEST'},
                content_type='application/json')
        self.assert_unavailable(response)
        self.assertEqual((Patient.objects.count(), Visit.objects.count()), before)

    def test_save_rolls_back_updated_name_when_audit_fails(self):
        with self.fail_audit(), self.assertLogs('apps.audit', level='ERROR'):
            response = self.client.post('/clinical/api/ficha/guardar/',
                {'idPaciente': self.patient.pk, 'f_nombre': 'Must rollback'}, content_type='application/json')
        self.assert_unavailable(response)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.first_names, 'Synthetic')
        self.assertFalse(hasattr(self.visit, 'anthropometry'))

    def test_delete_rolls_back_patient_and_visit_when_audit_fails(self):
        with self.fail_audit(), self.assertLogs('apps.audit', level='ERROR'):
            response = self.client.post('/clinical/api/ficha/eliminar/',
                {'patient_ids': [self.patient.pk], 'password': 'Synthetic-A10!'}, content_type='application/json')
        self.assert_unavailable(response)
        self.assertTrue(Patient.objects.filter(pk=self.patient.pk).exists())
        self.assertTrue(Visit.objects.filter(pk=self.visit.pk).exists())

    def test_share_batch_is_fully_audited_before_first_email(self):
        def send(**kwargs):
            self.assertEqual(ChangeLog.objects.filter(table_name='clinical_secure_share').count(), 2)
            self.assertEqual(SecureShare.objects.count(), 2)
            return {'success': True}
        with patch('security.services.email_service.send_secure_share_link_email', side_effect=send) as mail:
            response = self.client.post('/clinical/api/ficha/enviar-correo/',
                {'patient_ids': [self.patient.pk], 'recipients': ['first@example.invalid', 'second@example.invalid']},
                content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(mail.call_count, 2)

    def test_failure_on_second_share_audit_sends_nothing_and_rolls_back_entire_batch(self):
        create = ChangeLog.objects.create
        calls = []
        def fail_second(**kwargs):
            calls.append(kwargs['record_key'])
            if len(calls) == 2:
                raise DatabaseError('SYNTHETIC_PRIVATE')
            return create(**kwargs)
        with patch('audit.services.ChangeLog.objects.create', side_effect=fail_second), \
                patch('security.services.email_service.send_secure_share_link_email') as mail, \
                self.assertLogs('apps.audit', level='ERROR'):
            response = self.client.post('/clinical/api/ficha/enviar-correo/',
                {'patient_ids': [self.patient.pk], 'recipients': ['first@example.invalid', 'second@example.invalid']},
                content_type='application/json')
        self.assert_unavailable(response)
        self.assertEqual(len(calls), 2)
        mail.assert_not_called()
        self.assertFalse(SecureShare.objects.exists())

    def create_share(self, unlocked):
        token = 'a10-synthetic-token-1234567890'
        share = SecureShare.objects.create(visit=self.visit, recipient_email='first@example.invalid',
            token_hash=hashlib.sha256(token.encode()).hexdigest(), code_hash=make_password('123456'),
            expires_at=timezone.now() + timedelta(hours=1), created_by=self.user)
        if unlocked:
            session = self.client.session
            session[f'share_unlocked_{share.pk}'] = True
            session.save()
        return share, '/clinical/compartir/' + token + '/'

    def test_download_audit_failure_does_not_deliver_pdf_or_consume_quota(self):
        share, url = self.create_share(True)
        with self.fail_audit(), patch('clinical.views.generate_clinical_sheet_pdf') as pdf, \
                self.assertLogs('apps.audit', level='ERROR'):
            response = self.client.get(url, {'descarga': 'pdf', 'visit_id': self.visit.pk})
        self.assert_unavailable(response)
        pdf.assert_not_called()
        share.refresh_from_db()
        self.assertEqual(share.download_count, 0)

    def test_unlock_audit_failure_does_not_save_unlocked_session(self):
        share, url = self.create_share(False)
        with self.fail_audit(), self.assertLogs('apps.audit', level='ERROR'):
            response = self.client.post(url, {'code': '123456'})
        self.assert_unavailable(response)
        self.assertFalse(self.client.session.get(f'share_unlocked_{share.pk}', False))
