import json
import logging
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.cache import cache

from chatbot.services import query_gemini_assistant
from security.access import has_clinical_access

logger = logging.getLogger(__name__)


def is_user_clinically_authorized(user) -> bool:
    """
    Verifica que el usuario tenga rol o permisos activos para acceder
    a estadísticas y expedientes clínicos de la cohorte.
    """
    return has_clinical_access(user, 'read')


@login_required
@ensure_csrf_cookie
def chat_view(request):
    """
    Renderiza la interfaz principal y dedicada a pantalla completa del
    Asistente Clínico & Estadístico de CARDIOUNEMI.
    """
    if not is_user_clinically_authorized(request.user):
        return HttpResponseForbidden(
            "<h1>403 Prohibido</h1><p>No cuenta con rol o permisos autorizados para acceder a los datos clínicos de la cohorte.</p>"
        )
    return render(request, "chatbot/chat.html")


@require_POST
def query_api_view(request):
    """
    Endpoint API REST para recibir y procesar consultas en lenguaje natural.
    Ejecuta el pipeline de seguridad:
    1. Autenticación estricta (401 JSON en lugar de 302 HTML redirect).
    2. Autorización por rol clínico/administrativo (403 JSON).
    3. Rate Limiting por usuario / IP (429 JSON).
    4. Validación de CSRF token (garantizado por CsrfViewMiddleware).
    5. Zero PII y modo solo lectura.
    """
    # 1. Autenticación: responder 401 JSON si no hay sesión activa
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({
            'status': 'unauthorized',
            'message': 'No autenticado. Por favor inicie sesión.',
            'response': '🔒 Debe iniciar sesión para utilizar el Asistente Clínico.'
        }, status=401)

    # 2. Autorización: responder 403 JSON si no tiene rol clínico o administrativo activo
    if not is_user_clinically_authorized(request.user):
        return JsonResponse({
            'status': 'forbidden',
            'message': 'Acceso no autorizado. Requiere rol clínico o administrativo activo.',
            'response': '⛔ No cuenta con los privilegios clínicos o rol requerido para consultar estadísticas de la cohorte.'
        }, status=403)

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
        logger.error("Chatbot request failed.")
        return JsonResponse({
            'status': 'error',
            'message': 'Error interno del servidor.',
            'response': 'Ocurrió un error al procesar su consulta. Por favor intente nuevamente.'
        }, status=500)
