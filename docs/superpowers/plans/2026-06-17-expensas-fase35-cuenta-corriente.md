# Expensas Fase 3.5 — Cuenta corriente por departamento — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el modelo binario `Expensa.estado=pendiente|pagada` por una cuenta corriente por departamento con movimientos contables (débitos/créditos). Los comprobantes aprobados generan movimientos en lugar de marcar la expensa. Estado de la expensa se calcula on-the-fly (FIFO) desde los movimientos.

**Architecture:**
- Tabla nueva `movimientos_cuenta` con `tipo` enum + `monto > 0` + opcional `expensa_id` / `comprobante_id`.
- `Expensa.estado` eliminado; `EstadoExpensa` enum sigue en `models.py` para respuestas (no se persiste).
- `Comprobante.expensa_id` reemplazado por `Comprobante.departamento_id` (depto presenta pago a su cuenta).
- Módulo `backend/cuenta_corriente.py` con función pura `calcular_estado_cuenta()` (FIFO) — única fuente de verdad para saldos y estado calculado.
- Frontend: pantalla `/mi-cuenta` (depto), `/departamentos/{id}/cuenta` (admin), pantallas existentes de expensas/comprobantes adaptadas.
- Migración: clean start (borrar `consorcio.db`, re-seedear). No hay datos productivos.

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2; React 18 + Vite + react-router-dom; pytest.

**Spec:** `docs/superpowers/specs/2026-06-17-expensas-fase35-cuenta-corriente-design.md`

---

## File structure

**Backend — nuevos:**
- `backend/cuenta_corriente.py` — función pura FIFO `calcular_estado_cuenta()`, retorna `EstadoCuenta` dataclass.
- `backend/routers/movimientos.py` — 3 endpoints: GET mi-cuenta, GET cuenta admin, POST nota.
- `tests/test_cuenta_corriente.py` — unit tests FIFO sin HTTP.
- `tests/test_movimientos.py` — tests HTTP del nuevo router.

**Backend — modificados:**
- `backend/models.py` — sumar `TipoMovimiento` enum, sumar `MovimientoCuenta`, sumar `EstadoExpensa.parcial`, quitar `Expensa.estado` + `Expensa.comprobantes` relationship, cambiar `Comprobante.expensa_id` → `Comprobante.departamento_id` + relationship.
- `backend/schemas.py` — sumar `TipoMovimiento` reexport, `MovimientoCuentaOut`, `EstadoCuentaOut`, `NotaCrear`, `ComprobantePresentar` (sin expensa_id), modificar `ExpensaOut` (sin `estado`, sumar `estado_calculado` y `monto_pendiente`), modificar `ComprobanteOut` (sin `expensa_id`, sumar `departamento_id`).
- `backend/routers/expensas.py` — POST genera movimiento `expensa_emitida`; GET retorna `estado_calculado` + `monto_pendiente`; DELETE nuevo (admin, 409 si tiene pagos); eliminar POST `/expensas/{id}/comprobantes`; eliminar filtro `estado`.
- `backend/routers/comprobantes.py` — POST `/comprobantes` (depto, multipart, sin expensa_id); PATCH aprobar genera movimiento `pago_recibido`.
- `backend/main.py` — registrar router `movimientos`.
- `backend/seed.py` — crear movimientos por cada expensa y comprobante aprobado seedeado; sumar 1 nota crédito + 1 nota débito de ejemplo; quitar `Expensa.estado` y `Comprobante.expensa_id`.
- `tests/conftest.py` — análogo a seed; sumar fixtures con movimientos.
- `tests/test_expensas.py` — quitar asserts sobre `estado` persistido, sumar asserts sobre `estado_calculado`; sumar tests de DELETE.
- `tests/test_comprobantes.py` — cambiar POST path, quitar `expensa_id`, sumar test "aprobar genera movimiento".

**Docs:**
- `openapi.yaml` — sumar paths de movimientos, modificar `ExpensaOut`, `ComprobanteOut`, declarar tag `Movimientos`.

**Frontend — nuevos:**
- `frontend/src/api/movimientos.js` — `listarMisMovimientos`, `listarMovimientosDepto`, `crearNota`.
- `frontend/src/screens/MiCuenta.jsx` — pantalla depto con saldo + extracto + botón "Presentar pago".
- `frontend/src/screens/DepartamentoCuenta.jsx` — pantalla admin con saldo + extracto + botones nota crédito/débito.

**Frontend — modificados:**
- `frontend/src/api/comprobantes.js` — `presentarComprobante` sin `expensaId`.
- `frontend/src/api/expensas.js` — sumar `eliminarExpensa`; response trae `estado_calculado` y `monto_pendiente`.
- `frontend/src/screens/Expensas.jsx` — usar `estado_calculado`, quitar botón "Presentar comprobante" por tarjeta, sumar pill de vencimiento.
- `frontend/src/screens/Comprobantes.jsx` — el form del depto ya no pide expensa.
- `frontend/src/components/Sidebar.jsx` — sección "Expensas y pagos" con "Mi cuenta" primero (depto); botón "Cuenta del depto" en pantalla admin (ya cubierto en pantalla, no sidebar).
- `frontend/src/App.jsx` — rutas `/mi-cuenta` y `/departamentos/:id/cuenta`.

---

## Task 0: Setup — branch + clean DB + baseline

**Files:** ninguno modificado todavía.

- [ ] **Step 1: Crear branch desde `master`**

```bash
git checkout master
git pull --ff-only
git checkout -b feature/expensas-fase35-cuenta-corriente
```

- [ ] **Step 2: Borrar DB local para clean start (Fase 1-3 patrón consistente)**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
```

(Bash equivalent: `rm -f consorcio.db`)

- [ ] **Step 3: Correr suite actual para confirmar baseline verde antes de empezar**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: PASS — todos los tests existentes pasan en la rama recién creada.

- [ ] **Step 4: Commit del branch limpio (no hay cambios todavía; opcional skip si rama vacía)**

No-op si no hay cambios. Si hay cambios menores no relacionados, no commitearlos: deben hacerse en otro branch.

---

## Task 1: Models — TipoMovimiento + MovimientoCuenta + cambios a Expensa/Comprobante

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Localizar el bloque de enums (alrededor de line 45) y modificar `EstadoExpensa` para sumar `parcial`**

Abrir `backend/models.py`. Reemplazar el enum `EstadoExpensa` por:

```python
class EstadoExpensa(str, enum.Enum):
    pendiente = "pendiente"
    parcial = "parcial"
    pagada = "pagada"
    vencida = "vencida"
```

- [ ] **Step 2: Sumar el enum `TipoMovimiento` justo después de `EstadoComprobante`**

Buscar el final del bloque de enums (después de `EstadoComprobante`). Insertar:

```python
class TipoMovimiento(str, enum.Enum):
    expensa_emitida = "expensa_emitida"
    pago_recibido = "pago_recibido"
    interes_punitorio = "interes_punitorio"
    nota_debito = "nota_debito"
    nota_credito = "nota_credito"


TIPOS_DEBITO = frozenset({
    TipoMovimiento.expensa_emitida,
    TipoMovimiento.interes_punitorio,
    TipoMovimiento.nota_debito,
})
TIPOS_CREDITO = frozenset({
    TipoMovimiento.pago_recibido,
    TipoMovimiento.nota_credito,
})
```

- [ ] **Step 3: Modificar la clase `Expensa` — quitar `estado` y `comprobantes` relationship**

Reemplazar la clase `Expensa` (líneas ~219-245) por:

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
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    departamento: Mapped["Departamento"] = relationship(back_populates="expensas")
```

- [ ] **Step 4: Modificar la clase `Comprobante` — `expensa_id` → `departamento_id`**

Reemplazar la clase `Comprobante` (líneas ~248-269) por:

```python
class Comprobante(Base):
    __tablename__ = "comprobantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    archivo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estado: Mapped[EstadoComprobante] = mapped_column(
        SqlEnum(EstadoComprobante, name="estado_comprobante"),
        nullable=False,
        default=EstadoComprobante.pendiente_verificacion,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship()
```

- [ ] **Step 5: Sumar la clase `MovimientoCuenta` al final del archivo (después de la última tabla, antes de cualquier index helper si lo hubiera)**

Insertar:

```python
class MovimientoCuenta(Base):
    __tablename__ = "movimientos_cuenta"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[TipoMovimiento] = mapped_column(
        SqlEnum(TipoMovimiento, name="tipo_movimiento"),
        nullable=False,
    )
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    expensa_id: Mapped[int | None] = mapped_column(
        ForeignKey("expensas.id", ondelete="SET NULL"),
        nullable=True,
    )
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="SET NULL"),
        nullable=True,
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    departamento: Mapped["Departamento"] = relationship()
    expensa: Mapped["Expensa | None"] = relationship()
    comprobante: Mapped["Comprobante | None"] = relationship()
```

- [ ] **Step 6: Borrar la DB local (esquema cambió)**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
```

- [ ] **Step 7: Smoke check que la app importa sin error**

Run: `./.venv/Scripts/python.exe -c "from backend.models import MovimientoCuenta, TipoMovimiento, EstadoExpensa; print(TipoMovimiento.pago_recibido, EstadoExpensa.parcial)"`
Expected: imprime `TipoMovimiento.pago_recibido EstadoExpensa.parcial` sin error.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py
git commit -m "feat(models): MovimientoCuenta, TipoMovimiento; Expensa sin estado; Comprobante con departamento_id"
```

---

## Task 2: Schemas Pydantic

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Reexportar `TipoMovimiento` y `EstadoExpensa` desde schemas si el patrón existente lo hace; o importarlo donde haga falta**

Abrir `backend/schemas.py`. Buscar el bloque de imports desde `.models`. Sumar `TipoMovimiento` al import (y verificar que `EstadoExpensa` ya esté).

- [ ] **Step 2: Modificar `ExpensaOut` — quitar `estado` persistido, sumar `estado_calculado` y `monto_pendiente`**

Buscar la clase `ExpensaOut`. Reemplazar por:

```python
class ExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    periodo: str
    monto: float
    fecha_vencimiento: date
    estado_calculado: EstadoExpensa
    monto_pendiente: float
    ultimo_comprobante: Optional["ComprobanteOut"] = None
```

(Si `ultimo_comprobante` ya no aplica porque comprobante perdió FK a expensa, evaluar quitarlo. Decisión: **quitarlo** — la pantalla de expensas ya no muestra "tu último pago de esta expensa". Si está, eliminar la línea.)

Versión final sin `ultimo_comprobante`:

```python
class ExpensaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    periodo: str
    monto: float
    fecha_vencimiento: date
    estado_calculado: EstadoExpensa
    monto_pendiente: float
```

- [ ] **Step 3: Modificar `ComprobanteOut` — `expensa_id` → `departamento_id`**

Buscar `ComprobanteOut`. Reemplazar campo `expensa_id: int` por `departamento_id: int`.

- [ ] **Step 4: Sumar `ComprobantePresentar` (input del depto, sin expensa_id)**

Si hay un schema existente tipo `ComprobanteCrear`, eliminarlo o reemplazarlo. Sumar:

```python
class ComprobantePresentar(BaseModel):
    fecha_pago: date
    monto: float = Field(gt=0)
```

(El archivo viene aparte vía `UploadFile`, no en el body Pydantic.)

- [ ] **Step 5: Sumar schemas de movimientos**

Al final del archivo:

```python
class MovimientoCuentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    departamento_id: int
    fecha: date
    tipo: TipoMovimiento
    descripcion: str
    monto: float
    expensa_id: Optional[int] = None
    comprobante_id: Optional[int] = None
    fecha_creacion: datetime


class EstadoCuentaOut(BaseModel):
    departamento_id: int
    saldo_total: float
    movimientos: list[MovimientoCuentaOut]


class NotaCrear(BaseModel):
    departamento_id: int
    tipo: TipoMovimiento
    monto: float = Field(gt=0)
    descripcion: str = Field(min_length=1, max_length=500)
    fecha: Optional[date] = None

    @field_validator("tipo")
    @classmethod
    def solo_nota(cls, v: TipoMovimiento) -> TipoMovimiento:
        if v not in (TipoMovimiento.nota_credito, TipoMovimiento.nota_debito):
            raise ValueError("tipo debe ser nota_credito o nota_debito")
        return v
```

(Verificar imports: `field_validator`, `Field`, `Optional`, `date`, `datetime`, `TipoMovimiento`. Sumar los que falten al top del archivo.)

- [ ] **Step 6: Smoke import**

Run: `./.venv/Scripts/python.exe -c "from backend.schemas import MovimientoCuentaOut, EstadoCuentaOut, NotaCrear, ComprobantePresentar; print('ok')"`
Expected: imprime `ok`.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas.py
git commit -m "feat(schemas): MovimientoCuenta, NotaCrear, ExpensaOut con estado_calculado"
```

---

## Task 3: Módulo `cuenta_corriente.py` — FIFO con tests unitarios

**Files:**
- Create: `backend/cuenta_corriente.py`
- Create: `tests/test_cuenta_corriente.py`

- [ ] **Step 1: Escribir el test ANTES de la implementación — pago exacto cubre 1 expensa**

Crear `tests/test_cuenta_corriente.py`:

```python
"""Tests unitarios del módulo cuenta_corriente (FIFO). Sin HTTP, contra DB en memoria."""
from datetime import date

import pytest

from backend.cuenta_corriente import calcular_estado_cuenta
from backend.models import (
    Departamento,
    EstadoExpensa,
    Expensa,
    MovimientoCuenta,
    TipoMovimiento,
)


@pytest.fixture
def depto(db_session):
    d = Departamento(id=1, codigo="1A", descripcion="1° A")
    db_session.add(d)
    db_session.commit()
    return d


def _mov_expensa(db, depto_id, expensa_id, monto, fecha):
    db.add(
        MovimientoCuenta(
            departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {expensa_id}",
            monto=monto,
            expensa_id=expensa_id,
        )
    )


def _mov_pago(db, depto_id, monto, fecha, comprobante_id=None):
    db.add(
        MovimientoCuenta(
            departamento_id=depto_id,
            fecha=fecha,
            tipo=TipoMovimiento.pago_recibido,
            descripcion="Pago",
            monto=monto,
            comprobante_id=comprobante_id,
        )
    )


def test_pago_exacto_cubre_una_expensa(db_session, depto):
    e = Expensa(
        id=1,
        departamento_id=depto.id,
        periodo="2026-05",
        monto=1000.0,
        fecha_vencimiento=date(2026, 6, 10),
    )
    db_session.add(e)
    _mov_expensa(db_session, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_session, depto.id, 1000.0, date(2026, 6, 1))
    db_session.commit()

    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))

    assert estado.saldo_total == 0.0
    assert estado.por_expensa[1].monto_pagado == 1000.0
    assert estado.por_expensa[1].monto_pendiente == 0.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada
```

- [ ] **Step 2: Sumar fixture `db_session` al conftest si no existe**

Abrir `tests/conftest.py`. Si no hay un fixture `db_session` (solo TestClient), sumar:

```python
@pytest.fixture
def db_session():
    """Sesión SQLAlchemy aislada para tests unitarios sin HTTP."""
    from backend.database import Base, engine, SessionLocal
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
```

(Si ya existe algo equivalente o si el conftest usa otro patrón, adaptarse. El patrón actual del proyecto usa `db_test` o `client` — chequear y reutilizar. Si reutilizás `client`, podés sacar la sesión vía `client.app.dependency_overrides[get_db]`.)

- [ ] **Step 3: Correr el test — debe FALLAR porque `calcular_estado_cuenta` no existe**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cuenta_corriente.py::test_pago_exacto_cubre_una_expensa -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.cuenta_corriente'` o `ImportError`.

- [ ] **Step 4: Implementar `backend/cuenta_corriente.py` mínimo**

```python
"""Cuenta corriente por departamento — cálculo FIFO de saldo y estado por expensa.

Función pura: lee movimientos y expensas del depto, aplica FIFO en memoria,
retorna saldo total y estado calculado por expensa. No tiene side effects.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    EstadoExpensa,
    Expensa,
    MovimientoCuenta,
    TIPOS_CREDITO,
    TIPOS_DEBITO,
    TipoMovimiento,
)


@dataclass
class EstadoExpensaCalculado:
    expensa_id: int
    monto_total: float
    monto_pagado: float
    monto_pendiente: float
    estado: EstadoExpensa


@dataclass
class EstadoCuenta:
    departamento_id: int
    saldo_total: float
    por_expensa: dict[int, EstadoExpensaCalculado] = field(default_factory=dict)


def calcular_estado_cuenta(
    db: Session, departamento_id: int, hoy: date | None = None
) -> EstadoCuenta:
    hoy = hoy or date.today()

    expensas = list(
        db.scalars(
            select(Expensa)
            .where(Expensa.departamento_id == departamento_id)
            .order_by(Expensa.fecha_vencimiento.asc(), Expensa.id.asc())
        ).all()
    )

    movimientos = list(
        db.scalars(
            select(MovimientoCuenta)
            .where(MovimientoCuenta.departamento_id == departamento_id)
            .order_by(MovimientoCuenta.fecha.asc(), MovimientoCuenta.id.asc())
        ).all()
    )

    pendientes: dict[int, float] = {e.id: e.monto for e in expensas}
    pagado_por_expensa: dict[int, float] = {e.id: 0.0 for e in expensas}

    saldo_total = 0.0
    credito_disponible = 0.0

    for m in movimientos:
        if m.tipo in TIPOS_DEBITO:
            saldo_total += m.monto
        else:
            saldo_total -= m.monto
            credito_disponible += m.monto

    # FIFO: el crédito acumulado se aplica a las expensas más viejas.
    for e in expensas:
        if credito_disponible <= 0:
            break
        cubierto = min(credito_disponible, pendientes[e.id])
        pagado_por_expensa[e.id] = cubierto
        pendientes[e.id] -= cubierto
        credito_disponible -= cubierto

    por_expensa: dict[int, EstadoExpensaCalculado] = {}
    for e in expensas:
        pagado = pagado_por_expensa[e.id]
        pendiente = pendientes[e.id]
        if pendiente <= 0.001:
            estado = EstadoExpensa.pagada
        elif pagado > 0:
            estado = EstadoExpensa.parcial
        elif e.fecha_vencimiento < hoy:
            estado = EstadoExpensa.vencida
        else:
            estado = EstadoExpensa.pendiente
        por_expensa[e.id] = EstadoExpensaCalculado(
            expensa_id=e.id,
            monto_total=e.monto,
            monto_pagado=pagado,
            monto_pendiente=pendiente,
            estado=estado,
        )

    return EstadoCuenta(
        departamento_id=departamento_id,
        saldo_total=saldo_total,
        por_expensa=por_expensa,
    )
```

- [ ] **Step 5: Re-correr el test — PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cuenta_corriente.py::test_pago_exacto_cubre_una_expensa -v`
Expected: PASS.

- [ ] **Step 6: Sumar tests de los casos restantes**

Agregar al mismo archivo:

```python
def test_pago_parcial(db_session, depto):
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                fecha_vencimiento=date(2026, 6, 10))
    db_session.add(e)
    _mov_expensa(db_session, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_session, depto.id, 600.0, date(2026, 6, 1))
    db_session.commit()

    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 400.0
    assert estado.por_expensa[1].monto_pagado == 600.0
    assert estado.por_expensa[1].monto_pendiente == 400.0
    assert estado.por_expensa[1].estado == EstadoExpensa.parcial


def test_sobre_pago_genera_credito(db_session, depto):
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                fecha_vencimiento=date(2026, 6, 10))
    db_session.add(e)
    _mov_expensa(db_session, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_session, depto.id, 1500.0, date(2026, 6, 1))
    db_session.commit()

    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == -500.0  # crédito a favor
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada


def test_un_pago_cubre_dos_expensas_fifo(db_session, depto):
    e1 = Expensa(id=1, departamento_id=depto.id, periodo="2026-04", monto=1000.0,
                 fecha_vencimiento=date(2026, 5, 10))
    e2 = Expensa(id=2, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                 fecha_vencimiento=date(2026, 6, 10))
    db_session.add_all([e1, e2])
    _mov_expensa(db_session, depto.id, e1.id, 1000.0, date(2026, 4, 10))
    _mov_expensa(db_session, depto.id, e2.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_session, depto.id, 1500.0, date(2026, 6, 1))
    db_session.commit()

    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 500.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pagada  # FIFO: la vieja primero
    assert estado.por_expensa[2].estado == EstadoExpensa.parcial
    assert estado.por_expensa[2].monto_pendiente == 500.0


def test_nota_credito_y_debito(db_session, depto):
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-05", monto=1000.0,
                fecha_vencimiento=date(2026, 6, 10))
    db_session.add(e)
    _mov_expensa(db_session, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_session.add(MovimientoCuenta(
        departamento_id=depto.id, fecha=date(2026, 6, 1),
        tipo=TipoMovimiento.nota_credito, descripcion="Bonif.", monto=200.0,
    ))
    db_session.add(MovimientoCuenta(
        departamento_id=depto.id, fecha=date(2026, 6, 2),
        tipo=TipoMovimiento.nota_debito, descripcion="Ajuste", monto=50.0,
    ))
    db_session.commit()

    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))
    # 1000 (expensa) - 200 (NC) + 50 (ND) = 850 debe.
    assert estado.saldo_total == 850.0
    # FIFO: NC de 200 se aplica a la expensa.
    assert estado.por_expensa[1].monto_pagado == 200.0
    assert estado.por_expensa[1].estado == EstadoExpensa.parcial


def test_expensa_vencida_sin_pago(db_session, depto):
    e = Expensa(id=1, departamento_id=depto.id, periodo="2026-04", monto=1000.0,
                fecha_vencimiento=date(2026, 5, 10))
    db_session.add(e)
    _mov_expensa(db_session, depto.id, e.id, 1000.0, date(2026, 4, 10))
    db_session.commit()

    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))
    assert estado.por_expensa[1].estado == EstadoExpensa.vencida
    assert estado.saldo_total == 1000.0


def test_depto_sin_movimientos(db_session, depto):
    estado = calcular_estado_cuenta(db_session, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 0.0
    assert estado.por_expensa == {}
```

- [ ] **Step 7: Correr todos los tests del módulo**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cuenta_corriente.py -v`
Expected: PASS los 6 tests.

- [ ] **Step 8: Commit**

```bash
git add backend/cuenta_corriente.py tests/test_cuenta_corriente.py tests/conftest.py
git commit -m "feat(cuenta-corriente): módulo FIFO + tests unitarios (6 casos)"
```

---

## Task 4: Actualizar `tests/conftest.py` para nuevo esquema

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Quitar `estado=EstadoExpensa.pendiente` de las dos `Expensa(...)` seedeadas**

Buscar las dos definiciones de `Expensa(id=100, ...)` y `Expensa(id=101, ...)` (líneas ~143-158). Quitar la línea `estado=EstadoExpensa.pendiente,` de ambas.

- [ ] **Step 2: Quitar el import de `EstadoExpensa` si ya no se usa en el archivo**

Buscar `EstadoExpensa` con grep. Si ya no aparece, quitarlo del bloque de imports.

- [ ] **Step 3: Sumar `MovimientoCuenta` y `TipoMovimiento` a los imports**

```python
from backend.models import (
    # ... lo existente ...
    MovimientoCuenta,
    TipoMovimiento,
)
```

- [ ] **Step 4: Sumar dos movimientos `expensa_emitida` justo después de las dos `Expensa(...)` para mantener consistencia con el modelo**

En el mismo `db.add_all([...])`, después de las dos `Expensa(...)`:

```python
MovimientoCuenta(
    id=1100,
    departamento_id=depto_a.id,
    fecha=date(2026, 5, 1),
    tipo=TipoMovimiento.expensa_emitida,
    descripcion="Expensa 2026-05",
    monto=85000.00,
    expensa_id=100,
),
MovimientoCuenta(
    id=1101,
    departamento_id=depto_b.id,
    fecha=date(2026, 5, 1),
    tipo=TipoMovimiento.expensa_emitida,
    descripcion="Expensa 2026-05",
    monto=92000.00,
    expensa_id=101,
),
```

- [ ] **Step 5: Si hay comprobantes seedeados con `expensa_id`, cambiarlos a `departamento_id`**

Hacer grep en `tests/conftest.py` por `Comprobante(`. Si existe, cambiar `expensa_id=...` por `departamento_id=...`. Si no existe ningún Comprobante en conftest, no hacer nada.

- [ ] **Step 6: Correr toda la suite y observar qué rompe (esperable)**

Run: `./.venv/Scripts/python.exe -m pytest -v --tb=short 2>&1 | head -80`
Expected: tests de cuenta_corriente PASAN; tests de expensas/comprobantes FALLAN (esperable — se fixean en Tasks 5-8).

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): migrar fixtures Expensa/Comprobante a nuevo esquema + movimientos"
```

---

## Task 5: Actualizar `tests/test_expensas.py`

**Files:**
- Modify: `tests/test_expensas.py`

- [ ] **Step 1: Identificar todos los asserts que tocan `estado` de expensa**

```bash
grep -n "estado" tests/test_expensas.py
```

- [ ] **Step 2: Reemplazar asserts sobre `data["estado"]` por `data["estado_calculado"]`**

Edit cada ocurrencia. El valor por defecto sin movimientos sigue siendo `"pendiente"` (sin pagos, no vencida). Para una expensa con pago aplicado, sería `"pagada"` o `"parcial"`.

- [ ] **Step 3: Quitar el filtro `?estado=` en cualquier test que lo use**

Si hay tests que hacen `client.get("/expensas?estado=pendiente")`, eliminar ese test o reemplazarlo por `?estado_calculado=pendiente` **si** decidís soportar el filtro server-side (Task 7 decide). Por defecto, **eliminar el test del filtro** (out of scope esta fase).

- [ ] **Step 4: Sumar test de `DELETE /expensas/{id}` — 204 si no tiene pagos**

```python
def test_delete_expensa_sin_pagos_204(client, admin_headers):
    # Crear expensa nueva
    r = client.post("/expensas", json={
        "departamento_id": 1,
        "periodo": "2026-07",
        "monto": 50000,
        "fecha_vencimiento": "2026-08-10",
    }, headers=admin_headers)
    assert r.status_code == 201
    expensa_id = r.json()["id"]

    r = client.delete(f"/expensas/{expensa_id}", headers=admin_headers)
    assert r.status_code == 204
```

- [ ] **Step 5: Sumar test de DELETE — 409 si tiene pagos**

```python
def test_delete_expensa_con_pagos_409(client, admin_headers, depto_a_headers):
    # depto_a presenta y admin aprueba un comprobante.
    files = {"archivo": ("recibo.pdf", b"%PDF-1.4", "application/pdf")}
    r = client.post("/comprobantes",
                    data={"fecha_pago": "2026-06-05", "monto": "85000"},
                    files=files, headers=depto_a_headers)
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = client.patch(f"/comprobantes/{comp_id}",
                     json={"estado": "aprobado"}, headers=admin_headers)
    assert r.status_code == 200

    # La expensa 100 ahora tiene pago aplicado FIFO.
    r = client.delete("/expensas/100", headers=admin_headers)
    assert r.status_code == 409
    assert "pago" in r.json()["detail"].lower()
```

- [ ] **Step 6: Sumar test "crear expensa genera movimiento expensa_emitida"**

```python
def test_crear_expensa_genera_movimiento(client, admin_headers, depto_a_headers):
    r = client.post("/expensas", json={
        "departamento_id": 1,
        "periodo": "2026-08",
        "monto": 100000,
        "fecha_vencimiento": "2026-09-10",
    }, headers=admin_headers)
    assert r.status_code == 201

    r = client.get("/movimientos/mi-cuenta", headers=depto_a_headers)
    movs = r.json()["movimientos"]
    assert any(
        m["tipo"] == "expensa_emitida" and m["monto"] == 100000
        for m in movs
    )
```

- [ ] **Step 7: Correr el archivo**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_expensas.py -v --tb=short`
Expected: los tests pasarán recién después de Task 7 (router). Por ahora va a fallar — está OK, marcamos como expected fail en el commit.

- [ ] **Step 8: Commit (tests fallando intencionalmente — los fixea Task 7)**

```bash
git add tests/test_expensas.py
git commit -m "test(expensas): adaptar a estado_calculado + sumar tests DELETE y movimiento auto"
```

---

## Task 6: Actualizar `tests/test_comprobantes.py`

**Files:**
- Modify: `tests/test_comprobantes.py`

- [ ] **Step 1: Cambiar todos los `POST /expensas/{id}/comprobantes` por `POST /comprobantes`**

Grep `expensas/.*/comprobantes` y reemplazar el path. El body ya no incluye `expensa_id`.

- [ ] **Step 2: Quitar asserts sobre `data["expensa_id"]`. Reemplazar por `data["departamento_id"]`**

- [ ] **Step 3: Sumar test "aprobar comprobante genera movimiento pago_recibido"**

```python
def test_aprobar_comprobante_genera_movimiento(client, admin_headers, depto_a_headers):
    files = {"archivo": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    r = client.post("/comprobantes",
                    data={"fecha_pago": "2026-06-05", "monto": "30000"},
                    files=files, headers=depto_a_headers)
    comp_id = r.json()["id"]

    r = client.patch(f"/comprobantes/{comp_id}",
                     json={"estado": "aprobado"}, headers=admin_headers)
    assert r.status_code == 200

    r = client.get("/movimientos/mi-cuenta", headers=depto_a_headers)
    movs = r.json()["movimientos"]
    pagos = [m for m in movs if m["tipo"] == "pago_recibido"]
    assert any(m["monto"] == 30000 and m["comprobante_id"] == comp_id for m in pagos)
```

- [ ] **Step 4: Sumar test "rechazar comprobante NO genera movimiento"**

```python
def test_rechazar_comprobante_no_genera_movimiento(client, admin_headers, depto_a_headers):
    files = {"archivo": ("r.pdf", b"%PDF-1.4", "application/pdf")}
    r = client.post("/comprobantes",
                    data={"fecha_pago": "2026-06-05", "monto": "30000"},
                    files=files, headers=depto_a_headers)
    comp_id = r.json()["id"]

    r = client.patch(f"/comprobantes/{comp_id}",
                     json={"estado": "rechazado"}, headers=admin_headers)
    assert r.status_code == 200

    r = client.get("/movimientos/mi-cuenta", headers=depto_a_headers)
    movs = r.json()["movimientos"]
    pagos = [m for m in movs if m["tipo"] == "pago_recibido" and m["comprobante_id"] == comp_id]
    assert pagos == []
```

- [ ] **Step 5: Commit (tests fallando — los fixea Task 8)**

```bash
git add tests/test_comprobantes.py
git commit -m "test(comprobantes): POST sin expensa_id + tests de movimiento generado al aprobar"
```

---

## Task 7: Modificar `backend/routers/expensas.py`

**Files:**
- Modify: `backend/routers/expensas.py`

- [ ] **Step 1: Sumar imports necesarios**

Al top del archivo, sumar/asegurar:

```python
from datetime import date
from fastapi import HTTPException, status
from ..cuenta_corriente import calcular_estado_cuenta
from ..models import MovimientoCuenta, TipoMovimiento
```

- [ ] **Step 2: Reescribir helper `_expensa_to_out`**

Reemplazar por:

```python
def _expensa_to_out(expensa: Expensa, estado_calc) -> ExpensaOut:
    return ExpensaOut(
        id=expensa.id,
        departamento_id=expensa.departamento_id,
        periodo=expensa.periodo,
        monto=expensa.monto,
        fecha_vencimiento=expensa.fecha_vencimiento,
        estado_calculado=estado_calc.estado,
        monto_pendiente=estado_calc.monto_pendiente,
    )
```

- [ ] **Step 3: Refactor `listar_expensas` — quitar filtro `estado`, agrupar por depto y calcular FIFO**

Reemplazar el cuerpo de la función por:

```python
def listar_expensas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    periodo: str | None = Query(None),
    departamento_id: int | None = Query(None),
) -> list[ExpensaOut]:
    stmt = select(Expensa).order_by(Expensa.fecha_vencimiento.desc(), Expensa.id.desc())

    if user.rol == Rol.departamento:
        stmt = stmt.where(Expensa.departamento_id == user.departamento_id)
    elif departamento_id is not None:
        stmt = stmt.where(Expensa.departamento_id == departamento_id)

    if periodo is not None:
        stmt = stmt.where(Expensa.periodo == periodo)

    expensas = list(db.scalars(stmt).all())

    # Calcular estado FIFO una vez por depto.
    estados_por_depto: dict[int, dict[int, "EstadoExpensaCalculado"]] = {}
    out: list[ExpensaOut] = []
    for e in expensas:
        if e.departamento_id not in estados_por_depto:
            estados_por_depto[e.departamento_id] = (
                calcular_estado_cuenta(db, e.departamento_id).por_expensa
            )
        calc = estados_por_depto[e.departamento_id].get(e.id)
        if calc is None:
            continue
        out.append(_expensa_to_out(e, calc))
    return out
```

Quitar el parámetro `estado: EstadoExpensa | None = Query(...)` de la firma.

- [ ] **Step 4: Refactor `crear_expensa` — generar movimiento `expensa_emitida` automáticamente**

```python
def crear_expensa(
    payload: ExpensaCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ExpensaOut:
    existe = db.scalar(
        select(Expensa.id).where(
            Expensa.departamento_id == payload.departamento_id,
            Expensa.periodo == payload.periodo,
        )
    )
    if existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una expensa para ese departamento en ese período.",
        )

    expensa = Expensa(
        departamento_id=payload.departamento_id,
        periodo=payload.periodo,
        monto=payload.monto,
        fecha_vencimiento=payload.fecha_vencimiento,
    )
    db.add(expensa)
    db.flush()

    db.add(MovimientoCuenta(
        departamento_id=expensa.departamento_id,
        fecha=date.today(),
        tipo=TipoMovimiento.expensa_emitida,
        descripcion=f"Expensa {expensa.periodo}",
        monto=expensa.monto,
        expensa_id=expensa.id,
    ))
    db.commit()
    db.refresh(expensa)

    calc = calcular_estado_cuenta(db, expensa.departamento_id).por_expensa[expensa.id]
    return _expensa_to_out(expensa, calc)
```

- [ ] **Step 5: Refactor `obtener_expensa` para usar `estado_calculado`**

```python
def obtener_expensa(
    expensa_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ExpensaOut:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(status_code=404, detail="La expensa solicitada no existe.")
    if user.rol == Rol.departamento and expensa.departamento_id != user.departamento_id:
        raise HTTPException(status_code=403, detail="No autorizado.")

    calc = calcular_estado_cuenta(db, expensa.departamento_id).por_expensa.get(expensa.id)
    if calc is None:
        raise HTTPException(status_code=500, detail="Estado de la expensa no calculable.")
    return _expensa_to_out(expensa, calc)
```

- [ ] **Step 6: Eliminar el endpoint `POST /expensas/{id}/comprobantes` por completo**

Buscar y borrar la función `presentar_comprobante` entera y su decorator (líneas ~151-200 aprox).

- [ ] **Step 7: Sumar endpoint `DELETE /expensas/{expensa_id}` (admin)**

```python
@router.delete(
    "/{expensa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una expensa (solo admin, sin pagos aplicados)",
)
def eliminar_expensa(
    expensa_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(status_code=404, detail="La expensa solicitada no existe.")

    calc = calcular_estado_cuenta(db, expensa.departamento_id).por_expensa.get(expensa.id)
    if calc and calc.monto_pagado > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: la expensa tiene pago aplicado (FIFO).",
        )

    # Borrar el MovimientoCuenta(expensa_emitida) asociado y la expensa.
    db.execute(
        MovimientoCuenta.__table__.delete().where(
            MovimientoCuenta.expensa_id == expensa.id
        )
    )
    db.delete(expensa)
    db.commit()
```

- [ ] **Step 8: Correr tests de expensas**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_expensas.py -v --tb=short`
Expected: deberían pasar todos los del archivo. Si algunos requieren `/movimientos/mi-cuenta` (Task 9), pueden fallar — pero los de DELETE y los básicos pasan.

- [ ] **Step 9: Commit**

```bash
git add backend/routers/expensas.py
git commit -m "feat(expensas-router): estado_calculado FIFO, DELETE admin, movimiento auto en POST"
```

---

## Task 8: Modificar `backend/routers/comprobantes.py`

**Files:**
- Modify: `backend/routers/comprobantes.py`

- [ ] **Step 1: Revisar el router actual**

```bash
grep -n "def \|@router\|expensa_id" backend/routers/comprobantes.py
```

- [ ] **Step 2: Sumar imports**

```python
from ..models import MovimientoCuenta, TipoMovimiento
```

- [ ] **Step 3: Refactor `POST /comprobantes` (depto, multipart) — sin expensa_id**

```python
@router.post(
    "",
    response_model=ComprobanteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Presentar comprobante de pago",
)
def presentar_comprobante(
    fecha_pago: date = Form(...),
    monto: float = Form(...),
    archivo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> Comprobante:
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor que cero.")

    archivo_path = None
    if archivo is not None:
        archivo_path = guardar_archivo_comprobante(archivo)

    comprobante = Comprobante(
        departamento_id=user.departamento_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_path=archivo_path,
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db.add(comprobante)
    db.commit()
    db.refresh(comprobante)
    return comprobante
```

(Si `guardar_archivo_comprobante` no existe con ese nombre, usar la función real que se está usando en el código actual.)

- [ ] **Step 4: Refactor `GET /comprobantes` para filtrar por depto desde el token (no por expensa)**

Quitar cualquier filtro por `expensa_id`. El depto ve solo sus comprobantes (filtrar por `Comprobante.departamento_id == user.departamento_id`). El admin ve todos (con filtro opcional `?departamento_id=`).

- [ ] **Step 5: Refactor `PATCH /comprobantes/{id}` — al aprobar, generar MovimientoCuenta**

```python
@router.patch(
    "/{comprobante_id}",
    response_model=ComprobanteOut,
    summary="Verificar (aprobar/rechazar) un comprobante",
)
def verificar_comprobante(
    comprobante_id: int,
    payload: ComprobanteVerificar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Comprobante:
    comprobante = db.get(Comprobante, comprobante_id)
    if comprobante is None:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado.")
    if comprobante.estado != EstadoComprobante.pendiente_verificacion:
        raise HTTPException(
            status_code=409,
            detail="El comprobante ya fue verificado y no puede modificarse.",
        )

    comprobante.estado = payload.estado
    if payload.estado == EstadoComprobante.aprobado:
        db.add(MovimientoCuenta(
            departamento_id=comprobante.departamento_id,
            fecha=comprobante.fecha_pago,
            tipo=TipoMovimiento.pago_recibido,
            descripcion=f"Pago comprobante #{comprobante.id}",
            monto=comprobante.monto,
            comprobante_id=comprobante.id,
        ))

    db.commit()
    db.refresh(comprobante)
    return comprobante
```

- [ ] **Step 6: Correr tests de comprobantes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py -v --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/comprobantes.py
git commit -m "feat(comprobantes-router): POST sin expensa_id, aprobar genera movimiento pago_recibido"
```

---

## Task 9: Nuevo router `backend/routers/movimientos.py`

**Files:**
- Create: `backend/routers/movimientos.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear el router**

```python
"""Endpoints de cuenta corriente y notas (crédito/débito)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..cuenta_corriente import calcular_estado_cuenta
from ..database import get_db
from ..models import Departamento, MovimientoCuenta, Rol, TipoMovimiento
from ..schemas import EstadoCuentaOut, MovimientoCuentaOut, NotaCrear

router = APIRouter(tags=["Movimientos"])


def _cuenta(db: Session, departamento_id: int,
            desde: Optional[date], hasta: Optional[date]) -> EstadoCuentaOut:
    estado = calcular_estado_cuenta(db, departamento_id)

    stmt = (
        select(MovimientoCuenta)
        .where(MovimientoCuenta.departamento_id == departamento_id)
        .order_by(MovimientoCuenta.fecha.desc(), MovimientoCuenta.id.desc())
    )
    if desde is not None:
        stmt = stmt.where(MovimientoCuenta.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(MovimientoCuenta.fecha <= hasta)

    movs = list(db.scalars(stmt).all())
    return EstadoCuentaOut(
        departamento_id=departamento_id,
        saldo_total=estado.saldo_total,
        movimientos=[MovimientoCuentaOut.model_validate(m) for m in movs],
    )


@router.get(
    "/movimientos/mi-cuenta",
    response_model=EstadoCuentaOut,
    summary="Cuenta corriente del depto autenticado",
)
def mi_cuenta(
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
) -> EstadoCuentaOut:
    return _cuenta(db, user.departamento_id, desde, hasta)


@router.get(
    "/departamentos/{departamento_id}/cuenta",
    response_model=EstadoCuentaOut,
    summary="Cuenta corriente de un departamento (admin)",
)
def cuenta_departamento(
    departamento_id: int,
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EstadoCuentaOut:
    if db.get(Departamento, departamento_id) is None:
        raise HTTPException(status_code=404, detail="Departamento no existe.")
    return _cuenta(db, departamento_id, desde, hasta)


@router.post(
    "/movimientos/nota",
    response_model=MovimientoCuentaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nota de crédito o débito (admin)",
)
def crear_nota(
    payload: NotaCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> MovimientoCuenta:
    if db.get(Departamento, payload.departamento_id) is None:
        raise HTTPException(status_code=404, detail="Departamento no existe.")

    mov = MovimientoCuenta(
        departamento_id=payload.departamento_id,
        fecha=payload.fecha or date.today(),
        tipo=payload.tipo,
        descripcion=payload.descripcion,
        monto=payload.monto,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov
```

- [ ] **Step 2: Registrar el router en `backend/main.py`**

```bash
grep -n "include_router" backend/main.py
```

Sumar:

```python
from .routers import movimientos as movimientos_router
# ... más abajo, junto al resto de include_router:
app.include_router(movimientos_router.router)
```

- [ ] **Step 3: Smoke check de import**

Run: `./.venv/Scripts/python.exe -c "from backend.main import app; print([r.path for r in app.routes if hasattr(r, 'path') and 'cuenta' in r.path or 'movimientos' in r.path])"`
Expected: imprime los 3 paths.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/movimientos.py backend/main.py
git commit -m "feat(movimientos-router): GET mi-cuenta, GET cuenta admin, POST nota"
```

---

## Task 10: `tests/test_movimientos.py`

**Files:**
- Create: `tests/test_movimientos.py`

- [ ] **Step 1: Sumar tests HTTP**

```python
"""Tests del router de movimientos (cuenta corriente y notas)."""
import pytest


def test_get_mi_cuenta_sin_token_401(client):
    r = client.get("/movimientos/mi-cuenta")
    assert r.status_code == 401


def test_get_mi_cuenta_admin_403(client, admin_headers):
    # admin no es depto, no puede usar mi-cuenta
    r = client.get("/movimientos/mi-cuenta", headers=admin_headers)
    assert r.status_code == 403


def test_get_mi_cuenta_depto_200(client, depto_a_headers):
    r = client.get("/movimientos/mi-cuenta", headers=depto_a_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["departamento_id"] == 1  # ajustar al ID real del depto_a
    assert "saldo_total" in body
    assert isinstance(body["movimientos"], list)


def test_get_cuenta_departamento_admin_200(client, admin_headers):
    r = client.get("/departamentos/1/cuenta", headers=admin_headers)
    assert r.status_code == 200


def test_get_cuenta_departamento_depto_403(client, depto_a_headers):
    r = client.get("/departamentos/2/cuenta", headers=depto_a_headers)
    assert r.status_code == 403


def test_get_cuenta_departamento_inexistente_404(client, admin_headers):
    r = client.get("/departamentos/9999/cuenta", headers=admin_headers)
    assert r.status_code == 404


def test_post_nota_credito_admin_201(client, admin_headers, depto_a_headers):
    r = client.post("/movimientos/nota", json={
        "departamento_id": 1,
        "tipo": "nota_credito",
        "monto": 500,
        "descripcion": "Bonificación verano",
    }, headers=admin_headers)
    assert r.status_code == 201

    # Verificar que aparece en la cuenta del depto
    r = client.get("/movimientos/mi-cuenta", headers=depto_a_headers)
    movs = r.json()["movimientos"]
    assert any(m["tipo"] == "nota_credito" and m["monto"] == 500 for m in movs)


def test_post_nota_debito_admin_201(client, admin_headers):
    r = client.post("/movimientos/nota", json={
        "departamento_id": 1,
        "tipo": "nota_debito",
        "monto": 100,
        "descripcion": "Recargo administrativo",
    }, headers=admin_headers)
    assert r.status_code == 201


def test_post_nota_monto_invalido_400(client, admin_headers):
    r = client.post("/movimientos/nota", json={
        "departamento_id": 1,
        "tipo": "nota_credito",
        "monto": 0,
        "descripcion": "x",
    }, headers=admin_headers)
    assert r.status_code == 400


def test_post_nota_tipo_invalido_400(client, admin_headers):
    r = client.post("/movimientos/nota", json={
        "departamento_id": 1,
        "tipo": "pago_recibido",  # no permitido vía nota
        "monto": 100,
        "descripcion": "x",
    }, headers=admin_headers)
    assert r.status_code == 400


def test_post_nota_depto_403(client, depto_a_headers):
    r = client.post("/movimientos/nota", json={
        "departamento_id": 1,
        "tipo": "nota_credito",
        "monto": 100,
        "descripcion": "x",
    }, headers=depto_a_headers)
    assert r.status_code == 403


def test_post_nota_depto_inexistente_404(client, admin_headers):
    r = client.post("/movimientos/nota", json={
        "departamento_id": 9999,
        "tipo": "nota_credito",
        "monto": 100,
        "descripcion": "x",
    }, headers=admin_headers)
    assert r.status_code == 404


def test_mi_cuenta_filtra_por_fecha(client, admin_headers, depto_a_headers):
    # Crear nota con fecha vieja
    r = client.post("/movimientos/nota", json={
        "departamento_id": 1,
        "tipo": "nota_credito",
        "monto": 1,
        "descripcion": "vieja",
        "fecha": "2020-01-01",
    }, headers=admin_headers)
    assert r.status_code == 201

    r = client.get("/movimientos/mi-cuenta?desde=2026-01-01", headers=depto_a_headers)
    movs = r.json()["movimientos"]
    assert all(m["fecha"] >= "2026-01-01" for m in movs)
```

- [ ] **Step 2: Correr el archivo**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_movimientos.py -v --tb=short`
Expected: PASS los 13 tests.

- [ ] **Step 3: Commit**

```bash
git add tests/test_movimientos.py
git commit -m "test(movimientos): cobertura completa GET mi-cuenta, GET cuenta admin, POST nota"
```

---

## Task 11: OpenAPI

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Declarar tag `Movimientos`**

Buscar el bloque `tags:` al top. Sumar:

```yaml
  - name: Movimientos
    description: Cuenta corriente por departamento. Movimientos (débitos/créditos), notas y saldo.
```

- [ ] **Step 2: Modificar `ExpensaOut` — quitar `estado`, sumar `estado_calculado` y `monto_pendiente`**

En `components.schemas.ExpensaOut`, quitar la prop `estado`, sumar:

```yaml
        estado_calculado:
          type: string
          enum: [pendiente, parcial, pagada, vencida]
          description: Estado calculado a partir de los movimientos (no se persiste).
        monto_pendiente:
          type: number
          format: float
          description: Saldo pendiente FIFO de esta expensa.
```

Quitar `estado` del `required`. Sumar `estado_calculado` y `monto_pendiente` al `required`.

- [ ] **Step 3: Modificar `ComprobanteOut` — `expensa_id` → `departamento_id`**

En `components.schemas.ComprobanteOut`, reemplazar la prop y actualizar `required`.

- [ ] **Step 4: Sumar schemas nuevos**

```yaml
    TipoMovimiento:
      type: string
      enum: [expensa_emitida, pago_recibido, interes_punitorio, nota_debito, nota_credito]

    MovimientoCuentaOut:
      type: object
      required: [id, departamento_id, fecha, tipo, descripcion, monto, fecha_creacion]
      properties:
        id: { type: integer }
        departamento_id: { type: integer }
        fecha: { type: string, format: date }
        tipo: { $ref: '#/components/schemas/TipoMovimiento' }
        descripcion: { type: string }
        monto: { type: number, format: float, description: "Siempre positivo. El tipo indica signo." }
        expensa_id: { type: integer, nullable: true }
        comprobante_id: { type: integer, nullable: true }
        fecha_creacion: { type: string, format: date-time }

    EstadoCuentaOut:
      type: object
      required: [departamento_id, saldo_total, movimientos]
      properties:
        departamento_id: { type: integer }
        saldo_total:
          type: number
          format: float
          description: "Positivo = debe; negativo = a favor; cero = al día."
        movimientos:
          type: array
          items: { $ref: '#/components/schemas/MovimientoCuentaOut' }

    NotaCrear:
      type: object
      required: [departamento_id, tipo, monto, descripcion]
      properties:
        departamento_id: { type: integer }
        tipo:
          type: string
          enum: [nota_credito, nota_debito]
        monto: { type: number, format: float, exclusiveMinimum: 0 }
        descripcion: { type: string, minLength: 1, maxLength: 500 }
        fecha: { type: string, format: date, nullable: true }
```

- [ ] **Step 5: Sumar los 3 paths**

```yaml
  /movimientos/mi-cuenta:
    get:
      tags: [Movimientos]
      summary: Cuenta corriente del depto autenticado
      parameters:
        - in: query
          name: desde
          schema: { type: string, format: date }
        - in: query
          name: hasta
          schema: { type: string, format: date }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/EstadoCuentaOut' } } } }
        '401': { description: Sin token }
        '403': { description: Rol no permitido }

  /departamentos/{departamento_id}/cuenta:
    get:
      tags: [Movimientos]
      summary: Cuenta corriente de un departamento (admin)
      parameters:
        - in: path
          name: departamento_id
          required: true
          schema: { type: integer }
        - in: query
          name: desde
          schema: { type: string, format: date }
        - in: query
          name: hasta
          schema: { type: string, format: date }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/EstadoCuentaOut' } } } }
        '401': { description: Sin token }
        '403': { description: Rol no admin }
        '404': { description: Departamento inexistente }

  /movimientos/nota:
    post:
      tags: [Movimientos]
      summary: Crear nota de crédito o débito (admin)
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/NotaCrear' }
      responses:
        '201': { description: Creado, content: { application/json: { schema: { $ref: '#/components/schemas/MovimientoCuentaOut' } } } }
        '400': { description: Validación falló }
        '401': { description: Sin token }
        '403': { description: Rol no admin }
        '404': { description: Departamento inexistente }
```

- [ ] **Step 6: Modificar paths existentes — quitar `POST /expensas/{id}/comprobantes`, agregar `DELETE /expensas/{id}`, agregar `POST /comprobantes` (multipart)**

Eliminar la entrada de path `/expensas/{expensa_id}/comprobantes` entera.

En `/expensas/{expensa_id}`, sumar `delete:` con tag Expensas, security admin, 204/404/409.

En `/comprobantes`, sumar `post:` con `multipart/form-data` y campos `fecha_pago`, `monto`, `archivo`.

- [ ] **Step 7: Bumpear `info.description` con mención de cuenta corriente**

Editar `info.description` para sumar una línea: "Fase 3.5 (jun-2026): cuenta corriente por departamento — pagos se asignan FIFO desde movimientos."

- [ ] **Step 8: Validar YAML**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml', encoding='utf-8'))"`
Expected: no error.

- [ ] **Step 9: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): Fase 3.5 — Movimientos tag, EstadoCuenta, NotaCrear, ExpensaOut con estado_calculado"
```

---

## Task 12: Actualizar `backend/seed.py`

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Inspeccionar el seed actual de expensas y comprobantes**

```bash
grep -n "Expensa\|Comprobante" backend/seed.py
```

- [ ] **Step 2: Quitar `estado=EstadoExpensa.pendiente` de cada Expensa**

Edit cada ocurrencia.

- [ ] **Step 3: Para cada `Expensa(...)` seedeada, sumar su `MovimientoCuenta(expensa_emitida)`**

```python
from .models import MovimientoCuenta, TipoMovimiento
from datetime import timedelta

# ... después de db.add_all(expensas):
for e in expensas:
    db.add(MovimientoCuenta(
        departamento_id=e.departamento_id,
        fecha=e.fecha_vencimiento - timedelta(days=30),
        tipo=TipoMovimiento.expensa_emitida,
        descripcion=f"Expensa {e.periodo}",
        monto=e.monto,
        expensa_id=e.id,
    ))
```

- [ ] **Step 4: Si el seed crea `Comprobante` con `expensa_id`, cambiar a `departamento_id` y sumar movimiento si está aprobado**

Buscar `Comprobante(` en seed. Cambiar el FK. Para cada comprobante con `estado=EstadoComprobante.aprobado`, sumar:

```python
db.add(MovimientoCuenta(
    departamento_id=c.departamento_id,
    fecha=c.fecha_pago,
    tipo=TipoMovimiento.pago_recibido,
    descripcion=f"Pago comprobante #{c.id}",
    monto=c.monto,
    comprobante_id=c.id,
))
```

- [ ] **Step 5: Sumar variedad — 1 nota crédito + 1 nota débito**

Antes del `db.commit()` final:

```python
db.add(MovimientoCuenta(
    departamento_id=depto_a.id,
    fecha=date(2026, 6, 1),
    tipo=TipoMovimiento.nota_credito,
    descripcion="Bonificación pago anticipado",
    monto=2000.0,
))
db.add(MovimientoCuenta(
    departamento_id=depto_b.id,
    fecha=date(2026, 6, 1),
    tipo=TipoMovimiento.nota_debito,
    descripcion="Ajuste mantenimiento extraordinario",
    monto=1500.0,
))
```

- [ ] **Step 6: Borrar DB + correr backend para confirmar que seed funciona**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
./.venv/Scripts/python.exe -c "from backend.seed import seed_if_empty; from backend.database import SessionLocal, Base, engine; Base.metadata.create_all(bind=engine); s = SessionLocal(); seed_if_empty(s); s.close(); print('OK')"
```

Expected: imprime `OK` sin error.

- [ ] **Step 7: Smoke con uvicorn + curl manual**

(Opcional pero recomendado)
```powershell
# Terminal 1: ./.venv/Scripts/python.exe -m uvicorn backend.main:app --reload
# Terminal 2 (después de auth):
curl -H "Authorization: Bearer <TOKEN_DEPTO>" http://localhost:8000/movimientos/mi-cuenta
```

Expected: JSON con saldo y movimientos.

- [ ] **Step 8: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): movimientos por expensa/comprobante + notas de ejemplo"
```

---

## Task 13: Frontend — API clients

**Files:**
- Create: `frontend/src/api/movimientos.js`
- Modify: `frontend/src/api/comprobantes.js`
- Modify: `frontend/src/api/expensas.js`

- [ ] **Step 1: Crear `frontend/src/api/movimientos.js`**

```javascript
import { request } from "./client";

export function listarMisMovimientos({ desde, hasta } = {}) {
  const params = new URLSearchParams();
  if (desde) params.set("desde", desde);
  if (hasta) params.set("hasta", hasta);
  const qs = params.toString();
  return request(`/movimientos/mi-cuenta${qs ? `?${qs}` : ""}`);
}

export function listarMovimientosDepto(departamentoId, { desde, hasta } = {}) {
  const params = new URLSearchParams();
  if (desde) params.set("desde", desde);
  if (hasta) params.set("hasta", hasta);
  const qs = params.toString();
  return request(`/departamentos/${departamentoId}/cuenta${qs ? `?${qs}` : ""}`);
}

export function crearNota({ departamentoId, tipo, monto, descripcion, fecha }) {
  return request("/movimientos/nota", {
    method: "POST",
    body: JSON.stringify({
      departamento_id: departamentoId,
      tipo,
      monto,
      descripcion,
      fecha,
    }),
  });
}
```

- [ ] **Step 2: Modificar `frontend/src/api/comprobantes.js` — `presentarComprobante` sin expensaId**

Abrir el archivo. Encontrar `presentarComprobante`. Reemplazar firma por:

```javascript
export function presentarComprobante({ fechaPago, monto, archivo }) {
  const fd = new FormData();
  fd.append("fecha_pago", fechaPago);
  fd.append("monto", String(monto));
  if (archivo) fd.append("archivo", archivo);
  return request("/comprobantes", { method: "POST", body: fd });
}
```

(Confirmar que `request` permite body `FormData` sin setear `Content-Type` — si no, ajustar la implementación.)

- [ ] **Step 3: Modificar `frontend/src/api/expensas.js` — sumar `eliminarExpensa`**

```javascript
export function eliminarExpensa(id) {
  return request(`/expensas/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/movimientos.js frontend/src/api/comprobantes.js frontend/src/api/expensas.js
git commit -m "feat(frontend/api): movimientos.js + presentarComprobante sin expensaId"
```

---

## Task 14: Frontend — pantalla `/mi-cuenta` (depto)

**Files:**
- Create: `frontend/src/screens/MiCuenta.jsx`

- [ ] **Step 1: Crear el componente**

```jsx
import { useEffect, useState } from "react";
import { listarMisMovimientos } from "../api/movimientos";
import { presentarComprobante } from "../api/comprobantes";
import Modal from "../components/Modal";
import Tarjeta from "../components/Tarjeta";

const TIPO_LABEL = {
  expensa_emitida: "Expensa emitida",
  pago_recibido: "Pago",
  interes_punitorio: "Interés",
  nota_debito: "Nota de débito",
  nota_credito: "Nota de crédito",
};

const TIPO_SIGNO = {
  expensa_emitida: "+",
  pago_recibido: "-",
  interes_punitorio: "+",
  nota_debito: "+",
  nota_credito: "-",
};

function formatMoney(n) {
  return n.toLocaleString("es-AR", { style: "currency", currency: "ARS" });
}

export default function MiCuenta() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const cargar = () =>
    listarMisMovimientos()
      .then(setData)
      .catch((e) => setError(e.message));

  useEffect(() => {
    cargar();
  }, []);

  if (error) return <p role="alert">Error: {error}</p>;
  if (!data) return <p>Cargando...</p>;

  const saldo = data.saldo_total;
  const colorSaldo = saldo > 0 ? "var(--c-error)" : saldo < 0 ? "var(--c-success)" : "var(--c-text-muted)";

  return (
    <section>
      <header className="page-header">
        <h1>Mi cuenta</h1>
        <button onClick={() => setShowModal(true)}>+ Presentar pago</button>
      </header>

      <Tarjeta>
        <p style={{ fontSize: "1.5rem", color: colorSaldo }}>
          <strong>Saldo: {formatMoney(saldo)}</strong>
        </p>
        <p className="texto-muted">
          {saldo > 0 ? "Tenés saldo pendiente." : saldo < 0 ? "Tenés crédito a favor." : "Estás al día."}
        </p>
      </Tarjeta>

      <h2>Movimientos</h2>
      {data.movimientos.length === 0 ? (
        <p>No hay movimientos.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Tipo</th>
              <th>Descripción</th>
              <th>Monto</th>
            </tr>
          </thead>
          <tbody>
            {data.movimientos.map((m) => (
              <tr key={m.id}>
                <td>{m.fecha}</td>
                <td>{TIPO_LABEL[m.tipo]}</td>
                <td>{m.descripcion}</td>
                <td>{TIPO_SIGNO[m.tipo]}{formatMoney(m.monto)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showModal && (
        <ModalPresentarPago
          onClose={() => setShowModal(false)}
          onDone={() => {
            setShowModal(false);
            cargar();
          }}
        />
      )}
    </section>
  );
}

function ModalPresentarPago({ onClose, onDone }) {
  const [fechaPago, setFechaPago] = useState(new Date().toISOString().slice(0, 10));
  const [monto, setMonto] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await presentarComprobante({
        fechaPago,
        monto: parseFloat(monto),
        archivo,
      });
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal onClose={onClose} title="Presentar pago">
      <form onSubmit={submit}>
        <label>
          Fecha del pago
          <input type="date" value={fechaPago} onChange={(e) => setFechaPago(e.target.value)} required />
        </label>
        <label>
          Monto
          <input type="number" min="0.01" step="0.01" value={monto}
                 onChange={(e) => setMonto(e.target.value)} required />
        </label>
        <label>
          Comprobante (opcional)
          <input type="file" accept="image/*,application/pdf"
                 onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <p className="texto-muted">Tu pago será visible cuando administración lo apruebe.</p>
        <div className="modal-actions">
          <button type="button" onClick={onClose}>Cancelar</button>
          <button type="submit" disabled={submitting}>
            {submitting ? "Enviando..." : "Presentar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/screens/MiCuenta.jsx
git commit -m "feat(frontend/mi-cuenta): pantalla depto con saldo, extracto y modal presentar pago"
```

---

## Task 15: Frontend — pantalla `/departamentos/:id/cuenta` (admin)

**Files:**
- Create: `frontend/src/screens/DepartamentoCuenta.jsx`

- [ ] **Step 1: Crear el componente**

```jsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { listarMovimientosDepto, crearNota } from "../api/movimientos";
import Modal from "../components/Modal";
import Tarjeta from "../components/Tarjeta";

const TIPO_LABEL = {
  expensa_emitida: "Expensa emitida",
  pago_recibido: "Pago",
  interes_punitorio: "Interés",
  nota_debito: "Nota de débito",
  nota_credito: "Nota de crédito",
};

const TIPO_SIGNO = {
  expensa_emitida: "+",
  pago_recibido: "-",
  interes_punitorio: "+",
  nota_debito: "+",
  nota_credito: "-",
};

function formatMoney(n) {
  return n.toLocaleString("es-AR", { style: "currency", currency: "ARS" });
}

export default function DepartamentoCuenta() {
  const { id } = useParams();
  const departamentoId = parseInt(id, 10);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [showNotaCredito, setShowNotaCredito] = useState(false);
  const [showNotaDebito, setShowNotaDebito] = useState(false);

  const cargar = () =>
    listarMovimientosDepto(departamentoId)
      .then(setData)
      .catch((e) => setError(e.message));

  useEffect(() => {
    cargar();
  }, [departamentoId]);

  if (error) return <p role="alert">Error: {error}</p>;
  if (!data) return <p>Cargando...</p>;

  const saldo = data.saldo_total;
  const colorSaldo = saldo > 0 ? "var(--c-error)" : saldo < 0 ? "var(--c-success)" : "var(--c-text-muted)";

  return (
    <section>
      <header className="page-header">
        <h1>Cuenta corriente — Depto {departamentoId}</h1>
        <div>
          <button onClick={() => setShowNotaCredito(true)}>+ Nota de crédito</button>
          <button onClick={() => setShowNotaDebito(true)}>+ Nota de débito</button>
        </div>
      </header>

      <Tarjeta>
        <p style={{ fontSize: "1.5rem", color: colorSaldo }}>
          <strong>Saldo: {formatMoney(saldo)}</strong>
        </p>
      </Tarjeta>

      <h2>Movimientos</h2>
      {data.movimientos.length === 0 ? (
        <p>No hay movimientos.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Tipo</th>
              <th>Descripción</th>
              <th>Monto</th>
            </tr>
          </thead>
          <tbody>
            {data.movimientos.map((m) => (
              <tr key={m.id}>
                <td>{m.fecha}</td>
                <td>{TIPO_LABEL[m.tipo]}</td>
                <td>{m.descripcion}</td>
                <td>{TIPO_SIGNO[m.tipo]}{formatMoney(m.monto)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showNotaCredito && (
        <ModalNota
          tipo="nota_credito"
          titulo="Nueva nota de crédito"
          departamentoId={departamentoId}
          onClose={() => setShowNotaCredito(false)}
          onDone={() => {
            setShowNotaCredito(false);
            cargar();
          }}
        />
      )}
      {showNotaDebito && (
        <ModalNota
          tipo="nota_debito"
          titulo="Nueva nota de débito"
          departamentoId={departamentoId}
          onClose={() => setShowNotaDebito(false)}
          onDone={() => {
            setShowNotaDebito(false);
            cargar();
          }}
        />
      )}
    </section>
  );
}

function ModalNota({ tipo, titulo, departamentoId, onClose, onDone }) {
  const [monto, setMonto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await crearNota({
        departamentoId,
        tipo,
        monto: parseFloat(monto),
        descripcion,
        fecha,
      });
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal onClose={onClose} title={titulo}>
      <form onSubmit={submit}>
        <label>
          Monto
          <input type="number" min="0.01" step="0.01" value={monto}
                 onChange={(e) => setMonto(e.target.value)} required />
        </label>
        <label>
          Descripción
          <input type="text" value={descripcion}
                 onChange={(e) => setDescripcion(e.target.value)} required maxLength={500} />
        </label>
        <label>
          Fecha
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>Cancelar</button>
          <button type="submit" disabled={submitting}>
            {submitting ? "Guardando..." : "Crear"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/screens/DepartamentoCuenta.jsx
git commit -m "feat(frontend/admin-cuenta): pantalla admin con saldo, extracto y modales notas"
```

---

## Task 16: Frontend — modificar Expensas, Comprobantes, Sidebar, App routes

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx`
- Modify: `frontend/src/screens/Comprobantes.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Inspeccionar `Expensas.jsx` actual**

```bash
grep -n "estado\|comprobante\|Presentar" frontend/src/screens/Expensas.jsx
```

- [ ] **Step 2: En `Expensas.jsx` — usar `estado_calculado` en lugar de `estado`, sacar botón "Presentar comprobante"**

- Buscar todas las referencias a `expensa.estado` y reemplazar por `expensa.estado_calculado`.
- Si hay un `<button>` por tarjeta tipo "Presentar comprobante", eliminarlo (incluyendo el modal asociado si está en este archivo). Reemplazar con un link/botón que vaya a `/mi-cuenta` cuando el rol es depto:

```jsx
{rol === "departamento" && (
  <Link to="/mi-cuenta">Pagar desde Mi cuenta →</Link>
)}
```

- Si el filtro por estado en UI usa el query `?estado=`, sacar ese filtro o adaptarlo a filtrar client-side por `estado_calculado`.
- Para cada tarjeta, sumar pill de vencimiento:

```jsx
<span className="pill">Vence {expensa.fecha_vencimiento}</span>
{expensa.monto_pendiente > 0 && (
  <span className="pill">Pendiente {formatMoney(expensa.monto_pendiente)}</span>
)}
```

- Si admin, sumar botón "Eliminar" que llame a `eliminarExpensa(id)` con `confirm()`.

- [ ] **Step 3: En `Comprobantes.jsx` — actualizar el form (si el rol es depto y existe un form) para no pedir `expensa_id`**

```bash
grep -n "expensa\|expensaId\|presentar" frontend/src/screens/Comprobantes.jsx
```

Si hay un form de presentar dentro de esta pantalla, ya no usa `expensaId`. (Si la pantalla solo lista y el form vive en MiCuenta.jsx, podés quitar el form de acá.)

Sumar mensaje cuando depto no tiene comprobantes:

```jsx
{comprobantes.length === 0 && (
  <p>Aún no presentaste pagos. <Link to="/mi-cuenta">Andá a Mi cuenta</Link> para hacerlo.</p>
)}
```

- [ ] **Step 4: En `Sidebar.jsx` — reorganizar la sección "Expensas y pagos" para depto, con "Mi cuenta" primero**

```bash
grep -n "Expensas\|Comprobantes\|sección\|Expensas y pagos" frontend/src/components/Sidebar.jsx
```

Para el bloque del depto, modificar la sección "Expensas y pagos" para que contenga, en orden:
1. Mi cuenta → `/mi-cuenta`
2. Expensas → `/expensas`
3. Comprobantes → `/comprobantes`

Para el bloque del admin, no agregar nada al sidebar (el acceso a `/departamentos/:id/cuenta` se hace navegando desde la pantalla de departamentos — sumar ese link en la lista de departamentos en una iteración futura; por ahora la URL directa es suficiente para admin).

- [ ] **Step 5: En `App.jsx` — sumar las rutas nuevas**

Buscar el bloque de Routes. Sumar imports al top:

```jsx
import MiCuenta from "./screens/MiCuenta";
import DepartamentoCuenta from "./screens/DepartamentoCuenta";
```

Sumar las rutas dentro del `<Route path="/">`:

```jsx
<Route path="mi-cuenta" element={<MiCuenta />} />
<Route path="departamentos/:id/cuenta" element={<DepartamentoCuenta />} />
```

- [ ] **Step 6: Lanzar dev server y verificar manualmente**

```powershell
cd frontend
npm run dev
```

Loguearte como admin y como depto y verificar:
- Depto: sidebar muestra Mi cuenta primero. Click → carga saldo y extracto. Botón "Presentar pago" abre modal, submit OK.
- Depto: en /expensas las tarjetas muestran "Pagada / Parcial / Pendiente / Vencida" y pill de vencimiento. No hay botón "Presentar comprobante".
- Admin: navegar manualmente a `/departamentos/1/cuenta`. Ver saldo + extracto. Crear nota crédito y nota débito.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/screens/Expensas.jsx frontend/src/screens/Comprobantes.jsx frontend/src/components/Sidebar.jsx frontend/src/App.jsx
git commit -m "feat(frontend): Expensas con estado_calculado, Sidebar con Mi cuenta, rutas nuevas"
```

---

## Task 17: Smoke completo + merge

**Files:** ninguno modificado.

- [ ] **Step 1: Correr suite completa**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: PASS todos.

- [ ] **Step 2: Borrar DB, correr backend, login y smoke manual**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
./.venv/Scripts/python.exe -m uvicorn backend.main:app --reload
```

En otra terminal, hacer requests representativos vía curl o frontend:

```bash
# Login admin
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@consorcio.test","password":"admin123"}'

# Login depto A (con el TOKEN_DEPTO obtenido)
curl -H "Authorization: Bearer $TOKEN_DEPTO" http://localhost:8000/movimientos/mi-cuenta

# Crear nota crédito (TOKEN_ADMIN)
curl -X POST http://localhost:8000/movimientos/nota \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"departamento_id":1,"tipo":"nota_credito","monto":100,"descripcion":"prueba"}'
```

Verificar: saldo cambia tras nota crédito. Aprobar un comprobante → saldo cambia.

- [ ] **Step 3: Verificar UI completa en navegador**

Loguear depto + admin, ejecutar el flujo "feliz":
1. Depto presenta pago.
2. Admin aprueba comprobante.
3. Depto ve saldo actualizado en Mi cuenta y estado_calculado en Expensas.
4. Admin crea nota crédito sobre el depto.
5. Depto ve la nota en su extracto.

- [ ] **Step 4: Bumpear `MEMORY.md` solo si hay algo no obvio que valga la pena recordar**

(No es obligatorio — solo si descubriste un patrón nuevo. Si todo fluyó según el plan, saltear este paso.)

- [ ] **Step 5: Mergear a `master`**

```bash
git checkout master
git merge --no-ff feature/expensas-fase35-cuenta-corriente -m "Merge feature/expensas-fase35-cuenta-corriente: cuenta corriente por depto"
```

- [ ] **Step 6: Actualizar el roadmap — marcar Fase 3.5 como completada**

Edit `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`. Cambiar el estado de la fase 3.5 a "Completada (2026-MM-DD)". Commitear:

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 3.5 completada"
```

---

## Notas finales del plan

- **Sin reversión de comprobantes aprobados** (decisión del spec). Si se aprobó por error, admin compensa con nota crédito.
- **Sin filtro `?estado=` en `/expensas`** — el estado ahora es calculado, no indexable. Si se necesita en el futuro, se filtra client-side o se denormaliza.
- **Sin tabla `AsignacionPago`** — FIFO se recalcula. Si el volumen crece (>1000 movimientos/depto), considerar cache.
- **`monto_pendiente` puede ser float con decimales chicos** por aritmética. El umbral `<= 0.001` en `cuenta_corriente.py` cubre esos casos.
- **Eliminar expensa con pagos FIFO aplicados** devuelve 409 — la decisión fue conservadora. Si admin quiere "borrar de verdad", primero compensa con nota débito o le pide a desarrollo (raro).
