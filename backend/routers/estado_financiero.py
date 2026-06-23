"""GET /estado-financiero — dashboard de tesorería."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..caja_saldo import MovimientoSnapshot, calcular_saldo
from ..database import get_db
from ..models import Caja, MovimientoCaja, Rol
from ..schemas import CajaOut, EstadoFinancieroOut, MovimientoCajaOut

router = APIRouter(prefix="/estado-financiero", tags=["EstadoFinanciero"])


@router.get("", response_model=EstadoFinancieroOut)
def obtener_estado_financiero(
    ultimos: int = 20,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EstadoFinancieroOut:
    cajas_activas = list(db.scalars(
        select(Caja).where(Caja.activa == True).order_by(Caja.id)
    ).all())
    cajas_out = []
    total = 0.0
    for c in cajas_activas:
        movs = list(db.scalars(
            select(MovimientoCaja).where(MovimientoCaja.caja_id == c.id)
        ).all())
        snaps = [MovimientoSnapshot(tipo=m.tipo.value, monto=m.monto) for m in movs]
        saldo = calcular_saldo(c.saldo_inicial, snaps)
        total += saldo
        cajas_out.append(CajaOut(
            id=c.id, nombre=c.nombre, tipo=c.tipo, descripcion=c.descripcion,
            saldo_inicial=c.saldo_inicial, saldo_actual=saldo, activa=c.activa,
        ))
    ultimos_movs = list(db.scalars(
        select(MovimientoCaja)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(ultimos)
    ).all())
    return EstadoFinancieroOut(
        cajas=cajas_out,
        total=round(total, 2),
        ultimos_movimientos=[MovimientoCajaOut.model_validate(m) for m in ultimos_movs],
    )
