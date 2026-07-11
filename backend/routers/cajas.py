"""CRUD de Cajas — admin only."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..caja_saldo import MovimientoSnapshot, calcular_saldo
from ..database import get_db
from ..models import Caja, MovimientoCaja, PeriodoCerrado, Rol, TipoMovimientoCaja
from ..modulos import require_modulo
from ..schemas import AjusteCrear, CajaCrear, CajaActualizar, CajaOut, MovimientoCajaOut
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/cajas",
    tags=["Cajas"],
    dependencies=[Depends(require_modulo("finanzas"))],
)


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


def _bloquear_si_periodo_cerrado_por_fecha(db: Session, cid: int, fecha) -> None:
    """Verifica que el consorcio no haya cerrado el período YYYY-MM de la fecha."""
    periodo = f"{fecha.year:04d}-{fecha.month:02d}"
    if db.get(PeriodoCerrado, (periodo, cid)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )


@router.get("", response_model=list[CajaOut])
def listar_cajas(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[CajaOut]:
    cajas = db.scalars(select(Caja).where(Caja.consorcio_id == cid).order_by(Caja.id)).all()
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
    cid: int = Depends(get_consorcio_activo),
) -> CajaOut:
    if db.scalar(select(Caja).where(Caja.consorcio_id == cid, Caja.nombre == payload.nombre)):
        raise HTTPException(400, f"Ya existe una caja con el nombre '{payload.nombre}'.")
    caja = Caja(consorcio_id=cid, **payload.model_dump())
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
    cid: int = Depends(get_consorcio_activo),
) -> CajaOut:
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
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
    cid: int = Depends(get_consorcio_activo),
):
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
        raise HTTPException(404, "Caja no encontrada.")
    tiene_movs = db.scalar(
        select(MovimientoCaja.id).where(MovimientoCaja.caja_id == caja_id)
    )
    if tiene_movs:
        raise HTTPException(409, "La caja tiene movimientos. Marcala inactiva en lugar de borrarla.")
    db.delete(caja)
    db.commit()


@router.get("/{caja_id}/movimientos", response_model=list[MovimientoCajaOut])
def listar_movimientos(
    caja_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[MovimientoCaja]:
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
        raise HTTPException(404, "Caja no encontrada.")
    return list(db.scalars(
        select(MovimientoCaja)
        .where(MovimientoCaja.caja_id == caja_id)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(limit).offset(offset)
    ).all())


@router.post(
    "/{caja_id}/movimientos",
    response_model=MovimientoCajaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cargar ajuste manual (no usar para ingreso/egreso, se generan auto)"
)
def crear_ajuste(
    caja_id: int,
    payload: AjusteCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> MovimientoCaja:
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
        raise HTTPException(404, "Caja no encontrada.")
    if not caja.activa:
        raise HTTPException(400, "La caja está inactiva.")
    _bloquear_si_periodo_cerrado_por_fecha(db, cid, payload.fecha)
    mov = MovimientoCaja(
        consorcio_id=cid,
        caja_id=caja_id,
        fecha=payload.fecha,
        tipo=TipoMovimientoCaja.ajuste,
        monto=payload.monto,
        descripcion=payload.descripcion,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov
