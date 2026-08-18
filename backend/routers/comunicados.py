from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import Comunicado, Departamento, Rol
from ..modulos import require_modulo
from ..notificaciones import emitir
from ..notificaciones.catalogo import COMUNICADO_PUBLICADO
from ..schemas import ComunicadoCrear, ComunicadoOut
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/comunicados",
    tags=["Comunicación"],
    dependencies=[Depends(require_modulo("comunicacion"))],
)


@router.get(
    "",
    response_model=list[ComunicadoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar comunicados",
)
def listar_comunicados(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[Comunicado]:
    stmt = (
        select(Comunicado)
        .where(Comunicado.consorcio_id == cid, Comunicado.eliminado_at.is_(None))
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
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Comunicado:
    # autor_id y consorcio_id NUNCA del body: del token/header.
    comunicado = Comunicado(
        consorcio_id=cid,
        titulo=payload.titulo,
        cuerpo=payload.cuerpo,
        autor_id=user.id,
    )
    db.add(comunicado)
    db.flush()

    # Un comunicado le habla a todos los departamentos del consorcio, así que
    # hay que emitir uno por departamento: la audiencia del catálogo apunta a
    # un departamento concreto, no a "todos".
    deptos = db.scalars(
        select(Departamento.id).where(Departamento.consorcio_id == cid)
    ).all()
    for depto_id in deptos:
        emitir(
            db, COMUNICADO_PUBLICADO,
            consorcio_id=cid,
            contexto={"titulo": comunicado.titulo, "cuerpo": comunicado.cuerpo},
            actor_usuario_id=user.id,
            departamento_id=depto_id,
            tareas=tareas,
        )

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
    cid: int = Depends(get_consorcio_activo),
) -> None:
    comunicado = db.get(Comunicado, comunicado_id)
    if comunicado is None or comunicado.consorcio_id != cid or comunicado.eliminado_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comunicado no existe.",
        )
    comunicado.eliminado_at = datetime.now(timezone.utc)
    db.commit()
    return None
