from django.test import SimpleTestCase
from chatbot.models import BotQuery


class ChatbotModelStatusTests(SimpleTestCase):
    def test_bot_query_status_default(self):
        query = BotQuery(user_question="Clinical question")
        self.assertEqual(query.status, BotQuery.Status.SUCCESS)

    def test_bot_query_status_error(self):
        query = BotQuery(user_question="Question with error", status=BotQuery.Status.ERROR)
        self.assertEqual(query.status, BotQuery.Status.ERROR)
