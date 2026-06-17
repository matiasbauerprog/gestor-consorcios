from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..cuenta_corriente import calcular_estado_cuenta
from ..database import get_db
from ..models import (
    Departamento,
    Expensa,
    MovimientoCuenta,
    Rol,
    TipoMovimiento,
)
from ..schemas import ExpensaCrear, ExpensaOut

router = APIRouter(prefix="/expensas", tags=["Expensas"])

_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _expensa_to_out(expensa: Expensa, calc) -> ExpensaOut:
    return ExpensaOut(
        id=expensa.id,
        departamento_id=expensa.departamento_id,
        periodo=expensa.periodo,
        monto=expensa.monto,
        fecha_vencimiento=expensa.fecha_vencimiento,
        estado_calculado=calc.estado,
        monto_pendiente=calc.monto_pendiente,
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
) -> list[ExpensaOut]:
    stmt = select(Expensa).order_by(Expensa.fecha_vencimiento.desc(), Expensa.id.desc())

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
) -> ExpensaOut:
    if db.get(Departamento, payload.departamento_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )

    duplicado = db.scalar(
        select(Expensa.id).where(
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
        departamento_id=payload.departamento_id,
        periodo=payload.periodo,
        monto=payload.monto,
        fecha_vencimiento=payload.fecha_vencimiento,
    )
    db.add(expensa)
    db.flush()

    db.add(
        MovimientoCuenta(
            departamento_id=expensa.departamento_id,
            fecha=date.today(),
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {expensa.periodo}",
            monto=expensa.monto,
            expensa_id=expensa.id,
        )
    )
    db.commit()
    db.refresh(expensa)

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
) -> ExpensaOut:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
        )

    if user.rol == Rol.departamento and expensa.departamento_id != user.departamento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

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
) -> None:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
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
