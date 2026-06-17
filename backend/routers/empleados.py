from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Empleado, LiquidacionEmpleado, Proveedor, Rol
from ..schemas import EmpleadoActualizar, EmpleadoCrear, EmpleadoOut

router = APIRouter(prefix="/empleados", tags=["Personal"])


def _validar_proveedor(db: Session, proveedor_id: int) -> None:
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


@router.get(
    "",
    response_model=list[EmpleadoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar empleados",
)
def listar_empleados(
    activo: bool | None = Query(default=True),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Empleado]:
    stmt = select(Empleado).order_by(Empleado.nombre_completo.asc())
    if activo is not None:
        stmt = stmt.where(Empleado.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=EmpleadoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear empleado",
)
def crear_empleado(
    payload: EmpleadoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Empleado:
    duplicado = db.scalar(select(Empleado.id).where(Empleado.cuil == payload.cuil))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un empleado con ese CUIL.",
        )

    _validar_proveedor(db, payload.proveedor_id)

    empleado = Empleado(
        nombre_completo=payload.nombre_completo,
        cuil=payload.cuil,
        categoria=payload.categoria,
        fecha_ingreso=payload.fecha_ingreso,
        fecha_egreso=payload.fecha_egreso,
        sueldo_basico=payload.sueldo_basico,
        proveedor_id=payload.proveedor_id,
        activo=True,
    )
    db.add(empleado)
    db.commit()
    db.refresh(empleado)
    return empleado


@router.get(
    "/{empleado_id}",
    response_model=EmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener empleado",
)
def obtener_empleado(
    empleado_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Empleado:
    empleado = db.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )
    return empleado


@router.patch(
    "/{empleado_id}",
    response_model=EmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar empleado",
)
def actualizar_empleado(
    empleado_id: int,
    payload: EmpleadoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Empleado:
    empleado = db.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    if "proveedor_id" in cambios and cambios["proveedor_id"] is not None:
        _validar_proveedor(db, cambios["proveedor_id"])

    for campo, valor in cambios.items():
        setattr(empleado, campo, valor)

    db.commit()
    db.refresh(empleado)
    return empleado


@router.delete(
    "/{empleado_id}",
    response_model=EmpleadoOut | None,
    status_code=status.HTTP_200_OK,
    summary="Eliminar empleado (hard si no tiene liquidaciones; soft si tiene)",
)
def eliminar_empleado(
    empleado_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    empleado = db.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )

    tiene_liquidaciones = (
        db.scalar(
            select(LiquidacionEmpleado.id).where(LiquidacionEmpleado.empleado_id == empleado_id)
        )
        is not None
    )

    if tiene_liquidaciones:
        empleado.activo = False
        db.commit()
        db.refresh(empleado)
        return empleado

    db.delete(empleado)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
