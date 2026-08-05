"""Tests del devengamiento del recargo por mora. Sin HTTP, contra DB en memoria."""
from datetime import date

import pytest
from sqlalchemy import select

from backend.models import (
    Administracion,
    Consorcio,
    Departamento,
    Expensa,
    MovimientoCuenta,
    TipoMovimiento,
)
# `_devengar` es privado a propósito: el único punto de entrada de producción
# es `devengar_recargos_y_marcar`. Los tests que necesitan ver los movimientos
# emitidos llaman al helper privado en vez de exponer un atajo público que un
# read path futuro podría tomar por error (perdiendo la marca `recargo_evaluado`).
from backend.recargos import _devengar, devengar_recargos_y_marcar


@pytest.fixture
def depto(db_empty):
    db_empty.add(Administracion(
        id=1, razon_social="Admin recargos", cuit="30-11-1",
        email_contacto="a@a.com",
    ))
    db_empty.flush()
    db_empty.add(Consorcio(
        id=1, administracion_id=1, nombre="Recargos test",
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


def _expensa(db, expensa_id, venc1, venc2, monto1=1000.0, monto2=1070.0):
    e = Expensa(consorcio_id=1, id=expensa_id, departamento_id=1,
                periodo="2026-05", monto_primer_vencimiento=monto1,
                fecha_primer_vencimiento=venc1,
                monto_segundo_vencimiento=monto2,
                fecha_segundo_vencimiento=venc2, saldo_anterior=0.0)
    db.add(e)
    db.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=date(2026, 5, 1),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa",
        monto=monto1, expensa_id=expensa_id,
    ))
    db.commit()
    return e


def _pago(db, monto, fecha):
    db.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=fecha,
        tipo=TipoMovimiento.pago_recibido, descripcion="Pago", monto=monto,
    ))
    db.commit()


def test_expensa_impaga_al_vencimiento_devenga_recargo(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))

    nuevos = _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0]
    db_empty.commit()

    assert len(nuevos) == 1
    assert nuevos[0].monto == 70.0
    assert nuevos[0].tipo == TipoMovimiento.recargo
    assert nuevos[0].expensa_id == 1
    # Se fecha el día del vencimiento, que es cuando se ganó.
    assert nuevos[0].fecha == date(2026, 6, 10)


def test_expensa_pagada_antes_del_vencimiento_no_devenga(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _pago(db_empty, 1000.0, date(2026, 6, 5))

    assert _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0] == []


def test_la_expensa_que_no_devenga_queda_marcada_como_evaluada(db_empty, depto):
    """El caso caro: pagada a tiempo, no emite nada, y aun así no se vuelve
    a evaluar. Sin la marca, cada lectura pagaba un `calcular_estado_cuenta`
    entero por esta expensa, para siempre."""
    e = _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _pago(db_empty, 1000.0, date(2026, 6, 5))

    assert _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0] == []
    db_empty.commit()

    assert e.recargo_evaluado is True
    # Y ya no es candidata: la segunda pasada no la mira siquiera.
    assert devengar_recargos_y_marcar(db_empty, 1, hoy=date(2026, 6, 30)) is False


def test_sin_recargo_configurado_tambien_queda_evaluada(db_empty, depto):
    e = _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20),
                 monto1=1000.0, monto2=1000.0)

    assert _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0] == []
    db_empty.commit()

    assert e.recargo_evaluado is True
    assert devengar_recargos_y_marcar(db_empty, 1, hoy=date(2026, 6, 30)) is False


def test_marcar_reporta_que_hay_algo_para_commitear(db_empty, depto):
    """`devengar_recargos_y_marcar` es True aunque no se emita movimiento:
    la marca es una escritura y el llamador tiene que commitearla."""
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _pago(db_empty, 1000.0, date(2026, 6, 5))

    assert devengar_recargos_y_marcar(db_empty, 1, hoy=date(2026, 6, 15)) is True
    # Sin expensas vencidas nuevas no hay nada que persistir.
    db_empty.commit()
    assert devengar_recargos_y_marcar(db_empty, 1, hoy=date(2026, 6, 15)) is False


def test_una_expensa_ya_recargada_sin_marca_no_emite_segundo_movimiento(db_empty, depto):
    """Simula el estado post-migración: el recargo existe pero
    `recargo_evaluado` migró en 0. La guarda `ya_recargadas` lo cubre."""
    e = _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0]
    db_empty.commit()

    # Volvemos la expensa al estado que deja el ALTER TABLE.
    e.recargo_evaluado = False
    db_empty.commit()

    assert _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0] == []
    db_empty.commit()

    recargos = db_empty.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.tipo == TipoMovimiento.recargo
        )
    ).all()
    assert len(recargos) == 1
    assert e.recargo_evaluado is True


def test_pagar_despues_del_vencimiento_no_borra_el_recargo(db_empty, depto):
    """El recargo se ganó el 10/06; pagar el 12/06 no lo revierte."""
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _pago(db_empty, 1000.0, date(2026, 6, 12))

    nuevos = _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0]
    assert len(nuevos) == 1
    assert nuevos[0].monto == 70.0


def test_no_devenga_antes_del_vencimiento(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))

    assert _devengar(db_empty, 1, hoy=date(2026, 6, 10))[0] == []


def test_es_idempotente(db_empty, depto):
    e = _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))

    primera = _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0]
    db_empty.commit()
    segunda = _devengar(db_empty, 1, hoy=date(2026, 6, 20))[0]
    db_empty.commit()

    assert len(primera) == 1
    assert segunda == []
    # La que sí devengó también queda marcada: la segunda pasada ni la mira.
    assert e.recargo_evaluado is True
    assert devengar_recargos_y_marcar(db_empty, 1, hoy=date(2026, 6, 30)) is False


def test_sin_recargo_configurado_no_emite_movimiento(db_empty, depto):
    """monto_segundo == monto_primer: el consorcio no cobra recargo."""
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20),
             monto1=1000.0, monto2=1000.0)

    assert _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0] == []


def test_el_saldo_vuelve_a_coincidir_con_el_pendiente(db_empty, depto):
    """Es el punto de todo esto: saldo_total y la suma de pendientes empatan."""
    from backend.cuenta_corriente import calcular_estado_cuenta

    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0]
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, 1, hoy=date(2026, 6, 15))
    suma_pendientes = round(
        sum(c.monto_pendiente for c in estado.por_expensa.values()), 2
    )
    assert estado.saldo_total == 1070.0
    assert suma_pendientes == 1070.0


def test_una_expensa_no_admite_dos_movimientos_de_recargo(db_empty, depto):
    """La guarda de `_devengar` es un chequeo-y-después-inserto: dos lecturas
    concurrentes la pasan las dos. La restricción única de la base es la que
    impide el segundo recargo."""
    from sqlalchemy.exc import IntegrityError

    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _devengar(db_empty, 1, hoy=date(2026, 6, 15))
    db_empty.commit()

    db_empty.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=date(2026, 6, 10),
        tipo=TipoMovimiento.recargo, descripcion="Recargo duplicado",
        monto=70.0, expensa_id=1,
    ))
    with pytest.raises(IntegrityError):
        db_empty.flush()
    db_empty.rollback()


def test_la_emision_y_el_recargo_de_la_misma_expensa_conviven(db_empty, depto):
    """`tipo` forma parte de la clave: la restricción separa la emisión del
    recargo en vez de hacerlos chocar."""
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    nuevos = _devengar(db_empty, 1, hoy=date(2026, 6, 15))[0]
    db_empty.commit()

    assert len(nuevos) == 1
    movs = db_empty.scalars(
        select(MovimientoCuenta).where(MovimientoCuenta.expensa_id == 1)
    ).all()
    assert {m.tipo for m in movs} == {
        TipoMovimiento.expensa_emitida, TipoMovimiento.recargo
    }


def test_los_movimientos_sin_expensa_no_los_alcanza_la_restriccion(db_empty, depto):
    """Pagos, notas e intereses llevan `expensa_id` NULL, y SQLite trata cada
    NULL como distinto: varios del mismo tipo conviven."""
    _pago(db_empty, 500.0, date(2026, 6, 1))
    _pago(db_empty, 300.0, date(2026, 6, 2))
    _pago(db_empty, 200.0, date(2026, 6, 3))

    movs = db_empty.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.tipo == TipoMovimiento.pago_recibido
        )
    ).all()
    assert len(movs) == 3
