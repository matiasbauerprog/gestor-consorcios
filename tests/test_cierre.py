"""Unit tests del módulo backend/cierre.py — función pura, sin HTTP."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from backend.cierre import (
    calcular_intereses_al_cierre,
    calcular_preview_cierre,
)
from backend.models import (
    Administracion,
    Caja,
    ClaseProrrateo,
    CoeficienteDepartamento,
    Consorcio,
    Departamento,
    Expensa,
    FormaPago,
    Gasto,
    MovimientoCuenta,
    Proveedor,
    Rubro,
    TipoCaja,
    TipoMovimiento,
)


# ---------------------------------------------------------------------------
# Fixture base: DB en memoria con deptos 1 y 2 + configuración del consorcio.
# Usa db_empty (sin seed) para evitar depender del conftest que siembra
# Expensas con shape antiguo.
# ---------------------------------------------------------------------------

@pytest.fixture
def db(db_empty: Session) -> Session:
    """DB limpia con administracion + consorcio + deptos 1 y 2 y caja default."""
    db_empty.add(Administracion(
        id=1, razon_social="Admin Demo", cuit="30-11-1", email_contacto="a@a.com",
    ))
    db_empty.flush()
    db_empty.add(Consorcio(
        id=1,
        administracion_id=1,
        nombre="Consorcio Test",
        consorcio_domicilio="Av. Test 100",
        consorcio_cuit="30-99999999-9",
        admin_nombre="Admin Test",
        admin_domicilio="Oficinas 200",
        admin_email="admin@test.local",
        admin_telefono="11-1111-1111",
        admin_cuit="20-11111111-1",
        admin_rpa="0001",
        admin_situacion_fiscal="Monotributo",
        banco_titular="Consorcio Test",
        banco_nombre="Banco Test",
        banco_numero_cuenta="000-1234567/8",
        banco_cbu="0000000000000000000000",
        dia_primer_vencimiento=10,
        dias_entre_vencimientos=10,
        recargo_segundo_vencimiento_pct=7.0,
        tasa_interes_mensual_pct=3.0,
    ))
    db_empty.flush()
    db_empty.add(Departamento(id=1, consorcio_id=1, codigo="UF-1A", descripcion="Depto A"))
    db_empty.add(Departamento(id=2, consorcio_id=1, codigo="UF-2B", descripcion="Depto B"))
    db_empty.add(Caja(
        id=900,
        consorcio_id=1,
        nombre="Banco Test",
        tipo=TipoCaja.banco,
        saldo_inicial=0.0,
        activa=True,
    ))
    db_empty.flush()
    # Actualizar la caja default del consorcio ahora que la caja existe
    c = db_empty.get(Consorcio, 1)
    c.caja_default_pagos_id = 900
    db_empty.commit()
    return db_empty


@pytest.fixture
def proveedor(db: Session) -> Proveedor:
    p = Proveedor(consorcio_id=1, razon_social="ACME SRL", cuit="30-12345678-9")
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def clase_50_50(db: Session) -> ClaseProrrateo:
    """Clase A con 50/50 entre depto_a (id=1) y depto_b (id=2)."""
    c = ClaseProrrateo(consorcio_id=1, codigo="A", nombre="Clase A")
    db.add(c); db.flush()
    db.add(CoeficienteDepartamento(consorcio_id=1, departamento_id=1, clase_prorrateo_id=c.id, porcentaje=50))
    db.add(CoeficienteDepartamento(consorcio_id=1, departamento_id=2, clase_prorrateo_id=c.id, porcentaje=50))
    db.commit(); db.refresh(c)
    return c


def _gasto(periodo, monto, proveedor_id, *, clase_id=None, depto_id=None, rubro=Rubro.servicios_publicos, concepto="Test"):
    return Gasto(
        consorcio_id=1,
        periodo=periodo, monto=monto, rubro=rubro,
        clase_prorrateo_id=clase_id, departamento_id=depto_id,
        proveedor_id=proveedor_id, concepto=concepto,
        forma_pago=FormaPago.efectivo, caja_id=900,  # Fase 5: caja default
        fecha_pago=date(2026, 5, 15),
    )


def test_preview_periodo_vacio_genera_warning_sin_gastos(db, clase_50_50):
    preview = calcular_preview_cierre(db, "2026-05")
    codigos = [v.codigo for v in preview.validaciones]
    assert "sin_gastos" in codigos
    assert preview.puede_cerrar  # warnings no bloquean
    assert preview.expensas == []


def test_preview_un_gasto_clase_se_prorratea_por_coeficientes(db, proveedor, clase_50_50):
    db.add(_gasto("2026-05", 1000, proveedor.id, clase_id=clase_50_50.id))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    assert len(preview.expensas) == 2
    montos = sorted(e.monto_primer_vencimiento for e in preview.expensas)
    assert montos == [500.0, 500.0]


def test_preview_gasto_particular_va_solo_al_depto_indicado(db, proveedor, clase_50_50):
    db.add(_gasto("2026-05", 800, proveedor.id, depto_id=1, concepto="Reparación caño 1A"))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    deptos_con_expensa = {e.departamento_id for e in preview.expensas}
    assert deptos_con_expensa == {1}
    assert preview.expensas[0].monto_primer_vencimiento == 800.0
    assert preview.expensas[0].detalle[0].departamento_origen_id == 1


def test_preview_monto_segundo_venc_aplica_recargo_correcto(db, proveedor, clase_50_50):
    # default recargo 7%
    db.add(_gasto("2026-05", 1000, proveedor.id, clase_id=clase_50_50.id))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    for e in preview.expensas:
        assert e.monto_primer_vencimiento == 500.0
        assert e.monto_segundo_vencimiento == round(500 * 1.07, 2)


def test_preview_fecha_default_por_regla_configurable(db, clase_50_50):
    preview = calcular_preview_cierre(db, "2026-05")
    # default: dia=10, dias_entre=10 → 10-jun y 20-jun
    assert preview.fecha_primer_vencimiento == date(2026, 6, 10)
    assert preview.fecha_segundo_vencimiento == date(2026, 6, 20)


def test_preview_fecha_explicita_override(db, clase_50_50):
    preview = calcular_preview_cierre(
        db, "2026-05",
        fecha_primer_venc=date(2026, 6, 5),
        fecha_segundo_venc=date(2026, 6, 15),
    )
    assert preview.fecha_primer_vencimiento == date(2026, 6, 5)
    assert preview.fecha_segundo_vencimiento == date(2026, 6, 15)


def test_preview_validacion_bloqueante_coef_no_suma_100(db, proveedor):
    clase = ClaseProrrateo(codigo="X", nombre="X")
    db.add(clase); db.flush()
    db.add(CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=clase.id, porcentaje=60))
    db.add(CoeficienteDepartamento(departamento_id=2, clase_prorrateo_id=clase.id, porcentaje=30))
    db.add(_gasto("2026-05", 1000, proveedor.id, clase_id=clase.id))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    codigos = [v.codigo for v in preview.validaciones if v.tipo == "bloqueante"]
    assert "coeficientes_no_suman_100" in codigos
    assert not preview.puede_cerrar


def test_preview_validacion_bloqueante_coef_faltante(db, proveedor):
    clase = ClaseProrrateo(codigo="Y", nombre="Y")
    db.add(clase); db.flush()
    db.add(CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=clase.id, porcentaje=100))
    db.add(_gasto("2026-05", 1000, proveedor.id, clase_id=clase.id))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    codigos = [v.codigo for v in preview.validaciones if v.tipo == "bloqueante"]
    assert "coeficientes_faltantes" in codigos


def test_preview_validacion_bloqueante_fechas_invalidas(db, clase_50_50):
    preview = calcular_preview_cierre(
        db, "2026-05",
        fecha_primer_venc=date(2026, 6, 20),
        fecha_segundo_venc=date(2026, 6, 10),
    )
    codigos = [v.codigo for v in preview.validaciones if v.tipo == "bloqueante"]
    assert "fechas_invalidas" in codigos


def test_intereses_depto_al_dia_devuelve_cero(db):
    monto, _ = calcular_intereses_al_cierre(db, 1, date(2026, 6, 30))
    assert monto == 0.0


def test_intereses_un_mes_de_mora_calcula_correcto(db, proveedor):
    # Expensa de abril, 2° venc 20-may, monto 1000, sin pago. Calcular al 30-may.
    expensa = Expensa(
        consorcio_id=1,
        departamento_id=1, periodo="2026-04",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento=date(2026, 5, 10),
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento=date(2026, 5, 20),
        saldo_anterior=0.0,
    )
    db.add(expensa); db.flush()
    db.add(MovimientoCuenta(
        consorcio_id=1,
        departamento_id=1, fecha=date(2026, 5, 1),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa 2026-04",
        monto=1000, expensa_id=expensa.id,
    ))
    db.commit()

    monto, descripcion = calcular_intereses_al_cierre(db, 1, date(2026, 5, 30))
    # 10 días de mora, tasa 3%/mes → 0.001/día. 1000 × 0.001 × 10 = 10.
    assert monto == 10.0
    assert "2026-04" in descripcion
