"""Tests unitarios de las funciones puras de reportes (sin HTTP)."""
from datetime import date

from backend.reportes import (
    calcular_morosos,
    calcular_estado_financiero,
    calcular_gastos_del_periodo,
    calcular_lista_proveedores,
)


def test_morosos_solo_deudores_excluye_al_dia(db):
    items = calcular_morosos(db, 1, solo_deudores=True)
    for it in items:
        assert it.saldo > 0


def test_morosos_todos_incluye_a_favor_y_al_dia(db):
    todos = calcular_morosos(db, 1, solo_deudores=False)
    deudores = calcular_morosos(db, 1, solo_deudores=True)
    assert len(todos) >= len(deudores)


def test_morosos_orden_por_saldo_descendente(db):
    items = calcular_morosos(db, 1, solo_deudores=True)
    if len(items) > 1:
        for i in range(len(items) - 1):
            assert items[i].saldo >= items[i+1].saldo


def test_morosos_devenga_el_recargo_de_las_expensas_vencidas(db):
    """Regresión del cableado en `calcular_morosos`: sin el devengamiento el
    reporte informa 135000 y subestima la deuda en el recargo."""
    from datetime import timedelta

    from backend.models import Expensa, MovimientoCuenta, TipoMovimiento

    hoy = date.today()
    # Primer vencimiento pasado (ya rige el monto con recargo) y segundo
    # futuro (no corre interés punitorio, que ensuciaría la aritmética).
    db.add(Expensa(
        id=150, consorcio_id=1, departamento_id=1, periodo="2026-04",
        monto_primer_vencimiento=50000.0,
        fecha_primer_vencimiento=hoy - timedelta(days=5),
        monto_segundo_vencimiento=53500.0,
        fecha_segundo_vencimiento=hoy + timedelta(days=5),
        saldo_anterior=0.0,
    ))
    db.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=hoy - timedelta(days=25),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa 2026-04",
        monto=50000.0, expensa_id=150,
    ))
    db.commit()

    items = {it.departamento_id: it for it in calcular_morosos(db, 1, solo_deudores=True)}

    # 85000 (expensa del seed) + 53500 (50000 + 7% de recargo) = 138500.
    assert items[1].saldo == 138500.0


def test_estado_financiero_patrimonio_es_activo_menos_pasivo(db):
    rep = calcular_estado_financiero(db, 1, date.today())
    assert rep.patrimonio_neto == round(rep.activo_total - rep.pasivo_total, 2)


def test_estado_financiero_activo_suma_cajas_y_deudores(db):
    rep = calcular_estado_financiero(db, 1, date.today())
    suma_cajas = sum(c.saldo for c in rep.cajas)
    assert rep.activo_total == round(suma_cajas + rep.deudores_total, 2)


def test_gastos_del_periodo_total_es_suma_de_subtotales_mas_particulares(db):
    rep = calcular_gastos_del_periodo(db, 1, "2026-05")
    suma_rubros = sum(rep.subtotales_por_rubro.values())
    suma_particulares = sum(p.monto for p in rep.particulares)
    assert rep.total_general == round(suma_rubros + suma_particulares, 2)


def test_gastos_del_periodo_filtra_por_rubro(db):
    rep = calcular_gastos_del_periodo(db, 1, "2026-05", rubro="abonos_y_servicios")
    for items in rep.por_rubro.values():
        for it in items:
            assert it.rubro == "abonos_y_servicios"


def test_gastos_del_periodo_inexistente_total_cero(db):
    rep = calcular_gastos_del_periodo(db, 1, "2099-12")
    assert rep.total_general == 0
    assert rep.por_rubro == {}
    assert rep.particulares == []


def test_proveedores_orden_por_total_descendente(db):
    items = calcular_lista_proveedores(db, 1, anio=2026)
    if len(items) > 1:
        for i in range(len(items) - 1):
            assert items[i].total_facturado >= items[i+1].total_facturado


def test_proveedores_filtro_por_anio_restringe(db):
    items_2099 = calcular_lista_proveedores(db, 1, anio=2099)
    assert len(items_2099) == 0
