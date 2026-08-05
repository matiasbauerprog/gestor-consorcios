"""Tests unitarios del módulo cuenta_corriente (FIFO). Sin HTTP, contra DB en memoria."""
from datetime import date

import pytest
from sqlalchemy import select

from backend.cuenta_corriente import calcular_estado_cuenta
from backend.models import (
    Administracion,
    Consorcio,
    Departamento,
    EstadoExpensa,
    Expensa,
    MovimientoCuenta,
    TipoMovimiento,
)


@pytest.fixture
def depto(db_empty):
    # Setup mínimo para satisfacer FK con foreign_keys=ON en tests.
    db_empty.add(Administracion(
        id=1, razon_social="Admin cta cte", cuit="30-11-1",
        email_contacto="a@a.com",
    ))
    db_empty.flush()
    db_empty.add(Consorcio(
        id=1, administracion_id=1, nombre="Cta cte test",
        consorcio_domicilio="d", consorcio_cuit="c",
        admin_nombre="n", admin_domicilio="d", admin_email="e@e.com",
        admin_telefono="t", admin_cuit="c", admin_rpa="0",
        admin_situacion_fiscal="M", banco_titular="t", banco_nombre="n",
        banco_numero_cuenta="0", banco_cbu="0" * 22,
    ))
    db_empty.flush()
    d = Departamento(consorcio_id=1, id=1, codigo="1A", descripcion="1° A")
    db_empty.add(d)
    db_empty.commit()
    return d


def _mov_expensa(db, depto_id, expensa_id, monto, fecha):
    db.add(
        MovimientoCuenta(consorcio_id=1, departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {expensa_id}",
            monto=monto,
            expensa_id=expensa_id,
        )
    )


def _mov_recargo(db, depto_id, expensa_id, monto, fecha):
    """El recargo que `recargos._devengar` asienta el día del 1er vencimiento.

    El exigible sale de este movimiento, no de la fecha: sin él la expensa
    exige sólo el primer vencimiento.
    """
    db.add(
        MovimientoCuenta(consorcio_id=1, departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.recargo,
            descripcion=f"Recargo por mora — expensa {expensa_id}",
            monto=monto,
            expensa_id=expensa_id,
        )
    )


def _mov_pago(db, depto_id, monto, fecha, comprobante_id=None):
    db.add(
        MovimientoCuenta(consorcio_id=1, departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.pago_recibido,
            descripcion="Pago",
            monto=monto,
            comprobante_id=comprobante_id,
        )
    )


def test_pago_exacto_cubre_una_expensa(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1,
        departamento_id=depto.id,
        periodo="2026-05",
        monto_primer_vencimiento=1000.0,
        fecha_primer_vencimiento=date(2026, 6, 10),
        monto_segundo_vencimiento=1070.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        saldo_anterior=0.0,
    )
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 1))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))

    assert estado.saldo_total == 0.0
    assert estado.por_expensa[1].monto_pagado == 1000.0
    assert estado.por_expensa[1].monto_pendiente == 0.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada


def test_pago_parcial(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05", monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10), monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20), saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 600.0, date(2026, 6, 1))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 400.0
    assert estado.por_expensa[1].monto_pagado == 600.0
    assert estado.por_expensa[1].monto_pendiente == 400.0
    assert estado.por_expensa[1].estado == EstadoExpensa.parcial


def test_sobre_pago_genera_credito(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05", monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10), monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20), saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1500.0, date(2026, 6, 1))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == -500.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada


def test_un_pago_cubre_dos_expensas_fifo(db_empty, depto):
    e1 = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-04", monto_primer_vencimiento=1000.0,
                 fecha_primer_vencimiento=date(2026, 5, 10), monto_segundo_vencimiento=1070.0,
                 fecha_segundo_vencimiento=date(2026, 5, 20), saldo_anterior=0.0)
    e2 = Expensa(consorcio_id=1, id=2, departamento_id=depto.id, periodo="2026-05", monto_primer_vencimiento=1000.0,
                 fecha_primer_vencimiento=date(2026, 6, 10), monto_segundo_vencimiento=1070.0,
                 fecha_segundo_vencimiento=date(2026, 6, 20), saldo_anterior=0.0)
    db_empty.add_all([e1, e2])
    _mov_expensa(db_empty, depto.id, e1.id, 1000.0, date(2026, 4, 10))
    _mov_expensa(db_empty, depto.id, e2.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1500.0, date(2026, 6, 1))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 500.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada
    assert estado.por_expensa[2].estado == EstadoExpensa.parcial
    # No hay movimiento de recargo contra e1, así que su exigible es el primer
    # vencimiento (1000): el recargo se gana asentándolo, no dejando pasar la
    # fecha. El pago de 1500 cubre e1 y deja 500 para e2. El saldo (500) y la
    # suma de pendientes coinciden, que es la propiedad que antes se rompía.
    assert estado.por_expensa[2].monto_pendiente == 500.0


def test_nota_credito_y_debito(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05", monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10), monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20), saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.add(MovimientoCuenta(consorcio_id=1, departamento_id=depto.id, fecha=date(2026, 6, 1),
        tipo=TipoMovimiento.nota_credito, descripcion="Bonif.", monto=200.0,
    ))
    db_empty.add(MovimientoCuenta(consorcio_id=1, departamento_id=depto.id, fecha=date(2026, 6, 2),
        tipo=TipoMovimiento.nota_debito, descripcion="Ajuste", monto=50.0,
    ))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 850.0
    assert estado.por_expensa[1].monto_pagado == 200.0
    assert estado.por_expensa[1].estado == EstadoExpensa.parcial


def test_expensa_vencida_sin_pago(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-04", monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 5, 10), monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 5, 20), saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 4, 10))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.por_expensa[1].estado == EstadoExpensa.vencida
    assert estado.saldo_total == 1000.0


def test_depto_sin_movimientos(db_empty, depto):
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 0.0
    assert estado.por_expensa == {}


from backend.cuenta_corriente import interes_devengado, monto_exigible_de


def _expensa_simple():
    return Expensa(
        consorcio_id=1, id=99, departamento_id=1, periodo="2026-05",
        monto_primer_vencimiento=1000.0,
        fecha_primer_vencimiento=date(2026, 6, 10),
        monto_segundo_vencimiento=1070.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        saldo_anterior=0.0,
    )


def test_exigible_sin_recargo_devengado_es_el_primer_vencimiento():
    # Ya no depende de la fecha: mientras no haya recargo asentado, se exige el
    # primer vencimiento, pase el tiempo que pase.
    assert monto_exigible_de(_expensa_simple()) == 1000.0


def test_exigible_con_el_recargo_devengado_es_el_segundo():
    assert monto_exigible_de(_expensa_simple(), 70.0) == 1070.0


def test_el_exigible_no_incluye_intereses():
    # El interés se suma aparte, no infla el exigible.
    assert monto_exigible_de(_expensa_simple(), 70.0) == 1070.0


def test_interes_cero_antes_del_segundo_vencimiento():
    assert interes_devengado(
        saldo_base=1070.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 6, 15),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=None,
    ) == 0.0


def test_interes_cero_si_no_hay_saldo():
    assert interes_devengado(
        saldo_base=0.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=None,
    ) == 0.0


def test_interes_proporcional_a_los_dias_de_mora():
    # tasa diaria = 3 / 100 / 30 = 0.001 ; 30 días ; 1000 * 0.001 * 30 = 30.0
    assert interes_devengado(
        saldo_base=1000.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=None,
    ) == 30.0


def test_interes_arranca_desde_la_ultima_capitalizacion():
    # Ya se capitalizó hasta el 10/07: sólo se cobran los 10 días siguientes.
    assert interes_devengado(
        saldo_base=1000.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=date(2026, 7, 10),
    ) == 10.0


def test_interes_cero_si_ya_se_capitalizo_todo():
    assert interes_devengado(
        saldo_base=1000.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=date(2026, 7, 20),
    ) == 0.0


def test_pago_del_primer_vencimiento_tarde_no_cancela_la_expensa(db_empty, depto):
    """El bug crítico: pagar $1000 después del 1er venc dejaba la expensa
    `pagada` y se perdía el recargo de $70."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    # El devengamiento asienta el recargo el día del vencimiento, antes del pago.
    _mov_recargo(db_empty, depto.id, e.id, 70.0, date(2026, 6, 10))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 15))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 15))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1070.0
    assert calc.interes_acumulado == 0.0
    assert calc.monto_pendiente == 70.0
    assert calc.estado == EstadoExpensa.parcial


def test_expensa_impaga_pasado_el_segundo_vencimiento_acumula_interes(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    # Impaga al vencimiento: el recargo se devengó y la base de la mora es 1070.
    _mov_recargo(db_empty, depto.id, e.id, 70.0, date(2026, 6, 10))
    db_empty.commit()

    # 10 días de mora, tasa default 3% mensual -> 1070 * 0.001 * 10 = 10.70
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1070.0
    assert calc.interes_acumulado == 10.70
    assert calc.monto_pendiente == 1080.70
    assert calc.estado == EstadoExpensa.vencida


def test_interes_no_se_recobra_si_ya_fue_capitalizado(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_recargo(db_empty, depto.id, e.id, 70.0, date(2026, 6, 10))
    db_empty.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=depto.id, fecha=date(2026, 6, 25),
        tipo=TipoMovimiento.interes_punitorio, descripcion="Intereses",
        monto=5.35,
    ))
    db_empty.commit()

    # Capitalizado hasta el 25/06 -> sólo se devengan los 5 días siguientes.
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))

    assert estado.por_expensa[1].interes_acumulado == 5.35


def test_un_pago_posterior_a_hoy_no_cancela_la_expensa(db_empty, depto):
    """La foto de la cuenta a una fecha no puede incluir pagos del futuro."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 25))
    db_empty.commit()

    # Al 5 de junio ese pago todavía no ocurrió.
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 1000.0
    assert estado.por_expensa[1].monto_pagado == 0.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pendiente

    # Al 30 de junio sí.
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))
    assert estado.por_expensa[1].monto_pagado == 1000.0


def test_una_capitalizacion_posterior_a_hoy_no_recorta_el_interes(db_empty, depto):
    """El interés al 30/06 no puede descontarse por un cierre del 10/07."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_recargo(db_empty, depto.id, e.id, 70.0, date(2026, 6, 10))
    db_empty.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=depto.id, fecha=date(2026, 7, 10),
        tipo=TipoMovimiento.interes_punitorio, descripcion="Intereses", monto=99.0,
    ))
    db_empty.commit()

    # 10 días de mora al 30/06: 1070 * 0.001 * 10 = 10.70
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))
    assert estado.por_expensa[1].interes_acumulado == 10.70


def test_antes_del_vencimiento_el_exigible_sigue_siendo_el_primero(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1000.0
    assert calc.monto_pendiente == 1000.0
    assert calc.estado == EstadoExpensa.pendiente


# === Regresión del recargo fantasma ===
#
# El exigible se deducía de la fecha: pasado el 1er vencimiento devolvía el 2do
# sin mirar si algo se debía. A quien pagaba en término le aparecían 70 pesos
# sin movimiento que los respalde, la cola FIFO se los cobraba al mes siguiente
# y en el vencimiento de ESE mes el recargo se volvía real. El error crecía por
# período. Ahora el exigible sale del movimiento de recargo efectivamente
# asentado, el mismo hecho del que sale el saldo.

def test_pagada_en_termino_no_exige_el_recargo_despues_del_vencimiento(db_empty, depto):
    """El bug: 1000/1070 con 1er venc 10/06, pagada el 05/06, leída el 15/06."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 5))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 15))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1000.0
    assert calc.monto_pendiente == 0.0
    assert calc.interes_acumulado == 0.0
    assert calc.estado == EstadoExpensa.pagada
    assert estado.saldo_total == 0.0


def test_impaga_con_el_recargo_asentado_si_exige_el_segundo_vencimiento(db_empty, depto):
    """La contracara: si el recargo se devengó, el exigible lo incluye."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_recargo(db_empty, depto.id, e.id, 70.0, date(2026, 6, 10))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 15))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1070.0
    assert calc.monto_pendiente == 1070.0
    assert calc.estado == EstadoExpensa.vencida
    # Saldo y pendiente empatan: no hay diferencia sin movimiento que la respalde.
    assert estado.saldo_total == 1070.0


def test_dos_meses_pagados_en_termino_no_acumulan_ningun_recargo(db_empty, depto):
    """El escenario que componía: el fantasma de junio encabezaba el FIFO, se
    comía el pago puntual de julio, y en el vencimiento de julio el
    devengamiento emitía un recargo REAL de 70 sobre un depto al día."""
    from backend.recargos import devengar_recargos_y_marcar

    junio = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                    monto_primer_vencimiento=1000.0,
                    fecha_primer_vencimiento=date(2026, 6, 10),
                    monto_segundo_vencimiento=1070.0,
                    fecha_segundo_vencimiento=date(2026, 6, 20),
                    saldo_anterior=0.0)
    julio = Expensa(consorcio_id=1, id=2, departamento_id=depto.id, periodo="2026-06",
                    monto_primer_vencimiento=1000.0,
                    fecha_primer_vencimiento=date(2026, 7, 10),
                    monto_segundo_vencimiento=1070.0,
                    fecha_segundo_vencimiento=date(2026, 7, 20),
                    saldo_anterior=0.0)
    db_empty.add_all([junio, julio])
    _mov_expensa(db_empty, depto.id, junio.id, 1000.0, date(2026, 6, 1))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 5))
    _mov_expensa(db_empty, depto.id, julio.id, 1000.0, date(2026, 7, 1))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 7, 5))
    db_empty.commit()

    # El devengamiento corre en cada lectura: acá, después de ambos vencimientos.
    devengar_recargos_y_marcar(db_empty, depto.id, hoy=date(2026, 7, 31))
    db_empty.commit()

    recargos = db_empty.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.departamento_id == depto.id,
            MovimientoCuenta.tipo == TipoMovimiento.recargo,
        )
    ).all()
    assert recargos == []

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 7, 31))
    assert estado.saldo_total == 0.0
    for expensa_id in (1, 2):
        calc = estado.por_expensa[expensa_id]
        assert calc.monto_exigible == 1000.0
        assert calc.monto_pendiente == 0.0
        assert calc.interes_acumulado == 0.0
        assert calc.estado == EstadoExpensa.pagada
