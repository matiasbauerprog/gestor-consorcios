"""Traduce una audiencia del catálogo a la lista concreta de usuarios."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Consorcio, Departamento, Rol, Usuario
from .catalogo import Audiencia


def resolver_destinatarios(
    db: Session,
    audiencia: Audiencia,
    *,
    consorcio_id: int,
    departamento_id: int | None,
    excluir_usuario_id: int | None,
) -> list[Usuario]:
    """Usuarios activos que deben recibir un evento de esta audiencia.

    `excluir_usuario_id` es el actor: nadie recibe el evento que causó.
    """
    if audiencia == Audiencia.DEPARTAMENTO:
        if departamento_id is None:
            raise ValueError(
                "Un evento con audiencia DEPARTAMENTO necesita departamento_id."
            )
        # Join a Departamento para atar la consulta al tenant por sí misma.
        # Hoy los seis call sites derivan `departamento_id` de una entidad ya
        # validada contra el consorcio activo, así que no es explotable —
        # pero es defensa en profundidad: sin este join, un departamento_id
        # de OTRO consorcio (por ejemplo, uno que cambió de dueño) igual
        # resolvería destinatarios reales.
        stmt = select(Usuario).join(
            Departamento, Departamento.id == Usuario.departamento_id,
        ).where(
            Usuario.departamento_id == departamento_id,
            Usuario.rol == Rol.departamento,
            Departamento.consorcio_id == consorcio_id,
        )
    elif audiencia == Audiencia.ADMINISTRACION:
        consorcio = db.get(Consorcio, consorcio_id)
        if consorcio is None:
            return []
        stmt = select(Usuario).where(
            Usuario.administracion_id == consorcio.administracion_id,
            Usuario.rol == Rol.administracion,
        )
    else:  # pragma: no cover — el enum no tiene más miembros
        raise ValueError(f"Audiencia desconocida: {audiencia}")

    stmt = stmt.where(Usuario.activa == True)  # noqa: E712
    if excluir_usuario_id is not None:
        stmt = stmt.where(Usuario.id != excluir_usuario_id)

    return list(db.scalars(stmt.order_by(Usuario.id)).all())
