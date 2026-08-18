"""Tokens de recuperación de contraseña.

Aparte del router a propósito: son las reglas que importan (un solo uso,
vencimiento, límite de pedidos) y conviene poder testearlas sin levantar HTTP.

El token en claro se genera acá, se devuelve para el email y **no se persiste**:
en la base va sólo su sha256. No hace falta bcrypt como en las contraseñas —
el token tiene 256 bits de aleatoriedad, así que no hay diccionario que lo
adivine, y sha256 mantiene el canje barato.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import TokenRecuperacion, Usuario


def hashear(token_claro: str) -> str:
    return hashlib.sha256(token_claro.encode()).hexdigest()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def emitir_token(db: Session, usuario: Usuario) -> str | None:
    """Emite un token nuevo para `usuario` y devuelve el claro, o `None` si
    superó el límite de pedidos por hora.

    El límite se cuenta contra la base y no en memoria: sobrevive a un reinicio
    del servidor y funciona igual con más de una instancia.
    """
    settings = get_settings()
    ahora = _ahora()

    emitidos = db.scalar(
        select(func.count())
        .select_from(TokenRecuperacion)
        .where(
            TokenRecuperacion.usuario_id == usuario.id,
            TokenRecuperacion.creado_at >= ahora - timedelta(hours=1),
        )
    )
    if emitidos >= settings.RECUPERACION_MAX_POR_HORA:
        return None

    # Pedir un link nuevo invalida los anteriores: si no, un link viejo
    # reenviado o filtrado seguiría sirviendo.
    for viejo in db.scalars(
        select(TokenRecuperacion).where(
            TokenRecuperacion.usuario_id == usuario.id,
            TokenRecuperacion.usado_at.is_(None),
        )
    ):
        viejo.usado_at = ahora

    claro = secrets.token_urlsafe(32)
    db.add(
        TokenRecuperacion(
            usuario_id=usuario.id,
            token_hash=hashear(claro),
            expira_at=ahora + timedelta(minutes=settings.RECUPERACION_TOKEN_MINUTOS),
        )
    )
    db.commit()
    return claro


def canjear_token(db: Session, token_claro: str) -> Usuario | None:
    """Valida el token y lo marca usado. Devuelve el usuario, o `None` si el
    token no existe, ya se usó o venció."""
    if not token_claro:
        return None

    token = db.scalar(
        select(TokenRecuperacion).where(
            TokenRecuperacion.token_hash == hashear(token_claro)
        )
    )
    if token is None or token.usado_at is not None:
        return None

    # SQLite devuelve datetimes sin tzinfo; se normalizan para poder compararlos
    # con un `now` que sí la tiene.
    expira = token.expira_at
    if expira.tzinfo is None:
        expira = expira.replace(tzinfo=timezone.utc)
    if expira < _ahora():
        return None

    token.usado_at = _ahora()
    db.commit()
    return db.get(Usuario, token.usuario_id)
