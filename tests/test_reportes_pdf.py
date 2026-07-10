"""Smoke tests de generación de PDFs de reportes."""
from datetime import date

from backend.reportes import (
    calcular_morosos, calcular_estado_financiero,
    calcular_gastos_del_periodo, calcular_lista_proveedores,
)
from backend.pdf import (
    generar_pdf_morosos, generar_pdf_estado_financiero,
    generar_pdf_gastos_periodo, generar_pdf_lista_proveedores,
)


def test_pdf_morosos(db):
    from backend.models import Consorcio
    config = db.get(Consorcio, 1)
    items = calcular_morosos(db, 1, solo_deudores=False)
    pdf = generar_pdf_morosos(items, date.today(), config)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_pdf_estado_financiero(db):
    from backend.models import Consorcio
    config = db.get(Consorcio, 1)
    rep = calcular_estado_financiero(db, 1, date.today())
    pdf = generar_pdf_estado_financiero(rep, config)
    assert pdf.startswith(b"%PDF-")


def test_pdf_gastos_periodo(db):
    from backend.models import Consorcio
    config = db.get(Consorcio, 1)
    rep = calcular_gastos_del_periodo(db, 1, "2026-06")
    pdf = generar_pdf_gastos_periodo(rep, config)
    assert pdf.startswith(b"%PDF-")


def test_pdf_lista_proveedores(db):
    from backend.models import Consorcio
    config = db.get(Consorcio, 1)
    items = calcular_lista_proveedores(db, 1, anio=2026)
    pdf = generar_pdf_lista_proveedores(items, 2026, config)
    assert pdf.startswith(b"%PDF-")
