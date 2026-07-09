"""
Seed idempotente del super_admin.

Uso: SUPER_ADMIN_EMAIL=x SUPER_ADMIN_PASSWORD=y python -m backend.seed_super_admin [--force]
"""
import argparse
import logging
import os

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Rol, Usuario
from .security import hash_password

logger = logging.getLogger(__name__)


def seed(db: Session, *, force: bool = False) -> Usuario:
    # Lee os.environ en cada llamada (no get_settings): el cache de lru_cache
    # ignoraría variables seteadas después del primer acceso.
    email = os.environ.get("SUPER_ADMIN_EMAIL", "")
    password = os.environ.get("SUPER_ADMIN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("SUPER_ADMIN_EMAIL y SUPER_ADMIN_PASSWORD son requeridos")

    existente = db.query(Usuario).filter(Usuario.rol == Rol.super_admin).first()
    if existente is not None:
        if force:
            existente.password_hash = hash_password(password)
            existente.email = email
            db.commit()
            logger.info("Password del super_admin reseteado (--force)")
            return existente
        logger.info(f"Super_admin ya existe ({existente.email}), nada que hacer")
        return existente

    u = Usuario(
        email=email,
        password_hash=hash_password(password),
        rol=Rol.super_admin,
    )
    db.add(u)
    db.commit()
    logger.info(f"Super_admin creado: {email}")
    return u


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Resetear password si existe")
    args = parser.parse_args()
    with SessionLocal() as db:
        seed(db, force=args.force)


if __name__ == "__main__":
    main()
