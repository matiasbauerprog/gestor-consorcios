from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import EstadoReserva, Reserva, Rol
from ..schemas import ReservaOut

router = APIRouter(prefix="/reservas", tags=["Amenities"])


@router.get(
    "",
    response_model=list[ReservaOut],
    status_code=status.HTTP_200_OK,
    summary="Listar mis reservas",
)
def listar_reservas(
    estado: EstadoReserva | None = Query(
        default=None,
        description="Filtrar por estado de la reserva.",
    ),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Reserva]:
    stmt = select(Reserva).order_by(Reserva.inicio.desc(), Reserva.id.desc())

    # Aislamiento por usuario para Departamentos; Admin/Representante ven todo.
    # Identidad siempre del token, nunca del query.
    if user.rol == Rol.departamento:
        stmt = stmt.where(Reserva.usuario_id == user.id)

    if estado is not None:
        stmt = stmt.where(Reserva.estado == estado)

    return list(db.scalars(stmt).all())


@router.delete(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva",
)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Reserva:
    reserva = db.get(Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva solicitada no existe.",
        )

    # Solo el dueño o Administración pueden cancelar. Representante no.
    es_dueno = reserva.usuario_id == user.id
    es_admin = user.rol == Rol.administracion
    if not (es_dueno or es_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    if reserva.estado == EstadoReserva.cancelada:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La reserva ya está cancelada.",
        )

    reserva.estado = EstadoReserva.cancelada
    db.commit()
    db.refresh(reserva)
    return reserva
