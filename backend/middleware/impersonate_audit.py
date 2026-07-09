"""Middleware que loguea acciones mutantes cuando el JWT tiene el claim
`impersonated_by`. Los GETs no se loguean — el `impersonate_start` en el audit
log ya deja constancia de la sesión completa.

Notas de diseño:
- Se decodifica el JWT sin verificar `exp` (ya lo validó `get_current_user`).
- No falla el request si el logging falla — hace rollback silencioso.
- El body se lee de `request` post `call_next` a través del scope receive
  cacheado antes de invocar el endpoint.
"""
from __future__ import annotations

import json

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .. import database as _db_module
from ..audit import crear_audit_log_entry
from ..config import get_settings
from ..models import Consorcio, Departamento, Usuario

_MUTANTES = {"POST", "PUT", "PATCH", "DELETE"}


class ImpersonateAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Cachear body antes del endpoint (para poder loguearlo después sin
        # consumir el stream).
        body_bytes = b""
        if request.method in _MUTANTES:
            try:
                body_bytes = await request.body()
            except Exception:
                body_bytes = b""

            # Re-inyectar el body en el scope para que el endpoint pueda leerlo.
            async def _receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request._receive = _receive  # noqa: SLF001

        response: Response = await call_next(request)

        if request.method not in _MUTANTES:
            return response
        if response.status_code >= 400:
            return response

        auth = request.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            return response
        token = auth.removeprefix("Bearer ").strip()

        try:
            claims = jwt.decode(
                token,
                get_settings().SECRET_KEY,
                algorithms=[get_settings().JWT_ALGORITHM],
                options={"verify_exp": False},
            )
        except jwt.PyJWTError:
            return response

        impersonated_by = claims.get("impersonated_by")
        if impersonated_by is None:
            return response

        body_repr: object
        if body_bytes:
            try:
                body_repr = json.loads(body_bytes)
            except Exception:
                body_repr = body_bytes[:200].decode(errors="replace")
        else:
            body_repr = None

        cid_raw = request.headers.get("X-Consorcio-Id")
        administracion_id_afectada: int | None = None

        db = _db_module.SessionLocal()
        try:
            usuario_id = int(claims.get("sub", "0") or 0)
            u = db.get(Usuario, usuario_id) if usuario_id else None
            if u is not None:
                if u.administracion_id:
                    administracion_id_afectada = u.administracion_id
                elif u.departamento_id:
                    d = db.get(Departamento, u.departamento_id)
                    if d is not None:
                        c = db.get(Consorcio, d.consorcio_id)
                        if c is not None:
                            administracion_id_afectada = c.administracion_id

            crear_audit_log_entry(
                db,
                super_admin_usuario_id=int(impersonated_by),
                accion="impersonate_mutacion",
                administracion_id_afectada=administracion_id_afectada,
                detalles={
                    "method": request.method,
                    "path": request.url.path,
                    "consorcio_id": cid_raw,
                    "body": body_repr,
                    "status": response.status_code,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return response
