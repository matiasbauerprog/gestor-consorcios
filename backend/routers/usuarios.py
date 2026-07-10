from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Comunicado, Consorcio, Departamento, PeriodoCerrado, Reserva, Rol, Usuario
from ..schemas import UsuarioActualizar, UsuarioCrear, UsuarioEstado, UsuarioOut
from ..security import hash_password
from ..tenant import get_consorcio_activo

router = APIRouter(prefix="/usuarios", tags=["Administracion"])


def _usuario_scoped(db: Session, usuario_id: int, cid: int) -> Usuario | None:
    """Devuelve el usuario si pertenece al consorcio activo, sino None.
    Se aplica el mismo criterio que listar_usuarios."""
    u = db.get(Usuario, usuario_id)
    if u is None:
        return None
    if u.rol == Rol.departamento and u.departamento_id is not None:
        d = db.get(Departamento, u.departamento_id)
        return u if d is not None and d.consorcio_id == cid else None
    if u.rol == Rol.representante:
        return u if u.consorcio_id == cid else None
    if u.rol == Rol.administracion:
        c = db.get(Consorcio, cid)
        return u if c is not None and u.administracion_id == c.administracion_id else None
    return None


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
    cid: int = Depends(get_consorcio_activo),
) -> list[Usuario]:
    # Scope multitenant: usuarios "de" este consorcio son:
    # - departamento cuyo depto pertenece al consorcio
    # - representante del consorcio
    # - administración que administra este consorcio (admin_id == consorcio.admin_id)
    admin_id_sq = select(Consorcio.administracion_id).where(Consorcio.id == cid).scalar_subquery()
    depto_ids_sq = select(Departamento.id).where(Departamento.consorcio_id == cid).scalar_subquery()

    stmt = (
        select(Usuario)
        .where(
            or_(
                Usuario.departamento_id.in_(depto_ids_sq),
                Usuario.consorcio_id == cid,
                Usuario.administracion_id == admin_id_sq,
            )
        )
        .order_by(Usuario.email.asc())
    )
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
    cid: int = Depends(get_consorcio_activo),
) -> Usuario:
    if payload.departamento_id is not None:
        depto = db.get(Departamento, payload.departamento_id)
        if depto is None or depto.consorcio_id != cid:
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
        must_change_password=True,
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
    cid: int = Depends(get_consorcio_activo),
) -> Usuario:
    usuario = _usuario_scoped(db, usuario_id, cid)
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
        depto = db.get(Departamento, cambios["departamento_id"])
        if depto is None or depto.consorcio_id != cid:
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


@router.patch(
    "/{usuario_id}/estado",
    response_model=UsuarioOut,
    status_code=status.HTTP_200_OK,
    summary="Suspender o reactivar un usuario",
)
def cambiar_estado(
    usuario_id: int,
    payload: UsuarioEstado,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Usuario:
    if usuario_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no_puede_suspenderse_a_si_mismo",
        )
    usuario = _usuario_scoped(db, usuario_id, cid)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario solicitado no existe.",
        )
    usuario.activa = payload.activa
    db.commit()
    db.refresh(usuario)
    return usuario


def _tiene_actividad_vinculada(db: Session, usuario_id: int) -> bool:
    """True si eliminarlo dispararía FK RESTRICT (reservas, comunicados, cierres de período)."""
    if db.query(Reserva.id).filter(Reserva.usuario_id == usuario_id).first() is not None:
        return True
    if db.query(Comunicado.id).filter(Comunicado.autor_id == usuario_id).first() is not None:
        return True
    if db.query(PeriodoCerrado.periodo).filter(
        PeriodoCerrado.cerrado_por_usuario_id == usuario_id
    ).first() is not None:
        return True
    return False


@router.delete(
    "/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un usuario (hard delete)",
    response_class=Response,
)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Response:
    if usuario_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no_puede_eliminarse_a_si_mismo",
        )
    usuario = _usuario_scoped(db, usuario_id, cid)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario solicitado no existe.",
        )
    if _tiene_actividad_vinculada(db, usuario_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="usuario_con_actividad",
        )
    db.delete(usuario)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


