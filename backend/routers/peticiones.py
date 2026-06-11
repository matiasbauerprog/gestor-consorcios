from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import EstadoPeticion, Peticion, Rol
from ..schemas import PeticionActualizar, PeticionCrear, PeticionOut

_ADMIN_O_REPRESENTANTE = (Rol.administracion, Rol.representante)

router = APIRouter(prefix="/peticiones", tags=["Tareas"])


@router.get(
    "",
    response_model=list[PeticionOut],
    summary="Listar peticiones",
)
def listar_peticiones(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Peticion]:
    stmt = select(Peticion).order_by(Peticion.fecha_creacion.desc())

    # Directiva de seguridad: filtrado por departamento_id aplicado en SQL,
    # NO post-fetch, y la identidad proviene exclusivamente del token.
    if user.rol == Rol.departamento:
        stmt = stmt.where(Peticion.departamento_id == user.departamento_id)

    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=PeticionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una petición",
)
def crear_peticion(
    payload: PeticionCrear,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> Peticion:
    # departamento_id NUNCA del body: siempre del token.
    peticion = Peticion(
        departamento_id=user.departamento_id,
        titulo=payload.titulo,
        descripcion=payload.descripcion,
        estado=EstadoPeticion.abierta,
    )
    db.add(peticion)
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
) -> Peticion:
    peticion = db.get(Peticion, peticion_id)
    if peticion is None:
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
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(*_ADMIN_O_REPRESENTANTE)),
) -> Peticion:
    peticion = db.get(Peticion, peticion_id)
    if peticion is None:
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
    db.commit()
    db.refresh(peticion)
    return peticion
