"""Sistema de notificaciones.

`emitir` y `resolver_pendiente` son la única API pública. Todo lo demás
—catálogo, destinatarios, preferencias, correo— es interno del paquete.
"""
from .emisor import emitir, resolver_pendiente

__all__ = ["emitir", "resolver_pendiente"]
