"""Módulo de cierre de período — cálculo del preview.

Calcula el preview completo del cierre de un período. No persiste nada del
cierre en sí: el endpoint /periodos/{periodo}/cerrar consume el preview y
escribe las expensas y los intereses en una única transacción.

La única escritura propia del preview es el devengamiento de los recargos por
mora ya vencidos, que tiene que estar materializado antes de leer los saldos
que arrastra el cierre. Ese commit es independiente y ocurre antes de que se
evalúe `puede_cerrar`: si el cierre después se rechaza, los recargos quedan
igual — son deuda ya ganada, no parte del cierre —, pero por eso la
atomicidad es del cierre y no del request entero.
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
from .recargos import devengar_recargos_y_marcar


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
    db: Session, consorcio_id: int, depto_id: int, fecha_corte: date  # noqa: ARG001
) -> tuple[float, str]:
    """Suma los intereses ya calculados por `calcular_estado_cuenta` sobre
    todas las expensas del depto con interés acumulado > 0.

    No recalcula la mora: delega en `calcular_estado_cuenta`, que es la única
    fuente de verdad del interés devengado por expensa (base = monto exigible,
    no el pendiente que ya arrastra intereses de cierres anteriores). Así el
    cierre nunca compone interés sobre interés.

    `consorcio_id` queda sin uso en el cuerpo — se mantiene en la firma porque
    hay llamadores que lo pasan posicionalmente.

    Returns (monto_total, descripcion_agregada). Si monto == 0, retorna (0.0, "").
    """
    estado = calcular_estado_cuenta(db, depto_id, hoy=fecha_corte)

    intereses_por_expensa: list[tuple[str, float]] = []
    for expensa in db.scalars(
        select(Expensa).where(Expensa.departamento_id == depto_id)
    ).all():
        calc = estado.por_expensa.get(expensa.id)
        if calc is None or calc.interes_acumulado <= 0.001:
            continue
        intereses_por_expensa.append((expensa.periodo, calc.interes_acumulado))

    total = round(sum(m for _, m in intereses_por_expensa), 2)
    if total <= 0:
        return 0.0, ""

    partes = ", ".join(
        f"${m:.2f} por {p}" for p, m in intereses_por_expensa
    )
    descripcion = (
        f"Intereses al {fecha_corte.isoformat()} sobre "
        f"{len(intereses_por_expensa)} expensa(s) vencida(s): {partes}"
    )
    return total, descripcion


def periodo_cerrado_en(db: Session, consorcio_id: int, periodo: str) -> bool:
    """True si el consorcio ya cerró ese período. El cierre es POR consorcio."""
    return db.get(PeriodoCerrado, (periodo, consorcio_id)) is not None


def calcular_preview_cierre(
    db: Session,
    consorcio_id: int,
    periodo: str,
    fecha_primer_venc: date | None = None,
    fecha_segundo_venc: date | None = None,
) -> PreviewCierre:
    cerrado = periodo_cerrado_en(db, consorcio_id, periodo)
    config = db.get(Consorcio, consorcio_id)

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
        select(Gasto).where(
            Gasto.periodo == periodo,
            Gasto.consorcio_id == consorcio_id,
        )
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

    sin_pagar = [g for g in gastos_periodo if not g.pagado]
    if sin_pagar:
        validaciones.append(Validacion(
            "warning",
            "gastos_sin_pagar",
            f"Hay {len(sin_pagar)} gasto(s) del período todavía sin confirmar "
            f"el pago. Se prorratean igual, con el monto cargado.",
        ))

    if not gastos_periodo:
        validaciones.append(Validacion(
            "warning",
            "sin_gastos",
            f"El período {periodo} no tiene gastos cargados. Las expensas serán $0.",
        ))

    # Clases activas con gastos del período: validar coeficientes.
    clases_activas = list(db.scalars(
        select(ClaseProrrateo).where(
            ClaseProrrateo.activa.is_(True),
            ClaseProrrateo.consorcio_id == consorcio_id,
        )
    ).all())
    deptos = list(db.scalars(
        select(Departamento).where(Departamento.consorcio_id == consorcio_id)
    ).all())

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
        db, consorcio_id, periodo, cerrado, fecha_1, fecha_2,
        validaciones, gastos_periodo, config,
    )


def _completar_preview(
    db: Session,
    consorcio_id: int,
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

    deptos = list(db.scalars(
        select(Departamento).where(Departamento.consorcio_id == consorcio_id)
    ).all())

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

    # Devengamiento perezoso antes de mirar saldos: el `saldo_anterior` que
    # arrastra la expensa nueva tiene que incluir los recargos ya vencidos.
    # Se pasa `hoy=fecha_corte` para que un preview a una fecha de corte
    # pasada no devengue recargos posteriores a esa fecha. Un solo commit
    # para todo el padrón, no uno por departamento.
    hubo_recargos = False
    for d in deptos:
        if devengar_recargos_y_marcar(db, d.id, hoy=fecha_corte):
            hubo_recargos = True
    if hubo_recargos:
        db.commit()

    intereses_por_depto: dict[int, float] = {}
    for d in deptos:
        monto, descripcion = calcular_intereses_al_cierre(db, consorcio_id, d.id, fecha_corte)
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
