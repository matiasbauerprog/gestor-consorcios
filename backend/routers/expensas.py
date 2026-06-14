from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import (
    Comprobante,
    Departamento,
    EstadoComprobante,
    EstadoExpensa,
    Expensa,
    Rol,
)
from ..schemas import ComprobanteCrear, ComprobanteOut, ExpensaCrear, ExpensaOut


def _expensa_to_out(expensa) -> ExpensaOut:
    """Serialize an Expensa ORM object to ExpensaOut, populating ultimo_comprobante."""
    data = ExpensaOut.model_validate(expensa)
    data.ultimo_comprobante = (
        ComprobanteOut.model_validate(expensa.comprobantes[0])
        if expensa.comprobantes
        else None
    )
    return data

router = APIRouter(prefix="/expensas", tags=["Expensas"])

_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


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
    estado: EstadoExpensa | None = Query(
        default=None,
        description="Filtrar por estado de la expensa.",
    ),
    departamento_id: int | None = Query(default=None, gt=0, description="Filtrar por depto (Admin)."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
) -> list[Expensa]:
    stmt = select(Expensa).order_by(Expensa.fecha_vencimiento.desc(), Expensa.id.desc())

    # Aislamiento por unidad: el Departamento solo ve sus propias expensas.
    # El departamento_id se toma del token, nunca del body/query.
    if user.rol == Rol.departamento:
        stmt = stmt.where(Expensa.departamento_id == user.departamento_id)

    if periodo is not None:
        stmt = stmt.where(Expensa.periodo == periodo)
    if estado is not None:
        stmt = stmt.where(Expensa.estado == estado)

    # El query departamento_id solo aplica para Admin. Para Depto, su token define qué ve;
    # cualquier valor en el query se ignora (server-side hardening).
    if user.rol != Rol.departamento and departamento_id is not None:
        stmt = stmt.where(Expensa.departamento_id == departamento_id)

    stmt = stmt.offset(offset).limit(limit)
    expensas = list(db.scalars(stmt).all())
    return [_expensa_to_out(e) for e in expensas]


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
) -> Expensa:
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
        estado=EstadoExpensa.pendiente,
    )
    db.add(expensa)
    db.commit()
    db.refresh(expensa)
    return expensa


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
) -> Expensa:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
        )

    # Aislamiento por unidad para Departamentos; Admin/Representante ven todo.
    if user.rol == Rol.departamento and expensa.departamento_id != user.departamento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    return _expensa_to_out(expensa)


@router.post(
    "/{expensa_id}/comprobantes",
    response_model=ComprobanteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Presentar comprobante de pago de una expensa",
)
def presentar_comprobante(
    expensa_id: int,
    payload: ComprobanteCrear,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> Comprobante:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La expensa solicitada no existe.",
        )

    # Aislamiento por unidad: el departamento solo puede presentar comprobantes
    # sobre expensas asociadas a su propia unidad.
    if expensa.departamento_id != user.departamento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    comprobante = Comprobante(
        expensa_id=expensa.id,
        fecha_pago=payload.fecha_pago,
        monto=payload.monto,
        archivo_url=payload.archivo_url,
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db.add(comprobante)
    db.commit()
    db.refresh(comprobante)
    return comprobante
