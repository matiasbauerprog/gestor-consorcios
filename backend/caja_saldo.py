"""Cálculo de saldo de cajas.

Función pura: recibe saldo_inicial + lista de movimientos, devuelve saldo.
Sin side effects, sin DB, fácilmente testeable.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MovimientoSnapshot:
    """Snapshot mínimo de un movimiento para calcular saldo."""
    tipo: str  # "ingreso" | "egreso" | "ajuste"
    monto: float  # siempre positivo para ingreso/egreso; firmado para ajuste


def calcular_saldo(saldo_inicial: float, movimientos: list[MovimientoSnapshot]) -> float:
    """Calcula el saldo actual sumando los movimientos al saldo inicial.

    - ingreso → suma
    - egreso → resta
    - ajuste → suma el monto firmado (puede ser +/-)
    """
    saldo = saldo_inicial
    for m in movimientos:
        if m.tipo == "ingreso":
            saldo += m.monto
        elif m.tipo == "egreso":
            saldo -= m.monto
        elif m.tipo == "ajuste":
            saldo += m.monto  # monto ya firmado
        else:
            raise ValueError(f"Tipo de movimiento desconocido: {m.tipo}")
    return round(saldo, 2)
