from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import (
    Amenity, EstadoReserva, MovimientoCuenta, Reserva, Rol, TipoMovimiento, Usuario,
)
from ..modulos import require_modulo
from ..notificaciones import emitir
from ..notificaciones.catalogo import RESERVA_CANCELADA_POR_ADMIN
from ..schemas import ReservaOut
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/reservas",
    tags=["Amenities"],
    dependencies=[Depends(require_modulo("espacios_comunes"))],
)


@router.get(
    "",
    response_model=list[ReservaOut],
    status_code=status.HTTP_200_OK,
    summary="Listar reservas",
)
def listar_reservas(
    estado: EstadoReserva | None = Query(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[Reserva]:
    stmt = select(Reserva).where(Reserva.consorcio_id == cid).order_by(Reserva.inicio.desc(), Reserva.id.desc())
    if user.rol == Rol.departamento:
        stmt = stmt.where(Reserva.usuario_id == user.id)
    if estado is not None:
        stmt = stmt.where(Reserva.estado == estado)
    return list(db.scalars(stmt).all())


@router.get(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de una reserva",
)
def obtener_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> Reserva:
    reserva = db.get(Reserva, reserva_id)
    if reserva is None or reserva.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva solicitada no existe.",
        )
    es_dueno = reserva.usuario_id == user.id
    es_admin = user.rol == Rol.administracion
    if not (es_dueno or es_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )
    return reserva


@router.delete(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva",
)
def cancelar_reserva(
    reserva_id: int,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> Reserva:
    reserva = db.get(Reserva, reserva_id)
    if reserva is None or reserva.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva solicitada no existe.",
        )

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

    # Reversa del cargo, si tenía MovimientoCuenta asociado.
    monto_reversado = None
    if reserva.movimiento_cuenta_id is not None:
        amenity = db.get(Amenity, reserva.amenity_id)
        mov_original = db.get(MovimientoCuenta, reserva.movimiento_cuenta_id)
        reversar = False

        # Caso A: admin cancela reserva ajena → siempre reversa
        if es_admin and not es_dueno:
            reversar = True
        else:
            # Caso B: dueño cancela su propia
            if amenity.horas_minimas_cancelacion is None:
                reversar = True
            else:
                horas_hasta_inicio = (reserva.inicio - datetime.now()).total_seconds() / 3600
                if horas_hasta_inicio >= amenity.horas_minimas_cancelacion:
                    reversar = True

        if reversar and mov_original is not None:
            nota_credito = MovimientoCuenta(
                consorcio_id=cid,
                departamento_id=mov_original.departamento_id,
                fecha=date.today(),
                tipo=TipoMovimiento.nota_credito,
                monto=mov_original.monto,
                descripcion=f"Reversa de reserva cancelada {reserva.inicio.date().isoformat()}",
            )
            db.add(nota_credito)
            monto_reversado = mov_original.monto

    if es_admin and not es_dueno:
        amenity_n = db.get(Amenity, reserva.amenity_id)
        dueno = db.get(Usuario, reserva.usuario_id)
        # Un admin puede cancelar la reserva de otro admin: ahí no hay depto a
        # quien avisarle, y sin departamento_id el emisor no sabría a quién
        # buscar. Se sigue de largo, como hacía el helper viejo.
        if dueno is not None and dueno.departamento_id is not None:
            emitir(
                db, RESERVA_CANCELADA_POR_ADMIN,
                consorcio_id=cid,
                contexto={
                    "amenity": amenity_n.nombre,
                    "fecha": reserva.inicio.strftime("%Y-%m-%d %H:%M"),
                    "monto_reversado": monto_reversado,
                },
                actor_usuario_id=user.id,
                departamento_id=dueno.departamento_id,
                tareas=tareas,
                # "Canceló TU reserva... se reversó TU cargo": segunda persona
                # hacia quien reservó. Al conviviente le hablaría de algo ajeno.
                restringir_a_usuario_id=reserva.usuario_id,
            )

    db.commit()
    db.refresh(reserva)
    return reserva
