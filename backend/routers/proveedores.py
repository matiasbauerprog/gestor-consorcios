from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Proveedor, Rol
from ..schemas import ProveedorActualizar, ProveedorCrear, ProveedorOut

router = APIRouter(prefix="/proveedores", tags=["Configuración"])


@router.get(
    "",
    response_model=list[ProveedorOut],
    status_code=status.HTTP_200_OK,
    summary="Listar proveedores",
)
def listar_proveedores(
    activo: bool | None = Query(
        default=True, description="Filtrar por estado activo (default True)"
    ),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Proveedor]:
    stmt = select(Proveedor).order_by(Proveedor.razon_social.asc())
    if activo is not None:
        stmt = stmt.where(Proveedor.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ProveedorOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
)
def crear_proveedor(
    payload: ProveedorCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    duplicado = db.scalar(select(Proveedor.id).where(Proveedor.cuit == payload.cuit))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proveedor con ese CUIT.",
        )

    prov = Proveedor(
        razon_social=payload.razon_social,
        nombre_fantasia=payload.nombre_fantasia,
        cuit=payload.cuit,
        direccion=payload.direccion,
        activo=True,
    )
    db.add(prov)
    db.commit()
    db.refresh(prov)
    return prov


@router.get(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener proveedor",
)
def obtener_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor solicitado no existe.",
        )
    return prov


@router.patch(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    status_code=status.HTTP_200_OK,
    summary="Editar proveedor",
)
def actualizar_proveedor(
    proveedor_id: int,
    payload: ProveedorActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(prov, campo, valor)

    db.commit()
    db.refresh(prov)
    return prov


@router.delete(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar proveedor (soft-delete)",
)
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor solicitado no existe.",
        )
    prov.activo = False
    db.commit()
    db.refresh(prov)
    return prov
