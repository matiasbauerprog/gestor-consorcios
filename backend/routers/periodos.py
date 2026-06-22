import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..cierre import calcular_preview_cierre
from ..database import get_db
from ..models import (
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    PeriodoCerrado,
    Rol,
    TipoMovimiento,
)
from ..schemas import (
    CerrarPeriodoIn,
    EstadoCierreOut,
    ExpensaACrearOut,
    InteresACrearOut,
    LineaDetalleExpensaOut,
    PeriodoCerradoOut,
    PreviewCierreOut,
    ValidacionOut,
)

router = APIRouter(prefix="/periodos", tags=["Periodos"])

_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _preview_to_out(preview) -> PreviewCierreOut:
    return PreviewCierreOut(
        periodo=preview.periodo,
        cerrado=preview.cerrado,
        fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
        fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
        validaciones=[ValidacionOut(**v.__dict__) for v in preview.validaciones],
        puede_cerrar=preview.puede_cerrar,
        expensas=[
            ExpensaACrearOut(
                departamento_id=e.departamento_id,
                saldo_anterior=e.saldo_anterior,
                monto_primer_vencimiento=e.monto_primer_vencimiento,
                monto_segundo_vencimiento=e.monto_segundo_vencimiento,
                detalle=[
                    LineaDetalleExpensaOut(
                        rubro=d.rubro,
                        clase_prorrateo_id=d.clase_prorrateo_id,
                        departamento_origen_id=d.departamento_origen_id,
                        concepto=d.concepto,
                        monto=d.monto,
                    )
                    for d in e.detalle
                ],
            )
            for e in preview.expensas
        ],
        intereses=[InteresACrearOut(**i.__dict__) for i in preview.intereses],
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
    )


@router.get("", response_model=list[PeriodoCerradoOut], status_code=200)
def listar_periodos(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[PeriodoCerrado]:
    return list(db.scalars(
        select(PeriodoCerrado).order_by(PeriodoCerrado.fecha_cierre.desc())
    ).all())


@router.get("/{periodo}/estado", response_model=EstadoCierreOut, status_code=200)
def estado_periodo(
    periodo: str,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EstadoCierreOut:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido. Use formato YYYY-MM.")
    preview = calcular_preview_cierre(db, periodo)
    return EstadoCierreOut(
        periodo=preview.periodo,
        cerrado=preview.cerrado,
        validaciones=[ValidacionOut(**v.__dict__) for v in preview.validaciones],
        puede_cerrar=preview.puede_cerrar,
    )


@router.get("/{periodo}/preview", response_model=PreviewCierreOut, status_code=200)
def preview_periodo(
    periodo: str,
    fecha_1: date | None = Query(default=None),
    fecha_2: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> PreviewCierreOut:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido.")
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(409, f"El período {periodo} ya fue cerrado.")
    preview = calcular_preview_cierre(db, periodo, fecha_1, fecha_2)
    return _preview_to_out(preview)


@router.post("/{periodo}/cerrar", response_model=PeriodoCerradoOut, status_code=201)
def cerrar_periodo(
    periodo: str,
    payload: CerrarPeriodoIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> PeriodoCerrado:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido.")
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(409, f"El período {periodo} ya fue cerrado.")

    preview = calcular_preview_cierre(
        db, periodo,
        payload.fecha_primer_vencimiento,
        payload.fecha_segundo_vencimiento,
    )
    if not preview.puede_cerrar:
        raise HTTPException(409, "Hay validaciones bloqueantes pendientes para cerrar el período.")

    hoy = date.today()

    for it in preview.intereses:
        db.add(MovimientoCuenta(
            departamento_id=it.departamento_id,
            fecha=hoy,
            tipo=TipoMovimiento.interes_punitorio,
            descripcion=it.descripcion,
            monto=it.monto,
        ))
    db.flush()

    for exp in preview.expensas:
        e = Expensa(
            departamento_id=exp.departamento_id,
            periodo=periodo,
            monto_primer_vencimiento=exp.monto_primer_vencimiento,
            fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
            monto_segundo_vencimiento=exp.monto_segundo_vencimiento,
            fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
            saldo_anterior=exp.saldo_anterior,
        )
        db.add(e); db.flush()
        for d in exp.detalle:
            db.add(ExpensaDetalle(
                expensa_id=e.id,
                rubro=d.rubro,
                clase_prorrateo_id=d.clase_prorrateo_id,
                departamento_origen_id=d.departamento_origen_id,
                concepto=d.concepto,
                monto=d.monto,
            ))
        db.add(MovimientoCuenta(
            departamento_id=exp.departamento_id,
            fecha=hoy,
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {periodo}",
            monto=exp.monto_primer_vencimiento,
            expensa_id=e.id,
        ))

    cerrado = PeriodoCerrado(
        periodo=periodo,
        cerrado_por_usuario_id=user.id,
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
        cantidad_expensas=len(preview.expensas),
    )
    db.add(cerrado)
    db.commit()
    db.refresh(cerrado)
    return cerrado
