import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status

from . import blacklist
from .config import Settings, get_settings
from .models import Rol


@dataclass(frozen=True)
class CurrentUser:
    id: int
    rol: Rol
    departamento_id: int | None
    jti: str
    exp: int


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "No tiene permisos para acceder a este recurso.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def create_access_token(
    user_id: int,
    rol: Rol,
    departamento_id: int | None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "rol": rol.value,
        "departamento_id": departamento_id,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRES_MIN)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, settings: Settings | None = None) -> CurrentUser:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expirado.") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Token inválido.") from exc

    sub = payload.get("sub")
    rol_raw = payload.get("rol")
    departamento_id = payload.get("departamento_id")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if sub is None or rol_raw is None or jti is None or exp is None:
        raise _unauthorized("Token incompleto.")

    try:
        user_id = int(sub)
        rol = Rol(rol_raw)
        exp_int = int(exp)
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Token con claims inválidos.") from exc

    if rol == Rol.departamento and not isinstance(departamento_id, int):
        raise _unauthorized("Token sin departamento asociado.")

    # Revocación (logout): si el jti está en la blacklist, rechazar.
    if blacklist.is_revoked(jti):
        raise _unauthorized("Token revocado.")

    return CurrentUser(
        id=user_id,
        rol=rol,
        departamento_id=departamento_id,
        jti=jti,
        exp=exp_int,
    )


def get_current_user(request: Request) -> CurrentUser:
    auth = request.headers.get("Authorization")
    if not auth:
        raise _unauthorized("No se proporcionó token de autenticación.")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Esquema de autenticación inválido.")
    return decode_token(token)


def require_roles(*roles: Rol):
    allowed = {r for r in roles}

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.rol not in allowed:
            raise _forbidden()
        return user

    return _dep
