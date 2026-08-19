"""Router de notificaciones — Fase 11.

Cada usuario ve y modifica SOLO sus notificaciones (filtro por user.id), y
además SOLO dentro del consorcio activo (filtro por cid de X-Consorcio-Id):
un admin con varios edificios no debe listar, contar ni marcar como leídas
notificaciones de un consorcio que no es el que tiene abierto.

Rutas literales primero, ruta con parámetro al final — la Tarea 10 suma
`GET /notificaciones/preferencias` y necesita que ese orden se respete para
que FastAPI no la confunda con `{notificacion_id}`.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import Notificacion
from ..notificaciones.catalogo import eventos_para_rol
from ..notificaciones.preferencias import email_activo_para, guardar_preferencia
from ..schemas import (
    NotificacionOut,
    NotificacionesCountOut,
    PreferenciaNotificacionIn,
    PreferenciaNotificacionOut,
)
from ..tenant import get_consorcio_activo

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get(
    "",
    response_model=list[NotificacionOut],
    status_code=status.HTTP_200_OK,
    summary="Listar notificaciones del usuario",
)
def listar_notificaciones(
    solo_no_leidas: bool = False,
    q: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[Notificacion]:
    stmt = select(Notificacion).where(
        Notificacion.usuario_id == user.id,
        Notificacion.consorcio_id == cid,
    )
    if solo_no_leidas:
        stmt = stmt.where(Notificacion.leida == False)  # noqa: E712
    if q:
        stmt = stmt.where(Notificacion.mensaje.ilike(f"%{q}%"))

    stmt = stmt.order_by(Notificacion.created_at.desc(), Notificacion.id.desc())
    return list(db.scalars(stmt.offset(offset).limit(limit)).all())


@router.get(
    "/no-leidas-count",
    response_model=NotificacionesCountOut,
    status_code=status.HTTP_200_OK,
    summary="Contar notificaciones no leídas",
)
def contar_no_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> NotificacionesCountOut:
    base = select(func.count(Notificacion.id)).where(
        Notificacion.usuario_id == user.id,
        Notificacion.leida == False,  # noqa: E712
    )
    count = db.scalar(base.where(Notificacion.consorcio_id == cid)) or 0

    # Para que el admin con varios edificios no pierda trabajo de vista sin
    # tener que entrar a cada uno. Un depto o representante tiene un solo
    # consorcio, así que esta query les da 0 sola, sin necesidad de un if
    # por rol: no existen notificaciones suyas en OTRO consorcio.
    otros = db.scalar(base.where(Notificacion.consorcio_id != cid)) or 0

    return NotificacionesCountOut(count=count, otros_consorcios=otros)


@router.post(
    "/marcar-todas-leidas",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marcar todas las notificaciones como leídas",
)
def marcar_todas_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> None:
    notifs = list(db.scalars(
        select(Notificacion).where(
            Notificacion.usuario_id == user.id,
            Notificacion.consorcio_id == cid,
            Notificacion.leida == False,  # noqa: E712
        )
    ).all())
    for n in notifs:
        n.leida = True
    db.commit()


@router.get(
    "/preferencias",
    response_model=list[PreferenciaNotificacionOut],
    status_code=status.HTTP_200_OK,
    summary="Listar preferencias de aviso del usuario",
)
def listar_preferencias(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _cid: int = Depends(get_consorcio_activo),
) -> list[PreferenciaNotificacionOut]:
    return [
        PreferenciaNotificacionOut(
            tipo=ev.clave,
            etiqueta=ev.etiqueta,
            email_activo=email_activo_para(db, user.id, ev),
            editable=ev.editable,
            motivo_no_editable=ev.motivo_no_editable,
        )
        for ev in eventos_para_rol(user.rol)
    ]


@router.put(
    "/preferencias",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Guardar preferencias de aviso del usuario",
)
def guardar_preferencias(
    payload: list[PreferenciaNotificacionIn],
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _cid: int = Depends(get_consorcio_activo),
) -> None:
    # Sólo eventos del propio rol del usuario (según token) son tocables acá;
    # el catálogo decide además cuáles de ésos son editables.
    permitidos = {ev.clave: ev for ev in eventos_para_rol(user.rol)}

    for item in payload:
        ev = permitidos.get(item.tipo)
        if ev is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Aviso desconocido para tu rol: {item.tipo}.",
            )
        if not ev.editable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El aviso '{ev.etiqueta}' no se puede configurar.",
            )
        guardar_preferencia(db, user.id, ev, item.email_activo)

    db.commit()


@router.post(
    "/{notificacion_id}/marcar-leida",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marcar una notificación como leída",
)
def marcar_leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> None:
    notif = db.get(Notificacion, notificacion_id)
    if notif is None or notif.usuario_id != user.id or notif.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada.",
        )
    notif.leida = True
    db.commit()
