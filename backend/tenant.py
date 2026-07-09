"""
Dependency FastAPI que resuelve el consorcio activo del header X-Consorcio-Id
y valida que el usuario autenticado tenga acceso.

También hace enforcement del flag `must_change_password`: si el usuario tiene
must_change_password=True, todo endpoint operacional devuelve 403 con detail
"cambio_password_requerido". Los endpoints exentos son `/auth/*`, `/me/*`
(no incluyen a este resolver como dep).
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .database import get_db
from .models import Administracion, Consorcio, Departamento, Rol, Usuario


def get_consorcio_activo(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """
    Resuelve X-Consorcio-Id del header, valida acceso, devuelve el ID.

    - Chequea must_change_password: 403 con detail="cambio_password_requerido".
    - super_admin: 403 (no opera directo en consorcios; usa impersonate — Plan B).
    - admin: 200 si el consorcio pertenece a su administracion_id.
    - representante: 200 si el consorcio es el suyo.
    - departamento: 200 si el consorcio es el de su departamento.
    """
    raw = request.headers.get("X-Consorcio-Id") or request.headers.get("x-consorcio-id")
    if not raw:
        raise HTTPException(400, "X-Consorcio-Id requerido")
    try:
        cid = int(raw)
    except ValueError:
        raise HTTPException(400, "X-Consorcio-Id invalido")

    u = db.get(Usuario, user.id)
    if u is None:
        raise HTTPException(401)
    if u.must_change_password:
        raise HTTPException(403, "cambio_password_requerido")

    if u.rol == Rol.administracion:
        ok = db.query(Consorcio.id).filter(
            Consorcio.id == cid,
            Consorcio.administracion_id == u.administracion_id,
        ).first() is not None
    elif u.rol == Rol.representante:
        ok = u.consorcio_id == cid
    elif u.rol == Rol.departamento:
        d = db.get(Departamento, u.departamento_id) if u.departamento_id else None
        ok = d is not None and d.consorcio_id == cid
    else:
        # super_admin u otro rol
        raise HTTPException(403, "rol_sin_scope_de_consorcio")

    if not ok:
        raise HTTPException(403, "sin acceso a este consorcio")

    # Corta tokens vigentes de una administración suspendida: el login ya la
    # bloquea, pero sin este chequeo un JWT emitido antes de suspender seguiría
    # operando hasta su exp.
    suspendida = db.query(Administracion.id).join(
        Consorcio, Consorcio.administracion_id == Administracion.id
    ).filter(
        Consorcio.id == cid,
        Administracion.activa == False,  # noqa: E712
    ).first() is not None
    if suspendida:
        raise HTTPException(403, "administracion_suspendida")

    return cid
