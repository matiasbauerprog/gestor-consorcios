"""Sistema de notificaciones — Fase 11.

Doble canal:
- in-app: persiste un Notificacion en DB (campanita del frontend lo lee via polling).
- email: best-effort vía backend.email (modo console si SMTP_HOST vacío).

Helper `crear_notificacion` reusable para cualquier evento futuro.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .email import enviar_email
from .models import EstadoPeticion, Notificacion, Peticion, Rol, Usuario


def crear_notificacion(
    db: Session,
    usuario_id: int,
    mensaje: str,
    link: str | None = None,
) -> Notificacion:
    """Persiste una Notificacion para un usuario. No commitea — el caller lo hace."""
    notif = Notificacion(usuario_id=usuario_id, mensaje=mensaje, link=link)
    db.add(notif)
    return notif


def notificar_cambio_estado_peticion(
    db: Session,
    peticion: Peticion,
    estado_anterior: EstadoPeticion,
) -> None:
    """Doble canal cuando la petición pasa a convertida_en_trabajo o rechazada.

    No notifica si el estado no cambió, o si el nuevo estado es 'abierta'.
    Best-effort: si email falla, la in-app igual queda.
    """
    if estado_anterior == peticion.estado:
        return
    if peticion.estado not in (EstadoPeticion.convertida_en_trabajo, EstadoPeticion.rechazada):
        return

    usuarios = list(db.scalars(
        select(Usuario).where(
            Usuario.departamento_id == peticion.departamento_id,
            Usuario.rol == Rol.departamento,
        )
    ).all())

    mensaje = f"Tu petición '{peticion.titulo}' cambió de estado a: {peticion.estado.value}."

    for u in usuarios:
        crear_notificacion(db, usuario_id=u.id, mensaje=mensaje, link="/peticiones")
        if u.email:
            enviar_email(
                to=u.email,
                subject=f"Tu petición #{peticion.id} fue actualizada",
                body=f"Hola,\n\n{mensaje}\n\nSaludos,\nAdministración.",
                attachments=[],
            )
