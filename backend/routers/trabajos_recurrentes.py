"""Router de plantillas de trabajos recurrentes — Fase 11.

Admin define plantillas y las materializa manualmente con un click.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Proveedor, Rol, Trabajo, TrabajoRecurrente
from ..modulos import require_modulo
from ..tenant import get_consorcio_activo
from ..schemas import (
    TrabajoOut,
    TrabajoRecurrenteActualizar,
    TrabajoRecurrenteCrear,
    TrabajoRecurrenteOut,
)

router = APIRouter(
    prefix="/trabajos-recurrentes",
    tags=["TrabajosRecurrentes"],
    dependencies=[Depends(require_modulo("operacion"))],
)


@router.get("", response_model=list[TrabajoRecurrenteOut])
def listar(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
    cid: int = Depends(get_consorcio_activo),
):
    return list(db.scalars(
        select(TrabajoRecurrente).where(TrabajoRecurrente.consorcio_id == cid).order_by(TrabajoRecurrente.id)
    ).all())


@router.post("", response_model=TrabajoRecurrenteOut, status_code=201)
def crear(
    payload: TrabajoRecurrenteCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
    cid: int = Depends(get_consorcio_activo),
):
    if payload.proveedor_sugerido_id is not None:
        if (p := db.get(Proveedor, payload.proveedor_sugerido_id)) is None or p.consorcio_id != cid:
            raise HTTPException(404, f"Proveedor {payload.proveedor_sugerido_id} no encontrado.")
    tr = TrabajoRecurrente(consorcio_id=cid, **payload.model_dump())
    db.add(tr); db.commit(); db.refresh(tr)
    return tr


@router.patch("/{recurrente_id}", response_model=TrabajoRecurrenteOut)
def actualizar(
    recurrente_id: int,
    payload: TrabajoRecurrenteActualizar,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
    cid: int = Depends(get_consorcio_activo),
):
    tr = db.get(TrabajoRecurrente, recurrente_id)
    if tr is None or tr.consorcio_id != cid:
        raise HTTPException(404, "Recurrente no encontrado.")
    if payload.proveedor_sugerido_id is not None:
        if (p := db.get(Proveedor, payload.proveedor_sugerido_id)) is None or p.consorcio_id != cid:
            raise HTTPException(404, f"Proveedor {payload.proveedor_sugerido_id} no encontrado.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tr, k, v)
    db.commit(); db.refresh(tr)
    return tr


@router.delete("/{recurrente_id}", status_code=204)
def eliminar(
    recurrente_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
    cid: int = Depends(get_consorcio_activo),
):
    tr = db.get(TrabajoRecurrente, recurrente_id)
    if tr is None or tr.consorcio_id != cid:
        raise HTTPException(404, "Recurrente no encontrado.")
    db.delete(tr); db.commit()


@router.post("/{recurrente_id}/materializar", response_model=TrabajoOut, status_code=201)
def materializar(
    recurrente_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
    cid: int = Depends(get_consorcio_activo),
):
    """Crea un Trabajo concreto desde la plantilla."""
    tr = db.get(TrabajoRecurrente, recurrente_id)
    if tr is None or tr.consorcio_id != cid:
        raise HTTPException(404, "Recurrente no encontrado.")
    if not tr.activa:
        raise HTTPException(400, "La plantilla está inactiva.")
    t = Trabajo(consorcio_id=cid, descripcion=f"{tr.nombre} — {tr.descripcion}")
    db.add(t); db.commit(); db.refresh(t)
    return t
