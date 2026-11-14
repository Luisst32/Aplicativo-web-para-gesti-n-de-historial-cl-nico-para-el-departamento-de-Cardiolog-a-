import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import Permission

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
        self.user.user_permissions.set(Permission.objects.filter(
            content_type__app_label='clinical', codename__in=['view_patient', 'view_visit'],
        ))

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

    def test_missing_measurements_and_answers_are_not_clinical_defaults(self):
        """Absent source values remain absent instead of becoming normal findings."""
        self.visit2.anthropometry.delete()
        self.visit2.vital_signs.delete()
        self.visit2.education_level = None
        self.visit2.housing_type = None
        self.visit2.save(update_fields=['education_level', 'housing_type'])

        record = next(
            row for row in services.get_dashboard_evaluation_data()['records']
            if row['study_code'] == 'CUN-2026-002'
        )

        self.assertEqual(record['nivel_estudios'], 'Sin dato')
        self.assertEqual(record['tipo_vivienda'], 'Sin dato')
        self.assertIsNone(record['fc'])
        self.assertIsNone(record['sat_o2'])
        self.assertEqual(record['ecg_ritmo'], 'Sin ECG')
        self.assertIsNone(record['actividad_fisica'])
        self.assertEqual(record['tabaquismo'], 'Sin dato')
        self.assertIsNone(record['imc'])
        self.assertEqual(record['imc_cat'], 'Sin dato')

    def test_prevalence_denominators_exclude_missing_laboratory(self):
        Laboratory.objects.filter(visit=self.visit2).delete()
        data = services.get_dashboard_evaluation_data()
        self.assertEqual(data['summary_kpis']['dl_pct'], '100,0')
        self.assertEqual(data['module_kpis']['modificables']['dl_pct'], '100,0')
        self.assertEqual(data['module_kpis']['individuo']['hombres_pct'], '50,0')
        self.assertEqual(data['module_kpis']['individuo']['mujeres_pct'], '50,0')
        self.assertEqual(data['module_kpis']['no_cardio']['respiratorio_pct'], 'Sin dato')

    def test_dashboard_index_view(self):
        """Verifies index template renders with real data and WITHOUT formula buttons."""
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)

        # Context contains real database payload
        self.assertIn('records', response.context)
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

    def test_audit_classification_precision(self):
        """Verifies clinical classification precision on negative phrases, edge cases, and ECG."""
        from catalog.models.questionnaire import Question, QuestionnaireSection
        from catalog.models.demographics import EcgRhythm
        from clinical.models import VisitAnswer, Electrocardiogram

        sec, _ = QuestionnaireSection.objects.get_or_create(code='SEC_TEST', defaults={'name': 'Seccion Test', 'display_order': 1})
        q_mental = Question.objects.create(section=sec, code='salud_mental', text='Salud mental', response_type='TEXTO', display_order=1)
        q_dl = Question.objects.create(section=sec, code='r_dislip', text='Dislipemia', response_type='TEXTO', display_order=2)
        q_covid = Question.objects.create(section=sec, code='historia_covid', text='Historia COVID', response_type='TEXTO', display_order=3)
        q_pers = Question.objects.create(section=sec, code='personalidad_tipo_a', text='Tipo A', response_type='TEXTO', display_order=4)
        q_estres = Question.objects.create(section=sec, code='estres', text='Estres', response_type='TEXTO', display_order=5)

        # Visit 1 answers
        VisitAnswer.objects.create(visit=self.visit1, question=q_mental, text_value='No tiene depresión NI ansiedad')
        VisitAnswer.objects.create(visit=self.visit1, question=q_dl, text_value='SI, pero no tratada con farmacos')
        VisitAnswer.objects.create(visit=self.visit1, question=q_covid, text_value='Sí, pasó COVID-19, sin ingreso')
        VisitAnswer.objects.create(visit=self.visit1, question=q_pers, text_value='No tiene personalidad tipo A')
        VisitAnswer.objects.create(visit=self.visit1, question=q_estres, text_value='Si en el trebajo pero no en la vida familiar')
        rhythm, _ = EcgRhythm.objects.get_or_create(name='Ritmo Sinusal (RS)')
        Electrocardiogram.objects.create(visit=self.visit1, rhythm=rhythm, bundle_branch_block='NINGUNA')

        data = services.get_dashboard_evaluation_data()
        rec = next(r for r in data['records'] if r['id'] == self.visit1.visit_id)

        # Assert no false positives
        self.assertEqual(rec['salud_mental_desc'], 'Sin trastorno diagnosticado')
        self.assertFalse(rec['ansiedad'])
        self.assertFalse(rec['depresion'])

        # An explicit field is more reliable than a legacy combined value.
        self.assertTrue(services._mental_condition('Sí', 'Dato no disponible', 'depresi'))

        self.assertEqual(rec['dl_desc'], 'No tratada')
        self.assertTrue(rec['dislipemia'])

        self.assertEqual(rec['covid_historia'], 'Pasó COVID-19 sin hospitalización')
        self.assertTrue(rec['covid_infeccion'])
        self.assertFalse(rec['covid_hospitalizacion'])

        self.assertFalse(rec['personalidad_tipo_a'])

        self.assertEqual(rec['estres'], 'Estrés Laboral')
        self.assertTrue(rec['estres_laboral'])
        self.assertFalse(rec['estres_familiar'])

        self.assertEqual(rec['ecg_bloqueo_rama'], 'Sin bloqueo')
