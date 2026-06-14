from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Comprobante, EstadoComprobante, EstadoExpensa, Expensa, Rol
from ..schemas import ComprobanteActualizar, ComprobanteOut

router = APIRouter(prefix="/comprobantes", tags=["Expensas"])


@router.get(
    "",
    response_model=list[ComprobanteOut],
    status_code=status.HTTP_200_OK,
    summary="Listar comprobantes",
)
def listar_comprobantes(
    estado: EstadoComprobante | None = Query(default=None),
    departamento_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
) -> list[Comprobante]:
    stmt = (
        select(Comprobante)
        .join(Expensa, Comprobante.expensa_id == Expensa.id)
        .order_by(Comprobante.fecha_creacion.desc(), Comprobante.id.desc())
    )

    # Aislamiento por unidad para Departamentos. Su token define qué pueden ver;
    # el query departamento_id es ignorado.
    if user.rol == Rol.departamento:
        stmt = stmt.where(Expensa.departamento_id == user.departamento_id)
    elif departamento_id is not None:
        stmt = stmt.where(Expensa.departamento_id == departamento_id)

    if estado is not None:
        stmt = stmt.where(Comprobante.estado == estado)

    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.patch(
    "/{comprobante_id}",
    response_model=ComprobanteOut,
    status_code=status.HTTP_200_OK,
    summary="Aprobar o rechazar un comprobante",
)
def actualizar_comprobante(
    comprobante_id: int,
    payload: ComprobanteActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Comprobante:
    comprobante = db.get(Comprobante, comprobante_id)
    if comprobante is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comprobante solicitado no existe.",
        )

    # Solo se puede decidir sobre comprobantes pendientes. Estados terminales
    # son inmutables — evita que se "des-apruebe" un pago ya conciliado.
    if comprobante.estado != EstadoComprobante.pendiente_verificacion:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El comprobante ya fue verificado y no puede modificarse.",
        )

    comprobante.estado = payload.estado

    # Aprobar el comprobante cierra el ciclo contable: la expensa queda pagada.
    if payload.estado == EstadoComprobante.aprobado:
        comprobante.expensa.estado = EstadoExpensa.pagada

    db.commit()
    db.refresh(comprobante)
    return comprobante
