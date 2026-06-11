from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Comprobante, EstadoComprobante, EstadoExpensa, Rol
from ..schemas import ComprobanteActualizar, ComprobanteOut

router = APIRouter(prefix="/comprobantes", tags=["Expensas"])


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
