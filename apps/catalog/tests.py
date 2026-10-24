from django.test import SimpleTestCase
from catalog.models import Institution, QuestionnaireSection, Question, AnswerOption, EcgRhythm


class CatalogModelStatusTests(SimpleTestCase):
    def test_institution_status(self):
        inst = Institution(acronym='UNEMI', name='Universidad Estatal de Milagro')
        self.assertEqual(inst.status, Institution.Status.ACTIVE)

    def test_questionnaire_and_items_status(self):
        sec = QuestionnaireSection(code='MED_DIET', name='Mediterranean Diet', display_order=1)
        self.assertEqual(sec.status, QuestionnaireSection.Status.ACTIVE)

        q = Question(section=sec, code='Q1', text='Uses olive oil?', response_type='OPCION', display_order=1)
        self.assertEqual(q.status, Question.Status.ACTIVE)

        opt = AnswerOption(question=q, label='Yes', display_order=1, scores_predimed=True)
        self.assertEqual(opt.status, AnswerOption.Status.ACTIVE)

    def test_ecg_rhythm_status(self):
        rhythm = EcgRhythm(name='Sinus Rhythm')
        self.assertEqual(rhythm.status, EcgRhythm.Status.ACTIVE)
