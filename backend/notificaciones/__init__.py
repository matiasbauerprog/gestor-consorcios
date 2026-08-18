"""Sistema de notificaciones.

`emitir` y `resolver_pendiente` son la única API pública. Los helpers de
`legacy` son transitorios y los borra la tarea que migra los cuatro eventos
originales al catálogo.
"""
from .legacy import (  # noqa: F401  — transitorio, se borra en el Task 6
    crear_notificacion,
    notificar_cambio_estado_peticion,
    notificar_reserva_cancelada_por_admin,
    notificar_reserva_creada,
)

__all__ = [
    "crear_notificacion",
    "notificar_cambio_estado_peticion",
    "notificar_reserva_cancelada_por_admin",
    "notificar_reserva_creada",
]
