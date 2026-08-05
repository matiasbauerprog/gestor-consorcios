from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..cuenta_corriente import calcular_estado_cuenta
from ..database import get_db
from ..models import (
    Departamento,
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    PeriodoCerrado,
    Rol,
    TipoMovimiento,
)
from ..pdf import generar_pdf_boleta
from ..recargos import devengar_recargos_y_marcar
from ..schemas import ExpensaCrear, ExpensaOut, LineaDetalleExpensaOut
from ..modulos import require_modulo
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/expensas",
    tags=["Expensas"],
    dependencies=[Depends(require_modulo("cobranzas"))],
)

_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _expensa_to_out(expensa: Expensa, calc) -> ExpensaOut:
    return ExpensaOut(
        id=expensa.id,
        departamento_id=expensa.departamento_id,
        periodo=expensa.periodo,
        monto_primer_vencimiento=expensa.monto_primer_vencimiento,
        fecha_primer_vencimiento=expensa.fecha_primer_vencimiento,
        monto_segundo_vencimiento=expensa.monto_segundo_vencimiento,
        fecha_segundo_vencimiento=expensa.fecha_segundo_vencimiento,
        saldo_anterior=expensa.saldo_anterior,
        estado_calculado=calc.estado,
        monto_pendiente=calc.monto_pendiente,
        monto_exigible=calc.monto_exigible,
        interes_acumulado=calc.interes_acumulado,
        detalle=[LineaDetalleExpensaOut.model_validate(d) for d in expensa.detalle],
    )


@router.get(
    "",
    response_model=list[ExpensaOut],
    status_code=status.HTTP_200_OK,
    summary="Listar expensas",
)
def listar_expensas(
    periodo: str | None = Query(
        default=None,
        pattern=_PERIODO_PATTERN,
        description="Filtrar por período en formato YYYY-MM.",
    ),
    departamento_id: int | None = Query(
        default=None, gt=0, description="Filtrar por depto (Admin)."
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> list[ExpensaOut]:
    stmt = select(Expensa).where(Expensa.consorcio_id == cid).order_by(Expensa.fecha_primer_vencimiento.desc(), Expensa.id.desc())

    # Aislamiento por unidad: el Departamento solo ve sus propias expensas.
    # El departamento_id se toma del token, nunca del query param.
    if user.rol == Rol.departamento:
        stmt = stmt.where(Expensa.departamento_id == user.departamento_id)
    elif departamento_id is not None:
        stmt = stmt.where(Expensa.departamento_id == departamento_id)

    if periodo is not None:
        stmt = stmt.where(Expensa.periodo == periodo)

    stmt = stmt.offset(offset).limit(limit)
    expensas = list(db.scalars(stmt).all())

    # Devengamiento perezoso antes de leer: el exigible sale del recargo ya
    # asentado, así que sin devengar primero esta pantalla mostraría de menos.
    # Un solo commit para todos los deptos listados, no uno por departamento.
    hubo_recargos = False
    for depto_id in {e.departamento_id for e in expensas}:
        if devengar_recargos_y_marcar(db, depto_id):
            hubo_recargos = True
    if hubo_recargos:
        db.commit()

    # FIFO se calcula una vez por depto y se reutiliza para todas sus expensas.
    estados_por_depto: dict[int, dict[int, "object"]] = {}
    out: list[ExpensaOut] = []
    for e in expensas:
        if e.departamento_id not in estados_por_depto:
            estados_por_depto[e.departamento_id] = (
                calcular_estado_cuenta(db, e.departamento_id).por_expensa
            )
        calc = estados_por_depto[e.departamento_id].get(e.id)
        if calc is None:
            # No debería pasar: toda Expensa tiene su movimiento expensa_emitida.
            # Salvaguarda defensiva: omitir si la cuenta no tiene la expensa indexada.
            continue
        out.append(_expensa_to_out(e, calc))
    return out


@router.post(
    "",
    response_model=ExpensaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva expensa",
)
def crear_expensa(
    payload: ExpensaCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ExpensaOut:
    depto = db.get(Departamento, payload.departamento_id)
    if depto is None or depto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )

    pc = db.get(PeriodoCerrado, (payload.periodo, cid))
    if pc is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {payload.periodo} está cerrado y no admite cambios.",
        )

    duplicado = db.scalar(
        select(Expensa.id).where(
            Expensa.consorcio_id == cid,
            Expensa.departamento_id == payload.departamento_id,
            Expensa.periodo == payload.periodo,
        )
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una expensa para ese departamento en ese período.",
        )

    expensa = Expensa(
        consorcio_id=cid,
        departamento_id=payload.departamento_id,
        periodo=payload.periodo,
        monto_primer_vencimiento=payload.monto_primer_vencimiento,
        fecha_primer_vencimiento=payload.fecha_primer_vencimiento,
        monto_segundo_vencimiento=payload.monto_segundo_vencimiento,
        fecha_segundo_vencimiento=payload.fecha_segundo_vencimiento,
        saldo_anterior=0.0,
    )
    db.add(expensa)
    db.flush()

    db.add(
        MovimientoCuenta(
            consorcio_id=cid,
            departamento_id=expensa.departamento_id,
            fecha=date.today(),
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {expensa.periodo}",
            monto=expensa.monto_primer_vencimiento,
            expensa_id=expensa.id,
        )
    )
    db.commit()
    db.refresh(expensa)

    # La respuesta informa pendiente y exigible, así que también devenga: el
    # FIFO reparte el crédito desde la expensa más vieja y un recargo sin
    # asentar de una anterior le dejaría de más a ésta.
    if devengar_recargos_y_marcar(db, expensa.departamento_id):
        db.commit()

    calc = calcular_estado_cuenta(db, expensa.departamento_id).por_expensa[expensa.id]
    return _expensa_to_out(expensa, calc)


@router.get(
    "/{expensa_id}",
    response_model=ExpensaOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de una expensa",
)
def obtener_expensa(
    expensa_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> ExpensaOut:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None or expensa.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
        )

    if user.rol == Rol.departamento and expensa.departamento_id != user.departamento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    # Mismo devengamiento perezoso que en el listado: el exigible se lee del
    # recargo asentado, así que hay que emitirlo antes de calcular.
    if devengar_recargos_y_marcar(db, expensa.departamento_id):
        db.commit()

    calc = calcular_estado_cuenta(db, expensa.departamento_id).por_expensa.get(expensa.id)
    if calc is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Estado de la expensa no calculable.",
        )
    return _expensa_to_out(expensa, calc)


@router.delete(
    "/{expensa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una expensa (solo admin, sin pagos aplicados)",
)
def eliminar_expensa(
    expensa_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> None:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None or expensa.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
        )

    if db.get(PeriodoCerrado, (expensa.periodo, cid)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {expensa.periodo} está cerrado y no admite cambios.",
        )

    calc = calcular_estado_cuenta(db, expensa.departamento_id).por_expensa.get(expensa.id)
    if calc is not None and calc.monto_pagado > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: la expensa tiene pago aplicado (FIFO).",
        )

    db.execute(
        MovimientoCuenta.__table__.delete().where(
            MovimientoCuenta.expensa_id == expensa.id
        )
    )
    db.delete(expensa)
    db.commit()


@router.get(
    "/{expensa_id}/pdf",
    summary="Generar PDF de la boleta de expensa",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF de la boleta"},
        403: {"description": "Depto no autorizado a ver expensa ajena"},
        404: {"description": "Expensa no encontrada"},
    },
)
def descargar_pdf_expensa(
    expensa_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> Response:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None or expensa.consorcio_id != cid:
        raise HTTPException(404, "Expensa no encontrada.")

    # Autorización: depto solo ve las propias; admin/representante cualquiera
    if user.rol == Rol.departamento:
        if user.departamento_id != expensa.departamento_id:
            raise HTTPException(403, "No autorizado para ver esta expensa.")

    pdf_bytes = generar_pdf_boleta(expensa, db)
    filename = f"expensa-{expensa.periodo}-depto-{expensa.departamento_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
