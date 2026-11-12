import json
import time
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache

from chatbot.models import BotQuery
from chatbot.services import (
    is_sensitive_or_pii_query,
    is_modification_attempt,
    get_anonymized_cohort_context,
    query_gemini_assistant,
    fmt_safe_cell,
    apply_complementary_suppression,
    invalidate_cohort_cache,
    COHORT_SUMMARY_CACHE_KEY
)

User = get_user_model()


class ChatbotSecurityAndPrivacyTests(TestCase):
    """
    Pruebas rigurosas de seguridad, privacidad (Zero PII),
    control de divulgación estadística y modo solo consulta.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='medicounemi',
            email='medico@unemi.edu.ec',
            password='testpassword123',
            is_staff=True  # Autorizado
        )

    def test_sensitive_query_detection_cedula(self):
        self.assertTrue(is_sensitive_or_pii_query("Dame la cédula del paciente"))
        self.assertTrue(is_sensitive_or_pii_query("cuál es el número de documento de identidad"))
        self.assertTrue(is_sensitive_or_pii_query("buscar paciente con c.i. 0923456789"))
        self.assertTrue(is_sensitive_or_pii_query("ver datos del 0928475615"))

    def test_sensitive_query_detection_nombre(self):
        self.assertTrue(is_sensitive_or_pii_query("¿Cómo se llama el paciente con HTA?"))
        self.assertTrue(is_sensitive_or_pii_query("dame los nombres y apellidos de los evaluados"))
        self.assertTrue(is_sensitive_or_pii_query("quién es el paciente de 55 años"))

    def test_user_query_with_specific_person_name_blocked(self):
        """La pregunta del usuario NO viaja a Gemini si incluye nombres propios de personas."""
        self.assertTrue(is_sensitive_or_pii_query("¿qué tiene Juan Pérez?"))
        self.assertTrue(is_sensitive_or_pii_query("diagnóstico de Carlos Mendoza"))
        self.assertTrue(is_sensitive_or_pii_query("historial de María Gómez"))
        self.assertTrue(is_sensitive_or_pii_query("información del paciente Luis Silva"))

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

    def test_small_cell_suppression_has_no_percentage(self):
        """Con N=58 o 59, si cnt=3 (<5), debe salir '< 5 casos' SIN porcentaje (evitar inferencia inversa)."""
        res_suppressed = fmt_safe_cell(3, 58, threshold=5)
        self.assertEqual(res_suppressed, "< 5 casos*")
        self.assertNotIn("%", res_suppressed)
        self.assertNotIn("5.2", res_suppressed)

        # Para cero casos
        res_zero = fmt_safe_cell(0, 58)
        self.assertEqual(res_zero, "0 casos (0.0 %)")

        # Para conteos >= 5, sí muestra porcentaje exacto
        res_normal = fmt_safe_cell(10, 50)
        self.assertEqual(res_normal, "10 casos (20.0 %)")

    def test_complementary_suppression_case(self):
        """Supresión complementaria para evitar deducción por resta cuando se conoce el total."""
        # Supongamos N=58: Depresión=3 (<5), Ansiedad=10, Sin trastorno=45
        cats = {'depresion': 3, 'ansiedad': 10, 'sin_trastorno': 45}
        result = apply_complementary_suppression(cats, total=58, threshold=5)

        # La celda primaria < 5 se suprime
        self.assertEqual(result['depresion'], "< 5 casos*")
        # Para evitar 58 - 45 - 10 = 3, la segunda celda menor (ansiedad=10) se suprime complementariamente
        self.assertIn("supresión complementaria", result['ansiedad'])

    @patch('chatbot.services.get_dashboard_evaluation_data')
    def test_hypertension_and_hta_detection(self, mock_data):
        """Verifica que 'hipertensión', 'HTA' y 'tensión arterial' sean detectadas correctamente."""
        mock_data.return_value = {
            'records': [{'sexo': 'Hombre', 'hipertension': True, 'tas': 140, 'ant_fam_hta': True}],
            'total': 1,
            'summary_kpis': {},
            'module_kpis': {}
        }
        res_hta = query_gemini_assistant("¿cuántos casos de HTA existen?", user=self.user)
        self.assertIn("Hipertensión Arterial (HTA)", res_hta['response'])

        res_hip = query_gemini_assistant("pacientes con hipertensión", user=self.user)
        self.assertIn("Hipertensión Arterial (HTA)", res_hip['response'])

        res_ta = query_gemini_assistant("cuál es la tensión arterial sistólica media", user=self.user)
        self.assertIn("Hipertensión Arterial (HTA)", res_ta['response'])

    @patch('chatbot.services.get_dashboard_evaluation_data')
    def test_emotional_tension_not_detected_as_hypertension(self, mock_data):
        """'Tensión emocional' no debe confundirse con hipertensión arterial."""
        mock_data.return_value = {
            'records': [{'sexo': 'Hombre', 'depresion': False, 'ansiedad': True, 'hipertension': False}],
            'total': 1,
            'summary_kpis': {},
            'module_kpis': {}
        }
        res = query_gemini_assistant("pacientes con tensión emocional y estrés", user=self.user)
        self.assertNotIn("Hipertensión Arterial (HTA)", res['response'])

    def test_bulk_or_update_cache_invalidation(self):
        """Verifica que invalidate_cohort_cache elimine las claves del caché compartido."""
        cache.set(COHORT_SUMMARY_CACHE_KEY, "datos de cohorte en caché", timeout=300)
        self.assertIsNotNone(cache.get(COHORT_SUMMARY_CACHE_KEY))

        invalidate_cohort_cache()
        self.assertIsNone(cache.get(COHORT_SUMMARY_CACHE_KEY))


class ChatbotApiEndpointSecurityTests(TestCase):
    """
    Pruebas rigurosas de autenticación, autorización por rol (401/403 JSON)
    y rate limiting en el endpoint HTTP /chatbot/query/
    """
    def setUp(self):
        self.client = Client()
        # Usuario autorizado (médico / staff)
        self.auth_user = User.objects.create_user(
            username='doctora_investigadora',
            email='doctora@unemi.edu.ec',
            password='testpassword123',
            is_staff=True
        )
        # Usuario autenticado pero SIN permisos/rol clínico
        self.unauth_user = User.objects.create_user(
            username='usuario_sin_permiso',
            email='sinpermiso@unemi.edu.ec',
            password='testpassword123',
            is_staff=False,
            is_superuser=False
        )

    def test_unauthenticated_user_returns_401_json(self):
        """Un usuario no autenticado debe recibir 401 JSON (no una redirección 302 a HTML)."""
        response = self.client.post(
            '/chatbot/query/',
            json.dumps({'question': '¿Cuántos pacientes hay?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data['status'], 'unauthorized')
        self.assertIn('iniciar sesión', data['response'].lower())

    def test_authenticated_user_without_permission_returns_403_json(self):
        """Un usuario autenticado sin rol clínico o permisos debe recibir 403 Forbidden en JSON."""
        self.client.login(username='usuario_sin_permiso', password='testpassword123')
        response = self.client.post(
            '/chatbot/query/',
            json.dumps({'question': '¿Cuántos pacientes con HTA hay?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data['status'], 'forbidden')
        self.assertIn('privilegios clínicos', data['response'].lower())

    @patch('chatbot.services.get_dashboard_evaluation_data')
    def test_authorized_user_returns_200_json(self, mock_data):
        """Un usuario con rol autorizado recibe respuesta 200 JSON."""
        mock_data.return_value = {
            'records': [{'sexo': 'Hombre', 'hipertension': True, 'tas': 130}],
            'total': 1,
            'summary_kpis': {},
            'module_kpis': {}
        }
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

    def test_rate_limiting_returns_429_json(self):
        """Al exceder 20 peticiones por minuto, el endpoint responde 429 Too Many Requests en JSON."""
        self.client.login(username='doctora_investigadora', password='testpassword123')
        rate_key = f"ratelimit_bot_{self.auth_user.pk}_127.0.0.1"
        cache.set(rate_key, 20, timeout=60)

        response = self.client.post(
            '/chatbot/query/',
            json.dumps({'question': 'test rate limit'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)
        data = response.json()
        self.assertEqual(data['status'], 'rate_limited')
        self.assertIn('límite de consultas', data['response'].lower())
        cache.delete(rate_key)
