"""CRUD de Cajas — admin only."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..caja_saldo import MovimientoSnapshot, calcular_saldo
from ..database import get_db
from ..models import Caja, MovimientoCaja, Rol
from ..schemas import CajaCrear, CajaActualizar, CajaOut

router = APIRouter(prefix="/cajas", tags=["Cajas"])


def _caja_to_out(caja: Caja, movimientos: list[MovimientoCaja]) -> CajaOut:
    snaps = [MovimientoSnapshot(tipo=m.tipo.value, monto=m.monto) for m in movimientos]
    saldo = calcular_saldo(caja.saldo_inicial, snaps)
    return CajaOut(
        id=caja.id,
        nombre=caja.nombre,
        tipo=caja.tipo,
        descripcion=caja.descripcion,
        saldo_inicial=caja.saldo_inicial,
        saldo_actual=saldo,
        activa=caja.activa,
    )


@router.get("", response_model=list[CajaOut])
def listar_cajas(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[CajaOut]:
    cajas = db.scalars(select(Caja).order_by(Caja.id)).all()
    out = []
    for c in cajas:
        movs = db.scalars(
            select(MovimientoCaja).where(MovimientoCaja.caja_id == c.id)
        ).all()
        out.append(_caja_to_out(c, list(movs)))
    return out


@router.post("", response_model=CajaOut, status_code=status.HTTP_201_CREATED)
def crear_caja(
    payload: CajaCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> CajaOut:
    if db.scalar(select(Caja).where(Caja.nombre == payload.nombre)):
        raise HTTPException(400, f"Ya existe una caja con el nombre '{payload.nombre}'.")
    caja = Caja(**payload.model_dump())
    db.add(caja)
    db.commit()
    db.refresh(caja)
    return _caja_to_out(caja, [])


@router.patch("/{caja_id}", response_model=CajaOut)
def actualizar_caja(
    caja_id: int,
    payload: CajaActualizar,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> CajaOut:
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, "Caja no encontrada.")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(caja, campo, valor)
    db.commit()
    db.refresh(caja)
    movs = list(db.scalars(
        select(MovimientoCaja).where(MovimientoCaja.caja_id == caja.id)
    ).all())
    return _caja_to_out(caja, movs)


@router.delete("/{caja_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_caja(
    caja_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, "Caja no encontrada.")
    tiene_movs = db.scalar(
        select(MovimientoCaja.id).where(MovimientoCaja.caja_id == caja_id)
    )
    if tiene_movs:
        raise HTTPException(409, "La caja tiene movimientos. Marcala inactiva en lugar de borrarla.")
    db.delete(caja)
    db.commit()
