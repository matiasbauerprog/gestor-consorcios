from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import ClaseProrrateo, CoeficienteDepartamento, Rol
from ..tenant import get_consorcio_activo
from ..schemas import (
    ClaseProrrateoActualizar,
    ClaseProrrateoCrear,
    ClaseProrrateoOut,
)

router = APIRouter(prefix="/clases-prorrateo", tags=["Configuración"])


@router.get(
    "",
    response_model=list[ClaseProrrateoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar clases de prorrateo",
)
def listar_clases(
    activa: bool | None = Query(default=None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[ClaseProrrateo]:
    stmt = select(ClaseProrrateo).where(ClaseProrrateo.consorcio_id == cid).order_by(ClaseProrrateo.codigo.asc())
    if activa is not None:
        stmt = stmt.where(ClaseProrrateo.activa == activa)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ClaseProrrateoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear clase de prorrateo",
)
def crear_clase(
    payload: ClaseProrrateoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ClaseProrrateo:
    duplicada = db.scalar(
        select(ClaseProrrateo.id).where(
            ClaseProrrateo.codigo == payload.codigo,
            ClaseProrrateo.consorcio_id == cid,
        )
    )
    if duplicada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una clase con ese código.",
        )

    clase = ClaseProrrateo(
        consorcio_id=cid,
        codigo=payload.codigo,
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        activa=True,
    )
    db.add(clase)
    db.commit()
    db.refresh(clase)
    return clase


@router.get(
    "/{clase_prorrateo_id}",
    response_model=ClaseProrrateoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener clase de prorrateo",
)
def obtener_clase(
    clase_prorrateo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ClaseProrrateo:
    clase = db.get(ClaseProrrateo, clase_prorrateo_id)
    if clase is None or clase.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase solicitada no existe.",
        )
    return clase


@router.patch(
    "/{clase_prorrateo_id}",
    response_model=ClaseProrrateoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar clase de prorrateo",
)
def actualizar_clase(
    clase_prorrateo_id: int,
    payload: ClaseProrrateoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ClaseProrrateo:
    clase = db.get(ClaseProrrateo, clase_prorrateo_id)
    if clase is None or clase.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase solicitada no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(clase, campo, valor)

    db.commit()
    db.refresh(clase)
    return clase


@router.delete(
    "/{clase_prorrateo_id}",
    response_model=ClaseProrrateoOut | None,
    status_code=status.HTTP_200_OK,
    summary="Eliminar clase de prorrateo (hard si no tiene coeficientes; soft si tiene)",
)
def eliminar_clase(
    clase_prorrateo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
):
    from fastapi import Response

    clase = db.get(ClaseProrrateo, clase_prorrateo_id)
    if clase is None or clase.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase solicitada no existe.",
        )

    tiene_coeficientes = (
        db.scalar(
            select(CoeficienteDepartamento.id).where(
                CoeficienteDepartamento.clase_prorrateo_id == clase_prorrateo_id
            )
        )
        is not None
    )

    if tiene_coeficientes:
        clase.activa = False
        db.commit()
        db.refresh(clase)
        return clase

    db.delete(clase)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
