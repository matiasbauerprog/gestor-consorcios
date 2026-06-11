from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoTrabajo,
    Peticion,
    Presupuesto,
    Rol,
    Trabajo,
)
from ..schemas import (
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

    # Si el trabajo viene de una petición existente, validamos y la marcamos
    # como convertida. Si no, queda como trabajo "desde cero" (peticion_id null).
    if payload.peticion_id is not None:
        peticion = db.get(Peticion, payload.peticion_id)
        if peticion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La petición indicada no existe.",
            )
        peticion.estado = EstadoPeticion.convertida_en_trabajo
        peticion_id = peticion.id

    trabajo = Trabajo(
        peticion_id=peticion_id,
        descripcion=payload.descripcion,
        estado=EstadoTrabajo.en_curso,
    )
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


@router.post(
    "/{trabajo_id}/presupuestos",
    response_model=PresupuestoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar/aprobar presupuesto de un proveedor",
)
def registrar_presupuesto(
    trabajo_id: int,
    payload: PresupuestoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> Presupuesto:
    trabajo = db.get(Trabajo, trabajo_id)
    if trabajo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El trabajo solicitado no existe.",
        )

    presupuesto = Presupuesto(
        trabajo_id=trabajo.id,
        proveedor=payload.proveedor,
        monto=payload.monto,
        estado=(
            EstadoPresupuesto.aprobado if payload.aprobado else EstadoPresupuesto.presentado
        ),
    )
    db.add(presupuesto)
    db.commit()
    db.refresh(presupuesto)
    return presupuesto


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
