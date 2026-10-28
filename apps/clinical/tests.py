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
