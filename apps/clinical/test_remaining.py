from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity
from security.models import User
from clinical.models import Patient, Visit, Anthropometry, VitalSigns
from clinical.services.measurements import save_measurements
from clinical.services.import_tickets import store_upload, InvalidImportTicket

class MeasurementIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user(username='remaining_actor',email='remaining@example.invalid')
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        country,_=Country.objects.get_or_create(iso_alpha3='ECU',defaults={'name':'Ecuador'})
        province,_=Province.objects.get_or_create(country=country,iso_code='EC-G',defaults={'name':'Guayas'})
        canton,_=Canton.objects.get_or_create(province=province,dpa_code='0910',defaults={'name':'Milagro'})
        institution=Institution.objects.create(acronym='REMAIN',name='Synthetic')
        sex,_=Sex.objects.get_or_create(sex_id=1,defaults={'name':'Hombre'})
        ethnicity,_=Ethnicity.objects.get_or_create(name='Mestizo')
        cls.patient=Patient.objects.create(institution=institution,id_card='SYNTHETIC',first_names='Synthetic',last_name1='Test',birth_date=date(1990,1,1),birth_canton=canton,sex=sex,ethnicity=ethnicity,created_by=cls.user)
        cls.visit=Visit.objects.create(patient=cls.patient,evaluator=cls.user,study_code='9',visit_date=date(2026,1,1),residence_canton=canton)
    def test_omitted_values_never_create_measurements(self):
        self.assertEqual(save_measurements(self.visit,{}),(None,None))
        self.assertEqual(save_measurements(self.visit,{'f_peso':'','f_talla':''}),(None,None))
    def test_partial_patch_preserves_other_measurements(self):
        Anthropometry.objects.create(visit=self.visit,weight_kg=110,height_cm=180,waist_circumference_cm=100)
        VitalSigns.objects.create(visit=self.visit,systolic_bp=170,diastolic_bp=90)
        save_measurements(self.visit,{'f_peso':'105'})
        ant,vs=save_measurements(self.visit,{})
        self.assertEqual(float(ant.weight_kg),105)
        self.assertEqual(float(ant.height_cm),180)
        self.assertEqual(vs.systolic_bp,170)
    def test_incomplete_measurement_creation_is_rejected(self):
        with self.assertRaises(ValidationError):save_measurements(self.visit,{'f_peso':'105'})
        self.assertFalse(Anthropometry.objects.exists())
        for data in ({'f_tas':'170.5','f_tsi':'90'}, {'f_peso':'NaN','f_talla':'180'}):
            with self.assertRaises(ValidationError):
                save_measurements(self.visit,data)
        self.assertFalse(VitalSigns.objects.exists())
    def test_api_omitted_values_and_pagination(self):
        self.client.force_login(self.user)
        response=self.client.get('/clinical/api/pacientes/',{'page_size':1})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['total'],1)
        self.assertIsNone(response.json()['pacientes'][0]['peso'])
        self.assertEqual(self.client.get('/clinical/api/pacientes/',{'page_size':201}).status_code,400)
    def test_media_is_never_public(self):
        self.assertEqual(self.client.get('/media/synthetic.csv').status_code,404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/media/synthetic.csv').status_code,404)

    def test_list_query_count_does_not_grow_per_patient(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        self.client.force_login(self.user)
        self.client.get('/clinical/api/pacientes/')
        with CaptureQueriesContext(connection) as before:
            self.client.get('/clinical/api/pacientes/')
        for index in range(5):
            patient=Patient.objects.create(institution=self.patient.institution,id_card='SYNTHETIC'+str(index),
                first_names='Synthetic',last_name1='Extra',birth_date=date(1990,1,1),birth_canton=self.patient.birth_canton,
                sex=self.patient.sex,ethnicity=self.patient.ethnicity,created_by=self.user)
            Visit.objects.create(patient=patient,evaluator=self.user,study_code='EXTRA'+str(index),visit_date=date(2026,1,1),residence_canton=self.patient.birth_canton)
        with CaptureQueriesContext(connection) as after:
            response=self.client.get('/clinical/api/pacientes/',{'page_size':2})
        self.assertEqual(response.json()['total'],6)
        self.assertEqual(len(response.json()['pacientes']),2)
        self.assertEqual(response.json()['next_page'],2)
        self.assertLessEqual(len(after),len(before)+1)
        with CaptureQueriesContext(connection) as whole_cohort:
            response=self.client.get('/clinical/api/pacientes/')
        self.assertEqual(len(response.json()['pacientes']),6)
        self.assertLessEqual(len(whole_cohort),len(before)+1)

    def test_invalid_clinical_values_return_400_and_roll_back_name(self):
        self.client.force_login(self.user)
        for invalid in ({'f_fecha_nac':'invalid'}, {'renal_creatinina':'invalid'}):
            response=self.client.post('/clinical/api/ficha/guardar/',{'idPaciente':self.patient.pk,'f_nombre':'Must rollback',**invalid},content_type='application/json')
            self.assertEqual(response.status_code,400,response.content)
            self.patient.refresh_from_db()
            self.assertEqual(self.patient.first_names,'Synthetic')

class UploadBoundTests(SimpleTestCase):
    def test_streamed_limit_and_cleanup(self):
        from types import SimpleNamespace
        with TemporaryDirectory() as directory, override_settings(IMPORT_TEMP_ROOT=Path(directory)/'private',IMPORT_MAX_BYTES=8):
            from clinical.upload_limits import ImportSizeLimitHandler
            from django.core.files.uploadhandler import StopUpload
            with self.assertRaises(StopUpload):
                ImportSizeLimitHandler().receive_data_chunk(b'0123456789',0)
            with self.assertRaises(InvalidImportTicket):store_upload(BytesIO(b'0123456789'),'synthetic.csv',SimpleNamespace(pk=1))
            self.assertEqual(list((Path(directory)/'private').iterdir()),[])
