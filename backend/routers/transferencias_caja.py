"""POST/GET /transferencias-caja — admin only."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    Caja, MovimientoCaja, PeriodoCerrado, Rol,
    TipoMovimientoCaja, TransferenciaCaja
)
from ..modulos import require_modulo
from ..schemas import TransferenciaCajaCrear, TransferenciaCajaOut
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/transferencias-caja",
    tags=["TransferenciasCaja"],
    dependencies=[Depends(require_modulo("finanzas"))],
)


def _bloquear_si_periodo_cerrado_por_fecha(db: Session, cid: int, fecha) -> None:
    periodo = f"{fecha.year:04d}-{fecha.month:02d}"
    if db.get(PeriodoCerrado, (periodo, cid)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )


@router.get("", response_model=list[TransferenciaCajaOut])
def listar_transferencias(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
):
    return list(db.scalars(
        select(TransferenciaCaja)
        .where(TransferenciaCaja.consorcio_id == cid)
        .order_by(TransferenciaCaja.fecha.desc(), TransferenciaCaja.id.desc())
        .limit(limit).offset(offset)
    ).all())


@router.post("", response_model=TransferenciaCajaOut, status_code=status.HTTP_201_CREATED)
def crear_transferencia(
    payload: TransferenciaCajaCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
):
    if payload.caja_origen_id == payload.caja_destino_id:
        raise HTTPException(400, "Origen y destino deben ser cajas distintas.")
    origen = db.get(Caja, payload.caja_origen_id)
    destino = db.get(Caja, payload.caja_destino_id)
    if origen is None or destino is None or origen.consorcio_id != cid or destino.consorcio_id != cid:
        raise HTTPException(404, "Caja origen o destino no encontrada.")
    if not origen.activa or not destino.activa:
        raise HTTPException(400, "Las cajas deben estar activas.")
    _bloquear_si_periodo_cerrado_por_fecha(db, cid, payload.fecha)

    transf = TransferenciaCaja(consorcio_id=cid, **payload.model_dump())
    db.add(transf)
    db.flush()

    db.add_all([
        MovimientoCaja(
            consorcio_id=cid,
            caja_id=payload.caja_origen_id, fecha=payload.fecha,
            tipo=TipoMovimientoCaja.egreso, monto=payload.monto,
            descripcion=f"Transf → {destino.nombre}: {payload.descripcion}",
            transferencia_id=transf.id,
        ),
        MovimientoCaja(
            consorcio_id=cid,
            caja_id=payload.caja_destino_id, fecha=payload.fecha,
            tipo=TipoMovimientoCaja.ingreso, monto=payload.monto,
            descripcion=f"Transf ← {origen.nombre}: {payload.descripcion}",
            transferencia_id=transf.id,
        ),
    ])
    db.commit()
    db.refresh(transf)
    return transf
