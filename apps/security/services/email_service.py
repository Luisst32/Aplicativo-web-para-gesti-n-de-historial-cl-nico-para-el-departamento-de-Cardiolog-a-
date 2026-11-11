import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings
from django.core.mail import send_mail

from security.models import SystemSetting, decrypt_api_key

logger = logging.getLogger(__name__)


def _send_smtp_gmail(sender_email: str, app_password: str, recipient_email: str, subject: str, plain_msg: str, html_msg: str) -> bool:
    """
    Intenta despachar correo vía Gmail SMTP (probando puertos 587 y 465) con timeout de 3 segundos
    para evitar bloqueos cuando el proveedor de internet bloquea puertos salientes de correo.
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    msg.attach(MIMEText(plain_msg, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_msg, 'html', 'utf-8'))

    # Probar puertos estándar de Gmail con timeout corto
    for port in (587, 465):
        server = None
        try:
            if port == 465:
                server = smtplib.SMTP_SSL('smtp.gmail.com', port, timeout=3)
            else:
                server = smtplib.SMTP('smtp.gmail.com', port, timeout=3)
                server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            server.quit()
            logger.info(f"[EMAIL_SERVICE] Correo despachado exitosamente por Gmail SMTP (puerto {port}) a {recipient_email}")
            return True
        except Exception as e:
            logger.warning(f"[EMAIL_SERVICE] Intento de envío Gmail SMTP en puerto {port} falló: {e}")
            if server:
                try:
                    server.close()
                except Exception:
                    pass
    return False


def send_password_reset_email(user, reset_url: str) -> bool:
    """
    Envía el correo de restablecimiento de contraseña.
    Si se configuró Gmail con contraseña de aplicación, intenta el envío directo.
    Si el proveedor de red bloquea los puertos SMTP o no está configurado, registra el enlace
    en el logger y usa el backend de consola de Django.
    """
    subject = "CARDIOUNEMI - Restablecimiento de Contraseña"
    recipient_email = user.email

    if not recipient_email:
        logger.warning(f"Usuario {user.username} no tiene correo electrónico configurado para restablecer contraseña.")
        return False

    cfg = SystemSetting.get_settings()
    sender_email = (cfg.gmail_sender_email or '').strip()
    raw_app_password = ''
    if cfg.gmail_client_secret_encrypted:
        raw_app_password = decrypt_api_key(cfg.gmail_client_secret_encrypted).replace(' ', '').strip()

    from_email = sender_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'CARDIOUNEMI <noreply@cardiounemi.edu.ec>')
    user_name = user.full_name or user.username

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Restablecer Contraseña - CARDIOUNEMI</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
    <!-- Encabezado Institucional -->
    <tr>
      <td style="background: linear-gradient(135deg, #1b2a41 0%, #1b73bc 100%); padding: 30px 24px; text-align: center; color: #ffffff;">
        <h1 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: 0.5px;">CARDIOUNEMI</h1>
        <p style="margin: 6px 0 0; font-size: 13px; opacity: 0.85;">Gestión de Historial Clínico Cardiológico</p>
      </td>
    </tr>
    <!-- Contenido Principal -->
    <tr>
      <td style="padding: 32px 28px;">
        <h2 style="font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 14px;">
          Hola, {user_name}
        </h2>
        <p style="font-size: 14px; line-height: 1.6; color: #475569; margin-bottom: 20px;">
          Recibimos una solicitud para restablecer la contraseña asociada a tu cuenta en <strong>CARDIOUNEMI</strong>.
        </p>
        <p style="font-size: 14px; line-height: 1.6; color: #475569; margin-bottom: 26px;">
          Para crear una nueva contraseña, haz clic en el siguiente botón:
        </p>

        <!-- Botón de Acción -->
        <div style="text-align: center; margin: 28px 0;">
          <a href="{reset_url}" target="_blank" style="background: #1b73bc; color: #ffffff; padding: 13px 28px; font-size: 14px; font-weight: 700; text-decoration: none; border-radius: 8px; display: inline-block; box-shadow: 0 3px 8px rgba(27, 115, 188, 0.35);">
            Restablecer mi Contraseña
          </a>
        </div>

        <p style="font-size: 12.5px; line-height: 1.5; color: #64748b; margin-bottom: 18px;">
          Si el botón no funciona, copia y pega el siguiente enlace en tu navegador web:
        </p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 12px; word-break: break-all; font-size: 12px; color: #1b73bc; margin-bottom: 24px; font-family: monospace;">
          <a href="{reset_url}" style="color: #1b73bc; text-decoration: underline;">{reset_url}</a>
        </div>

        <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 14px; border-radius: 4px; margin-bottom: 24px;">
          <p style="margin: 0; font-size: 12.5px; color: #1e40af; line-height: 1.5;">
            <strong>Nota:</strong> Este enlace expirará en 24 horas. Si no solicitaste este cambio, puedes ignorar este correo.
          </p>
        </div>

        <p style="margin: 0; font-size: 13px; color: #64748b;">
          Atentamente,<br>
          <strong>Equipo CARDIOUNEMI</strong>
        </p>
      </td>
    </tr>
    <!-- Pie de Correo -->
    <tr>
      <td style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center; font-size: 11.5px; color: #94a3b8;">
        Este es un mensaje institucional generado automáticamente por el sistema de Cardiología UNEMI.
      </td>
    </tr>
  </table>
</body>
</html>
"""

    plain_message = f"""Hola, {user_name}:

Recibimos una solicitud para restablecer la contraseña de tu cuenta en CARDIOUNEMI.

Para crear una nueva contraseña, ingresa al siguiente enlace:
{reset_url}

Este enlace expirará en 24 horas. Si no realizaste esta solicitud, puedes ignorar este mensaje.

Atentamente,
Equipo CARDIOUNEMI
"""

    logger.info(f"[PASSWORD_RESET] Enlace de recuperación generado para {user.username} ({recipient_email}): {reset_url}")

    # 1. Si Gmail está configurado y habilitado, intentar envío real vía Gmail SMTP
    if sender_email and raw_app_password and cfg.gmail_api_enabled:
        sent = _send_smtp_gmail(
            sender_email=sender_email,
            app_password=raw_app_password,
            recipient_email=recipient_email,
            subject=subject,
            plain_msg=plain_message,
            html_msg=html_content
        )
        if sent:
            return True

    # 2. Respaldo a configuración estándar de Django / consola
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[recipient_email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.exception(f"[PASSWORD_RESET] Error despachando correo a {recipient_email}: {e}")
        return False
