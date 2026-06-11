from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import Comunicado, Rol
from ..schemas import ComunicadoCrear, ComunicadoOut

router = APIRouter(prefix="/comunicados", tags=["Comunicación"])


@router.get(
    "",
    response_model=list[ComunicadoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar comunicados",
)
def listar_comunicados(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[Comunicado]:
    stmt = (
        select(Comunicado)
        .where(Comunicado.eliminado_at.is_(None))
        .order_by(Comunicado.fecha_publicacion.desc(), Comunicado.id.desc())
    )
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ComunicadoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar un comunicado",
)
def crear_comunicado(
    payload: ComunicadoCrear,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Comunicado:
    # autor_id NUNCA del body: siempre del token.
    comunicado = Comunicado(
        titulo=payload.titulo,
        cuerpo=payload.cuerpo,
        autor_id=user.id,
    )
    db.add(comunicado)
    db.commit()
    db.refresh(comunicado)
    return comunicado


@router.delete(
    "/{comunicado_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar un comunicado (soft-delete)",
)
def borrar_comunicado(
    comunicado_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> None:
    comunicado = db.get(Comunicado, comunicado_id)
    if comunicado is None or comunicado.eliminado_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comunicado no existe.",
        )
    comunicado.eliminado_at = datetime.now(timezone.utc)
    db.commit()
    return None
