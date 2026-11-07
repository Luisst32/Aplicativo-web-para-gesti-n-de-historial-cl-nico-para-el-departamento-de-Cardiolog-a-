import json
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from chatbot.services import query_gemini_assistant

logger = logging.getLogger(__name__)


@login_required
@ensure_csrf_cookie
def chat_view(request):
    """
    Renderiza la interfaz principal y dedicada a pantalla completa del
    Asistente Clínico & Estadístico de CARDIOUNEMI.
    """
    return render(request, "chatbot/chat.html")


@login_required
@require_POST
def query_api_view(request):
    """
    Endpoint API REST para recibir y procesar consultas en lenguaje natural.
    Ejecuta el pipeline de seguridad (Zero PII, solo lectura, análisis con Gemini Flash).
    """
    try:
        if request.content_type == 'application/json':
            body_data = json.loads(request.body.decode('utf-8'))
            question = body_data.get('question', '')
        else:
            question = request.POST.get('question', '')

        from security.models import SystemSetting
        if not SystemSetting.is_chatbot_enabled():
            return JsonResponse({
                'status': 'disabled',
                'message': 'El Asistente Clínico Inteligente ha sido desactivado temporalmente.',
                'response': '⚠️ El Asistente Clínico Inteligente ha sido desactivado temporalmente por la administración del sistema.'
            }, status=200)

        question = (question or '').strip()
        if not question:
            return JsonResponse({
                'status': 'error',
                'message': 'La consulta no puede estar vacía.',
                'response': 'Por favor formule una pregunta clínica o estadística válida.'
            }, status=400)

        if len(question) > 2000:
            return JsonResponse({
                'status': 'error',
                'message': 'La consulta excede el límite permitido de 2000 caracteres.',
                'response': 'Por favor formule una consulta más concisa (máximo 2000 caracteres).'
            }, status=400)

        result = query_gemini_assistant(question, user=request.user)
        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Formato JSON inválido.',
            'response': 'La solicitud no pudo ser procesada debido a un error de formato.'
        }, status=400)
    except Exception as e:
        logger.exception(f"Error procesando consulta de chatbot: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Error interno del servidor.',
            'response': 'Ocurrió un error al procesar su consulta. Por favor intente nuevamente.'
        }, status=500)
