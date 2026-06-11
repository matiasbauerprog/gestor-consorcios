from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import blacklist
from ..auth import CurrentUser, create_access_token, get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..schemas import CambiarPasswordIn, LoginIn, TokenOut, UsuarioOut
from ..security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])

# Hash dummy precomputado al cargar el módulo. Se usa cuando el email no existe
# para que `verify_password` corra siempre, equiparando el tiempo de respuesta
# y previniendo enumeración de usuarios por timing attack.
_DUMMY_HASH = hash_password("anti-enumeration-placeholder")


@router.post(
    "/login",
    response_model=TokenOut,
    status_code=status.HTTP_200_OK,
    summary="Autenticar usuario y obtener token JWT",
)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(Usuario).where(Usuario.email == payload.email))

    # Siempre llamamos a verify_password (aunque user sea None) para no filtrar
    # vía timing si el email existe o no.
    hashed = user.password_hash if user is not None else _DUMMY_HASH
    password_ok = verify_password(payload.password, hashed)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
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


@router.get(
    "/me",
    response_model=UsuarioOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener los datos del usuario autenticado",
)
def obtener_usuario_actual(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Usuario:
    usuario = db.get(Usuario, user.id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario asociado al token ya no existe.",
        )
    return usuario


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar el token actual (logout)",
    response_class=Response,
)
def logout(user: CurrentUser = Depends(get_current_user)) -> Response:
    # Revoca el jti del token hasta su `exp` natural. A partir de acá, cualquier
    # request que lo presente verá 401 "Token revocado." en `decode_token`.
    blacklist.revoke(user.jti, user.exp)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/cambiar-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambiar la contraseña del usuario autenticado",
    response_class=Response,
)
def cambiar_password(
    payload: CambiarPasswordIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    usuario = db.get(Usuario, user.id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario asociado al token ya no existe.",
        )

    if not verify_password(payload.current_password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
