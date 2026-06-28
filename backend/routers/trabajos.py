from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoTrabajo,
    Peticion,
    Presupuesto,
    Proveedor,
    Rol,
    Trabajo,
)
from ..notificaciones import notificar_cambio_estado_peticion
from ..schemas import (
    CompletarTrabajoOut,
    PresupuestoCrear,
    PresupuestoOut,
    TrabajoActualizar,
    TrabajoCrear,
    TrabajoOut,
)

router = APIRouter(prefix="/trabajos", tags=["Tareas"])

_ADMIN_O_REPRESENTANTE = (Rol.administracion, Rol.representante)


@router.post(
    "",
    response_model=TrabajoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Convertir una petición en trabajo a realizar",
)
def crear_trabajo(
    payload: TrabajoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> Trabajo:
    peticion_id: int | None = None
    peticion_a_notificar: Peticion | None = None
    estado_anterior: EstadoPeticion | None = None

    # Si el trabajo viene de una petición existente, validamos y la marcamos
    # como convertida. Si no, queda como trabajo "desde cero" (peticion_id null).
    if payload.peticion_id is not None:
        peticion = db.get(Peticion, payload.peticion_id)
        if peticion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La petición indicada no existe.",
            )
        estado_anterior = peticion.estado
        peticion.estado = EstadoPeticion.convertida_en_trabajo
        peticion_id = peticion.id
        peticion_a_notificar = peticion

    trabajo = Trabajo(
        peticion_id=peticion_id,
        descripcion=payload.descripcion,
        estado=EstadoTrabajo.en_curso,
    )
    db.add(trabajo)
    db.flush()

    # Notificar al depto que su petición pasó a convertida_en_trabajo.
    if peticion_a_notificar is not None:
        notificar_cambio_estado_peticion(db, peticion_a_notificar, estado_anterior)

    db.commit()
    db.refresh(trabajo)
    return trabajo


@router.patch(
    "/{trabajo_id}",
    response_model=TrabajoOut,
    status_code=status.HTTP_200_OK,
    summary="Cerrar un trabajo (finalizar o cancelar)",
)
def actualizar_trabajo(
    trabajo_id: int,
    payload: TrabajoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> Trabajo:
    trabajo = db.get(Trabajo, trabajo_id)
    if trabajo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El trabajo solicitado no existe.",
        )

    # Solo se puede cerrar un trabajo en curso. Estados terminales son inmutables.
    if trabajo.estado != EstadoTrabajo.en_curso:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El trabajo no se puede modificar en su estado actual.",
        )

    trabajo.estado = payload.estado
    db.commit()
    db.refresh(trabajo)
    return trabajo


@router.get("", response_model=list[TrabajoOut])
def listar_trabajos(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> list[Trabajo]:
    return list(
        db.scalars(select(Trabajo).order_by(Trabajo.fecha_creacion.desc())).all()
    )


@router.get("/{trabajo_id}", response_model=TrabajoOut)
def obtener_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> Trabajo:
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajo no encontrado.",
        )
    return t


@router.post(
    "/{trabajo_id}/completar",
    response_model=CompletarTrabajoOut,
    summary="Devuelve payload pre-completado para crear el Gasto. NO crea el Gasto.",
)
def completar_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> CompletarTrabajoOut:
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajo no encontrado.",
        )
    if t.presupuesto_aprobado_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El trabajo no tiene un presupuesto aprobado.",
        )
    p = db.get(Presupuesto, t.presupuesto_aprobado_id)
    return CompletarTrabajoOut(
        proveedor_id=p.proveedor_id,
        monto=p.monto,
        concepto_sugerido=t.descripcion or "Trabajo",
        trabajo_id=t.id,
    )


@router.post("/{trabajo_id}/cancelar", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
):
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajo no encontrado.",
        )
    t.estado = EstadoTrabajo.cancelado

    # Cascade: si el trabajo provenía de una petición convertida, marcarla
    # también como cancelada y notificar al depto. La petición no debería
    # quedar huérfana en "convertida_en_trabajo" sin trabajo activo.
    if t.peticion_id:
        peticion = db.get(Peticion, t.peticion_id)
        if peticion and peticion.estado == EstadoPeticion.convertida_en_trabajo:
            estado_anterior = peticion.estado
            peticion.estado = EstadoPeticion.cancelada
            db.flush()
            notificar_cambio_estado_peticion(db, peticion, estado_anterior)

    db.commit()
