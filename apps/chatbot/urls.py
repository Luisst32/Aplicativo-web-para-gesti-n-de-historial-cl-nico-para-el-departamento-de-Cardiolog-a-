from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.chat_view, name="chat"),
    path("query/", views.query_api_view, name="query"),
]
