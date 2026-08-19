"""El emisor: única puerta de entrada para generar notificaciones.

No sabe nada de eventos concretos. Lee el catálogo, resuelve destinatarios,
descarta al actor, persiste la campanita y encola el mail. Agregar un evento
no toca este archivo.
"""
from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Notificacion
from .catalogo import evento as _evento
from .correo import MailPendiente, encolar
from .destinatarios import resolver_destinatarios
from .preferencias import email_activo_para


def emitir(
    db: Session,
    clave: str,
    *,
    consorcio_id: int,
    contexto: dict,
    actor_usuario_id: int | None,
    departamento_id: int | None = None,
    entidad_id: int | None = None,
    tareas: BackgroundTasks | None = None,
    restringir_a_usuario_id: int | None = None,
) -> None:
    """Emite un evento del catálogo. NO commitea — el caller lo hace.

    Va dentro de la transacción de la operación que lo causó: si esa
    operación falla, no queda un aviso fantasma.

    `restringir_a_usuario_id` acota los destinatarios ya resueltos a esa única
    persona. Existe para los avisos redactados en segunda persona hacia alguien
    concreto y no hacia la unidad: "tu reserva fue confirmada, se cargó $N a tu
    cuenta". Si en la unidad viven propietario e inquilino y reserva uno, al
    otro ese texto le hablaría de algo que no hizo. Si el usuario no está entre
    los destinatarios resueltos, no se emite nada.
    """
    ev = _evento(clave)

    destinatarios = resolver_destinatarios(
        db, ev.audiencia,
        consorcio_id=consorcio_id,
        departamento_id=departamento_id,
        excluir_usuario_id=actor_usuario_id,
    )
    if restringir_a_usuario_id is not None:
        destinatarios = [
            u for u in destinatarios if u.id == restringir_a_usuario_id
        ]
    if not destinatarios:
        return

    mails: list[MailPendiente] = []

    for u in destinatarios:
        if ev.crea_campanita:
            db.add(Notificacion(
                consorcio_id=consorcio_id,
                usuario_id=u.id,
                tipo=ev.clave,
                mensaje=ev.mensaje(contexto),
                link=ev.link(contexto),
                entidad_tipo=ev.entidad_tipo,
                entidad_id=entidad_id if ev.entidad_tipo else None,
            ))

        if u.email and email_activo_para(db, u.id, ev):
            # Payload completo ACÁ: la tarea de fondo corre con la sesión
            # cerrada y no puede resolver nada contra la DB.
            mails.append(MailPendiente(
                to=u.email,
                subject=ev.asunto(contexto),
                body=ev.cuerpo(contexto),
                clave_evento=ev.clave,
            ))

    encolar(tareas, mails)


def resolver_pendiente(
    db: Session,
    *,
    consorcio_id: int,
    entidad_tipo: str,
    entidad_id: int,
) -> int:
    """Apaga el pendiente para TODOS sus destinatarios. Devuelve cuántos apagó.

    Que Ana apruebe el comprobante le apaga el puntito a Juan también: el
    puntito significa "te queda algo por hacer", no "hay novedades". Juan
    puede no llegar a verlo nunca; el hecho igual queda en su historial, ya
    marcado como leído.

    NO commitea — el caller lo hace.
    """
    ids = list(db.scalars(
        select(Notificacion.id).where(
            Notificacion.consorcio_id == consorcio_id,
            Notificacion.entidad_tipo == entidad_tipo,
            Notificacion.entidad_id == entidad_id,
            Notificacion.leida == False,  # noqa: E712
        )
    ).all())
    if not ids:
        return 0

    db.execute(
        update(Notificacion)
        .where(Notificacion.id.in_(ids))
        .values(leida=True)
    )
    return len(ids)
