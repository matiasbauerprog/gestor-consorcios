"""Login sin credenciales para el modo demo.

Este router SOLO se registra cuando DEMO_MODE=true (ver backend/main.py). En
producción la ruta no existe y cualquier request da 404.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_access_token
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..schemas import DemoLoginIn, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Auth"])

# Lista blanca cerrada: rol del selector → email del usuario demo que genera
# backend/seed_demo.py. No se acepta email ni id por body: no hay forma de
# pedir el token de otro usuario.
_USUARIOS_DEMO: dict[str, str] = {
    "administracion": "admin@demo.local",
    "propietario_al_dia": "uf01a@demo.local",
    "propietario_moroso": "uf03c@demo.local",
}


@router.post(
    "/demo-login",
    response_model=TokenOut,
    status_code=status.HTTP_200_OK,
    summary="Emitir token de un usuario demo sin credenciales",
)
def demo_login(payload: DemoLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    email = _USUARIOS_DEMO[payload.rol]  # el Literal del schema ya validó
    user = db.scalar(select(Usuario).where(Usuario.email == email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El dataset demo todavía no fue generado.",
        )

    settings = get_settings()
    token = create_access_token(
        user_id=user.id,
        rol=user.rol,
        departamento_id=user.departamento_id,
        settings=settings,
    )
    return TokenOut(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRES_MIN * 60,
        user=UsuarioOut.model_validate(user),
    )
