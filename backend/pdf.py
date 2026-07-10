"""Generación del PDF de boleta de liquidación (Fase 6a).

Función pura: lee de la DB lo necesario, arma el PDF con ReportLab.
No persiste nada. ReportLab es Python puro — sin deps del SO.
"""
from collections import defaultdict
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Consorcio,
    Departamento,
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    TipoMovimiento,
)

_RUBRO_LABELS = {
    "sueldos_y_cargas_sociales": "Sueldos y cargas sociales",
    "servicios_publicos": "Servicios públicos",
    "abonos_y_servicios": "Abonos y servicios",
    "mantenimiento_partes_comunes": "Mantenimiento partes comunes",
    "trabajos_reparaciones_unidades": "Trabajos / reparaciones en unidades",
    "gastos_bancarios": "Gastos bancarios",
    "gastos_administracion": "Gastos administración",
    "seguros": "Seguros",
    "gastos_generales": "Gastos generales",
}


def _money(n: float) -> str:
    return f"${n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _rubro_label(rubro_value: str) -> str:
    return _RUBRO_LABELS.get(rubro_value, rubro_value)


def _dibujar_header_consorcio(story, config: Consorcio, titulo: str, subtitulo: str = "") -> None:
    """Suma al story el header común a todos los PDFs del consorcio."""
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    normal = styles["Normal"]
    small = ParagraphStyle("small_header", parent=normal, fontSize=8, textColor=colors.grey)

    story.append(Paragraph(config.nombre, h1))
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


def generar_pdf_boleta(expensa: Expensa, db: Session) -> bytes:
    """Genera el PDF de la boleta. Devuelve bytes."""
    config = db.get(Consorcio, expensa.consorcio_id)
    departamento = db.get(Departamento, expensa.departamento_id)

    pagos = list(db.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.departamento_id == expensa.departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.pago_recibido,
        ).order_by(MovimientoCuenta.fecha)
    ).all())

    intereses = list(db.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.departamento_id == expensa.departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.interes_punitorio,
        )
    ).all())

    detalles = list(db.scalars(
        select(ExpensaDetalle).where(ExpensaDetalle.expensa_id == expensa.id)
    ).all())

    gastos_por_rubro: dict[str, list[ExpensaDetalle]] = defaultdict(list)
    for d in detalles:
        gastos_por_rubro[d.rubro.value].append(d)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Boleta {expensa.periodo} - Depto {departamento.codigo}",
    )

    styles = getSampleStyleSheet()
    h2 = styles["Heading2"]
    h3 = styles["Heading3"]
    normal = styles["Normal"]

    story = []

    # Header común
    _dibujar_header_consorcio(
        story, config,
        titulo=f"Boleta Nº {expensa.id} · Período {expensa.periodo}",
        subtitulo=f"Emitida {date.today().isoformat()}",
    )

    # Depto
    story.append(Paragraph(f"Departamento {departamento.codigo}", h2))
    story.append(Spacer(1, 0.3 * cm))

    # Liquidación
    story.append(Paragraph("Su liquidación", h3))
    liq_data = [["Concepto", "Importe"]]
    liq_data.append(["Saldo anterior", _money(expensa.saldo_anterior)])
    for mov in pagos:
        liq_data.append([f"{mov.fecha} · {mov.descripcion}", f"({_money(mov.monto)})"])
    for mov in intereses:
        liq_data.append([f"Intereses · {mov.descripcion}", _money(mov.monto)])
    liq_tbl = Table(liq_data, colWidths=[12 * cm, 4 * cm])
    liq_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(liq_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Gastos por rubro
    story.append(Paragraph("Gastos del período (su prorrateo)", h3))
    for rubro, items in gastos_por_rubro.items():
        sub_total = sum(it.monto for it in items)
        story.append(Paragraph(
            f"<b>{_rubro_label(rubro)}</b> — {_money(sub_total)}", normal
        ))
        gas_data = [[it.concepto, _money(it.monto)] for it in items]
        gas_tbl = Table(gas_data, colWidths=[12 * cm, 4 * cm])
        gas_tbl.setStyle(TableStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (0, -1), 16),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
        ]))
        story.append(gas_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Totales
    story.append(Paragraph("Total a pagar", h3))
    tot_data = [
        [f"1° vencimiento {expensa.fecha_primer_vencimiento}",
         _money(expensa.monto_primer_vencimiento)],
        [f"2° vencimiento {expensa.fecha_segundo_vencimiento} (+recargo)",
         _money(expensa.monto_segundo_vencimiento)],
    ]
    tot_tbl = Table(tot_data, colWidths=[12 * cm, 4 * cm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.grey),
        ("LINEABOVE", (0, 1), (-1, 1), 0.5, colors.grey),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # Datos para pagar
    story.append(Paragraph("Para pagar", h3))
    story.append(Paragraph(
        f"{config.banco_nombre} · CBU {config.banco_cbu}", normal
    ))
    if config.banco_alias:
        story.append(Paragraph(f"Alias: {config.banco_alias}", normal))
    story.append(Paragraph(f"Titular: {config.banco_titular}", normal))

    doc.build(story)
    return buf.getvalue()


def generar_pdf_morosos(items, fecha: date, config: Consorcio) -> bytes:
    """PDF del reporte de morosos."""
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
        story.append(Paragraph("Sin morosos al día de la fecha.", getSampleStyleSheet()["Normal"]))
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


def generar_pdf_estado_financiero(reporte, config: Consorcio) -> bytes:
    """PDF del estado financiero (activo/pasivo/patrimonio)."""
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


def generar_pdf_gastos_periodo(reporte, config: Consorcio) -> bytes:
    """PDF del detalle de gastos del período."""
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


def generar_pdf_lista_proveedores(items, anio: int, config: Consorcio) -> bytes:
    """PDF del ranking de proveedores."""
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


def generar_pdf_movimientos_caja(
    movimientos: list,  # list[MovimientoCaja]
    cajas: list,  # list[Caja]
    desde: date,
    hasta: date,
    config: Consorcio,
) -> bytes:
    """Genera el PDF de movimientos de caja de un rango de fechas, agrupado
    por caja con totales de ingresos, egresos y saldo neto.

    `movimientos` deben venir filtrados por consorcio + rango.
    `cajas` debe incluir todas las cajas del consorcio (para agrupar aunque
    no tengan movimientos en el rango).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Movimientos de caja {desde} a {hasta}",
    )
    styles = getSampleStyleSheet()
    h3 = styles["Heading3"]
    normal = styles["Normal"]
    small = ParagraphStyle("small_mov", parent=normal, fontSize=8, textColor=colors.grey)

    story = []
    _dibujar_header_consorcio(
        story, config,
        titulo="Movimientos de caja",
        subtitulo=f"Período: {desde.isoformat()} a {hasta.isoformat()}",
    )

    # Agrupar por caja_id
    caja_por_id = {c.id: c for c in cajas}
    movs_por_caja: dict[int, list] = defaultdict(list)
    for m in movimientos:
        movs_por_caja[m.caja_id].append(m)

    total_ingresos_gral = 0.0
    total_egresos_gral = 0.0

    for caja in sorted(cajas, key=lambda c: c.nombre):
        movs = sorted(
            movs_por_caja.get(caja.id, []),
            key=lambda m: (m.fecha, m.id),
        )
        if not movs:
            continue

        story.append(Paragraph(caja.nombre, h3))

        data = [["Fecha", "Tipo", "Descripción", "Monto"]]
        ingresos_c = egresos_c = 0.0
        for m in movs:
            tipo_str = m.tipo.value if hasattr(m.tipo, "value") else str(m.tipo)
            signo = "+" if tipo_str == "ingreso" else "-"
            data.append([
                m.fecha.isoformat(),
                tipo_str.capitalize(),
                (m.descripcion or "")[:60],
                f"{signo}{_money(m.monto)}",
            ])
            if tipo_str == "ingreso":
                ingresos_c += m.monto
            else:
                egresos_c += m.monto

        neto = ingresos_c - egresos_c
        data.append([
            "", "", "Neto del período",
            _money(neto),
        ])

        tbl = Table(data, colWidths=[2.5 * cm, 2.2 * cm, 9 * cm, 3 * cm])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4 * cm))

        total_ingresos_gral += ingresos_c
        total_egresos_gral += egresos_c

    if not any(movs_por_caja.values()):
        story.append(Paragraph("Sin movimientos en el período.", normal))
    else:
        # Totales generales
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Totales del período", h3))
        totales = [
            ["Ingresos", _money(total_ingresos_gral)],
            ["Egresos", _money(total_egresos_gral)],
            ["Neto", _money(total_ingresos_gral - total_egresos_gral)],
        ]
        tbl_t = Table(totales, colWidths=[8 * cm, 3 * cm])
        tbl_t.setStyle(TableStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(tbl_t)

    doc.build(story)
    return buf.getvalue()
