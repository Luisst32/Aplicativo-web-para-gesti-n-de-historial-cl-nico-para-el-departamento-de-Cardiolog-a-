from django.test import SimpleTestCase
from chatbot.models import BotQuery


class ChatbotModelStatusSimpleTests(SimpleTestCase):
    def test_bot_query_status_default(self):
        query = BotQuery(user_question="¿Cuántos pacientes tienen hipertensión?")
        self.assertEqual(query.status, BotQuery.QueryStatus.SUCCESS)
        self.assertIsNone(query.error_message)

    def test_bot_query_status_error(self):
        query = BotQuery(
            user_question="Pregunta con error",
            status=BotQuery.QueryStatus.ERROR,
            error_message="Error de conexión con el proveedor LLM"
        )
        self.assertEqual(query.status, BotQuery.QueryStatus.ERROR)
        self.assertEqual(query.error_message, "Error de conexión con el proveedor LLM")
