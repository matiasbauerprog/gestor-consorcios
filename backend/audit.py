"""Helpers para el audit log del super-admin.

- `redactar_payload`: convierte un dict a un dict serializable con campos
  sensibles reemplazados por "[REDACTED]" y truncado a 500 caracteres.
- `crear_audit_log_entry`: persiste una fila en `audit_log_super_admin`.
  No commitea; el caller decide.
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLogSuperAdmin

_CLAVES_SENSIBLES = re.compile(r"password|token|secret", re.IGNORECASE)
_MAX_LEN = 500


def _redactar_recursivo(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED]" if _CLAVES_SENSIBLES.search(k) else _redactar_recursivo(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redactar_recursivo(x) for x in obj]
    return obj


def redactar_payload(payload: Any) -> Any:
    """Redacta claves sensibles y trunca la serialización a 500 chars."""
    red = _redactar_recursivo(payload)
    s = json.dumps(red, default=str, ensure_ascii=False)
    if len(s) <= _MAX_LEN:
        return red
    return s[:_MAX_LEN - 3] + "..."


def crear_audit_log_entry(
    db: Session,
    *,
    super_admin_usuario_id: int,
    accion: str,
    administracion_id_afectada: int | None = None,
    motivo: str | None = None,
    detalles: Any | None = None,
) -> AuditLogSuperAdmin:
    """Persiste una entrada de audit log. No commitea."""
    detalles_str: str | None = None
    if detalles is not None:
        red = redactar_payload(detalles)
        detalles_str = red if isinstance(red, str) else json.dumps(red, default=str, ensure_ascii=False)

    entry = AuditLogSuperAdmin(
        super_admin_usuario_id=super_admin_usuario_id,
        accion=accion,
        administracion_id_afectada=administracion_id_afectada,
        motivo=motivo,
        detalles=detalles_str,
    )
    db.add(entry)
    db.flush()
    return entry
