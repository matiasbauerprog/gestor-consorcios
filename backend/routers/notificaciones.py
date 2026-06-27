"""Router de notificaciones — Fase 11.

Cada usuario ve y modifica SOLO sus notificaciones (filtro por user.id).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import Notificacion
from ..schemas import NotificacionOut, NotificacionesCountOut

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get(
    "",
    response_model=list[NotificacionOut],
    summary="Listar notificaciones del usuario",
)
def listar_notificaciones(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Notificacion]:
    return list(db.scalars(
        select(Notificacion)
        .where(Notificacion.usuario_id == user.id)
        .order_by(Notificacion.created_at.desc())
        .limit(limit)
    ).all())


@router.get(
    "/no-leidas-count",
    response_model=NotificacionesCountOut,
    summary="Contar notificaciones no leídas",
)
def contar_no_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> NotificacionesCountOut:
    count = db.scalar(
        select(func.count(Notificacion.id)).where(
            Notificacion.usuario_id == user.id,
            Notificacion.leida == False,
        )
    ) or 0
    return NotificacionesCountOut(count=count)


@router.post(
    "/{notif_id}/marcar-leida",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marcar una notificación como leída",
)
def marcar_leida(
    notif_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    notif = db.get(Notificacion, notif_id)
    if notif is None or notif.usuario_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada.",
        )
    notif.leida = True
    db.commit()


@router.post(
    "/marcar-todas-leidas",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marcar todas las notificaciones como leídas",
)
def marcar_todas_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    notifs = list(db.scalars(
        select(Notificacion).where(
            Notificacion.usuario_id == user.id,
            Notificacion.leida == False,
        )
    ).all())
    for n in notifs:
        n.leida = True
    db.commit()
