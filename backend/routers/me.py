"""Endpoints /me/* — resource propia del usuario autenticado (Plan A multitenant)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import Consorcio, Departamento, Rol, Usuario

router = APIRouter(prefix="/me", tags=["Me"])


class ConsorcioMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


@router.get(
    "/consorcios",
    response_model=list[ConsorcioMini],
    status_code=status.HTTP_200_OK,
    summary="Lista los consorcios accesibles al usuario autenticado",
)
def listar_mis_consorcios(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Consorcio]:
    u = db.get(Usuario, user.id)
    if u is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    if u.rol == Rol.administracion:
        return db.query(Consorcio).filter(
            Consorcio.administracion_id == u.administracion_id
        ).order_by(Consorcio.nombre).all()
    if u.rol == Rol.representante and u.consorcio_id is not None:
        c = db.get(Consorcio, u.consorcio_id)
        return [c] if c is not None else []
    if u.rol == Rol.departamento and u.departamento_id is not None:
        d = db.get(Departamento, u.departamento_id)
        if d is None:
            return []
        c = db.get(Consorcio, d.consorcio_id)
        return [c] if c is not None else []
    return []
