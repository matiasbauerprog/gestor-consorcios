from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import Consorcio, Departamento, EstadoPeticion, Peticion, Rol
from ..modulos import require_modulo
from ..notificaciones import emitir, resolver_pendiente
from ..notificaciones.catalogo import (
    PETICION_BORRADA_POR_DEPTO,
    PETICION_ESTADO_CAMBIADO,
    PETICION_NUEVA,
)
from ..schemas import PeticionActualizar, PeticionCrear, PeticionOut
from ..tenant import get_consorcio_activo

_ADMIN_O_REPRESENTANTE = (Rol.administracion, Rol.representante)

router = APIRouter(
    prefix="/peticiones",
    tags=["Tareas"],
    dependencies=[Depends(require_modulo("operacion"))],
)


@router.get(
    "",
    response_model=list[PeticionOut],
    summary="Listar peticiones",
)
def listar_peticiones(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> list[Peticion]:
    # Admin y representante ven TODAS las peticiones, siempre.
    #
    # Para un departamento depende de `peticiones_visibles_a_depto` (Datos del
    # consorcio): en True —el default histórico— ve también las de los demás,
    # que es transparencia útil para coordinar entre vecinos; en False ve sólo
    # las suyas, para los consorcios que prefieren no exponer los reclamos de
    # una unidad al resto. GET /peticiones/{id} ya restringía al propio depto,
    # así que este filtro no abre nada nuevo: cierra el listado.
    stmt = select(Peticion).where(Peticion.consorcio_id == cid)

    if user.rol == Rol.departamento:
        consorcio = db.get(Consorcio, cid)
        if consorcio is not None and not consorcio.peticiones_visibles_a_depto:
            stmt = stmt.where(Peticion.departamento_id == user.departamento_id)

    stmt = stmt.order_by(Peticion.fecha_creacion.desc())
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=PeticionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una petición",
)
def crear_peticion(
    payload: PeticionCrear,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> Peticion:
    # departamento_id NUNCA del body: siempre del token.
    peticion = Peticion(
        consorcio_id=cid,
        departamento_id=user.departamento_id,
        titulo=payload.titulo,
        descripcion=payload.descripcion,
        estado=EstadoPeticion.abierta,
    )
    db.add(peticion)
    db.flush()

    depto = db.get(Departamento, user.departamento_id)
    emitir(
        db, PETICION_NUEVA,
        consorcio_id=cid,
        contexto={
            "codigo_depto": depto.codigo if depto else "Un departamento",
            "titulo": peticion.titulo,
        },
        actor_usuario_id=user.id,
        entidad_id=peticion.id,
        tareas=tareas,
    )

    db.commit()
    db.refresh(peticion)
    return peticion


@router.get(
    "/{peticion_id}",
    response_model=PeticionOut,
    summary="Obtener detalle de una petición",
)
def obtener_peticion(
    peticion_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> Peticion:
    peticion = db.get(Peticion, peticion_id)
    if peticion is None or peticion.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La petición solicitada no existe.",
        )

    if user.rol == Rol.departamento and peticion.departamento_id != user.departamento_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    return peticion


@router.patch(
    "/{peticion_id}",
    response_model=PeticionOut,
    status_code=status.HTTP_200_OK,
    summary="Rechazar una petición",
)
def actualizar_peticion(
    peticion_id: int,
    payload: PeticionActualizar,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
    cid: int = Depends(get_consorcio_activo),
) -> Peticion:
    peticion = db.get(Peticion, peticion_id)
    if peticion is None or peticion.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La petición solicitada no existe.",
        )

    # Solo se acepta `abierta → rechazada`. La rama de aceptación va por
    # POST /trabajos. Cualquier otro estado de partida es terminal.
    if peticion.estado != EstadoPeticion.abierta:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La petición no se puede modificar en su estado actual.",
        )

    peticion.estado = payload.estado
    # `strip()` para que un textarea con espacios no cuente como motivo: o hay
    # texto real o queda NULL, que es como la UI distingue "sin motivo".
    motivo = (payload.motivo_rechazo or "").strip()
    peticion.motivo_rechazo = motivo or None
    db.flush()

    # El rechazo saca la petición de "abierta": el pendiente del admin ya no
    # es trabajo por hacer.
    resolver_pendiente(
        db, consorcio_id=cid, entidad_tipo="peticion", entidad_id=peticion.id,
    )
    emitir(
        db, PETICION_ESTADO_CAMBIADO,
        consorcio_id=cid,
        contexto={
            "titulo": peticion.titulo,
            "estado": peticion.estado.value,
            "peticion_id": peticion.id,
        },
        actor_usuario_id=user.id,
        departamento_id=peticion.departamento_id,
        tareas=tareas,
    )

    db.commit()
    db.refresh(peticion)
    return peticion


@router.delete(
    "/{peticion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una petición",
)
def eliminar_peticion(
    peticion_id: int,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
) -> None:
    peticion = db.get(Peticion, peticion_id)
    if peticion is None or peticion.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La petición solicitada no existe.",
        )

    # Admin/Representante: pueden borrar cualquier petición en cualquier estado
    if user.rol in (Rol.administracion, Rol.representante):
        # El pendiente apunta a esta petición y no puede quedar vivo señalando
        # algo que ya no existe. Va después de los chequeos de permiso, no
        # antes: así ninguna rama que termina en 403/409 lo toca.
        resolver_pendiente(
            db, consorcio_id=cid, entidad_tipo="peticion", entidad_id=peticion.id,
        )
        db.delete(peticion)
        db.commit()
        return

    # Departamento: solo puede borrar SU PROPIA petición Y solo si está ABIERTA
    if user.rol == Rol.departamento:
        if peticion.departamento_id != user.departamento_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para eliminar esta petición.",
            )
        if peticion.estado != EstadoPeticion.abierta:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo podés eliminar peticiones en estado abierta.",
            )

        resolver_pendiente(
            db, consorcio_id=cid, entidad_tipo="peticion", entidad_id=peticion.id,
        )
        depto = db.get(Departamento, user.departamento_id)
        emitir(
            db, PETICION_BORRADA_POR_DEPTO,
            consorcio_id=cid,
            contexto={
                "codigo_depto": depto.codigo if depto else "Un departamento",
                "titulo": peticion.titulo,
            },
            actor_usuario_id=user.id,
            tareas=tareas,
        )
        db.delete(peticion)
        db.commit()
        return

    # Cualquier otro rol no autorizado
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No autorizado.",
    )
