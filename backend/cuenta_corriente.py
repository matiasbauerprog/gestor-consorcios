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


def monto_exigible_de(expensa: Expensa, hoy: date) -> float:
    """Monto que hay que pagar hoy por esta expensa, sin contar intereses.

    Pasado el primer vencimiento pasa a regir el segundo (que incluye el
    recargo). El día exacto del vencimiento todavía rige el primero.
    """
    if hoy <= expensa.fecha_primer_vencimiento:
        return expensa.monto_primer_vencimiento
    return expensa.monto_segundo_vencimiento


def interes_devengado(
    saldo_base: float,
    fecha_segundo_vencimiento: date,
    fecha_corte: date,
    tasa_mensual_pct: float,
    ultima_capitalizacion: date | None,
) -> float:
    """Interés punitorio sobre `saldo_base` por el tramo de mora todavía NO
    capitalizado.

    El cierre de período capitaliza intereses como movimientos de cuenta. Si
    contáramos la mora desde el segundo vencimiento sin mirar esos movimientos,
    cada cierre volvería a cobrar lo que el anterior ya cobró.
    """
    if saldo_base <= 0.005:
        return 0.0
    if fecha_segundo_vencimiento >= fecha_corte:
        return 0.0
    desde = fecha_segundo_vencimiento
    if ultima_capitalizacion is not None and ultima_capitalizacion > desde:
        desde = ultima_capitalizacion
    dias_mora = (fecha_corte - desde).days
    if dias_mora <= 0:
        return 0.0
    tasa_diaria = tasa_mensual_pct / 100 / 30
    return round(saldo_base * tasa_diaria * dias_mora, 2)


def calcular_estado_cuenta(
    db: Session, departamento_id: int, hoy: date | None = None
) -> EstadoCuenta:
    hoy = hoy or date.today()

    expensas = list(
        db.scalars(
            select(Expensa)
            .where(Expensa.departamento_id == departamento_id)
            .order_by(Expensa.fecha_primer_vencimiento.asc(), Expensa.id.asc())
        ).all()
    )

    movimientos = list(
        db.scalars(
            select(MovimientoCuenta)
            .where(MovimientoCuenta.departamento_id == departamento_id)
            .order_by(MovimientoCuenta.fecha.asc(), MovimientoCuenta.id.asc())
        ).all()
    )

    pendientes: dict[int, float] = {e.id: e.monto_primer_vencimiento for e in expensas}
    pagado_por_expensa: dict[int, float] = {e.id: 0.0 for e in expensas}

    saldo_total = 0.0
    credito_disponible = 0.0

    for m in movimientos:
        if m.tipo in TIPOS_DEBITO:
            saldo_total += m.monto
        else:
            saldo_total -= m.monto
            credito_disponible += m.monto

    saldo_total = round(saldo_total, 2)
    credito_disponible = round(credito_disponible, 2)
    if abs(saldo_total) < 0.005:
        saldo_total = 0.0
    if abs(credito_disponible) < 0.005:
        credito_disponible = 0.0

    # FIFO: el crédito acumulado se aplica a las expensas más viejas.
    for e in expensas:
        if credito_disponible <= 0.005:
            break
        cubierto = min(credito_disponible, pendientes[e.id])
        cubierto = round(cubierto, 2)
        pagado_por_expensa[e.id] = round(pagado_por_expensa[e.id] + cubierto, 2)
        pendientes[e.id] = round(pendientes[e.id] - cubierto, 2)
        credito_disponible = round(credito_disponible - cubierto, 2)

    por_expensa: dict[int, EstadoExpensaCalculado] = {}
    for e in expensas:
        pagado = round(pagado_por_expensa[e.id], 2)
        pendiente = round(pendientes[e.id], 2)
        if pendiente <= 0.005:
            estado = EstadoExpensa.pagada
            pendiente = 0.0
        elif pagado > 0:
            estado = EstadoExpensa.parcial
        elif e.fecha_primer_vencimiento < hoy:
            estado = EstadoExpensa.vencida
        else:
            estado = EstadoExpensa.pendiente
        por_expensa[e.id] = EstadoExpensaCalculado(
            expensa_id=e.id,
            monto_total=e.monto_primer_vencimiento,
            monto_pagado=pagado,
            monto_pendiente=pendiente,
            estado=estado,
        )

    return EstadoCuenta(
        departamento_id=departamento_id,
        saldo_total=saldo_total,
        por_expensa=por_expensa,
    )
