import datetime
from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model

from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity, StaffCategory
from clinical.models import Patient, Visit, Anthropometry, VitalSigns, VisitAnswer
from clinical.validators import validate_ecuadorian_id, validate_clinical_ranges
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


class SavImporterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='evaluador_sav',
            password='Password123!',
            email='evaluador@unemi.edu.ec'
        )
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



class FichaEliminarSecurityTests(TestCase):
    def setUp(self):
        self.password = "DoctorSeguro2026!"
        self.user = User.objects.create_user(
            username="cardiologo_test",
            password=self.password,
            email="cardiologo@unemi.edu.ec"
        )
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
