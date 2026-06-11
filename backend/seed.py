import logging
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Departamento, EstadoPeticion, Peticion, Rol, Usuario
from .security import hash_password

logger = logging.getLogger(__name__)


def _resolve_default_password() -> tuple[str, bool]:
    cfg = get_settings().SEED_DEFAULT_PASSWORD
    if cfg:
        return cfg, False
    return secrets.token_urlsafe(12), True


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Usuario).limit(1)) is not None:
        return

    password, generated = _resolve_default_password()

    depto_a = Departamento(codigo="UF-1A", descripcion="Piso 1, Unidad A")
    depto_b = Departamento(codigo="UF-2B", descripcion="Piso 2, Unidad B")
    db.add_all([depto_a, depto_b])
    db.flush()

    admin = Usuario(
        email="admin@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.administracion,
        departamento_id=None,
    )
    user_a = Usuario(
        email="depto-a@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.departamento,
        departamento_id=depto_a.id,
    )
    user_b = Usuario(
        email="depto-b@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.departamento,
        departamento_id=depto_b.id,
    )
    db.add_all([admin, user_a, user_b])
    db.flush()

    db.add_all(
        [
            Peticion(
                departamento_id=depto_a.id,
                titulo="Filtración en cocina",
                descripcion="Hay una filtración del piso de arriba en la cocina.",
                estado=EstadoPeticion.abierta,
            ),
            Peticion(
                departamento_id=depto_b.id,
                titulo="Luz quemada en pasillo",
                descripcion="La lámpara del pasillo del 2do piso está quemada.",
                estado=EstadoPeticion.abierta,
            ),
        ]
    )
    db.commit()

    logger.warning(
        "Seed completado. Usuarios: admin id=%s, depto-a id=%s, depto-b id=%s",
        admin.id,
        user_a.id,
        user_b.id,
    )
    if generated:
        logger.warning(
            "SEED_DEFAULT_PASSWORD no definida — generada al vuelo: %s "
            "(guardala ahora; no se persiste).",
            password,
        )
