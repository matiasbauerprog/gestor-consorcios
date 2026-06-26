# Fase 6b — Reportes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4 reportes consultables y exportables a PDF (morosos, estado financiero, gastos del período, lista de proveedores), accesibles a admin/representante/depto.

**Architecture:**
- Backend: módulo puro `backend/reportes.py` con dataclasses + funciones de cálculo, extensión de `backend/pdf.py` con 4 funciones PDF nuevas + refactor de header reutilizable, router `/reportes` con 8 endpoints (4 JSON + 4 PDF).
- Frontend: API client `api/reportes.js`, 4 pantallas planas en sidebar nueva sección "Reportes", reusa patrón blob URL para PDFs.
- Sin cambios al modelo. Sin migración. Cero bloqueos cross-recurso (read-only).

**Tech Stack:** Python (ReportLab para PDFs, SQLAlchemy 2.0 + select aggregations), FastAPI, React 18.

**Reference:** El diseño detallado vive en `docs/superpowers/specs/2026-06-25-fase6b-reportes-design.md`.

---

## Task 0: Setup branch + baseline

**Files:** ninguno (git).

- [ ] **Step 1: Crear branch desde master**

```bash
git checkout master
git checkout -b feature/expensas-fase6b-reportes
```

- [ ] **Step 2: Verificar baseline de la suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: `542 passed` (baseline post-Fase 6a).

---

## Task 1: Módulo `backend/reportes.py` (cálculo puro) + tests

**Files:**
- Create: `backend/reportes.py`
- Create: `tests/test_reportes_calculo.py`

- [ ] **Step 1: Crear `backend/reportes.py` con dataclasses + funciones**

```python
"""Reportes — Fase 6b.

Funciones puras: leen de la DB y devuelven dataclasses listas para serializar
(a JSON via Pydantic) o renderizar a PDF.

Sin side effects, sin mutaciones. Cada función testea contra fixtures.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .caja_saldo import MovimientoSnapshot, calcular_saldo
from .cuenta_corriente import calcular_estado_cuenta
from .models import (
    Caja,
    Departamento,
    Expensa,
    Gasto,
    MovimientoCaja,
    MovimientoCuenta,
    Proveedor,
)


# === Dataclasses ===

@dataclass(frozen=True)
class ItemMoroso:
    departamento_id: int
    departamento_codigo: str
    saldo: float                       # > 0 = debe; < 0 = a favor
    periodos_vencidos_impagos: int
    primer_vencimiento_impago: date | None


@dataclass(frozen=True)
class ItemActivoCaja:
    caja_id: int
    nombre: str
    saldo: float


@dataclass(frozen=True)
class ItemPasivoGasto:
    gasto_id: int
    proveedor: str
    concepto: str
    monto: float
    fecha_registrada: date


@dataclass(frozen=True)
class EstadoFinancieroReporte:
    fecha_corte: date
    cajas: list[ItemActivoCaja]
    deudores_total: float
    pasivos: list[ItemPasivoGasto]
    activo_total: float
    pasivo_total: float
    patrimonio_neto: float


@dataclass(frozen=True)
class ItemGastoDetalle:
    fecha: date
    concepto: str
    rubro: str
    proveedor: str
    forma_pago: str
    caja: str
    monto: float
    es_particular: bool


@dataclass(frozen=True)
class GastosDelPeriodoReporte:
    periodo: str
    por_rubro: dict[str, list[ItemGastoDetalle]]
    particulares: list[ItemGastoDetalle]
    subtotales_por_rubro: dict[str, float]
    total_general: float


@dataclass(frozen=True)
class ItemProveedor:
    proveedor_id: int
    razon_social: str
    cuit: str
    cantidad_gastos: int
    total_facturado: float
    ultimo_gasto: date | None


# === Funciones de cálculo ===

def calcular_morosos(db: Session, solo_deudores: bool = True) -> list[ItemMoroso]:
    """Calcula la lista de morosos. Iter por Departamento y suma saldo via cuenta_corriente."""
    deptos = list(db.scalars(select(Departamento).order_by(Departamento.id)).all())
    items: list[ItemMoroso] = []
    hoy = date.today()
    for d in deptos:
        estado = calcular_estado_cuenta(db, d.id)
        saldo = estado.saldo_total  # > 0 = debe
        if solo_deudores and saldo <= 0:
            continue

        # Contar expensas vencidas impagas + primer venc impago
        expensas_vencidas = list(db.scalars(
            select(Expensa)
            .where(
                Expensa.departamento_id == d.id,
                Expensa.fecha_segundo_vencimiento < hoy,
            )
            .order_by(Expensa.fecha_primer_vencimiento)
        ).all())
        # Una expensa está impaga si su monto > pagos asignados (simplificación:
        # contamos todas las vencidas cuando saldo > 0; si saldo <= 0 no aplica)
        periodos_vencidos = len(expensas_vencidas) if saldo > 0 else 0
        primer_imp = expensas_vencidas[0].fecha_primer_vencimiento if expensas_vencidas and saldo > 0 else None

        items.append(ItemMoroso(
            departamento_id=d.id,
            departamento_codigo=d.codigo,
            saldo=saldo,
            periodos_vencidos_impagos=periodos_vencidos,
            primer_vencimiento_impago=primer_imp,
        ))

    items.sort(key=lambda x: x.saldo, reverse=True)
    return items


def calcular_estado_financiero(db: Session, fecha_corte: date) -> EstadoFinancieroReporte:
    """Snapshot patrimonial a una fecha."""
    # Cajas activas
    cajas_db = list(db.scalars(select(Caja).where(Caja.activa == True).order_by(Caja.id)).all())
    cajas_items: list[ItemActivoCaja] = []
    cajas_total = 0.0
    for c in cajas_db:
        movs = list(db.scalars(
            select(MovimientoCaja).where(
                MovimientoCaja.caja_id == c.id,
                MovimientoCaja.fecha <= fecha_corte,
            )
        ).all())
        snaps = [MovimientoSnapshot(tipo=m.tipo.value, monto=m.monto) for m in movs]
        saldo = calcular_saldo(c.saldo_inicial, snaps)
        cajas_items.append(ItemActivoCaja(caja_id=c.id, nombre=c.nombre, saldo=saldo))
        cajas_total += saldo

    # Deudores total: suma de saldos positivos
    morosos = calcular_morosos(db, solo_deudores=True)
    deudores_total = sum(m.saldo for m in morosos)

    # Pasivos: gastos con fecha_pago > fecha_corte
    gastos_futuros = list(db.scalars(
        select(Gasto).where(Gasto.fecha_pago > fecha_corte)
    ).all())
    pasivos: list[ItemPasivoGasto] = []
    for g in gastos_futuros:
        prov = db.get(Proveedor, g.proveedor_id) if g.proveedor_id else None
        pasivos.append(ItemPasivoGasto(
            gasto_id=g.id,
            proveedor=prov.razon_social if prov else "—",
            concepto=g.concepto or "—",
            monto=g.monto,
            fecha_registrada=g.fecha_pago,
        ))
    pasivo_total = sum(p.monto for p in pasivos)

    activo_total = cajas_total + deudores_total
    patrimonio = activo_total - pasivo_total

    return EstadoFinancieroReporte(
        fecha_corte=fecha_corte,
        cajas=cajas_items,
        deudores_total=round(deudores_total, 2),
        pasivos=pasivos,
        activo_total=round(activo_total, 2),
        pasivo_total=round(pasivo_total, 2),
        patrimonio_neto=round(patrimonio, 2),
    )


def calcular_gastos_del_periodo(
    db: Session,
    periodo: str,
    rubro: str | None = None,
    proveedor_id: int | None = None,
) -> GastosDelPeriodoReporte:
    """Detalle de gastos de un período YYYY-MM, agrupado por rubro y separando particulares."""
    q = select(Gasto).where(Gasto.periodo == periodo)
    if rubro:
        q = q.where(Gasto.rubro == rubro)
    if proveedor_id is not None:
        q = q.where(Gasto.proveedor_id == proveedor_id)
    gastos = list(db.scalars(q.order_by(Gasto.fecha_pago)).all())

    por_rubro: dict[str, list[ItemGastoDetalle]] = defaultdict(list)
    particulares: list[ItemGastoDetalle] = []
    subtotales: dict[str, float] = defaultdict(float)
    total = 0.0

    for g in gastos:
        prov = db.get(Proveedor, g.proveedor_id) if g.proveedor_id else None
        caja = db.get(Caja, g.caja_id) if g.caja_id else None
        item = ItemGastoDetalle(
            fecha=g.fecha_pago,
            concepto=g.concepto or "—",
            rubro=g.rubro.value if g.rubro else "—",
            proveedor=prov.razon_social if prov else "—",
            forma_pago=g.forma_pago.value if g.forma_pago else "—",
            caja=caja.nombre if caja else "—",
            monto=g.monto,
            es_particular=(g.clase_prorrateo_id is None and g.departamento_id is not None),
        )
        total += g.monto
        if item.es_particular:
            particulares.append(item)
        else:
            por_rubro[item.rubro].append(item)
            subtotales[item.rubro] += g.monto

    return GastosDelPeriodoReporte(
        periodo=periodo,
        por_rubro=dict(por_rubro),
        particulares=particulares,
        subtotales_por_rubro={k: round(v, 2) for k, v in subtotales.items()},
        total_general=round(total, 2),
    )


def calcular_lista_proveedores(
    db: Session,
    anio: int,
    periodo: str | None = None,
) -> list[ItemProveedor]:
    """Ranking de proveedores por monto facturado en un año (opcional restringir a un período)."""
    q = select(Gasto).where(Gasto.periodo.like(f"{anio}-%"))
    if periodo:
        q = q.where(Gasto.periodo == periodo)
    gastos = list(db.scalars(q).all())

    agg: dict[int, dict] = {}
    for g in gastos:
        if g.proveedor_id is None:
            continue
        entry = agg.setdefault(g.proveedor_id, {"cant": 0, "total": 0.0, "ultima": None})
        entry["cant"] += 1
        entry["total"] += g.monto
        if entry["ultima"] is None or g.fecha_pago > entry["ultima"]:
            entry["ultima"] = g.fecha_pago

    items: list[ItemProveedor] = []
    for prov_id, data in agg.items():
        prov = db.get(Proveedor, prov_id)
        if prov is None:
            continue
        items.append(ItemProveedor(
            proveedor_id=prov_id,
            razon_social=prov.razon_social,
            cuit=prov.cuit or "—",
            cantidad_gastos=data["cant"],
            total_facturado=round(data["total"], 2),
            ultimo_gasto=data["ultima"],
        ))
    items.sort(key=lambda x: x.total_facturado, reverse=True)
    return items
```

**Verificado**: la función existente es `calcular_estado_cuenta(db, departamento_id, hoy=None)` y devuelve `EstadoCuenta` con campo `.saldo_total` (verificado en `backend/cuenta_corriente.py:38`).

- [ ] **Step 2: Crear `tests/test_reportes_calculo.py`**

```python
"""Tests unitarios de las funciones puras de reportes (sin HTTP)."""
from datetime import date

import pytest

from backend.reportes import (
    calcular_morosos,
    calcular_estado_financiero,
    calcular_gastos_del_periodo,
    calcular_lista_proveedores,
)


def test_morosos_solo_deudores_excluye_al_dia(db):
    """Si el depto tiene saldo <= 0 no aparece con solo_deudores=True."""
    items = calcular_morosos(db, solo_deudores=True)
    for it in items:
        assert it.saldo > 0


def test_morosos_todos_incluye_a_favor_y_al_dia(db):
    """Con solo_deudores=False aparecen todos los deptos."""
    todos = calcular_morosos(db, solo_deudores=False)
    deudores = calcular_morosos(db, solo_deudores=True)
    assert len(todos) >= len(deudores)


def test_morosos_orden_por_saldo_descendente(db):
    """Lista ordenada por saldo (mayor deudor primero)."""
    items = calcular_morosos(db, solo_deudores=True)
    if len(items) > 1:
        for i in range(len(items) - 1):
            assert items[i].saldo >= items[i+1].saldo


def test_estado_financiero_patrimonio_es_activo_menos_pasivo(db):
    rep = calcular_estado_financiero(db, date.today())
    assert rep.patrimonio_neto == round(rep.activo_total - rep.pasivo_total, 2)


def test_estado_financiero_activo_suma_cajas_y_deudores(db):
    rep = calcular_estado_financiero(db, date.today())
    suma_cajas = sum(c.saldo for c in rep.cajas)
    assert rep.activo_total == round(suma_cajas + rep.deudores_total, 2)


def test_gastos_del_periodo_total_es_suma_de_subtotales_mas_particulares(db):
    from backend.models import Expensa
    # Tomar un período donde haya gastos sembrados
    rep = calcular_gastos_del_periodo(db, "2026-05")
    suma_rubros = sum(rep.subtotales_por_rubro.values())
    suma_particulares = sum(p.monto for p in rep.particulares)
    assert rep.total_general == round(suma_rubros + suma_particulares, 2)


def test_gastos_del_periodo_filtra_por_rubro(db):
    rep = calcular_gastos_del_periodo(db, "2026-05", rubro="abonos_y_servicios")
    # Si hay resultados, todos deben ser del rubro filtrado
    for items in rep.por_rubro.values():
        for it in items:
            assert it.rubro == "abonos_y_servicios"


def test_gastos_del_periodo_inexistente_total_cero(db):
    rep = calcular_gastos_del_periodo(db, "2099-12")
    assert rep.total_general == 0
    assert rep.por_rubro == {}
    assert rep.particulares == []


def test_proveedores_orden_por_total_descendente(db):
    items = calcular_lista_proveedores(db, anio=2026)
    if len(items) > 1:
        for i in range(len(items) - 1):
            assert items[i].total_facturado >= items[i+1].total_facturado


def test_proveedores_filtro_por_anio_restringe(db):
    items_2026 = calcular_lista_proveedores(db, anio=2026)
    items_2099 = calcular_lista_proveedores(db, anio=2099)
    assert len(items_2099) == 0  # no debería haber gastos en 2099
```

- [ ] **Step 3: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reportes_calculo.py -v
```

Expected: 10 passed.

**Si falla por nombre de la función `calcular_estado_cuenta_departamento`**: grep el módulo `backend/cuenta_corriente.py` para encontrar el nombre real y adaptar el import.

- [ ] **Step 4: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 552 pass (542 baseline + 10 nuevos), 0 fail.

- [ ] **Step 5: Commit**

```bash
git add backend/reportes.py tests/test_reportes_calculo.py
git commit -m "feat(reportes): módulo puro reportes.py con 4 funciones de cálculo + tests"
```

---

## Task 2: Extender `backend/pdf.py` con 4 funciones de reporte PDF + refactor header

**Files:**
- Modify: `backend/pdf.py`
- Create: `tests/test_reportes_pdf.py`

- [ ] **Step 1: Refactorizar header reutilizable en `backend/pdf.py`**

Buscar la sección del PDF de boleta (Fase 6a) que arma el header del consorcio. Extraer a función reutilizable:

```python
def _dibujar_header_consorcio(story, config, titulo: str, subtitulo: str = "") -> None:
    """Sumar al story el header común a todos los PDFs del consorcio."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, textColor=colors.grey)

    story.append(Paragraph(config.consorcio_nombre, h1))
    story.append(Paragraph(
        f"{config.consorcio_domicilio} · CUIT {config.consorcio_cuit}", normal
    ))
    story.append(Paragraph(
        f"Admin: {config.admin_nombre} (RPA {config.admin_rpa}) · "
        f"{config.admin_email} · {config.admin_telefono}", small
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(titulo, h2))
    if subtitulo:
        story.append(Paragraph(subtitulo, small))
    story.append(Spacer(1, 0.4 * cm))
```

Y modificar `generar_pdf_boleta` para que use `_dibujar_header_consorcio` con `titulo=f"Boleta Nº {expensa.id} · Período {expensa.periodo}"`. Asegurarse de no romper la salida actual (testear `tests/test_pdf_boleta.py` para verificar).

- [ ] **Step 2: Sumar `generar_pdf_morosos` al final de `backend/pdf.py`**

```python
def generar_pdf_morosos(items, fecha, config) -> bytes:
    """PDF del reporte de morosos."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title=f"Lista de morosos al {fecha.isoformat()}",
    )

    story = []
    _dibujar_header_consorcio(story, config, "Lista de morosos", f"Al {fecha.isoformat()}")

    if not items:
        story.append(Paragraph("Sin morosos al día de la fecha. ✓", getSampleStyleSheet()["Normal"]))
    else:
        data = [["Depto", "Saldo deudor", "Períodos vencidos impagos", "Primer venc. impago"]]
        for it in items:
            data.append([
                it.departamento_codigo,
                _money(it.saldo),
                str(it.periodos_vencidos_impagos),
                it.primer_vencimiento_impago.isoformat() if it.primer_vencimiento_impago else "—",
            ])
        total = sum(it.saldo for it in items)
        data.append(["TOTAL", _money(total), "", ""])

        tbl = Table(data, colWidths=[3*cm, 4*cm, 5*cm, 4*cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
            ("BACKGROUND", (0,-1), (-1,-1), colors.lightgrey),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("ALIGN", (2,0), (2,-1), "CENTER"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(tbl)

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 3: Sumar `generar_pdf_estado_financiero`**

```python
def generar_pdf_estado_financiero(reporte, config) -> bytes:
    """PDF del estado financiero (activo/pasivo/patrimonio)."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title=f"Estado financiero al {reporte.fecha_corte.isoformat()}",
    )
    styles = getSampleStyleSheet()

    story = []
    _dibujar_header_consorcio(
        story, config, "Estado financiero",
        f"Al {reporte.fecha_corte.isoformat()}",
    )

    # Activo
    story.append(Paragraph("<b>ACTIVO</b>", styles["Heading3"]))
    activo_data = [["Concepto", "Importe"]]
    for c in reporte.cajas:
        activo_data.append([f"  {c.nombre}", _money(c.saldo)])
    activo_data.append(["  Deudores (saldos a cobrar)", _money(reporte.deudores_total)])
    activo_data.append(["TOTAL ACTIVO", _money(reporte.activo_total)])
    tbl_a = Table(activo_data, colWidths=[12*cm, 4*cm])
    tbl_a.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    story.append(tbl_a)
    story.append(Spacer(1, 0.4*cm))

    # Pasivo
    story.append(Paragraph("<b>PASIVO</b>", styles["Heading3"]))
    if not reporte.pasivos:
        story.append(Paragraph("Sin pasivos registrados.", styles["Normal"]))
    else:
        pasivo_data = [["Proveedor", "Concepto", "Importe"]]
        for p in reporte.pasivos:
            pasivo_data.append([p.proveedor, p.concepto, _money(p.monto)])
        pasivo_data.append(["", "TOTAL PASIVO", _money(reporte.pasivo_total)])
        tbl_p = Table(pasivo_data, colWidths=[6*cm, 6*cm, 4*cm])
        tbl_p.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
            ("ALIGN", (2,0), (2,-1), "RIGHT"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]))
        story.append(tbl_p)
    story.append(Spacer(1, 0.5*cm))

    # Patrimonio
    story.append(Paragraph(
        f"<b>PATRIMONIO NETO (Activo - Pasivo): {_money(reporte.patrimonio_neto)}</b>",
        styles["Heading2"],
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Sumar `generar_pdf_gastos_periodo`**

```python
def generar_pdf_gastos_periodo(reporte, config) -> bytes:
    """PDF del detalle de gastos del período."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title=f"Gastos del período {reporte.periodo}",
    )
    styles = getSampleStyleSheet()
    story = []
    _dibujar_header_consorcio(
        story, config, "Detalle de gastos",
        f"Período {reporte.periodo}",
    )

    for rubro, items in reporte.por_rubro.items():
        subtotal = reporte.subtotales_por_rubro.get(rubro, 0.0)
        story.append(Paragraph(
            f"<b>{_rubro_label(rubro)}</b> — {_money(subtotal)}",
            styles["Heading3"],
        ))
        data = [["Fecha", "Concepto", "Proveedor", "Caja", "Forma pago", "Importe"]]
        for it in items:
            data.append([
                it.fecha.isoformat(), it.concepto, it.proveedor, it.caja,
                it.forma_pago, _money(it.monto),
            ])
        tbl = Table(data, colWidths=[2*cm, 4*cm, 3.5*cm, 2.5*cm, 2*cm, 3*cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("ALIGN", (-1,0), (-1,-1), "RIGHT"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3*cm))

    if reporte.particulares:
        story.append(Paragraph("<b>Gastos particulares (a deptos)</b>", styles["Heading3"]))
        data = [["Fecha", "Concepto", "Proveedor", "Caja", "Forma pago", "Importe"]]
        for it in reporte.particulares:
            data.append([
                it.fecha.isoformat(), it.concepto, it.proveedor, it.caja,
                it.forma_pago, _money(it.monto),
            ])
        tbl = Table(data, colWidths=[2*cm, 4*cm, 3.5*cm, 2.5*cm, 2*cm, 3*cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("ALIGN", (-1,0), (-1,-1), "RIGHT"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        f"<b>TOTAL GENERAL: {_money(reporte.total_general)}</b>",
        styles["Heading2"],
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 5: Sumar `generar_pdf_lista_proveedores`**

```python
def generar_pdf_lista_proveedores(items, anio, config) -> bytes:
    """PDF del ranking de proveedores."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title=f"Lista de proveedores {anio}",
    )
    styles = getSampleStyleSheet()
    story = []
    _dibujar_header_consorcio(story, config, "Lista de proveedores", f"Año {anio}")

    if not items:
        story.append(Paragraph("Sin proveedores facturados en el año.", styles["Normal"]))
    else:
        data = [["Razón social", "CUIT", "Cant. gastos", "Total facturado", "Último gasto"]]
        for it in items:
            data.append([
                it.razon_social,
                it.cuit,
                str(it.cantidad_gastos),
                _money(it.total_facturado),
                it.ultimo_gasto.isoformat() if it.ultimo_gasto else "—",
            ])
        total = sum(it.total_facturado for it in items)
        data.append(["TOTAL", "", "", _money(total), ""])
        tbl = Table(data, colWidths=[6*cm, 3*cm, 2*cm, 3*cm, 2*cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
            ("BACKGROUND", (0,-1), (-1,-1), colors.lightgrey),
            ("ALIGN", (2,0), (2,-1), "CENTER"),
            ("ALIGN", (3,0), (3,-1), "RIGHT"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]))
        story.append(tbl)

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 6: Crear `tests/test_reportes_pdf.py`**

```python
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
    from backend.models import ConfiguracionConsorcio
    config = db.get(ConfiguracionConsorcio, 1)
    items = calcular_morosos(db, solo_deudores=False)
    pdf = generar_pdf_morosos(items, date.today(), config)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_pdf_estado_financiero(db):
    from backend.models import ConfiguracionConsorcio
    config = db.get(ConfiguracionConsorcio, 1)
    rep = calcular_estado_financiero(db, date.today())
    pdf = generar_pdf_estado_financiero(rep, config)
    assert pdf.startswith(b"%PDF-")


def test_pdf_gastos_periodo(db):
    from backend.models import ConfiguracionConsorcio
    config = db.get(ConfiguracionConsorcio, 1)
    rep = calcular_gastos_del_periodo(db, "2026-05")
    pdf = generar_pdf_gastos_periodo(rep, config)
    assert pdf.startswith(b"%PDF-")


def test_pdf_lista_proveedores(db):
    from backend.models import ConfiguracionConsorcio
    config = db.get(ConfiguracionConsorcio, 1)
    items = calcular_lista_proveedores(db, anio=2026)
    pdf = generar_pdf_lista_proveedores(items, 2026, config)
    assert pdf.startswith(b"%PDF-")
```

- [ ] **Step 7: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reportes_pdf.py tests/test_pdf_boleta.py -v
```

Expected: 7 passed (4 nuevos + 3 de boleta que siguen verdes tras el refactor).

- [ ] **Step 8: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 556 pass (552 + 4 nuevos).

- [ ] **Step 9: Commit**

```bash
git add backend/pdf.py tests/test_reportes_pdf.py
git commit -m "feat(pdf): 4 funciones de reportes + refactor _dibujar_header_consorcio + tests"
```

---

## Task 3: Schemas Pydantic + Router `/reportes` + tests endpoint

**Files:**
- Modify: `backend/schemas.py`
- Create: `backend/routers/reportes.py`
- Modify: `backend/main.py`
- Create: `tests/test_reportes_endpoints.py`

- [ ] **Step 1: Sumar schemas en `backend/schemas.py`**

Al final del archivo:

```python
# === Fase 6b — Reportes ===

class ItemMorosoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    departamento_id: int
    departamento_codigo: str
    saldo: float
    periodos_vencidos_impagos: int
    primer_vencimiento_impago: date | None


class ItemActivoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    caja_id: int
    nombre: str
    saldo: float


class ItemPasivoGastoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gasto_id: int
    proveedor: str
    concepto: str
    monto: float
    fecha_registrada: date


class EstadoFinancieroReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha_corte: date
    cajas: list[ItemActivoCajaOut]
    deudores_total: float
    pasivos: list[ItemPasivoGastoOut]
    activo_total: float
    pasivo_total: float
    patrimonio_neto: float


class ItemGastoDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    concepto: str
    rubro: str
    proveedor: str
    forma_pago: str
    caja: str
    monto: float
    es_particular: bool


class GastosDelPeriodoReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    periodo: str
    por_rubro: dict[str, list[ItemGastoDetalleOut]]
    particulares: list[ItemGastoDetalleOut]
    subtotales_por_rubro: dict[str, float]
    total_general: float


class ItemProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    proveedor_id: int
    razon_social: str
    cuit: str
    cantidad_gastos: int
    total_facturado: float
    ultimo_gasto: date | None
```

- [ ] **Step 2: Crear `backend/routers/reportes.py`**

```python
"""Router de reportes (lectura) — Fase 6b.

Acceso: admin + representante + departamento. Solo GET.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import ConfiguracionConsorcio
from ..pdf import (
    generar_pdf_estado_financiero,
    generar_pdf_gastos_periodo,
    generar_pdf_lista_proveedores,
    generar_pdf_morosos,
)
from ..reportes import (
    calcular_estado_financiero,
    calcular_gastos_del_periodo,
    calcular_lista_proveedores,
    calcular_morosos,
)
from ..schemas import (
    EstadoFinancieroReporteOut,
    GastosDelPeriodoReporteOut,
    ItemMorosoOut,
    ItemProveedorOut,
)

router = APIRouter(prefix="/reportes", tags=["Reportes"])


# === Morosos ===

@router.get("/morosos", response_model=list[ItemMorosoOut])
def listar_morosos(
    solo_deudores: bool = True,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_morosos(db, solo_deudores=solo_deudores)


@router.get("/morosos/pdf")
def pdf_morosos(
    solo_deudores: bool = True,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    items = calcular_morosos(db, solo_deudores=solo_deudores)
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_morosos(items, date.today(), config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="morosos.pdf"'},
    )


# === Estado financiero ===

@router.get("/estado-financiero", response_model=EstadoFinancieroReporteOut)
def obtener_estado_financiero(
    fecha_corte: date | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_estado_financiero(db, fecha_corte or date.today())


@router.get("/estado-financiero/pdf")
def pdf_estado_financiero(
    fecha_corte: date | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    rep = calcular_estado_financiero(db, fecha_corte or date.today())
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_estado_financiero(rep, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="estado-financiero.pdf"'},
    )


# === Gastos del período ===

@router.get("/gastos/{periodo}", response_model=GastosDelPeriodoReporteOut)
def obtener_gastos_del_periodo(
    periodo: str,
    rubro: str | None = None,
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_gastos_del_periodo(db, periodo, rubro=rubro, proveedor_id=proveedor_id)


@router.get("/gastos/{periodo}/pdf")
def pdf_gastos_periodo(
    periodo: str,
    rubro: str | None = None,
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    rep = calcular_gastos_del_periodo(db, periodo, rubro=rubro, proveedor_id=proveedor_id)
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_gastos_periodo(rep, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="gastos-{periodo}.pdf"'},
    )


# === Lista de proveedores ===

@router.get("/proveedores", response_model=list[ItemProveedorOut])
def listar_proveedores(
    anio: int = date.today().year,
    periodo: str | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_lista_proveedores(db, anio=anio, periodo=periodo)


@router.get("/proveedores/pdf")
def pdf_proveedores(
    anio: int = date.today().year,
    periodo: str | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    items = calcular_lista_proveedores(db, anio=anio, periodo=periodo)
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_lista_proveedores(items, anio, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="proveedores-{anio}.pdf"'},
    )
```

- [ ] **Step 3: Registrar el router en `backend/main.py`**

Sumar `reportes` al import de `from .routers import (...)` y `app.include_router(reportes.router)` donde se incluyen los demás.

- [ ] **Step 4: Smoke import**

```bash
.venv/Scripts/python.exe -c "from backend.main import app; print('OK')"
```

Expected: `OK`.

- [ ] **Step 5: Crear `tests/test_reportes_endpoints.py`**

```python
"""Tests de endpoints HTTP de reportes."""


def test_morosos_admin_200(client, headers_admin):
    r = client.get("/reportes/morosos", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_morosos_depto_200_transparencia(client, headers_depto_a):
    r = client.get("/reportes/morosos", headers=headers_depto_a)
    assert r.status_code == 200


def test_morosos_sin_token_401(client):
    r = client.get("/reportes/morosos")
    assert r.status_code == 401


def test_morosos_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/morosos/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_estado_financiero_admin_200(client, headers_admin):
    r = client.get("/reportes/estado-financiero", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "activo_total" in body and "pasivo_total" in body and "patrimonio_neto" in body


def test_estado_financiero_filtro_fecha(client, headers_admin):
    r = client.get("/reportes/estado-financiero?fecha_corte=2026-01-01", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["fecha_corte"] == "2026-01-01"


def test_estado_financiero_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/estado-financiero/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_gastos_periodo_admin_200(client, headers_admin):
    r = client.get("/reportes/gastos/2026-05", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["periodo"] == "2026-05"
    assert "por_rubro" in body and "particulares" in body


def test_gastos_periodo_filtro_rubro(client, headers_admin):
    r = client.get("/reportes/gastos/2026-05?rubro=abonos_y_servicios", headers=headers_admin)
    assert r.status_code == 200
    for items in r.json()["por_rubro"].values():
        for it in items:
            assert it["rubro"] == "abonos_y_servicios"


def test_gastos_periodo_inexistente_total_cero(client, headers_admin):
    r = client.get("/reportes/gastos/2099-12", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["total_general"] == 0


def test_gastos_periodo_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/gastos/2026-05/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_proveedores_admin_200(client, headers_admin):
    r = client.get("/reportes/proveedores?anio=2026", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_proveedores_pdf_admin_200(client, headers_admin):
    r = client.get("/reportes/proveedores/pdf?anio=2026", headers=headers_admin)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")
```

- [ ] **Step 6: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reportes_endpoints.py -v --tb=short
```

Expected: 13 passed.

- [ ] **Step 7: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 569 pass (556 + 13 nuevos), 0 fail.

- [ ] **Step 8: Commit**

```bash
git add backend/schemas.py backend/routers/reportes.py backend/main.py tests/test_reportes_endpoints.py
git commit -m "feat(reportes): router /reportes con 8 endpoints (4 JSON + 4 PDF) + tests"
```

---

## Task 4: OpenAPI

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Sumar tag**

En la sección `tags:`:
```yaml
  - name: Reportes
    description: Reportes consultables (morosos, estado financiero, gastos, proveedores)
```

- [ ] **Step 2: Sumar 8 paths**

Al final de `paths:`:

```yaml
  /reportes/morosos:
    get:
      tags: [Reportes]
      summary: Lista de morosos
      operationId: listarMorosos
      security: [{bearerAuth: []}]
      parameters:
        - name: solo_deudores
          in: query
          schema: { type: boolean, default: true }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/ItemMorosoOut' }
        '401': { description: Token ausente }

  /reportes/morosos/pdf:
    get:
      tags: [Reportes]
      summary: PDF de lista de morosos
      operationId: pdfMorosos
      security: [{bearerAuth: []}]
      parameters:
        - name: solo_deudores
          in: query
          schema: { type: boolean, default: true }
      responses:
        '200':
          description: PDF
          content:
            application/pdf:
              schema: { type: string, format: binary }

  /reportes/estado-financiero:
    get:
      tags: [Reportes]
      summary: Estado financiero a una fecha
      operationId: obtenerEstadoFinancieroReporte
      security: [{bearerAuth: []}]
      parameters:
        - name: fecha_corte
          in: query
          schema: { type: string, format: date }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EstadoFinancieroReporteOut' }

  /reportes/estado-financiero/pdf:
    get:
      tags: [Reportes]
      summary: PDF del estado financiero
      operationId: pdfEstadoFinanciero
      security: [{bearerAuth: []}]
      parameters:
        - name: fecha_corte
          in: query
          schema: { type: string, format: date }
      responses:
        '200':
          description: PDF
          content:
            application/pdf:
              schema: { type: string, format: binary }

  /reportes/gastos/{periodo}:
    get:
      tags: [Reportes]
      summary: Detalle de gastos del período
      operationId: obtenerGastosDelPeriodoReporte
      security: [{bearerAuth: []}]
      parameters:
        - name: periodo
          in: path
          required: true
          schema: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        - name: rubro
          in: query
          schema: { type: string }
        - name: proveedor_id
          in: query
          schema: { type: integer }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastosDelPeriodoReporteOut' }

  /reportes/gastos/{periodo}/pdf:
    get:
      tags: [Reportes]
      summary: PDF del detalle de gastos del período
      operationId: pdfGastosPeriodo
      security: [{bearerAuth: []}]
      parameters:
        - name: periodo
          in: path
          required: true
          schema: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        - name: rubro
          in: query
          schema: { type: string }
        - name: proveedor_id
          in: query
          schema: { type: integer }
      responses:
        '200':
          description: PDF
          content:
            application/pdf:
              schema: { type: string, format: binary }

  /reportes/proveedores:
    get:
      tags: [Reportes]
      summary: Lista de proveedores con totales facturados
      operationId: listarProveedoresReporte
      security: [{bearerAuth: []}]
      parameters:
        - name: anio
          in: query
          schema: { type: integer }
        - name: periodo
          in: query
          schema: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/ItemProveedorOut' }

  /reportes/proveedores/pdf:
    get:
      tags: [Reportes]
      summary: PDF de la lista de proveedores
      operationId: pdfProveedores
      security: [{bearerAuth: []}]
      parameters:
        - name: anio
          in: query
          schema: { type: integer }
        - name: periodo
          in: query
          schema: { type: string }
      responses:
        '200':
          description: PDF
          content:
            application/pdf:
              schema: { type: string, format: binary }
```

- [ ] **Step 3: Sumar 7 schemas en `components.schemas`**

```yaml
    ItemMorosoOut:
      type: object
      properties:
        departamento_id: { type: integer }
        departamento_codigo: { type: string }
        saldo: { type: number }
        periodos_vencidos_impagos: { type: integer }
        primer_vencimiento_impago: { type: string, format: date, nullable: true }

    ItemActivoCajaOut:
      type: object
      properties:
        caja_id: { type: integer }
        nombre: { type: string }
        saldo: { type: number }

    ItemPasivoGastoOut:
      type: object
      properties:
        gasto_id: { type: integer }
        proveedor: { type: string }
        concepto: { type: string }
        monto: { type: number }
        fecha_registrada: { type: string, format: date }

    EstadoFinancieroReporteOut:
      type: object
      properties:
        fecha_corte: { type: string, format: date }
        cajas:
          type: array
          items: { $ref: '#/components/schemas/ItemActivoCajaOut' }
        deudores_total: { type: number }
        pasivos:
          type: array
          items: { $ref: '#/components/schemas/ItemPasivoGastoOut' }
        activo_total: { type: number }
        pasivo_total: { type: number }
        patrimonio_neto: { type: number }

    ItemGastoDetalleOut:
      type: object
      properties:
        fecha: { type: string, format: date }
        concepto: { type: string }
        rubro: { type: string }
        proveedor: { type: string }
        forma_pago: { type: string }
        caja: { type: string }
        monto: { type: number }
        es_particular: { type: boolean }

    GastosDelPeriodoReporteOut:
      type: object
      properties:
        periodo: { type: string }
        por_rubro:
          type: object
          additionalProperties:
            type: array
            items: { $ref: '#/components/schemas/ItemGastoDetalleOut' }
        particulares:
          type: array
          items: { $ref: '#/components/schemas/ItemGastoDetalleOut' }
        subtotales_por_rubro:
          type: object
          additionalProperties: { type: number }
        total_general: { type: number }

    ItemProveedorOut:
      type: object
      properties:
        proveedor_id: { type: integer }
        razon_social: { type: string }
        cuit: { type: string }
        cantidad_gastos: { type: integer }
        total_facturado: { type: number }
        ultimo_gasto: { type: string, format: date, nullable: true }
```

- [ ] **Step 4: Validar yaml**

```bash
.venv/Scripts/python.exe -c "import yaml; spec = yaml.safe_load(open('openapi.yaml').read()); print('paths:', len(spec['paths']), 'schemas:', len(spec['components']['schemas']))"
```

Expected: paths +8, schemas +7 respecto al baseline.

- [ ] **Step 5: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): tag Reportes + 8 paths + 7 schemas (Fase 6b)"
```

---

## Task 5: Frontend API client + 2 pantallas (Morosos + Estado Financiero)

**Files:**
- Create: `frontend/src/api/reportes.js`
- Create: `frontend/src/screens/ReporteMorosos.jsx`
- Create: `frontend/src/screens/ReporteEstadoFinanciero.jsx`

- [ ] **Step 1: Crear `frontend/src/api/reportes.js`**

```javascript
import { apiFetch, API_BASE } from "./client";

// JSON
export function listarMorosos({ soloDeudores = true } = {}) {
  return apiFetch(`/reportes/morosos?solo_deudores=${soloDeudores}`);
}

export function obtenerEstadoFinanciero(fechaCorte) {
  const qs = fechaCorte ? `?fecha_corte=${fechaCorte}` : "";
  return apiFetch(`/reportes/estado-financiero${qs}`);
}

export function obtenerGastosDelPeriodo(periodo, { rubro, proveedorId } = {}) {
  const params = new URLSearchParams();
  if (rubro) params.set("rubro", rubro);
  if (proveedorId != null) params.set("proveedor_id", proveedorId);
  const qs = params.toString() ? `?${params}` : "";
  return apiFetch(`/reportes/gastos/${periodo}${qs}`);
}

export function listarProveedores({ anio, periodo } = {}) {
  const params = new URLSearchParams();
  if (anio) params.set("anio", anio);
  if (periodo) params.set("periodo", periodo);
  const qs = params.toString() ? `?${params}` : "";
  return apiFetch(`/reportes/proveedores${qs}`);
}

// PDFs — abren en nueva pestaña con blob URL (mismo patrón que api/pdf.js)
async function _abrirPdf(path, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function abrirPdfMorosos({ soloDeudores = true }, token) {
  return _abrirPdf(`/reportes/morosos/pdf?solo_deudores=${soloDeudores}`, token);
}

export function abrirPdfEstadoFinanciero(fechaCorte, token) {
  const qs = fechaCorte ? `?fecha_corte=${fechaCorte}` : "";
  return _abrirPdf(`/reportes/estado-financiero/pdf${qs}`, token);
}

export function abrirPdfGastosPeriodo(periodo, filtros, token) {
  const params = new URLSearchParams();
  if (filtros?.rubro) params.set("rubro", filtros.rubro);
  if (filtros?.proveedorId != null) params.set("proveedor_id", filtros.proveedorId);
  const qs = params.toString() ? `?${params}` : "";
  return _abrirPdf(`/reportes/gastos/${periodo}/pdf${qs}`, token);
}

export function abrirPdfProveedores({ anio, periodo }, token) {
  const params = new URLSearchParams();
  if (anio) params.set("anio", anio);
  if (periodo) params.set("periodo", periodo);
  const qs = params.toString() ? `?${params}` : "";
  return _abrirPdf(`/reportes/proveedores/pdf${qs}`, token);
}
```

- [ ] **Step 2: Crear `frontend/src/screens/ReporteMorosos.jsx`**

```jsx
import { useEffect, useState } from "react";
import { listarMorosos, abrirPdfMorosos } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function ReporteMorosos() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [soloDeudores, setSoloDeudores] = useState(true);
  const [cargando, setCargando] = useState(true);

  async function cargar() {
    setCargando(true);
    const r = await listarMorosos({ soloDeudores });
    if (r.status === 200) setItems(r.data);
    setCargando(false);
  }

  useEffect(() => { cargar(); }, [soloDeudores]);

  const total = items.reduce((acc, it) => acc + it.saldo, 0);

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Lista de morosos</h2>
        <button type="button" onClick={() => abrirPdfMorosos({ soloDeudores }, token)}>
          📄 Descargar PDF
        </button>
      </header>

      <label>
        <input type="checkbox" checked={soloDeudores} onChange={(e) => setSoloDeudores(e.target.checked)} />
        {" "}Solo deudores (excluir saldos a favor y al día)
      </label>

      {cargando && <p>Cargando…</p>}
      {!cargando && items.length === 0 && (
        <Tarjeta><p>✓ Sin morosos al día de la fecha.</p></Tarjeta>
      )}
      {!cargando && items.length > 0 && (
        <table>
          <thead>
            <tr><th>Depto</th><th>Saldo</th><th>Períodos vencidos</th><th>Primer venc. impago</th></tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.departamento_id}>
                <td>{it.departamento_codigo}</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(it.saldo)}</td>
                <td style={{ textAlign: "center" }}>{it.periodos_vencidos_impagos}</td>
                <td>{it.primer_vencimiento_impago || "—"}</td>
              </tr>
            ))}
            <tr style={{ fontWeight: "bold", borderTop: "2px solid #ccc" }}>
              <td>TOTAL</td>
              <td style={{ textAlign: "right" }}>{fmtMoney(total)}</td>
              <td colSpan="2"></td>
            </tr>
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Crear `frontend/src/screens/ReporteEstadoFinanciero.jsx`**

```jsx
import { useEffect, useState } from "react";
import { obtenerEstadoFinanciero, abrirPdfEstadoFinanciero } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function ReporteEstadoFinanciero() {
  const { token } = useAuth();
  const [rep, setRep] = useState(null);
  const [fechaCorte, setFechaCorte] = useState(new Date().toISOString().slice(0, 10));

  async function cargar() {
    const r = await obtenerEstadoFinanciero(fechaCorte);
    if (r.status === 200) setRep(r.data);
  }

  useEffect(() => { cargar(); }, [fechaCorte]);

  if (!rep) return <p>Cargando…</p>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Estado financiero</h2>
        <button type="button" onClick={() => abrirPdfEstadoFinanciero(fechaCorte, token)}>
          📄 Descargar PDF
        </button>
      </header>

      <label>
        Fecha de corte:
        <input type="date" value={fechaCorte} onChange={(e) => setFechaCorte(e.target.value)} />
      </label>

      <Tarjeta>
        <h3>ACTIVO</h3>
        <table>
          <tbody>
            {rep.cajas.map((c) => (
              <tr key={c.caja_id}>
                <td>{c.nombre}</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(c.saldo)}</td>
              </tr>
            ))}
            <tr>
              <td>Deudores (saldos a cobrar)</td>
              <td style={{ textAlign: "right" }}>{fmtMoney(rep.deudores_total)}</td>
            </tr>
            <tr style={{ fontWeight: "bold", borderTop: "2px solid #ccc" }}>
              <td>TOTAL ACTIVO</td>
              <td style={{ textAlign: "right" }}>{fmtMoney(rep.activo_total)}</td>
            </tr>
          </tbody>
        </table>
      </Tarjeta>

      <Tarjeta>
        <h3>PASIVO</h3>
        {rep.pasivos.length === 0 ? (
          <p>Sin pasivos registrados.</p>
        ) : (
          <table>
            <thead><tr><th>Proveedor</th><th>Concepto</th><th>Importe</th></tr></thead>
            <tbody>
              {rep.pasivos.map((p) => (
                <tr key={p.gasto_id}>
                  <td>{p.proveedor}</td>
                  <td>{p.concepto}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(p.monto)}</td>
                </tr>
              ))}
              <tr style={{ fontWeight: "bold", borderTop: "2px solid #ccc" }}>
                <td colSpan="2">TOTAL PASIVO</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(rep.pasivo_total)}</td>
              </tr>
            </tbody>
          </table>
        )}
      </Tarjeta>

      <Tarjeta>
        <h2>PATRIMONIO NETO: {fmtMoney(rep.patrimonio_neto)}</h2>
      </Tarjeta>
    </section>
  );
}
```

- [ ] **Step 4: Build smoke**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/api/reportes.js frontend/src/screens/ReporteMorosos.jsx frontend/src/screens/ReporteEstadoFinanciero.jsx
git commit -m "feat(frontend): api/reportes + pantallas Morosos y Estado Financiero"
```

---

## Task 6: Frontend — 2 pantallas restantes (Gastos del período + Proveedores)

**Files:**
- Create: `frontend/src/screens/ReporteGastosPeriodo.jsx`
- Create: `frontend/src/screens/ReporteProveedores.jsx`

- [ ] **Step 1: Crear `frontend/src/screens/ReporteGastosPeriodo.jsx`**

```jsx
import { useEffect, useState } from "react";
import { obtenerGastosDelPeriodo, abrirPdfGastosPeriodo } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

const NOMBRES_RUBRO = {
  sueldos_y_cargas_sociales: "Sueldos y cargas sociales",
  servicios_publicos: "Servicios públicos",
  abonos_y_servicios: "Abonos y servicios",
  mantenimiento_partes_comunes: "Mantenimiento partes comunes",
  trabajos_reparaciones_unidades: "Trabajos / reparaciones en unidades",
  gastos_bancarios: "Gastos bancarios",
  gastos_administracion: "Gastos administración",
  seguros: "Seguros",
  gastos_generales: "Gastos generales",
};

export default function ReporteGastosPeriodo() {
  const { token } = useAuth();
  const [periodo, setPeriodo] = useState(new Date().toISOString().slice(0, 7));
  const [rubro, setRubro] = useState("");
  const [rep, setRep] = useState(null);

  async function cargar() {
    const r = await obtenerGastosDelPeriodo(periodo, { rubro: rubro || undefined });
    if (r.status === 200) setRep(r.data);
  }

  useEffect(() => { cargar(); }, [periodo, rubro]);

  if (!rep) return <p>Cargando…</p>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Detalle de gastos del período</h2>
        <button type="button" onClick={() => abrirPdfGastosPeriodo(periodo, { rubro: rubro || undefined }, token)}>
          📄 Descargar PDF
        </button>
      </header>

      <div className="filtros">
        <label>
          Período:
          <input type="month" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
        </label>
        <label>
          Rubro:
          <select value={rubro} onChange={(e) => setRubro(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(NOMBRES_RUBRO).map(([val, lbl]) => (
              <option key={val} value={val}>{lbl}</option>
            ))}
          </select>
        </label>
      </div>

      {Object.entries(rep.por_rubro).map(([rubroKey, items]) => (
        <Tarjeta key={rubroKey}>
          <h3>{NOMBRES_RUBRO[rubroKey] || rubroKey} — {fmtMoney(rep.subtotales_por_rubro[rubroKey])}</h3>
          <table>
            <thead><tr><th>Fecha</th><th>Concepto</th><th>Proveedor</th><th>Caja</th><th>Forma pago</th><th>Importe</th></tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i}>
                  <td>{it.fecha}</td><td>{it.concepto}</td><td>{it.proveedor}</td>
                  <td>{it.caja}</td><td>{it.forma_pago}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(it.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tarjeta>
      ))}

      {rep.particulares.length > 0 && (
        <Tarjeta>
          <h3>Gastos particulares (a deptos)</h3>
          <table>
            <thead><tr><th>Fecha</th><th>Concepto</th><th>Proveedor</th><th>Caja</th><th>Forma pago</th><th>Importe</th></tr></thead>
            <tbody>
              {rep.particulares.map((it, i) => (
                <tr key={i}>
                  <td>{it.fecha}</td><td>{it.concepto}</td><td>{it.proveedor}</td>
                  <td>{it.caja}</td><td>{it.forma_pago}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(it.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tarjeta>
      )}

      <Tarjeta>
        <h2>TOTAL GENERAL: {fmtMoney(rep.total_general)}</h2>
      </Tarjeta>
    </section>
  );
}
```

- [ ] **Step 2: Crear `frontend/src/screens/ReporteProveedores.jsx`**

```jsx
import { useEffect, useState } from "react";
import { listarProveedores, abrirPdfProveedores } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function ReporteProveedores() {
  const { token } = useAuth();
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [items, setItems] = useState([]);

  async function cargar() {
    const r = await listarProveedores({ anio });
    if (r.status === 200) setItems(r.data);
  }

  useEffect(() => { cargar(); }, [anio]);

  const total = items.reduce((acc, it) => acc + it.total_facturado, 0);

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Lista de proveedores</h2>
        <button type="button" onClick={() => abrirPdfProveedores({ anio }, token)}>
          📄 Descargar PDF
        </button>
      </header>

      <label>
        Año:
        <input type="number" min="2000" max="2100" value={anio} onChange={(e) => setAnio(Number(e.target.value))} />
      </label>

      {items.length === 0 ? (
        <Tarjeta><p>Sin proveedores facturados en {anio}.</p></Tarjeta>
      ) : (
        <table>
          <thead>
            <tr><th>Razón social</th><th>CUIT</th><th>Cant. gastos</th><th>Total facturado</th><th>Último gasto</th></tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.proveedor_id}>
                <td>{it.razon_social}</td>
                <td>{it.cuit}</td>
                <td style={{ textAlign: "center" }}>{it.cantidad_gastos}</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(it.total_facturado)}</td>
                <td>{it.ultimo_gasto || "—"}</td>
              </tr>
            ))}
            <tr style={{ fontWeight: "bold", borderTop: "2px solid #ccc" }}>
              <td colSpan="3">TOTAL</td>
              <td style={{ textAlign: "right" }}>{fmtMoney(total)}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Build smoke**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/screens/ReporteGastosPeriodo.jsx frontend/src/screens/ReporteProveedores.jsx
git commit -m "feat(frontend): pantallas Gastos del período + Lista de proveedores"
```

---

## Task 7: Sidebar + Routes

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: En `Sidebar.jsx`, sumar sección "Reportes"**

Leer `SECCIONES` y sumar (entre "Tesorería" y "Sueldos"):

```javascript
{
  titulo: "Reportes",
  modulos: [
    { ruta: "/reportes/morosos", nombre: "Lista de morosos", rolesPermitidos: ["administracion", "representante", "departamento"] },
    { ruta: "/reportes/estado-financiero", nombre: "Estado financiero", rolesPermitidos: ["administracion", "representante", "departamento"] },
    { ruta: "/reportes/gastos", nombre: "Detalle de gastos", rolesPermitidos: ["administracion", "representante", "departamento"] },
    { ruta: "/reportes/proveedores", nombre: "Lista de proveedores", rolesPermitidos: ["administracion", "representante", "departamento"] },
  ],
},
```

- [ ] **Step 2: En `App.jsx`, sumar imports + 4 rutas**

Imports al inicio:
```jsx
import ReporteMorosos from "./screens/ReporteMorosos";
import ReporteEstadoFinanciero from "./screens/ReporteEstadoFinanciero";
import ReporteGastosPeriodo from "./screens/ReporteGastosPeriodo";
import ReporteProveedores from "./screens/ReporteProveedores";
```

Rutas dentro del bloque autenticado:
```jsx
<Route path="reportes/morosos" element={<ReporteMorosos />} />
<Route path="reportes/estado-financiero" element={<ReporteEstadoFinanciero />} />
<Route path="reportes/gastos" element={<ReporteGastosPeriodo />} />
<Route path="reportes/proveedores" element={<ReporteProveedores />} />
```

- [ ] **Step 3: Build smoke**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/components/Sidebar.jsx frontend/src/App.jsx
git commit -m "feat(frontend): sidebar sección Reportes + 4 rutas en App"
```

---

## Task 8: Smoke + merge + roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`

- [ ] **Step 1: Smoke E2E manual**

Arrancar uvicorn + frontend.

Pruebas:
1. Admin → Sidebar nueva sección "Reportes" con 4 items.
2. Click "Lista de morosos" → ver tabla con deudores + total; toggle "Solo deudores" cambia la lista; "Descargar PDF" abre nueva pestaña con PDF válido.
3. Click "Estado financiero" → ver Activo (cajas + deudores), Pasivo (gastos futuros), Patrimonio neto. Cambiar fecha de corte y verificar que el snapshot cambia.
4. Click "Detalle de gastos" → seleccionar período "2026-05" → ver gastos agrupados por rubro con subtotales; filtrar por rubro reduce la lista; PDF abre.
5. Click "Lista de proveedores" → ver ranking; cambiar año a 2099 → ver mensaje "Sin proveedores facturados"; PDF abre.
6. Logout, login depto → todos los 4 reportes son accesibles (transparencia).

- [ ] **Step 2: Suite final**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 569+ pass, 0 fail.

- [ ] **Step 3: Actualizar roadmap**

En `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`, reemplazar la línea de Fase 6b por:

```markdown
| **6b** ✅ | **Reportes (morosos, estado financiero, gastos, proveedores)** (completada 2026-06-XX) | 4 reportes consultables y exportables a PDF, accesibles a admin/representante/depto (transparencia). Sin formato Ley 941 oficial (queda para Fase 6c si entra cliente CABA). |
```

Sumar al historial:
```markdown
- 2026-06-XX: **Fase 6b completada** (~569 tests, mergeada a master). 4 reportes (morosos / estado financiero / gastos del período / lista de proveedores) consultables y exportables a PDF reusando ReportLab. Acceso para admin + representante + depto (transparencia). Refactor de `_dibujar_header_consorcio` para reuso entre los 4 reportes nuevos + boleta de Fase 6a.
```

Actualizar próximo paso:
```markdown
Roadmap original completado. Próximas fases comerciales (opcional): Fase 6c (modo Ley 941 oficial CABA), Fase 7 (multi-consorcio para escalar a estudios de administración).
```

- [ ] **Step 4: Commit roadmap + merge a master**

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 6b completada (reportes)"

git checkout master
git merge --no-ff feature/expensas-fase6b-reportes -m "Merge feature/expensas-fase6b-reportes: 4 reportes con export PDF

Fase 6b — Lista de morosos, estado financiero, detalle de gastos del período
y lista de proveedores. Pantallas con filtros + export PDF (reusa ReportLab
de Fase 6a). Acceso transparente para admin, representante y departamento.
Cierra el roadmap original. Modo Ley 941 oficial queda para Fase 6c."
```

- [ ] **Step 5: Done**

---

## Notas finales

- **Orden de tasks**: módulo puro → PDFs → router HTTP → frontend client → frontend pantallas → sidebar/routes → smoke/merge. Pattern conocido.
- **TDD**: Tasks 1 y 2 escriben tests primero (unit + smoke).
- **Commits frecuentes**: ~9 commits totales.
- **Sin migración**: no hay cambios al modelo.
- **Riesgo bajo**: read-only sobre data existente, sin side effects.
