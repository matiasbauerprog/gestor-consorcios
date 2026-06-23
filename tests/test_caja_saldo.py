"""Tests unitarios del módulo puro caja_saldo."""
import pytest

from backend.caja_saldo import MovimientoSnapshot, calcular_saldo


def test_saldo_sin_movimientos_devuelve_saldo_inicial():
    assert calcular_saldo(1000.0, []) == 1000.0


def test_ingreso_suma_al_saldo():
    movs = [MovimientoSnapshot(tipo="ingreso", monto=500.0)]
    assert calcular_saldo(1000.0, movs) == 1500.0


def test_egreso_resta_del_saldo():
    movs = [MovimientoSnapshot(tipo="egreso", monto=300.0)]
    assert calcular_saldo(1000.0, movs) == 700.0


def test_ajuste_positivo_suma():
    movs = [MovimientoSnapshot(tipo="ajuste", monto=200.0)]
    assert calcular_saldo(1000.0, movs) == 1200.0


def test_ajuste_negativo_resta():
    movs = [MovimientoSnapshot(tipo="ajuste", monto=-150.0)]
    assert calcular_saldo(1000.0, movs) == 850.0


def test_combinacion_de_tipos():
    movs = [
        MovimientoSnapshot(tipo="ingreso", monto=2000.0),
        MovimientoSnapshot(tipo="egreso", monto=500.0),
        MovimientoSnapshot(tipo="ajuste", monto=-100.0),
    ]
    # 1000 + 2000 - 500 - 100 = 2400
    assert calcular_saldo(1000.0, movs) == 2400.0


def test_tipo_invalido_devuelve_error():
    movs = [MovimientoSnapshot(tipo="loquesea", monto=100.0)]
    with pytest.raises(ValueError, match="Tipo de movimiento desconocido"):
        calcular_saldo(0.0, movs)
