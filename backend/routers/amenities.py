from datetime import date, datetime, time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import (
    Amenity,
    Departamento,
    EstadoReserva,
    MovimientoCuenta,
    Reserva,
    Rol,
    TipoMovimiento,
)
from ..modulos import require_modulo
from ..notificaciones import emitir
from ..notificaciones.catalogo import RESERVA_CONFIRMADA, RESERVA_NUEVA_DE_DEPTO
from ..tenant import get_consorcio_activo
from ..schemas import (
    AmenityActualizar,
    AmenityCrear,
    AmenityOut,
    BloqueHorarioOut,
    DisponibilidadOut,
    ReservaCrear,
    ReservaOut,
)

router = APIRouter(
    prefix="/amenities",
    tags=["Amenities"],
    dependencies=[Depends(require_modulo("espacios_comunes"))],
)


@router.get(
    "",
    response_model=list[AmenityOut],
    status_code=status.HTTP_200_OK,
    summary="Listar amenities",
)
def listar_amenities(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[Amenity]:
    stmt = select(Amenity).where(Amenity.consorcio_id == cid).order_by(Amenity.nombre.asc())
    # incluir_inactivos solo aplica para admin; para depto/representante se ignora silenciosamente.
    if not (incluir_inactivos and user.rol == Rol.administracion):
        stmt = stmt.where(Amenity.activo == True)  # noqa: E712
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=AmenityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un amenity (espacio común)",
)
def crear_amenity(
    payload: AmenityCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Amenity:
    duplicado = db.scalar(
        select(Amenity.id).where(
            Amenity.consorcio_id == cid,
            Amenity.nombre == payload.nombre,
        )
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un amenity con ese nombre.",
        )

    # model_dump(exclude={"nombre"}) porque nombre ya se valida arriba (chequeo
    # de duplicado) y se pasa aparte; el resto de los campos opcionales
    # (precio_reserva, duracion_maxima_horas, etc.) antes se perdían acá: el
    # constructor solo copiaba nombre/descripcion y el resto quedaba en None
    # sin importar lo que mandara el cliente — sin que ningún 400/409 lo
    # delatara, porque el schema los valida bien.
    amenity = Amenity(
        consorcio_id=cid,
        nombre=payload.nombre,
        **payload.model_dump(exclude={"nombre"}),
    )
    db.add(amenity)
    db.commit()
    db.refresh(amenity)
    return amenity


@router.patch(
    "/{amenity_id}",
    response_model=AmenityOut,
    status_code=status.HTTP_200_OK,
    summary="Editar un amenity",
)
def actualizar_amenity(
    amenity_id: int,
    payload: AmenityActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Amenity:
    amenity = db.get(Amenity, amenity_id)
    if amenity is None or amenity.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El amenity solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)

    if "nombre" in cambios and cambios["nombre"] != amenity.nombre:
        en_uso = db.scalar(
            select(Amenity.id).where(
                Amenity.consorcio_id == cid,
                Amenity.nombre == cambios["nombre"],
                Amenity.id != amenity.id,
            )
        )
        if en_uso is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un amenity con ese nombre.",
            )

    for campo, valor in cambios.items():
        setattr(amenity, campo, valor)

    db.commit()
    db.refresh(amenity)
    return amenity


@router.get(
    "/{amenity_id}/disponibilidad",
    response_model=DisponibilidadOut,
    status_code=status.HTTP_200_OK,
    summary="Consultar disponibilidad de un amenity",
)
def consultar_disponibilidad(
    amenity_id: int,
    desde: date = Query(..., description="Fecha inicial del rango (ISO 8601)."),
    hasta: date = Query(..., description="Fecha final del rango (ISO 8601)."),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> DisponibilidadOut:
    if desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro `desde` no puede ser posterior a `hasta`.",
        )

    amenity = db.get(Amenity, amenity_id)
    if amenity is None or amenity.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El amenity solicitado no existe.",
        )

    desde_dt = datetime.combine(desde, time.min)
    hasta_dt = datetime.combine(hasta, time.max)

    stmt = (
        select(Reserva)
        .where(
            Reserva.amenity_id == amenity_id,
            Reserva.estado == EstadoReserva.confirmada,
            Reserva.inicio < hasta_dt,
            Reserva.fin > desde_dt,
        )
        .order_by(Reserva.inicio.asc())
    )
    reservas = db.scalars(stmt).all()

    bloques = [
        BloqueHorarioOut(inicio=r.inicio, fin=r.fin, disponible=False)
        for r in reservas
    ]
    return DisponibilidadOut(amenity_id=amenity_id, bloques=bloques)


@router.post(
    "/{amenity_id}/reservas",
    response_model=ReservaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar un amenity",
)
def crear_reserva(
    amenity_id: int,
    payload: ReservaCrear,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> Reserva:
    amenity = db.get(Amenity, amenity_id)
    if amenity is None or amenity.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El amenity solicitado no existe.",
        )

    if not amenity.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El amenity está inactivo.",
        )

    # Normalización: payload puede venir con tz o naive. Comparamos en naive
    # contra datetime.now() para evitar mezclar offsets — el front manda naive.
    inicio_naive = payload.inicio.replace(tzinfo=None) if payload.inicio.tzinfo else payload.inicio
    fin_naive = payload.fin.replace(tzinfo=None) if payload.fin.tzinfo else payload.fin
    ahora = datetime.now().replace(microsecond=0)

    if inicio_naive <= ahora:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede reservar para el pasado.",
        )

    duracion_horas = (fin_naive - inicio_naive).total_seconds() / 3600
    if amenity.duracion_maxima_horas is not None and duracion_horas > amenity.duracion_maxima_horas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La duración supera el máximo permitido ({amenity.duracion_maxima_horas}h).",
        )

    if amenity.anticipacion_maxima_dias is not None:
        dias_anticipacion = (inicio_naive.date() - ahora.date()).days
        if dias_anticipacion > amenity.anticipacion_maxima_dias:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No se puede reservar con más de {amenity.anticipacion_maxima_dias} "
                    f"días de anticipación."
                ),
            )

    # Límite de reservas activas por depto: solo para rol departamento.
    if user.rol == Rol.departamento and amenity.max_reservas_activas_por_depto is not None:
        activas = db.scalar(
            select(func.count(Reserva.id)).where(
                Reserva.amenity_id == amenity_id,
                Reserva.usuario_id == user.id,
                Reserva.estado == EstadoReserva.confirmada,
                Reserva.inicio > ahora,
            )
        ) or 0
        if activas >= amenity.max_reservas_activas_por_depto:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya alcanzaste el máximo de reservas activas para este amenity "
                    f"({amenity.max_reservas_activas_por_depto})."
                ),
            )

    # Anti-solapamiento: dos intervalos [a, b) y [c, d) se superponen
    # iff a < d AND c < b. Se ignoran reservas canceladas.
    solape_id = db.scalar(
        select(Reserva.id).where(
            Reserva.amenity_id == amenity_id,
            Reserva.estado == EstadoReserva.confirmada,
            Reserva.inicio < fin_naive,
            Reserva.fin > inicio_naive,
        )
    )
    if solape_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El horario solicitado se superpone con una reserva existente.",
        )

    # usuario_id NUNCA del body: siempre del token.
    reserva = Reserva(
        consorcio_id=cid,
        amenity_id=amenity_id,
        usuario_id=user.id,
        inicio=inicio_naive,
        fin=fin_naive,
        estado=EstadoReserva.confirmada,
    )
    db.add(reserva)
    db.flush()  # asignar id antes de FK del movimiento

    # Cobro: solo si reservante es depto y el amenity tiene precio.
    if user.rol == Rol.departamento and amenity.precio_reserva is not None:
        movimiento = MovimientoCuenta(
            consorcio_id=cid,
            departamento_id=user.departamento_id,
            fecha=date.today(),
            tipo=TipoMovimiento.nota_debito,
            monto=amenity.precio_reserva,
            descripcion=f"Reserva {amenity.nombre} {inicio_naive.date().isoformat()}",
        )
        db.add(movimiento)
        db.flush()
        reserva.movimiento_cuenta_id = movimiento.id

    monto = (
        amenity.precio_reserva
        if (user.rol == Rol.departamento and amenity.precio_reserva is not None)
        else None
    )
    ctx_reserva = {
        "amenity": amenity.nombre,
        "fecha": inicio_naive.strftime("%Y-%m-%d %H:%M"),
        "monto": monto,
    }
    if user.rol == Rol.departamento:
        # `actor_usuario_id=None` a propósito: es la confirmación al propio
        # reservante, el único caso donde el actor sí debe recibir el aviso
        # porque el mail es el comprobante de su propia acción. Y va acotado a
        # él solo: el texto le habla de "tu reserva" y "tu cuenta corriente",
        # así que al otro habitante de la unidad no le corresponde.
        emitir(
            db, RESERVA_CONFIRMADA,
            consorcio_id=cid, contexto=ctx_reserva,
            actor_usuario_id=None,
            departamento_id=user.departamento_id,
            tareas=tareas,
            restringir_a_usuario_id=user.id,
        )

        # A la administración también le interesa: un depto acaba de tomar un
        # turno de un espacio común, no es sólo un aviso para quien reservó.
        depto = db.get(Departamento, user.departamento_id)
        emitir(
            db, RESERVA_NUEVA_DE_DEPTO,
            consorcio_id=cid,
            contexto={
                "codigo_depto": depto.codigo if depto else "Un departamento",
                "amenity": amenity.nombre,
                "fecha": inicio_naive.strftime("%Y-%m-%d %H:%M"),
            },
            actor_usuario_id=user.id,
            tareas=tareas,
        )

    db.commit()
    db.refresh(reserva)
    return reserva


@router.delete(
    "/{amenity_id}",
    response_model=AmenityOut,
    status_code=status.HTTP_200_OK,
    summary="Dar de baja un amenity (soft-delete)",
)
def dar_de_baja_amenity(
    amenity_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Amenity:
    amenity = db.get(Amenity, amenity_id)
    if amenity is None or amenity.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El amenity solicitado no existe.",
        )
    if not amenity.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El amenity ya está inactivo.",
        )
    amenity.activo = False
    db.commit()
    db.refresh(amenity)
    return amenity
