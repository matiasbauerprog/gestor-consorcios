"""Blacklist in-memory de JWTs revocados (logout).

Diseño:
- Mapa `jti -> exp_timestamp` (epoch seconds).
- Cada lookup hace un GC barato: descarta entradas vencidas en la propia consulta.
- Cleanup completo opcional vía `_sweep()`; lo dispara `revoke()` cada vez que
  el mapa crece más allá de un umbral, para acotar el peor caso de memoria.

Limitaciones (asumidas por la Opción A del plan):
- No persiste entre reinicios. Tras un restart, los tokens "deslogueados"
  vuelven a ser válidos hasta su `exp` natural.
- No se comparte entre procesos; usarlo con un único worker uvicorn.
"""
from __future__ import annotations

import threading
import time

# Umbral de tamaño antes de hacer un sweep completo. Bajo a propósito para
# pruebas; en prod cualquier valor < ~10k jti está bien (memoria despreciable).
_SWEEP_THRESHOLD = 1024

_blacklist: dict[str, int] = {}
_lock = threading.Lock()


def revoke(jti: str, exp_ts: int) -> None:
    """Marca un jti como inválido hasta `exp_ts` (epoch seconds)."""
    with _lock:
        _blacklist[jti] = exp_ts
        if len(_blacklist) > _SWEEP_THRESHOLD:
            _sweep_locked()


def is_revoked(jti: str) -> bool:
    """True si el jti está revocado y todavía no expiró."""
    now = int(time.time())
    with _lock:
        exp_ts = _blacklist.get(jti)
        if exp_ts is None:
            return False
        if exp_ts <= now:
            # Ya expiró por su cuenta: lo sacamos para no inflar el dict.
            _blacklist.pop(jti, None)
            return False
        return True


def _sweep_locked() -> None:
    """Elimina entradas ya vencidas. Asume que el lock ya está tomado."""
    now = int(time.time())
    vencidos = [j for j, exp in _blacklist.items() if exp <= now]
    for j in vencidos:
        _blacklist.pop(j, None)


def clear() -> None:
    """Hook para tests: vacía la blacklist."""
    with _lock:
        _blacklist.clear()
