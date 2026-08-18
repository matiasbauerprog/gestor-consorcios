"""Registro de errores inesperados.

Un error se registra en **dos lugares**, en este orden:

1. La salida del servidor, siempre. Es la fuente de verdad: sobrevive a que la
   base esté caída, que es justo cuando más se necesita el rastro.
2. La tabla `errores_registrados`, si se puede. Es la copia cómoda de consultar
   desde el panel.

Y se devuelve un código corto que se le muestra al usuario. Ese código es la
única pieza que viaja del vecino al soporte: con él se llega a la fila y a la
línea del log.

**Regla dura:** registrar nunca puede levantar una excepción. Si lo hiciera,
taparía el error original y le cambiaría la respuesta al usuario.
"""
import logging
import re
import secrets
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .models import ErrorRegistrado

logger = logging.getLogger(__name__)

# Sin I, L, O, 0, 1: se confunden al dictarlos por teléfono.
_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LARGO = 6

_MAX_MENSAJE = 1000
_MAX_TRAZA = 8000

# Busca `password: 'x'`, `"token" = x`, `secret=x` y variantes, y se queda con
# la clave y el separador para poder reponerlos con el valor tachado.
_SECRETO_EN_TEXTO = re.compile(
    r"(?P<clave>['\"]?\w*(?:password|token|secret)\w*['\"]?)"
    r"(?P<separador>\s*[:=]\s*)"
    r"['\"]?[^'\",;}\s]+['\"]?",
    re.IGNORECASE,
)


def generar_codigo() -> str:
    """Código corto, legible en voz alta, con espacio de sobra para no repetir."""
    cuerpo = "".join(secrets.choice(_ALFABETO) for _ in range(_LARGO))
    return f"E-{cuerpo}"


def _mensaje_seguro(exc: BaseException) -> str:
    """El texto del error, tachando lo que parezca un secreto.

    `audit.redactar_payload` no sirve acá: trabaja sobre nombres de campo de un
    dict, y el texto de una excepción es una cadena suelta donde el secreto
    viene incrustado (`{'password': 'secreta'}`).

    Esto es **mejor esfuerzo**, no una garantía: busca `password`, `token` o
    `secret` seguidos de un valor y lo reemplaza. La protección de verdad es
    que el código no meta payloads en los mensajes de excepción; esto es la red
    por si alguno se escapa.
    """
    crudo = f"{exc}"
    tachado = _SECRETO_EN_TEXTO.sub(
        lambda m: f"{m.group('clave')}{m.group('separador')}[REDACTED]", crudo
    )
    return tachado[:_MAX_MENSAJE]


def registrar(
    exc: BaseException,
    *,
    ruta: str,
    metodo: str,
    usuario_id: int | None,
    rol: str | None,
    consorcio_id: int | None,
    db: Session | None = None,
) -> str:
    """Registra `exc` y devuelve el código para mostrarle al usuario.

    Nunca levanta: cualquier problema propio se loguea y se sigue.
    """
    codigo = generar_codigo()
    mensaje = _mensaje_seguro(exc)
    traza = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )[:_MAX_TRAZA]

    # Primero el log, siempre. Si todo lo demás falla, esto queda.
    logger.error(
        "[%s] %s %s -> %s: %s | usuario=%s rol=%s consorcio=%s\n%s",
        codigo, metodo, ruta, type(exc).__name__, mensaje,
        usuario_id, rol, consorcio_id, traza,
    )

    if db is None:
        return codigo

    try:
        db.add(
            ErrorRegistrado(
                codigo=codigo,
                ocurrido_at=datetime.now(timezone.utc),
                ruta=ruta[:255],
                metodo=metodo[:10],
                tipo=type(exc).__name__[:120],
                mensaje=mensaje,
                traza=traza,
                usuario_id=usuario_id,
                rol=rol,
                consorcio_id=consorcio_id,
            )
        )
        db.commit()
    except Exception as propio:  # noqa: BLE001 — nunca puede tapar el original
        logger.error(
            "[%s] no se pudo persistir el error (la traza de arriba es la que "
            "vale): %s", codigo, propio,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 — la sesión ya puede estar inservible
            pass

    return codigo


def purgar_viejos(db: Session, dias: int) -> int:
    """Borra los errores más viejos que `dias`. Devuelve cuántos borró."""
    corte = datetime.now(timezone.utc) - timedelta(days=dias)
    resultado = db.execute(
        delete(ErrorRegistrado).where(ErrorRegistrado.ocurrido_at < corte)
    )
    db.commit()
    return resultado.rowcount or 0
