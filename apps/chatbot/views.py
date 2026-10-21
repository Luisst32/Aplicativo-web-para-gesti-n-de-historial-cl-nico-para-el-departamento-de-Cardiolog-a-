from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def chat_view(request):
    """
    Renders the dedicated, full-page clinical AI assistant chat interface.
    """
    return render(request, "chatbot/chat.html")
