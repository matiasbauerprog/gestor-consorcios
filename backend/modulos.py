"""Catálogo de módulos habilitables por administración (control de super_admin).

`require_modulo(key)` es una dependency-factory router-level: hereda los
chequeos de `get_consorcio_activo` (header, password, suspensión) y suma el
gate del módulo. NULL en `Administracion.modulos_habilitados` = todos activos.
"""
from __future__ import annotations

import json

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Administracion, Consorcio
from .tenant import get_consorcio_activo

MODULOS = (
    "comunicacion",
    "cobranzas",
    "gastos",
    "finanzas",
    "operacion",
    "espacios_comunes",
    "reportes",
    "personal",
)


def modulos_habilitados_de(admin: Administracion) -> set[str]:
    if admin.modulos_habilitados is None:
        return set(MODULOS)
    return set(json.loads(admin.modulos_habilitados))


def require_modulo(modulo: str):
    if modulo not in MODULOS:
        raise ValueError(f"Módulo desconocido: {modulo}")

    def dep(
        cid: int = Depends(get_consorcio_activo),
        db: Session = Depends(get_db),
    ) -> int:
        admin = db.scalar(
            select(Administracion)
            .join(Consorcio, Consorcio.administracion_id == Administracion.id)
            .where(Consorcio.id == cid)
        )
        if admin is None or modulo not in modulos_habilitados_de(admin):
            raise HTTPException(status_code=403, detail="modulo_no_habilitado")
        return cid

    return dep
