from django.test import SimpleTestCase
from datetime import date
from clinical.models import Patient, Visit


class ClinicalModelStatusSimpleTests(SimpleTestCase):
    def test_patient_default_status(self):
        patient = Patient(
            id_card='0912345678',
            first_names='Juan',
            last_name1='Pérez',
            birth_date=date(1980, 1, 1)
        )
        self.assertEqual(patient.status, Patient.PatientStatus.ACTIVE)
        self.assertTrue(patient.is_active)
        self.assertFalse(patient.is_deceased)
        self.assertIsNone(patient.status_date)
        self.assertIsNone(patient.status_reason)

    def test_patient_deceased_status(self):
        patient = Patient(
            id_card='0912345678',
            first_names='Juan',
            last_name1='Pérez',
            birth_date=date(1980, 1, 1)
        )
        patient.status = Patient.PatientStatus.DECEASED
        patient.is_active = False
        patient.status_date = date(2026, 5, 10)
        patient.status_reason = "Fallecimiento por complicación cardiovascular"

        self.assertEqual(patient.status, Patient.PatientStatus.DECEASED)
        self.assertFalse(patient.is_active)
        self.assertTrue(patient.is_deceased)
        self.assertEqual(patient.status_reason, "Fallecimiento por complicación cardiovascular")

    def test_patient_transferred_status(self):
        patient = Patient(
            id_card='0987654321',
            first_names='María',
            last_name1='Gómez',
            birth_date=date(1990, 3, 15)
        )
        patient.status = Patient.PatientStatus.TRANSFERRED
        patient.is_active = False
        patient.status_reason = "Derivado a: Hospital Teodoro Maldonado Carbo"

        self.assertEqual(patient.status, Patient.PatientStatus.TRANSFERRED)
        self.assertFalse(patient.is_active)
        self.assertIn("Hospital Teodoro Maldonado", patient.status_reason)

    def test_visit_default_status(self):
        visit = Visit(
            study_code='CUN-2026-001',
            visit_date=date(2026, 2, 10)
        )
        self.assertEqual(visit.status, Visit.VisitStatus.COMPLETED)
        self.assertTrue(visit.is_active)
        self.assertIsNone(visit.cancellation_reason)
