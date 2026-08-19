"""GET /tesoreria — resumen de tesorería + PDF de movimientos.

No confundir con `/reportes/estado-financiero`: eso es el balance contable
(activo/pasivo/patrimonio a una fecha). Esto es el saldo de las cajas hoy.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..caja_saldo import MovimientoSnapshot, calcular_saldo
from ..database import get_db
from ..models import Caja, Consorcio, MovimientoCaja, Rol
from ..modulos import require_modulo
from ..pdf import generar_pdf_movimientos_caja
from ..schemas import CajaOut, MovimientoCajaOut, ResumenTesoreriaOut
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/tesoreria",
    tags=["Tesoreria"],
    dependencies=[Depends(require_modulo("finanzas"))],
)


@router.get("", response_model=ResumenTesoreriaOut)
def obtener_resumen_tesoreria(
    ultimos: int = 20,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ResumenTesoreriaOut:
    cajas_activas = list(db.scalars(
        select(Caja).where(
            Caja.activa == True,  # noqa: E712
            Caja.consorcio_id == cid,
        ).order_by(Caja.id)
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
        .where(MovimientoCaja.consorcio_id == cid)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(ultimos)
    ).all())
    return ResumenTesoreriaOut(
        cajas=cajas_out,
        total=round(total, 2),
        ultimos_movimientos=[MovimientoCajaOut.model_validate(m) for m in ultimos_movs],
    )


@router.get("/movimientos-pdf")
def descargar_pdf_movimientos(
    desde: date = Query(..., description="Fecha inicial (inclusive)"),
    hasta: date = Query(..., description="Fecha final (inclusive)"),
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Response:
    """PDF con todos los movimientos de caja del consorcio en el rango dado,
    agrupados por caja y con totales."""
    if desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`desde` no puede ser posterior a `hasta`.",
        )
    cajas = list(db.scalars(
        select(Caja).where(Caja.consorcio_id == cid).order_by(Caja.id)
    ).all())
    movs = list(db.scalars(
        select(MovimientoCaja).where(
            MovimientoCaja.consorcio_id == cid,
            MovimientoCaja.fecha >= desde,
            MovimientoCaja.fecha <= hasta,
        )
    ).all())
    config = db.get(Consorcio, cid)
    pdf = generar_pdf_movimientos_caja(movs, cajas, desde, hasta, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="movimientos-{desde}-a-{hasta}.pdf"',
        },
    )
