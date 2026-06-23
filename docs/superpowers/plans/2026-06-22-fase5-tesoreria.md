# Fase 5 Tesorería — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modelar las cajas (cuentas financieras) del consorcio. Cada gasto sale de una caja, cada pago aprobado entra a una caja. Sumar transferencias entre cajas + ajustes manuales + dashboard "estado financiero".

**Architecture:**
- 3 modelos nuevos (`Caja`, `MovimientoCaja`, `TransferenciaCaja`) y 4 campos sumados a modelos existentes (`Gasto.caja_id`, `GastoHabitual.caja_id`, `Comprobante.caja_destino_id`, `ConfiguracionConsorcio.caja_default_pagos_id`).
- Saldo de caja calculado on-demand (módulo puro `backend/caja_saldo.py`) — no se persiste.
- Movimientos de `ingreso`/`egreso` se generan automáticamente cuando se crea un gasto o se aprueba un comprobante. Movimientos de `ajuste` se cargan manualmente.
- Frontend: nueva sección "Tesorería" en sidebar con 3 pantallas (estado-financiero, cajas, transferencias) y modificaciones a 5 pantallas existentes (gastos, gastos-habituales, comprobantes, liquidaciones, configuracion).

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2 + pytest (backend). React 18 + Vite + react-router-dom (frontend).

**Reference:** El diseño detallado vive en `docs/superpowers/specs/2026-06-22-fase5-tesoreria-design.md`.

---

## Task 0: Setup branch + clean DB

**Files:** ninguno (operaciones de git/fs).

- [ ] **Step 1: Crear branch desde master**

```bash
git checkout master
git pull # opcional, si master está sincronizado
git checkout -b feature/expensas-fase5-tesoreria
```

- [ ] **Step 2: Limpiar DB de desarrollo**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
```

(Si la DB está bloqueada, cerrá uvicorn primero.)

- [ ] **Step 3: Verificar que la suite arranca verde**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: `481 passed` (baseline post-Fase 4.5).

---

## Task 1: Modelos Fase 5

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Agregar enums nuevos (después de `class Rubro`, antes de `class FormaPago`)**

```python
class TipoCaja(str, enum.Enum):
    efectivo = "efectivo"
    banco = "banco"
    fondo_reparacion = "fondo_reparacion"
    otro = "otro"


class TipoMovimientoCaja(str, enum.Enum):
    ingreso = "ingreso"
    egreso = "egreso"
    ajuste = "ajuste"
```

- [ ] **Step 2: Sumar clase `Caja` al final de los modelos (antes de cualquier `# === Configuración ===`)**

```python
class Caja(Base):
    __tablename__ = "cajas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    tipo: Mapped[TipoCaja] = mapped_column(
        SqlEnum(TipoCaja, name="tipo_caja"), nullable=False
    )
    descripcion: Mapped[str | None] = mapped_column(String(500))
    saldo_inicial: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    movimientos: Mapped[list["MovimientoCaja"]] = relationship(back_populates="caja")
```

- [ ] **Step 3: Sumar clase `MovimientoCaja`**

```python
class MovimientoCaja(Base):
    __tablename__ = "movimientos_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[TipoMovimientoCaja] = mapped_column(
        SqlEnum(TipoMovimientoCaja, name="tipo_movimiento_caja"), nullable=False
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)

    gasto_id: Mapped[int | None] = mapped_column(ForeignKey("gastos.id"))
    comprobante_id: Mapped[int | None] = mapped_column(ForeignKey("comprobantes.id"))
    transferencia_id: Mapped[int | None] = mapped_column(
        ForeignKey("transferencias_caja.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    caja: Mapped["Caja"] = relationship(back_populates="movimientos")
```

- [ ] **Step 4: Sumar clase `TransferenciaCaja`**

```python
class TransferenciaCaja(Base):
    __tablename__ = "transferencias_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    caja_origen_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
    caja_destino_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
```

- [ ] **Step 5: Sumar `caja_id` a `Gasto` (clase existente, después de `forma_pago`)**

```python
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
```

- [ ] **Step 6: Sumar `caja_id` a `GastoHabitual` (clase existente, después de `forma_pago`)**

```python
    caja_id: Mapped[int] = mapped_column(
        ForeignKey("cajas.id"), nullable=False
    )
```

- [ ] **Step 7: Sumar `caja_destino_id` a `Comprobante` (clase existente, nullable)**

```python
    caja_destino_id: Mapped[int | None] = mapped_column(ForeignKey("cajas.id"))
```

- [ ] **Step 8: Sumar `caja_default_pagos_id` a `ConfiguracionConsorcio` (clase existente, después de `tasa_interes_mensual_pct`)**

```python
    caja_default_pagos_id: Mapped[int | None] = mapped_column(ForeignKey("cajas.id"))
```

- [ ] **Step 9: Smoke import (sin DB)**

```bash
.venv/Scripts/python.exe -c "from backend.models import Caja, MovimientoCaja, TransferenciaCaja, TipoCaja, TipoMovimientoCaja; print('OK')"
```

Expected: `OK`.

- [ ] **Step 10: Commit**

```bash
git add backend/models.py
git commit -m "feat(models): Caja, MovimientoCaja, TransferenciaCaja + caja_id/destino en Gasto/Comprobante/Config"
```

---

## Task 2: Schemas Pydantic + módulo puro `caja_saldo.py`

**Files:**
- Modify: `backend/schemas.py`
- Create: `backend/caja_saldo.py`
- Create: `tests/test_caja_saldo.py`

- [ ] **Step 1: Sumar schemas de Caja en `backend/schemas.py` (después de los schemas de Liquidación)**

```python
# === Cajas (Fase 5) ===

class CajaCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    tipo: TipoCaja
    descripcion: str | None = Field(None, max_length=500)
    saldo_inicial: float = Field(default=0.0)
    activa: bool = Field(default=True)


class CajaActualizar(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=100)
    descripcion: str | None = Field(None, max_length=500)
    activa: bool | None = None


class CajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoCaja
    descripcion: str | None
    saldo_inicial: float
    saldo_actual: float  # calculado en el router con caja_saldo.calcular_saldo
    activa: bool
```

- [ ] **Step 2: Sumar `from .models import TipoCaja, TipoMovimientoCaja` al import del top**

(Si los imports están agrupados, agregalos a la línea existente que importa enums.)

- [ ] **Step 3: Sumar schemas de MovimientoCaja**

```python
class AjusteCrear(BaseModel):
    fecha: date
    monto: float = Field(..., description="Positivo o negativo. Suma/resta al saldo.")
    descripcion: str = Field(..., min_length=5, max_length=500)


class MovimientoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caja_id: int
    fecha: date
    tipo: TipoMovimientoCaja
    monto: float
    descripcion: str
    gasto_id: int | None
    comprobante_id: int | None
    transferencia_id: int | None
```

- [ ] **Step 4: Sumar schemas de TransferenciaCaja**

```python
class TransferenciaCajaCrear(BaseModel):
    caja_origen_id: int
    caja_destino_id: int
    monto: float = Field(..., gt=0)
    fecha: date
    descripcion: str = Field(..., min_length=1, max_length=500)


class TransferenciaCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caja_origen_id: int
    caja_destino_id: int
    monto: float
    fecha: date
    descripcion: str
```

- [ ] **Step 5: Sumar schema del dashboard `EstadoFinancieroOut`**

```python
class EstadoFinancieroOut(BaseModel):
    cajas: list[CajaOut]
    total: float
    ultimos_movimientos: list[MovimientoCajaOut]
```

- [ ] **Step 6: Adaptar `GastoCrear` y `GastoActualizar` para incluir `caja_id`**

Buscar `class GastoCrear` y sumar:
```python
    caja_id: int
```
(required en `GastoCrear`; `caja_id: int | None = None` en `GastoActualizar`.)

- [ ] **Step 7: Adaptar `GastoHabitualCrear` y `GastoHabitualActualizar` con `caja_id`**

Mismo patrón (required al crear, opcional al actualizar).

- [ ] **Step 8: Adaptar `PlanCuotasCrear` con `caja_id`**

```python
    caja_id: int
```

- [ ] **Step 9: Adaptar `LiquidacionEmpleadoCrear` / `LiquidacionEmpleadoActualizar` con `caja_id`**

```python
    caja_id: int
```

- [ ] **Step 10: Adaptar `ConfiguracionConsorcioOut` y `ConfiguracionConsorcioActualizar`**

Sumar a ambos:
```python
    caja_default_pagos_id: int | None = None
```

(En `ConfiguracionConsorcioActualizar` es opcional. En `ConfiguracionConsorcioOut` también es `int | None`.)

- [ ] **Step 11: Crear `backend/caja_saldo.py` (módulo puro, sin DB)**

```python
"""Cálculo de saldo de cajas.

Función pura: recibe saldo_inicial + lista de movimientos, devuelve saldo.
Sin side effects, sin DB, fácilmente testeable.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MovimientoSnapshot:
    """Snapshot mínimo de un movimiento para calcular saldo."""
    tipo: str  # "ingreso" | "egreso" | "ajuste"
    monto: float  # siempre positivo para ingreso/egreso; firmado para ajuste


def calcular_saldo(saldo_inicial: float, movimientos: list[MovimientoSnapshot]) -> float:
    """Calcula el saldo actual sumando los movimientos al saldo inicial.

    - ingreso → suma
    - egreso → resta
    - ajuste → suma el monto firmado (puede ser +/-)
    """
    saldo = saldo_inicial
    for m in movimientos:
        if m.tipo == "ingreso":
            saldo += m.monto
        elif m.tipo == "egreso":
            saldo -= m.monto
        elif m.tipo == "ajuste":
            saldo += m.monto  # monto ya firmado
        else:
            raise ValueError(f"Tipo de movimiento desconocido: {m.tipo}")
    return round(saldo, 2)
```

- [ ] **Step 12: Crear `tests/test_caja_saldo.py`**

```python
"""Tests unitarios del módulo puro caja_saldo."""
import pytest

from backend.caja_saldo import MovimientoSnapshot, calcular_saldo


def test_saldo_sin_movimientos_devuelve_saldo_inicial():
    assert calcular_saldo(1000.0, []) == 1000.0


def test_ingreso_suma_al_saldo():
    movs = [MovimientoSnapshot(tipo="ingreso", monto=500.0)]
    assert calcular_saldo(1000.0, movs) == 1500.0


def test_egreso_resta_del_saldo():
    movs = [MovimientoSnapshot(tipo="egreso", monto=300.0)]
    assert calcular_saldo(1000.0, movs) == 700.0


def test_ajuste_positivo_suma():
    movs = [MovimientoSnapshot(tipo="ajuste", monto=200.0)]
    assert calcular_saldo(1000.0, movs) == 1200.0


def test_ajuste_negativo_resta():
    movs = [MovimientoSnapshot(tipo="ajuste", monto=-150.0)]
    assert calcular_saldo(1000.0, movs) == 850.0


def test_combinacion_de_tipos():
    movs = [
        MovimientoSnapshot(tipo="ingreso", monto=2000.0),
        MovimientoSnapshot(tipo="egreso", monto=500.0),
        MovimientoSnapshot(tipo="ajuste", monto=-100.0),
    ]
    # 1000 + 2000 - 500 - 100 = 2400
    assert calcular_saldo(1000.0, movs) == 2400.0


def test_tipo_invalido_devuelve_error():
    movs = [MovimientoSnapshot(tipo="loquesea", monto=100.0)]
    with pytest.raises(ValueError, match="Tipo de movimiento desconocido"):
        calcular_saldo(0.0, movs)
```

- [ ] **Step 13: Correr los tests unitarios**

```bash
.venv/Scripts/python.exe -m pytest tests/test_caja_saldo.py -v
```

Expected: 7 passed.

- [ ] **Step 14: Commit**

```bash
git add backend/schemas.py backend/caja_saldo.py tests/test_caja_saldo.py
git commit -m "feat(schemas+caja_saldo): schemas Fase 5 + módulo puro de cálculo de saldo"
```

---

## Task 3: Adaptar conftest + tests existentes al nuevo shape

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_gastos.py`
- Modify: `tests/test_comprobantes.py`
- Modify: `tests/test_liquidaciones.py`
- Modify: `tests/test_configuracion.py`

- [ ] **Step 1: Grep fixtures que crean `Gasto(...)`, `GastoHabitual(...)`, `Comprobante(...)` en conftest**

```bash
grep -n "Gasto(\|GastoHabitual(\|Comprobante(" tests/conftest.py
```

- [ ] **Step 2: Sumar fixture `caja_seed` en conftest**

Después de la fixture `clase_a` o equivalente (al inicio del setup):

```python
@pytest.fixture
def caja_seed(db_empty):
    """Crea una caja default 'Banco Test' (id=900) y la devuelve."""
    from backend.models import Caja, TipoCaja
    caja = Caja(
        id=900,
        nombre="Banco Test",
        tipo=TipoCaja.banco,
        saldo_inicial=0.0,
        activa=True,
    )
    db_empty.add(caja)
    db_empty.flush()
    return caja
```

Si el seed sembrado del conftest (`db` con datos) ya carga una caja por defecto (vía seed.py adaptado en Task 13), no hace falta esta fixture local — usar la del seed.

- [ ] **Step 3: Adaptar todas las construcciones `Gasto(...)` en conftest para incluir `caja_id=900`** (o el id real de la caja sembrada)

Ejemplo:
```python
Gasto(
    periodo="2026-05", monto=1000, ...,
    forma_pago=FormaPago.efectivo,
    caja_id=900,  # NUEVO
)
```

- [ ] **Step 4: Adaptar `GastoHabitual(...)` igual**

```python
GastoHabitual(
    nombre="Sueldo encargado", ...,
    forma_pago=FormaPago.transferencia,
    caja_id=900,  # NUEVO
)
```

- [ ] **Step 5: Adaptar `Comprobante(...)` aprobados**

Los comprobantes en estado `pendiente_verificacion` no necesitan `caja_destino_id`. Los `aprobado` sí (sino el invariante "aprobado ⇒ tiene caja_destino" se rompe). Adaptar:

```python
Comprobante(
    departamento_id=1, fecha_pago=..., monto=..., estado=EstadoComprobante.aprobado,
    archivo_path="x.jpg",
    caja_destino_id=900,  # NUEVO en los aprobados
)
```

- [ ] **Step 6: Correr conftest sólo (smoke)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_caja_saldo.py -v
```

Expected: aún 7 passed (conftest se carga sin romper).

- [ ] **Step 7: Correr suite completa para ver qué falla**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Anotar el número de fallos. Esperable: muchos tests en `test_gastos.py`, `test_comprobantes.py`, `test_liquidaciones.py`, `test_configuracion.py` fallan por payloads que no incluyen `caja_id`.

- [ ] **Step 8: Adaptar `tests/test_gastos.py`**

Buscar todos los POST a `/gastos`, `/gastos/plan-cuotas`, `/gastos-habituales`:
```bash
grep -n "client.post.*gastos\|client.post.*plan-cuotas\|client.post.*habituales" tests/test_gastos.py
```
En cada payload sumar `"caja_id": 900` (o el id de la caja del seed).

Si hay constantes tipo `_GASTO_VALIDO`, `_PLAN_VALIDO`, `_HABITUAL_VALIDO`, agregar el campo ahí (centralizado).

- [ ] **Step 9: Adaptar `tests/test_comprobantes.py`**

Los tests que aprueban un comprobante (PATCH con estado=aprobado) ahora necesitan pasar `caja_destino_id`. Sumarlo al payload del PATCH.

- [ ] **Step 10: Adaptar `tests/test_liquidaciones.py`**

Los POST/PATCH a `/liquidaciones` ahora requieren `caja_id`. Sumar al payload.

- [ ] **Step 11: Adaptar `tests/test_configuracion.py`**

El `_PAYLOAD_VALIDO` se mantiene como está (caja_default_pagos_id es nullable). Sumar test específico:

```python
def test_put_configuracion_acepta_caja_default(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["caja_default_pagos_id"] = 900  # caja sembrada
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["caja_default_pagos_id"] == 900
```

- [ ] **Step 12: Correr suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Esperable: los tests con shape adaptado pasan. Pueden quedar algunos fallos (los routers todavía no validan/usan `caja_id`) — se arreglan en Tasks 8-12. **Anotar el número de fallos para comparar después.**

- [ ] **Step 13: Commit**

```bash
git add tests/
git commit -m "test: payloads de Gasto/GastoHabitual/Comprobante/Liquidacion con caja_id Fase 5"
```

---

## Task 4: Router `/cajas` + tests

**Files:**
- Create: `backend/routers/cajas.py`
- Create: `tests/test_cajas.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `backend/routers/cajas.py`**

```python
"""CRUD de Cajas — admin only."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..caja_saldo import MovimientoSnapshot, calcular_saldo
from ..database import get_db
from ..models import Caja, MovimientoCaja, Rol
from ..schemas import CajaCrear, CajaActualizar, CajaOut

router = APIRouter(prefix="/cajas", tags=["Cajas"])


def _caja_to_out(caja: Caja, movimientos: list[MovimientoCaja]) -> CajaOut:
    snaps = [MovimientoSnapshot(tipo=m.tipo.value, monto=m.monto) for m in movimientos]
    saldo = calcular_saldo(caja.saldo_inicial, snaps)
    return CajaOut(
        id=caja.id,
        nombre=caja.nombre,
        tipo=caja.tipo,
        descripcion=caja.descripcion,
        saldo_inicial=caja.saldo_inicial,
        saldo_actual=saldo,
        activa=caja.activa,
    )


@router.get("", response_model=list[CajaOut])
def listar_cajas(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[CajaOut]:
    cajas = db.scalars(select(Caja).order_by(Caja.id)).all()
    out = []
    for c in cajas:
        movs = db.scalars(
            select(MovimientoCaja).where(MovimientoCaja.caja_id == c.id)
        ).all()
        out.append(_caja_to_out(c, movs))
    return out


@router.post("", response_model=CajaOut, status_code=status.HTTP_201_CREATED)
def crear_caja(
    payload: CajaCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> CajaOut:
    if db.scalar(select(Caja).where(Caja.nombre == payload.nombre)):
        raise HTTPException(400, f"Ya existe una caja con el nombre '{payload.nombre}'.")
    caja = Caja(**payload.model_dump())
    db.add(caja)
    db.commit()
    db.refresh(caja)
    return _caja_to_out(caja, [])


@router.patch("/{caja_id}", response_model=CajaOut)
def actualizar_caja(
    caja_id: int,
    payload: CajaActualizar,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> CajaOut:
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, "Caja no encontrada.")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(caja, campo, valor)
    db.commit()
    db.refresh(caja)
    movs = db.scalars(
        select(MovimientoCaja).where(MovimientoCaja.caja_id == caja.id)
    ).all()
    return _caja_to_out(caja, movs)


@router.delete("/{caja_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_caja(
    caja_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, "Caja no encontrada.")
    tiene_movs = db.scalar(
        select(MovimientoCaja.id).where(MovimientoCaja.caja_id == caja_id)
    )
    if tiene_movs:
        raise HTTPException(409, "La caja tiene movimientos. Marcala inactiva en lugar de borrarla.")
    db.delete(caja)
    db.commit()
```

- [ ] **Step 2: Registrar el router en `backend/main.py`**

Sumar `cajas` al import existente `from .routers import (...)` y la línea `app.include_router(cajas.router)`.

- [ ] **Step 3: Smoke import**

```bash
.venv/Scripts/python.exe -c "from backend.main import app; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Crear `tests/test_cajas.py`**

```python
"""Tests HTTP del router /cajas."""
from backend.models import Caja, MovimientoCaja, TipoCaja, TipoMovimientoCaja
from datetime import date


def test_listar_cajas_sin_token_devuelve_401(client):
    r = client.get("/cajas")
    assert r.status_code == 401


def test_listar_cajas_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/cajas", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_cajas_como_admin_200(client, headers_admin):
    r = client.get("/cajas", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_crear_caja_admin_201(client, headers_admin):
    payload = {"nombre": "Caja Test Nueva", "tipo": "banco", "saldo_inicial": 5000}
    r = client.post("/cajas", json=payload, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Caja Test Nueva"
    assert body["tipo"] == "banco"
    assert body["saldo_inicial"] == 5000
    assert body["saldo_actual"] == 5000
    assert body["activa"] is True


def test_crear_caja_nombre_duplicado_400(client, headers_admin):
    payload = {"nombre": "Caja Duplicada", "tipo": "efectivo"}
    r1 = client.post("/cajas", json=payload, headers=headers_admin)
    assert r1.status_code == 201
    r2 = client.post("/cajas", json=payload, headers=headers_admin)
    assert r2.status_code == 400


def test_patch_caja_actualiza_nombre(client, headers_admin):
    p = client.post("/cajas", json={"nombre": "Original", "tipo": "otro"}, headers=headers_admin).json()
    r = client.patch(f"/cajas/{p['id']}", json={"nombre": "Renombrada"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Renombrada"


def test_delete_caja_sin_movimientos_204(client, headers_admin):
    p = client.post("/cajas", json={"nombre": "Borrable", "tipo": "otro"}, headers=headers_admin).json()
    r = client.delete(f"/cajas/{p['id']}", headers=headers_admin)
    assert r.status_code == 204


def test_delete_caja_con_movimientos_409(client, headers_admin, db):
    p = client.post("/cajas", json={"nombre": "Con movs", "tipo": "banco"}, headers=headers_admin).json()
    db.add(MovimientoCaja(
        caja_id=p["id"], fecha=date.today(), tipo=TipoMovimientoCaja.ajuste,
        monto=100, descripcion="test"
    ))
    db.commit()
    r = client.delete(f"/cajas/{p['id']}", headers=headers_admin)
    assert r.status_code == 409


def test_saldo_actual_refleja_movimientos(client, headers_admin, db):
    p = client.post("/cajas", json={"nombre": "Saldo Test", "tipo": "banco", "saldo_inicial": 1000}, headers=headers_admin).json()
    caja_id = p["id"]
    db.add_all([
        MovimientoCaja(caja_id=caja_id, fecha=date.today(), tipo=TipoMovimientoCaja.ingreso, monto=500, descripcion="x"),
        MovimientoCaja(caja_id=caja_id, fecha=date.today(), tipo=TipoMovimientoCaja.egreso, monto=200, descripcion="x"),
        MovimientoCaja(caja_id=caja_id, fecha=date.today(), tipo=TipoMovimientoCaja.ajuste, monto=-50, descripcion="x"),
    ])
    db.commit()
    r = client.get("/cajas", headers=headers_admin)
    cajas = r.json()
    nueva = next(c for c in cajas if c["id"] == caja_id)
    # 1000 + 500 - 200 - 50 = 1250
    assert nueva["saldo_actual"] == 1250
```

- [ ] **Step 5: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_cajas.py -v
```

Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/cajas.py backend/main.py tests/test_cajas.py
git commit -m "feat(cajas): CRUD admin + saldo calculado + tests"
```

---

## Task 5: Router `/cajas/{id}/movimientos` (ajustes) + tests

**Files:**
- Modify: `backend/routers/cajas.py`
- Create: `tests/test_movimientos_caja.py`

- [ ] **Step 1: Sumar endpoints de movimientos en `cajas.py`**

Después del DELETE de caja, antes del cierre del archivo:

```python
from ..models import PeriodoCerrado, TipoMovimientoCaja
from ..schemas import AjusteCrear, MovimientoCajaOut


def _bloquear_si_periodo_cerrado_por_fecha(db: Session, fecha) -> None:
    """Verifica que el período YYYY-MM de la fecha no esté cerrado."""
    periodo = f"{fecha.year:04d}-{fecha.month:02d}"
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )


@router.get("/{caja_id}/movimientos", response_model=list[MovimientoCajaOut])
def listar_movimientos(
    caja_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[MovimientoCaja]:
    if db.get(Caja, caja_id) is None:
        raise HTTPException(404, "Caja no encontrada.")
    return list(db.scalars(
        select(MovimientoCaja)
        .where(MovimientoCaja.caja_id == caja_id)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(limit).offset(offset)
    ).all())


@router.post(
    "/{caja_id}/movimientos",
    response_model=MovimientoCajaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cargar ajuste manual (no usar para ingreso/egreso, se generan auto)"
)
def crear_ajuste(
    caja_id: int,
    payload: AjusteCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> MovimientoCaja:
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, "Caja no encontrada.")
    if not caja.activa:
        raise HTTPException(400, "La caja está inactiva.")
    _bloquear_si_periodo_cerrado_por_fecha(db, payload.fecha)
    mov = MovimientoCaja(
        caja_id=caja_id,
        fecha=payload.fecha,
        tipo=TipoMovimientoCaja.ajuste,
        monto=payload.monto,
        descripcion=payload.descripcion,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov
```

- [ ] **Step 2: Crear `tests/test_movimientos_caja.py`**

```python
"""Tests de POST/GET /cajas/{id}/movimientos."""
from datetime import date


def _crear_caja(client, headers, nombre="Caja Mov Test"):
    return client.post(
        "/cajas", json={"nombre": nombre, "tipo": "banco"}, headers=headers
    ).json()


def test_post_ajuste_positivo_suma_al_saldo(client, headers_admin):
    c = _crear_caja(client, headers_admin)
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 500, "descripcion": "Ajuste positivo de prueba"},
        headers=headers_admin
    )
    assert r.status_code == 201
    # Verificar saldo via GET /cajas
    cajas = client.get("/cajas", headers=headers_admin).json()
    nueva = next(x for x in cajas if x["id"] == c["id"])
    assert nueva["saldo_actual"] == 500


def test_post_ajuste_negativo_resta(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Neg")
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": -200, "descripcion": "Ajuste negativo prueba"},
        headers=headers_admin
    )
    assert r.status_code == 201
    cajas = client.get("/cajas", headers=headers_admin).json()
    nueva = next(x for x in cajas if x["id"] == c["id"])
    assert nueva["saldo_actual"] == -200


def test_ajuste_descripcion_corta_devuelve_400(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Corta")
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 100, "descripcion": "abc"},
        headers=headers_admin
    )
    assert r.status_code == 400


def test_ajuste_caja_inexistente_404(client, headers_admin):
    r = client.post(
        "/cajas/9999/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 100, "descripcion": "test ajuste largo"},
        headers=headers_admin
    )
    assert r.status_code == 404


def test_ajuste_caja_inactiva_400(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Inactiva")
    client.patch(f"/cajas/{c['id']}", json={"activa": False}, headers=headers_admin)
    r = client.post(
        f"/cajas/{c['id']}/movimientos",
        json={"fecha": date.today().isoformat(), "monto": 100, "descripcion": "intento ajuste"},
        headers=headers_admin
    )
    assert r.status_code == 400


def test_listar_movimientos_paginado(client, headers_admin):
    c = _crear_caja(client, headers_admin, nombre="Caja Paginada")
    for i in range(5):
        client.post(
            f"/cajas/{c['id']}/movimientos",
            json={"fecha": date.today().isoformat(), "monto": 10*(i+1), "descripcion": f"Ajuste numero {i}"},
            headers=headers_admin
        )
    r = client.get(f"/cajas/{c['id']}/movimientos?limit=3", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_listar_movimientos_depto_403(client, headers_depto_a):
    r = client.get("/cajas/1/movimientos", headers=headers_depto_a)
    assert r.status_code == 403
```

- [ ] **Step 3: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_movimientos_caja.py -v
```

Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/cajas.py tests/test_movimientos_caja.py
git commit -m "feat(cajas): endpoints /cajas/{id}/movimientos (GET + POST ajuste) + tests"
```

---

## Task 6: Router `/transferencias-caja` + tests

**Files:**
- Create: `backend/routers/transferencias_caja.py`
- Create: `tests/test_transferencias.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `backend/routers/transferencias_caja.py`**

```python
"""POST/GET /transferencias-caja — admin only."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    Caja, MovimientoCaja, PeriodoCerrado, Rol,
    TipoMovimientoCaja, TransferenciaCaja
)
from ..schemas import TransferenciaCajaCrear, TransferenciaCajaOut

router = APIRouter(prefix="/transferencias-caja", tags=["TransferenciasCaja"])


def _bloquear_si_periodo_cerrado_por_fecha(db: Session, fecha) -> None:
    periodo = f"{fecha.year:04d}-{fecha.month:02d}"
    if db.get(PeriodoCerrado, periodo) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )


@router.get("", response_model=list[TransferenciaCajaOut])
def listar_transferencias(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    return list(db.scalars(
        select(TransferenciaCaja)
        .order_by(TransferenciaCaja.fecha.desc(), TransferenciaCaja.id.desc())
        .limit(limit).offset(offset)
    ).all())


@router.post("", response_model=TransferenciaCajaOut, status_code=status.HTTP_201_CREATED)
def crear_transferencia(
    payload: TransferenciaCajaCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    if payload.caja_origen_id == payload.caja_destino_id:
        raise HTTPException(400, "Origen y destino deben ser cajas distintas.")
    origen = db.get(Caja, payload.caja_origen_id)
    destino = db.get(Caja, payload.caja_destino_id)
    if origen is None or destino is None:
        raise HTTPException(404, "Caja origen o destino no encontrada.")
    if not origen.activa or not destino.activa:
        raise HTTPException(400, "Las cajas deben estar activas.")
    _bloquear_si_periodo_cerrado_por_fecha(db, payload.fecha)

    transf = TransferenciaCaja(**payload.model_dump())
    db.add(transf)
    db.flush()

    db.add_all([
        MovimientoCaja(
            caja_id=payload.caja_origen_id, fecha=payload.fecha,
            tipo=TipoMovimientoCaja.egreso, monto=payload.monto,
            descripcion=f"Transf → {destino.nombre}: {payload.descripcion}",
            transferencia_id=transf.id,
        ),
        MovimientoCaja(
            caja_id=payload.caja_destino_id, fecha=payload.fecha,
            tipo=TipoMovimientoCaja.ingreso, monto=payload.monto,
            descripcion=f"Transf ← {origen.nombre}: {payload.descripcion}",
            transferencia_id=transf.id,
        ),
    ])
    db.commit()
    db.refresh(transf)
    return transf
```

- [ ] **Step 2: Registrar el router en `backend/main.py`**

Sumar `transferencias_caja` al import y `app.include_router(transferencias_caja.router)`.

- [ ] **Step 3: Crear `tests/test_transferencias.py`**

```python
"""Tests de POST/GET /transferencias-caja."""
from datetime import date


def _crear_caja(client, headers, nombre):
    return client.post(
        "/cajas", json={"nombre": nombre, "tipo": "banco", "saldo_inicial": 1000},
        headers=headers
    ).json()


def test_transferencia_genera_dos_movimientos(client, headers_admin):
    a = _crear_caja(client, headers_admin, "Origen A")
    b = _crear_caja(client, headers_admin, "Destino B")
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": b["id"],
        "monto": 300, "fecha": date.today().isoformat(),
        "descripcion": "Test transfer",
    }, headers=headers_admin)
    assert r.status_code == 201

    cajas = client.get("/cajas", headers=headers_admin).json()
    nueva_a = next(c for c in cajas if c["id"] == a["id"])
    nueva_b = next(c for c in cajas if c["id"] == b["id"])
    assert nueva_a["saldo_actual"] == 700
    assert nueva_b["saldo_actual"] == 1300


def test_transferencia_misma_caja_400(client, headers_admin):
    a = _crear_caja(client, headers_admin, "Solo Una")
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": a["id"],
        "monto": 100, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_admin)
    assert r.status_code == 400


def test_transferencia_monto_cero_400(client, headers_admin):
    a = _crear_caja(client, headers_admin, "A0")
    b = _crear_caja(client, headers_admin, "B0")
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": b["id"],
        "monto": 0, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_admin)
    assert r.status_code == 400


def test_transferencia_caja_inactiva_400(client, headers_admin):
    a = _crear_caja(client, headers_admin, "A inact")
    b = _crear_caja(client, headers_admin, "B inact")
    client.patch(f"/cajas/{a['id']}", json={"activa": False}, headers=headers_admin)
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": b["id"],
        "monto": 100, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_admin)
    assert r.status_code == 400


def test_transferencia_depto_403(client, headers_depto_a):
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": 1, "caja_destino_id": 2,
        "monto": 100, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_transferencias_admin_200(client, headers_admin):
    r = client.get("/transferencias-caja", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
```

- [ ] **Step 4: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_transferencias.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/transferencias_caja.py backend/main.py tests/test_transferencias.py
git commit -m "feat(transferencias): router /transferencias-caja (genera 2 movimientos atómicos) + tests"
```

---

## Task 7: Router `/estado-financiero` + tests

**Files:**
- Create: `backend/routers/estado_financiero.py`
- Create: `tests/test_estado_financiero.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `backend/routers/estado_financiero.py`**

```python
"""GET /estado-financiero — dashboard de tesorería."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..caja_saldo import MovimientoSnapshot, calcular_saldo
from ..database import get_db
from ..models import Caja, MovimientoCaja, Rol
from ..schemas import CajaOut, EstadoFinancieroOut, MovimientoCajaOut

router = APIRouter(prefix="/estado-financiero", tags=["EstadoFinanciero"])


@router.get("", response_model=EstadoFinancieroOut)
def obtener_estado_financiero(
    ultimos: int = 20,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EstadoFinancieroOut:
    cajas_activas = list(db.scalars(select(Caja).where(Caja.activa == True).order_by(Caja.id)).all())
    cajas_out = []
    total = 0.0
    for c in cajas_activas:
        movs = list(db.scalars(
            select(MovimientoCaja).where(MovimientoCaja.caja_id == c.id)
        ).all())
        snaps = [MovimientoSnapshot(tipo=m.tipo.value, monto=m.monto) for m in movs]
        saldo = calcular_saldo(c.saldo_inicial, snaps)
        total += saldo
        cajas_out.append(CajaOut(
            id=c.id, nombre=c.nombre, tipo=c.tipo, descripcion=c.descripcion,
            saldo_inicial=c.saldo_inicial, saldo_actual=saldo, activa=c.activa,
        ))
    ultimos_movs = list(db.scalars(
        select(MovimientoCaja)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(ultimos)
    ).all())
    return EstadoFinancieroOut(
        cajas=cajas_out,
        total=round(total, 2),
        ultimos_movimientos=[MovimientoCajaOut.model_validate(m) for m in ultimos_movs],
    )
```

- [ ] **Step 2: Registrar en `backend/main.py`**

Sumar `estado_financiero` al import y `app.include_router(estado_financiero.router)`.

- [ ] **Step 3: Crear `tests/test_estado_financiero.py`**

```python
"""Tests del dashboard /estado-financiero."""


def test_estado_financiero_sin_token_401(client):
    r = client.get("/estado-financiero")
    assert r.status_code == 401


def test_estado_financiero_depto_403(client, headers_depto_a):
    r = client.get("/estado-financiero", headers=headers_depto_a)
    assert r.status_code == 403


def test_estado_financiero_admin_200_estructura(client, headers_admin):
    r = client.get("/estado-financiero", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "cajas" in body
    assert "total" in body
    assert "ultimos_movimientos" in body
    assert isinstance(body["cajas"], list)


def test_estado_financiero_excluye_cajas_inactivas(client, headers_admin):
    p = client.post("/cajas", json={"nombre": "Caja Inactiva EF", "tipo": "banco", "saldo_inicial": 5000}, headers=headers_admin).json()
    client.patch(f"/cajas/{p['id']}", json={"activa": False}, headers=headers_admin)
    r = client.get("/estado-financiero", headers=headers_admin).json()
    ids = [c["id"] for c in r["cajas"]]
    assert p["id"] not in ids


def test_estado_financiero_total_es_suma_de_saldos(client, headers_admin):
    a = client.post("/cajas", json={"nombre": "EF A", "tipo": "banco", "saldo_inicial": 1000}, headers=headers_admin).json()
    b = client.post("/cajas", json={"nombre": "EF B", "tipo": "efectivo", "saldo_inicial": 500}, headers=headers_admin).json()
    r = client.get("/estado-financiero", headers=headers_admin).json()
    # total debe ser >= 1500 (puede haber más cajas seedeadas)
    cajas_propias = [c for c in r["cajas"] if c["id"] in [a["id"], b["id"]]]
    assert sum(c["saldo_actual"] for c in cajas_propias) == 1500
```

- [ ] **Step 4: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_estado_financiero.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/estado_financiero.py backend/main.py tests/test_estado_financiero.py
git commit -m "feat(estado-financiero): dashboard GET /estado-financiero + tests"
```

---

## Task 8: Integración de Cajas en `/gastos` (POST, PATCH, DELETE)

**Files:**
- Modify: `backend/routers/gastos.py`
- Modify: `tests/test_gastos.py` (sumar tests específicos)

- [ ] **Step 1: En `backend/routers/gastos.py`, sumar import**

```python
from ..models import Caja, MovimientoCaja, TipoMovimientoCaja
```

- [ ] **Step 2: Sumar helper `_validar_caja_activa`**

Después del helper `_bloquear_si_periodo_cerrado`:

```python
def _validar_caja_activa(db: Session, caja_id: int) -> Caja:
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, f"Caja {caja_id} no encontrada.")
    if not caja.activa:
        raise HTTPException(400, f"La caja '{caja.nombre}' está inactiva.")
    return caja


def _crear_movimiento_para_gasto(db: Session, gasto: Gasto) -> None:
    """Crea el MovimientoCaja egreso asociado a un Gasto."""
    db.add(MovimientoCaja(
        caja_id=gasto.caja_id,
        fecha=gasto.fecha_pago,
        tipo=TipoMovimientoCaja.egreso,
        monto=gasto.monto,
        descripcion=gasto.concepto or f"Gasto {gasto.id}",
        gasto_id=gasto.id,
    ))


def _borrar_movimiento_de_gasto(db: Session, gasto_id: int) -> None:
    """Borra el MovimientoCaja asociado a un Gasto (si existe)."""
    movs = db.scalars(
        select(MovimientoCaja).where(MovimientoCaja.gasto_id == gasto_id)
    ).all()
    for m in movs:
        db.delete(m)
```

- [ ] **Step 3: Adaptar `crear_gasto`** — antes de `db.add(gasto)`, validar caja:

```python
    _validar_caja_activa(db, payload.caja_id)
```

Y después de `db.flush()` (para obtener `gasto.id`):

```python
    _crear_movimiento_para_gasto(db, gasto)
```

Antes del `db.commit()` final.

- [ ] **Step 4: Adaptar `actualizar_gasto`** — al final del PATCH, antes del commit:

```python
    _borrar_movimiento_de_gasto(db, gasto.id)
    _crear_movimiento_para_gasto(db, gasto)
```

Si `payload.caja_id` está presente, validar:

```python
    if payload.caja_id is not None:
        _validar_caja_activa(db, payload.caja_id)
```

- [ ] **Step 5: Adaptar `eliminar_gasto`** — antes de `db.delete(gasto)`:

```python
    _borrar_movimiento_de_gasto(db, gasto.id)
```

- [ ] **Step 6: Adaptar `crear_plan_cuotas`** — validar caja y crear movimiento por cada cuota generada

Al inicio, después de validar período:
```python
    _validar_caja_activa(db, payload.caja_id)
```

En el loop de cuotas, al construir cada Gasto, sumar `caja_id=payload.caja_id`. Después del `db.add(gasto)` y `db.flush()`, llamar `_crear_movimiento_para_gasto(db, gasto)`.

- [ ] **Step 7: Adaptar `cargar_habituales`** — el GastoHabitual ya tiene `caja_id`, usarlo al construir cada Gasto

En el loop, construir cada `Gasto(..., caja_id=habitual.caja_id, ...)` y crear movimiento.

- [ ] **Step 8: Sumar tests específicos en `tests/test_gastos.py`**

Al final del archivo:

```python
def test_crear_gasto_sin_caja_id_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO)
    payload.pop("caja_id", None)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_caja_inexistente_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, caja_id=99999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_gasto_genera_movimiento_caja(client, headers_admin, db):
    from backend.models import MovimientoCaja
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    gasto_id = r.json()["id"]
    movs = db.query(MovimientoCaja).filter_by(gasto_id=gasto_id).all()
    assert len(movs) == 1
    assert movs[0].tipo.value == "egreso"
    assert movs[0].monto == r.json()["monto"]


def test_patch_gasto_recrea_movimiento(client, headers_admin, db):
    from backend.models import MovimientoCaja
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin).json()
    gasto_id = r["id"]
    nuevo_monto = r["monto"] + 100
    client.patch(f"/gastos/{gasto_id}", json={"monto": nuevo_monto}, headers=headers_admin)
    movs = db.query(MovimientoCaja).filter_by(gasto_id=gasto_id).all()
    assert len(movs) == 1
    assert movs[0].monto == nuevo_monto


def test_delete_gasto_borra_movimiento(client, headers_admin, db):
    from backend.models import MovimientoCaja
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin).json()
    gasto_id = r["id"]
    client.delete(f"/gastos/{gasto_id}", headers=headers_admin)
    movs = db.query(MovimientoCaja).filter_by(gasto_id=gasto_id).all()
    assert len(movs) == 0
```

- [ ] **Step 9: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v --tb=short
```

Expected: todos los tests existentes + 5 nuevos pasan.

- [ ] **Step 10: Commit**

```bash
git add backend/routers/gastos.py tests/test_gastos.py
git commit -m "feat(gastos): integración con Cajas — caja_id required + movimiento cascade"
```

---

## Task 9: Integración en `/gastos-habituales`

**Files:**
- Modify: `backend/routers/gastos_habituales.py`
- Modify: `tests/test_gastos_habituales.py`

- [ ] **Step 1: En el router, sumar import + validación de caja al POST/PATCH**

```python
from ..models import Caja


def _validar_caja_activa(db: Session, caja_id: int) -> Caja:
    caja = db.get(Caja, caja_id)
    if caja is None:
        raise HTTPException(404, f"Caja {caja_id} no encontrada.")
    if not caja.activa:
        raise HTTPException(400, f"La caja '{caja.nombre}' está inactiva.")
    return caja
```

En `crear_habitual` y `actualizar_habitual`: validar `payload.caja_id` antes de construir/actualizar el modelo.

- [ ] **Step 2: Adaptar tests existentes para incluir `caja_id` en payloads**

Buscar `_HABITUAL_VALIDO` y sumar `"caja_id": 900` (o el id real del seed).

- [ ] **Step 3: Sumar tests específicos**

```python
def test_crear_habitual_sin_caja_id_400(client, headers_admin):
    payload = dict(_HABITUAL_VALIDO)
    payload.pop("caja_id", None)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_habitual_caja_inexistente_404(client, headers_admin):
    payload = dict(_HABITUAL_VALIDO, caja_id=99999)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_gastos_habituales.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/routers/gastos_habituales.py tests/test_gastos_habituales.py
git commit -m "feat(habituales): caja_id required + validación"
```

---

## Task 10: Integración en `/comprobantes` (aprobar con caja_destino)

**Files:**
- Modify: `backend/routers/comprobantes.py`
- Modify: `tests/test_comprobantes.py`

- [ ] **Step 1: En `comprobantes.py`, sumar imports**

```python
from ..models import Caja, ConfiguracionConsorcio, MovimientoCaja, TipoMovimientoCaja
```

- [ ] **Step 2: Adaptar el endpoint que aprueba el comprobante (PATCH)**

Identificar el endpoint que cambia `estado` a `aprobado` (probablemente `actualizar_comprobante`). Cuando se aprueba:

1. Resolver `caja_destino_id`:
```python
    caja_destino_id = payload.caja_destino_id
    if caja_destino_id is None:
        cfg = db.get(ConfiguracionConsorcio, 1)
        caja_destino_id = cfg.caja_default_pagos_id if cfg else None
    if caja_destino_id is None:
        raise HTTPException(400, "Debe indicar caja_destino_id (no hay default configurada).")
```

2. Validar caja activa:
```python
    caja_dst = db.get(Caja, caja_destino_id)
    if caja_dst is None or not caja_dst.activa:
        raise HTTPException(400, "Caja destino inválida o inactiva.")
```

3. Persistir en el comprobante:
```python
    comprobante.caja_destino_id = caja_destino_id
```

4. Generar MovimientoCaja además del MovimientoCuenta existente:
```python
    db.add(MovimientoCaja(
        caja_id=caja_destino_id,
        fecha=comprobante.fecha_pago,
        tipo=TipoMovimientoCaja.ingreso,
        monto=comprobante.monto,
        descripcion=f"Pago comprobante #{comprobante.id}",
        comprobante_id=comprobante.id,
    ))
```

- [ ] **Step 3: En `ComprobanteActualizar` schema (en schemas.py), sumar `caja_destino_id: int | None`**

(Si todavía no lo hiciste en Task 2.)

- [ ] **Step 4: Sumar tests**

```python
def test_aprobar_comprobante_sin_caja_y_sin_default_400(client, headers_admin):
    # Asumiendo que el seed setea caja_default_pagos_id, primero borrarla
    client.put("/configuracion", json={...sin caja_default_pagos_id...}, headers=headers_admin)
    # Crear un comprobante pendiente
    ...
    r = client.patch(f"/comprobantes/{cid}", json={"estado": "aprobado"}, headers=headers_admin)
    assert r.status_code == 400


def test_aprobar_comprobante_con_default_usa_default(client, headers_admin, db):
    from backend.models import MovimientoCaja
    # Crear un comprobante pendiente (asumiendo seed)
    ...
    r = client.patch(f"/comprobantes/{cid}", json={"estado": "aprobado"}, headers=headers_admin)
    assert r.status_code == 200
    movs = db.query(MovimientoCaja).filter_by(comprobante_id=cid).all()
    assert len(movs) == 1
    assert movs[0].tipo.value == "ingreso"


def test_aprobar_comprobante_con_caja_explicita(client, headers_admin, db):
    from backend.models import MovimientoCaja
    # Crear caja extra + crear comprobante pendiente
    caja = client.post("/cajas", json={"nombre": "Banco Extra", "tipo": "banco"}, headers=headers_admin).json()
    ...
    r = client.patch(f"/comprobantes/{cid}", json={"estado": "aprobado", "caja_destino_id": caja["id"]}, headers=headers_admin)
    assert r.status_code == 200
    movs = db.query(MovimientoCaja).filter_by(comprobante_id=cid).all()
    assert movs[0].caja_id == caja["id"]
```

(Completar los `...` con la lógica concreta de crear comprobante pendiente, usando los fixtures existentes.)

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_comprobantes.py -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/comprobantes.py backend/schemas.py tests/test_comprobantes.py
git commit -m "feat(comprobantes): caja_destino_id al aprobar + genera MovimientoCaja ingreso"
```

---

## Task 11: Integración en `/liquidaciones` (caja_id required)

**Files:**
- Modify: `backend/routers/liquidaciones.py`
- Modify: `tests/test_liquidaciones.py`

- [ ] **Step 1: En el router, validar `payload.caja_id` y propagarla a los Gastos generados**

En POST/PATCH liquidación:
1. Validar caja activa (helper igual a Task 8).
2. Cada Gasto del rubro `sueldos_y_cargas_sociales` que se genera al liquidar lleva `caja_id=payload.caja_id`.
3. Por cada Gasto generado se crea su MovimientoCaja egreso (similar a Task 8).

- [ ] **Step 2: Cuando se edita una liquidación (PATCH)**: borrar movimientos viejos asociados a los gastos viejos y recrear con los nuevos.

- [ ] **Step 3: Adaptar tests existentes para incluir `caja_id` en payloads**

- [ ] **Step 4: Sumar test específico que verifique la creación de MovimientoCaja**

```python
def test_liquidacion_genera_movimientos_caja(client, headers_admin, db):
    from backend.models import MovimientoCaja, Gasto
    payload = {..., "caja_id": 900}  # caja sembrada
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 201
    liq_id = r.json()["id"]
    gastos = db.query(Gasto).filter_by(liquidacion_id=liq_id).all()
    for g in gastos:
        movs = db.query(MovimientoCaja).filter_by(gasto_id=g.id).all()
        assert len(movs) == 1
        assert movs[0].caja_id == 900
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_liquidaciones.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/liquidaciones.py tests/test_liquidaciones.py
git commit -m "feat(liquidaciones): caja_id propagada a Gastos generados + MovimientoCaja cascade"
```

---

## Task 12: Configuración + `caja_default_pagos_id`

**Files:**
- (Cambio menor: el router `/configuracion` usa `model_dump()` así que ya pasa el campo automáticamente — ver Fase 4 Task 9 para el patrón.)
- Modify: `tests/test_configuracion.py`

- [ ] **Step 1: Smoke — verificar que el campo ya entra al PUT**

```bash
.venv/Scripts/python.exe -m pytest tests/test_configuracion.py -v
```

Si pasa, no hay que tocar router. Si falla con 400, sumar el campo a `_PAYLOAD_VALIDO`.

- [ ] **Step 2: Sumar tests específicos**

```python
def test_get_configuracion_incluye_caja_default(client, headers_admin):
    r = client.get("/configuracion", headers=headers_admin)
    assert "caja_default_pagos_id" in r.json()


def test_put_configuracion_setear_caja_default(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["caja_default_pagos_id"] = 900
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["caja_default_pagos_id"] == 900
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_configuracion.py
git commit -m "test(configuracion): cobertura del campo caja_default_pagos_id"
```

---

## Task 13: OpenAPI

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Sumar tag**

```yaml
  - name: Cajas
    description: Cuentas financieras del consorcio
  - name: TransferenciasCaja
    description: Transferencias entre cajas
  - name: EstadoFinanciero
    description: Dashboard de tesorería
```

- [ ] **Step 2: Sumar paths nuevos**

```yaml
  /cajas:
    get:
      tags: [Cajas]
      summary: Listar cajas con saldo (admin)
      operationId: listarCajas
      security:
        - bearerAuth: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/CajaOut' }
        '401': { description: Token ausente }
        '403': { description: Rol sin permisos }
    post:
      tags: [Cajas]
      summary: Crear caja (admin)
      operationId: crearCaja
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CajaCrear' }
      responses:
        '201': { description: Creada, content: { application/json: { schema: { $ref: '#/components/schemas/CajaOut' }}}}
        '400': { description: Nombre duplicado o payload inválido }

  /cajas/{caja_id}:
    patch:
      tags: [Cajas]
      summary: Editar caja (admin)
      operationId: actualizarCaja
      security: [{bearerAuth: []}]
      parameters:
        - name: caja_id
          in: path
          required: true
          schema: { type: integer }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CajaActualizar' }
      responses:
        '200': { description: OK }
        '404': { description: No encontrada }
    delete:
      tags: [Cajas]
      summary: Eliminar caja (admin, solo sin movimientos)
      operationId: eliminarCaja
      security: [{bearerAuth: []}]
      parameters:
        - name: caja_id
          in: path
          required: true
          schema: { type: integer }
      responses:
        '204': { description: Borrada }
        '404': { description: No encontrada }
        '409': { description: Tiene movimientos, no se puede borrar }

  /cajas/{caja_id}/movimientos:
    get:
      tags: [Cajas]
      summary: Listar movimientos de una caja (admin)
      operationId: listarMovimientos
      security: [{bearerAuth: []}]
      parameters:
        - name: caja_id
          in: path
          required: true
          schema: { type: integer }
        - name: limit
          in: query
          schema: { type: integer, default: 100 }
        - name: offset
          in: query
          schema: { type: integer, default: 0 }
      responses:
        '200': { description: OK }
    post:
      tags: [Cajas]
      summary: Cargar ajuste manual (admin)
      operationId: crearAjuste
      security: [{bearerAuth: []}]
      parameters:
        - name: caja_id
          in: path
          required: true
          schema: { type: integer }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/AjusteCrear' }
      responses:
        '201': { description: Ajuste creado }
        '400': { description: Caja inactiva o descripción muy corta }
        '404': { description: Caja no encontrada }
        '409': { description: Período cerrado }

  /transferencias-caja:
    get:
      tags: [TransferenciasCaja]
      summary: Listar transferencias (admin)
      operationId: listarTransferencias
      security: [{bearerAuth: []}]
      responses:
        '200': { description: OK }
    post:
      tags: [TransferenciasCaja]
      summary: Crear transferencia (admin)
      operationId: crearTransferencia
      security: [{bearerAuth: []}]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/TransferenciaCajaCrear' }
      responses:
        '201': { description: Creada }
        '400': { description: Origen=destino, monto<=0, caja inactiva }
        '409': { description: Período cerrado }

  /estado-financiero:
    get:
      tags: [EstadoFinanciero]
      summary: Dashboard de tesorería (admin)
      operationId: obtenerEstadoFinanciero
      security: [{bearerAuth: []}]
      parameters:
        - name: ultimos
          in: query
          schema: { type: integer, default: 20 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EstadoFinancieroOut' }
```

- [ ] **Step 3: Sumar 8 schemas nuevos en `components.schemas`**

```yaml
    CajaCrear:
      type: object
      required: [nombre, tipo]
      properties:
        nombre: { type: string, minLength: 1, maxLength: 100 }
        tipo: { type: string, enum: [efectivo, banco, fondo_reparacion, otro] }
        descripcion: { type: string, maxLength: 500 }
        saldo_inicial: { type: number, default: 0 }
        activa: { type: boolean, default: true }

    CajaActualizar:
      type: object
      properties:
        nombre: { type: string, minLength: 1, maxLength: 100 }
        descripcion: { type: string }
        activa: { type: boolean }

    CajaOut:
      type: object
      properties:
        id: { type: integer }
        nombre: { type: string }
        tipo: { type: string }
        descripcion: { type: string, nullable: true }
        saldo_inicial: { type: number }
        saldo_actual: { type: number }
        activa: { type: boolean }

    AjusteCrear:
      type: object
      required: [fecha, monto, descripcion]
      properties:
        fecha: { type: string, format: date }
        monto: { type: number, description: "Positivo o negativo" }
        descripcion: { type: string, minLength: 5, maxLength: 500 }

    MovimientoCajaOut:
      type: object
      properties:
        id: { type: integer }
        caja_id: { type: integer }
        fecha: { type: string, format: date }
        tipo: { type: string, enum: [ingreso, egreso, ajuste] }
        monto: { type: number }
        descripcion: { type: string }
        gasto_id: { type: integer, nullable: true }
        comprobante_id: { type: integer, nullable: true }
        transferencia_id: { type: integer, nullable: true }

    TransferenciaCajaCrear:
      type: object
      required: [caja_origen_id, caja_destino_id, monto, fecha, descripcion]
      properties:
        caja_origen_id: { type: integer }
        caja_destino_id: { type: integer }
        monto: { type: number, exclusiveMinimum: 0 }
        fecha: { type: string, format: date }
        descripcion: { type: string, minLength: 1, maxLength: 500 }

    TransferenciaCajaOut:
      type: object
      properties:
        id: { type: integer }
        caja_origen_id: { type: integer }
        caja_destino_id: { type: integer }
        monto: { type: number }
        fecha: { type: string, format: date }
        descripcion: { type: string }

    EstadoFinancieroOut:
      type: object
      properties:
        cajas:
          type: array
          items: { $ref: '#/components/schemas/CajaOut' }
        total: { type: number }
        ultimos_movimientos:
          type: array
          items: { $ref: '#/components/schemas/MovimientoCajaOut' }
```

- [ ] **Step 4: Modificar schemas existentes**

- `GastoCrear`, `GastoActualizar`: sumar `caja_id: { type: integer }`. En `GastoCrear` agregar a `required`.
- `GastoHabitualCrear`, `GastoHabitualActualizar`: idem.
- `PlanCuotasCrear`: idem.
- `LiquidacionEmpleadoCrear`, `LiquidacionEmpleadoActualizar`: idem.
- `ConfiguracionConsorcioOut`, `ConfiguracionConsorcioActualizar`: sumar `caja_default_pagos_id: { type: integer, nullable: true }`.
- `ComprobanteActualizar`: sumar `caja_destino_id: { type: integer, nullable: true }`.

- [ ] **Step 5: Validar YAML**

```bash
.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml').read()); print('OK')"
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): tags + paths + schemas de Fase 5 (cajas, transferencias, estado-financiero)"
```

---

## Task 14: Seed actualizado

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Sumar imports**

```python
from .models import Caja, MovimientoCaja, TipoCaja, TipoMovimientoCaja
```

- [ ] **Step 2: Crear las 3 cajas default al inicio del seed (después de proveedores, antes de configuración)**

```python
# ----- Fase 5: cajas default -----
caja_banco = Caja(
    id=1, nombre="Banco Provincia", tipo=TipoCaja.banco, saldo_inicial=0.0, activa=True
)
caja_chica = Caja(
    id=2, nombre="Caja chica", tipo=TipoCaja.efectivo, saldo_inicial=0.0, activa=True
)
caja_fondo = Caja(
    id=3, nombre="Fondo de reparación", tipo=TipoCaja.fondo_reparacion,
    saldo_inicial=0.0, activa=True,
)
db.add_all([caja_banco, caja_chica, caja_fondo])
db.flush()
```

- [ ] **Step 3: Setear `caja_default_pagos_id` en la ConfiguracionConsorcio**

En el `ConfiguracionConsorcio(...)` existente, sumar:
```python
    caja_default_pagos_id=caja_banco.id,
```

- [ ] **Step 4: Sumar `caja_id=caja_banco.id` a cada `GastoHabitual(...)` del seed**

- [ ] **Step 5: Sumar `caja_id=caja_banco.id` a cada `Gasto(...)` del seed**

Y por cada Gasto del seed, sumar un MovimientoCaja egreso correspondiente. Si el seed tiene un loop o helper, adaptarlo. Si crea cada gasto manualmente, sumar al final de cada `db.add(gasto)`:

```python
db.flush()
db.add(MovimientoCaja(
    caja_id=caja_banco.id, fecha=gasto.fecha_pago,
    tipo=TipoMovimientoCaja.egreso, monto=gasto.monto,
    descripcion=gasto.concepto, gasto_id=gasto.id,
))
```

- [ ] **Step 6: Sumar `caja_destino_id=caja_banco.id` a cada `Comprobante(...)` ya aprobado del seed**

Y por cada uno, sumar el MovimientoCaja ingreso correspondiente.

- [ ] **Step 7: Smoke — re-seed**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
.venv/Scripts/python.exe -c "from backend.database import engine; from backend.models import Base; Base.metadata.create_all(engine); from backend.seed import seed_if_empty; from backend.database import SessionLocal; seed_if_empty(SessionLocal()); print('seed OK')"
```

Expected: `seed OK`.

- [ ] **Step 8: Verificar suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: todos pasan (los nuevos tests de cajas + los existentes adaptados).

- [ ] **Step 9: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): 3 cajas default + Gastos/Comprobantes con caja_id y movimientos"
```

---

## Task 15: Frontend API clients

**Files:**
- Create: `frontend/src/api/cajas.js`
- Create: `frontend/src/api/movimientosCaja.js`
- Create: `frontend/src/api/transferencias.js`
- Create: `frontend/src/api/estadoFinanciero.js`

- [ ] **Step 1: Crear `frontend/src/api/cajas.js`**

```javascript
import { apiFetch } from "./client";

export function listarCajas() { return apiFetch("/cajas"); }
export function crearCaja(payload) { return apiFetch("/cajas", { method: "POST", body: payload }); }
export function actualizarCaja(id, payload) { return apiFetch(`/cajas/${id}`, { method: "PATCH", body: payload }); }
export function eliminarCaja(id) { return apiFetch(`/cajas/${id}`, { method: "DELETE" }); }
```

- [ ] **Step 2: Crear `frontend/src/api/movimientosCaja.js`**

```javascript
import { apiFetch } from "./client";

export function listarMovimientos(cajaId, { limit = 100, offset = 0 } = {}) {
  return apiFetch(`/cajas/${cajaId}/movimientos?limit=${limit}&offset=${offset}`);
}

export function crearAjuste(cajaId, payload) {
  return apiFetch(`/cajas/${cajaId}/movimientos`, { method: "POST", body: payload });
}
```

- [ ] **Step 3: Crear `frontend/src/api/transferencias.js`**

```javascript
import { apiFetch } from "./client";

export function listarTransferencias() { return apiFetch("/transferencias-caja"); }
export function crearTransferencia(payload) {
  return apiFetch("/transferencias-caja", { method: "POST", body: payload });
}
```

- [ ] **Step 4: Crear `frontend/src/api/estadoFinanciero.js`**

```javascript
import { apiFetch } from "./client";

export function obtenerEstadoFinanciero({ ultimos = 20 } = {}) {
  return apiFetch(`/estado-financiero?ultimos=${ultimos}`);
}
```

- [ ] **Step 5: Build smoke**

```bash
cd frontend && npm run build
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/
git commit -m "feat(frontend/api): clients cajas, movimientosCaja, transferencias, estadoFinanciero"
```

---

## Task 16: Frontend — Pantalla `/estado-financiero`

**Files:**
- Create: `frontend/src/screens/EstadoFinanciero.jsx`
- Create: `frontend/src/components/ModalNuevaTransferencia.jsx`

- [ ] **Step 1: Crear `EstadoFinanciero.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { obtenerEstadoFinanciero } from "../api/estadoFinanciero";
import Tarjeta from "../components/Tarjeta";
import ModalNuevaTransferencia from "../components/ModalNuevaTransferencia";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function EstadoFinanciero() {
  const [data, setData] = useState(null);
  const [modalTransfer, setModalTransfer] = useState(false);

  async function cargar() {
    const r = await obtenerEstadoFinanciero();
    if (r.status === 200) setData(r.data);
  }

  useEffect(() => { cargar(); }, []);

  if (!data) return <p>Cargando…</p>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Estado financiero</h2>
        <button type="button" onClick={() => setModalTransfer(true)}>
          🔄 Transferir entre cajas
        </button>
      </header>

      <Tarjeta>
        <h3>Total general</h3>
        <p style={{ fontSize: "1.5em" }}><strong>{fmtMoney(data.total)}</strong></p>
      </Tarjeta>

      <div className="grid-cajas" style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
        {data.cajas.map((c) => (
          <Link key={c.id} to={`/cajas?caja=${c.id}`} style={{ textDecoration: "none" }}>
            <Tarjeta>
              <h3>{c.nombre}</h3>
              <p className="meta">{c.tipo}</p>
              <p style={{ fontSize: "1.3em" }}><strong>{fmtMoney(c.saldo_actual)}</strong></p>
            </Tarjeta>
          </Link>
        ))}
      </div>

      <Tarjeta>
        <h3>Últimos 20 movimientos</h3>
        {data.ultimos_movimientos.length === 0 ? (
          <p>Sin movimientos.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Fecha</th><th>Caja</th><th>Tipo</th><th>Monto</th><th>Descripción</th>
              </tr>
            </thead>
            <tbody>
              {data.ultimos_movimientos.map((m) => {
                const caja = data.cajas.find((c) => c.id === m.caja_id);
                return (
                  <tr key={m.id}>
                    <td>{m.fecha}</td>
                    <td>{caja?.nombre || m.caja_id}</td>
                    <td>{m.tipo}</td>
                    <td>{fmtMoney(m.monto)}</td>
                    <td>{m.descripcion}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Tarjeta>

      {modalTransfer && (
        <ModalNuevaTransferencia
          cajas={data.cajas}
          onClose={() => setModalTransfer(false)}
          onCreada={() => { setModalTransfer(false); cargar(); }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Crear `ModalNuevaTransferencia.jsx`**

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { crearTransferencia } from "../api/transferencias";

export default function ModalNuevaTransferencia({ cajas, onClose, onCreada }) {
  const [origen, setOrigen] = useState(cajas[0]?.id || "");
  const [destino, setDestino] = useState(cajas[1]?.id || "");
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [descripcion, setDescripcion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const r = await crearTransferencia({
      caja_origen_id: Number(origen),
      caja_destino_id: Number(destino),
      monto: Number(monto),
      fecha,
      descripcion,
    });
    setGuardando(false);
    if (r.status === 201) onCreada();
    else setError(r.data?.detail || "No se pudo crear la transferencia.");
  }

  return (
    <Modal titulo="Transferir entre cajas" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>
          Origen
          <select value={origen} onChange={(e) => setOrigen(e.target.value)} required>
            {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label>
          Destino
          <select value={destino} onChange={(e) => setDestino(e.target.value)} required>
            {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label>
          Monto
          <input type="number" step="0.01" min="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} required />
        </label>
        <label>
          Fecha
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} required />
        </label>
        <label>
          Descripción
          <input type="text" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} required />
        </label>
        {error && <p role="alert" className="error-banner">{error}</p>}
        <button type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Confirmar transferencia"}
        </button>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 3: Build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/screens/EstadoFinanciero.jsx frontend/src/components/ModalNuevaTransferencia.jsx
git commit -m "feat(frontend): pantalla /estado-financiero + ModalNuevaTransferencia"
```

---

## Task 17: Frontend — Pantalla `/cajas` + modales

**Files:**
- Create: `frontend/src/screens/Cajas.jsx`
- Create: `frontend/src/components/ModalCaja.jsx` (crear/editar)
- Create: `frontend/src/components/ModalAjusteCaja.jsx`

- [ ] **Step 1: Crear `Cajas.jsx`** (CRUD admin con tabla + modal detalle)

```jsx
import { useEffect, useState } from "react";
import { listarCajas, eliminarCaja } from "../api/cajas";
import { listarMovimientos } from "../api/movimientosCaja";
import Tarjeta from "../components/Tarjeta";
import ModalCaja from "../components/ModalCaja";
import ModalAjusteCaja from "../components/ModalAjusteCaja";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

export default function Cajas() {
  const [cajas, setCajas] = useState([]);
  const [modalCaja, setModalCaja] = useState(null);  // null | "nueva" | caja-object para editar
  const [modalAjuste, setModalAjuste] = useState(null); // null | caja-object
  const [detalleCaja, setDetalleCaja] = useState(null);
  const [movimientos, setMovimientos] = useState([]);

  async function cargar() {
    const r = await listarCajas();
    if (r.status === 200) setCajas(r.data);
  }

  useEffect(() => { cargar(); }, []);

  async function abrirDetalle(caja) {
    setDetalleCaja(caja);
    const r = await listarMovimientos(caja.id, { limit: 50 });
    if (r.status === 200) setMovimientos(r.data);
  }

  async function borrar(caja) {
    if (!window.confirm(`¿Eliminar caja "${caja.nombre}"?`)) return;
    const r = await eliminarCaja(caja.id);
    if (r.status === 204) cargar();
    else alert(r.data?.detail || "No se pudo borrar.");
  }

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Cajas</h2>
        <button type="button" onClick={() => setModalCaja("nueva")}>+ Nueva caja</button>
      </header>

      <table>
        <thead>
          <tr>
            <th>Nombre</th><th>Tipo</th><th>Descripción</th><th>Saldo</th><th>Activa</th><th></th>
          </tr>
        </thead>
        <tbody>
          {cajas.map((c) => (
            <tr key={c.id}>
              <td><button type="button" onClick={() => abrirDetalle(c)} style={{textDecoration: "underline"}}>{c.nombre}</button></td>
              <td>{c.tipo}</td>
              <td>{c.descripcion || "—"}</td>
              <td>{fmtMoney(c.saldo_actual)}</td>
              <td>{c.activa ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModalCaja(c)}>Editar</button>
                <button type="button" onClick={() => setModalAjuste(c)}>Ajuste</button>
                <button type="button" onClick={() => borrar(c)}>Borrar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {detalleCaja && (
        <Tarjeta>
          <h3>Movimientos de "{detalleCaja.nombre}"</h3>
          <button type="button" onClick={() => setDetalleCaja(null)}>Cerrar</button>
          <table>
            <thead><tr><th>Fecha</th><th>Tipo</th><th>Monto</th><th>Descripción</th></tr></thead>
            <tbody>
              {movimientos.map((m) => (
                <tr key={m.id}>
                  <td>{m.fecha}</td>
                  <td>{m.tipo}</td>
                  <td>{fmtMoney(m.monto)}</td>
                  <td>{m.descripcion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tarjeta>
      )}

      {modalCaja && (
        <ModalCaja
          caja={modalCaja === "nueva" ? null : modalCaja}
          onClose={() => setModalCaja(null)}
          onGuardada={() => { setModalCaja(null); cargar(); }}
        />
      )}

      {modalAjuste && (
        <ModalAjusteCaja
          caja={modalAjuste}
          onClose={() => setModalAjuste(null)}
          onCreado={() => { setModalAjuste(null); cargar(); }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Crear `ModalCaja.jsx`** (crear o editar caja)

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { crearCaja, actualizarCaja } from "../api/cajas";

export default function ModalCaja({ caja, onClose, onGuardada }) {
  const esEditar = caja !== null;
  const [nombre, setNombre] = useState(caja?.nombre || "");
  const [tipo, setTipo] = useState(caja?.tipo || "banco");
  const [descripcion, setDescripcion] = useState(caja?.descripcion || "");
  const [saldoInicial, setSaldoInicial] = useState(caja?.saldo_inicial || 0);
  const [activa, setActiva] = useState(caja?.activa ?? true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = esEditar
      ? { nombre, descripcion, activa }
      : { nombre, tipo, descripcion, saldo_inicial: Number(saldoInicial), activa };
    const r = esEditar
      ? await actualizarCaja(caja.id, payload)
      : await crearCaja(payload);
    setGuardando(false);
    if (r.status === 200 || r.status === 201) onGuardada();
    else setError(r.data?.detail || "Error al guardar.");
  }

  return (
    <Modal titulo={esEditar ? "Editar caja" : "Nueva caja"} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>Nombre <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} required /></label>
        {!esEditar && (
          <>
            <label>Tipo
              <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
                <option value="banco">Banco</option>
                <option value="efectivo">Efectivo</option>
                <option value="fondo_reparacion">Fondo de reparación</option>
                <option value="otro">Otro</option>
              </select>
            </label>
            <label>Saldo inicial <input type="number" step="0.01" value={saldoInicial} onChange={(e) => setSaldoInicial(e.target.value)} /></label>
          </>
        )}
        <label>Descripción <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></label>
        <label><input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Activa</label>
        {error && <p role="alert" className="error-banner">{error}</p>}
        <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 3: Crear `ModalAjusteCaja.jsx`** (cargar ajuste manual)

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { crearAjuste } from "../api/movimientosCaja";

export default function ModalAjusteCaja({ caja, onClose, onCreado }) {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [monto, setMonto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const r = await crearAjuste(caja.id, {
      fecha, monto: Number(monto), descripcion,
    });
    setGuardando(false);
    if (r.status === 201) onCreado();
    else setError(r.data?.detail || "Error al crear el ajuste.");
  }

  return (
    <Modal titulo={`Ajuste manual — ${caja.nombre}`} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <p>Cargá un ajuste positivo o negativo. Quedará registrado con su descripción.</p>
        <label>Fecha <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} required /></label>
        <label>Monto (+/-) <input type="number" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} required /></label>
        <label>Descripción (mín 5 chars) <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} minLength="5" required /></label>
        {error && <p role="alert" className="error-banner">{error}</p>}
        <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Confirmar ajuste"}</button>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 4: Build**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/screens/Cajas.jsx frontend/src/components/ModalCaja.jsx frontend/src/components/ModalAjusteCaja.jsx
git commit -m "feat(frontend): pantalla /cajas con CRUD + modales caja y ajuste manual"
```

---

## Task 18: Frontend — Pantalla `/transferencias`

**Files:**
- Create: `frontend/src/screens/Transferencias.jsx`

- [ ] **Step 1: Crear pantalla simple que liste transferencias + reuse el modal**

```jsx
import { useEffect, useState } from "react";
import { listarTransferencias } from "../api/transferencias";
import { listarCajas } from "../api/cajas";
import ModalNuevaTransferencia from "../components/ModalNuevaTransferencia";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

export default function Transferencias() {
  const [transfers, setTransfers] = useState([]);
  const [cajas, setCajas] = useState([]);
  const [modal, setModal] = useState(false);

  async function cargar() {
    const [t, c] = await Promise.all([listarTransferencias(), listarCajas()]);
    if (t.status === 200) setTransfers(t.data);
    if (c.status === 200) setCajas(c.data);
  }

  useEffect(() => { cargar(); }, []);

  const nombreCaja = (id) => cajas.find((c) => c.id === id)?.nombre || `#${id}`;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Transferencias entre cajas</h2>
        <button type="button" onClick={() => setModal(true)}>+ Nueva transferencia</button>
      </header>
      <table>
        <thead><tr><th>Fecha</th><th>Origen</th><th>Destino</th><th>Monto</th><th>Descripción</th></tr></thead>
        <tbody>
          {transfers.map((t) => (
            <tr key={t.id}>
              <td>{t.fecha}</td>
              <td>{nombreCaja(t.caja_origen_id)}</td>
              <td>{nombreCaja(t.caja_destino_id)}</td>
              <td>{fmtMoney(t.monto)}</td>
              <td>{t.descripcion}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {modal && (
        <ModalNuevaTransferencia
          cajas={cajas}
          onClose={() => setModal(false)}
          onCreada={() => { setModal(false); cargar(); }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/Transferencias.jsx
git commit -m "feat(frontend): pantalla /transferencias con listado + modal nueva"
```

---

## Task 19: Frontend — Ajustes en `/gastos` y `/gastos-habituales`

**Files:**
- Modify: `frontend/src/screens/Gastos.jsx`
- Modify: `frontend/src/screens/GastosHabituales.jsx`

- [ ] **Step 1: En `Gastos.jsx`**, cargar lista de cajas al montar y mostrar dropdown en el form

En el componente del modal de nuevo/editar gasto (o donde esté el form):
- Sumar state `cajas` y useEffect que llama `listarCajas()`.
- Agregar dropdown "Caja origen" (required) al form, antes de "Forma de pago".
- En la tabla/lista de gastos, sumar columna "Caja" mostrando `nombreCaja(g.caja_id)`.

- [ ] **Step 2: Idem en `GastosHabituales.jsx`** — sumar dropdown caja al form, sumar columna en la lista.

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/Gastos.jsx frontend/src/screens/GastosHabituales.jsx
git commit -m "feat(frontend): dropdown Caja en Gastos y GastosHabituales (form + columna)"
```

---

## Task 20: Frontend — Ajustes en `/comprobantes` y `/liquidaciones`

**Files:**
- Modify: `frontend/src/screens/Comprobantes.jsx`
- Modify: `frontend/src/screens/Liquidaciones.jsx`

- [ ] **Step 1: En `Comprobantes.jsx`**, al aprobar un comprobante, mostrar mini-modal con dropdown "Caja destino"

- Antes del PATCH, abrir un modal `ModalAprobarComprobante` con dropdown de cajas (pre-seleccionado con `configuracion.caja_default_pagos_id` si está disponible).
- El PATCH debe incluir `caja_destino_id` en el body junto con `estado=aprobado`.

- [ ] **Step 2: En `Liquidaciones.jsx`**, sumar dropdown "Caja origen" en el form de nueva liquidación (required).

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/Comprobantes.jsx frontend/src/screens/Liquidaciones.jsx
git commit -m "feat(frontend): caja_destino al aprobar comprobante + caja en liquidación"
```

---

## Task 21: Frontend — Configuración + Sidebar + Routes

**Files:**
- Modify: `frontend/src/screens/Configuracion.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: En `Configuracion.jsx`**, sumar dropdown "Caja default para pagos recibidos" en el fieldset "Vencimientos e intereses" (o crear uno nuevo)

```jsx
<label>
  Caja default para pagos recibidos
  <select
    value={form.caja_default_pagos_id || ""}
    onChange={(e) => setForm({ ...form, caja_default_pagos_id: e.target.value ? Number(e.target.value) : null })}
  >
    <option value="">— Ninguna —</option>
    {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
  </select>
</label>
```

Cargar `cajas` al montar el componente vía `listarCajas()`.

- [ ] **Step 2: En `Sidebar.jsx`**, sumar nueva sección "Tesorería" entre "Expensas y pagos" y "Sueldos"

```javascript
{
  titulo: "Tesorería",
  modulos: [
    { ruta: "/estado-financiero", nombre: "Estado financiero", rolesPermitidos: ["administracion"] },
    { ruta: "/cajas", nombre: "Cajas", rolesPermitidos: ["administracion"] },
    { ruta: "/transferencias", nombre: "Transferencias", rolesPermitidos: ["administracion"] },
  ],
},
```

- [ ] **Step 3: En `App.jsx`**, sumar imports + rutas

```jsx
import EstadoFinanciero from "./screens/EstadoFinanciero";
import Cajas from "./screens/Cajas";
import Transferencias from "./screens/Transferencias";
```

Sumar dentro del `<Route path="/">` group:
```jsx
<Route path="estado-financiero" element={<EstadoFinanciero />} />
<Route path="cajas" element={<Cajas />} />
<Route path="transferencias" element={<Transferencias />} />
```

- [ ] **Step 4: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/Configuracion.jsx frontend/src/components/Sidebar.jsx frontend/src/App.jsx
git commit -m "feat(frontend): Configuración caja default + Sidebar Tesorería + Routes"
```

---

## Task 22: Smoke E2E + merge + roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`

- [ ] **Step 1: Reset DB + arrancar uvicorn + frontend**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
# terminal 1:
.venv\Scripts\python -m uvicorn backend.main:app --reload
# terminal 2:
cd frontend; npm run dev
```

- [ ] **Step 2: Smoke E2E**

1. Login admin → `/estado-financiero` → ver 3 cajas (Banco $0, Caja chica $0, Fondo $0). Total $0.
2. Click "Transferir entre cajas" → transferir $10000 de Banco a Fondo → debería fallar (Banco no tiene fondos) o aceptarlo igual (no validamos descubierto). Probar igual.
3. Ir a `/cajas` → editar Banco Provincia → cargar saldo_inicial $100.000. Saldo actual: $100.000.
4. Click "Ajuste" en Banco → cargar +$5000 con descripción "depósito inicial extra". Saldo Banco: $105.000.
5. Ir a `/gastos` → crear gasto $3000 (forma_pago efectivo) con caja=Caja chica → falla porque Caja chica no tiene saldo (pero igual lo acepta). Saldo Caja chica: -$3000.
6. Volver a `/estado-financiero` → ver: Banco $105.000, Caja chica -$3000, Fondo $0. Total $102.000.
7. Logout. Login depto-a → presentar comprobante por $50.000 con archivo.
8. Logout. Login admin → `/comprobantes` → aprobar el comprobante → modal pide caja destino → seleccionar Banco. Saldo Banco: $155.000.
9. Verificar en `/estado-financiero` los últimos movimientos: deberían aparecer 4-5 movimientos (transferencias, ajuste, egreso, ingreso).
10. Probar cerrar período → bloquear los gastos y transferencias del período cerrado (409).

- [ ] **Step 3: Suite final**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: ~520+ tests passing (481 baseline + ~40 nuevos).

- [ ] **Step 4: Actualizar roadmap** — marcar Fase 5 como ✅

En `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`:

```markdown
| **5** ✅ | **Caja, fondo de reparación, estado financiero** (completada YYYY-MM-DD) | Cajas configurables, transferencias, ajustes manuales, dashboard. |
```

Sumar al historial:
```markdown
- YYYY-MM-DD: **Fase 5 completada** (~520 tests, mergeada a master). Multi-caja sin conciliación; 3 modelos nuevos + 4 campos sumados a modelos existentes; bloqueos cross-recurso ampliados.
```

Actualizar "Próximo paso":
```markdown
Brainstorming de Fase 6 (Reportes Ley 941 + PDF de liquidación).
```

- [ ] **Step 5: Commit roadmap + merge a master**

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 5 completada (tesorería)"

git checkout master
git merge --no-ff feature/expensas-fase5-tesoreria -m "Merge feature/expensas-fase5-tesoreria: caja, transferencias y estado financiero

Fase 5 — Modela las cajas (cuentas financieras) del consorcio. Cada gasto sale
de una caja, cada pago aprobado entra a una caja. Transferencias entre cajas y
ajustes manuales como red de seguridad para descuadres con extracto bancario."
```

- [ ] **Step 6: Done**

---

## Notas finales

- **Orden de tasks razonado:** modelos → schemas+módulo puro → fixtures → routers nuevos → integración en routers existentes → docs → seed → frontend. Mismo patrón Fase 4.
- **TDD:** Task 2 contiene tests unitarios del módulo puro (TDD pleno). Tasks 4-7 sumar tests del router justo después del router (mismo archivo, mismo commit). Tasks 8-11 sumar tests de integración.
- **Commits frecuentes:** cada task termina con su propio commit. ~22 commits totales.
- **Cross-recurso:** los bloqueos por período cerrado se centralizan en helpers locales por router. Si crece, se mueve a `backend/helpers.py`.
- **Migración:** clean start (borrar `consorcio.db`).
