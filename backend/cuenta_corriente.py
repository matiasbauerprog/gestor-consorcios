"""Cuenta corriente por departamento — cálculo FIFO de saldo y estado por expensa.

Función pura: lee movimientos y expensas del depto, aplica FIFO en memoria,
retorna saldo total y estado calculado por expensa. No tiene side effects.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    EstadoExpensa,
    Expensa,
    MovimientoCuenta,
    TIPOS_CREDITO,
    TIPOS_DEBITO,
    TipoMovimiento,
)


@dataclass
class EstadoExpensaCalculado:
    expensa_id: int
    monto_total: float
    monto_pagado: float
    monto_pendiente: float
    estado: EstadoExpensa


@dataclass
class EstadoCuenta:
    departamento_id: int
    saldo_total: float
    por_expensa: dict[int, EstadoExpensaCalculado] = field(default_factory=dict)


def calcular_estado_cuenta(
    db: Session, departamento_id: int, hoy: date | None = None
) -> EstadoCuenta:
    hoy = hoy or date.today()

    expensas = list(
        db.scalars(
            select(Expensa)
            .where(Expensa.departamento_id == departamento_id)
            .order_by(Expensa.fecha_vencimiento.asc(), Expensa.id.asc())
        ).all()
    )

    movimientos = list(
        db.scalars(
            select(MovimientoCuenta)
            .where(MovimientoCuenta.departamento_id == departamento_id)
            .order_by(MovimientoCuenta.fecha.asc(), MovimientoCuenta.id.asc())
        ).all()
    )

    pendientes: dict[int, float] = {e.id: e.monto for e in expensas}
    pagado_por_expensa: dict[int, float] = {e.id: 0.0 for e in expensas}

    saldo_total = 0.0
    credito_disponible = 0.0

    for m in movimientos:
        if m.tipo in TIPOS_DEBITO:
            saldo_total += m.monto
        else:
            saldo_total -= m.monto
            credito_disponible += m.monto

    # FIFO: el crédito acumulado se aplica a las expensas más viejas.
    for e in expensas:
        if credito_disponible <= 0:
            break
        cubierto = min(credito_disponible, pendientes[e.id])
        pagado_por_expensa[e.id] = cubierto
        pendientes[e.id] -= cubierto
        credito_disponible -= cubierto

    por_expensa: dict[int, EstadoExpensaCalculado] = {}
    for e in expensas:
        pagado = pagado_por_expensa[e.id]
        pendiente = pendientes[e.id]
        if pendiente <= 0.001:
            estado = EstadoExpensa.pagada
        elif pagado > 0:
            estado = EstadoExpensa.parcial
        elif e.fecha_vencimiento < hoy:
            estado = EstadoExpensa.vencida
        else:
            estado = EstadoExpensa.pendiente
        por_expensa[e.id] = EstadoExpensaCalculado(
            expensa_id=e.id,
            monto_total=e.monto,
            monto_pagado=pagado,
            monto_pendiente=pendiente,
            estado=estado,
        )

    return EstadoCuenta(
        departamento_id=departamento_id,
        saldo_total=saldo_total,
        por_expensa=por_expensa,
    )
