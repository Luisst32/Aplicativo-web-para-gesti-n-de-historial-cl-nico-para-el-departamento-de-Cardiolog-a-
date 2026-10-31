import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse

from security.models import User
from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity, StaffCategory
from clinical.models import Visit, Patient, Anthropometry, VitalSigns, Laboratory, VisitAnswer
from apps.dashboard import services


class DashboardServicesAndViewsTestCase(TestCase):
    def setUp(self):
        self.user, _ = User.objects.get_or_create(
            username="doctor_dash_test",
            defaults={
                "email": "docdash@unemi.edu.ec",
                "first_name": "Doc",
                "last_name": "Dash"
            }
        )
        self.user.set_password("testpassword123")
        self.user.save()

        self.client = Client()
        self.client.login(username="doctor_dash_test", password="testpassword123")

        self.country, _ = Country.objects.get_or_create(iso_alpha3='ECU', defaults={'name': 'Ecuador'})
        self.province, _ = Province.objects.get_or_create(country=self.country, iso_code='EC-G', defaults={'name': 'Guayas'})
        self.canton, _ = Canton.objects.get_or_create(province=self.province, dpa_code='0910', defaults={'name': 'Milagro'})

        self.institution, _ = Institution.objects.get_or_create(
            acronym="UNEMI",
            defaults={"name": "Universidad Estatal de Milagro"}
        )
        self.sex_m, _ = Sex.objects.get_or_create(sex_id=1, defaults={"name": "Hombre"})
        self.sex_f, _ = Sex.objects.get_or_create(sex_id=2, defaults={"name": "Mujer"})
        self.ethnicity, _ = Ethnicity.objects.get_or_create(name="Mestizo")
        self.staff_pdi, _ = StaffCategory.objects.get_or_create(name="PDI (Docentes)")
        self.staff_pas, _ = StaffCategory.objects.get_or_create(name="PAS (Administrativos)")

        # Create Patient 1: Hypertensive & Obese
        self.patient1 = Patient.objects.create(
            institution=self.institution,
            id_card="0923485712",
            first_names="Juan",
            last_name1="Perez",
            birth_date=datetime.date(1980, 5, 10),
            sex=self.sex_m,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            created_by=self.user
        )
        self.visit1 = Visit.objects.create(
            patient=self.patient1,
            evaluator=self.user,
            study_code="CUN-2026-001",
            visit_date=datetime.date(2026, 6, 1),
            staff_category=self.staff_pdi,
            residence_canton=self.canton
        )
        Anthropometry.objects.create(
            visit=self.visit1,
            weight_kg=Decimal("95.00"),
            height_cm=Decimal("170.0"),
            waist_circumference_cm=Decimal("105.0")
        )
        VitalSigns.objects.create(
            visit=self.visit1,
            systolic_bp=145,
            diastolic_bp=95
        )
        Laboratory.objects.create(
            visit=self.visit1,
            glucose_mg_dl=Decimal("90.0"),
            total_cholesterol_mg_dl=Decimal("220.0"),
            ldl_mg_dl=Decimal("140.0"),
            triglycerides_mg_dl=Decimal("160.0")
        )

        # Create Patient 2: Normal/Healthy Woman
        self.patient2 = Patient.objects.create(
            institution=self.institution,
            id_card="0923485713",
            first_names="Maria",
            last_name1="Gomez",
            birth_date=datetime.date(1996, 8, 20),
            sex=self.sex_f,
            ethnicity=self.ethnicity,
            birth_canton=self.canton,
            created_by=self.user
        )
        self.visit2 = Visit.objects.create(
            patient=self.patient2,
            evaluator=self.user,
            study_code="CUN-2026-002",
            visit_date=datetime.date(2026, 6, 2),
            staff_category=self.staff_pas,
            residence_canton=self.canton
        )
        Anthropometry.objects.create(
            visit=self.visit2,
            weight_kg=Decimal("55.00"),
            height_cm=Decimal("165.0"),
            waist_circumference_cm=Decimal("70.0")
        )
        VitalSigns.objects.create(
            visit=self.visit2,
            systolic_bp=110,
            diastolic_bp=70
        )
        Laboratory.objects.create(
            visit=self.visit2,
            glucose_mg_dl=Decimal("85.0"),
            total_cholesterol_mg_dl=Decimal("170.0"),
            ldl_mg_dl=Decimal("95.0"),
            triglycerides_mg_dl=Decimal("100.0")
        )

    def test_services_get_dashboard_evaluation_data(self):
        """Verifies calculation service produces accurate metrics and cohorts."""
        data = services.get_dashboard_evaluation_data()
        self.assertEqual(data['total'], 2)
        self.assertEqual(len(data['records']), 2)
        self.assertIn(2026, data['years'])
        self.assertIn('PDI (Docentes)', data['categories'])
        self.assertIn('PAS (Administrativos)', data['categories'])

        # Check Patient 1 record
        rec1 = next(r for r in data['records'] if r['study_code'] == 'CUN-2026-001')
        self.assertEqual(rec1['sexo'], 'Hombre')
        self.assertEqual(rec1['edad'], 46)
        self.assertEqual(rec1['grupo_edad'], '40-49 años')
        self.assertTrue(rec1['hipertension'])  # Due to BP 145/95
        self.assertTrue(rec1['obesidad'])      # BMI > 30 (95 / 1.7^2 = 32.87)
        self.assertTrue(rec1['dislipemia'])    # Chol 220 >= 200
        self.assertEqual(rec1['abd_riesgo'], 'Riesgo Elevado (>102)')
        self.assertIn(rec1['riesgo_global'], ['Alto (2-3 factores)', 'Muy Alto (4+ factores)'])

        # Check Patient 2 record
        rec2 = next(r for r in data['records'] if r['study_code'] == 'CUN-2026-002')
        self.assertEqual(rec2['sexo'], 'Mujer')
        self.assertEqual(rec2['edad'], 29)
        self.assertEqual(rec2['grupo_edad'], '<40 años')
        self.assertFalse(rec2['hipertension'])
        self.assertFalse(rec2['obesidad'])
        self.assertFalse(rec2['dislipemia'])
        self.assertEqual(rec2['abd_riesgo'], 'Normal (<80)')
        self.assertEqual(rec2['riesgo_global'], 'Bajo (0 factores)')

    def test_dashboard_index_view(self):
        """Verifies index template renders with real data and WITHOUT formula buttons."""
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)

        # Context contains real database payload
        self.assertIn('records_json', response.context)
        self.assertIn('available_years', response.context)
        self.assertEqual(response.context['total_evaluated'], 2)

        content = response.content.decode('utf-8')
        # Crucial requirement: No formula buttons or panels in HTML
        self.assertNotIn('btn-toggle-all-formulas', content)
        self.assertNotIn('formula-btn-pill', content)
        self.assertNotIn('formula-panel', content)
        self.assertNotIn('toggleFormula', content)
        self.assertNotIn('toggleAllFormulas', content)

    def test_dashboard_api_data_endpoint(self):
        """Verifies JSON API endpoint returns HTTP 200 with valid dataset."""
        response = self.client.get(reverse("dashboard:api_data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['total'], 2)
        self.assertEqual(len(payload['records']), 2)
        self.assertEqual(payload['years'], [2026])
        self.assertIn('module_kpis', payload)
        self.assertIn('institutions', payload)

    def test_dashboard_incorporates_all_8_clinical_blocks(self):
        """Verifies that all 8 requested clinical blocks are incorporated in context and template."""
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # 1. Verification of all 8 tabs in template HTML
        expected_tabs = [
            'tab-resumen-general',
            'tab-datos-individuo',
            'tab-exploracion-fisica',
            'tab-factores-modificables',
            'tab-factores-emergentes',
            'tab-antecedentes-familiares',
            'tab-historia-no-cardio',
            'tab-covid-19',
            'tab-electrocardiograma',
        ]
        for tab in expected_tabs:
            self.assertIn(tab, content, f"Pestaña {tab} no encontrada en el HTML")

        # Verification of slicer-inst in template
        self.assertIn('slicer-inst', content)
        self.assertIn('available_institutions', response.context)

        # 2. Verification of module_kpis in template context
        self.assertIn('module_kpis', response.context)
        m_kpis = response.context['module_kpis']
        expected_modules = [
            'individuo', 'exploracion', 'modificables',
            'emergentes', 'familiares', 'no_cardio',
            'covid', 'ecg'
        ]
        for m in expected_modules:
            self.assertIn(m, m_kpis, f"Módulo KPI {m} ausente en context['module_kpis']")

        # 3. Verification of 8 block fields inside evaluated records
        data = services.get_dashboard_evaluation_data()
        rec1 = data['records'][0]
        block_fields = [
            'institucion',                                 # Filtro Institución
            'nivel_estudios', 'estado_civil',             # Bloque 1: Datos individuo
            'pa_categoria', 'abd_riesgo',                 # Bloque 2: Exploración física
            'predimed_adherencia', 'tabaquismo',          # Bloque 3: Factores modificables
            'calidad_sueno', 'personalidad_tipo_a',       # Bloque 4: Factores emergentes
            'ant_fam_hta', 'ant_fam_cv_mayor',            # Bloque 5: Antecedentes familiares
            'respiratorio_desc', 'salud_mental_desc',     # Bloque 6: Historia no cardio
            'covid_infeccion', 'covid_tiene_secuelas',    # Bloque 7: COVID-19
            'ecg_es_sinusal', 'ecg_pr_cat', 'ecg_qtc_cat' # Bloque 8: Electrocardiograma
        ]
        for f in block_fields:
            self.assertIn(f, rec1, f"Campo clínico {f} ausente en record")
