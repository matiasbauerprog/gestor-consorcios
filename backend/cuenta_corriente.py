"""Cuenta corriente por departamento — cálculo FIFO de saldo y estado por expensa.

Función pura: lee movimientos y expensas del depto, aplica FIFO en memoria,
retorna saldo total y estado calculado por expensa. No tiene side effects.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Consorcio,
    Departamento,
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
    monto_exigible: float
    interes_acumulado: float
    monto_pagado: float
    monto_pendiente: float
    estado: EstadoExpensa


@dataclass
class EstadoCuenta:
    departamento_id: int
    saldo_total: float
    por_expensa: dict[int, EstadoExpensaCalculado] = field(default_factory=dict)


def monto_exigible_de(expensa: Expensa, recargo_devengado: float = 0.0) -> float:
    """Monto que hay que pagar por esta expensa, sin contar intereses.

    El exigible NO se deduce de la fecha sino del hecho asentado: el primer
    vencimiento más el recargo que efectivamente se devengó contra esta expensa
    (movimientos de tipo `recargo`). Derivarlo de la fecha inventaba un recargo
    fantasma para quien pagaba en término: el saldo de la cuenta sólo suma los
    movimientos, así que un exigible mayor que ellos abría una diferencia sin
    respaldo que la cola FIFO arrastraba al período siguiente.

    Quién decide si el recargo se gana es `recargos._devengar`, que mira la foto
    de la cuenta al día del vencimiento. Acá sólo se lee lo que ya decidió.
    """
    return round(expensa.monto_primer_vencimiento + recargo_devengado, 2)


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
            .where(
                MovimientoCuenta.departamento_id == departamento_id,
                # La foto es a `hoy`: un pago de mañana no cancela nada hoy.
                MovimientoCuenta.fecha <= hoy,
            )
            .order_by(MovimientoCuenta.fecha.asc(), MovimientoCuenta.id.asc())
        ).all()
    )

    # El recargo devengado por expensa sale de los movimientos ya cargados
    # (filtrados a `hoy`): una sola pasada, sin una query por expensa.
    recargos_por_expensa: dict[int, float] = {}
    for m in movimientos:
        if m.tipo == TipoMovimiento.recargo and m.expensa_id is not None:
            recargos_por_expensa[m.expensa_id] = round(
                recargos_por_expensa.get(m.expensa_id, 0.0) + m.monto, 2
            )

    # El techo de cada expensa es el primer vencimiento más el recargo que
    # realmente se asentó contra ella — el mismo hecho que ve el saldo.
    exigibles: dict[int, float] = {
        e.id: monto_exigible_de(e, recargos_por_expensa.get(e.id, 0.0))
        for e in expensas
    }
    pendientes: dict[int, float] = dict(exigibles)
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

    # Tasa punitoria del consorcio del depto, y hasta dónde ya se capitalizó.
    depto = db.get(Departamento, departamento_id)
    consorcio = db.get(Consorcio, depto.consorcio_id) if depto is not None else None
    tasa_mensual_pct = consorcio.tasa_interes_mensual_pct if consorcio is not None else 0.0

    ultima_capitalizacion = db.scalar(
        select(func.max(MovimientoCuenta.fecha)).where(
            MovimientoCuenta.departamento_id == departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.interes_punitorio,
            MovimientoCuenta.fecha <= hoy,
        )
    )

    por_expensa: dict[int, EstadoExpensaCalculado] = {}
    for e in expensas:
        pagado = round(pagado_por_expensa[e.id], 2)
        saldo = round(pendientes[e.id], 2)
        interes = interes_devengado(
            saldo_base=saldo,
            fecha_segundo_vencimiento=e.fecha_segundo_vencimiento,
            fecha_corte=hoy,
            tasa_mensual_pct=tasa_mensual_pct,
            ultima_capitalizacion=ultima_capitalizacion,
        )
        pendiente = round(saldo + interes, 2)
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
            monto_total=exigibles[e.id],
            monto_exigible=exigibles[e.id],
            interes_acumulado=interes,
            monto_pagado=pagado,
            monto_pendiente=pendiente,
            estado=estado,
        )

    return EstadoCuenta(
        departamento_id=departamento_id,
        saldo_total=saldo_total,
        por_expensa=por_expensa,
    )
