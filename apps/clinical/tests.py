from django.test import SimpleTestCase
from datetime import date
from clinical.models import Patient, Visit


class ClinicalModelStatusTests(SimpleTestCase):
    def test_patient_default_status(self):
        patient = Patient(
            id_card='0912345678',
            first_names='Juan',
            last_name1='Pérez',
            birth_date=date(1980, 1, 1)
        )
        self.assertEqual(patient.status, Patient.Status.ACTIVE)

    def test_patient_inactive_status(self):
        patient = Patient(
            id_card='0912345678',
            first_names='Juan',
            last_name1='Pérez',
            birth_date=date(1980, 1, 1),
            status=Patient.Status.INACTIVE
        )
        self.assertEqual(patient.status, Patient.Status.INACTIVE)

    def test_visit_default_status(self):
        visit = Visit(
            study_code='CUN-2026-001',
            visit_date=date(2026, 2, 10)
        )
        self.assertEqual(visit.status, Visit.Status.COMPLETED)
