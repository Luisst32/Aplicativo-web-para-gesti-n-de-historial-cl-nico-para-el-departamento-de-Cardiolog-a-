import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from chatbot.models import BotQuery
from chatbot.services import (
    is_sensitive_or_pii_query,
    is_modification_attempt,
    get_anonymized_cohort_context,
    query_gemini_assistant
)

User = get_user_model()


class ChatbotSecurityAndPrivacyTests(TestCase):
    """
    Pruebas rigurosas de seguridad, privacidad (Zero PII) y modo solo consulta.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='medicounemi',
            email='medico@unemi.edu.ec',
            password='testpassword123'
        )

    def test_sensitive_query_detection_cedula(self):
        self.assertTrue(is_sensitive_or_pii_query("Dame la cédula del paciente"))
        self.assertTrue(is_sensitive_or_pii_query("cuál es el número de documento de identidad"))
        self.assertTrue(is_sensitive_or_pii_query("buscar paciente con c.i. 0923456789"))

    def test_sensitive_query_detection_nombre(self):
        self.assertTrue(is_sensitive_or_pii_query("¿Cómo se llama el paciente con HTA?"))
        self.assertTrue(is_sensitive_or_pii_query("dame los nombres y apellidos de los evaluados"))
        self.assertTrue(is_sensitive_or_pii_query("quién es el paciente de 55 años"))

    def test_sensitive_query_detection_contacto(self):
        self.assertTrue(is_sensitive_or_pii_query("Dame el teléfono o celular de contacto"))
        self.assertTrue(is_sensitive_or_pii_query("cuál es su dirección de domicilio"))
        self.assertTrue(is_sensitive_or_pii_query("envíale un correo electrónico o mail"))

    def test_safe_clinical_queries_not_blocked(self):
        self.assertFalse(is_sensitive_or_pii_query("¿Cuál es la prevalencia de hipertensión arterial?"))
        self.assertFalse(is_sensitive_or_pii_query("¿Cuántos evaluados tienen sobrepeso u obesidad?"))
        self.assertFalse(is_sensitive_or_pii_query("¿Qué hallazgos se observaron en el electrocardiograma?"))
        self.assertFalse(is_sensitive_or_pii_query("¿Cómo se distribuye el riesgo cardiovascular global?"))

    def test_modification_attempt_detection(self):
        self.assertTrue(is_modification_attempt("elimina los registros de la tabla"))
        self.assertTrue(is_modification_attempt("modificar el diagnóstico a normal"))
        self.assertTrue(is_modification_attempt("borrar paciente"))
        self.assertTrue(is_modification_attempt("DROP TABLE clinical_visit"))
        self.assertFalse(is_modification_attempt("¿Cuántos docentes presentan sobrepeso?"))

    def test_privacy_refusal_response_via_service(self):
        res = query_gemini_assistant("dame el nombre y cédula del paciente 1", user=self.user)
        self.assertEqual(res['status'], 'success')
        self.assertIn("Protección de Datos Médicos", res['response'])
        self.assertIn("anonimización", res['response'].lower())

    def test_modification_refusal_response_via_service(self):
        res = query_gemini_assistant("eliminar todos los pacientes con riesgo alto", user=self.user)
        self.assertEqual(res['status'], 'success')
        self.assertIn("Solo Consulta", res['response'])

    def test_cohort_context_has_zero_pii(self):
        context = get_anonymized_cohort_context()
        self.assertNotIn("cédula", context.lower())
        self.assertNotIn("primer_nombre", context.lower())
        self.assertNotIn("primer_apellido", context.lower())
        self.assertIn("N =", context)

    def test_deterministic_fallback_mode_without_api_key(self):
        res = query_gemini_assistant("¿Cuál es la prevalencia de hipertensión arterial?", user=self.user)
        self.assertEqual(res['status'], 'success')
        self.assertIn("Hipertensión", res['response'])
        self.assertIn("30,5", res['response'])

    def test_gemini_disabled_toggle_prevents_api_call(self):
        from security.models import SystemSetting
        SystemSetting.set_settings(
            chatbot_enabled=True,
            raw_api_key='AIzaFakeKeyForDisabledTest_123',
            gemini_enabled=False
        )
        res = query_gemini_assistant("¿Cuál es la prevalencia de hipertensión arterial?", user=self.user)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res.get('mode'), 'deterministic_fallback')
        self.assertIn("deshabilitada en los Ajustes del Sistema", res['response'])

    def test_bot_query_logging_in_db(self):
        initial_count = BotQuery.objects.count()
        res = query_gemini_assistant("¿Cuántos evaluados hay en total?", user=self.user)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(BotQuery.objects.count(), initial_count + 1)
        logged = BotQuery.objects.first()
        self.assertEqual(logged.user, self.user)
        self.assertIn("59", logged.bot_response)


class ChatbotApiEndpointTests(TestCase):
    """
    Pruebas del endpoint HTTP /chatbot/query/
    """
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='doctora_investigadora',
            email='doctora@unemi.edu.ec',
            password='testpassword123'
        )

    def test_unauthenticated_user_redirected(self):
        response = self.client.post('/chatbot/query/', {'question': 'hola'}, content_type='application/json')
        # Login required redirects with 302
        self.assertEqual(response.status_code, 302)

    def test_empty_question_returns_400(self):
        self.client.login(username='doctora_investigadora', password='testpassword123')
        response = self.client.post(
            '/chatbot/query/',
            json.dumps({'question': '   '}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')

    def test_valid_question_returns_json_200(self):
        self.client.login(username='doctora_investigadora', password='testpassword123')
        response = self.client.post(
            '/chatbot/query/',
            json.dumps({'question': '¿Cuál es la prevalencia de hipertensión arterial?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('response', data)
        self.assertTrue(any(w in data['response'].lower() for w in ['hipertensi', 'hta']))

    def test_chat_page_view_accessible(self):
        self.client.login(username='doctora_investigadora', password='testpassword123')
        response = self.client.get('/chatbot/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chatbot/chat.html')
