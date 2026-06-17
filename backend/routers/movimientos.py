"""Endpoints de cuenta corriente y notas (crédito/débito)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..cuenta_corriente import calcular_estado_cuenta
from ..database import get_db
from ..models import Departamento, MovimientoCuenta, Rol
from ..schemas import EstadoCuentaOut, MovimientoCuentaOut, NotaCrear

router = APIRouter(tags=["Movimientos"])


def _cuenta(
    db: Session,
    departamento_id: int,
    desde: date | None,
    hasta: date | None,
) -> EstadoCuentaOut:
    estado = calcular_estado_cuenta(db, departamento_id)

    stmt = (
        select(MovimientoCuenta)
        .where(MovimientoCuenta.departamento_id == departamento_id)
        .order_by(MovimientoCuenta.fecha.desc(), MovimientoCuenta.id.desc())
    )
    if desde is not None:
        stmt = stmt.where(MovimientoCuenta.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(MovimientoCuenta.fecha <= hasta)

    movs = list(db.scalars(stmt).all())
    return EstadoCuentaOut(
        departamento_id=departamento_id,
        saldo_total=estado.saldo_total,
        movimientos=[MovimientoCuentaOut.model_validate(m) for m in movs],
    )


@router.get(
    "/movimientos/mi-cuenta",
    response_model=EstadoCuentaOut,
    status_code=status.HTTP_200_OK,
    summary="Cuenta corriente del departamento autenticado",
)
def mi_cuenta(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> EstadoCuentaOut:
    return _cuenta(db, user.departamento_id, desde, hasta)


@router.get(
    "/departamentos/{departamento_id}/cuenta",
    response_model=EstadoCuentaOut,
    status_code=status.HTTP_200_OK,
    summary="Cuenta corriente de un departamento (admin)",
)
def cuenta_departamento(
    departamento_id: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EstadoCuentaOut:
    if db.get(Departamento, departamento_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )
    return _cuenta(db, departamento_id, desde, hasta)


@router.post(
    "/movimientos/nota",
    response_model=MovimientoCuentaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nota de crédito o débito (admin)",
)
def crear_nota(
    payload: NotaCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> MovimientoCuenta:
    if db.get(Departamento, payload.departamento_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )

    mov = MovimientoCuenta(
        departamento_id=payload.departamento_id,
        fecha=payload.fecha or date.today(),
        tipo=payload.tipo,
        descripcion=payload.descripcion,
        monto=payload.monto,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov
