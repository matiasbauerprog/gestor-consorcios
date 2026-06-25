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
    ConfiguracionConsorcio,
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


def generar_pdf_boleta(expensa: Expensa, db: Session) -> bytes:
    """Genera el PDF de la boleta. Devuelve bytes."""
    config = db.get(ConfiguracionConsorcio, 1)
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
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    h3 = styles["Heading3"]
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, textColor=colors.grey)

    story = []

    # Header
    story.append(Paragraph(config.consorcio_nombre, h1))
    story.append(Paragraph(
        f"{config.consorcio_domicilio} · CUIT {config.consorcio_cuit}", normal
    ))
    story.append(Paragraph(
        f"Admin: {config.admin_nombre} (RPA {config.admin_rpa}) · "
        f"{config.admin_email} · {config.admin_telefono}", small
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"<b>Boleta Nº</b> {expensa.id} · "
        f"<b>Período</b> {expensa.periodo} · "
        f"<b>Emitida</b> {date.today().isoformat()}", normal
    ))
    story.append(Spacer(1, 0.5 * cm))

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
