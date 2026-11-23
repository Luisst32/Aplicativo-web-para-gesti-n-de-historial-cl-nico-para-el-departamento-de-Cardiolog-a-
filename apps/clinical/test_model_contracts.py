"""A17 regressions against real model fields and real dataset readers/writers."""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
from unittest.mock import patch

import pandas as pd
import pyreadr
import pyreadstat
from django.contrib.auth.models import Permission
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from catalog.models import (Country, Province, Canton, Institution, Sex, Ethnicity,
                            QuestionnaireSection, Question, AnswerOption)
from clinical.models import Patient, Visit, VisitAnswer, Echocardiogram
from clinical.services import sav_importer, sav_exporter
from clinical.services.importer.executor import _execute_staged_dataset
from security.models import User


class DatasetMetadataContractTests(SimpleTestCase):
    def test_numeric_sav_formats_hide_decimals_for_integer_columns(self):
        frame = pd.DataFrame({
            'VISITA': [1.0, 2.0],
            'MEDICION': [1.0, 2.43],
            'VACIA': [float('nan'), float('nan')],
        })

        formats = sav_exporter._adaptive_numeric_formats(
            frame,
            {'VISITA': 'F8.2', 'MEDICION': 'F8.2', 'VACIA': 'F8.2'},
        )

        self.assertEqual(formats['VISITA'], 'F8.0')
        self.assertEqual(formats['MEDICION'], 'F8.2')
        self.assertEqual(formats['VACIA'], 'F8.0')

    def test_metadata_matches_reader_label_contract(self):
        frame = pd.DataFrame({'ONE': [1], 'TWO': [2]})
        metadata = sav_importer.DatasetMetadata(frame, column_labels=['First label', None])
        self.assertEqual(metadata.column_names_to_labels, {'ONE': 'First label', 'TWO': None})
        self.assertEqual(sav_importer.DatasetMetadata(frame).column_names_to_labels,
                         {'ONE': 'ONE', 'TWO': 'TWO'})

    def test_actual_csv_and_rds_readers_supply_named_labels(self):
        frame = pd.DataFrame({'SYNTHETIC_COLUMN': [1.0]})
        with TemporaryDirectory() as directory:
            for extension in ('.csv', '.rds'):
                with self.subTest(extension=extension):
                    path = Path(directory) / ('synthetic' + extension)
                    if extension == '.csv':
                        frame.to_csv(path, index=False)
                    else:
                        pyreadr.write_rds(str(path), frame)
                    values, metadata = sav_importer._read_dataset_file(path, path.name)
                    self.assertEqual(metadata.number_rows, 1)
                    self.assertEqual(metadata.column_names_to_labels['SYNTHETIC_COLUMN'], 'SYNTHETIC_COLUMN')
                    self.assertEqual(values['SYNTHETIC_COLUMN'], [1.0])


class ClinicalModelContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='contract_actor', email='actor@example.invalid')
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        province, _ = Province.objects.get_or_create(country=country, iso_code='EC-G', defaults={'name': 'Guayas'})
        canton, _ = Canton.objects.get_or_create(province=province, dpa_code='0910', defaults={'name': 'Milagro'})
        institution, _ = Institution.objects.get_or_create(acronym='UNEMI', defaults={'name': 'Synthetic institution'})
        sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        Sex.objects.get_or_create(sex_id=2, defaults={'name': 'Mujer'})
        ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        cls.patient = Patient.objects.create(
            institution=institution, id_card='0923485718', first_names='Synthetic',
            last_name1='Contract', birth_date=date(2000, 12, 15), birth_canton=canton,
            sex=sex, ethnicity=ethnicity, created_by=cls.user,
        )
        cls.visit = Visit.objects.create(patient=cls.patient, evaluator=cls.user,
                                         study_code='701', visit_date=date(2026, 12, 14), residence_canton=canton)
        cls.section = QuestionnaireSection.objects.create(code='A17_TEST', name='Synthetic', display_order=1)

    def setUp(self):
        self.folder = self.enterContext(TemporaryDirectory(prefix='cardio-contract-'))
        self.enterContext(override_settings(IMPORT_TEMP_ROOT=Path(self.folder) / 'private'))
        self.client.force_login(self.user)

    def answer(self, code, *, label=None, number=None, text=None):
        question = Question.objects.create(section=self.section, code=code, text=code,
                                           response_type='OPCION' if label else 'TEXTO', display_order=1)
        option = AnswerOption.objects.create(question=question, label=label, display_order=1) if label else None
        return VisitAnswer.objects.create(visit=self.visit, question=question,
                                          selected_option=option, numeric_value=number, text_value=text)

    def export_frame(self, format_type='csv', privacy_mode=False):
        data, _, _ = sav_exporter.generate_export_dataset([self.patient.pk], format_type=format_type, privacy_mode=privacy_mode)
        if format_type == 'csv':
            return pd.read_csv(BytesIO(data), dtype={'C.I': str, 'TELÉFONO': str})
        path = Path(self.folder) / 'synthetic-export.sav'
        path.write_bytes(data)
        frame, _ = pyreadstat.read_sav(str(path))
        return frame

    def import_format(self, extension):
        column = 'A17_NEW_' + extension.upper()
        frame = pd.DataFrame({'CODIGO': [701.0], 'UNIVERSIDAD': [1.0], column: ['Synthetic answer']})
        path = Path(self.folder) / ('synthetic.' + extension)
        if extension == 'csv':
            frame.to_csv(path, index=False)
        else:
            pyreadr.write_rds(str(path), frame)
        analysis = sav_importer.analyze_sav_file(BytesIO(path.read_bytes()), path.name, self.user)
        self.assertTrue(analysis['success'])
        result = sav_importer.execute_sav_import(analysis['temp_token'], self.user)
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 1)
        question = Question.objects.get(code=column.lower())
        self.assertEqual(question.text, column)
        self.assertEqual(VisitAnswer.objects.get(visit=self.visit, question=question).text_value, 'Synthetic answer')

    def test_actual_csv_import_with_new_column_creates_question_and_answer(self):
        self.import_format('csv')

    def test_actual_rds_import_with_new_column_creates_question_and_answer(self):
        self.import_format('rds')

    def test_csv_export_age_uses_evaluation_date_before_birthday(self):
        frame = self.export_frame()
        self.assertEqual(len(frame.columns), 535)
        self.assertIn('ECOCARDIOGRAMA', frame.columns)
        self.assertIn('C.I', frame.columns)
        self.assertEqual(str(frame.iloc[0]['C.I']), str(self.patient.id_card))
        self.assertEqual(frame.iloc[0]['EDAD'], 25)

    def test_csv_export_age_changes_on_birthday(self):
        self.visit.visit_date = date(2026, 12, 15)
        self.visit.save(update_fields=['visit_date'])
        self.assertEqual(self.export_frame().iloc[0]['EDAD'], 26)

    def test_sav_export_uses_full_template_and_can_be_read_back(self):
        frame = self.export_frame('sav')
        self.assertEqual(len(frame.columns), 535)
        self.assertIn('ECOCARDIOGRAMA', frame.columns)
        self.assertIn('C.I', frame.columns)
        self.assertIn('NOMBRES', frame.columns)
        self.assertEqual(str(frame.iloc[0]['C.I']), str(self.patient.id_card))
        self.assertEqual(frame.iloc[0]['EDAD'], 25)
        self.assertFalse(pd.isna(frame.iloc[0]['FECHA']))

    def test_export_privacy_mode_excludes_sensitive_data(self):
        frame_priv = self.export_frame('csv', privacy_mode=True)
        self.assertEqual(len(frame_priv.columns), 529)
        self.assertNotIn('C.I', frame_priv.columns)
        self.assertNotIn('NOMBRES', frame_priv.columns)
        self.assertNotIn('APELLIDO1', frame_priv.columns)
        self.assertNotIn('APELLIDO2', frame_priv.columns)
        self.assertNotIn('TELÉFONO', frame_priv.columns)
        self.assertNotIn('CORREO', frame_priv.columns)
        self.assertIn('ECOCARDIOGRAMA', frame_priv.columns)

    def test_multiformat_export_supports_zsav_rds_and_rdata(self):
        # Prueba exportación comprimida ZSAV
        zsav_data, zsav_name, zsav_type = sav_exporter.generate_export_dataset([self.patient.pk], format_type='zsav')
        self.assertTrue(zsav_name.endswith('.zsav'))
        self.assertEqual(zsav_type, 'application/x-spss-sav')
        self.assertGreater(len(zsav_data), 0)

        # Prueba exportación RStudio RDS
        rds_data, rds_name, rds_type = sav_exporter.generate_export_dataset([self.patient.pk], format_type='rds')
        self.assertTrue(rds_name.endswith('.rds'))
        self.assertEqual(rds_type, 'application/octet-stream')
        p_rds = Path(self.folder) / 'test.rds'
        p_rds.write_bytes(rds_data)
        rds_read = pyreadr.read_r(str(p_rds))[None]
        self.assertEqual(len(rds_read.columns), 535)
        self.assertIn('C.I', rds_read.columns)
        self.assertIn('ECOCARDIOGRAMA', rds_read.columns)

        # Prueba exportación RStudio RData
        rdata_data, rdata_name, rdata_type = sav_exporter.generate_export_dataset([self.patient.pk], format_type='rdata')
        self.assertTrue(rdata_name.endswith('.RData'))
        p_rdata = Path(self.folder) / 'test.RData'
        p_rdata.write_bytes(rdata_data)
        rdata_read = pyreadr.read_r(str(p_rdata))['CardioUnemi']
        self.assertEqual(len(rdata_read.columns), 535)
        self.assertIn('C.I', rdata_read.columns)
        self.assertIn('ECOCARDIOGRAMA', rdata_read.columns)

    def test_echo_export_does_not_read_nonexistent_fractional_shortening(self):
        Echocardiogram.objects.create(visit=self.visit, lvef_percentage=Decimal('61.0'))
        frame = self.export_frame()
        self.assertTrue(pd.isna(frame.iloc[0]['FRACCION_ACORTAMIENTO_FA']))
        self.assertEqual(frame.iloc[0]['FRACCION_EYECCION_TEICHOLZ'], 61)

    def test_fractional_shortening_is_preserved_from_recorded_answer(self):
        self.answer('fraccion_acortamiento_fa', number=Decimal('32.5'))
        Echocardiogram.objects.create(visit=self.visit)
        self.assertEqual(self.export_frame().iloc[0]['FRACCION_ACORTAMIENTO_FA'], 32.5)

    def test_reference_sav_round_trip_preserves_rows_and_schema(self):
        source = Path(settings.BASE_DIR).parent / 'datos' / 'MATRIZ CARDIOESPOL 2026 FINAL.sav'
        if not source.exists():
            self.skipTest('No está disponible la matriz SPSS de referencia local.')

        source_frame, _ = pyreadstat.read_sav(str(source), apply_value_formats=False)
        staged_source = Path(self.folder) / 'reference-source.sav'
        shutil.copy2(source, staged_source)
        result = _execute_staged_dataset(staged_source, self.user)
        self.assertTrue(result['success'], result)
        imported_ids = list(
            Visit.objects.filter(source_dataset__isnull=False)
            .order_by('source_row_index')
            .values_list('patient_id', flat=True)
        )
        self.assertGreater(len(imported_ids), 0)

        exported, _, _ = sav_exporter.generate_export_dataset(imported_ids, format_type='sav')
        output_path = Path(self.folder) / 'round-trip.sav'
        output_path.write_bytes(exported)
        output_frame, _ = pyreadstat.read_sav(str(output_path), apply_value_formats=False)
        self.assertEqual(list(output_frame.columns), list(source_frame.columns))
        self.assertEqual(len(output_frame), len(source_frame))
        pd.testing.assert_frame_equal(source_frame, output_frame, check_dtype=False, check_names=True)

    def test_import_export_round_trip_preserves_duplicate_prefix_columns(self):
        frame = pd.DataFrame({
            'UNIVERSIDAD': [1.0, 2.0],
            'CODIGONUEV': [432.0, 433.0],
            'NOMBRES': ['Ana', 'Luis'],
            'APELLIDO1': ['Uno', 'Dos'],
            'APELLIDO2': ['', 'Tres'],
            'C.I': ['0923485734', '0923485742'],
            'FECHA': [date(2026, 3, 23), date(2026, 3, 24)],
            'MOMENTO': [datetime(2026, 3, 23, 8, 15, 30), datetime(2026, 3, 24, 9, 45, 0)],
            'FECHA_DE_NACIMIENTO': [date(1990, 1, 2), date(1991, 2, 3)],
            'SEXO': [1.0, 2.0],
            'CIUDAD': [4.0, 4.0],
            'PROVINCIA': [1.0, 1.0],
            'FUNCION_DIASTOLICA_VENTRICULO_IZQUIERDO': [1.0, 2.0],
            'FUNCION_DIASTOLICA_VENTRICULO_DERECHO': [2.0, 1.0],
        })
        with TemporaryDirectory(prefix='cardio-roundtrip-') as directory:
            source = Path(directory) / 'source.sav'
            pyreadstat.write_sav(frame, str(source))
            source_frame, _ = pyreadstat.read_sav(str(source), apply_value_formats=False)
            staged_source = Path(directory) / 'staged-source.sav'
            shutil.copy2(source, staged_source)
            result = _execute_staged_dataset(staged_source, self.user)
            self.assertTrue(result['success'], result)
            self.assertEqual(result['errors'], [], result)
            ids = list(Visit.objects.filter(source_dataset__isnull=False).values_list('patient_id', flat=True))
            self.assertGreater(len(ids), 0, result)
            exported, _, _ = sav_exporter.generate_export_dataset(ids, format_type='sav')
            output = Path(directory) / 'output.sav'
            output.write_bytes(exported)
            output_frame, _ = pyreadstat.read_sav(str(output), apply_value_formats=False)
            self.assertEqual(list(output_frame.columns), list(source_frame.columns))
            pd.testing.assert_frame_equal(source_frame, output_frame, check_dtype=False, check_names=True)

    def test_selected_option_label_and_zero_survive_export(self):
        self.answer('a17_choice', label='Sí')
        self.answer('a17_zero', number=Decimal('0'))
        template = {'columns': ['A17_CHOICE', 'A17_ZERO'],
                    'dtypes': {'A17_CHOICE': 'float64', 'A17_ZERO': 'float64'},
                    'value_labels': {'A17_CHOICE': {1: 'Sí'}}, 'labels': {},
                    'lbl_to_val_map': {'A17_CHOICE': {'SÍ': 1}}}
        with patch.object(sav_exporter, 'get_sav_template_metadata', return_value=template):
            row = self.export_frame().iloc[0]
        self.assertEqual(row['A17_CHOICE'], 1)
        self.assertEqual(row['A17_ZERO'], 0)

    def test_dashboard_handles_real_selected_option_label(self):
        self.answer('f_estudios', label='Postgrado')
        response = self.client.get('/dashboard/api/data/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['records'][0]['nivel_estudios'], 'Postgrado')
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)

    def test_api_export_dataset_includes_sensitive_by_default(self):
        response = self.client.post('/clinical/api/export-dataset/', {
            'format': 'csv',
            'scope': 'all'
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        frame = pd.read_csv(BytesIO(response.content), dtype={'C.I': str, 'TELÉFONO': str})
        self.assertEqual(len(frame.columns), 535)
        self.assertIn('C.I', frame.columns)
        self.assertIn('NOMBRES', frame.columns)
        self.assertIn('APELLIDO1', frame.columns)
        self.assertIn('APELLIDO2', frame.columns)
        self.assertIn('TELÉFONO', frame.columns)
        self.assertIn('CORREO', frame.columns)
        self.assertEqual(str(frame.iloc[0]['C.I']), '0923485718')
        self.assertEqual(str(frame.iloc[0]['NOMBRES']), 'Synthetic')
        self.assertEqual(str(frame.iloc[0]['APELLIDO1']), 'Contract')

    def test_api_export_dataset_excludes_sensitive_when_privacy_mode_is_true(self):
        response = self.client.post('/clinical/api/export-dataset/', {
            'format': 'csv',
            'scope': 'all',
            'privacy_mode': True
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        frame = pd.read_csv(BytesIO(response.content))
        self.assertEqual(len(frame.columns), 529)
        self.assertNotIn('C.I', frame.columns)
        self.assertNotIn('NOMBRES', frame.columns)
        self.assertNotIn('APELLIDO1', frame.columns)
        self.assertNotIn('APELLIDO2', frame.columns)
        self.assertNotIn('TELÉFONO', frame.columns)
        self.assertNotIn('CORREO', frame.columns)
        self.assertIn('ECOCARDIOGRAMA', frame.columns)

    def test_form_get_api_populates_phone_email_and_normalized_controls(self):
        self.patient.phone = '0997965072'
        self.patient.email = 'test@example.com'
        self.patient.save()
        self.answer('f_estado_civil', label='CASADO/A')
        self.answer('f_convive_con', label='Con sus hijos')
        self.answer('f_estudios', label='Postgrado')
        self.answer('f_hijos', label='2 Hijos')
        self.answer('peso_corporal', label='Obesidad grado 1 (leve)')

        response = self.client.get(f'/clinical/api/ficha/{self.patient.patient_id}/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['paciente']['telefono'], '0997965072')
        self.assertEqual(payload['paciente']['correo'], 'test@example.com')
        self.assertEqual(payload['datos']['f_telefono'], '0997965072')
        self.assertEqual(payload['datos']['f_correo'], 'test@example.com')
        self.assertEqual(payload['datos']['f_estado_civil'], '2_casado')
        self.assertEqual(payload['datos']['f_convive_con'], '4')
        self.assertEqual(payload['datos']['f_estudios'], '7')
        self.assertEqual(payload['datos']['f_hijos'], '2')
        self.assertEqual(payload['datos']['r_sobrepeso'], 'Si')

    def test_form_get_api_resolves_phone_and_email_from_visit_answers_when_empty_on_patient(self):
        self.patient.phone = None
        self.patient.email = None
        self.patient.save()
        self.answer('telefono', text='0988776655')
        self.answer('correo', text='fallback@test.org')

        response = self.client.get(f'/clinical/api/ficha/{self.patient.patient_id}/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['paciente']['telefono'], '0988776655')
        self.assertEqual(payload['paciente']['correo'], 'fallback@test.org')
        self.assertEqual(payload['datos']['f_telefono'], '0988776655')
        self.assertEqual(payload['datos']['f_correo'], 'fallback@test.org')
