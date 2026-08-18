"""Catálogo declarativo de eventos de notificación.

Cada evento se define UNA vez acá: quién lo recibe, qué texto muestra, a
dónde lleva, si manda mail por defecto y —si representa trabajo pendiente—
a qué entidad apunta. El emisor no sabe nada de eventos concretos; lee de
este diccionario. Agregar un aviso nuevo es agregar una entrada acá y una
línea en el lugar donde ocurre la acción.
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from ..models import Rol


class Audiencia(str, Enum):
    DEPARTAMENTO = "departamento"
    ADMINISTRACION = "administracion"


_ROL_POR_AUDIENCIA = {
    Audiencia.DEPARTAMENTO: Rol.departamento,
    Audiencia.ADMINISTRACION: Rol.administracion,
}


@dataclass(frozen=True)
class EventoNotificacion:
    clave: str
    audiencia: Audiencia
    etiqueta: str
    mensaje: Callable[[dict], str]
    link: Callable[[dict], str | None]
    crea_campanita: bool = True
    email_por_defecto: bool = False
    asunto: Callable[[dict], str] | None = None
    cuerpo: Callable[[dict], str] | None = None
    # No-None ⇒ el evento es un pendiente y puede apagarse solo.
    entidad_tipo: str | None = None

    @property
    def puede_mandar_mail(self) -> bool:
        return self.asunto is not None

    @property
    def editable(self) -> bool:
        """False ⇒ el interruptor se muestra pero no se puede tocar.

        Dos casos: el evento nunca manda mail (no hay nada que apagar), o el
        evento es sólo-mail (apagarlo dejaría al usuario sin ningún aviso).
        """
        return self.puede_mandar_mail and self.crea_campanita

    @property
    def motivo_no_editable(self) -> str | None:
        if self.editable:
            return None
        if not self.puede_mandar_mail:
            return "Sólo aparece en la campanita."
        return "Sólo se envía por correo."


def _firma(texto: str) -> str:
    return f"Hola,\n\n{texto}\n\nSaludos,\nAdministración."


# --- Claves ---------------------------------------------------------------

PETICION_ESTADO_CAMBIADO = "peticion_estado_cambiado"
TRABAJO_COMPLETADO = "trabajo_completado"
RESERVA_CONFIRMADA = "reserva_confirmada"
RESERVA_CANCELADA_POR_ADMIN = "reserva_cancelada_por_admin"
COMUNICADO_PUBLICADO = "comunicado_publicado"
EXPENSA_EMITIDA = "expensa_emitida"
COMPROBANTE_APROBADO = "comprobante_aprobado"
COMPROBANTE_RECHAZADO = "comprobante_rechazado"
PETICION_NUEVA = "peticion_nueva"
COMPROBANTE_PRESENTADO = "comprobante_presentado"
PETICION_BORRADA_POR_DEPTO = "peticion_borrada_por_depto"
RESERVA_NUEVA_DE_DEPTO = "reserva_nueva_de_depto"


def _msg_peticion_estado(c: dict) -> str:
    # El valor CRUDO del estado va en el texto: tests/test_trabajos.py filtra
    # por "convertida_en_trabajo". Cambiar esto rompe ese test, a propósito.
    return f"Tu petición '{c['titulo']}' cambió de estado a: {c['estado']}."


def _msg_reserva_confirmada(c: dict) -> str:
    texto = f"Tu reserva de {c['amenity']} para el {c['fecha']} fue confirmada."
    if c.get("monto") is not None:
        texto += f"\nSe cargó ${c['monto']:.2f} a tu cuenta corriente."
    return texto


def _msg_reserva_cancelada(c: dict) -> str:
    texto = f"La administración canceló tu reserva de {c['amenity']} del {c['fecha']}."
    if c.get("monto_reversado") is not None:
        texto += f" Se reversó el cargo de ${c['monto_reversado']:.2f}."
    return texto


def _msg_comprobante_rechazado(c: dict) -> str:
    texto = f"Tu comprobante de pago por ${c['monto']:.2f} fue rechazado."
    if c.get("motivo"):
        texto += f" Motivo: {c['motivo']}"
    return texto


_EVENTOS = [
    # --- Al departamento --------------------------------------------------
    EventoNotificacion(
        clave=PETICION_ESTADO_CAMBIADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Cambia el estado de mi petición",
        mensaje=_msg_peticion_estado,
        link=lambda c: "/peticiones",
        email_por_defecto=True,
        asunto=lambda c: f"Tu petición #{c['peticion_id']} fue actualizada",
        cuerpo=lambda c: _firma(_msg_peticion_estado(c)),
    ),
    EventoNotificacion(
        clave=TRABAJO_COMPLETADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Se completa el trabajo de mi petición",
        mensaje=lambda c: f"El trabajo de tu petición '{c['titulo']}' fue completado.",
        link=lambda c: "/peticiones",
        asunto=lambda c: "El trabajo de tu petición fue completado",
        cuerpo=lambda c: _firma(
            f"El trabajo de tu petición '{c['titulo']}' fue completado."
        ),
    ),
    EventoNotificacion(
        clave=RESERVA_CONFIRMADA,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Confirmación de mi reserva",
        mensaje=_msg_reserva_confirmada,
        link=lambda c: "/reservas",
        # Sin campanita: el usuario acaba de ver la confirmación en pantalla.
        crea_campanita=False,
        email_por_defecto=True,
        asunto=lambda c: f"Reserva confirmada: {c['amenity']}",
        cuerpo=lambda c: f"{_msg_reserva_confirmada(c)}\n\nSaludos,\nAdministración.",
    ),
    EventoNotificacion(
        clave=RESERVA_CANCELADA_POR_ADMIN,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="La administración cancela mi reserva",
        mensaje=_msg_reserva_cancelada,
        link=lambda c: "/reservas",
        email_por_defecto=True,
        asunto=lambda c: f"Tu reserva de {c['amenity']} fue cancelada",
        cuerpo=lambda c: _firma(_msg_reserva_cancelada(c)),
    ),
    EventoNotificacion(
        clave=COMUNICADO_PUBLICADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Se publica un comunicado",
        mensaje=lambda c: f"Nuevo comunicado: {c['titulo']}",
        link=lambda c: "/comunicados",
        email_por_defecto=True,
        asunto=lambda c: f"Nuevo comunicado: {c['titulo']}",
        cuerpo=lambda c: _firma(
            f"Se publicó un comunicado nuevo: {c['titulo']}\n\n{c['cuerpo']}"
        ),
    ),
    EventoNotificacion(
        clave=EXPENSA_EMITIDA,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Se emite mi expensa del período",
        mensaje=lambda c: (
            f"Ya está disponible tu expensa del período {c['periodo']}: "
            f"${c['monto']:.2f}, vence el {c['vencimiento']}."
        ),
        link=lambda c: "/expensas",
        email_por_defecto=True,
        asunto=lambda c: f"Expensa {c['periodo']} disponible",
        cuerpo=lambda c: _firma(
            f"Ya está disponible tu expensa del período {c['periodo']} por "
            f"${c['monto']:.2f}, con vencimiento el {c['vencimiento']}."
        ),
    ),
    EventoNotificacion(
        clave=COMPROBANTE_APROBADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Me aprueban un comprobante de pago",
        mensaje=lambda c: f"Tu comprobante de pago por ${c['monto']:.2f} fue aprobado.",
        link=lambda c: "/comprobantes",
        asunto=lambda c: "Tu comprobante de pago fue aprobado",
        cuerpo=lambda c: _firma(
            f"Tu comprobante de pago por ${c['monto']:.2f} fue aprobado."
        ),
    ),
    EventoNotificacion(
        clave=COMPROBANTE_RECHAZADO,
        audiencia=Audiencia.DEPARTAMENTO,
        etiqueta="Me rechazan un comprobante de pago",
        mensaje=_msg_comprobante_rechazado,
        link=lambda c: "/comprobantes",
        email_por_defecto=True,
        asunto=lambda c: "Tu comprobante de pago fue rechazado",
        cuerpo=lambda c: _firma(_msg_comprobante_rechazado(c)),
    ),
    # --- A la administración ----------------------------------------------
    EventoNotificacion(
        clave=PETICION_NUEVA,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento crea una petición",
        mensaje=lambda c: f"{c['codigo_depto']} creó la petición '{c['titulo']}'.",
        link=lambda c: "/peticiones",
        entidad_tipo="peticion",
        asunto=lambda c: f"Nueva petición de {c['codigo_depto']}",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} creó la petición '{c['titulo']}'."
        ),
    ),
    EventoNotificacion(
        clave=COMPROBANTE_PRESENTADO,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento presenta un comprobante",
        mensaje=lambda c: (
            f"{c['codigo_depto']} presentó un comprobante por ${c['monto']:.2f}."
        ),
        link=lambda c: "/comprobantes",
        entidad_tipo="comprobante",
        asunto=lambda c: f"Comprobante presentado por {c['codigo_depto']}",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} presentó un comprobante de pago por "
            f"${c['monto']:.2f} y está esperando verificación."
        ),
    ),
    EventoNotificacion(
        clave=PETICION_BORRADA_POR_DEPTO,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento borra su petición",
        mensaje=lambda c: f"{c['codigo_depto']} borró su petición '{c['titulo']}'.",
        link=lambda c: "/peticiones",
        asunto=lambda c: f"{c['codigo_depto']} borró una petición",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} borró su petición '{c['titulo']}'."
        ),
    ),
    EventoNotificacion(
        clave=RESERVA_NUEVA_DE_DEPTO,
        audiencia=Audiencia.ADMINISTRACION,
        etiqueta="Un departamento reserva un amenity",
        mensaje=lambda c: (
            f"{c['codigo_depto']} reservó {c['amenity']} para el {c['fecha']}."
        ),
        link=lambda c: "/reservas",
        asunto=lambda c: f"Nueva reserva de {c['codigo_depto']}",
        cuerpo=lambda c: _firma(
            f"{c['codigo_depto']} reservó {c['amenity']} para el {c['fecha']}."
        ),
    ),
]

CATALOGO: dict[str, EventoNotificacion] = {ev.clave: ev for ev in _EVENTOS}


def evento(clave: str) -> EventoNotificacion:
    """Devuelve el evento. `KeyError` si la clave no existe.

    Explota a propósito: las claves son constantes de este módulo, así que
    una clave desconocida es un bug de programación, no un dato del usuario.
    """
    return CATALOGO[clave]


def eventos_para_rol(rol: Rol) -> list[EventoNotificacion]:
    """Eventos que un usuario de ese rol puede llegar a recibir."""
    return [
        ev for ev in _EVENTOS
        if _ROL_POR_AUDIENCIA.get(ev.audiencia) == rol
    ]
