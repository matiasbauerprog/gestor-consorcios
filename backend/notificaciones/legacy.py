"""Sistema de notificaciones — Fase 11.

Doble canal:
- in-app: persiste un Notificacion en DB (campanita del frontend lo lee via polling).
- email: best-effort vía backend.email (modo console si SMTP_HOST vacío).

Helper `crear_notificacion` reusable para cualquier evento futuro.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..mail_service import enviar_email
from ..models import EstadoPeticion, Notificacion, Peticion, Rol, Usuario


def crear_notificacion(
    db: Session,
    *,
    consorcio_id: int,
    usuario_id: int,
    mensaje: str,
    link: str | None = None,
) -> Notificacion:
    """Persiste una Notificacion para un usuario. No commitea — el caller lo hace."""
    notif = Notificacion(
        consorcio_id=consorcio_id,
        usuario_id=usuario_id,
        mensaje=mensaje,
        link=link,
    )
    db.add(notif)
    return notif


def notificar_cambio_estado_peticion(
    db: Session,
    peticion: Peticion,
    estado_anterior: EstadoPeticion,
) -> None:
    """Doble canal cuando la petición pasa a convertida_en_trabajo, rechazada o cancelada.

    No notifica si el estado no cambió, o si el nuevo estado es 'abierta'.
    Best-effort: si email falla, la in-app igual queda.
    """
    if estado_anterior == peticion.estado:
        return
    if peticion.estado not in (
        EstadoPeticion.convertida_en_trabajo,
        EstadoPeticion.rechazada,
        EstadoPeticion.cancelada,
    ):
        return

    usuarios = list(db.scalars(
        select(Usuario).where(
            Usuario.departamento_id == peticion.departamento_id,
            Usuario.rol == Rol.departamento,
        )
    ).all())

    mensaje = f"Tu petición '{peticion.titulo}' cambió de estado a: {peticion.estado.value}."

    for u in usuarios:
        crear_notificacion(
            db,
            consorcio_id=peticion.consorcio_id,
            usuario_id=u.id,
            mensaje=mensaje,
            link="/peticiones",
        )
        if u.email:
            enviar_email(
                to=u.email,
                subject=f"Tu petición #{peticion.id} fue actualizada",
                body=f"Hola,\n\n{mensaje}\n\nSaludos,\nAdministración.",
                attachments=[],
            )


def notificar_reserva_creada(
    db: Session,
    reserva,  # type: Reserva
    amenity_nombre: str,
    monto_cobrado: float | None,
) -> None:
    """Email-only al depto que reservó. Sin campanita (acaba de ver la confirmación)."""
    from ..models import Rol, Usuario

    usuario = db.get(Usuario, reserva.usuario_id)
    if usuario is None or usuario.rol != Rol.departamento or not usuario.email:
        return

    fecha_str = reserva.inicio.strftime("%Y-%m-%d %H:%M")
    cuerpo = f"Tu reserva de {amenity_nombre} para el {fecha_str} fue confirmada."
    if monto_cobrado is not None:
        cuerpo += f"\nSe cargó ${monto_cobrado:.2f} a tu cuenta corriente."
    cuerpo += "\n\nSaludos,\nAdministración."

    enviar_email(
        to=usuario.email,
        subject=f"Reserva confirmada: {amenity_nombre}",
        body=cuerpo,
        attachments=[],
    )


def notificar_reserva_cancelada_por_admin(
    db: Session,
    reserva,  # type: Reserva
    amenity_nombre: str,
    monto_reversado: float | None,
) -> None:
    """Doble canal cuando admin cancela una reserva ajena."""
    from ..models import Rol, Usuario

    usuarios = list(db.scalars(
        select(Usuario).where(
            Usuario.id == reserva.usuario_id,
            Usuario.rol == Rol.departamento,
        )
    ).all())

    if not usuarios:
        return

    fecha_str = reserva.inicio.strftime("%Y-%m-%d %H:%M")
    mensaje = f"La administración canceló tu reserva de {amenity_nombre} del {fecha_str}."
    if monto_reversado is not None:
        mensaje += f" Se reversó el cargo de ${monto_reversado:.2f}."

    for u in usuarios:
        crear_notificacion(
            db,
            consorcio_id=reserva.consorcio_id,
            usuario_id=u.id,
            mensaje=mensaje,
            link="/reservas",
        )
        if u.email:
            enviar_email(
                to=u.email,
                subject=f"Tu reserva de {amenity_nombre} fue cancelada",
                body=f"Hola,\n\n{mensaje}\n\nSaludos,\nAdministración.",
                attachments=[],
            )
