from django.test import SimpleTestCase
from catalog.models import Institution, QuestionnaireSection, Question, AnswerOption, EcgRhythm


class CatalogModelStatusSimpleTests(SimpleTestCase):
    def test_institution_active_default(self):
        inst = Institution(acronym='UNEMI', name='Universidad Estatal de Milagro')
        self.assertTrue(inst.is_active)

    def test_questionnaire_and_items_active_default(self):
        sec = QuestionnaireSection(code='MED_DIET', name='Dieta Mediterránea', display_order=1)
        self.assertTrue(sec.is_active)

        q = Question(section=sec, code='Q1', text='¿Usa aceite de oliva?', response_type='OPCION', display_order=1)
        self.assertTrue(q.is_active)

        opt = AnswerOption(question=q, label='Sí', display_order=1, scores_predimed=True)
        self.assertTrue(opt.is_active)

    def test_ecg_rhythm_active_default(self):
        rhythm = EcgRhythm(name='Ritmo Sinusal')
        self.assertTrue(rhythm.is_active)
