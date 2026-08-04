"""Tests unitarios del módulo cuenta_corriente (FIFO). Sin HTTP, contra DB en memoria."""
from datetime import date

import pytest

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


def test_exigible_antes_del_primer_vencimiento():
    assert monto_exigible_de(_expensa_simple(), date(2026, 6, 5)) == 1000.0


def test_exigible_el_dia_del_primer_vencimiento_todavia_es_el_primero():
    assert monto_exigible_de(_expensa_simple(), date(2026, 6, 10)) == 1000.0


def test_exigible_pasado_el_primer_vencimiento_es_el_segundo():
    assert monto_exigible_de(_expensa_simple(), date(2026, 6, 11)) == 1070.0


def test_exigible_pasado_el_segundo_vencimiento_sigue_siendo_el_segundo():
    # El interés se suma aparte, no infla el exigible.
    assert monto_exigible_de(_expensa_simple(), date(2026, 7, 30)) == 1070.0


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
