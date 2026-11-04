import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from .models import User, SystemSetting

logger = logging.getLogger(__name__)


def login_view(request):
    """
    Autenticación institucional de usuarios.
    Permite el inicio de sesión con correo electrónico o nombre de usuario.
    """
    if request.user.is_authenticated:
        next_url = request.GET.get('next')
        if not next_url or next_url in ('/', '/dashboard/'):
            return redirect('clinical:list')
        return redirect(next_url)

    error_message = None

    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip() or request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not identifier or not password:
            error_message = 'Por favor completa tu correo y contraseña.'
        else:
            user_obj = None
            if '@' in identifier:
                user_obj = User.objects.filter(email__iexact=identifier).first()
            if not user_obj:
                user_obj = User.objects.filter(username__iexact=identifier).first()

            username_to_auth = user_obj.username if user_obj else identifier
            user = authenticate(request, username=username_to_auth, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)
                    next_url = request.GET.get('next')
                    if not next_url or next_url in ('/', '/dashboard/'):
                        return redirect('clinical:list')
                    return redirect(next_url)
                else:
                    error_message = 'Tu cuenta de usuario se encuentra inactiva.'
            else:
                error_message = 'Credenciales incorrectas. Verifica tu correo y contraseña.'

    context = {
        'error_message': error_message
    }
    return render(request, 'security/login.html', context)


def logout_view(request):
    """
    Cierra la sesión del usuario actual y lo redirige al formulario de inicio de sesión.
    """
    logout(request)
    return redirect('security:login')


@login_required
@require_http_methods(["GET", "POST"])
def api_profile_view(request):
    """
    Consulta o actualización de datos de perfil del usuario en sesión.
    Para confirmar cambios en el perfil, se exige la contraseña actual por seguridad.
    """
    user = request.user
    if request.method == "GET":
        role_name = "Administrador" if user.is_superuser else (user.roles.first().name if user.roles.exists() else "Usuario")
        return JsonResponse({
            "status": "success",
            "user": {
                "id": user.user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "second_last_name": user.second_last_name or "",
                "full_name": user.full_name,
                "email": user.email,
                "role": role_name,
                "institution": user.institution.name if user.institution else "Universidad Estatal de Milagro"
            }
        })

    # POST: Actualizar datos de perfil
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        second_last_name = (data.get('second_last_name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        current_password = data.get('current_password', '')

        # Validación 1: Contraseña obligatoria para confirmar cambios
        if not current_password:
            return JsonResponse({
                "status": "error",
                "message": "Debe ingresar su contraseña actual para confirmar los cambios de perfil."
            }, status=400)

        if not user.check_password(current_password):
            return JsonResponse({
                "status": "error",
                "message": "La contraseña ingresada es incorrecta. Verifíquela e intente nuevamente."
            }, status=400)

        # Validación 2: Campos obligatorios
        if not first_name:
            return JsonResponse({"status": "error", "message": "El nombre es obligatorio."}, status=400)
        if not last_name:
            return JsonResponse({"status": "error", "message": "El primer apellido es obligatorio."}, status=400)
        if not email or '@' not in email:
            return JsonResponse({"status": "error", "message": "Ingrese un correo electrónico válido."}, status=400)

        # Validación 3: Unicidad de email excluyendo el usuario actual
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            return JsonResponse({
                "status": "error",
                "message": "Ya existe otro usuario registrado con ese correo electrónico."
            }, status=400)

        user.first_name = first_name
        user.last_name = last_name
        user.second_last_name = second_last_name
        user.email = email
        user.save()

        role_name = "Administrador" if user.is_superuser else (user.roles.first().name if user.roles.exists() else "Usuario")
        return JsonResponse({
            "status": "success",
            "message": "Perfil actualizado correctamente.",
            "user": {
                "id": user.user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "second_last_name": user.second_last_name or "",
                "full_name": user.full_name,
                "email": user.email,
                "role": role_name
            }
        })
    except Exception as e:
        logger.exception(f"Error actualizando perfil: {e}")
        return JsonResponse({"status": "error", "message": f"Error al actualizar el perfil: {str(e)}"}, status=500)


@login_required
@require_POST
def api_change_password_view(request):
    """
    Cambio seguro de contraseña para el usuario autenticado.
    """
    user = request.user
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not old_password:
            return JsonResponse({"status": "error", "message": "Debe ingresar su contraseña actual."}, status=400)
        if not user.check_password(old_password):
            return JsonResponse({"status": "error", "message": "La contraseña actual es incorrecta."}, status=400)
        if not new_password:
            return JsonResponse({"status": "error", "message": "Debe ingresar la nueva contraseña."}, status=400)
        if len(new_password) < 8:
            return JsonResponse({"status": "error", "message": "La nueva contraseña debe tener al menos 8 caracteres."}, status=400)
        if new_password != confirm_password:
            return JsonResponse({"status": "error", "message": "Las nuevas contraseñas no coinciden."}, status=400)
        if old_password == new_password:
            return JsonResponse({"status": "error", "message": "La nueva contraseña debe ser diferente a la actual."}, status=400)

        user.set_password(new_password)
        user.save()
        # Mantener la sesión activa tras el cambio de credenciales
        update_session_auth_hash(request, user)

        return JsonResponse({
            "status": "success",
            "message": "Contraseña actualizada exitosamente."
        })
    except Exception as e:
        logger.exception(f"Error cambiando contraseña: {e}")
        return JsonResponse({"status": "error", "message": f"Error al cambiar contraseña: {str(e)}"}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def api_settings_view(request):
    """
    Consulta o actualización de la configuración global del sistema (SystemSetting).
    Permite activar/desactivar el chatbot y configurar la clave de API de Gemini (encriptada).
    """
    if request.method == "GET":
        cfg = SystemSetting.get_settings()
        raw_key = SystemSetting.get_gemini_api_key()
        if raw_key and len(raw_key) > 8:
            masked = f"{raw_key[:6]}...{'*' * 8}...{raw_key[-4:]}"
        elif raw_key:
            masked = "********"
        else:
            masked = ""

        return JsonResponse({
            "status": "success",
            "chatbot_enabled": cfg.chatbot_enabled,
            "gemini_model": cfg.gemini_model,
            "api_key_configured": bool(raw_key),
            "api_key_masked": masked,
            "updated_at": cfg.updated_at_utc.strftime("%d/%m/%Y %H:%M") if cfg.updated_at_utc else ""
        })

    # POST: Guardar ajustes
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        chatbot_enabled = data.get('chatbot_enabled')
        if isinstance(chatbot_enabled, str):
            chatbot_enabled = chatbot_enabled.lower() in ('true', '1', 'on', 'yes')
        elif chatbot_enabled is None:
            chatbot_enabled = True

        raw_api_key = data.get('gemini_api_key')
        # Si envían la clave enmascarada (con asteriscos), no sobreescribir la existente
        if raw_api_key and '***' in raw_api_key:
            raw_api_key = None

        gemini_model = (data.get('gemini_model') or 'gemini-3.5-flash-lite').strip()

        cfg = SystemSetting.set_settings(
            chatbot_enabled=chatbot_enabled,
            raw_api_key=raw_api_key,
            model=gemini_model,
            user=request.user
        )

        raw_key = SystemSetting.get_gemini_api_key()
        if raw_key and len(raw_key) > 8:
            masked = f"{raw_key[:6]}...{'*' * 8}...{raw_key[-4:]}"
        elif raw_key:
            masked = "********"
        else:
            masked = ""

        return JsonResponse({
            "status": "success",
            "message": "Ajustes del sistema guardados correctamente.",
            "chatbot_enabled": cfg.chatbot_enabled,
            "gemini_model": cfg.gemini_model,
            "api_key_configured": bool(raw_key),
            "api_key_masked": masked
        })
    except Exception as e:
        logger.exception(f"Error guardando ajustes: {e}")
        return JsonResponse({"status": "error", "message": f"Error al guardar ajustes: {str(e)}"}, status=500)
