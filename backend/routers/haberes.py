from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Haber, Rol
from ..schemas import HaberActualizar, HaberCrear, HaberOut

router = APIRouter(prefix="/haberes", tags=["Personal"])


@router.get(
    "",
    response_model=list[HaberOut],
    status_code=status.HTTP_200_OK,
    summary="Listar haberes (catálogo)",
)
def listar_haberes(
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Haber]:
    stmt = select(Haber).order_by(Haber.orden.asc(), Haber.nombre.asc())
    if activo is not None:
        stmt = stmt.where(Haber.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=HaberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear haber",
)
def crear_haber(
    payload: HaberCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    duplicado = db.scalar(select(Haber.id).where(Haber.nombre == payload.nombre))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un haber con ese nombre.",
        )

    haber = Haber(
        nombre=payload.nombre,
        tipo=payload.tipo,
        valor_default=payload.valor_default,
        orden=payload.orden,
        activo=True,
    )
    db.add(haber)
    db.commit()
    db.refresh(haber)
    return haber


@router.get(
    "/{haber_id}",
    response_model=HaberOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener haber",
)
def obtener_haber(
    haber_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    haber = db.get(Haber, haber_id)
    if haber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El haber solicitado no existe.",
        )
    return haber


@router.patch(
    "/{haber_id}",
    response_model=HaberOut,
    status_code=status.HTTP_200_OK,
    summary="Editar haber",
)
def actualizar_haber(
    haber_id: int,
    payload: HaberActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    haber = db.get(Haber, haber_id)
    if haber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El haber solicitado no existe.",
        )

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(haber, campo, valor)

    db.commit()
    db.refresh(haber)
    return haber


@router.delete(
    "/{haber_id}",
    response_model=HaberOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar haber (soft-delete)",
)
def eliminar_haber(
    haber_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    haber = db.get(Haber, haber_id)
    if haber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El haber solicitado no existe.",
        )

    haber.activo = False
    db.commit()
    db.refresh(haber)
    return haber
