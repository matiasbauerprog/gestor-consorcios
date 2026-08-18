"""Envío de email con modo console fallback para dev/test.

Si SMTP_HOST está vacío en config, los emails se loggean al stdout
en lugar de mandarse — útil para desarrollo y CI sin SMTP real.
"""
import logging
import smtplib
from email.message import EmailMessage

from .config import get_settings

logger = logging.getLogger(__name__)


def enviar_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    """Envía un email. Modo console si SMTP_HOST vacío.

    Args:
        to: destinatario (string single email).
        subject: asunto.
        body: cuerpo (texto plano).
        attachments: lista de tuplas (filename, content_bytes, mime_type).

    Returns:
        True si OK (incluido modo console), False si falló el envío.
    """
    attachments = attachments or []
    settings = get_settings()

    # DEMO_MODE fuerza consola: el demo es público y no debe mandar mail real
    # a nadie, aunque el servicio tenga SMTP configurado por error.
    if settings.DEMO_MODE or not settings.SMTP_HOST:
        # Modo console: loggear y devolver True
        print(f"[EMAIL CONSOLE MODE] To: {to} | Subject: {subject}")
        print(f"[EMAIL CONSOLE MODE] Body:\n{body}")
        for fname, content, mime in attachments:
            print(f"[EMAIL CONSOLE MODE] Attachment: {fname} ({len(content)} bytes, {mime})")
        return True

    msg = EmailMessage()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    for fname, content, mime in attachments:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=fname)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        # ERROR y no print: un envío fallido es un problema real y tiene que
        # poder filtrarse como tal en el registro de producción. Se sigue
        # devolviendo False en vez de propagar, para que quien llama decida
        # (en la recuperación de contraseña, por ejemplo, un fallo de envío no
        # debe cambiar la respuesta: delataría qué emails están registrados).
        logger.error("[EMAIL ERROR] To: %s | Error: %s", to, e)
        return False
