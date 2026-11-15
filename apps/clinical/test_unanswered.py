"""Real PostgreSQL round trips for unanswered clinical controls."""
from django.test import TestCase
from django.db import models, IntegrityError, transaction
from clinical.test_model_contracts import ClinicalModelContractTests
from clinical.models import Electrocardiogram, Echocardiogram, OrderedStudies, VitalSigns, VisitAnswer
from clinical.services.clinical_form import update_clinical_record
from clinical.services.yes_no import RADIO_FIELDS, CHECKBOX_FIELDS
from clinical.views import _build_form_datos


class UnansweredTests(TestCase):
    setUpTestData = classmethod(ClinicalModelContractTests.setUpTestData.__func__)

    def save(self, data):
        return update_clinical_record(self.patient, data, self.user, '127.0.0.1')

    def test_new_models_have_no_boolean_defaults(self):
        for model in (Electrocardiogram, Echocardiogram, OrderedStudies, VitalSigns):
            for field in model._meta.fields:
                if isinstance(field, models.BooleanField):
                    with self.subTest(model=model.__name__, field=field.name):
                        self.assertTrue(field.null)
                        self.assertFalse(field.has_default())
                        self.assertIsNone(getattr(model(), field.name))

    def test_empty_patient_form_has_no_automatic_answers(self):
        data = _build_form_datos(self.patient, self.visit)
        for key in RADIO_FIELDS | CHECKBOX_FIELDS:
            with self.subTest(key=key):
                self.assertIn(data[key], (None, ''))

    def test_text_answers_yes_no_null_and_omission(self):
        for value in ('Si', 'No', None):
            self.save({'nc_asma': value})
            answer = VisitAnswer.objects.get(visit=self.visit, question__code='nc_asma')
            self.assertEqual(answer.text_value, value)
            self.assertEqual(_build_form_datos(self.patient, self.visit)['nc_asma'], value)
        self.save({'nc_asma': 'No'})
        self.save({})
        self.assertEqual(VisitAnswer.objects.get(visit=self.visit, question__code='nc_asma').text_value, 'No')

    def test_relational_yes_no_null_and_omission(self):
        for value, expected in [('Si', True), ('No', False), (None, None), ('', None)]:
            self.save({'est_tac_cardiaco': value})
            self.assertIs(OrderedStudies.objects.get(visit=self.visit).cardiac_ct, expected)
        self.save({'est_tac_cardiaco': 'No'})
        self.save({})
        self.assertIs(OrderedStudies.objects.get(visit=self.visit).cardiac_ct, False)

    def test_blank_full_form_can_save_without_inventing_ecg(self):
        self.save({key: '' for key in RADIO_FIELDS | CHECKBOX_FIELDS})
        self.assertFalse(Electrocardiogram.objects.filter(visit=self.visit).exists())
        self.assertFalse(VisitAnswer.objects.filter(visit=self.visit, text_value='No').exists())

    def test_invalid_answer_does_not_write(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.save({'nc_asma': 'unknown'})
        self.assertFalse(VisitAnswer.objects.filter(visit=self.visit).exists())

    def test_null_answer_still_rejects_multiple_values(self):
        self.save({'nc_asma': None})
        answer = VisitAnswer.objects.get(visit=self.visit, question__code='nc_asma')
        with self.assertRaises(IntegrityError), transaction.atomic():
            answer.text_value = 'No'
            answer.numeric_value = 0
            answer.save()

    def test_dashboard_null_override_beats_legacy_answer(self):
        from dashboard.boolean_answers import recorded_answers
        self.save({'nc_asma': 'Si'})
        self.save({'nc_asma': None})
        self.assertIsNone(recorded_answers(self.visit)['nc_asma'])

    def test_export_missing_boolean_is_not_zero(self):
        import math
        from clinical.services.sav_exporter import _export_bool
        self.assertTrue(math.isnan(_export_bool(None)))
        self.assertEqual(_export_bool('No'), 0)
        self.assertEqual(_export_bool('Si'), 1)

    def test_covid_fields_save_independently_and_clear_to_null(self):
        from dashboard.services import get_dashboard_evaluation_data
        for hospital, expected in [('No',False), ('Si',True), (None,None)]:
            self.save({'covid_paso':'Si','covid_ingreso':hospital})
            row = next(r for r in get_dashboard_evaluation_data()['records'] if r['id']==self.visit.pk)
            self.assertIs(row['covid_infeccion'],True)
            self.assertIs(row['covid_hospitalizacion'],expected)
            self.assertEqual(_build_form_datos(self.patient,self.visit)['covid_ingreso'],hospital)
        self.assertFalse(VisitAnswer.objects.filter(visit=self.visit,question__code='historia_covid').exists())

    def test_all_form_controls_clear_to_sql_null(self):
        VitalSigns.objects.create(visit=self.visit,systolic_bp=120,diastolic_bp=80)
        from catalog.models import EcgRhythm
        rhythm=EcgRhythm.objects.create(name='Synthetic rhythm')
        Electrocardiogram.objects.create(visit=self.visit,rhythm=rhythm)
        self.save({key:'No' if key in RADIO_FIELDS else '0' for key in RADIO_FIELDS | CHECKBOX_FIELDS})
        self.save({key:None for key in RADIO_FIELDS | CHECKBOX_FIELDS})
        for answer in VisitAnswer.objects.filter(visit=self.visit):
            self.assertIsNone(answer.text_value,answer.question.code)
            self.assertIsNone(answer.numeric_value)
            self.assertIsNone(answer.selected_option_id)
        from dashboard.services import get_dashboard_evaluation_data
        row=next(r for r in get_dashboard_evaluation_data()['records'] if r['id']==self.visit.pk)
        for key in ['covid_infeccion','covid_hospitalizacion','covid_secuelas_cardio','covid_secuelas_resp','covid_fatiga_long','covid_niebla_mental','covid_tiene_secuelas','personalidad_tipo_a','mal_ambiente_laboral','ant_padre_hta','ant_madre_dm','asma','epoc']:
            self.assertIsNone(row[key],key)

    def test_covid_legacy_summary_does_not_invent_hospital_answer(self):
        from clinical.services.covid_answers import resolve_covid
        for source in ({}, {'historia_covid':'Si'}, {'historia_covid':'No'}, {'historia_covid':'Si sin ingreso','covid_ingreso':None}):
            self.assertIsNone(resolve_covid(source)['covid_hospitalizacion'])
        self.assertIs(resolve_covid({'historia_covid':'Si sin ingreso'})['covid_hospitalizacion'],False)
        self.assertIs(resolve_covid({'historia_covid':'Si con ingreso'})['covid_hospitalizacion'],True)

    def test_covid_entire_cohort_uses_answered_denominator(self):
        from clinical.models import Patient, Visit
        from catalog.models import Question
        from dashboard.services import get_dashboard_evaluation_data
        q=Question.objects.create(section=self.section,code='covid_ingreso',text='Hospital',response_type='TEXTO',display_order=1)
        for index,value in enumerate(['Si','No',None]):
            if index==0:
                visit=self.visit
            else:
                patient=Patient.objects.create(institution=self.patient.institution,id_card='COVIDTEST'+str(index),first_names='Synthetic',last_name1='Test',birth_date=self.patient.birth_date,birth_canton=self.patient.birth_canton,sex=self.patient.sex,ethnicity=self.patient.ethnicity,created_by=self.user)
                visit=Visit.objects.create(patient=patient,evaluator=self.user,study_code='COVID-'+str(index),visit_date=self.visit.visit_date,residence_canton=self.visit.residence_canton)
            VisitAnswer.objects.create(visit=visit,question=q,text_value=value)
        data=get_dashboard_evaluation_data()
        values=[r['covid_hospitalizacion'] for r in data['records']]
        self.assertEqual(sum(v is True for v in values),1)
        self.assertEqual(sum(v is False for v in values),1)
        self.assertEqual(sum(v is None for v in values),1)
        self.assertEqual(data['module_kpis']['covid']['covid_hosp_pct'],'50,0')

    def test_missing_diet_does_not_become_low_adherence(self):
        from dashboard.services import get_dashboard_evaluation_data
        def row():
            return next(r for r in get_dashboard_evaluation_data()['records'] if r['id']==self.visit.pk)
        self.assertIsNone(row()['predimed_adherencia'])
        self.save({'pred_q4':'No'})
        self.assertIsNone(row()['predimed_adherencia'])
        self.save({'pred_q1':'Si','pred_q3':'Si','pred_q4':'Si'})
        self.assertEqual(row()['predimed_adherencia'],'Buena Adherencia')
        self.save({'pred_q4':None})
        self.assertIsNone(row()['predimed_adherencia'])

    def test_all_categorical_radios_are_unanswered_and_clearable(self):
        from clinical.services.yes_no import CHOICE_FIELDS
        data=_build_form_datos(self.patient,self.visit)
        for code in CHOICE_FIELDS:
            self.assertIsNone(data[code],code)
        self.save({'res_fsvi':'Normal','res_presiones_vi':'Normales','res_fdvi':'Normal'})
        self.assertEqual(_build_form_datos(self.patient,self.visit)['res_fsvi'],'Normal')
        self.save({code:None for code in CHOICE_FIELDS})
        data=_build_form_datos(self.patient,self.visit)
        for code in CHOICE_FIELDS:
            self.assertIsNone(data[code],code)
            answer=VisitAnswer.objects.get(visit=self.visit,question__code=code)
            self.assertIsNone(answer.text_value,code)
        self.assertIsNone(Echocardiogram.objects.get(visit=self.visit).diastolic_dysfunction)
