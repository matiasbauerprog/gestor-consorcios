"""Envío de correo diferido: sale después de que la respuesta ya se fue.

Antes el mail se mandaba dentro de la operación. Un comunicado a cuarenta
departamentos eran cuarenta handshakes SMTP con el request abierto y el
usuario mirando una pantalla trabada.

El payload viaja completo (to/subject/body ya armados) porque la tarea de
fondo corre con la sesión de request ya cerrada: no puede tocar la DB para
resolver nada. La única DB que abre es una propia, y sólo para registrar un
error si el envío falla.
"""
import logging
from dataclasses import dataclass

from fastapi import BackgroundTasks

from .. import errores
from ..mail_service import enviar_email

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MailPendiente:
    to: str
    subject: str
    body: str
    clave_evento: str


def enviar_uno(mail: MailPendiente) -> None:
    """Manda un mail. Nunca levanta: es el contrato con BackgroundTasks.

    Una excepción acá no tendría a quién propagar —la respuesta ya salió— y
    en algunos servidores tumba el worker. Se registra y se sigue.
    """
    try:
        enviar_email(
            to=mail.to, subject=mail.subject, body=mail.body, attachments=[],
        )
    except Exception as exc:  # noqa: BLE001 — ver docstring
        _registrar(exc, mail)


def _registrar(exc: Exception, mail: MailPendiente) -> None:
    # Import local: `database` importa modelos, y a nivel de módulo esto
    # cierra un ciclo con `backend.notificaciones`.
    from ..database import SessionLocal

    db = None
    try:
        db = SessionLocal()
        errores.registrar(
            exc,
            ruta=f"notificaciones/{mail.clave_evento}",
            metodo="EMAIL",
            usuario_id=None,
            rol=None,
            consorcio_id=None,
            db=db,
        )
    except Exception as propio:  # noqa: BLE001 — nunca tapar el original
        logger.error(
            "No se pudo registrar el fallo de envío a %s: %s", mail.to, propio,
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001 — la sesión ya puede estar rota
                pass


def encolar(tareas: BackgroundTasks | None, mails: list[MailPendiente]) -> None:
    """Encola los mails. Sin `tareas` (tests, scripts) envía en línea."""
    for mail in mails:
        if tareas is None:
            enviar_uno(mail)
        else:
            tareas.add_task(enviar_uno, mail)
