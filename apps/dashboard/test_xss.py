import json
import re

from django.contrib.auth.models import Permission
from django.test import TestCase

from catalog.models import Country, Province, Canton, Institution, Sex, Ethnicity
from clinical.models import Patient, Visit
from security.models import User


class DashboardStoredXssTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='xss_reader', email='reader@example.invalid')
        self.user.user_permissions.set(Permission.objects.filter(
            content_type__app_label='clinical', codename__in=['view_patient', 'view_visit'],
        ))
        country = Country.objects.create(iso_alpha3='XSZ', name='Synthetic XSS country')
        province = Province.objects.create(country=country, iso_code='XS-T', name='Synthetic province')
        canton = Canton.objects.create(province=province, dpa_code='9998', name='Synthetic canton')
        institution = Institution.objects.create(acronym='XSS-ONLY', name='Synthetic institution')
        sex, _ = Sex.objects.get_or_create(sex_id=1, defaults={'name': 'Hombre'})
        ethnicity = Ethnicity.objects.create(name='Synthetic ethnicity')
        self.patient = Patient.objects.create(
            institution=institution, id_card='XSS-SYNTH', first_names='Synthetic', last_name1='Patient',
            birth_date='1990-01-01', birth_canton=canton, sex=sex, ethnicity=ethnicity, created_by=self.user,
        )
        Visit.objects.create(patient=self.patient, evaluator=self.user, study_code='XSS-01',
                             visit_date='2026-01-01', residence_canton=canton)
        self.client.force_login(self.user)

    def rendered_records(self, payload):
        self.patient.first_names = payload
        self.patient.save(update_fields=['first_names'])
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        match = re.search(r'<script id="dashboard-records-data" type="application/json">(.*?)</script>',
                          content, flags=re.S)
        self.assertIsNotNone(match)
        self.assertNotIn(payload, content)
        records = json.loads(match.group(1))
        self.assertTrue(any(payload in record['nombre'] for record in records))
        return match.group(1)

    def test_stored_script_closing_tag_cannot_escape_json_node(self):
        encoded = self.rendered_records('</script><script>window.__xss=1</script>')
        self.assertIn('\\u003C/script\\u003E', encoded)

    def test_stored_html_events_remain_data(self):
        encoded = self.rendered_records('<img src=x onerror="window.__xss=1">')
        self.assertNotIn('<img', encoded)

    def test_accents_quotes_and_ampersands_round_trip(self):
        self.rendered_records('María O\'Connor & "Ana"')
