"""Reportes — Fase 6b.

Funciones de lectura: leen de la DB y devuelven dataclasses listas para
serializar (a JSON via Pydantic) o renderizar a PDF. No mutan nada, con una
sola excepción: `calcular_morosos` devenga los recargos por mora vencidos
antes de leer, porque un reporte de deuda que no los ve la subestima.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .caja_saldo import MovimientoSnapshot, calcular_saldo
from .cuenta_corriente import calcular_estado_cuenta
from .models import (
    Caja,
    Departamento,
    Expensa,
    Gasto,
    MovimientoCaja,
    Proveedor,
)
from .recargos import devengar_recargos_y_marcar


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

def calcular_morosos(db: Session, consorcio_id: int, solo_deudores: bool = True) -> list[ItemMoroso]:
    """Calcula la lista de morosos iterando los Departamentos del consorcio."""
    deptos = list(db.scalars(
        select(Departamento)
        .where(Departamento.consorcio_id == consorcio_id)
        .order_by(Departamento.id)
    ).all())
    items: list[ItemMoroso] = []
    hoy = date.today()

    # Devengamiento perezoso: el reporte de morosos tiene que ver el recargo
    # ya emitido, si no subestima la deuda. Un solo commit para todo el
    # padrón, no uno por departamento.
    hubo_recargos = False
    for d in deptos:
        if devengar_recargos_y_marcar(db, d.id, hoy=hoy):
            hubo_recargos = True
    if hubo_recargos:
        db.commit()

    for d in deptos:
        estado = calcular_estado_cuenta(db, d.id)
        saldo = round(estado.saldo_total, 2)
        if solo_deudores and saldo <= 0.01:
            continue

        expensas_vencidas = list(db.scalars(
            select(Expensa)
            .where(
                Expensa.departamento_id == d.id,
                Expensa.fecha_segundo_vencimiento < hoy,
            )
            .order_by(Expensa.fecha_primer_vencimiento)
        ).all())
        periodos_vencidos = len(expensas_vencidas) if saldo > 0.01 else 0
        primer_imp = expensas_vencidas[0].fecha_primer_vencimiento if (expensas_vencidas and saldo > 0.01) else None

        items.append(ItemMoroso(
            departamento_id=d.id,
            departamento_codigo=d.codigo,
            saldo=saldo,
            periodos_vencidos_impagos=periodos_vencidos,
            primer_vencimiento_impago=primer_imp,
        ))

    items.sort(key=lambda x: x.saldo, reverse=True)
    return items


def calcular_estado_financiero(db: Session, consorcio_id: int, fecha_corte: date) -> EstadoFinancieroReporte:
    """Snapshot patrimonial a una fecha, scoped al consorcio."""
    cajas_db = list(db.scalars(
        select(Caja).where(
            Caja.activa == True,  # noqa: E712
            Caja.consorcio_id == consorcio_id,
        ).order_by(Caja.id)
    ).all())
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

    morosos = calcular_morosos(db, consorcio_id, solo_deudores=True)
    deudores_total = sum(m.saldo for m in morosos)

    # Un gasto es pasivo si todavía no se pagó, o si su pago cae después del
    # corte. La primera rama es la que importa desde que los recurrentes se
    # materializan impagos con `fecha_pago` al día 1 del período (siempre
    # pasada) y sin MovimientoCaja: sin ella no descontaban de la caja ni
    # figuraban como deuda, y el patrimonio neto salía inflado.
    gastos_pendientes = list(db.scalars(
        select(Gasto).where(
            Gasto.consorcio_id == consorcio_id,
            or_(
                Gasto.pagado == False,  # noqa: E712
                Gasto.fecha_pago > fecha_corte,
            ),
        )
    ).all())
    pasivos: list[ItemPasivoGasto] = []
    for g in gastos_pendientes:
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
    consorcio_id: int,
    periodo: str,
    rubro: str | None = None,
    proveedor_id: int | None = None,
) -> GastosDelPeriodoReporte:
    """Detalle de gastos de un período YYYY-MM, agrupado por rubro y separando particulares."""
    q = select(Gasto).where(
        Gasto.periodo == periodo,
        Gasto.consorcio_id == consorcio_id,
    )
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
    consorcio_id: int,
    anio: int,
    periodo: str | None = None,
) -> list[ItemProveedor]:
    """Ranking de proveedores por monto facturado en un año (opcional restringir a un período)."""
    q = select(Gasto).where(
        Gasto.periodo.like(f"{anio}-%"),
        Gasto.consorcio_id == consorcio_id,
    )
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
