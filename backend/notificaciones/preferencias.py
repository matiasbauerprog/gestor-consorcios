"""Preferencias de mail por usuario y por evento.

Se persiste sólo la diferencia contra el default del catálogo. Un usuario
que nunca opinó no tiene fila, así que cambiar un default más adelante lo
alcanza a él y respeta al que sí opinó.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PreferenciaNotificacion
from .catalogo import EventoNotificacion


def preferencias_de(db: Session, usuario_id: int) -> dict[str, bool]:
    """Sólo las filas guardadas — los defaults no aparecen acá."""
    filas = db.scalars(
        select(PreferenciaNotificacion).where(
            PreferenciaNotificacion.usuario_id == usuario_id
        )
    ).all()
    return {f.tipo: f.email_activo for f in filas}


def email_activo_para(db: Session, usuario_id: int, ev: EventoNotificacion) -> bool:
    """Valor efectivo: la fila del usuario si existe, el default si no."""
    if not ev.puede_mandar_mail:
        return False
    fila = db.scalar(
        select(PreferenciaNotificacion).where(
            PreferenciaNotificacion.usuario_id == usuario_id,
            PreferenciaNotificacion.tipo == ev.clave,
        )
    )
    if fila is None:
        return ev.email_por_defecto
    return fila.email_activo


def guardar_preferencia(
    db: Session, usuario_id: int, ev: EventoNotificacion, email_activo: bool
) -> None:
    """Crea, actualiza o borra la fila según se aparte o no del default.

    No commitea — el caller lo hace.
    """
    fila = db.scalar(
        select(PreferenciaNotificacion).where(
            PreferenciaNotificacion.usuario_id == usuario_id,
            PreferenciaNotificacion.tipo == ev.clave,
        )
    )

    if email_activo == ev.email_por_defecto:
        # Volver al default es dejar de tener opinión, no guardar el default.
        if fila is not None:
            db.delete(fila)
        return

    if fila is None:
        db.add(PreferenciaNotificacion(
            usuario_id=usuario_id, tipo=ev.clave, email_activo=email_activo,
        ))
    else:
        fila.email_activo = email_activo
