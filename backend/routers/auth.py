from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import blacklist
from ..auth import CurrentUser, create_access_token, get_current_user
from ..config import get_settings
from ..database import get_db
from ..mail_service import enviar_email
from ..models import Administracion, Consorcio, Departamento, Rol, Usuario
from ..recuperacion import canjear_token, emitir_token
from ..schemas import (
    CambiarPasswordIn,
    LoginIn,
    RecuperarPasswordIn,
    RestablecerPasswordIn,
    TokenOut,
    UsuarioOut,
)
from ..security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])

# Hash dummy precomputado al cargar el módulo. Se usa cuando el email no existe
# para que `verify_password` corra siempre, equiparando el tiempo de respuesta
# y previniendo enumeración de usuarios por timing attack.
_DUMMY_HASH = hash_password("anti-enumeration-placeholder")


def _administracion_activa_para(db: Session, user: Usuario) -> bool:
    """Devuelve True si el tenant del usuario está activo (o si el usuario no tiene tenant)."""
    if user.rol == Rol.super_admin:
        return True
    aid = None
    if user.rol == Rol.administracion:
        aid = user.administracion_id
    elif user.rol == Rol.representante and user.consorcio_id is not None:
        c = db.get(Consorcio, user.consorcio_id)
        aid = c.administracion_id if c is not None else None
    elif user.rol == Rol.departamento and user.departamento_id is not None:
        d = db.get(Departamento, user.departamento_id)
        if d is not None:
            c = db.get(Consorcio, d.consorcio_id)
            aid = c.administracion_id if c is not None else None
    if aid is None:
        return True
    admin_tenant = db.get(Administracion, aid)
    return admin_tenant is not None and admin_tenant.activa


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

    # Usuario suspendido por su admin: cortar antes de emitir token.
    if not user.activa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="usuario_suspendido",
        )

    # Multitenant: bloquear login si la administracion del usuario está suspendida.
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
    "/recuperar-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Pedir un link para restablecer la contraseña",
)
def recuperar_password(
    payload: RecuperarPasswordIn, db: Session = Depends(get_db)
) -> dict:
    """Siempre responde 202, exista o no la cuenta.

    Cualquier ramificación observable —código distinto, mensaje distinto, o un
    error cuando falla el envío— convierte este formulario en un verificador de
    qué emails están registrados. `enviar_email` devuelve False ante un fallo
    en vez de levantar excepción, así que el 202 se mantiene igual.
    """
    usuario = db.scalar(select(Usuario).where(Usuario.email == payload.email))

    if (
        usuario is not None
        and usuario.activa
        and _administracion_activa_para(db, usuario)
    ):
        claro = emitir_token(db, usuario)
        if claro is not None:  # None = superó el límite de pedidos por hora
            settings = get_settings()
            link = f"{settings.FRONTEND_URL}/restablecer-password?token={claro}"
            enviar_email(
                to=usuario.email,
                subject="Restablecer tu contraseña",
                body=(
                    "Hola,\n\n"
                    "Pediste restablecer tu contraseña. Entrá acá para elegir "
                    "una nueva:\n\n"
                    f"{link}\n\n"
                    f"El link vence en {settings.RECUPERACION_TOKEN_MINUTOS} "
                    "minutos y se puede usar una sola vez.\n\n"
                    "Si no fuiste vos, ignorá este mensaje: tu contraseña no "
                    "cambió.\n\n"
                    "Administración."
                ),
            )

    return {"detail": "Si el email está registrado, te va a llegar un mensaje."}


@router.post(
    "/restablecer-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restablecer la contraseña con el token del email",
    response_class=Response,
)
def restablecer_password(
    payload: RestablecerPasswordIn, db: Session = Depends(get_db)
) -> Response:
    usuario = canjear_token(db, payload.token)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El link es inválido o venció. Pedí uno nuevo.",
        )

    usuario.password_hash = hash_password(payload.new_password)
    # Sin esto, quien tenía cambio obligatorio pendiente resetea su clave y
    # sigue recibiendo 403 en todo endpoint operacional.
    usuario.must_change_password = False
    db.commit()
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
    usuario.must_change_password = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
