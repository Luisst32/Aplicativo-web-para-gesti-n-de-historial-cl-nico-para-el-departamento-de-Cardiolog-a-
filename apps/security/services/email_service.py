import logging
import smtplib
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from django.conf import settings
from django.core.mail import send_mail, EmailMessage

from security.models import SystemSetting, decrypt_api_key

logger = logging.getLogger(__name__)


def _send_smtp_gmail(sender_email: str, app_password: str, recipient_email: str, subject: str, plain_msg: str, html_msg: str, attachments: list = None) -> tuple[bool, str]:
    """
    Intenta despachar correo vía Gmail SMTP (probando puertos 465, 587 y 25) con timeout de 3 segundos
    para evitar bloqueos cuando el proveedor de internet bloquea puertos salientes de correo.
    Soporta lista de adjuntos [(filename, filebytes), ...].
    """
    if attachments:
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email

        alt_part = MIMEMultipart('alternative')
        alt_part.attach(MIMEText(plain_msg, 'plain', 'utf-8'))
        alt_part.attach(MIMEText(html_msg, 'html', 'utf-8'))
        msg.attach(alt_part)

        for fname, fbytes in attachments:
            part = MIMEApplication(fbytes, _subtype="pdf")
            part.add_header('Content-Disposition', 'attachment', filename=fname)
            msg.attach(part)
    else:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email

        msg.attach(MIMEText(plain_msg, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_msg, 'html', 'utf-8'))

    # Probar puertos estándar de Gmail: 465 (SSL directo), 587 (STARTTLS) y 25
    last_err = ""
    for port in (465, 587, 25):
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
            return True, f"Enviado exitosamente vía Gmail SMTP (puerto {port})"
        except Exception as e:
            last_err = str(e)
            logger.warning(f"[EMAIL_SERVICE] Intento de envío Gmail SMTP en puerto {port} falló: {e}")
            if server:
                try:
                    server.close()
                except Exception:
                    pass
    return False, last_err or "Puertos SMTP no disponibles en la red"


def send_password_reset_email(user, reset_url: str) -> dict:
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
        return {"success": False, "smtp_delivered": False, "error": "Usuario sin correo"}

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
            <strong>Nota:</strong> Este enlace expirará en 15 minutos. Si no solicitaste este cambio, puedes ignorar este correo.
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

Este enlace expirará en 15 minutos. Si no realizaste esta solicitud, puedes ignorar este mensaje.

Atentamente,
Equipo CARDIOUNEMI
"""

    logger.info(f"[PASSWORD_RESET] Enlace de recuperación generado para {user.username} ({recipient_email}): {reset_url}")

    # 1. Registrar siempre en el backend de Django (consola en dev, locmem en tests)
    django_sent = False
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[recipient_email],
            html_message=html_content,
            fail_silently=False,
        )
        django_sent = True
    except Exception as e:
        logger.exception(f"[PASSWORD_RESET] Error despachando correo vía Django send_mail a {recipient_email}: {e}")

    # 2. Si Gmail está configurado y habilitado, intentar envío real vía Gmail SMTP
    if sender_email and raw_app_password and cfg.gmail_api_enabled:
        sent, err_msg = _send_smtp_gmail(
            sender_email=sender_email,
            app_password=raw_app_password,
            recipient_email=recipient_email,
            subject=subject,
            plain_msg=plain_message,
            html_msg=html_content
        )
        if sent:
            return {"success": True, "smtp_delivered": True, "method": "smtp"}
        else:
            return {"success": django_sent, "smtp_delivered": False, "method": "console", "error": err_msg}

    return {"success": django_sent, "smtp_delivered": False, "method": "console", "error": "SMTP no configurado"}


def send_clinical_sheet_email(recipient_emails: list, subject: str, note_message: str, pdf_attachments: list, sender_user=None) -> dict:
    """
    Envía una o más fichas clínicas en PDF por correo electrónico a los destinatarios especificados.
    pdf_attachments: lista de tuplas (filename, pdf_bytes).
    """
    if not recipient_emails:
        return {"success": False, "error": "No se indicaron correos destinatarios."}

    if not pdf_attachments:
        return {"success": False, "error": "No se proporcionó ningún documento PDF para adjuntar."}

    clean_recipients = []
    for r in recipient_emails:
        if isinstance(r, str):
            for email_part in r.replace(';', ',').split(','):
                email_clean = email_part.strip()
                if email_clean and '@' in email_clean and email_clean not in clean_recipients:
                    clean_recipients.append(email_clean)

    if not clean_recipients:
        return {"success": False, "error": "Las direcciones de correo proporcionadas no son válidas."}

    cfg = SystemSetting.get_settings()
    sender_email = (cfg.gmail_sender_email or '').strip()
    raw_app_password = ''
    if cfg.gmail_client_secret_encrypted:
        raw_app_password = decrypt_api_key(cfg.gmail_client_secret_encrypted).replace(' ', '').strip()

    from_email = sender_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'CARDIOUNEMI <noreply@cardiounemi.edu.ec>')
    doctor_name = sender_user.full_name or sender_user.username if sender_user else "Departamento de Cardiología"

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
    <!-- Encabezado Institucional -->
    <tr>
      <td style="background: linear-gradient(135deg, #1b2a41 0%, #1b73bc 100%); padding: 28px 24px; text-align: center; color: #ffffff;">
        <h1 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: 0.5px;">CARDIOUNEMI</h1>
        <p style="margin: 6px 0 0; font-size: 13px; opacity: 0.9;">Estudio Cardiovascular Oficial · Universidad Estatal de Milagro</p>
      </td>
    </tr>
    <!-- Contenido Principal -->
    <tr>
      <td style="padding: 30px 26px;">
        <h2 style="font-size: 17px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 12px;">
          Ficha Clínica Cardiológica Oficial Adjunta
        </h2>
        <p style="font-size: 13.5px; line-height: 1.6; color: #475569; margin-bottom: 16px;">
          Estimado(a), adjunto a este mensaje encontrará el documento oficial en formato PDF correspondiente al Cuestionario de Evaluación Cardiovascular de CARDIOUNEMI.
        </p>

        {f'<div style="background: #f8fafc; border-left: 4px solid #1b73bc; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;"><strong style="font-size: 12.5px; color: #1e293b;">Observaciones del Especialista:</strong><p style="margin: 4px 0 0; font-size: 13px; color: #475569; font-style: italic;">{note_message}</p></div>' if note_message else ''}

        <div style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
          <p style="margin: 0; font-size: 12.5px; color: #1e40af; line-height: 1.5;">
            📄 <strong>Documentos adjuntos:</strong> {len(pdf_attachments)} archivo(s) PDF generado(s) desde el repositorio clínico institucional.
          </p>
        </div>

        <p style="margin: 0; font-size: 13px; color: #64748b;">
          Emitido por: <strong>{doctor_name}</strong><br>
          Universidad Estatal de Milagro (UNEMI)
        </p>
      </td>
    </tr>
    <!-- Pie -->
    <tr>
      <td style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 24px; text-align: center; font-size: 11px; color: #94a3b8;">
        Este correo contiene información médica confidencial protegida por normas institucionales y bioéticas.
      </td>
    </tr>
  </table>
</body>
</html>
"""

    plain_message = f"""CARDIOUNEMI - Ficha Clínica Cardiológica
Estimado(a), adjunto a este correo encontrará el Cuestionario Oficial UNEMI en formato PDF.

{f'Observaciones: {note_message}' if note_message else ''}

Emitido por: {doctor_name}
Universidad Estatal de Milagro (UNEMI)
"""

    # 1. Enviar vía Django EmailMessage (soporta backend consola o locmem en tests)
    django_ok = False
    try:
        msg = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=from_email,
            to=clean_recipients,
        )
        msg.content_subtype = "html"
        for fname, fbytes in pdf_attachments:
            msg.attach(fname, fbytes, 'application/pdf')
        msg.send(fail_silently=False)
        django_ok = True
    except Exception as e:
        logger.exception(f"[CLINICAL_SHEET_EMAIL] Error al enviar correo vía Django: {e}")

    # 2. Si Gmail SMTP está configurado y habilitado, enviar a cada destinatario
    if sender_email and raw_app_password and cfg.gmail_api_enabled:
        smtp_errors = []
        for rcpt in clean_recipients:
            ok, err = _send_smtp_gmail(
                sender_email=sender_email,
                app_password=raw_app_password,
                recipient_email=rcpt,
                subject=subject,
                plain_msg=plain_message,
                html_msg=html_content,
                attachments=pdf_attachments
            )
            if not ok:
                smtp_errors.append(f"{rcpt}: {err}")

        if not smtp_errors:
            return {"success": True, "smtp_delivered": True, "recipients": clean_recipients}
        else:
            return {"success": django_ok, "smtp_delivered": False, "recipients": clean_recipients, "error": "; ".join(smtp_errors)}

    return {"success": django_ok, "smtp_delivered": False, "recipients": clean_recipients, "note": "Enviado por consola/backend por falta de SMTP activo"}


def send_secure_share_link_email(
    recipient_email: str,
    access_url: str,
    expires_at,
    note_message: str = '',
    subject: str = None,
    sender_user=None
) -> dict:
    """
    Envía un correo institucional 100% GENÉRICO y SEGURO con enlace único de acceso.
    NO contiene nombres, cédulas ni datos clínicos del paciente.
    NO adjunta ningún archivo (el PDF se generará en el servidor tras validar el código).
    """
    clean_email = (recipient_email or '').strip()
    if not clean_email or '@' not in clean_email:
        return {"success": False, "error": "Dirección de correo inválida."}

    subj = (subject or "Documento disponible en portal seguro").strip()
    if not subj:
        subj = "Documento disponible en portal seguro"

    # Sanitizar mensaje adicional (máximo 300 caracteres, escapar HTML)
    safe_note = html.escape((note_message or '').strip()[:300])

    cfg = SystemSetting.get_settings()
    sender_email = (cfg.gmail_sender_email or '').strip()
    raw_app_password = ''
    if cfg.gmail_client_secret_encrypted:
        raw_app_password = decrypt_api_key(cfg.gmail_client_secret_encrypted).replace(' ', '').strip()

    from_email = sender_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'CARDIOUNEMI <noreply@cardiounemi.edu.ec>')
    doctor_name = getattr(sender_user, 'full_name', '') or getattr(sender_user, 'username', '') if sender_user else "Departamento de Cardiología"

    expires_text = expires_at.strftime('%d/%m/%Y a las %H:%M') if hasattr(expires_at, 'strftime') else str(expires_at)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>{html.escape(subj)}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
    <!-- Encabezado Institucional -->
    <tr>
      <td style="background: linear-gradient(135deg, #1b2a41 0%, #1b73bc 100%); padding: 28px 24px; text-align: center; color: #ffffff;">
        <h1 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: 0.5px;">CARDIOUNEMI</h1>
        <p style="margin: 6px 0 0; font-size: 13px; opacity: 0.9;">Portal Seguro · Universidad Estatal de Milagro</p>
      </td>
    </tr>
    <!-- Contenido Principal -->
    <tr>
      <td style="padding: 30px 26px;">
        <h2 style="font-size: 17px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 12px;">
          Documento Clínico Disponible en Portal Seguro
        </h2>
        <p style="font-size: 13.5px; line-height: 1.6; color: #475569; margin-bottom: 16px;">
          Estimado(a), se ha puesto a su disposición un documento oficial en el repositorio institucional seguro de CARDIOUNEMI.
        </p>
        <p style="font-size: 13.5px; line-height: 1.6; color: #475569; margin-bottom: 20px;">
          Para acceder y descargar el documento, pulse el botón a continuación e ingrese el <strong>código de verificación de 6 dígitos</strong> que le fue proporcionado por su especialista a través de un canal seguro:
        </p>

        <!-- Botón de Acceso -->
        <div style="text-align: center; margin: 26px 0;">
          <a href="{access_url}" style="display: inline-block; background: #1b73bc; color: #ffffff; font-size: 14.5px; font-weight: 700; text-decoration: none; padding: 12px 28px; border-radius: 8px; box-shadow: 0 2px 6px rgba(27, 115, 188, 0.35);">
            Acceder al Documento Seguro
          </a>
        </div>

        <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px;">
          <p style="margin: 0; font-size: 12.5px; color: #1e40af; line-height: 1.5;">
            ⏱️ <strong>Caducidad del enlace:</strong> Este acceso vence el <strong>{expires_text}</strong>. Pasada esta fecha o superado el número de intentos permitidos, el enlace quedará inhabilitado.
          </p>
        </div>

        {f'''<div style="background: #f8fafc; border-left: 4px solid #1b73bc; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;">
          <strong style="font-size: 12.5px; color: #1e293b;">Observaciones:</strong>
          <p style="margin: 4px 0 0; font-size: 13px; color: #475569; font-style: italic;">{safe_note}</p>
        </div>''' if safe_note else ''}

        <p style="margin: 18px 0 6px 0; font-size: 12px; color: #64748b;">
          Si no puede hacer clic en el botón, copie y pegue el siguiente enlace en su navegador:
        </p>
        <p style="margin: 0; font-size: 11.5px; color: #1b73bc; word-break: break-all;">
          {access_url}
        </p>

        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;">

        <p style="margin: 0; font-size: 12.5px; color: #64748b;">
          Emitido por: <strong>{html.escape(doctor_name)}</strong><br>
          Universidad Estatal de Milagro (UNEMI)
        </p>
      </td>
    </tr>
    <!-- Pie -->
    <tr>
      <td style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 24px; text-align: center; font-size: 11px; color: #94a3b8;">
        Este mensaje no contiene datos personales ni diagnósticos médicos. La entrega de este documento cumple con los protocolos de seguridad bioética institucional.
      </td>
    </tr>
  </table>
</body>
</html>
"""

    plain_message = f"""CARDIOUNEMI - Documento Disponible en Portal Seguro
Estimado(a), se ha puesto a su disposición un documento oficial en el repositorio institucional de CARDIOUNEMI.

Para acceder, ingrese al siguiente enlace e introduzca el código de verificación de 6 dígitos que le fue entregado por su especialista:
{access_url}

Caducidad: {expires_text}

{f'Observaciones: {safe_note}' if safe_note else ''}

Emitido por: {doctor_name}
Universidad Estatal de Milagro (UNEMI)
"""

    # 1. Enviar vía Django EmailMessage
    django_ok = False
    try:
        msg = EmailMessage(
            subject=subj,
            body=html_content,
            from_email=from_email,
            to=[clean_email],
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
        django_ok = True
    except Exception as e:
        logger.exception(f"[SECURE_SHARE_EMAIL] Error al enviar correo vía Django a {clean_email}: {e}")

    # 2. Si Gmail SMTP está configurado y habilitado, enviar directamente
    if sender_email and raw_app_password and cfg.gmail_api_enabled:
        ok, err = _send_smtp_gmail(
            sender_email=sender_email,
            app_password=raw_app_password,
            recipient_email=clean_email,
            subject=subj,
            plain_msg=plain_message,
            html_msg=html_content,
            attachments=None
        )
        if ok:
            return {"success": True, "smtp_delivered": True, "recipient": clean_email}
        else:
            return {"success": django_ok, "smtp_delivered": False, "recipient": clean_email, "error": err}

    return {"success": django_ok, "smtp_delivered": False, "recipient": clean_email, "note": "Enviado por consola/backend"}
