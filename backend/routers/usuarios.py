from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Departamento, Rol, Usuario
from ..schemas import UsuarioActualizar, UsuarioCrear, UsuarioOut
from ..security import hash_password

router = APIRouter(prefix="/usuarios", tags=["Administracion"])


def _verificar_consistencia_rol_depto(rol: Rol, departamento_id: int | None) -> None:
    """Las invariantes rol↔depto deben mantenerse en POST y en el estado final del PATCH."""
    if rol == Rol.departamento and departamento_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los usuarios con rol `departamento` requieren `departamento_id`.",
        )
    if rol != Rol.departamento and departamento_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo los usuarios con rol `departamento` pueden tener `departamento_id`.",
        )


@router.get(
    "",
    response_model=list[UsuarioOut],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios",
)
def listar_usuarios(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Usuario]:
    stmt = select(Usuario).order_by(Usuario.email.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario",
)
def crear_usuario(
    payload: UsuarioCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Usuario:
    if payload.departamento_id is not None:
        if db.get(Departamento, payload.departamento_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El departamento indicado no existe.",
            )

    duplicado = db.scalar(select(Usuario.id).where(Usuario.email == payload.email))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email.",
        )

    usuario = Usuario(
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
        departamento_id=payload.departamento_id,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioOut,
    status_code=status.HTTP_200_OK,
    summary="Editar un usuario (sin cambiar contraseña)",
)
def actualizar_usuario(
    usuario_id: int,
    payload: UsuarioActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)

    if "email" in cambios and cambios["email"] != usuario.email:
        en_uso = db.scalar(
            select(Usuario.id).where(
                Usuario.email == cambios["email"],
                Usuario.id != usuario.id,
            )
        )
        if en_uso is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email.",
            )

    if "departamento_id" in cambios and cambios["departamento_id"] is not None:
        if db.get(Departamento, cambios["departamento_id"]) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El departamento indicado no existe.",
            )

    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)

    # Verificación de invariantes sobre el estado FINAL del usuario, no sobre el payload:
    # un PATCH parcial puede dejar al usuario en estado inconsistente si solo cambia
    # `rol` sin tocar `departamento_id` o viceversa.
    _verificar_consistencia_rol_depto(usuario.rol, usuario.departamento_id)

    db.commit()
    db.refresh(usuario)
    return usuario
