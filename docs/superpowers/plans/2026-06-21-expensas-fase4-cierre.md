# Expensas Fase 4 — Cierre de período y liquidación — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el flujo manual de "crear expensa una por una" por un evento contable formal — **el cierre del período** — que genera N expensas con desglose por rubro, 1°/2° vencimiento, saldo anterior heredado e intereses automáticos sobre morosos.

**Architecture:**
- Tabla nueva `periodos_cerrados` (PK = `periodo`). Su existencia bloquea cargar/editar gastos y expensas de ese período.
- Tabla nueva `expensa_detalle` (snapshot por rubro/clase/concepto al cierre).
- `Expensa` modificada: rename `monto` → `monto_primer_vencimiento`, `fecha_vencimiento` → `fecha_primer_vencimiento`. Nuevos campos `monto_segundo_vencimiento`, `fecha_segundo_vencimiento`, `saldo_anterior`.
- `ConfiguracionConsorcio` con 4 nuevos campos: `dia_primer_vencimiento`, `dias_entre_vencimientos`, `recargo_segundo_vencimiento_pct`, `tasa_interes_mensual_pct`.
- Módulo `backend/cierre.py` (función pura) — `calcular_preview_cierre()` + `calcular_intereses_al_cierre()`. Sin side effects.
- Router `backend/routers/periodos.py` — 4 endpoints. POST `/cerrar` ejecuta toda la escritura en una transacción atómica.
- Bloqueos cross-recurso (409) en `/gastos`, `/expensas`, `/liquidaciones` cuando el período está cerrado.
- Frontend: pantalla nueva `/cierre-de-periodo` (Estado + Preview + Confirm), `/periodos` (historial), modal de desglose en cada `TarjetaExpensa`, form de Configuración con los 4 nuevos campos.
- Migración: clean start (borrar `consorcio.db`, re-seedear). No hay datos productivos.

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2; React 18 + Vite + react-router-dom; pytest.

**Spec:** `docs/superpowers/specs/2026-06-21-fase4-cierre-design.md`

---

## File structure

**Backend — nuevos:**
- `backend/cierre.py` — dataclasses (`Validacion`, `LineaDetalleExpensa`, `ExpensaACrear`, `InteresACrear`, `PreviewCierre`) + funciones `calcular_preview_cierre()` y `calcular_intereses_al_cierre()`. Sin side effects.
- `backend/routers/periodos.py` — 4 endpoints: GET `/periodos`, GET `/periodos/{periodo}/estado`, GET `/periodos/{periodo}/preview`, POST `/periodos/{periodo}/cerrar`.
- `tests/test_cierre.py` — unit tests del módulo puro (prorrateo, validaciones, intereses).
- `tests/test_periodos.py` — tests HTTP del router + bloqueos cross-recurso.

**Backend — modificados:**
- `backend/models.py` — modificar `Expensa` (rename + nuevos campos), sumar `ExpensaDetalle`, sumar `PeriodoCerrado`, sumar 4 campos a `ConfiguracionConsorcio`.
- `backend/schemas.py` — modificar `ExpensaOut` (nuevos nombres + detalle), `ExpensaCrear` (nuevos nombres), `ConfiguracionConsorcioActualizar` + `ConfiguracionConsorcioOut` (4 campos nuevos); sumar `ValidacionOut`, `LineaDetalleExpensaOut`, `ExpensaACrearOut`, `InteresACrearOut`, `PreviewCierreOut`, `EstadoCierreOut`, `CerrarPeriodoIn`, `PeriodoCerradoOut`.
- `backend/routers/expensas.py` — POST/PATCH/DELETE 409 si período cerrado; `_expensa_to_out` adaptado a nuevos campos.
- `backend/routers/gastos.py` — POST/PATCH/DELETE 409 si período cerrado.
- `backend/routers/liquidaciones.py` — POST/PATCH/DELETE 409 si período cerrado.
- `backend/routers/configuracion.py` — admite nuevos campos en PATCH.
- `backend/main.py` — registrar router `periodos`.
- `backend/seed.py` — adaptar `Expensa` al nuevo shape; agregar `ExpensaDetalle` por cada expensa seedeada; sumar 4 campos a la `ConfiguracionConsorcio` seedeada; **no** crear `PeriodoCerrado` (queda abierto para que el demo pueda cerrarlo).
- `tests/conftest.py` — adaptar fixtures de expensas al nuevo shape; nuevo fixture `db_lista_para_cierre`.
- `tests/test_expensas.py` — adaptar asserts al nuevo shape.
- `tests/test_gastos.py` — sumar tests de bloqueo 409 si período cerrado.
- `tests/test_liquidaciones.py` — sumar tests de bloqueo 409 si período cerrado.
- `tests/test_configuracion.py` — sumar tests de validación de los 4 campos nuevos.

**Docs:**
- `openapi.yaml` — paths nuevos `/periodos*`, modificar `ExpensaOut`, modificar `ConfiguracionConsorcio*`, declarar tag `Periodos`.

**Frontend — nuevos:**
- `frontend/src/api/periodos.js` — `listarPeriodos`, `estadoPeriodo`, `previewPeriodo`, `cerrarPeriodo`.
- `frontend/src/screens/CierreDePeriodo.jsx` — dos modos en una sola ruta (Estado + Preview).
- `frontend/src/screens/Periodos.jsx` — tabla de historial.
- `frontend/src/components/ModalDesgloseExpensa.jsx` — modal mostrando `ExpensaDetalle` agrupado por rubro.

**Frontend — modificados:**
- `frontend/src/api/expensas.js` — adapter al nuevo shape (`monto_primer_vencimiento`, etc.).
- `frontend/src/api/configuracion.js` — payload incluye los 4 campos nuevos.
- `frontend/src/screens/Expensas.jsx` — `TarjetaExpensa` muestra 1°/2° venc + saldo anterior + botón "Ver desglose".
- `frontend/src/screens/MiCuenta.jsx` — bloque de saldo con próximo vencimiento detallado.
- `frontend/src/screens/Configuracion.jsx` — sección "Vencimientos e intereses" con los 4 campos.
- `frontend/src/screens/Gastos.jsx` — gastos de período cerrado se muestran con candado, sin Editar/Borrar.
- `frontend/src/components/Sidebar.jsx` — "Cierre de período" y "Historial de cierres" en sección "Expensas y pagos".
- `frontend/src/App.jsx` — rutas `/cierre-de-periodo` y `/periodos`.

---

## Task 0: Setup — branch + clean DB + baseline

**Files:** ninguno modificado todavía.

- [ ] **Step 1: Crear branch desde `master`**

```bash
git checkout master
git pull --ff-only
git checkout -b feature/expensas-fase4-cierre
```

- [ ] **Step 2: Borrar DB local para clean start (patrón Fase 1-3.5)**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
```

(Bash: `rm -f consorcio.db`)

- [ ] **Step 3: Correr suite actual para confirmar baseline verde antes de empezar**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: **453 passed** en la rama recién creada.

- [ ] **Step 4: No commit todavía** (no hay cambios). Tasks siguientes hacen commit independiente.

---

## Task 1: Models — Expensa rename + ExpensaDetalle + PeriodoCerrado + Configuracion

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Modificar la clase `Expensa` (rename campos + nuevos)**

Localizar la clase `Expensa` (alrededor de la línea 241). Reemplazarla por:

```python
class Expensa(Base):
    __tablename__ = "expensas"
    __table_args__ = (
        UniqueConstraint("departamento_id", "periodo", name="uq_expensa_depto_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)

    # renombrados desde el shape Fase 3.5:
    monto_primer_vencimiento: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_primer_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    # nuevos en Fase 4:
    monto_segundo_vencimiento: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_segundo_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    saldo_anterior: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")
    detalle: Mapped[list["ExpensaDetalle"]] = relationship(
        back_populates="expensa", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Sumar la clase `ExpensaDetalle` (después de `Expensa`)**

Insertar inmediatamente después de la clase `Expensa`:

```python
class ExpensaDetalle(Base):
    __tablename__ = "expensa_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    expensa_id: Mapped[int] = mapped_column(
        ForeignKey("expensas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)
    clase_prorrateo_id: Mapped[int | None] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    expensa: Mapped["Expensa"] = relationship(back_populates="detalle")
```

- [ ] **Step 3: Sumar la clase `PeriodoCerrado` (después de `ExpensaDetalle`)**

```python
class PeriodoCerrado(Base):
    __tablename__ = "periodos_cerrados"

    periodo: Mapped[str] = mapped_column(String(7), primary_key=True)
    fecha_cierre: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cerrado_por_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    total_expensado: Mapped[float] = mapped_column(Float, nullable=False)
    total_intereses: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cantidad_expensas: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 4: Modificar `ConfiguracionConsorcio` — sumar 4 campos**

Localizar la clase `ConfiguracionConsorcio` (alrededor de la línea 381). Al final de la clase, **antes** del cierre, agregar:

```python
    # vencimientos e intereses (Fase 4)
    dia_primer_vencimiento: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dias_entre_vencimientos: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    recargo_segundo_vencimiento_pct: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    tasa_interes_mensual_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
```

- [ ] **Step 5: Smoke check de imports/sintaxis**

```bash
./.venv/Scripts/python.exe -c "from backend import models; print('OK')"
```
Expected: `OK` (sin tracebacks).

- [ ] **Step 6: Commit**

```bash
git add backend/models.py
git commit -m "feat(models): Expensa con 1°/2° venc + saldo_anterior; ExpensaDetalle; PeriodoCerrado; Configuracion + 4 campos"
```

---

## Task 2: Schemas Pydantic

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Modificar `ExpensaCrear` y `ExpensaOut` con los nuevos nombres**

Reemplazar el bloque `ExpensaCrear` (línea ~127) por:

```python
class ExpensaCrear(BaseModel):
    departamento_id: int = Field(..., gt=0)
    periodo: str = Field(..., pattern=_PERIODO_PATTERN)
    monto_primer_vencimiento: float = Field(..., gt=0)
    fecha_primer_vencimiento: date
    monto_segundo_vencimiento: float = Field(..., gt=0)
    fecha_segundo_vencimiento: date
```

Reemplazar el bloque `ExpensaOut` (línea ~161) por:

```python
class LineaDetalleExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rubro: Rubro
    clase_prorrateo_id: int | None
    departamento_origen_id: int | None
    concepto: str
    monto: float


class ExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    periodo: str
    monto_primer_vencimiento: float
    fecha_primer_vencimiento: date
    monto_segundo_vencimiento: float
    fecha_segundo_vencimiento: date
    saldo_anterior: float
    estado_calculado: EstadoExpensa
    monto_pendiente: float
    detalle: list[LineaDetalleExpensaOut]
```

- [ ] **Step 2: Sumar import `Rubro` arriba** (si no está ya)

Buscar el bloque de imports al principio del archivo. Si no está `Rubro`, agregar a la línea de imports de `..models`:

```python
from .models import (
    # ... lo que ya hubiera ...
    Rubro,
)
```

- [ ] **Step 3: Modificar `ConfiguracionConsorcioActualizar`**

En el bloque `ConfiguracionConsorcioActualizar` (línea ~320), después de `banco_alias`, agregar:

```python
    # vencimientos e intereses (Fase 4)
    dia_primer_vencimiento: int = Field(..., ge=1, le=28)
    dias_entre_vencimientos: int = Field(..., ge=1)
    recargo_segundo_vencimiento_pct: float = Field(..., ge=0)
    tasa_interes_mensual_pct: float = Field(..., ge=0)
```

- [ ] **Step 4: Modificar `ConfiguracionConsorcioOut`**

En el bloque `ConfiguracionConsorcioOut` (línea ~342), después de `banco_alias`, agregar los mismos 4 campos sin validadores:

```python
    dia_primer_vencimiento: int
    dias_entre_vencimientos: int
    recargo_segundo_vencimiento_pct: float
    tasa_interes_mensual_pct: float
```

- [ ] **Step 5: Sumar schemas de Fase 4 al final del archivo**

Al final de `schemas.py`, agregar:

```python
# ─── Fase 4: Cierre de período ────────────────────────────────────────────

class ValidacionOut(BaseModel):
    tipo: Literal["bloqueante", "warning"]
    codigo: str
    mensaje: str


class InteresACrearOut(BaseModel):
    departamento_id: int
    monto: float
    descripcion: str


class ExpensaACrearOut(BaseModel):
    departamento_id: int
    saldo_anterior: float
    monto_primer_vencimiento: float
    monto_segundo_vencimiento: float
    detalle: list[LineaDetalleExpensaOut]


class PreviewCierreOut(BaseModel):
    periodo: str
    cerrado: bool
    fecha_primer_vencimiento: date
    fecha_segundo_vencimiento: date
    validaciones: list[ValidacionOut]
    puede_cerrar: bool
    expensas: list[ExpensaACrearOut]
    intereses: list[InteresACrearOut]
    total_expensado: float
    total_intereses: float


class EstadoCierreOut(BaseModel):
    """Subset de PreviewCierreOut: solo validaciones, sin números."""
    periodo: str
    cerrado: bool
    validaciones: list[ValidacionOut]
    puede_cerrar: bool


class CerrarPeriodoIn(BaseModel):
    fecha_primer_vencimiento: date | None = None
    fecha_segundo_vencimiento: date | None = None


class PeriodoCerradoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    periodo: str
    fecha_cierre: datetime
    cerrado_por_usuario_id: int
    total_expensado: float
    total_intereses: float
    cantidad_expensas: int
```

- [ ] **Step 6: Smoke**

```bash
./.venv/Scripts/python.exe -c "from backend import schemas; print('OK')"
```
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas.py
git commit -m "feat(schemas): ExpensaOut+Crear con shape Fase 4; ConfiguracionConsorcio+4 campos; schemas cierre"
```

---

## Task 3: Módulo `backend/cierre.py` + unit tests

**Files:**
- Create: `backend/cierre.py`
- Create: `tests/test_cierre.py`

- [ ] **Step 1: Crear `backend/cierre.py` con dataclasses**

```python
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
    ConfiguracionConsorcio,
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
```

- [ ] **Step 2: Sumar helper `_calcular_fechas_default`**

```python
def _calcular_fechas_default(
    periodo: str, config: ConfiguracionConsorcio
) -> tuple[date, date]:
    """fecha_1 = día N del mes siguiente al período. fecha_2 = fecha_1 + M días."""
    year, month = map(int, periodo.split("-"))
    # mes siguiente
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    fecha_1 = date(next_year, next_month, config.dia_primer_vencimiento)
    fecha_2 = fecha_1 + timedelta(days=config.dias_entre_vencimientos)
    return fecha_1, fecha_2
```

- [ ] **Step 3: Sumar `calcular_intereses_al_cierre`**

```python
def calcular_intereses_al_cierre(
    db: Session, depto_id: int, fecha_corte: date
) -> tuple[float, str]:
    """Suma intereses sobre todas las expensas del depto con saldo > 0 cuyo
    2° vencimiento ya pasó. Tasa diaria = mensual_pct / 100 / 30.

    Returns (monto_total, descripcion_agregada). Si monto == 0, retorna ("",
    descripcion vacía).
    """
    config = db.scalar(select(ConfiguracionConsorcio))
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
```

- [ ] **Step 4: Sumar `calcular_preview_cierre` — esqueleto + validaciones**

```python
def calcular_preview_cierre(
    db: Session,
    periodo: str,
    fecha_primer_venc: date | None = None,
    fecha_segundo_venc: date | None = None,
) -> PreviewCierre:
    cerrado = db.get(PeriodoCerrado, periodo) is not None
    config = db.scalar(select(ConfiguracionConsorcio))

    validaciones: list[Validacion] = []
    fecha_1: date
    fecha_2: date

    if config is None:
        validaciones.append(Validacion(
            "bloqueante",
            "configuracion_incompleta",
            "Falta cargar la configuración del consorcio antes de cerrar períodos.",
        ))
        # Sin config no podemos calcular fechas default — devolvemos un preview
        # vacío y bloqueado.
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
            # Validar que TODOS los deptos tengan coef y que sume 100.
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
            # Clase activa sin gastos en el período: warning.
            if any(g.clase_prorrateo_id == clase.id for g in gastos_periodo):
                pass  # imposible por el if anterior
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
```

- [ ] **Step 5: Sumar helper `_completar_preview`** (prorrateo + intereses + saldo anterior)

```python
def _completar_preview(
    db: Session,
    periodo: str,
    cerrado: bool,
    fecha_1: date,
    fecha_2: date,
    validaciones: list[Validacion],
    gastos_periodo: list[Gasto],
    config: ConfiguracionConsorcio,
) -> PreviewCierre:
    """Calcula expensas, intereses y saldo anterior. Si hay bloqueantes graves
    (cierre ya hecho, config incompleta), devuelve preview vacío de expensas.
    """
    preview = PreviewCierre(
        periodo=periodo,
        cerrado=cerrado,
        fecha_primer_vencimiento=fecha_1,
        fecha_segundo_vencimiento=fecha_2,
        validaciones=validaciones,
    )

    # Si ya está cerrado, no calcular nada más.
    if cerrado:
        return preview

    deptos = list(db.scalars(select(Departamento)).all())

    # Acumular líneas por depto.
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

    # Intereses por depto (al día de hoy).
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

    # Construir expensas a crear.
    recargo = config.recargo_segundo_vencimiento_pct / 100
    for d in deptos:
        detalle = lineas_por_depto.get(d.id, [])
        monto_1 = round(sum(l.monto for l in detalle), 2)
        if monto_1 <= 0:
            continue  # depto sin nada que expensar este mes
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
```

- [ ] **Step 6: Smoke import**

```bash
./.venv/Scripts/python.exe -c "from backend.cierre import calcular_preview_cierre, calcular_intereses_al_cierre; print('OK')"
```
Expected: `OK`.

- [ ] **Step 7: Crear `tests/test_cierre.py` — fixtures de helpers**

```python
"""Unit tests del módulo backend/cierre.py — función pura, sin HTTP."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from backend.cierre import (
    calcular_intereses_al_cierre,
    calcular_preview_cierre,
)
from backend.models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    Departamento,
    Expensa,
    FormaPago,
    Gasto,
    MovimientoCuenta,
    Proveedor,
    Rubro,
    TipoMovimiento,
)


@pytest.fixture
def proveedor(db: Session) -> Proveedor:
    p = Proveedor(razon_social="ACME SRL", cuit="30-12345678-9")
    db.add(p); db.commit(); db.refresh(p)
    return p


@pytest.fixture
def clase_50_50(db: Session) -> ClaseProrrateo:
    """Clase A con 50/50 entre depto_a (id=1) y depto_b (id=2)."""
    c = ClaseProrrateo(codigo="A", nombre="Clase A")
    db.add(c); db.flush()
    db.add(CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=c.id, porcentaje=50))
    db.add(CoeficienteDepartamento(departamento_id=2, clase_prorrateo_id=c.id, porcentaje=50))
    db.commit(); db.refresh(c)
    return c


def _gasto(periodo, monto, proveedor_id, *, clase_id=None, depto_id=None, rubro=Rubro.servicios, concepto="Test"):
    return Gasto(
        periodo=periodo, monto=monto, rubro=rubro,
        clase_prorrateo_id=clase_id, departamento_id=depto_id,
        proveedor_id=proveedor_id, concepto=concepto,
        forma_pago=FormaPago.efectivo, fecha_pago=date(2026, 5, 15),
    )
```

(Asume que `conftest.py` provee la fixture `db` y que ya existen los deptos id=1, id=2 del seed por defecto. Si no, Task 4 las agrega.)

- [ ] **Step 8: Sumar primer test "preview sin gastos genera warning"**

```python
def test_preview_periodo_vacio_genera_warning_sin_gastos(db, clase_50_50):
    preview = calcular_preview_cierre(db, "2026-05")
    codigos = [v.codigo for v in preview.validaciones]
    assert "sin_gastos" in codigos
    assert preview.puede_cerrar  # warnings no bloquean
    assert preview.expensas == []
```

- [ ] **Step 9: Run, expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cierre.py::test_preview_periodo_vacio_genera_warning_sin_gastos -v`
Expected: PASS.

- [ ] **Step 10: Sumar test "un gasto de clase se prorratea por coeficientes"**

```python
def test_preview_un_gasto_clase_se_prorratea_por_coeficientes(db, proveedor, clase_50_50):
    db.add(_gasto("2026-05", 1000, proveedor.id, clase_id=clase_50_50.id))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    assert len(preview.expensas) == 2
    montos = sorted(e.monto_primer_vencimiento for e in preview.expensas)
    assert montos == [500.0, 500.0]
```

Run + commit en step 14.

- [ ] **Step 11: Test "gasto particular va solo al depto indicado"**

```python
def test_preview_gasto_particular_va_solo_al_depto_indicado(db, proveedor, clase_50_50):
    db.add(_gasto("2026-05", 800, proveedor.id, depto_id=1, concepto="Reparación caño 1A"))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    deptos_con_expensa = {e.departamento_id for e in preview.expensas}
    assert deptos_con_expensa == {1}
    assert preview.expensas[0].monto_primer_vencimiento == 800.0
    assert preview.expensas[0].detalle[0].departamento_origen_id == 1
```

- [ ] **Step 12: Test "monto_segundo_venc aplica recargo correcto"**

```python
def test_preview_monto_segundo_venc_aplica_recargo_correcto(db, proveedor, clase_50_50):
    # default recargo 7%
    db.add(_gasto("2026-05", 1000, proveedor.id, clase_id=clase_50_50.id))
    db.commit()

    preview = calcular_preview_cierre(db, "2026-05")
    for e in preview.expensas:
        assert e.monto_primer_vencimiento == 500.0
        assert e.monto_segundo_vencimiento == round(500 * 1.07, 2)
```

- [ ] **Step 13: Test "fecha default por regla configurable"**

```python
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
```

- [ ] **Step 14: Tests de validaciones bloqueantes**

```python
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
    # solo depto 1, falta depto 2
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
```

- [ ] **Step 15: Tests de intereses**

```python
def test_intereses_depto_al_dia_devuelve_cero(db):
    monto, _ = calcular_intereses_al_cierre(db, 1, date(2026, 6, 30))
    assert monto == 0.0


def test_intereses_un_mes_de_mora_calcula_correcto(db, proveedor):
    # Expensa de abril, 2° venc 20-may, monto 1000, sin pago. Calcular al 30-may.
    expensa = Expensa(
        departamento_id=1, periodo="2026-04",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento=date(2026, 5, 10),
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento=date(2026, 5, 20),
        saldo_anterior=0.0,
    )
    db.add(expensa); db.flush()
    db.add(MovimientoCuenta(
        departamento_id=1, fecha=date(2026, 5, 1),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa 2026-04",
        monto=1000, expensa_id=expensa.id,
    ))
    db.commit()

    monto, descripcion = calcular_intereses_al_cierre(db, 1, date(2026, 5, 30))
    # 10 días de mora, tasa 3%/mes → 0.001/día. 1000 × 0.001 × 10 = 10.
    assert monto == 10.0
    assert "2026-04" in descripcion
```

- [ ] **Step 16: Run toda la suite del archivo nuevo**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_cierre.py -v
```
Expected: todos los tests definidos pasan (8+).

- [ ] **Step 17: Commit**

```bash
git add backend/cierre.py tests/test_cierre.py
git commit -m "feat(cierre): módulo puro calcular_preview_cierre + intereses + unit tests"
```

---

## Task 4: Actualizar conftest al nuevo shape de Expensa

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Buscar las fixtures de expensas en `conftest.py`**

```bash
grep -n "Expensa\|fecha_vencimiento\|monto=" tests/conftest.py
```

- [ ] **Step 2: Adaptar cada construcción de `Expensa(...)` al nuevo shape**

Localizar cada uso. Reemplazar:

```python
Expensa(
    departamento_id=...,
    periodo=...,
    monto=X,
    fecha_vencimiento=DATE,
)
```

por:

```python
Expensa(
    departamento_id=...,
    periodo=...,
    monto_primer_vencimiento=X,
    fecha_primer_vencimiento=DATE,
    monto_segundo_vencimiento=round(X * 1.07, 2),
    fecha_segundo_vencimiento=DATE + timedelta(days=10),
    saldo_anterior=0.0,
)
```

(asegurar que `timedelta` esté importado).

- [ ] **Step 3: Verificar que la suite anterior siga corriendo** (algunos tests existentes pueden romperse por el cambio de shape — se resuelven en Task 5)

```bash
./.venv/Scripts/python.exe -m pytest tests/test_cierre.py -v
```
Expected: tests de Task 3 siguen verde.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): Expensa fixtures con shape Fase 4 (1°/2° venc)"
```

---

## Task 5: Adaptar tests existentes al nuevo shape de Expensa

**Files:**
- Modify: `tests/test_expensas.py`
- Modify: `tests/test_comprobantes.py` (si asume shape viejo)
- Modify: `tests/test_movimientos.py` (idem)

- [ ] **Step 1: Buscar usos de `"monto"` y `"fecha_vencimiento"` en tests**

```bash
grep -rn "\"monto\":\|\"fecha_vencimiento\":\|\.monto[^_]" tests/ | grep -v conftest
```

- [ ] **Step 2: Adaptar payloads de POST /expensas**

Buscar bloques tipo:
```python
client.post("/expensas", json={"departamento_id": 1, "periodo": "2026-05", "monto": 85000, "fecha_vencimiento": "2026-06-10"}, ...)
```
Reemplazar por:
```python
client.post("/expensas", json={
    "departamento_id": 1,
    "periodo": "2026-05",
    "monto_primer_vencimiento": 85000,
    "fecha_primer_vencimiento": "2026-06-10",
    "monto_segundo_vencimiento": 90950,
    "fecha_segundo_vencimiento": "2026-06-20",
}, ...)
```

- [ ] **Step 3: Adaptar asserts sobre el response**

Donde había:
```python
assert body["monto"] == 85000
assert body["fecha_vencimiento"] == "2026-06-10"
```
Cambiar a:
```python
assert body["monto_primer_vencimiento"] == 85000
assert body["fecha_primer_vencimiento"] == "2026-06-10"
assert body["monto_segundo_vencimiento"] == 90950
assert body["saldo_anterior"] == 0.0
assert body["detalle"] == []  # creación individual no tiene detalle
```

- [ ] **Step 4: Run suite completa para detectar tests rotos**

```bash
./.venv/Scripts/python.exe -m pytest -q
```
Identificar fallas y corregir uno a uno. Los routers todavía no fueron tocados, así que algunos asserts pueden seguir fallando — eso es esperable hasta Task 6.

- [ ] **Step 5: Commit parcial (solo los cambios a tests, no a routers)**

```bash
git add tests/
git commit -m "test: payloads/asserts de Expensa adaptados al shape Fase 4"
```

---

## Task 6: Router `/expensas` adaptado al nuevo shape

**Files:**
- Modify: `backend/routers/expensas.py`

- [ ] **Step 1: Adaptar `_expensa_to_out` para incluir nuevos campos**

Reemplazar la función (línea ~24):

```python
def _expensa_to_out(expensa: Expensa, calc) -> ExpensaOut:
    return ExpensaOut(
        id=expensa.id,
        departamento_id=expensa.departamento_id,
        periodo=expensa.periodo,
        monto_primer_vencimiento=expensa.monto_primer_vencimiento,
        fecha_primer_vencimiento=expensa.fecha_primer_vencimiento,
        monto_segundo_vencimiento=expensa.monto_segundo_vencimiento,
        fecha_segundo_vencimiento=expensa.fecha_segundo_vencimiento,
        saldo_anterior=expensa.saldo_anterior,
        estado_calculado=calc.estado,
        monto_pendiente=calc.monto_pendiente,
        detalle=[
            LineaDetalleExpensaOut.model_validate(d) for d in expensa.detalle
        ],
    )
```

- [ ] **Step 2: Sumar imports faltantes**

Al principio del archivo, ajustar imports:

```python
from ..models import (
    Departamento,
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    PeriodoCerrado,
    Rol,
    TipoMovimiento,
)
from ..schemas import ExpensaCrear, ExpensaOut, LineaDetalleExpensaOut
```

- [ ] **Step 3: Adaptar `crear_expensa` para usar los nuevos nombres**

Reemplazar el bloque que construye `Expensa(...)` (línea ~117):

```python
expensa = Expensa(
    departamento_id=payload.departamento_id,
    periodo=payload.periodo,
    monto_primer_vencimiento=payload.monto_primer_vencimiento,
    fecha_primer_vencimiento=payload.fecha_primer_vencimiento,
    monto_segundo_vencimiento=payload.monto_segundo_vencimiento,
    fecha_segundo_vencimiento=payload.fecha_segundo_vencimiento,
    saldo_anterior=0.0,
)
```

Y adaptar el movimiento generado:

```python
db.add(
    MovimientoCuenta(
        departamento_id=expensa.departamento_id,
        fecha=date.today(),
        tipo=TipoMovimiento.expensa_emitida,
        descripcion=f"Expensa {expensa.periodo}",
        monto=expensa.monto_primer_vencimiento,
        expensa_id=expensa.id,
    )
)
```

- [ ] **Step 4: Sumar bloqueo de POST si período cerrado**

Justo antes del bloque que verifica duplicado en `crear_expensa`, agregar:

```python
if db.get(PeriodoCerrado, payload.periodo) is not None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"El período {payload.periodo} está cerrado y no admite cambios.",
    )
```

- [ ] **Step 5: Sumar bloqueo de DELETE si período cerrado**

En `eliminar_expensa` (línea ~181), justo después de cargar la expensa:

```python
if db.get(PeriodoCerrado, expensa.periodo) is not None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"El período {expensa.periodo} está cerrado y no admite cambios.",
    )
```

- [ ] **Step 6: Run tests de expensas**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_expensas.py -v
```
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/expensas.py
git commit -m "feat(expensas): shape Fase 4 (1°/2° venc + detalle) + bloqueo 409 si período cerrado"
```

---

## Task 7: Router `/periodos` — endpoints + tests

**Files:**
- Create: `backend/routers/periodos.py`
- Create: `tests/test_periodos.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `backend/routers/periodos.py`**

```python
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..cierre import (
    InteresACrear,
    LineaDetalleExpensa,
    calcular_preview_cierre,
)
from ..database import get_db
from ..models import (
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    PeriodoCerrado,
    Rol,
    TipoMovimiento,
)
from ..schemas import (
    CerrarPeriodoIn,
    EstadoCierreOut,
    ExpensaACrearOut,
    InteresACrearOut,
    LineaDetalleExpensaOut,
    PeriodoCerradoOut,
    PreviewCierreOut,
    ValidacionOut,
)

router = APIRouter(prefix="/periodos", tags=["Periodos"])

_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _preview_to_out(preview) -> PreviewCierreOut:
    return PreviewCierreOut(
        periodo=preview.periodo,
        cerrado=preview.cerrado,
        fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
        fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
        validaciones=[ValidacionOut(**v.__dict__) for v in preview.validaciones],
        puede_cerrar=preview.puede_cerrar,
        expensas=[
            ExpensaACrearOut(
                departamento_id=e.departamento_id,
                saldo_anterior=e.saldo_anterior,
                monto_primer_vencimiento=e.monto_primer_vencimiento,
                monto_segundo_vencimiento=e.monto_segundo_vencimiento,
                detalle=[
                LineaDetalleExpensaOut(
                    rubro=d.rubro,
                    clase_prorrateo_id=d.clase_prorrateo_id,
                    departamento_origen_id=d.departamento_origen_id,
                    concepto=d.concepto,
                    monto=d.monto,
                )
                for d in e.detalle
            ],
            )
            for e in preview.expensas
        ],
        intereses=[InteresACrearOut(**i.__dict__) for i in preview.intereses],
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
    )


@router.get("", response_model=list[PeriodoCerradoOut], status_code=200)
def listar_periodos(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[PeriodoCerrado]:
    return list(db.scalars(
        select(PeriodoCerrado).order_by(PeriodoCerrado.fecha_cierre.desc())
    ).all())


@router.get("/{periodo}/estado", response_model=EstadoCierreOut, status_code=200)
def estado_periodo(
    periodo: str,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EstadoCierreOut:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido. Use formato YYYY-MM.")
    preview = calcular_preview_cierre(db, periodo)
    return EstadoCierreOut(
        periodo=preview.periodo,
        cerrado=preview.cerrado,
        validaciones=[ValidacionOut(**v.__dict__) for v in preview.validaciones],
        puede_cerrar=preview.puede_cerrar,
    )


@router.get("/{periodo}/preview", response_model=PreviewCierreOut, status_code=200)
def preview_periodo(
    periodo: str,
    fecha_1: date | None = Query(default=None),
    fecha_2: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> PreviewCierreOut:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido.")
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(409, f"El período {periodo} ya fue cerrado.")
    preview = calcular_preview_cierre(db, periodo, fecha_1, fecha_2)
    return _preview_to_out(preview)


@router.post("/{periodo}/cerrar", response_model=PeriodoCerradoOut, status_code=201)
def cerrar_periodo(
    periodo: str,
    payload: CerrarPeriodoIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> PeriodoCerrado:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido.")
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(409, f"El período {periodo} ya fue cerrado.")

    preview = calcular_preview_cierre(
        db, periodo,
        payload.fecha_primer_vencimiento,
        payload.fecha_segundo_vencimiento,
    )
    if not preview.puede_cerrar:
        raise HTTPException(409, "Hay validaciones bloqueantes pendientes para cerrar el período.")

    hoy = date.today()

    # 1) intereses
    for it in preview.intereses:
        db.add(MovimientoCuenta(
            departamento_id=it.departamento_id,
            fecha=hoy,
            tipo=TipoMovimiento.interes_punitorio,
            descripcion=it.descripcion,
            monto=it.monto,
        ))
    db.flush()

    # 2) expensas + detalle + movimiento expensa_emitida
    for exp in preview.expensas:
        e = Expensa(
            departamento_id=exp.departamento_id,
            periodo=periodo,
            monto_primer_vencimiento=exp.monto_primer_vencimiento,
            fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
            monto_segundo_vencimiento=exp.monto_segundo_vencimiento,
            fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
            saldo_anterior=exp.saldo_anterior,
        )
        db.add(e); db.flush()
        for d in exp.detalle:
            db.add(ExpensaDetalle(
                expensa_id=e.id,
                rubro=d.rubro,
                clase_prorrateo_id=d.clase_prorrateo_id,
                departamento_origen_id=d.departamento_origen_id,
                concepto=d.concepto,
                monto=d.monto,
            ))
        db.add(MovimientoCuenta(
            departamento_id=exp.departamento_id,
            fecha=hoy,
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {periodo}",
            monto=exp.monto_primer_vencimiento,
            expensa_id=e.id,
        ))

    # 3) marcar cerrado
    cerrado = PeriodoCerrado(
        periodo=periodo,
        cerrado_por_usuario_id=user.id,
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
        cantidad_expensas=len(preview.expensas),
    )
    db.add(cerrado)
    db.commit()
    db.refresh(cerrado)
    return cerrado
```

(Nota: el `re.fullmatch(...)` evita un import top-level adicional; se puede refactorizar a un import limpio si preferís — opcional.)

- [ ] **Step 2: Registrar router en `backend/main.py`**

```python
from .routers import (
    # ... lo que ya hubiera ...
    periodos,
)

# ... más abajo, donde se incluyen routers:
app.include_router(periodos.router)
```

- [ ] **Step 3: Smoke**

```bash
./.venv/Scripts/python.exe -c "from backend.main import app; print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Crear `tests/test_periodos.py` con fixtures + happy path**

```python
"""Tests HTTP del router /periodos + bloqueos cross-recurso."""
from datetime import date, timedelta

import pytest

from backend.models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    Expensa,
    FormaPago,
    Gasto,
    MovimientoCuenta,
    Proveedor,
    Rubro,
    TipoMovimiento,
)


@pytest.fixture
def db_lista_para_cierre(db):
    """Setup mínimo para cerrar período 2026-05: 1 clase 50/50, 2 gastos."""
    proveedor = Proveedor(razon_social="ACME", cuit="30-12345678-9")
    db.add(proveedor); db.flush()

    clase = ClaseProrrateo(codigo="A", nombre="Clase A")
    db.add(clase); db.flush()
    db.add(CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=clase.id, porcentaje=50))
    db.add(CoeficienteDepartamento(departamento_id=2, clase_prorrateo_id=clase.id, porcentaje=50))

    db.add(Gasto(
        periodo="2026-05", monto=1000, rubro=Rubro.servicios,
        clase_prorrateo_id=clase.id, departamento_id=None,
        proveedor_id=proveedor.id, concepto="Luz",
        forma_pago=FormaPago.efectivo, fecha_pago=date(2026, 5, 10),
    ))
    db.add(Gasto(
        periodo="2026-05", monto=500, rubro=Rubro.servicios,
        clase_prorrateo_id=None, departamento_id=1,
        proveedor_id=proveedor.id, concepto="Reparación 1A",
        forma_pago=FormaPago.efectivo, fecha_pago=date(2026, 5, 15),
    ))
    db.commit()
    return db
```

- [ ] **Step 5: Tests happy path**

```python
def test_listar_periodos_admin_200_vacio_si_no_hay_cierres(client, headers_admin):
    r = client.get("/periodos", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_listar_periodos_depto_403(client, headers_depto_a):
    r = client.get("/periodos", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_estado_admin_200_devuelve_validaciones(client, headers_admin, db_lista_para_cierre):
    r = client.get("/periodos/2026-05/estado", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["periodo"] == "2026-05"
    assert body["cerrado"] is False
    assert "validaciones" in body
    assert body["puede_cerrar"] is True


def test_get_preview_admin_200_genera_expensas(client, headers_admin, db_lista_para_cierre):
    r = client.get("/periodos/2026-05/preview", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert len(body["expensas"]) == 2
    montos = sorted(e["monto_primer_vencimiento"] for e in body["expensas"])
    # depto 2: 500 de la clase A. depto 1: 500 de la clase A + 500 particular = 1000.
    assert montos == [500.0, 1000.0]


def test_cerrar_periodo_genera_n_expensas_con_movimientos(
    client, headers_admin, db_lista_para_cierre,
):
    r = client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["periodo"] == "2026-05"
    assert body["cantidad_expensas"] == 2

    # Verificar expensas en DB
    r2 = client.get("/expensas?periodo=2026-05", headers=headers_admin)
    assert r2.status_code == 200
    assert len(r2.json()) == 2


def test_cerrar_periodo_idempotente_segundo_call_409(client, headers_admin, db_lista_para_cierre):
    r1 = client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)
    assert r1.status_code == 201
    r2 = client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)
    assert r2.status_code == 409
```

- [ ] **Step 6: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_periodos.py -v
```
Expected: 6 tests pass.

- [ ] **Step 7: Tests de bloqueos cross-recurso (en el mismo archivo)**

```python
def test_post_gasto_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)
    r = client.post("/gastos", json={
        "periodo": "2026-05", "rubro": "servicios", "concepto": "Tarde",
        "monto": 100, "proveedor_id": 1,
        "clase_prorrateo_id": 1, "departamento_id": None,
        "forma_pago": "efectivo", "fecha_pago": "2026-05-30",
    }, headers=headers_admin)
    assert r.status_code == 409


def test_post_expensa_individual_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)
    r = client.post("/expensas", json={
        "departamento_id": 1, "periodo": "2026-05",
        "monto_primer_vencimiento": 100, "fecha_primer_vencimiento": "2026-06-10",
        "monto_segundo_vencimiento": 107, "fecha_segundo_vencimiento": "2026-06-20",
    }, headers=headers_admin)
    assert r.status_code == 409


def test_comprobante_periodo_cerrado_sigue_funcionando_200(client, headers_admin, headers_depto_a, db_lista_para_cierre):
    client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)
    # Presentar comprobante sigue siendo viable porque la cuenta corriente está viva.
    files = {"archivo": ("c.png", b"\x89PNG\r\n\x1a\n_dummy", "image/png")}
    r = client.post("/comprobantes",
        data={"fecha_pago": "2026-06-15", "monto": 500},
        files=files, headers=headers_depto_a,
    )
    assert r.status_code == 201
```

- [ ] **Step 8: Run, expect pass — entonces el bloqueo de /gastos debe estar implementado (Task 9 lo cubre). Por ahora, marcar este test como skip si falla.**

Si falla, hacer:
```python
@pytest.mark.skip(reason="bloqueo /gastos implementado en Task 9")
def test_post_gasto_periodo_cerrado_409(...):
    ...
```
Y des-skipearlo cuando esté listo.

- [ ] **Step 9: Commit**

```bash
git add backend/routers/periodos.py backend/main.py tests/test_periodos.py
git commit -m "feat(periodos): router con GET/POST + tests happy path + idempotencia"
```

---

## Task 8: Bloqueos cross-recurso en `/gastos` y `/liquidaciones`

**Files:**
- Modify: `backend/routers/gastos.py`
- Modify: `backend/routers/liquidaciones.py`
- Modify: `tests/test_gastos.py` (sumar tests del bloqueo)

- [ ] **Step 1: En `gastos.py`, sumar import + helper**

Al principio:
```python
from ..models import PeriodoCerrado
```

Definir helper (al inicio del archivo, después de imports):
```python
def _bloquear_si_periodo_cerrado(db: Session, periodo: str) -> None:
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )
```

- [ ] **Step 2: Llamar el helper en POST, PATCH, DELETE de gastos**

En cada handler, **al principio** después de validar payload:
```python
_bloquear_si_periodo_cerrado(db, payload.periodo)  # POST
_bloquear_si_periodo_cerrado(db, gasto.periodo)    # PATCH / DELETE
```

(adaptar según la firma exacta de cada handler).

- [ ] **Step 3: Idem para `liquidaciones.py`**

En `POST /liquidaciones`, `PATCH /liquidaciones/{id}`, `DELETE /liquidaciones/{id}`:
- POST: `_bloquear_si_periodo_cerrado(db, payload.periodo)`
- PATCH/DELETE: `_bloquear_si_periodo_cerrado(db, liquidacion.periodo)`

Definir el mismo helper local en `liquidaciones.py` (DRY: si pesa, lo movemos a un módulo `backend/helpers.py` en una siguiente fase).

- [ ] **Step 4: Des-skipear los tests bloqueados en Task 7 si los habías marcado skip**

- [ ] **Step 5: Run tests de gastos + periodos**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_gastos.py tests/test_periodos.py tests/test_liquidaciones.py -v
```
Expected: todo verde.

- [ ] **Step 6: Sumar tests específicos en `test_gastos.py`** (si no fueron cubiertos en Task 7)

```python
def test_patch_gasto_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    # Crear un gasto antes de cerrar
    r_crear = client.post("/gastos", json={...}, headers=headers_admin)
    gasto_id = r_crear.json()["id"]

    # Cerrar
    client.post("/periodos/2026-05/cerrar", json={}, headers=headers_admin)

    # Intentar editar
    r = client.patch(f"/gastos/{gasto_id}", json={"monto": 9999}, headers=headers_admin)
    assert r.status_code == 409


def test_delete_gasto_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    # Análogo a patch
    ...
```

- [ ] **Step 7: Commit**

```bash
git add backend/routers/gastos.py backend/routers/liquidaciones.py tests/test_gastos.py tests/test_liquidaciones.py tests/test_periodos.py
git commit -m "feat(gastos,liquidaciones): bloqueo 409 si período cerrado + tests"
```

---

## Task 9: Configuración — endpoint con 4 nuevos campos

**Files:**
- Modify: `backend/routers/configuracion.py`
- Modify: `tests/test_configuracion.py`

- [ ] **Step 1: Verificar el PATCH actual**

```bash
cat backend/routers/configuracion.py | head -50
```

Si el handler ya usa `ConfiguracionConsorcioActualizar`, automáticamente acepta los 4 nuevos campos (Pydantic los valida).

- [ ] **Step 2: Verificar la lógica de "create on first PATCH" o "update existing"**

Buscar en el handler la línea que hace `setattr` o `model_dump()`. Si usa `model_dump()`, los nuevos campos se persisten automáticamente.

- [ ] **Step 3: Si la lógica del handler enumera campos manualmente, sumar los 4 nuevos**

```python
config.dia_primer_vencimiento = payload.dia_primer_vencimiento
config.dias_entre_vencimientos = payload.dias_entre_vencimientos
config.recargo_segundo_vencimiento_pct = payload.recargo_segundo_vencimiento_pct
config.tasa_interes_mensual_pct = payload.tasa_interes_mensual_pct
```

- [ ] **Step 4: Test "validar dia_primer_vencimiento fuera de rango devuelve 400"**

```python
def test_patch_configuracion_dia_invalido_devuelve_400(client, headers_admin):
    # Asume que ya hay una configuración seedeada o creada
    payload_base = { ... }  # toma payload válido y modifica solo el día
    payload_base["dia_primer_vencimiento"] = 30  # fuera de rango (>28)
    r = client.patch("/configuracion", json=payload_base, headers=headers_admin)
    assert r.status_code == 400
```

- [ ] **Step 5: Test "los 4 campos default vienen del seed"**

```python
def test_get_configuracion_incluye_4_nuevos_campos(client, headers_admin):
    r = client.get("/configuracion", headers=headers_admin)
    body = r.json()
    assert "dia_primer_vencimiento" in body
    assert "dias_entre_vencimientos" in body
    assert "recargo_segundo_vencimiento_pct" in body
    assert "tasa_interes_mensual_pct" in body
```

- [ ] **Step 6: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_configuracion.py -v
```
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/configuracion.py tests/test_configuracion.py
git commit -m "feat(configuracion): aceptar 4 campos Fase 4 + tests de validación"
```

---

## Task 10: OpenAPI

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Sumar tag**

En la sección `tags:` del yaml:
```yaml
- name: Periodos
  description: Cierre de período y liquidación
```

- [ ] **Step 2: Sumar 4 paths**

Al final del bloque `paths:`:

```yaml
  /periodos:
    get:
      tags: [Periodos]
      summary: Listar períodos cerrados (admin)
      operationId: listarPeriodos
      security:
        - bearerAuth: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/PeriodoCerradoOut'
        '401': { description: Token ausente o inválido }
        '403': { description: Rol sin permisos }

  /periodos/{periodo}/estado:
    get:
      tags: [Periodos]
      summary: Diagnóstico del período (admin) — solo validaciones
      operationId: estadoPeriodo
      security:
        - bearerAuth: []
      parameters:
        - $ref: '#/components/parameters/periodoParam'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EstadoCierreOut'
        '400': { description: Período inválido }
        '401': { description: Token ausente o inválido }
        '403': { description: Rol sin permisos }

  /periodos/{periodo}/preview:
    get:
      tags: [Periodos]
      summary: Preview completo del cierre (admin)
      operationId: previewPeriodo
      security:
        - bearerAuth: []
      parameters:
        - $ref: '#/components/parameters/periodoParam'
        - name: fecha_1
          in: query
          schema: { type: string, format: date }
        - name: fecha_2
          in: query
          schema: { type: string, format: date }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PreviewCierreOut'
        '409': { description: Período ya cerrado }

  /periodos/{periodo}/cerrar:
    post:
      tags: [Periodos]
      summary: Cerrar período (admin)
      operationId: cerrarPeriodo
      security:
        - bearerAuth: []
      parameters:
        - $ref: '#/components/parameters/periodoParam'
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CerrarPeriodoIn'
      responses:
        '201':
          description: Período cerrado
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PeriodoCerradoOut'
        '409': { description: Bloqueado (ya cerrado o validaciones bloqueantes) }
```

- [ ] **Step 3: Sumar parameter `periodoParam` si no existe**

```yaml
components:
  parameters:
    periodoParam:
      name: periodo
      in: path
      required: true
      schema:
        type: string
        pattern: '^\d{4}-(0[1-9]|1[0-2])$'
        example: "2026-05"
```

- [ ] **Step 4: Sumar 6 schemas nuevos en `components.schemas`**

```yaml
    ValidacionOut:
      type: object
      properties:
        tipo: { type: string, enum: [bloqueante, warning] }
        codigo: { type: string }
        mensaje: { type: string }
      required: [tipo, codigo, mensaje]

    LineaDetalleExpensaOut:
      type: object
      properties:
        rubro: { type: string }
        clase_prorrateo_id: { type: integer, nullable: true }
        departamento_origen_id: { type: integer, nullable: true }
        concepto: { type: string }
        monto: { type: number }

    ExpensaACrearOut:
      type: object
      properties:
        departamento_id: { type: integer }
        saldo_anterior: { type: number }
        monto_primer_vencimiento: { type: number }
        monto_segundo_vencimiento: { type: number }
        detalle:
          type: array
          items: { $ref: '#/components/schemas/LineaDetalleExpensaOut' }

    InteresACrearOut:
      type: object
      properties:
        departamento_id: { type: integer }
        monto: { type: number }
        descripcion: { type: string }

    PreviewCierreOut:
      type: object
      properties:
        periodo: { type: string }
        cerrado: { type: boolean }
        fecha_primer_vencimiento: { type: string, format: date }
        fecha_segundo_vencimiento: { type: string, format: date }
        validaciones:
          type: array
          items: { $ref: '#/components/schemas/ValidacionOut' }
        puede_cerrar: { type: boolean }
        expensas:
          type: array
          items: { $ref: '#/components/schemas/ExpensaACrearOut' }
        intereses:
          type: array
          items: { $ref: '#/components/schemas/InteresACrearOut' }
        total_expensado: { type: number }
        total_intereses: { type: number }

    EstadoCierreOut:
      type: object
      properties:
        periodo: { type: string }
        cerrado: { type: boolean }
        validaciones:
          type: array
          items: { $ref: '#/components/schemas/ValidacionOut' }
        puede_cerrar: { type: boolean }

    CerrarPeriodoIn:
      type: object
      properties:
        fecha_primer_vencimiento: { type: string, format: date, nullable: true }
        fecha_segundo_vencimiento: { type: string, format: date, nullable: true }

    PeriodoCerradoOut:
      type: object
      properties:
        periodo: { type: string }
        fecha_cierre: { type: string, format: date-time }
        cerrado_por_usuario_id: { type: integer }
        total_expensado: { type: number }
        total_intereses: { type: number }
        cantidad_expensas: { type: integer }
```

- [ ] **Step 5: Modificar `ExpensaOut` existente — agregar los nuevos campos**

Buscar `ExpensaOut` en `components.schemas` y reemplazar por:

```yaml
    ExpensaOut:
      type: object
      properties:
        id: { type: integer }
        departamento_id: { type: integer }
        periodo: { type: string }
        monto_primer_vencimiento: { type: number }
        fecha_primer_vencimiento: { type: string, format: date }
        monto_segundo_vencimiento: { type: number }
        fecha_segundo_vencimiento: { type: string, format: date }
        saldo_anterior: { type: number }
        estado_calculado: { type: string }
        monto_pendiente: { type: number }
        detalle:
          type: array
          items: { $ref: '#/components/schemas/LineaDetalleExpensaOut' }
```

- [ ] **Step 6: Modificar `ExpensaCrear` y `ConfiguracionConsorcio*` análogamente**

(Sigue el mismo patrón: agregar los nuevos campos al schema yaml.)

- [ ] **Step 7: Smoke validation del yaml**

```bash
./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): paths /periodos, schemas Fase 4 + ExpensaOut/Crear actualizados"
```

---

## Task 11: Seed — adaptar al nuevo shape

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Buscar construcciones de `Expensa(...)` en seed**

```bash
grep -n "Expensa(" backend/seed.py
```

- [ ] **Step 2: Adaptar cada `Expensa(...)`**

Reemplazar:
```python
Expensa(
    departamento_id=...,
    periodo=...,
    monto=...,
    fecha_vencimiento=...,
)
```

por:
```python
Expensa(
    departamento_id=...,
    periodo=...,
    monto_primer_vencimiento=...,
    fecha_primer_vencimiento=...,
    monto_segundo_vencimiento=round(... * 1.07, 2),
    fecha_segundo_vencimiento=... + timedelta(days=10),
    saldo_anterior=0.0,
)
```

- [ ] **Step 3: Sumar `ExpensaDetalle` por cada expensa seedeada**

Justo después de cada `db.add(expensa); db.flush()`, agregar un detalle representativo (mínimo 1 línea):

```python
db.add(ExpensaDetalle(
    expensa_id=expensa.id,
    rubro=Rubro.servicios,
    clase_prorrateo_id=clase_a.id,  # ajustar a la clase del seed
    departamento_origen_id=None,
    concepto="Demo: prorrateo clase A",
    monto=expensa.monto_primer_vencimiento,
))
```

(Si el seed ya tiene gastos, lo ideal es que el detalle refleje un prorrateo coherente; en su defecto, una sola línea con el total alcanza para demo.)

- [ ] **Step 4: Sumar los 4 campos a la `ConfiguracionConsorcio` seedeada**

Buscar el bloque que crea `ConfiguracionConsorcio(...)` y agregar:

```python
ConfiguracionConsorcio(
    ...  # los campos existentes
    dia_primer_vencimiento=10,
    dias_entre_vencimientos=10,
    recargo_segundo_vencimiento_pct=7.0,
    tasa_interes_mensual_pct=3.0,
)
```

- [ ] **Step 5: NO seedear `PeriodoCerrado`** — el demo debe poder cerrar período actual sin fricción.

- [ ] **Step 6: Smoke — borrar DB y re-seedear**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
./.venv/Scripts/python.exe -c "from backend.database import engine; from backend.models import Base; Base.metadata.create_all(engine); from backend.seed import seed_if_empty; from backend.database import SessionLocal; seed_if_empty(SessionLocal()); print('seed OK')"
```
Expected: `seed OK` sin errores.

- [ ] **Step 7: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): Expensa shape Fase 4 + ExpensaDetalle + 4 campos config"
```

---

## Task 12: Frontend — API clients

**Files:**
- Create: `frontend/src/api/periodos.js`
- Modify: `frontend/src/api/expensas.js` (si tiene constants del shape viejo)
- Modify: `frontend/src/api/configuracion.js` (idem)

- [ ] **Step 1: Crear `frontend/src/api/periodos.js`**

```javascript
import { apiFetch } from "./client";

export function listarPeriodos() {
  return apiFetch("/periodos");
}

export function estadoPeriodo(periodo) {
  return apiFetch(`/periodos/${periodo}/estado`);
}

export function previewPeriodo(periodo, { fecha_1, fecha_2 } = {}) {
  const qs = new URLSearchParams();
  if (fecha_1) qs.set("fecha_1", fecha_1);
  if (fecha_2) qs.set("fecha_2", fecha_2);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/periodos/${periodo}/preview${suffix}`);
}

export function cerrarPeriodo(periodo, body = {}) {
  return apiFetch(`/periodos/${periodo}/cerrar`, {
    method: "POST",
    body,
  });
}
```

- [ ] **Step 2: Smoke build**

```bash
cd frontend && npm run build
```
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/periodos.js
git commit -m "feat(frontend/api): periodos.js — listar/estado/preview/cerrar"
```

---

## Task 13: Pantalla `/cierre-de-periodo` (admin)

**Files:**
- Create: `frontend/src/screens/CierreDePeriodo.jsx`

- [ ] **Step 1: Crear el archivo con estructura básica de dos modos**

```jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  estadoPeriodo,
  previewPeriodo,
  cerrarPeriodo,
} from "../api/periodos";
import Tarjeta from "../components/Tarjeta";

function periodoActual() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function CierreDePeriodo() {
  const navigate = useNavigate();
  const [periodo, setPeriodo] = useState(periodoActual());
  const [estado, setEstado] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  useEffect(() => {
    setPreview(null);
    setError(null);
    (async () => {
      const r = await estadoPeriodo(periodo);
      if (r.status === 200) setEstado(r.data);
      else if (r.status !== 401) setError("No se pudo cargar el estado del período.");
    })();
  }, [periodo]);

  async function handleGenerarPreview() {
    setCargando(true);
    const r = await previewPeriodo(periodo);
    setCargando(false);
    if (r.status === 200) setPreview(r.data);
    else setError(r.data?.detail || "No se pudo generar el preview.");
  }

  async function handleConfirmar() {
    if (!preview) return;
    setConfirmando(true);
    const r = await cerrarPeriodo(periodo, {
      fecha_primer_vencimiento: preview.fecha_primer_vencimiento,
      fecha_segundo_vencimiento: preview.fecha_segundo_vencimiento,
    });
    setConfirmando(false);
    if (r.status === 201) {
      navigate("/periodos");
    } else {
      setError(r.data?.detail || "No se pudo cerrar el período.");
    }
  }

  return (
    <section>
      <h2>Cierre de período</h2>
      <label>
        Período:{" "}
        <input
          type="month"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </label>

      {error && <p role="alert" className="error-banner">{error}</p>}

      {!preview && estado && (
        <Tarjeta>
          <h3>Estado de {periodo}</h3>
          {estado.cerrado && <p><strong>⚠ Este período ya fue cerrado.</strong></p>}
          <ul className="lista-validaciones">
            {estado.validaciones.map((v, i) => (
              <li key={i} className={`val-${v.tipo}`}>
                {v.tipo === "bloqueante" ? "✗" : "⚠"} {v.mensaje}
              </li>
            ))}
            {estado.validaciones.length === 0 && <li>✓ Sin observaciones.</li>}
          </ul>
          <button
            type="button"
            onClick={handleGenerarPreview}
            disabled={!estado.puede_cerrar || cargando}
          >
            {cargando ? "Generando…" : "Generar preview"}
          </button>
        </Tarjeta>
      )}

      {preview && (
        <Tarjeta>
          <h3>Vista previa de cierre — {periodo}</h3>
          <div>
            Total a expensar: <strong>{formatMoney(preview.total_expensado)}</strong>
            {" · "}Boletas: {preview.expensas.length}
            {" · "}Intereses: {formatMoney(preview.total_intereses)}
          </div>
          <ul>
            {preview.expensas.map((e) => (
              <li key={e.departamento_id}>
                Depto {e.departamento_id}: {formatMoney(e.monto_primer_vencimiento)}
                {e.saldo_anterior > 0 && ` + ${formatMoney(e.saldo_anterior)} saldo ant.`}
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => setPreview(null)}>← Volver</button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm("¿Confirmar cierre? Esta acción es irreversible.")) {
                handleConfirmar();
              }
            }}
            disabled={!preview.puede_cerrar || confirmando}
          >
            {confirmando ? "Cerrando…" : "Confirmar cierre del mes"}
          </button>
        </Tarjeta>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Build**

```bash
cd frontend && npm run build
```
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/CierreDePeriodo.jsx
git commit -m "feat(frontend): pantalla /cierre-de-periodo con modos Estado y Preview"
```

---

## Task 14: Pantalla `/periodos` (historial admin)

**Files:**
- Create: `frontend/src/screens/Periodos.jsx`

- [ ] **Step 1: Crear el archivo**

```jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarPeriodos } from "../api/periodos";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function Periodos() {
  const [periodos, setPeriodos] = useState([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    (async () => {
      const r = await listarPeriodos();
      if (r.status === 200) setPeriodos(r.data);
      setCargando(false);
    })();
  }, []);

  if (cargando) return <p>Cargando…</p>;

  return (
    <section>
      <h2>Historial de cierres</h2>
      {periodos.length === 0 ? (
        <p>Todavía no hay períodos cerrados.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Período</th>
              <th>Cerrado el</th>
              <th>Boletas</th>
              <th>Total expensado</th>
              <th>Intereses</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {periodos.map((p) => (
              <tr key={p.periodo}>
                <td>{p.periodo}</td>
                <td>{new Date(p.fecha_cierre).toLocaleString("es-AR")}</td>
                <td>{p.cantidad_expensas}</td>
                <td>{formatMoney(p.total_expensado)}</td>
                <td>{formatMoney(p.total_intereses)}</td>
                <td><Link to={`/expensas?periodo=${p.periodo}`}>Ver expensas</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/screens/Periodos.jsx
git commit -m "feat(frontend): pantalla /periodos historial de cierres"
```

---

## Task 15: Modal de desglose + ajustes en Expensas y MiCuenta

**Files:**
- Create: `frontend/src/components/ModalDesgloseExpensa.jsx`
- Modify: `frontend/src/screens/Expensas.jsx`
- Modify: `frontend/src/screens/MiCuenta.jsx`

- [ ] **Step 1: Crear `ModalDesgloseExpensa.jsx`**

```jsx
import Modal from "./Modal";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

const NOMBRES_RUBRO = {
  sueldos_y_cargas_sociales: "Sueldos y cargas sociales",
  servicios: "Servicios",
  reparaciones: "Reparaciones",
  administracion: "Administración",
  otros: "Otros",
};

export default function ModalDesgloseExpensa({ expensa, onClose }) {
  const detalle = expensa.detalle || [];
  // agrupar por rubro
  const grupos = {};
  for (const d of detalle) {
    grupos[d.rubro] = grupos[d.rubro] || [];
    grupos[d.rubro].push(d);
  }
  const total = detalle.reduce((acc, d) => acc + d.monto, 0);

  return (
    <Modal titulo={`Desglose Expensa ${expensa.periodo}`} onClose={onClose}>
      {detalle.length === 0 && <p>Esta expensa no tiene detalle (creación individual).</p>}
      {Object.entries(grupos).map(([rubro, lineas]) => {
        const sub = lineas.reduce((acc, d) => acc + d.monto, 0);
        return (
          <div key={rubro}>
            <h4>{NOMBRES_RUBRO[rubro] || rubro} — {formatMoney(sub)}</h4>
            <ul>
              {lineas.map((d, i) => (
                <li key={i}>
                  {d.departamento_origen_id ? "Particular" : `Clase ${d.clase_prorrateo_id}`}
                  {" · "}{d.concepto}
                  {" · "}{formatMoney(d.monto)}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <hr />
      <p><strong>Total: {formatMoney(total)}</strong></p>
    </Modal>
  );
}
```

- [ ] **Step 2: En `Expensas.jsx`, adaptar `TarjetaExpensa`**

Localizar el JSX que renderiza monto y vencimiento. Reemplazar el bloque "Vence X — $monto" por:

```jsx
<>
  <h3>{expensa.periodo}</h3>
  <p className="meta">
    1° venc {expensa.fecha_primer_vencimiento}: <strong>{formatMoney(expensa.monto_primer_vencimiento)}</strong>
  </p>
  <p className="meta">
    2° venc {expensa.fecha_segundo_vencimiento}: {formatMoney(expensa.monto_segundo_vencimiento)} (+recargo)
  </p>
  {expensa.saldo_anterior > 0 && (
    <p className="meta">Saldo anterior: {formatMoney(expensa.saldo_anterior)}</p>
  )}
  <p>
    <BadgeEstado estado={expensa.estado_calculado} />
    <button type="button" onClick={() => onVerDesglose(expensa)}>Ver desglose</button>
  </p>
</>
```

Sumar state local `modalDesglose` y el render del modal.

- [ ] **Step 3: En `MiCuenta.jsx`, sumar bloque "Próximo vencimiento"**

Localizar el bloque que renderiza el saldo actual. Justo después del saldo, agregar:

```jsx
{proximaExpensa && (
  <Tarjeta>
    <h3>Próximo vencimiento</h3>
    <p>
      Si pagás hasta el {proximaExpensa.fecha_primer_vencimiento}:{" "}
      <strong>{formatMoney(proximaExpensa.monto_primer_vencimiento)}</strong>
    </p>
    <p>
      Del {sumarDias(proximaExpensa.fecha_primer_vencimiento, 1)} al{" "}
      {proximaExpensa.fecha_segundo_vencimiento}:{" "}
      <strong>{formatMoney(proximaExpensa.monto_segundo_vencimiento)}</strong> (+recargo)
    </p>
    <p className="meta">
      Después del {proximaExpensa.fecha_segundo_vencimiento}: se acumulan intereses mensuales.
    </p>
  </Tarjeta>
)}
```

Donde `proximaExpensa` es la expensa con menor `fecha_primer_vencimiento` futura del depto (calcular del array de expensas que ya carga la pantalla). Helper `sumarDias(fecha, n)`:

```javascript
function sumarDias(yyyymmdd, n) {
  const d = new Date(yyyymmdd);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
```

- [ ] **Step 4: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/components/ModalDesgloseExpensa.jsx frontend/src/screens/Expensas.jsx frontend/src/screens/MiCuenta.jsx
git commit -m "feat(frontend): modal desglose + TarjetaExpensa con 1°/2° venc + saldo ant."
```

---

## Task 16: Configuración — form con los 4 nuevos campos

**Files:**
- Modify: `frontend/src/screens/Configuracion.jsx`

- [ ] **Step 1: Sumar al form los 4 campos**

Localizar dónde se renderiza el form de configuración. Agregar una sección nueva:

```jsx
<fieldset>
  <legend>Vencimientos e intereses</legend>
  <label>
    Día del 1° vencimiento
    <input
      type="number" min="1" max="28"
      value={form.dia_primer_vencimiento}
      onChange={(e) => setForm({ ...form, dia_primer_vencimiento: Number(e.target.value) })}
    />
  </label>
  <label>
    Días entre 1° y 2° vencimiento
    <input
      type="number" min="1"
      value={form.dias_entre_vencimientos}
      onChange={(e) => setForm({ ...form, dias_entre_vencimientos: Number(e.target.value) })}
    />
  </label>
  <label>
    % recargo del 2° vencimiento
    <input
      type="number" step="0.5" min="0"
      value={form.recargo_segundo_vencimiento_pct}
      onChange={(e) => setForm({ ...form, recargo_segundo_vencimiento_pct: Number(e.target.value) })}
    />
  </label>
  <label>
    % interés mensual punitorio
    <input
      type="number" step="0.5" min="0"
      value={form.tasa_interes_mensual_pct}
      onChange={(e) => setForm({ ...form, tasa_interes_mensual_pct: Number(e.target.value) })}
    />
  </label>
</fieldset>
```

- [ ] **Step 2: Asegurar que el state inicial del form incluye los 4 campos**

Cuando se carga la config inicial del GET, propagar los 4 valores al state.

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/screens/Configuracion.jsx
git commit -m "feat(frontend/configuracion): sección Vencimientos e intereses con 4 campos"
```

---

## Task 17: Sidebar + Routes + bloqueos visuales de gastos

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/screens/Gastos.jsx`

- [ ] **Step 1: Sidebar — sumar 2 entries en sección "Expensas y pagos"**

Localizar el array `SECCIONES`. En la sección "Expensas y pagos", agregar **antes** de "Gastos":

```javascript
{
  ruta: "/cierre-de-periodo",
  nombre: "Cierre de período",
  rolesPermitidos: ["administracion"],
},
{
  ruta: "/periodos",
  nombre: "Historial de cierres",
  rolesPermitidos: ["administracion"],
},
```

- [ ] **Step 2: App.jsx — sumar 2 rutas**

Buscar el bloque de `<Route>`. Sumar:

```jsx
<Route path="/cierre-de-periodo" element={
  <RequiereRol roles={["administracion"]}><CierreDePeriodo /></RequiereRol>
} />
<Route path="/periodos" element={
  <RequiereRol roles={["administracion"]}><Periodos /></RequiereRol>
} />
```

Sumar imports correspondientes arriba.

- [ ] **Step 3: Gastos.jsx — candado para gastos de período cerrado**

Para esto necesitamos saber qué períodos están cerrados. Opciones:
- (a) Llamar `listarPeriodos()` al montar y guardar el set de cerrados.
- (b) Confiar en que el backend devuelve 409 al editar y mostrar error.

Lo más limpio es (a). Localizar el componente Gastos. Sumar:

```jsx
const [cerrados, setCerrados] = useState(new Set());

useEffect(() => {
  (async () => {
    const r = await listarPeriodos();
    if (r.status === 200) {
      setCerrados(new Set(r.data.map((p) => p.periodo)));
    }
  })();
}, []);
```

En la fila de cada gasto:
```jsx
{cerrados.has(gasto.periodo) ? (
  <span title="Período cerrado — no editable">🔒</span>
) : (
  <>
    <button onClick={() => editar(gasto)}>Editar</button>
    <button onClick={() => borrar(gasto)}>Borrar</button>
  </>
)}
```

- [ ] **Step 4: Build + smoke**

```bash
cd frontend && npm run build
```
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.jsx frontend/src/App.jsx frontend/src/screens/Gastos.jsx
git commit -m "feat(frontend): sidebar/routes para cierre + historial; candado en Gastos cerrados"
```

---

## Task 18: Smoke manual + merge + roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`

- [ ] **Step 1: Reset completo de DB + arrancar uvicorn + frontend**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
# terminal 1:
./.venv/Scripts/python.exe -m uvicorn backend.main:app --reload
# terminal 2:
cd frontend; npm run dev
```

- [ ] **Step 2: Smoke flow E2E**

Login admin → ir a `/cierre-de-periodo` → seleccionar mes corriente → ver checklist → "Generar preview" → revisar montos → "Confirmar cierre" → navegar a `/periodos` → verificar el período en historial → ir a `/expensas?periodo=YYYY-MM` → verificar 2 boletas → abrir "Ver desglose" en una → verificar líneas por rubro.

Logout. Login depto-a → `/mi-cuenta` → verificar saldo actualizado + próximo vencimiento detallado.

Logout. Login admin → ir a `/gastos` → tratar de editar un gasto del período recién cerrado → debe aparecer candado, no botones.

Logout. Login admin → ir a `/cierre-de-periodo` → seleccionar **mismo mes** → estado debe decir "ya cerrado".

- [ ] **Step 3: Si algo falla, anotar y arreglar antes de mergear**

Solo si todo el smoke verde, seguir.

- [ ] **Step 4: Run suite final**

```bash
./.venv/Scripts/python.exe -m pytest -v
```
Expected: **490+ tests passing** (453 baseline + ~40 nuevos).

- [ ] **Step 5: Actualizar roadmap**

En `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`, marcar Fase 4 como ✅:

```markdown
| **4** ✅ | **Cierre de período y liquidación** (completada YYYY-MM-DD) | ...
```

Agregar al historial de cambios:
```markdown
- YYYY-MM-DD: **Fase 4 completada** (490+ tests, mergeada a master). Cierre formal con preview-resumen, snapshot ExpensaDetalle, 1°/2° venc, intereses automáticos.
```

Actualizar "Próximo paso":
```markdown
Brainstorming de Fase 5 (Caja, fondo de reparación, estado financiero).
```

- [ ] **Step 6: Commit roadmap update + merge a master**

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 4 completada (cierre de período y liquidación)"

git checkout master
git merge --no-ff feature/expensas-fase4-cierre -m "Merge feature/expensas-fase4-cierre: cierre de período y liquidación

Fase 4 — Cierre formal con tabla PeriodoCerrado. Genera N expensas con
desglose por rubro/clase (ExpensaDetalle), 1°/2° vencimiento con recargo,
saldo anterior heredado e intereses automáticos sobre morosos."
```

- [ ] **Step 7: Push**

```bash
git push origin master
git push origin feature/expensas-fase4-cierre  # opcional, para historial
```

- [ ] **Step 8: Done. Fase 5 disponible para brainstorming.**

---

## Notas finales

- **Orden de tasks razonado:** modelos primero (1), schemas (2), módulo puro con tests (3), fixtures (4), adaptar tests existentes (5), routers (6-9), docs (10), seed (11). Frontend al final (12-17), después del backend estable. Smoke + merge (18).
- **TDD discipline:** Tasks 3, 7, 9 contienen pares `test → implementation → run`. Las demás son cambios incrementales chicos cubiertos por la suite existente.
- **Commits frecuentes:** cada task termina con su propio commit. ~18 commits totales para la fase.
- **Bloqueos cross-recurso:** se centraliza en Task 8 para no duplicar reglas en cada router. Si más adelante crece, mover a `backend/helpers.py`.
- **Migración:** clean start (borrar `consorcio.db`). Se mantiene el patrón Fase 1-3.5 — no hay datos productivos a preservar.
