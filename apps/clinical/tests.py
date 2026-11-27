import datetime
import json
from decimal import Decimal
from django.urls import reverse
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity, StaffCategory
from clinical.models import Patient, Visit, Anthropometry, VitalSigns, VisitAnswer
from clinical.validators import (
    validate_ecuadorian_id,
    validate_clinical_ranges,
    validate_email_address,
    validate_ecuadorian_phone,
)
from clinical.pdf import generate_clinical_sheet_pdf
from audit.models import ChangeLog
from audit.services import register_audit_log

User = get_user_model()


class EcuadorianIdValidatorTests(SimpleTestCase):
    def test_valid_cedula(self):
        # Cédulas válidas con algoritmo módulo 10
        self.assertTrue(validate_ecuadorian_id('0923485718'))
        self.assertTrue(validate_ecuadorian_id('1710034065'))

    def test_invalid_length_and_characters(self):
        self.assertFalse(validate_ecuadorian_id(''))
        self.assertFalse(validate_ecuadorian_id('12345'))
        self.assertFalse(validate_ecuadorian_id('092348571A'))
        self.assertFalse(validate_ecuadorian_id(None))

    def test_invalid_checksum(self):
        # Último dígito incorrecto
        self.assertFalse(validate_ecuadorian_id('0923485719'))


class EmailAndPhoneValidatorTests(SimpleTestCase):
    def test_valid_emails(self):
        self.assertTrue(validate_email_address('cvillacres@unemi.edu.ec'))
        self.assertTrue(validate_email_address('doctor.cardiologia@hospital.gob.ec'))
        self.assertTrue(validate_email_address('paciente123@gmail.com'))

    def test_invalid_emails(self):
        self.assertFalse(validate_email_address(''))
        self.assertFalse(validate_email_address(None))
        self.assertFalse(validate_email_address('correo_sin_arroba'))
        self.assertFalse(validate_email_address('correo@sinpunto'))
        self.assertFalse(validate_email_address('correo@.com'))
        self.assertFalse(validate_email_address('@dominio.com'))

    def test_valid_ecuadorian_phones(self):
        self.assertTrue(validate_ecuadorian_phone('0987654321'))
        self.assertTrue(validate_ecuadorian_phone('0991234567'))
        self.assertTrue(validate_ecuadorian_phone('+593987654321'))
        self.assertTrue(validate_ecuadorian_phone('042971234'))
        self.assertTrue(validate_ecuadorian_phone('+59342971234'))

    def test_invalid_ecuadorian_phones(self):
        self.assertFalse(validate_ecuadorian_phone(''))
        self.assertFalse(validate_ecuadorian_phone(None))
        self.assertFalse(validate_ecuadorian_phone('12345'))
        self.assertFalse(validate_ecuadorian_phone('0812345678'))
        self.assertFalse(validate_ecuadorian_phone('09876543210123'))



class ClinicalRangeValidatorTests(SimpleTestCase):
    def test_valid_ranges(self):
        data = {
            'weight_kg': 70.0,
            'height_cm': 170.0,
            'waist_circumference_cm': 85.0,
            'systolic_bp': 120,
            'diastolic_bp': 80,
            'oxygen_saturation': 98,
            'heart_rate': 72
        }
        errores = validate_clinical_ranges(data)
        self.assertEqual(len(errores), 0)

    def test_out_of_range_tas_and_weight(self):
        data = {
            'weight_kg': 10.0,   # Rango: 20 - 350 kg
            'height_cm': 170.0,
            'systolic_bp': 350,  # Rango: 50 - 300 mmHg
        }
        errores = validate_clinical_ranges(data)
        self.assertEqual(len(errores), 2)


class ClinicalCRUDAndIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='doctor_test',
            email='doctor@unemi.edu.ec',
            password='password123',
            first_name='María',
            last_name='Pérez'
        )
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        self.country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        self.province, _ = Province.objects.get_or_create(country=self.country, iso_code='EC-G', defaults={'name': 'Guayas'})
        self.canton, _ = Canton.objects.get_or_create(province=self.province, dpa_code='0910', defaults={'name': 'Milagro'})
        self.institution, _ = Institution.objects.get_or_create(acronym='UNEMI', defaults={'name': 'Universidad Estatal de Milagro'})
        self.sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        self.ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        self.staff_cat, _ = StaffCategory.objects.get_or_create(name='PDI')

    def test_patient_visit_and_pdf_generation(self):
        # 1. Crear Paciente
        patient = Patient.objects.create(
            institution=self.institution,
            id_card='0923485712',
            first_names='Juan Carlos',
            last_name1='Pérez',
            last_name2='Gómez',
            birth_date=datetime.date(1985, 2, 9),
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            email='jperez@unemi.edu.ec',
            created_by=self.user
        )
        self.assertEqual(patient.full_name, 'Juan Carlos Pérez Gómez')

        # 2. Crear Visita
        visit = Visit.objects.create(
            patient=patient,
            evaluator=self.user,
            visit_number=1,
            study_code='0499/2026',
            visit_date=datetime.date(2026, 2, 10),
            staff_category=self.staff_cat,
            residence_canton=self.canton,
            faculty='Ciencias de la Salud'
        )
        self.assertEqual(visit.study_year, 2026)

        # 3. Antropometría y Signos Vitales
        ant = Anthropometry.objects.create(
            visit=visit,
            weight_kg=Decimal('74.00'),
            height_cm=Decimal('172.0'),
            waist_circumference_cm=Decimal('88.0')
        )
        self.assertAlmostEqual(float(ant.bmi), 25.01, places=1)

        vs = VitalSigns.objects.create(
            visit=visit,
            systolic_bp=120,
            diastolic_bp=80,
            oxygen_saturation=98,
            heart_rate=72
        )
        self.assertEqual(vs.systolic_bp, 120)

        # 4. Auditoría
        log = register_audit_log(
            user=self.user,
            table_name='patient',
            record_key=patient.patient_id,
            action='INSERT',
            new_value={'name': patient.full_name}
        )
        self.assertIsNotNone(log)
        self.assertEqual(ChangeLog.objects.filter(record_key=str(patient.patient_id)).count(), 1)

        # 5. Generación de PDF (HU-17)
        pdf_bytes = generate_clinical_sheet_pdf(visit)
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_list_view_dynamic_filters(self):
        self.client.force_login(self.user)
        # 1. Sin pacientes en 2027, el año 2027 NO debe aparecer en el filtro
        resp_inicial = self.client.get(reverse('clinical:list'))
        self.assertEqual(resp_inicial.status_code, 200)
        self.assertNotIn(2027, resp_inicial.context['available_years'])

        # 2. Al registrar un paciente con visita en 2027, debe detectarse dinámicamente
        patient_2027 = Patient.objects.create(
            institution=self.institution,
            id_card='0928374651',
            first_names='Ana',
            last_name1='López',
            birth_date=datetime.date(1990, 5, 12),
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            created_by=self.user,
        )
        Visit.objects.create(
            patient=patient_2027,
            evaluator=self.user,
            study_code='0099/2027',
            visit_date=datetime.date(2027, 3, 15),
            residence_canton=self.canton,
            staff_category=self.staff_cat,
        )
        resp = self.client.get(reverse('clinical:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('available_years', resp.context)
        self.assertIn(2027, resp.context['available_years'])
        self.assertIn('available_estamentos', resp.context)
        est_codes = [e['code'] for e in resp.context['available_estamentos']]
        self.assertIn('PDI', est_codes)

    def test_patient_next_code_api(self):
        self.client.force_login(self.user)
        # Código inicial cuando no hay visitas numéricas
        resp = self.client.get(reverse('clinical:api_patient_next_code'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertIn('next_code', data)

        # Crear visita con código 150
        patient = Patient.objects.create(
            institution=self.institution,
            first_names='Prueba',
            last_name1='Codigo',
            birth_date=datetime.date(1990, 1, 1),
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            created_by=self.user,
        )
        Visit.objects.create(
            patient=patient,
            evaluator=self.user,
            study_code='150',
            visit_date=datetime.date(2026, 1, 1),
            residence_canton=self.canton,
            staff_category=self.staff_cat,
        )
        resp2 = self.client.get(reverse('clinical:api_patient_next_code'))
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2.get('next_code'), '151')

    def test_patient_create_api_separated_names_and_validators(self):
        self.client.force_login(self.user)
        # 1. Intento con correo inválido
        payload_invalid_email = {
            'codigo': '201',
            'first_names': 'Carlos Alberto',
            'last_name1': 'Zambrano',
            'last_name2': 'Mendoza',
            'correo': 'correo_invalido_sin_dominio',
            'telefono': '0987654321',
            'sexo': 'Hombre',
            'fecha_nacimiento': '1992-06-15',
            'institucion': 'UNEMI',
            'estamento': 'PDI',
        }
        resp = self.client.post(
            reverse('clinical:api_patient_create'),
            data=json.dumps(payload_invalid_email),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('correo electrónico', resp.json().get('error', '').lower())

        # 2. Intento con teléfono inválido
        payload_invalid_phone = {
            'codigo': '202',
            'first_names': 'Carlos Alberto',
            'last_name1': 'Zambrano',
            'last_name2': 'Mendoza',
            'correo': 'carlos.zambrano@unemi.edu.ec',
            'telefono': '123456',  # Inválido en Ecuador
            'sexo': 'Hombre',
            'fecha_nacimiento': '1992-06-15',
            'institucion': 'UNEMI',
            'estamento': 'PDI',
        }
        resp2 = self.client.post(
            reverse('clinical:api_patient_create'),
            data=json.dumps(payload_invalid_phone),
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('teléfono', resp2.json().get('error', '').lower())

        # 3. Creación exitosa con nombres separados y datos válidos
        payload_valid = {
            'codigo': '203',
            'first_names': 'Carlos Alberto',
            'last_name1': 'Zambrano',
            'last_name2': 'Mendoza',
            'correo': 'carlos.zambrano@unemi.edu.ec',
            'telefono': '0987654321',
            'sexo': 'Hombre',
            'fecha_nacimiento': '1992-06-15',
            'institucion': 'UNEMI',
            'estamento': 'PDI',
        }
        resp3 = self.client.post(
            reverse('clinical:api_patient_create'),
            data=json.dumps(payload_valid),
            content_type='application/json'
        )
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.json()
        self.assertTrue(data3.get('success'))
        self.assertEqual(data3.get('paciente', {}).get('nombre'), 'Carlos Alberto Zambrano Mendoza')



class SavImporterTests(TestCase):
    def setUp(self):
        import tempfile
        from django.test import override_settings
        private_dir = self.enterContext(tempfile.TemporaryDirectory(prefix='cardio-import-test-'))
        self.enterContext(override_settings(IMPORT_TEMP_ROOT=private_dir))
        self.user = User.objects.create_user(
            username='evaluador_sav',
            password='Password123!',
            email='evaluador@unemi.edu.ec'
        )
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        self.client.force_login(self.user)

    def test_analyze_without_file_fails(self):
        response = self.client.post('/clinical/api/import-sav/analyze/')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get('success'))

    def test_analyze_invalid_extension_fails(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_file = SimpleUploadedFile("datos.txt", b"dummy content")
        response = self.client.post('/clinical/api/import-sav/analyze/', {'file': fake_file})
        self.assertEqual(response.status_code, 400)
        self.assertIn("SPSS", response.json().get('error', ''))

    def test_execute_without_token_fails(self):
        response = self.client.post(
            '/clinical/api/import-sav/execute/',
            data='{}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_execute_sav_import_duplicate_reporting(self):
        from unittest.mock import patch, MagicMock
        from pathlib import Path
        from django.conf import settings
        from apps.clinical.services.sav_importer import execute_sav_import

        inst_unemi, _ = Institution.objects.get_or_create(acronym='UNEMI', defaults={'name': 'Universidad Estatal de Milagro'})
        sex_h, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        eth, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        prov, _ = Province.objects.get_or_create(iso_code='EC-G', defaults={'name': 'Guayas'})
        cant, _ = Canton.objects.get_or_create(dpa_code='0910', defaults={'province': prov, 'name': 'Milagro'})

        p = Patient.objects.create(
            institution=inst_unemi,
            id_card='0900000001',
            first_names='Carlos',
            last_name1='Pérez',
            birth_date=datetime.date(1980, 1, 1),
            sex=sex_h,
            ethnicity=eth,
            birth_canton=cant,
            created_by=self.user
        )
        Visit.objects.create(
            patient=p,
            evaluator=self.user,
            study_code='1',
            visit_date=datetime.date(2026, 1, 1),
            residence_canton=cant
        )

        from io import BytesIO
        from clinical.services.import_tickets import store_upload
        ticket, dummy_file = store_upload(BytesIO(b'fake sav content'), 'dataset.sav', self.user)

        mock_meta = MagicMock()
        mock_meta.number_rows = 1
        mock_meta.number_columns = 2
        mock_meta.variable_value_labels = {'UNIVERSIDAD': {1.0: 'UNEMI'}}
        mock_df = {'CODIGO': [1], 'UNIVERSIDAD': [1.0]}

        with patch('apps.clinical.services.sav_importer.pyreadstat.read_sav', return_value=(mock_df, mock_meta)):
            res = execute_sav_import(ticket, self.user, duplicate_action='update')

        self.assertTrue(res.get('success'))
        self.assertEqual(res.get('total_rows'), 1)
        self.assertEqual(res.get('duplicate_count'), 1)
        self.assertEqual(res.get('updated_count'), 1)
        self.assertEqual(len(res.get('duplicate_records')), 1)
        dup_rec = res['duplicate_records'][0]
        self.assertEqual(dup_rec['code'], '1')
        self.assertEqual(dup_rec['institution'], 'UNEMI')
        self.assertEqual(dup_rec['action'], 'Actualizado en BD')
        self.assertIn('1 duplicados actualizados en BD', res['message'])



class FichaEliminarSecurityTests(TestCase):
    def setUp(self):
        self.password = "DoctorSeguro2026!"
        self.user = User.objects.create_user(
            username="cardiologo_test",
            password=self.password,
            email="cardiologo@unemi.edu.ec"
        )
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        self.client.force_login(self.user)

        self.country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        self.province, _ = Province.objects.get_or_create(country=self.country, iso_code='EC-G', defaults={'name': 'Guayas'})
        self.canton, _ = Canton.objects.get_or_create(province=self.province, dpa_code='0910', defaults={'name': 'Milagro'})
        self.institution, _ = Institution.objects.get_or_create(acronym='UNEMI', defaults={'name': 'Universidad Estatal de Milagro'})
        self.sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        self.ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')

        self.patient = Patient.objects.create(
            id_card="0923485718",
            first_names="Carlos",
            last_name1="Eliminable",
            birth_date=datetime.date(1990, 5, 20),
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            institution=self.institution,
            created_by=self.user
        )
        self.visit = Visit.objects.create(
            patient=self.patient,
            evaluator=self.user,
            study_code="999",
            visit_number=1,
            visit_date=datetime.date.today(),
            residence_canton=self.canton,
            status=Visit.Status.COMPLETED
        )

    def test_delete_without_password_fails(self):
        resp = self.client.post(
            '/clinical/api/ficha/eliminar/',
            data={'patient_id': self.patient.patient_id, 'password': ''},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json().get('success'))
        self.assertIn("contraseña", resp.json().get('error', '').lower())
        # El paciente sigue existiendo
        self.assertTrue(Patient.objects.filter(patient_id=self.patient.patient_id).exists())

    def test_delete_with_wrong_password_rejected(self):
        resp = self.client.post(
            '/clinical/api/ficha/eliminar/',
            data={'patient_id': self.patient.patient_id, 'password': 'wrong_password_123'},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json().get('success'))
        self.assertIn("incorrecta", resp.json().get('error', '').lower())
        # El paciente sigue existiendo
        self.assertTrue(Patient.objects.filter(patient_id=self.patient.patient_id).exists())

    def test_delete_with_correct_password_deletes_patient_and_visit_and_logs_audit(self):
        resp = self.client.post(
            '/clinical/api/ficha/eliminar/',
            data={'patient_id': self.patient.patient_id, 'password': self.password},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('success'))
        # Ficha y paciente eliminados
        self.assertFalse(Visit.objects.filter(study_code="999").exists())
        self.assertFalse(Patient.objects.filter(patient_id=self.patient.patient_id).exists())
        # Registro en ChangeLog de auditoria
        log = ChangeLog.objects.filter(record_key=str(self.patient.patient_id), action='DELETE').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)

    def test_batch_delete_with_correct_password_deletes_all_selected(self):
        p2 = Patient.objects.create(
            id_card="0923485726",
            first_names="Ana",
            last_name1="Seleccionada",
            birth_date=datetime.date(1992, 1, 15),
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            institution=self.institution,
            created_by=self.user
        )
        v2 = Visit.objects.create(
            patient=p2,
            evaluator=self.user,
            study_code="998",
            visit_number=1,
            visit_date=datetime.date.today(),
            residence_canton=self.canton,
            status=Visit.Status.COMPLETED
        )

        resp = self.client.post(
            '/clinical/api/ficha/eliminar/',
            data={'patient_ids': [self.patient.patient_id, p2.patient_id], 'password': self.password},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('success'))
        self.assertEqual(resp.json().get('deleted_count'), 2)
        # Verificar eliminaciones
        self.assertFalse(Patient.objects.filter(patient_id=self.patient.patient_id).exists())
        self.assertFalse(Patient.objects.filter(patient_id=p2.patient_id).exists())
        self.assertFalse(Visit.objects.filter(study_code="999").exists())
        self.assertFalse(Visit.objects.filter(study_code="998").exists())


class SavImporterColumnMappingTests(SimpleTestCase):
    def test_detect_column_typos_maps_destination(self):
        from apps.clinical.services.sav_importer import detect_column_typos
        cols = [
            'PATRON_LLENQADO_MITRAL_RESTRICTIVO',
            'ANTECEDENTRS_ICTUS',
            'CUANTAS_PERSONAS_CONVIVE_CON_USTES_EN_EL_HOGAR',
            'TRONTO_ARTERIA_PULMUNAR'
        ]
        typos = detect_column_typos(cols)
        self.assertEqual(len(typos), 4)

        dest_map = {t['original']: (t['corrected'], t['destination']) for t in typos}
        self.assertIn('PATRON_LLENADO_MITRAL_RESTRICTIVO', dest_map['PATRON_LLENQADO_MITRAL_RESTRICTIVO'][0])
        self.assertIn('Ecocardiograma', dest_map['PATRON_LLENQADO_MITRAL_RESTRICTIVO'][1])

        self.assertIn('ANTECEDENTES_ICTUS', dest_map['ANTECEDENTRS_ICTUS'][0])
        self.assertIn('Cuestionario Clínico', dest_map['ANTECEDENTRS_ICTUS'][1])

        self.assertIn('TRONCO_ARTERIA_PULMONAR', dest_map['TRONTO_ARTERIA_PULMUNAR'][0])
        self.assertIn('Ecocardiograma', dest_map['TRONTO_ARTERIA_PULMUNAR'][1])

    def test_get_column_destination(self):
        from apps.clinical.services.sav_importer import get_column_destination
        mod, fld = get_column_destination('TAS_TS')
        self.assertEqual(mod, 'Signos Vitales')

        mod_medas, _ = get_column_destination('ACEITE_DE_OLIVA_CONSUMO')
        self.assertEqual(mod_medas, 'Cuestionario Dieta MEDAS')

        mod_est, _ = get_column_destination('USTED_SE_HA_REALIZADO_ESTUDIOS_CLINICOS')
        self.assertEqual(mod_est, 'Estudios Solicitados')

        mod_mapa, _ = get_column_destination('USTED_SE_HA_REALIZADO_ESTUDIOS_DE_MAPA')
        self.assertEqual(mod_mapa, 'Estudios Solicitados')


class PatientCreateApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='evaluador_modal',
            password='Password123!',
            email='evaluador@unemi.edu.ec'
        )
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        self.client.force_login(self.user)
        self.country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        self.province, _ = Province.objects.get_or_create(country=self.country, iso_code='EC-G', defaults={'name': 'Guayas'})
        self.canton, _ = Canton.objects.get_or_create(province=self.province, dpa_code='0910', defaults={'name': 'Milagro'})
        self.inst_unemi, _ = Institution.objects.get_or_create(acronym='UNEMI', defaults={'name': 'Universidad Estatal de Milagro'})
        self.inst_inst2, _ = Institution.objects.get_or_create(acronym='INST2', defaults={'name': 'Institución de prueba'})
        self.sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        self.ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        self.staff_cat, _ = StaffCategory.objects.get_or_create(name='PDI')

    def test_create_patient_unemi_success(self):
        payload = {
            'nombre': 'Carmen Villacrés Moreira',
            'cedula': '0928475615',
            'fecha_nac': '1985-06-15',
            'sexo': 'M',
            'estamento': 'PDI',
            'universidad': 'UNEMI',
            'facultad': 'FACS',
            'telefono': '0987654321',
            'correo': 'cvillacres@unemi.edu.ec'
        }
        resp = self.client.post('/clinical/api/pacientes/crear/', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        p = Patient.objects.get(id_card='0928475615')
        self.assertEqual(p.institution.acronym, 'UNEMI')
        self.assertEqual(p.visit.faculty, 'FACS')

    def test_create_patient_inst2_success(self):
        payload = {
            'nombre': 'Roberto Gómez Andrade',
            'cedula': '0923485718',
            'fecha_nac': '1992-03-22',
            'sexo': 'H',
            'estamento': 'PDI',
            'universidad': 'INST2',
            'facultad': 'FIEC',
            'telefono': '0991234567',
            'correo': 'rgomez@example.invalid'
        }
        resp = self.client.post('/clinical/api/pacientes/crear/', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        p = Patient.objects.get(id_card='0923485718')
        self.assertEqual(p.institution.acronym, 'INST2')
        self.assertEqual(p.visit.faculty, 'FIEC')

    def test_create_patient_without_faculty_estamento_stores_none(self):
        """AD/PAS/SERVICIO no tienen facultad: aunque llegue una, no se guarda."""
        cedulas = ('0928475706', '0928475714', '0928475722')
        for cedula, estamento in zip(cedulas, ('AD', 'PAS', 'SERVICIO')):
            payload = {
                'nombre': f'Prueba Estamento {estamento}',
                'cedula': cedula,
                'fecha_nac': '1980-01-01',
                'sexo': 'H',
                'estamento': estamento,
                'universidad': 'UNEMI',
                'facultad': 'FACS',
            }
            resp = self.client.post('/clinical/api/pacientes/crear/', data=payload, content_type='application/json')
            self.assertEqual(resp.status_code, 200, resp.content)
            self.assertIsNone(Patient.objects.get(id_card=cedula).visit.faculty)

    def test_create_student_keeps_faculty_and_blank_is_none(self):
        base = {'fecha_nac': '2003-01-01', 'sexo': 'M', 'estamento': 'ESTUDIANTES', 'universidad': 'UNEMI'}
        resp = self.client.post('/clinical/api/pacientes/crear/', content_type='application/json',
                                data={**base, 'nombre': 'Ana Est Uno', 'cedula': '0928475730', 'facultad': 'FACI'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Patient.objects.get(id_card='0928475730').visit.faculty, 'FACI')
        resp = self.client.post('/clinical/api/pacientes/crear/', content_type='application/json',
                                data={**base, 'nombre': 'Ana Est Dos', 'cedula': '0928475748', 'facultad': ''})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(Patient.objects.get(id_card='0928475748').visit.faculty)

    def test_create_patient_missing_required_fails(self):
        payload = {
            'nombre': '',
            'fecha_nac': ''
        }
        resp = self.client.post('/clinical/api/pacientes/crear/', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_create_patient_with_manual_study_code_success(self):
        payload = {
            'codigo': '777',
            'nombre': 'Valeria Santos Mera',
            'cedula': '0928475631',
            'fecha_nac': '1995-07-14',
            'sexo': 'M',
            'estamento': 'PDI',
            'universidad': 'UNEMI',
            'facultad': 'FACS',
            'telefono': '0981112233',
            'correo': 'vsantos@unemi.edu.ec'
        }
        resp = self.client.post('/clinical/api/pacientes/crear/', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        p = Patient.objects.get(id_card='0928475631')
        self.assertEqual(p.visit.study_code, '777')
        self.assertEqual(data['paciente']['codigo'], '777')

    def test_create_patient_with_duplicate_manual_code_returns_conflict(self):
        payload1 = {
            'codigo': '888',
            'nombre': 'Primer Paciente Con Codigo',
            'cedula': '0928475649',
            'fecha_nac': '1990-01-01',
            'sexo': 'H',
            'universidad': 'UNEMI'
        }
        resp1 = self.client.post('/clinical/api/pacientes/crear/', data=payload1, content_type='application/json')
        self.assertEqual(resp1.status_code, 200)

        payload2 = {
            'codigo': '888',
            'nombre': 'Segundo Paciente Mismo Codigo',
            'cedula': '0928475656',
            'fecha_nac': '1991-02-02',
            'sexo': 'M',
            'universidad': 'UNEMI'
        }
        resp2 = self.client.post('/clinical/api/pacientes/crear/', data=payload2, content_type='application/json')
        self.assertEqual(resp2.status_code, 409)
        self.assertIn('ya está asignado', resp2.json().get('error', ''))

    def test_same_study_code_across_different_institutions(self):
        # UNEMI y INST2 pueden compartir el mismo study_code ("1") con IDs autogeneradas distintas
        p_unemi = Patient.objects.create(
            institution=self.inst_unemi,
            id_card='0911111111',
            first_names='Paciente UNEMI',
            last_name1='P1',
            birth_date='1985-05-10',
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            created_by=self.user
        )
        v_unemi = Visit.objects.create(
            patient=p_unemi,
            evaluator=self.user,
            study_code='1',
            visit_date='2026-01-15',
            residence_canton=self.canton
        )

        p_inst2 = Patient.objects.create(
            institution=self.inst_inst2,
            id_card='0822222222',
            first_names='Paciente INST2',
            last_name1='P1',
            birth_date='1988-08-20',
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            created_by=self.user
        )
        v_inst2 = Visit.objects.create(
            patient=p_inst2,
            evaluator=self.user,
            study_code='1',  # Mismo código de estudio
            visit_date='2026-02-10',
            residence_canton=self.canton
        )

        self.assertNotEqual(p_unemi.patient_id, p_inst2.patient_id)
        self.assertNotEqual(v_unemi.visit_id, v_inst2.visit_id)
        self.assertEqual(v_unemi.study_code, '1')
        self.assertEqual(v_inst2.study_code, '1')
        self.assertEqual(v_unemi.patient.institution.acronym, 'UNEMI')
        self.assertEqual(v_inst2.patient.institution.acronym, 'INST2')


import json
import secrets
import hashlib
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from clinical.models import SecureShare


class SecureShareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cardiologo_share',
            email='cardio_share@unemi.edu.ec',
            password='password123'
        )
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clinical'))
        self.country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        self.prov, _ = Province.objects.get_or_create(country=self.country, iso_code='EC-G', defaults={'name': 'Guayas'})
        self.canton, _ = Canton.objects.get_or_create(province=self.prov, dpa_code='0910', defaults={'name': 'Milagro'})
        self.inst, _ = Institution.objects.get_or_create(acronym='UNEMI', defaults={'name': 'Universidad Estatal de Milagro'})
        self.sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        self.ethnicity, _ = Ethnicity.objects.get_or_create(name='Mestizo')
        self.patient = Patient.objects.create(
            institution=self.inst,
            id_card='0923485718',
            first_names='Juan',
            last_name1='Perez',
            birth_date='1980-01-01',
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            email='paciente@correo.com',
            created_by=self.user
        )
        self.visit = Visit.objects.create(
            patient=self.patient,
            evaluator=self.user,
            study_code='CUN-001',
            visit_date='2026-03-01',
            residence_canton=self.canton
        )

    def test_api_send_patient_sheet_email_creates_secureshares(self):
        self.client.login(username='cardiologo_share', password='password123')
        payload = {
            'patient_ids': [self.patient.patient_id],
            'recipients': ['destinatario1@correo.com', 'destinatario2@correo.com'],
            'duration_hours': 48,
            'subject': 'Documento disponible en portal seguro',
            'notes': 'Indicaciones médicas confidenciales.'
        }
        response = self.client.post(
            reverse('clinical:api_ficha_enviar_correo'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 2)
        for res in data['results']:
            self.assertTrue(res['success'])
            self.assertEqual(len(res['code']), 6)
            self.assertTrue(res['code'].isdigit())

        shares = SecureShare.objects.filter(visit=self.visit)
        self.assertEqual(shares.count(), 2)
        for s in shares:
            self.assertEqual(len(s.token_hash), 64)
            self.assertTrue(s.code_hash.startswith('pbkdf2_') or 'argon2' in s.code_hash or s.code_hash.startswith('bcrypt'))
            self.assertEqual(s.attempts, 0)
            self.assertEqual(s.download_count, 0)
            self.assertEqual(s.max_attempts, 5)
            self.assertIsNone(s.max_downloads)
            self.assertFalse(s.is_revoked)

    def test_max_recipients_limit(self):
        self.client.login(username='cardiologo_share', password='password123')
        payload = {
            'patient_ids': [self.patient.patient_id],
            'recipients': [f'user{i}@correo.com' for i in range(6)],  # 6 > 5
            'duration_hours': 48
        }
        response = self.client.post(
            reverse('clinical:api_ficha_enviar_correo'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('5 destinatarios', response.json()['error'])

    def test_public_secure_share_multi_visit_and_unlimited_downloads(self):
        # Crear segundo paciente y visita
        patient2 = Patient.objects.create(
            institution=self.inst,
            id_card='0923485726',
            first_names='María',
            last_name1='Gómez',
            birth_date='1985-05-05',
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            email='maria@correo.com',
            created_by=self.user
        )
        visit2 = Visit.objects.create(
            patient=patient2,
            evaluator=self.user,
            study_code='CUN-002',
            visit_date='2026-03-02',
            residence_canton=self.canton
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        raw_code = '654321'
        code_hash = make_password(raw_code)
        expires_at = timezone.now() + datetime.timedelta(hours=48)

        share = SecureShare.objects.create(
            visit=self.visit,
            recipient_email='multi@correo.com',
            token_hash=token_hash,
            code_hash=code_hash,
            expires_at=expires_at,
            max_downloads=None,  # Ilimitado
            created_by=self.user
        )
        share.visits.set([self.visit, visit2])

        self.assertEqual(len(share.get_visits()), 2)

        url = reverse('clinical:public_secure_share', kwargs={'token': raw_token})

        # 1. GET inicial muestra formulario bloqueado con 2 documentos
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, '2 documentos clínicos')

        # 2. POST con código correcto desbloquea la vista
        res_post = self.client.post(url, {'code': raw_code})
        self.assertEqual(res_post.status_code, 200)
        self.assertContains(res_post, 'Descargar Todo Comprimido (.ZIP)')
        self.assertContains(res_post, 'Descargar PDF')

        # 3. Descarga comprimida en ZIP
        res_zip = self.client.get(f"{url}?descarga=zip")
        self.assertEqual(res_zip.status_code, 200)
        self.assertEqual(res_zip['Content-Type'], 'application/zip')
        self.assertIn('documentos_clinicos.zip', res_zip['Content-Disposition'])

        # 4. Descarga por separado en PDF
        res_pdf = self.client.get(f"{url}?descarga=pdf&visit_id={visit2.visit_id}")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
        self.assertIn('.pdf', res_pdf['Content-Disposition'])

        # 5. Comprobar descargas ilimitadas (más de 3 descargas no bloquean)
        for _ in range(5):
            self.client.get(f"{url}?descarga=zip")
        share.refresh_from_db()
        self.assertGreater(share.download_count, 3)
        self.assertTrue(share.is_valid())

    def test_api_download_batch_pdf(self):
        self.client.login(username='cardiologo_share', password='password123')
        url = reverse('clinical:api_download_batch_pdf')

        # Un solo paciente -> PDF
        res_single = self.client.get(f"{url}?patient_ids={self.patient.patient_id}")
        self.assertEqual(res_single.status_code, 200)
        self.assertEqual(res_single['Content-Type'], 'application/pdf')

        # Múltiples pacientes -> ZIP
        patient2 = Patient.objects.create(
            institution=self.inst,
            id_card='0923485734',
            first_names='Carlos',
            last_name1='López',
            birth_date='1988-08-08',
            sex=self.sex,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            email='carlos@correo.com',
            created_by=self.user
        )
        Visit.objects.create(
            patient=patient2,
            evaluator=self.user,
            study_code='CUN-003',
            visit_date='2026-03-03',
            residence_canton=self.canton
        )

        res_batch = self.client.get(f"{url}?patient_ids={self.patient.patient_id},{patient2.patient_id}")
        self.assertEqual(res_batch.status_code, 200)
        self.assertEqual(res_batch['Content-Type'], 'application/zip')
        self.assertIn('Fichas_Clinicas_Cardiologia_UNEMI.zip', res_batch['Content-Disposition'])

    def test_public_secure_share_flow(self):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        raw_code = '123456'
        code_hash = make_password(raw_code)
        expires_at = timezone.now() + datetime.timedelta(hours=48)

        share = SecureShare.objects.create(
            visit=self.visit,
            recipient_email='evaluador@correo.com',
            token_hash=token_hash,
            code_hash=code_hash,
            expires_at=expires_at,
            created_by=self.user
        )

        url = reverse('clinical:public_secure_share', kwargs={'token': raw_token})

        # 1. GET inicial muestra formulario
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get['Referrer-Policy'], 'no-referrer')

        # 2. POST con código incorrecto incrementa intentos
        res_post_bad = self.client.post(url, {'code': '000000'})
        self.assertEqual(res_post_bad.status_code, 200)
        share.refresh_from_db()
        self.assertEqual(share.attempts, 1)

        # 3. POST con código correcto desbloquea el acceso y muestra la interfaz de descarga
        res_post_ok = self.client.post(url, {'code': raw_code})
        self.assertEqual(res_post_ok.status_code, 200)
        self.assertTrue(res_post_ok.context['is_unlocked'])

        # 4. Descarga del PDF oficial
        res_pdf = self.client.get(f"{url}?descarga=pdf")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
        self.assertIn('.pdf', res_pdf['Content-Disposition'])
        self.assertEqual(res_pdf['Referrer-Policy'], 'no-referrer')
        self.assertIn('no-store', res_pdf['Cache-Control'])

        share.refresh_from_db()
        self.assertGreaterEqual(share.download_count, 1)

