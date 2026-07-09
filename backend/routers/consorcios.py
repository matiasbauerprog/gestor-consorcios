"""Endpoints /consorcios (Plan D).

Reemplazan gradualmente a `/configuracion` (que queda deprecated):
- GET  /consorcios        (admin): listado de consorcios de la administración
- POST /consorcios        (admin): alta con wizard 4-pasos + crea caja default
- GET  /consorcios/{id}   (admin del tenant, depto/rep del propio consorcio)
- PATCH /consorcios/{id}  (admin)

El consorcio pertenece a la Administración del usuario admin (via
`user.administracion_id`). Departamentos y representantes solo pueden leer el
consorcio al que pertenecen (mismo criterio que get_consorcio_activo).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import Caja, Consorcio, Departamento, Rol, TipoCaja, Usuario
from ..schemas import ConsorcioActualizar, ConsorcioCrear, ConsorcioOut

router = APIRouter(prefix="/consorcios", tags=["Consorcios"])


def _administracion_id_del_admin(db: Session, user: CurrentUser) -> int:
    u = db.get(Usuario, user.id)
    if u is None or u.administracion_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene administración asociada.")
    return u.administracion_id


@router.get(
    "",
    response_model=list[ConsorcioOut],
    status_code=status.HTTP_200_OK,
    summary="Listar consorcios de la administración",
)
def listar_consorcios(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Consorcio]:
    admin_id = _administracion_id_del_admin(db, user)
    return list(
        db.scalars(
            select(Consorcio)
            .where(Consorcio.administracion_id == admin_id)
            .order_by(Consorcio.nombre.asc())
        ).all()
    )


@router.post(
    "",
    response_model=ConsorcioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear consorcio (wizard 4-pasos) + caja default",
)
def crear_consorcio(
    payload: ConsorcioCrear,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Consorcio:
    admin_id = _administracion_id_del_admin(db, user)

    duplicado = db.scalar(
        select(Consorcio.id).where(
            Consorcio.administracion_id == admin_id,
            Consorcio.consorcio_cuit == payload.consorcio_cuit,
        )
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un consorcio con ese CUIT en tu administración.",
        )

    consorcio = Consorcio(
        administracion_id=admin_id,
        **payload.model_dump(),
    )
    db.add(consorcio)
    db.flush()

    caja_default = Caja(
        consorcio_id=consorcio.id,
        nombre="Banco principal",
        tipo=TipoCaja.banco,
        saldo_inicial=0.0,
        activa=True,
    )
    db.add(caja_default)
    db.flush()
    consorcio.caja_default_pagos_id = caja_default.id

    db.commit()
    db.refresh(consorcio)
    return consorcio


@router.get(
    "/{consorcio_id}",
    response_model=ConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener consorcio por id",
)
def obtener_consorcio(
    consorcio_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Consorcio:
    consorcio = db.get(Consorcio, consorcio_id)
    if consorcio is None:
        raise HTTPException(status_code=404, detail="Consorcio no encontrado.")

    u = db.get(Usuario, user.id)
    if u is None:
        raise HTTPException(status_code=401)

    if user.rol == Rol.administracion:
        if consorcio.administracion_id != u.administracion_id:
            raise HTTPException(status_code=404, detail="Consorcio no encontrado.")
    elif user.rol == Rol.representante:
        if u.consorcio_id != consorcio_id:
            raise HTTPException(status_code=404, detail="Consorcio no encontrado.")
    elif user.rol == Rol.departamento:
        d = db.get(Departamento, u.departamento_id) if u.departamento_id else None
        if d is None or d.consorcio_id != consorcio_id:
            raise HTTPException(status_code=404, detail="Consorcio no encontrado.")
    else:
        raise HTTPException(status_code=403, detail="Rol sin acceso a consorcios.")

    return consorcio


@router.patch(
    "/{consorcio_id}",
    response_model=ConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Editar consorcio",
)
def actualizar_consorcio(
    consorcio_id: int,
    payload: ConsorcioActualizar,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Consorcio:
    admin_id = _administracion_id_del_admin(db, user)

    consorcio = db.get(Consorcio, consorcio_id)
    if consorcio is None or consorcio.administracion_id != admin_id:
        raise HTTPException(status_code=404, detail="Consorcio no encontrado.")

    cambios = payload.model_dump(exclude_unset=True)

    if "caja_default_pagos_id" in cambios and cambios["caja_default_pagos_id"] is not None:
        caja = db.get(Caja, cambios["caja_default_pagos_id"])
        if caja is None or caja.consorcio_id != consorcio_id:
            raise HTTPException(status_code=400, detail="Caja default inválida.")

    for campo, valor in cambios.items():
        setattr(consorcio, campo, valor)

    db.commit()
    db.refresh(consorcio)
    return consorcio
