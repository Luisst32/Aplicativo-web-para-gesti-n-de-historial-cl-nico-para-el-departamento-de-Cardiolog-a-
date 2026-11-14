import json
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, SimpleTestCase

from catalog.models import Question, QuestionnaireSection, AnswerOption
from clinical.models import VisitAnswer, Echocardiogram, OrderedStudies, Patient
from dashboard.questionnaire import get_questionnaire_dashboard, catalog, safe_value, SECTIONS, SENSITIVE
from dashboard import tests as dashboard_fixtures
from dashboard import services


class QuestionnaireCoverageTests(TestCase):
    setUp = dashboard_fixtures.DashboardServicesAndViewsTestCase.setUp

    def answer(self, code, value=None, *, label=None):
        section, _ = QuestionnaireSection.objects.get_or_create(code='Q2026_TEST', defaults={'name':'Synthetic questionnaire', 'display_order':1})
        question, _ = Question.objects.get_or_create(code=code, defaults={'section':section,'text':code,'response_type':'TEXTO','display_order':1})
        option = AnswerOption.objects.create(question=question,label=label,display_order=1) if label else None
        return VisitAnswer.objects.create(visit=self.visit1,question=question,text_value=value,selected_option=option)

    def test_all_form_controls_and_all_relational_columns_are_accounted_for(self):
        from clinical.models import Patient, Visit, Anthropometry, VitalSigns, Electrocardiogram, Echocardiogram, Laboratory, OrderedStudies
        from dashboard.questionnaire import PRIVATE_FORM
        source = catalog()
        template = (Path(settings.BASE_DIR)/'apps/clinical/templates/clinical/form.html').read_text(encoding='utf-8')
        names = set(re.findall(r'\bname="([A-Za-z][A-Za-z0-9_]*)"',template)) - PRIVATE_FORM
        # Metadata and CSS group names are not form controls.
        controls = set(re.findall(r'<(?:input|select|textarea)\b[^>]*\bname="([A-Za-z][A-Za-z0-9_]*)"',template)) - PRIVATE_FORM
        self.assertFalse(controls - set(source['fields']))
        result = get_questionnaire_dashboard()
        ids = {field['id'] for field in result['fields']}
        for prefix, model in zip(SECTIONS,(Patient,Visit,Anthropometry,VitalSigns,Electrocardiogram,Echocardiogram,Laboratory,OrderedStudies)):
            for field in model._meta.concrete_fields:
                if not field.primary_key and field.name not in SENSITIVE:
                    self.assertIn('db:'+prefix+'.'+field.name,ids)
        self.assertEqual(len(ids),len(result['fields']))
        for field in result['fields']:
            if '?' in field['label']:
                self.assertTrue(field['label'].startswith('¿'),field['label'])

    def test_priority_answers_include_legacy_aliases_and_do_not_impute_missing_negatives(self):
        from clinical.services.sav_importer import SPSS_QUESTION_ALIASES
        for code in ('covid_paso','r_apnea','r_disfunc','r_irc'):
            self.answer(code,'Si')
        result = get_questionnaire_dashboard()
        first = next(r for r in result['records'] if r['id']==self.visit1.pk)
        second = next(r for r in result['records'] if r['id']==self.visit2.pk)
        for code in ('covid_paso','r_apnea','r_disfunc','r_irc'):
            self.assertEqual(first['values'][code],'Sí')
            self.assertNotIn(code,second['values'])
        for code in ('covid_paso','r_apnea','r_disfunc','r_irc'):
            VisitAnswer.objects.filter(visit=self.visit1,question__code=code).delete()
            alias=SPSS_QUESTION_ALIASES.get(code)
            if alias and alias!=code:
                self.answer(alias[:30],'Si')
                first=next(r for r in get_questionnaire_dashboard()['records'] if r['id']==self.visit1.pk)
                self.assertEqual(first['values'][code],'Sí')

    def test_actual_numbers_zero_options_and_absent_blocks(self):
        self.visit1.laboratory.glucose_mg_dl=0
        self.visit1.laboratory.save()
        Echocardiogram.objects.create(visit=self.visit1,lvef_percentage=60)
        OrderedStudies.objects.create(visit=self.visit1,clinical_analysis=True)
        self.answer('r_apnea',label='No')
        rows={r['id']:r for r in get_questionnaire_dashboard()['records']}
        values=rows[self.visit1.pk]['values']
        self.assertEqual(values['db:laboratory.glucose_mg_dl'],0)
        self.assertEqual(values['db:echocardiogram.lvef_percentage'],60)
        self.assertEqual(values['db:ordered_studies.clinical_analysis'],'Sí')
        self.assertEqual(values['r_apnea'],'No')
        self.assertNotIn('db:echocardiogram.lvef_percentage',rows[self.visit2.pk]['values'])

    def test_sensitive_identity_and_free_text_never_ship_in_questionnaire_payload(self):
        self.answer('covid_cv_detalle','PRIVATE_NOTE_2026')
        self.answer('f_nombre','PRIVATE_NAME_2026')
        self.patient1.first_names='PRIVATE_NAME_2026';self.patient1.save()
        data=get_questionnaire_dashboard()
        encoded=json.dumps(data)
        self.assertNotIn('PRIVATE_NOTE_2026',encoded)
        self.assertNotIn('PRIVATE_NAME_2026',encoded)
        self.assertNotIn(self.patient1.id_card,encoded)
        row=next(r for r in data['records'] if r['id']==self.visit1.pk)
        self.assertTrue(row['values']['covid_cv_detalle'])

    def test_duplicate_codes_and_inactive_patient_records_are_available_separately(self):
        self.visit2.study_code=self.visit1.study_code;self.visit2.save()
        self.patient2.status=Patient.Status.INACTIVE;self.patient2.save()
        rows=get_questionnaire_dashboard()['records']
        self.assertEqual(len(rows),2)
        self.assertNotEqual(rows[0]['id'],rows[1]['id'])
        self.assertEqual(rows[0]['code'],rows[1]['code'])

    def test_dashboard_view_uses_escaped_records_payload(self):
        response=self.client.get('/dashboard/')
        self.assertEqual(response.status_code,200)
        content=response.content.decode()
        self.assertIn('dashboard-records-data', content)
        self.assertIn('records', response.context)
        self.assertNotIn('questionnaire_dashboard', response.context)

    def test_covid_admission_is_not_inferred_from_infection_only(self):
        answer=self.answer('historia_covid','Si')
        row=next(r for r in get_questionnaire_dashboard()['records'] if r['id']==self.visit1.pk)
        self.assertEqual(row['values']['covid_paso'],'Sí')
        self.assertNotIn('covid_ingreso',row['values'])
        answer.text_value='Pasó COVID-19 con ingreso';answer.save()
        row=next(r for r in get_questionnaire_dashboard()['records'] if r['id']==self.visit1.pk)
        self.assertEqual(row['values']['covid_ingreso'],'Sí')
        self.answer('covid_ingreso','No')
        row=next(r for r in get_questionnaire_dashboard()['records'] if r['id']==self.visit1.pk)
        self.assertEqual(row['values']['covid_ingreso'],'No')

    def test_required_risk_answers_feed_the_dashboard_without_cross_counting(self):
        self.answer('r_apnea', 'Si')
        self.answer('r_disfunc', 'Si')
        self.answer('r_irc', 'Si')
        record = next(row for row in services.get_dashboard_evaluation_data()['records'] if row['id'] == self.visit1.pk)
        self.assertTrue(record['apnea_sueno'])
        self.assertTrue(record['disfuncion_erectil'])
        self.assertTrue(record['insuficiencia_renal'])
        self.assertFalse(record['cancer'])

    def test_any_vasculopathy_uses_any_recorded_location(self):
        self.answer('r_vasc_perif', 'No')
        self.answer('r_vasc_fem', 'Si')
        record = next(row for row in services.get_dashboard_evaluation_data()['records'] if row['id'] == self.visit1.pk)
        self.assertFalse(record['vasculopatia_periferica'])
        self.assertTrue(record['vasculopatia_femoral'])
        self.assertTrue(record['vasculopatia_cualquiera'])

        VisitAnswer.objects.filter(visit=self.visit1, question__code='r_vasc_fem').delete()
        record = next(row for row in services.get_dashboard_evaluation_data()['records'] if row['id'] == self.visit1.pk)
        self.assertFalse(record['vasculopatia_cualquiera'])


class QuestionnaireValueTests(SimpleTestCase):
    def test_free_text_cannot_be_rendered_as_a_category(self):
        self.assertIs(safe_value('PRIVATE_TEXT',{'kind':'text'}),True)
        self.assertIsNone(safe_value('',{'kind':'boolean'}))
        self.assertIsNone(safe_value('unknown',{'kind':'boolean'}))
        self.assertEqual(safe_value('0',{'kind':'boolean'}),'No')
        self.assertEqual(safe_value('sí',{'kind':'boolean'}),'Sí')
        self.assertEqual(safe_value(0,{'kind':'number'}),0)
        self.assertIsNone(safe_value('NaN',{'kind':'number'}))
