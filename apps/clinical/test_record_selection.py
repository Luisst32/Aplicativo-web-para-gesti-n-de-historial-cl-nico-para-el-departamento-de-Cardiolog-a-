"""A04: synthetic collisions must never broaden or substitute a selection."""
import hashlib
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

import pandas as pd
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity, EcgRhythm, QuestionnaireSection
from clinical.models import Patient, Visit, SecureShare
from clinical.services.record_selection import RecordSelectionError, record_id, patient_ids
from clinical.services.sav_exporter import generate_export_dataset
from security.models import User


class SelectionSyntaxTests(SimpleTestCase):
    def test_only_positive_primary_keys_and_anchored_ui_prefixes(self):
        for value in (1, '1', 'p1', 'p_1'):
            self.assertEqual(record_id(value), 1)
        self.assertEqual(record_id('h_12', 'h'), 12)
        for value in (None, True, False, 1.0, {}, [], '', 'all', 'todos', 'p',
                      '1p', 'pp1', 'p__1', '1_2', '0', '-1', '01', '١', '9' * 40):
            with self.subTest(value=value), self.assertRaises(RecordSelectionError):
                record_id(value)

    def test_batch_rejects_empty_or_malformed_members_and_deduplicates(self):
        self.assertEqual(patient_ids(['p1', 1, 'p_2']), [1, 2])
        for values in ([], None, {}, 1, True, '1,,2', [1, None], ['all'], ['1', 'todos']):
            with self.subTest(values=values), self.assertRaises(RecordSelectionError):
                patient_ids(values)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ExactRecordSelectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Synthetic-selection-2026!'
        cls.user = User.objects.create_user(username='selection_actor', password=cls.password,
                                           email='selection@example.invalid')
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        province, _ = Province.objects.get_or_create(country=country, iso_code='EC-G', defaults={'name': 'Guayas'})
        canton, _ = Canton.objects.get_or_create(province=province, dpa_code='0910', defaults={'name': 'Milagro'})
        sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        EcgRhythm.objects.get_or_create(name='Ritmo Sinusal (RS)')
        QuestionnaireSection.objects.create(code='A04_TEST', name='Synthetic selection', display_order=1)
        cls.patients = []
        cls.visits = []
        for pk, card, code, acronym, visit_pk in (
            (6101, 'A04-FIRST', '800000', 'A04_A', 9101),
            (6202, '6101', '6101', 'A04_B', 9202),
        ):
            institution = Institution.objects.create(acronym=acronym, name='Synthetic ' + acronym)
            patient = Patient.objects.create(pk=pk, id_card=card, first_names='Synthetic',
                last_name1=acronym, birth_date=date(1990 if pk == 6101 else 1995, 1, 1), birth_canton=canton,
                institution=institution, sex=sex, ethnicity=ethnicity, created_by=cls.user)
            visit = Visit.objects.create(pk=visit_pk, patient=patient, evaluator=cls.user,
                study_code=code, visit_date=date(2026, 1, 1), residence_canton=canton)
            cls.patients.append(patient)
            cls.visits.append(visit)

    def setUp(self):
        self.client.force_login(self.user)

    def export(self, ids):
        data, _, _ = generate_export_dataset(ids, format_type='csv')
        return pd.read_csv(BytesIO(data))

    def test_detail_and_form_use_primary_key_despite_card_and_code_collision(self):
        for path in ('pacientes', 'ficha'):
            for pk in ('6101', 'p6101', 'p_6101'):
                response = self.client.get(f'/clinical/api/{path}/{pk}/')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(str(response.json()['paciente']['id']), '6101')

    def test_detail_and_form_never_fall_back_to_study_code(self):
        for path in ('pacientes', 'ficha'):
            self.assertEqual(self.client.get(f'/clinical/api/{path}/800000/').status_code, 404)
            self.assertEqual(self.client.get(f'/clinical/api/{path}/pp6101/').status_code, 400)

    def test_save_invalid_id_does_not_fall_back_to_demographics(self):
        for selector in ({'idPaciente': '800000'}, {'idPaciente': 'pp6101'}, {}):
            response = self.client.post('/clinical/api/ficha/guardar/', {
                **selector, 'f_cedula': 'A04-FIRST', 'f_codigo': '800000', 'f_nombre': 'Wrong',
            }, content_type='application/json')
            self.assertIn(response.status_code, (400, 404))
        self.patients[0].refresh_from_db()
        self.assertEqual(self.patients[0].first_names, 'Synthetic')

    def test_save_rejects_contradictory_selectors(self):
        response = self.client.post('/clinical/api/ficha/guardar/?paciente=6101',
                                   {'idPaciente': '6202'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_save_updates_only_explicit_primary_key_even_with_other_patients_demographics(self):
        response = self.client.post('/clinical/api/ficha/guardar/',
            {'idPaciente': 'p6101', 'f_cedula': '6101', 'f_codigo': '6101', 'f_nombre': 'Changed'},
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.patients[0].refresh_from_db()
        self.patients[1].refresh_from_db()
        self.assertEqual(self.patients[0].first_names, 'Changed')
        self.assertEqual(self.patients[1].first_names, 'Synthetic')

    def test_pdf_without_selection_or_with_unknown_selection_never_generates_another(self):
        with patch('clinical.views.generate_clinical_sheet_pdf') as pdf:
            for query, status in (('', 400), ('?paciente=800000', 404), ('?historial=800000', 404),
                                  ('?paciente=6101&historial=800000', 404),
                                  ('?paciente=6101&historial=9202', 404), ('?paciente=pp6101', 400)):
                self.assertEqual(self.client.get('/clinical/ficha/pdf/' + query).status_code, status)
            pdf.assert_not_called()

    def test_pdf_uses_actual_visit_key_and_cross_checks_patient(self):
        with patch('clinical.views.generate_clinical_sheet_pdf', return_value=b'pdf') as pdf:
            response = self.client.get('/clinical/ficha/pdf/?paciente=p_6101&historial=h_9101')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(pdf.call_args.args[0].pk, 9101)
            self.assertEqual(self.client.get('/clinical/ficha/9101/pdf/?historial=9202').status_code, 400)

    def test_explicit_blank_template_still_works(self):
        with patch('clinical.views.generate_clinical_sheet_pdf', return_value=b'blank') as pdf:
            self.assertEqual(self.client.get('/clinical/ficha/pdf/?blank=1').status_code, 200)
            pdf.assert_called_once_with(None, is_blank=True)

    def test_batch_pdf_requires_every_patient_and_visit(self):
        with patch('clinical.views.generate_clinical_sheet_pdf') as pdf, patch('clinical.views._generate_zip_stream') as archive:
            for ids in ('6101,800000', '6101,all', '6101,,6202'):
                self.assertIn(self.client.get('/clinical/api/ficha/descargar-seleccionados/',
                                             {'patient_ids': ids}).status_code, (400, 404))
            self.visits[1].delete()
            self.assertEqual(self.client.get('/clinical/api/ficha/descargar-seleccionados/',
                                            {'patient_ids': '6101,6202'}).status_code, 404)
            pdf.assert_not_called()
            archive.assert_not_called()

    def test_batch_pdf_deduplicates_and_allows_both_institutions(self):
        with patch('clinical.views._generate_zip_stream', return_value=b'zip') as archive:
            response = self.client.get('/clinical/api/ficha/descargar-seleccionados/',
                                       {'patient_ids': 'p6101,p_6202,6101'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([v.pk for v in archive.call_args.args[0]], [9101, 9202])

    def test_delete_does_not_expand_to_another_patients_card_or_code(self):
        response = self.client.post('/clinical/api/ficha/eliminar/',
                                   {'patient_ids': [6101], 'password': self.password}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted_count'], 1)
        self.assertFalse(Patient.objects.filter(pk=6101).exists())
        self.assertTrue(Patient.objects.filter(pk=6202).exists())

    def test_mixed_invalid_delete_is_all_or_nothing(self):
        response = self.client.post('/clinical/api/ficha/eliminar/',
                                   {'patient_ids': [6101, 800000], 'password': self.password}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Patient.objects.filter(pk__in=[6101, 6202]).count(), 2)
        self.assertEqual(Visit.objects.filter(pk__in=[9101, 9202]).count(), 2)

    def test_dataset_collision_exports_exactly_one_record(self):
        frame = self.export([6101])
        self.assertEqual(len(frame), 1)
        self.assertEqual(int(frame.iloc[0]['EDAD']), 36)
        self.assertEqual(int(frame.iloc[0, 2]), 800000)

    def test_dataset_invalid_selection_never_falls_back_to_all(self):
        for ids in ([800000], [6101, 800000], [], ['all'], ['todos'], True, [True]):
            with self.subTest(ids=ids), self.assertRaises(RecordSelectionError):
                self.export(ids)

    def test_all_scope_exports_only_active_patients_even_when_none_are_active(self):
        Patient.objects.filter(pk=6202).update(status=Patient.Status.INACTIVE)
        self.assertEqual(len(self.export(None)), 1)
        with self.assertRaises(RecordSelectionError):
            self.export([6202])
        Patient.objects.update(status=Patient.Status.INACTIVE)
        self.assertEqual(len(self.export(None)), 0)

    def test_export_http_requires_explicit_all_scope_or_nonempty_selection(self):
        with patch('clinical.views.generate_export_dataset', return_value=(b'csv', 'test.csv', 'text/csv')) as export:
            url = '/clinical/api/export-dataset/'
            for payload in ({}, {'patient_ids': []}, {'scope': 'all', 'patient_ids': [6101]}):
                self.assertEqual(self.client.post(url, payload, content_type='application/json').status_code, 400)
            export.assert_not_called()
            for scope in ('all', 'todos'):
                self.assertEqual(self.client.post(url, {'scope': scope}, content_type='application/json').status_code, 200)
                self.assertIsNone(export.call_args.kwargs['patient_ids'])

    def test_export_http_validates_real_selection_and_supports_single_id_and_comma_list(self):
        url = '/clinical/api/export-dataset/'
        for ids, status in (('6101', 200), ('6101,6202', 200), ('6101,800000', 404),
                            ('6101,,6202', 400), ('all', 400), ('[6101]', 200)):
            response = self.client.get(url, {'format': 'csv', 'patient_ids': ids})
            self.assertEqual(response.status_code, status, response.content[:200])
            if status == 200:
                frame = pd.read_csv(BytesIO(response.content))
                self.assertEqual(len(frame), 2 if ids == '6101,6202' else 1)

    def test_share_rejects_partial_selection_before_creating_or_sending(self):
        with patch('security.services.email_service.send_secure_share_link_email') as send:
            response = self.client.post('/clinical/api/ficha/enviar-correo/',
                {'patient_ids': [6101, 800000], 'recipients': ['synthetic@example.invalid']}, content_type='application/json')
            self.assertEqual(response.status_code, 404)
            self.assertFalse(SecureShare.objects.exists())
            send.assert_not_called()

    def create_unlocked_share(self, *, multiple=False):
        token = 'synthetic-a04-token'
        share = SecureShare.objects.create(visit=self.visits[0], recipient_email='synthetic@example.invalid',
            token_hash=hashlib.sha256(token.encode()).hexdigest(), code_hash='unused',
            expires_at=timezone.now() + timedelta(hours=1), created_by=self.user)
        share.visits.set(self.visits if multiple else self.visits[:1])
        session = self.client.session
        session[f'share_unlocked_{share.pk}'] = True
        session.save()
        return share, '/clinical/compartir/' + token + '/'

    def test_shared_pdf_unknown_or_outside_document_does_not_consume_quota(self):
        share, url = self.create_unlocked_share()
        with patch('clinical.views.generate_clinical_sheet_pdf') as pdf:
            for vid, status in (('800000', 404), ('9202', 404), ('pp9101', 400)):
                self.assertEqual(self.client.get(url, {'descarga': 'pdf', 'visit_id': vid}).status_code, status)
            pdf.assert_not_called()
        share.refresh_from_db()
        self.assertEqual(share.download_count, 0)

    def test_shared_multiple_requires_document_but_valid_document_downloads(self):
        share, url = self.create_unlocked_share(multiple=True)
        with patch('clinical.views.generate_clinical_sheet_pdf', return_value=b'pdf') as pdf:
            self.assertEqual(self.client.get(url, {'descarga': 'pdf'}).status_code, 400)
            pdf.assert_not_called()
            self.assertEqual(self.client.get(url, {'descarga': 'pdf', 'visit_id': '9202'}).status_code, 200)
            self.assertEqual(pdf.call_args.args[0].pk, 9202)
        share.refresh_from_db()
        self.assertEqual(share.download_count, 1)

    def test_direct_download_on_unlock_rejects_an_explicit_unrelated_document(self):
        from django.contrib.auth.hashers import make_password
        share, url = self.create_unlocked_share()
        share.code_hash = make_password('123456')
        share.save(update_fields=['code_hash'])
        session = self.client.session
        del session[f'share_unlocked_{share.pk}']
        session.save()
        with patch('clinical.views.generate_clinical_sheet_pdf') as pdf:
            response = self.client.post(url, {'code': '123456', 'direct_download': '1', 'visit_id': '9202'})
            self.assertEqual(response.status_code, 404)
            pdf.assert_not_called()
        share.refresh_from_db()
        self.assertEqual(share.download_count, 0)
