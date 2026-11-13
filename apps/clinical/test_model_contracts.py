"""A17 regressions against real model fields and real dataset readers/writers."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import pyreadr
import pyreadstat
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase, override_settings

from catalog.models import (Country, Province, Canton, Institution, Sex, Ethnicity,
                            QuestionnaireSection, Question, AnswerOption)
from clinical.models import Patient, Visit, VisitAnswer, Echocardiogram
from clinical.services import sav_importer, sav_exporter
from security.models import User


class DatasetMetadataContractTests(SimpleTestCase):
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

    def export_frame(self, format_type='csv'):
        data, _, _ = sav_exporter.generate_export_dataset([self.patient.pk], format_type=format_type)
        if format_type == 'csv':
            return pd.read_csv(BytesIO(data))
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
        self.assertEqual(len(frame.columns), 342)
        self.assertEqual(frame.iloc[0]['EDAD'], 25)

    def test_csv_export_age_changes_on_birthday(self):
        self.visit.visit_date = date(2026, 12, 15)
        self.visit.save(update_fields=['visit_date'])
        self.assertEqual(self.export_frame().iloc[0]['EDAD'], 26)

    def test_sav_export_uses_full_template_and_can_be_read_back(self):
        frame = self.export_frame('sav')
        self.assertEqual(len(frame.columns), 342)
        self.assertEqual(frame.iloc[0]['EDAD'], 25)
        self.assertFalse(pd.isna(frame.iloc[0]['FECHA']))

    def test_echo_export_does_not_read_nonexistent_fractional_shortening(self):
        Echocardiogram.objects.create(visit=self.visit, lvef_percentage=Decimal('61.0'))
        frame = self.export_frame()
        self.assertTrue(pd.isna(frame.iloc[0]['FRACCION_ACORTAMIENTO_FA']))
        self.assertEqual(frame.iloc[0]['FRACCION_EYECCION_TEICHOLZ'], 61)

    def test_fractional_shortening_is_preserved_from_recorded_answer(self):
        self.answer('fraccion_acortamiento_fa', number=Decimal('32.5'))
        Echocardiogram.objects.create(visit=self.visit)
        self.assertEqual(self.export_frame().iloc[0]['FRACCION_ACORTAMIENTO_FA'], 32.5)

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
