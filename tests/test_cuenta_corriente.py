"""Tests unitarios del módulo cuenta_corriente (FIFO). Sin HTTP, contra DB en memoria."""
from datetime import date

import pytest

from backend.cuenta_corriente import calcular_estado_cuenta
from backend.models import (
    Departamento,
    EstadoExpensa,
    Expensa,
    MovimientoCuenta,
    TipoMovimiento,
)


@pytest.fixture
def depto(db_empty):
    d = Departamento(id=1, codigo="1A", descripcion="1° A")
    db_empty.add(d)
    db_empty.commit()
    return d


def _mov_expensa(db, depto_id, expensa_id, monto, fecha):
    db.add(
        MovimientoCuenta(
            departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {expensa_id}",
            monto=monto,
            expensa_id=expensa_id,
        )
    )


def _mov_pago(db, depto_id, monto, fecha, comprobante_id=None):
    db.add(
        MovimientoCuenta(
            departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.pago_recibido,
            descripcion="Pago",
            monto=monto,
            comprobante_id=comprobante_id,
        )
    )


def test_pago_exacto_cubre_una_expensa(db_empty, depto):
    e = Expensa(
        id=1,
        departamento_id=depto.id,
        periodo="2026-05",
        monto=1000.0,
        fecha_vencimiento=date(2026, 6, 10),
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
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                fecha_vencimiento=date(2026, 6, 10))
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
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                fecha_vencimiento=date(2026, 6, 10))
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1500.0, date(2026, 6, 1))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == -500.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada


def test_un_pago_cubre_dos_expensas_fifo(db_empty, depto):
    e1 = Expensa(id=1, departamento_id=depto.id, periodo="2026-04", monto=1000.0,
                 fecha_vencimiento=date(2026, 5, 10))
    e2 = Expensa(id=2, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                 fecha_vencimiento=date(2026, 6, 10))
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
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                fecha_vencimiento=date(2026, 6, 10))
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.add(MovimientoCuenta(
        departamento_id=depto.id, fecha=date(2026, 6, 1),
        tipo=TipoMovimiento.nota_credito, descripcion="Bonif.", monto=200.0,
    ))
    db_empty.add(MovimientoCuenta(
        departamento_id=depto.id, fecha=date(2026, 6, 2),
        tipo=TipoMovimiento.nota_debito, descripcion="Ajuste", monto=50.0,
    ))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 850.0
    assert estado.por_expensa[1].monto_pagado == 200.0
    assert estado.por_expensa[1].estado == EstadoExpensa.parcial


def test_expensa_vencida_sin_pago(db_empty, depto):
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-04", monto=1000.0,
                fecha_vencimiento=date(2026, 5, 10))
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
