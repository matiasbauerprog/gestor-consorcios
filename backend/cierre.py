"""Módulo de cierre de período — función pura.

Calcula el preview completo del cierre de un período sin escribir nada. El
endpoint /periodos/{periodo}/cerrar consume el preview y persiste en una
transacción atómica.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .cuenta_corriente import calcular_estado_cuenta
from .models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    Consorcio,
    Departamento,
    EstadoExpensa,
    Expensa,
    Gasto,
    PeriodoCerrado,
    Rubro,
)


@dataclass
class Validacion:
    tipo: Literal["bloqueante", "warning"]
    codigo: str
    mensaje: str


@dataclass
class LineaDetalleExpensa:
    rubro: Rubro
    clase_prorrateo_id: int | None
    departamento_origen_id: int | None
    concepto: str
    monto: float


@dataclass
class ExpensaACrear:
    departamento_id: int
    saldo_anterior: float
    monto_primer_vencimiento: float
    monto_segundo_vencimiento: float
    detalle: list[LineaDetalleExpensa] = field(default_factory=list)


@dataclass
class InteresACrear:
    departamento_id: int
    monto: float
    descripcion: str


@dataclass
class PreviewCierre:
    periodo: str
    cerrado: bool
    fecha_primer_vencimiento: date
    fecha_segundo_vencimiento: date
    validaciones: list[Validacion] = field(default_factory=list)
    expensas: list[ExpensaACrear] = field(default_factory=list)
    intereses: list[InteresACrear] = field(default_factory=list)
    total_expensado: float = 0.0
    total_intereses: float = 0.0

    @property
    def puede_cerrar(self) -> bool:
        return not self.cerrado and not any(
            v.tipo == "bloqueante" for v in self.validaciones
        )


def _calcular_fechas_default(
    periodo: str, config: Consorcio
) -> tuple[date, date]:
    """fecha_1 = día N del mes siguiente al período. fecha_2 = fecha_1 + M días."""
    year, month = map(int, periodo.split("-"))
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    fecha_1 = date(next_year, next_month, config.dia_primer_vencimiento)
    fecha_2 = fecha_1 + timedelta(days=config.dias_entre_vencimientos)
    return fecha_1, fecha_2


def calcular_intereses_al_cierre(
    db: Session, depto_id: int, fecha_corte: date
) -> tuple[float, str]:
    """Suma intereses sobre todas las expensas del depto con saldo > 0 cuyo
    2° vencimiento ya pasó. Tasa diaria = mensual_pct / 100 / 30.

    Returns (monto_total, descripcion_agregada). Si monto == 0, retorna (0.0, "").
    """
    config = db.scalar(select(Consorcio))
    if config is None:
        return 0.0, ""

    estado = calcular_estado_cuenta(db, depto_id, hoy=fecha_corte)
    tasa_diaria = config.tasa_interes_mensual_pct / 100 / 30

    intereses_por_expensa: list[tuple[str, float]] = []
    for expensa in db.scalars(
        select(Expensa).where(Expensa.departamento_id == depto_id)
    ).all():
        calc = estado.por_expensa.get(expensa.id)
        if calc is None or calc.monto_pendiente <= 0.001:
            continue
        if expensa.fecha_segundo_vencimiento >= fecha_corte:
            continue
        dias_mora = (fecha_corte - expensa.fecha_segundo_vencimiento).days
        if dias_mora <= 0:
            continue
        interes = round(calc.monto_pendiente * tasa_diaria * dias_mora, 2)
        if interes > 0:
            intereses_por_expensa.append((expensa.periodo, interes))

    total = round(sum(m for _, m in intereses_por_expensa), 2)
    if total <= 0:
        return 0.0, ""

    partes = ", ".join(
        f"${m:.2f} por {p}" for p, m in intereses_por_expensa
    )
    descripcion = f"Intereses al {fecha_corte.isoformat()} sobre {len(intereses_por_expensa)} expensa(s) vencida(s): {partes}"
    return total, descripcion


def calcular_preview_cierre(
    db: Session,
    periodo: str,
    fecha_primer_venc: date | None = None,
    fecha_segundo_venc: date | None = None,
) -> PreviewCierre:
    cerrado = db.get(PeriodoCerrado, periodo) is not None
    config = db.scalar(select(Consorcio))

    validaciones: list[Validacion] = []

    if config is None:
        validaciones.append(Validacion(
            "bloqueante",
            "configuracion_incompleta",
            "Falta cargar la configuración del consorcio antes de cerrar períodos.",
        ))
        return PreviewCierre(
            periodo=periodo,
            cerrado=cerrado,
            fecha_primer_vencimiento=date.today(),
            fecha_segundo_vencimiento=date.today() + timedelta(days=10),
            validaciones=validaciones,
        )

    # Fechas: default por regla si no vinieron del caller.
    if fecha_primer_venc is None or fecha_segundo_venc is None:
        f1_def, f2_def = _calcular_fechas_default(periodo, config)
        fecha_1 = fecha_primer_venc or f1_def
        fecha_2 = fecha_segundo_venc or f2_def
    else:
        fecha_1 = fecha_primer_venc
        fecha_2 = fecha_segundo_venc

    if fecha_2 <= fecha_1:
        validaciones.append(Validacion(
            "bloqueante",
            "fechas_invalidas",
            "La fecha de 2° vencimiento debe ser posterior a la del 1°.",
        ))

    if cerrado:
        validaciones.append(Validacion(
            "bloqueante",
            "periodo_ya_cerrado",
            f"El período {periodo} ya fue cerrado.",
        ))

    # Validar coeficientes y gastos huérfanos.
    gastos_periodo = list(db.scalars(
        select(Gasto).where(Gasto.periodo == periodo)
    ).all())

    huerfanos = [
        g for g in gastos_periodo
        if g.clase_prorrateo_id is None and g.departamento_id is None
    ]
    if huerfanos:
        validaciones.append(Validacion(
            "bloqueante",
            "gastos_huerfanos",
            f"Hay {len(huerfanos)} gasto(s) del período sin clase de prorrateo ni departamento asignado.",
        ))

    if not gastos_periodo:
        validaciones.append(Validacion(
            "warning",
            "sin_gastos",
            f"El período {periodo} no tiene gastos cargados. Las expensas serán $0.",
        ))

    # Clases activas con gastos del período: validar coeficientes.
    clases_activas = list(db.scalars(
        select(ClaseProrrateo).where(ClaseProrrateo.activa.is_(True))
    ).all())
    deptos = list(db.scalars(select(Departamento)).all())

    clases_con_gasto_ids = {
        g.clase_prorrateo_id for g in gastos_periodo if g.clase_prorrateo_id is not None
    }
    for clase in clases_activas:
        coefs = list(db.scalars(
            select(CoeficienteDepartamento).where(
                CoeficienteDepartamento.clase_prorrateo_id == clase.id
            )
        ).all())
        if clase.id in clases_con_gasto_ids:
            deptos_con_coef = {c.departamento_id for c in coefs}
            faltantes = [d for d in deptos if d.id not in deptos_con_coef]
            if faltantes:
                validaciones.append(Validacion(
                    "bloqueante",
                    "coeficientes_faltantes",
                    f"La clase '{clase.nombre}' tiene gastos en el período pero faltan coeficientes para {len(faltantes)} depto(s).",
                ))
            suma = sum(c.porcentaje for c in coefs)
            if abs(suma - 100.0) > 0.01:
                validaciones.append(Validacion(
                    "bloqueante",
                    "coeficientes_no_suman_100",
                    f"La clase '{clase.nombre}' tiene coeficientes que suman {suma:.2f}% (debe ser 100%).",
                ))
        else:
            validaciones.append(Validacion(
                "warning",
                "clases_sin_gastos",
                f"La clase '{clase.nombre}' está activa pero no tiene gastos en el período (no se prorratea).",
            ))

    return _completar_preview(
        db, periodo, cerrado, fecha_1, fecha_2,
        validaciones, gastos_periodo, config,
    )


def _completar_preview(
    db: Session,
    periodo: str,
    cerrado: bool,
    fecha_1: date,
    fecha_2: date,
    validaciones: list[Validacion],
    gastos_periodo: list[Gasto],
    config: Consorcio,
) -> PreviewCierre:
    """Calcula expensas, intereses y saldo anterior. Si ya está cerrado,
    devuelve preview vacío de expensas."""
    preview = PreviewCierre(
        periodo=periodo,
        cerrado=cerrado,
        fecha_primer_vencimiento=fecha_1,
        fecha_segundo_vencimiento=fecha_2,
        validaciones=validaciones,
    )

    if cerrado:
        return preview

    deptos = list(db.scalars(select(Departamento)).all())

    lineas_por_depto: dict[int, list[LineaDetalleExpensa]] = {d.id: [] for d in deptos}

    for gasto in gastos_periodo:
        if gasto.departamento_id is not None:
            lineas_por_depto.setdefault(gasto.departamento_id, []).append(
                LineaDetalleExpensa(
                    rubro=gasto.rubro,
                    clase_prorrateo_id=None,
                    departamento_origen_id=gasto.departamento_id,
                    concepto=gasto.concepto,
                    monto=round(gasto.monto, 2),
                )
            )
        elif gasto.clase_prorrateo_id is not None:
            coefs = list(db.scalars(
                select(CoeficienteDepartamento).where(
                    CoeficienteDepartamento.clase_prorrateo_id == gasto.clase_prorrateo_id
                )
            ).all())
            for c in coefs:
                monto_depto = round(gasto.monto * c.porcentaje / 100, 2)
                if monto_depto <= 0:
                    continue
                lineas_por_depto.setdefault(c.departamento_id, []).append(
                    LineaDetalleExpensa(
                        rubro=gasto.rubro,
                        clase_prorrateo_id=gasto.clase_prorrateo_id,
                        departamento_origen_id=None,
                        concepto=gasto.concepto,
                        monto=monto_depto,
                    )
                )

    fecha_corte = date.today()
    intereses_por_depto: dict[int, float] = {}
    for d in deptos:
        monto, descripcion = calcular_intereses_al_cierre(db, d.id, fecha_corte)
        if monto > 0:
            preview.intereses.append(InteresACrear(
                departamento_id=d.id,
                monto=monto,
                descripcion=descripcion,
            ))
            intereses_por_depto[d.id] = monto

    if intereses_por_depto:
        preview.validaciones.append(Validacion(
            "warning",
            "deptos_con_saldo_vencido",
            f"{len(intereses_por_depto)} depto(s) con saldo vencido. Se calcularán intereses al cierre.",
        ))

    recargo = config.recargo_segundo_vencimiento_pct / 100
    for d in deptos:
        detalle = lineas_por_depto.get(d.id, [])
        monto_1 = round(sum(l.monto for l in detalle), 2)
        if monto_1 <= 0:
            continue
        monto_2 = round(monto_1 * (1 + recargo), 2)

        saldo_act = calcular_estado_cuenta(db, d.id, hoy=fecha_corte).saldo_total
        saldo_anterior = round(saldo_act + intereses_por_depto.get(d.id, 0.0), 2)

        preview.expensas.append(ExpensaACrear(
            departamento_id=d.id,
            saldo_anterior=saldo_anterior,
            monto_primer_vencimiento=monto_1,
            monto_segundo_vencimiento=monto_2,
            detalle=detalle,
        ))

    preview.total_expensado = round(sum(e.monto_primer_vencimiento for e in preview.expensas), 2)
    preview.total_intereses = round(sum(i.monto for i in preview.intereses), 2)
    return preview
