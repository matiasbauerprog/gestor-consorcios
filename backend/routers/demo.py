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
from ..models import Rol, Usuario
from ..schemas import DemoLoginIn, TokenOut, UsuarioOut
from .auth import _administracion_activa_para

router = APIRouter(prefix="/auth", tags=["Auth"])

# Lista blanca cerrada: rol del selector → (email, Rol esperado) del usuario
# demo que genera backend/seed_demo.py. No se acepta email ni id por body: no
# hay forma de pedir el token de otro usuario.
#
# Guardamos también el Rol esperado (no solo el email) porque el rol real
# sale de `user.rol` en la base: si el seed crea el usuario con el rol
# equivocado, o si alguien lo muta después vía POST /usuarios, demo-login no
# debe acuñar un token con un alcance distinto al que el selector prometía.
_USUARIOS_DEMO: dict[str, tuple[str, Rol]] = {
    "administracion": ("admin@demo.local", Rol.administracion),
    "propietario_al_dia": ("uf01a@demo.local", Rol.departamento),
    "propietario_moroso": ("uf03c@demo.local", Rol.departamento),
}


@router.post(
    "/demo-login",
    response_model=TokenOut,
    status_code=status.HTTP_200_OK,
    summary="Emitir token de un usuario demo sin credenciales",
)
def demo_login(payload: DemoLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    # Defensa en profundidad (candado 2, segunda capa): el registro
    # condicional en backend/main.py es la barrera principal, pero si algún
    # día alguien registra este router sin pasar por ese `if` (ej. lo suma a
    # mano al bloque de includes incondicionales), esta línea sigue negando
    # el endpoint. 404 y no 403: en producción el endpoint no debe parecer
    # que "existe pero está prohibido".
    if not get_settings().DEMO_MODE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    email, rol_esperado = _USUARIOS_DEMO[payload.rol]  # el Literal del schema ya validó
    user = db.scalar(select(Usuario).where(Usuario.email == email))

    # Mismo detail para "no existe" y "existe pero con otro rol": no
    # diferenciar evita filtrar si alguien mutó el usuario demo (rol, baja)
    # por otra vía y de paso cierra cualquier duda sobre qué le pasó al
    # dataset — para el cliente ambos casos son "el demo no está listo".
    if user is None or user.rol != rol_esperado:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El dataset demo todavía no fue generado.",
        )

    # Mismos gates que /auth/login (backend/routers/auth.py): demo-login no
    # debe emitir tokens que un login real rechazaría.
    if not user.activa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="usuario_suspendido",
        )
    if not _administracion_activa_para(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="administracion_suspendida",
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
