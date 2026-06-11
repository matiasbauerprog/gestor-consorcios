from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Departamento, Rol
from ..schemas import DepartamentoActualizar, DepartamentoCrear, DepartamentoOut

router = APIRouter(prefix="/departamentos", tags=["Administracion"])


@router.get(
    "",
    response_model=list[DepartamentoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar departamentos",
)
def listar_departamentos(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Departamento]:
    stmt = select(Departamento).order_by(Departamento.codigo.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=DepartamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un departamento (unidad funcional)",
)
def crear_departamento(
    payload: DepartamentoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Departamento:
    duplicado = db.scalar(select(Departamento.id).where(Departamento.codigo == payload.codigo))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un departamento con ese código.",
        )

    departamento = Departamento(codigo=payload.codigo, descripcion=payload.descripcion)
    db.add(departamento)
    db.commit()
    db.refresh(departamento)
    return departamento


@router.patch(
    "/{departamento_id}",
    response_model=DepartamentoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar un departamento",
)
def actualizar_departamento(
    departamento_id: int,
    payload: DepartamentoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Departamento:
    departamento = db.get(Departamento, departamento_id)
    if departamento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(departamento, campo, valor)

    db.commit()
    db.refresh(departamento)
    return departamento
