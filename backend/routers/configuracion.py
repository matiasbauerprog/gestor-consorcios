from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import ConfiguracionConsorcio, Rol
from ..schemas import ConfiguracionConsorcioActualizar, ConfiguracionConsorcioOut

router = APIRouter(prefix="/configuracion", tags=["Configuración"])

_SINGLETON_ID = 1


@router.get(
    "",
    response_model=ConfiguracionConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener configuración del consorcio (singleton)",
)
def obtener_configuracion(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> ConfiguracionConsorcio:
    cfg = db.get(ConfiguracionConsorcio, _SINGLETON_ID)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La configuración del consorcio no fue inicializada.",
        )
    return cfg


@router.put(
    "",
    response_model=ConfiguracionConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar configuración del consorcio (singleton)",
)
def actualizar_configuracion(
    payload: ConfiguracionConsorcioActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ConfiguracionConsorcio:
    cfg = db.get(ConfiguracionConsorcio, _SINGLETON_ID)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La configuración del consorcio no fue inicializada.",
        )

    for campo, valor in payload.model_dump().items():
        setattr(cfg, campo, valor)

    db.commit()
    db.refresh(cfg)
    return cfg
