import json
import logging
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import Resolver404, resolve, reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods, require_POST

from .models import User, SystemSetting
from security.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)


def _safe_redirect_target(request):
    """Retorna una URL de destino segura y existente tras autenticar al usuario."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if not next_url:
        return 'home'
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return 'home'

    path_only = next_url.split('?', 1)[0]
    if path_only in ('/', '/security/login/', '/security/logout/'):
        return 'home'

    try:
        resolve(path_only)
        return next_url
    except Resolver404:
        return 'home'


def login_view(request):
    """
    Autenticación institucional de usuarios.
    Permite el inicio de sesión con correo electrónico o nombre de usuario.
    """
    if request.user.is_authenticated:
        return redirect(_safe_redirect_target(request))

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

                    # Gestión de persistencia de sesión (Mantener sesión activa)
                    keep_session = request.POST.get('keep_session')
                    if keep_session:
                        # Conservar sesión durante 30 días continuos
                        request.session.set_expiry(60 * 60 * 24 * 30)
                    else:
                        # Expira inmediatamente al cerrar el navegador
                        request.session.set_expiry(0)

                    return redirect(_safe_redirect_target(request))
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


def _mask_api_key(raw_key: str) -> str:
    if raw_key and len(raw_key) > 8:
        return f"{raw_key[:6]}...{'*' * 8}...{raw_key[-4:]}"
    return "********" if raw_key else ""


@login_required
@require_http_methods(["GET", "POST"])
def api_settings_view(request):
    """
    Consulta o actualización de la configuración relacional del sistema (SystemSetting)
    vinculada exclusivamente al rol Administrador (security.role).
    Gestiona credenciales cifradas y parámetros para Gemini, OpenAI, Claude y Gmail API.
    """
    cfg = SystemSetting.get_settings()
    is_admin = cfg.is_role_authorized(request.user)

    if request.method == "GET":
        raw_gemini = SystemSetting.get_gemini_api_key(user=request.user) if is_admin else ""
        raw_openai = SystemSetting.get_openai_api_key(user=request.user) if is_admin else ""
        raw_claude = SystemSetting.get_claude_api_key(user=request.user) if is_admin else ""
        raw_gmail_secret = SystemSetting.get_gmail_client_secret(user=request.user) if is_admin else ""
        raw_gmail_refresh = SystemSetting.get_gmail_refresh_token(user=request.user) if is_admin else ""

        return JsonResponse({
            "status": "success",
            "chatbot_enabled": cfg.chatbot_enabled,
            "active_llm_provider": cfg.active_llm_provider or "gemini",

            # Google Gemini
            "gemini_enabled": cfg.gemini_enabled if is_admin else False,
            "gemini_model": (cfg.gemini_model or "gemini-2.5-flash") if is_admin else "",
            "gemini_api_key_configured": bool(raw_gemini) if is_admin else False,
            "gemini_api_key_masked": _mask_api_key(raw_gemini) if is_admin else "",
            "api_key_configured": bool(raw_gemini) if is_admin else False,
            "api_key_masked": _mask_api_key(raw_gemini) if is_admin else "",

            # OpenAI / ChatGPT
            "openai_enabled": cfg.openai_enabled if is_admin else False,
            "openai_model": (cfg.openai_model or "gpt-4o-mini") if is_admin else "",
            "openai_api_key_configured": bool(raw_openai) if is_admin else False,
            "openai_api_key_masked": _mask_api_key(raw_openai) if is_admin else "",

            # Anthropic Claude
            "claude_enabled": cfg.claude_enabled if is_admin else False,
            "claude_model": (cfg.claude_model or "claude-3-5-sonnet-20241022") if is_admin else "",
            "claude_api_key_configured": bool(raw_claude) if is_admin else False,
            "claude_api_key_masked": _mask_api_key(raw_claude) if is_admin else "",

            # Google Gmail REST API
            "gmail_api_enabled": cfg.gmail_api_enabled if is_admin else False,
            "gmail_client_id": (cfg.gmail_client_id or "") if is_admin else "",
            "gmail_sender_email": (cfg.gmail_sender_email or "") if is_admin else "",
            "gmail_redirect_uri": (cfg.gmail_redirect_uri or "http://127.0.0.1:8000/security/oauth2/gmail/callback/") if is_admin else "",
            "gmail_secret_configured": bool(raw_gmail_secret) if is_admin else False,
            "gmail_secret_masked": _mask_api_key(raw_gmail_secret) if is_admin else "",
            "gmail_refresh_configured": bool(raw_gmail_refresh) if is_admin else False,
            "gmail_refresh_masked": _mask_api_key(raw_gmail_refresh) if is_admin else "",
            "last_token_refresh": (cfg.last_token_refresh.strftime("%d/%m/%Y %H:%M") if cfg.last_token_refresh else "") if is_admin else "",

            "is_admin": is_admin,
            "role_name": cfg.role.name if cfg.role_id else "",
            "updated_at": cfg.updated_at_utc.strftime("%d/%m/%Y %H:%M") if cfg.updated_at_utc else ""
        })

    if not is_admin:
        return JsonResponse({
            "status": "error",
            "message": "Acceso denegado: solo el rol Administrador puede modificar la configuración del sistema."
        }, status=403)

    # POST: Guardar ajustes (solo rol Administrador)
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        def _to_bool(val, default=None):
            if val is None: return default
            if isinstance(val, bool): return val
            return str(val).lower() in ('true', '1', 'on', 'yes')

        chatbot_enabled = _to_bool(data.get('chatbot_enabled'), default=cfg.chatbot_enabled)
        active_llm_provider = data.get('active_llm_provider', cfg.active_llm_provider)

        # Gemini
        raw_gemini_key = data.get('gemini_api_key')
        if raw_gemini_key and '***' in raw_gemini_key:
            raw_gemini_key = None
        gemini_model = data.get('gemini_model')
        gemini_enabled = _to_bool(data.get('gemini_enabled'), default=None)

        # OpenAI
        raw_openai_key = data.get('openai_api_key')
        if raw_openai_key and '***' in raw_openai_key:
            raw_openai_key = None
        openai_model = data.get('openai_model')
        openai_enabled = _to_bool(data.get('openai_enabled'), default=None)

        # Claude
        raw_claude_key = data.get('claude_api_key')
        if raw_claude_key and '***' in raw_claude_key:
            raw_claude_key = None
        claude_model = data.get('claude_model')
        claude_enabled = _to_bool(data.get('claude_enabled'), default=None)

        # Gmail
        gmail_client_id = data.get('gmail_client_id')
        raw_gmail_secret = data.get('gmail_client_secret')
        if raw_gmail_secret and '***' in raw_gmail_secret:
            raw_gmail_secret = None
        raw_gmail_refresh = data.get('gmail_refresh_token')
        if raw_gmail_refresh and '***' in raw_gmail_refresh:
            raw_gmail_refresh = None
        gmail_sender_email = data.get('gmail_sender_email')
        gmail_api_enabled = _to_bool(data.get('gmail_api_enabled'), default=None)
        gmail_redirect_uri = data.get('gmail_redirect_uri')

        cfg = SystemSetting.set_settings(
            chatbot_enabled=chatbot_enabled,
            active_llm_provider=active_llm_provider,
            raw_api_key=raw_gemini_key,
            model=gemini_model,
            gemini_enabled=gemini_enabled,
            raw_openai_key=raw_openai_key,
            openai_model=openai_model,
            openai_enabled=openai_enabled,
            raw_claude_key=raw_claude_key,
            claude_model=claude_model,
            claude_enabled=claude_enabled,
            gmail_client_id=gmail_client_id,
            raw_gmail_secret=raw_gmail_secret,
            raw_gmail_refresh_token=raw_gmail_refresh,
            gmail_sender_email=gmail_sender_email,
            gmail_api_enabled=gmail_api_enabled,
            gmail_redirect_uri=gmail_redirect_uri,
            user=request.user
        )

        raw_gemini = SystemSetting.get_gemini_api_key(user=request.user)
        raw_openai = SystemSetting.get_openai_api_key(user=request.user)
        raw_claude = SystemSetting.get_claude_api_key(user=request.user)

        return JsonResponse({
            "status": "success",
            "message": "Ajustes del sistema y credenciales de APIs guardados correctamente.",
            "chatbot_enabled": cfg.chatbot_enabled,
            "active_llm_provider": cfg.active_llm_provider,
            "gemini_model": cfg.gemini_model,
            "gemini_api_key_configured": bool(raw_gemini),
            "gemini_api_key_masked": _mask_api_key(raw_gemini),
            "openai_api_key_configured": bool(raw_openai),
            "openai_api_key_masked": _mask_api_key(raw_openai),
            "claude_api_key_configured": bool(raw_claude),
            "claude_api_key_masked": _mask_api_key(raw_claude),
            "is_admin": True
        })
    except PermissionDenied as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=403)
    except Exception as e:
        logger.exception(f"Error guardando ajustes: {e}")
        return JsonResponse({"status": "error", "message": f"Error al guardar ajustes: {str(e)}"}, status=500)


@require_POST
def password_reset_request_view(request):
    """
    Solicitud institucional de restablecimiento de contraseña.
    Busca al usuario por correo electrónico o nombre de usuario y le envía
    un enlace con token criptográfico válido por 24 horas.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        identifier = (data.get('email') or data.get('identifier') or '').strip()

        if not identifier:
            return JsonResponse({
                "status": "error",
                "message": "Por favor ingresa tu correo electrónico institucional o nombre de usuario."
            }, status=400)

        user = None
        if '@' in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            user = User.objects.filter(username__iexact=identifier).first()

        if not user or not user.is_active:
            return JsonResponse({
                "status": "error",
                "message": "No se encontró ningún usuario activo registrado con ese correo o usuario."
            }, status=404)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = request.build_absolute_uri(
            reverse('security:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        )
        dispatch_result = send_password_reset_email(user, reset_url)

        if dispatch_result.get("smtp_delivered"):
            return JsonResponse({
                "status": "success",
                "smtp_delivered": True,
                "message": f"Hemos enviado un correo a {user.email} con las instrucciones para restablecer tu contraseña. Por favor revisa tu bandeja de entrada o spam."
            })
        else:
            # En entorno local o si el proveedor de internet bloquea puertos SMTP (587/465)
            return JsonResponse({
                "status": "success",
                "smtp_delivered": False,
                "reset_url": reset_url,
                "recipient_email": user.email,
                "message": "Los puertos de correo saliente (587/465) están bloqueados por tu proveedor de red local. En este entorno de desarrollo puedes acceder directamente con el botón de abajo:",
            })
    except Exception as e:
        logger.exception(f"Error procesando solicitud de restablecimiento de contraseña: {e}")
        return JsonResponse({
            "status": "error",
            "message": "Ocurrió un error al procesar tu solicitud. Intenta nuevamente más tarde."
        }, status=500)


def password_reset_confirm_view(request, uidb64, token):
    """
    Validación de token criptográfico y definición de la nueva contraseña.
    Permite acceder mediante GET (formulario) y POST (actualización de credencial).
    """
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid, is_active=True).first()
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid_link = bool(user and default_token_generator.check_token(user, token))

    if request.method == "POST":
        if not valid_link:
            return JsonResponse({
                "status": "error",
                "message": "El enlace de restablecimiento es inválido o ha caducado. Por favor solicita uno nuevo."
            }, status=400)

        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST

            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')

            if not new_password:
                return JsonResponse({"status": "error", "message": "Debe ingresar una nueva contraseña."}, status=400)
            if len(new_password) < 8:
                return JsonResponse({"status": "error", "message": "La nueva contraseña debe tener al menos 8 caracteres."}, status=400)
            if new_password != confirm_password:
                return JsonResponse({"status": "error", "message": "Las contraseñas ingresadas no coinciden."}, status=400)

            user.set_password(new_password)
            user.save()

            logger.info(f"Contraseña restablecida exitosamente para usuario {user.username}.")
            return JsonResponse({
                "status": "success",
                "message": "¡Contraseña actualizada exitosamente! Ya puedes iniciar sesión con tu nueva credencial."
            })
        except Exception as e:
            logger.exception(f"Error confirmando restablecimiento de contraseña: {e}")
            return JsonResponse({"status": "error", "message": f"Error al actualizar la contraseña: {str(e)}"}, status=500)

    # GET request: Renderizar formulario institucional
    context = {
        'valid_link': valid_link,
        'uidb64': uidb64,
        'token': token,
        'username': user.username if valid_link else '',
        'user_email': user.email if valid_link else '',
    }
    return render(request, 'security/password_reset_confirm.html', context)

