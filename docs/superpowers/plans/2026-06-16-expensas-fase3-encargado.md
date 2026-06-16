# Expensas — Fase 3: encargado y cargas sociales (ampliada) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar gestión completa de empleados (encargados) + catálogos de haberes y conceptos de liquidación + liquidación mensual con cálculo automático de descuentos/contribuciones (snapshot) y generación de N Gastos asociados.

**Architecture:** 5 nuevas tablas (`Empleado`, `Haber`, `ConceptoLiquidacion`, `LiquidacionEmpleado`, `LiquidacionHaber`, `LiquidacionDetalle`) + columna `liquidacion_id` en `Gasto`. 4 routers nuevos (`empleados`, `haberes`, `conceptos_liquidacion`, `liquidaciones`). Frontend con 3 pantallas en Configuración + 1 en Expensas y pagos (tabs `Del mes` / `Historial`).

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + SQLite. React + Vite + React Router. Tests con pytest. Sin nuevas dependencias.

**Spec:** [docs/superpowers/specs/2026-06-16-expensas-fase3-encargado-design.md](../specs/2026-06-16-expensas-fase3-encargado-design.md)

**Errores de validación Pydantic:** convertidos a HTTP 400 por `backend/main.py:67`.

---

## Setup inicial

### Task 0: Branch + estado limpio

- [ ] **Step 1: Verificar estado y crear branch**

Run: `git status && git branch --show-current`
Expected: rama `master`, working tree puede tener `.claude/settings*.json` modificados y `package*.json` untracked (ignorables).

```bash
git checkout -b feature/expensas-fase3
```

- [ ] **Step 2: Borrar `consorcio.db` local si existe**

Detener `uvicorn` si está corriendo. Luego:

Run: `rm -f consorcio.db`
Expected: ningún output.

- [ ] **Step 3: Confirmar baseline verde**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 356 tests passing (post-Fase 2).

---

## Fase A — Backend foundation

### Task 1: Enums y modelos en `backend/models.py`

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Agregar los 3 enums nuevos al bloque de enums (después de `FormaPago`, antes de la primera clase de tabla)**

```python
class CategoriaEmpleado(str, enum.Enum):
    encargado_permanente_con_vivienda = "encargado_permanente_con_vivienda"
    encargado_permanente_sin_vivienda = "encargado_permanente_sin_vivienda"
    encargado_suplente = "encargado_suplente"
    ayudante = "ayudante"


class TipoConcepto(str, enum.Enum):
    descuento = "descuento"
    contribucion = "contribucion"


class TipoHaber(str, enum.Enum):
    monto_fijo = "monto_fijo"
    porcentaje_sobre_basico = "porcentaje_sobre_basico"
    cantidad_x_valor = "cantidad_x_valor"
```

- [ ] **Step 2: Agregar `Empleado` al final del archivo**

```python
class Empleado(Base):
    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuil: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    categoria: Mapped[CategoriaEmpleado] = mapped_column(
        SqlEnum(CategoriaEmpleado, name="categoria_empleado"), nullable=False
    )
    fecha_ingreso: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_egreso: Mapped[date | None] = mapped_column(Date)
    sueldo_basico: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 3: Agregar `Haber` al final del archivo**

```python
class Haber(Base):
    __tablename__ = "haberes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tipo: Mapped[TipoHaber] = mapped_column(SqlEnum(TipoHaber, name="tipo_haber"), nullable=False)
    valor_default: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 4: Agregar `ConceptoLiquidacion` al final del archivo**

```python
class ConceptoLiquidacion(Base):
    __tablename__ = "conceptos_liquidacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    tipo: Mapped[TipoConcepto] = mapped_column(SqlEnum(TipoConcepto, name="tipo_concepto"), nullable=False)
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 5: Agregar `LiquidacionEmpleado` al final del archivo**

```python
class LiquidacionEmpleado(Base):
    __tablename__ = "liquidaciones_empleado"
    __table_args__ = (
        UniqueConstraint("empleado_id", "periodo", name="uq_liquidacion_empleado_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int] = mapped_column(
        ForeignKey("empleados.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodo: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    sueldo_bruto: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    haberes: Mapped[list["LiquidacionHaber"]] = relationship(
        back_populates="liquidacion",
        cascade="all, delete-orphan",
        order_by="LiquidacionHaber.orden",
    )
    detalle: Mapped[list["LiquidacionDetalle"]] = relationship(
        back_populates="liquidacion",
        cascade="all, delete-orphan",
        order_by="LiquidacionDetalle.orden",
    )
```

- [ ] **Step 6: Agregar `LiquidacionHaber` al final del archivo**

```python
class LiquidacionHaber(Base):
    __tablename__ = "liquidaciones_haber"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidacion_id: Mapped[int] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[TipoHaber | None] = mapped_column(
        SqlEnum(TipoHaber, name="tipo_haber"), nullable=True
    )
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    cantidad: Mapped[float | None] = mapped_column(Float, nullable=True)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    liquidacion: Mapped["LiquidacionEmpleado"] = relationship(back_populates="haberes")
```

- [ ] **Step 7: Agregar `LiquidacionDetalle` al final del archivo**

```python
class LiquidacionDetalle(Base):
    __tablename__ = "liquidaciones_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    liquidacion_id: Mapped[int] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concepto_nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    concepto_tipo: Mapped[TipoConcepto] = mapped_column(
        SqlEnum(TipoConcepto, name="tipo_concepto"), nullable=False
    )
    porcentaje_aplicado: Mapped[float] = mapped_column(Float, nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    liquidacion: Mapped["LiquidacionEmpleado"] = relationship(back_populates="detalle")
```

- [ ] **Step 8: Agregar columna `liquidacion_id` al modelo `Gasto` existente**

En la clase `Gasto`, después de `gasto_habitual_id`, agregar:

```python
    liquidacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("liquidaciones_empleado.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 9: Verificar import + suite**

Run:
```
./.venv/Scripts/python.exe -c "from backend.models import CategoriaEmpleado, TipoConcepto, TipoHaber, Empleado, Haber, ConceptoLiquidacion, LiquidacionEmpleado, LiquidacionHaber, LiquidacionDetalle, Gasto; print('OK')"
```
Expected: imprime `OK`.

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 356 tests passing.

- [ ] **Step 10: Commit**

```bash
git add backend/models.py
git commit -m "feat(models): enums + Empleado + Haber + ConceptoLiquidacion + LiquidacionEmpleado/Haber/Detalle + Gasto.liquidacion_id"
```

---

### Task 2: Schemas Pydantic en `backend/schemas.py`

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Actualizar import de `..models`**

En el bloque `from .models import (...)`, agregar (alfabéticamente): `CategoriaEmpleado`, `TipoConcepto`, `TipoHaber`. Quedaría así (mostrando solo las líneas nuevas en contexto):

```python
from .models import (
    CategoriaEmpleado,
    EstadoComprobante,
    EstadoExpensa,
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoReserva,
    EstadoTrabajo,
    FormaPago,
    Rol,
    Rubro,
    TipoConcepto,
    TipoHaber,
)
```

- [ ] **Step 2: Agregar `_CUIL_PATTERN` y schemas de Empleado al final del archivo**

```python
# El CUIL/CUIT comparte el mismo formato XX-XXXXXXXX-X. Reutilizamos el pattern.
_CUIL_PATTERN = _CUIT_PATTERN


class EmpleadoCrear(BaseModel):
    nombre_completo: str = Field(..., min_length=1, max_length=255)
    cuil: str = Field(..., pattern=_CUIL_PATTERN)
    categoria: CategoriaEmpleado
    fecha_ingreso: date
    fecha_egreso: date | None = None
    sueldo_basico: float = Field(..., gt=0)
    proveedor_id: int = Field(..., gt=0)


class EmpleadoActualizar(BaseModel):
    # cuil inmutable
    nombre_completo: str | None = Field(default=None, min_length=1, max_length=255)
    categoria: CategoriaEmpleado | None = None
    fecha_ingreso: date | None = None
    fecha_egreso: date | None = None
    sueldo_basico: float | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    activo: bool | None = None


class EmpleadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_completo: str
    cuil: str
    categoria: CategoriaEmpleado
    fecha_ingreso: date
    fecha_egreso: date | None
    sueldo_basico: float
    proveedor_id: int
    activo: bool
```

- [ ] **Step 3: Agregar schemas de `Haber`**

```python
class HaberCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    tipo: TipoHaber
    valor_default: float = Field(default=0, ge=0)
    orden: int = Field(default=0, ge=0)


class HaberActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: TipoHaber | None = None
    valor_default: float | None = Field(default=None, ge=0)
    orden: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class HaberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoHaber
    valor_default: float
    orden: int
    activo: bool
```

- [ ] **Step 4: Agregar schemas de `ConceptoLiquidacion`**

```python
class ConceptoLiquidacionCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    tipo: TipoConcepto
    porcentaje: float = Field(..., ge=0, le=100)
    proveedor_id: int | None = Field(default=None, gt=0)
    orden: int = Field(default=0, ge=0)


class ConceptoLiquidacionActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: TipoConcepto | None = None
    porcentaje: float | None = Field(default=None, ge=0, le=100)
    proveedor_id: int | None = Field(default=None, gt=0)
    orden: int | None = Field(default=None, ge=0)
    activo: bool | None = None


class ConceptoLiquidacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoConcepto
    porcentaje: float
    proveedor_id: int | None
    orden: int
    activo: bool
```

- [ ] **Step 5: Agregar schemas de `Liquidacion`**

```python
class LiquidacionHaberItem(BaseModel):
    """Item de haber del catálogo a aplicar en la liquidación."""
    haber_id: int = Field(..., gt=0)
    valor_override: float | None = Field(default=None, ge=0)
    cantidad: float | None = Field(default=None, ge=0)


class LiquidacionHaberAdHoc(BaseModel):
    """Haber suelto sin catálogo (ej. SAC)."""
    nombre: str = Field(..., min_length=1, max_length=120)
    monto: float = Field(..., gt=0)


class LiquidacionEmpleadoCrear(BaseModel):
    empleado_id: int = Field(..., gt=0)
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
    haberes: list[LiquidacionHaberItem] = Field(default_factory=list)
    haberes_ad_hoc: list[LiquidacionHaberAdHoc] = Field(default_factory=list)


class LiquidacionEmpleadoActualizar(BaseModel):
    haberes: list[LiquidacionHaberItem] = Field(default_factory=list)
    haberes_ad_hoc: list[LiquidacionHaberAdHoc] = Field(default_factory=list)


class LiquidacionHaberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoHaber | None
    valor: float | None
    cantidad: float | None
    monto: float
    orden: int


class LiquidacionDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    concepto_nombre: str
    concepto_tipo: TipoConcepto
    porcentaje_aplicado: float
    monto: float
    proveedor_id: int | None
    orden: int


class LiquidacionEmpleadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empleado_id: int
    periodo: str
    sueldo_bruto: float
    fecha_creacion: datetime
    haberes: list[LiquidacionHaberOut]
    detalle: list[LiquidacionDetalleOut]
```

- [ ] **Step 6: Verificar imports**

Run:
```
./.venv/Scripts/python.exe -c "from backend.schemas import EmpleadoCrear, EmpleadoActualizar, EmpleadoOut, HaberCrear, HaberActualizar, HaberOut, ConceptoLiquidacionCrear, ConceptoLiquidacionActualizar, ConceptoLiquidacionOut, LiquidacionEmpleadoCrear, LiquidacionEmpleadoActualizar, LiquidacionEmpleadoOut, LiquidacionHaberItem, LiquidacionHaberAdHoc, LiquidacionHaberOut, LiquidacionDetalleOut; print('OK')"
```
Expected: imprime `OK`.

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 356 tests passing.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas.py
git commit -m "feat(schemas): Empleado + Haber + ConceptoLiquidacion + LiquidacionEmpleado y dependientes"
```

---

### Task 3: Extender `tests/conftest.py` con fixtures de Fase 3

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Agregar imports al bloque `from backend.models`**

Sumar (alfabético): `CategoriaEmpleado`, `ConceptoLiquidacion`, `Empleado`, `Haber`, `LiquidacionDetalle`, `LiquidacionEmpleado`, `LiquidacionHaber`, `TipoConcepto`, `TipoHaber`.

- [ ] **Step 2: Sumar al `db.add_all([...])` final del `_seed()` los siguientes objetos, ANTES del `db.commit()`**

```python
            # Fase 3: empleado de ejemplo (id=900)
            Empleado(
                id=900,
                nombre_completo="Test Empleado",
                cuil="20-30000000-3",
                categoria=CategoriaEmpleado.encargado_permanente_sin_vivienda,
                fecha_ingreso=date(2020, 1, 1),
                fecha_egreso=None,
                sueldo_basico=1000000.0,
                proveedor_id=600,  # proveedor sembrado en Fase 1
                activo=True,
            ),
            # Fase 3: dos haberes mínimos
            Haber(
                id=940,
                nombre="Básico Test",
                tipo=TipoHaber.porcentaje_sobre_basico,
                valor_default=100.0,
                orden=1,
                activo=True,
            ),
            Haber(
                id=941,
                nombre="Antigüedad Test",
                tipo=TipoHaber.porcentaje_sobre_basico,
                valor_default=1.0,
                orden=2,
                activo=True,
            ),
            # Fase 3: dos conceptos mínimos
            ConceptoLiquidacion(
                id=950,
                nombre="Jubilación Test",
                tipo=TipoConcepto.descuento,
                porcentaje=11.0,
                proveedor_id=600,
                orden=1,
                activo=True,
            ),
            ConceptoLiquidacion(
                id=951,
                nombre="AFIP Test",
                tipo=TipoConcepto.contribucion,
                porcentaje=16.0,
                proveedor_id=600,
                orden=10,
                activo=True,
            ),
```

> Los conceptos apuntan a `proveedor_id=600` (proveedor genérico de tests). En producción cada concepto apuntaría a AFIP/FATERYH/etc. — pero para los tests con un solo proveedor alcanza.

- [ ] **Step 3: Verificar suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 356 tests passing.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): seed mínimo de Empleado, Haber y ConceptoLiquidacion"
```

---

## Fase B — Routers backend con TDD

### Task 4: Router `empleados` (TDD)

**Files:**
- Create: `tests/test_empleados.py`
- Create: `backend/routers/empleados.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `tests/test_empleados.py`**

```python
from datetime import date


_EMPLEADO_NUEVO = {
    "nombre_completo": "Juan Pérez",
    "cuil": "20-12345678-9",
    "categoria": "encargado_permanente_sin_vivienda",
    "fecha_ingreso": "2024-03-01",
    "fecha_egreso": None,
    "sueldo_basico": 800000,
    "proveedor_id": 600,
}


# ---------------------------------------------------------------------------
# GET /empleados
# ---------------------------------------------------------------------------


def test_listar_empleados_sin_token_devuelve_401(client):
    r = client.get("/empleados")
    assert r.status_code == 401


def test_listar_empleados_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/empleados", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_empleados_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/empleados", headers=headers_admin)
    assert r.status_code == 200
    cuils = {e["cuil"] for e in r.json()}
    assert "20-30000000-3" in cuils


def test_listar_empleados_filtra_activos_por_default(client, headers_admin):
    r = client.get("/empleados", headers=headers_admin)
    assert all(e["activo"] for e in r.json())


def test_listar_empleados_inactivos_via_query(client, headers_admin):
    # Desactivar al empleado del seed.
    client.delete("/empleados/900", headers=headers_admin)

    r = client.get("/empleados?activo=false", headers=headers_admin)
    assert any(e["id"] == 900 for e in r.json())


# ---------------------------------------------------------------------------
# POST /empleados
# ---------------------------------------------------------------------------


def test_crear_empleado_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/empleados", json=_EMPLEADO_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre_completo"] == "Juan Pérez"
    assert body["activo"] is True


def test_crear_empleado_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/empleados", json=_EMPLEADO_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_empleado_cuil_duplicado_devuelve_409(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, cuil="20-30000000-3")
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_empleado_cuil_invalido_devuelve_400(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, cuil="ABC")
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_empleado_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, proveedor_id=9999)
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_empleado_sueldo_cero_devuelve_400(client, headers_admin):
    payload = dict(_EMPLEADO_NUEVO, sueldo_basico=0)
    r = client.post("/empleados", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /empleados/{id}
# ---------------------------------------------------------------------------


def test_obtener_empleado_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/empleados/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_empleado_existente_devuelve_200(client, headers_admin):
    r = client.get("/empleados/900", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["cuil"] == "20-30000000-3"


# ---------------------------------------------------------------------------
# PATCH /empleados/{id}
# ---------------------------------------------------------------------------


def test_patch_empleado_actualiza_sueldo(client, headers_admin):
    r = client.patch("/empleados/900", json={"sueldo_basico": 1500000}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["sueldo_basico"] == 1500000


def test_patch_empleado_cuil_en_body_es_ignorado(client, headers_admin):
    r = client.patch(
        "/empleados/900",
        json={"cuil": "99-99999999-9", "sueldo_basico": 1200000},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["cuil"] == "20-30000000-3"


def test_patch_empleado_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/empleados/9999", json={"sueldo_basico": 1}, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /empleados/{id}
# ---------------------------------------------------------------------------


def test_delete_empleado_sin_liquidaciones_es_hard_delete(client, headers_admin):
    creado = client.post("/empleados", json=_EMPLEADO_NUEVO, headers=headers_admin).json()
    r = client.delete(f"/empleados/{creado['id']}", headers=headers_admin)
    assert r.status_code == 204

    r2 = client.get(f"/empleados/{creado['id']}", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_empleado_con_liquidaciones_es_soft_delete(client, headers_admin, db_session):
    from backend.models import LiquidacionEmpleado as Liq
    db_session.add(Liq(empleado_id=900, periodo="2026-06", sueldo_bruto=1000000))
    db_session.commit()

    r = client.delete("/empleados/900", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    r2 = client.get("/empleados/900", headers=headers_admin)
    assert r2.status_code == 200
    assert r2.json()["activo"] is False


def test_delete_empleado_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/empleados/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr tests para confirmar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_empleados.py -v`
Expected: FAIL en todos (router no existe).

- [ ] **Step 3: Crear `backend/routers/empleados.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Empleado, LiquidacionEmpleado, Proveedor, Rol
from ..schemas import EmpleadoActualizar, EmpleadoCrear, EmpleadoOut

router = APIRouter(prefix="/empleados", tags=["Personal"])


def _validar_proveedor(db: Session, proveedor_id: int) -> None:
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


@router.get(
    "",
    response_model=list[EmpleadoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar empleados",
)
def listar_empleados(
    activo: bool | None = Query(default=True),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Empleado]:
    stmt = select(Empleado).order_by(Empleado.nombre_completo.asc())
    if activo is not None:
        stmt = stmt.where(Empleado.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=EmpleadoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear empleado",
)
def crear_empleado(
    payload: EmpleadoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Empleado:
    duplicado = db.scalar(select(Empleado.id).where(Empleado.cuil == payload.cuil))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un empleado con ese CUIL.",
        )

    _validar_proveedor(db, payload.proveedor_id)

    empleado = Empleado(
        nombre_completo=payload.nombre_completo,
        cuil=payload.cuil,
        categoria=payload.categoria,
        fecha_ingreso=payload.fecha_ingreso,
        fecha_egreso=payload.fecha_egreso,
        sueldo_basico=payload.sueldo_basico,
        proveedor_id=payload.proveedor_id,
        activo=True,
    )
    db.add(empleado)
    db.commit()
    db.refresh(empleado)
    return empleado


@router.get(
    "/{empleado_id}",
    response_model=EmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener empleado",
)
def obtener_empleado(
    empleado_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Empleado:
    empleado = db.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )
    return empleado


@router.patch(
    "/{empleado_id}",
    response_model=EmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar empleado",
)
def actualizar_empleado(
    empleado_id: int,
    payload: EmpleadoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Empleado:
    empleado = db.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    if "proveedor_id" in cambios and cambios["proveedor_id"] is not None:
        _validar_proveedor(db, cambios["proveedor_id"])

    for campo, valor in cambios.items():
        setattr(empleado, campo, valor)

    db.commit()
    db.refresh(empleado)
    return empleado


@router.delete(
    "/{empleado_id}",
    response_model=EmpleadoOut | None,
    status_code=status.HTTP_200_OK,
    summary="Eliminar empleado (hard si no tiene liquidaciones; soft si tiene)",
)
def eliminar_empleado(
    empleado_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    empleado = db.get(Empleado, empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )

    tiene_liquidaciones = (
        db.scalar(
            select(LiquidacionEmpleado.id).where(LiquidacionEmpleado.empleado_id == empleado_id)
        )
        is not None
    )

    if tiene_liquidaciones:
        empleado.activo = False
        db.commit()
        db.refresh(empleado)
        return empleado

    db.delete(empleado)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Registrar router en `backend/main.py`**

Sumar al import alfabético `empleados` y al final de los `include_router` agregar `app.include_router(empleados.router)`.

- [ ] **Step 5: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_empleados.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: tests verdes + suite completa verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_empleados.py backend/routers/empleados.py backend/main.py
git commit -m "feat(empleados): CRUD admin-only con soft/hard delete según liquidaciones"
```

---

### Task 5: Router `haberes` (TDD)

**Files:**
- Create: `tests/test_haberes.py`
- Create: `backend/routers/haberes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `tests/test_haberes.py`**

```python
_HABER_NUEVO = {
    "nombre": "Premio Producción",
    "tipo": "monto_fijo",
    "valor_default": 50000,
    "orden": 99,
}


# ---------------------------------------------------------------------------
# GET /haberes
# ---------------------------------------------------------------------------


def test_listar_haberes_sin_token_devuelve_401(client):
    r = client.get("/haberes")
    assert r.status_code == 401


def test_listar_haberes_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/haberes", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_haberes_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/haberes", headers=headers_admin)
    assert r.status_code == 200
    nombres = {h["nombre"] for h in r.json()}
    assert "Básico Test" in nombres


def test_listar_haberes_ordenados(client, headers_admin):
    r = client.get("/haberes", headers=headers_admin)
    ordenes = [h["orden"] for h in r.json()]
    assert ordenes == sorted(ordenes)


# ---------------------------------------------------------------------------
# POST /haberes
# ---------------------------------------------------------------------------


def test_crear_haber_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/haberes", json=_HABER_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Premio Producción"
    assert body["activo"] is True


def test_crear_haber_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/haberes", json=_HABER_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_haber_nombre_duplicado_devuelve_409(client, headers_admin):
    payload = dict(_HABER_NUEVO, nombre="Básico Test")
    r = client.post("/haberes", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_haber_tipo_invalido_devuelve_400(client, headers_admin):
    payload = dict(_HABER_NUEVO, tipo="invalido")
    r = client.post("/haberes", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_haber_valor_negativo_devuelve_400(client, headers_admin):
    payload = dict(_HABER_NUEVO, valor_default=-10)
    r = client.post("/haberes", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /haberes/{id}
# ---------------------------------------------------------------------------


def test_obtener_haber_existente_devuelve_200(client, headers_admin):
    r = client.get("/haberes/940", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Básico Test"


def test_obtener_haber_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/haberes/9999", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /haberes/{id}
# ---------------------------------------------------------------------------


def test_patch_haber_actualiza_valor(client, headers_admin):
    r = client.patch("/haberes/940", json={"valor_default": 105.0}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["valor_default"] == 105.0


def test_patch_haber_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/haberes/9999", json={"valor_default": 1}, headers=headers_admin)
    assert r.status_code == 404


def test_patch_haber_desactiva(client, headers_admin):
    r = client.patch("/haberes/940", json={"activo": False}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False


# ---------------------------------------------------------------------------
# DELETE /haberes/{id} — soft-delete siempre
# ---------------------------------------------------------------------------


def test_delete_haber_es_soft_delete(client, headers_admin):
    r = client.delete("/haberes/940", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    # Sigue existiendo.
    r2 = client.get("/haberes/940", headers=headers_admin)
    assert r2.status_code == 200


def test_delete_haber_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/haberes/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr tests para confirmar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_haberes.py -v`
Expected: FAIL en todos.

- [ ] **Step 3: Crear `backend/routers/haberes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Haber, Rol
from ..schemas import HaberActualizar, HaberCrear, HaberOut

router = APIRouter(prefix="/haberes", tags=["Personal"])


@router.get(
    "",
    response_model=list[HaberOut],
    status_code=status.HTTP_200_OK,
    summary="Listar haberes (catálogo)",
)
def listar_haberes(
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Haber]:
    stmt = select(Haber).order_by(Haber.orden.asc(), Haber.nombre.asc())
    if activo is not None:
        stmt = stmt.where(Haber.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=HaberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear haber",
)
def crear_haber(
    payload: HaberCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    duplicado = db.scalar(select(Haber.id).where(Haber.nombre == payload.nombre))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un haber con ese nombre.",
        )

    haber = Haber(
        nombre=payload.nombre,
        tipo=payload.tipo,
        valor_default=payload.valor_default,
        orden=payload.orden,
        activo=True,
    )
    db.add(haber)
    db.commit()
    db.refresh(haber)
    return haber


@router.get(
    "/{haber_id}",
    response_model=HaberOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener haber",
)
def obtener_haber(
    haber_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    haber = db.get(Haber, haber_id)
    if haber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El haber solicitado no existe.",
        )
    return haber


@router.patch(
    "/{haber_id}",
    response_model=HaberOut,
    status_code=status.HTTP_200_OK,
    summary="Editar haber",
)
def actualizar_haber(
    haber_id: int,
    payload: HaberActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    haber = db.get(Haber, haber_id)
    if haber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El haber solicitado no existe.",
        )

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(haber, campo, valor)

    db.commit()
    db.refresh(haber)
    return haber


@router.delete(
    "/{haber_id}",
    response_model=HaberOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar haber (soft-delete)",
)
def eliminar_haber(
    haber_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Haber:
    haber = db.get(Haber, haber_id)
    if haber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El haber solicitado no existe.",
        )

    haber.activo = False
    db.commit()
    db.refresh(haber)
    return haber
```

- [ ] **Step 4: Registrar router en `backend/main.py`**

Sumar `haberes` al import alfabético y `app.include_router(haberes.router)` después del último include.

- [ ] **Step 5: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_haberes.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_haberes.py backend/routers/haberes.py backend/main.py
git commit -m "feat(haberes): CRUD admin-only con soft-delete"
```

---

### Task 6: Router `conceptos_liquidacion` (TDD)

**Files:**
- Create: `tests/test_conceptos_liquidacion.py`
- Create: `backend/routers/conceptos_liquidacion.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `tests/test_conceptos_liquidacion.py`**

```python
_CONCEPTO_NUEVO = {
    "nombre": "FATERYH Test",
    "tipo": "contribucion",
    "porcentaje": 8.535,
    "proveedor_id": 600,
    "orden": 20,
}


# ---------------------------------------------------------------------------
# GET /conceptos-liquidacion
# ---------------------------------------------------------------------------


def test_listar_conceptos_sin_token_devuelve_401(client):
    r = client.get("/conceptos-liquidacion")
    assert r.status_code == 401


def test_listar_conceptos_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/conceptos-liquidacion", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_conceptos_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/conceptos-liquidacion", headers=headers_admin)
    assert r.status_code == 200
    nombres = {c["nombre"] for c in r.json()}
    assert "Jubilación Test" in nombres


# ---------------------------------------------------------------------------
# POST /conceptos-liquidacion
# ---------------------------------------------------------------------------


def test_crear_concepto_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/conceptos-liquidacion", json=_CONCEPTO_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["nombre"] == "FATERYH Test"


def test_crear_concepto_nombre_duplicado_devuelve_409(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, nombre="Jubilación Test")
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_concepto_porcentaje_fuera_de_rango_devuelve_400(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, porcentaje=150)
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_concepto_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, proveedor_id=9999)
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_concepto_sin_proveedor_es_201(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, proveedor_id=None)
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["proveedor_id"] is None


# ---------------------------------------------------------------------------
# PATCH, DELETE
# ---------------------------------------------------------------------------


def test_patch_concepto_actualiza_porcentaje(client, headers_admin):
    r = client.patch("/conceptos-liquidacion/950", json={"porcentaje": 12.0}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["porcentaje"] == 12.0


def test_patch_concepto_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/conceptos-liquidacion/9999", json={"porcentaje": 1}, headers=headers_admin)
    assert r.status_code == 404


def test_delete_concepto_es_soft_delete(client, headers_admin):
    r = client.delete("/conceptos-liquidacion/950", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False


def test_delete_concepto_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/conceptos-liquidacion/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr tests para confirmar fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_conceptos_liquidacion.py -v`
Expected: FAIL.

- [ ] **Step 3: Crear `backend/routers/conceptos_liquidacion.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import ConceptoLiquidacion, Proveedor, Rol
from ..schemas import (
    ConceptoLiquidacionActualizar,
    ConceptoLiquidacionCrear,
    ConceptoLiquidacionOut,
)

router = APIRouter(prefix="/conceptos-liquidacion", tags=["Personal"])


def _validar_proveedor(db: Session, proveedor_id: int | None) -> None:
    if proveedor_id is None:
        return
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


@router.get(
    "",
    response_model=list[ConceptoLiquidacionOut],
    status_code=status.HTTP_200_OK,
    summary="Listar conceptos de liquidación",
)
def listar_conceptos(
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[ConceptoLiquidacion]:
    stmt = select(ConceptoLiquidacion).order_by(
        ConceptoLiquidacion.orden.asc(), ConceptoLiquidacion.nombre.asc()
    )
    if activo is not None:
        stmt = stmt.where(ConceptoLiquidacion.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear concepto",
)
def crear_concepto(
    payload: ConceptoLiquidacionCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ConceptoLiquidacion:
    duplicado = db.scalar(
        select(ConceptoLiquidacion.id).where(ConceptoLiquidacion.nombre == payload.nombre)
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un concepto con ese nombre.",
        )

    _validar_proveedor(db, payload.proveedor_id)

    concepto = ConceptoLiquidacion(
        nombre=payload.nombre,
        tipo=payload.tipo,
        porcentaje=payload.porcentaje,
        proveedor_id=payload.proveedor_id,
        orden=payload.orden,
        activo=True,
    )
    db.add(concepto)
    db.commit()
    db.refresh(concepto)
    return concepto


@router.get(
    "/{concepto_id}",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener concepto",
)
def obtener_concepto(
    concepto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ConceptoLiquidacion:
    concepto = db.get(ConceptoLiquidacion, concepto_id)
    if concepto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El concepto solicitado no existe.",
        )
    return concepto


@router.patch(
    "/{concepto_id}",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_200_OK,
    summary="Editar concepto",
)
def actualizar_concepto(
    concepto_id: int,
    payload: ConceptoLiquidacionActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ConceptoLiquidacion:
    concepto = db.get(ConceptoLiquidacion, concepto_id)
    if concepto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El concepto solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    if "proveedor_id" in cambios:
        _validar_proveedor(db, cambios["proveedor_id"])

    for campo, valor in cambios.items():
        setattr(concepto, campo, valor)

    db.commit()
    db.refresh(concepto)
    return concepto


@router.delete(
    "/{concepto_id}",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar concepto (soft-delete)",
)
def eliminar_concepto(
    concepto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ConceptoLiquidacion:
    concepto = db.get(ConceptoLiquidacion, concepto_id)
    if concepto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El concepto solicitado no existe.",
        )

    concepto.activo = False
    db.commit()
    db.refresh(concepto)
    return concepto
```

- [ ] **Step 4: Registrar router en `backend/main.py`**

Sumar `conceptos_liquidacion` al import alfabético y `app.include_router(conceptos_liquidacion.router)`.

- [ ] **Step 5: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_conceptos_liquidacion.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_conceptos_liquidacion.py backend/routers/conceptos_liquidacion.py backend/main.py
git commit -m "feat(conceptos-liquidacion): CRUD admin-only con proveedor opcional y soft-delete"
```

---

### Task 7: Router `liquidaciones` con cálculo y generación de Gastos (TDD)

**Files:**
- Create: `tests/test_liquidaciones.py`
- Create: `backend/routers/liquidaciones.py`
- Modify: `backend/main.py`

> Esta es la pieza más compleja del backend. El router calcula bruto desde haberes, aplica conceptos, hace snapshot, y genera N Gastos. La validación se cubre por test.

- [ ] **Step 1: Crear `tests/test_liquidaciones.py`**

```python
from datetime import date


def _payload_basico():
    """Liquidación con 2 haberes simples y los conceptos del seed."""
    return {
        "empleado_id": 900,
        "periodo": "2026-07",
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},  # Básico 100% → $1.000.000
            {"haber_id": 941, "valor_override": 12.0, "cantidad": None},  # Antigüedad 12% → $120.000
        ],
        "haberes_ad_hoc": [],
    }


# ---------------------------------------------------------------------------
# GET /liquidaciones
# ---------------------------------------------------------------------------


def test_listar_liquidaciones_sin_token_devuelve_401(client):
    r = client.get("/liquidaciones")
    assert r.status_code == 401


def test_listar_liquidaciones_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/liquidaciones", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_liquidaciones_vacio_inicialmente(client, headers_admin):
    r = client.get("/liquidaciones", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# POST /liquidaciones — happy path
# ---------------------------------------------------------------------------


def test_crear_liquidacion_calcula_bruto_correctamente(client, headers_admin):
    # Empleado seed tiene sueldo_basico=1.000.000.
    # Básico = 100% × 1.000.000 = 1.000.000
    # Antigüedad = 12% × 1.000.000 = 120.000
    # Bruto = 1.120.000
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["sueldo_bruto"] == 1120000
    assert len(body["haberes"]) == 2
    assert body["haberes"][0]["nombre"] == "Básico Test"
    assert body["haberes"][0]["monto"] == 1000000
    assert body["haberes"][1]["nombre"] == "Antigüedad Test"
    assert body["haberes"][1]["monto"] == 120000


def test_crear_liquidacion_aplica_conceptos_sobre_bruto(client, headers_admin):
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    body = r.json()
    # Conceptos seed: Jubilación 11% descuento + AFIP 16% contribución.
    # Sobre bruto 1.120.000: jubilación = 123.200, AFIP = 179.200.
    detalle = {d["concepto_nombre"]: d for d in body["detalle"]}
    assert detalle["Jubilación Test"]["monto"] == 123200
    assert detalle["Jubilación Test"]["concepto_tipo"] == "descuento"
    assert detalle["AFIP Test"]["monto"] == 179200
    assert detalle["AFIP Test"]["concepto_tipo"] == "contribucion"


def test_crear_liquidacion_haberes_ad_hoc(client, headers_admin):
    payload = _payload_basico()
    payload["haberes_ad_hoc"] = [{"nombre": "SAC", "monto": 500000}]
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    # Bruto = 1.000.000 + 120.000 + 500.000 = 1.620.000.
    assert body["sueldo_bruto"] == 1620000
    nombres = {h["nombre"] for h in body["haberes"]}
    assert "SAC" in nombres


def test_crear_liquidacion_haber_cantidad_x_valor(client, headers_admin):
    # Crear un haber de tipo cantidad_x_valor.
    nuevo_haber = client.post(
        "/haberes",
        json={"nombre": "HE 50 Test", "tipo": "cantidad_x_valor", "valor_default": 5000, "orden": 5},
        headers=headers_admin,
    ).json()

    payload = {
        "empleado_id": 900,
        "periodo": "2026-07",
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},  # Básico
            {"haber_id": nuevo_haber["id"], "valor_override": None, "cantidad": 10},  # 10 × 5000
        ],
        "haberes_ad_hoc": [],
    }
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    # Básico 1M + HE 10*5000 = 1.050.000.
    assert body["sueldo_bruto"] == 1050000


def test_crear_liquidacion_genera_gastos_asociados(client, headers_admin):
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    liq_id = r.json()["id"]

    rg = client.get(f"/gastos?gasto_habitual_id=&periodo=2026-07", headers=headers_admin)
    # Filtramos manualmente por liquidacion_id mirando todos los gastos del período.
    todos = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    gastos_liq = [g for g in todos if g.get("liquidacion_id") == liq_id]
    assert len(gastos_liq) >= 2  # sueldo neto + al menos 1 por proveedor
    assert all(g["rubro"] == "sueldos_y_cargas_sociales" for g in gastos_liq)


def test_crear_liquidacion_duplicada_devuelve_409(client, headers_admin):
    client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    r = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)
    assert r.status_code == 409


def test_crear_liquidacion_empleado_inexistente_devuelve_404(client, headers_admin):
    payload = _payload_basico()
    payload["empleado_id"] = 9999
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_liquidacion_haber_inexistente_devuelve_404(client, headers_admin):
    payload = _payload_basico()
    payload["haberes"][0]["haber_id"] = 9999
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_liquidacion_periodo_invalido_devuelve_400(client, headers_admin):
    payload = _payload_basico()
    payload["periodo"] = "abc"
    r = client.post("/liquidaciones", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Snapshot: cambiar % de concepto NO afecta liquidaciones pasadas
# ---------------------------------------------------------------------------


def test_snapshot_concepto_no_se_modifica_retroactivamente(client, headers_admin):
    client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin)

    # Cambiar el % de Jubilación de 11 a 50.
    client.patch("/conceptos-liquidacion/950", json={"porcentaje": 50.0}, headers=headers_admin)

    # La liquidación anterior conserva el % original.
    todas = client.get("/liquidaciones", headers=headers_admin).json()
    detalle = {d["concepto_nombre"]: d for d in todas[0]["detalle"]}
    assert detalle["Jubilación Test"]["porcentaje_aplicado"] == 11.0


# ---------------------------------------------------------------------------
# PATCH /liquidaciones/{id}
# ---------------------------------------------------------------------------


def test_patch_liquidacion_recalcula_bruto(client, headers_admin):
    creada = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin).json()

    # Cambiar antigüedad de 12% a 20%.
    nuevo = {
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},
            {"haber_id": 941, "valor_override": 20.0, "cantidad": None},
        ],
        "haberes_ad_hoc": [],
    }
    r = client.patch(f"/liquidaciones/{creada['id']}", json=nuevo, headers=headers_admin)
    assert r.status_code == 200
    # Bruto = 1.000.000 + 200.000 = 1.200.000.
    assert r.json()["sueldo_bruto"] == 1200000


def test_patch_liquidacion_regenera_gastos(client, headers_admin):
    creada = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin).json()

    # Contar gastos pre-PATCH.
    pre = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    pre_count = len([g for g in pre if g.get("liquidacion_id") == creada["id"]])
    assert pre_count > 0

    # PATCH cambia los haberes.
    nuevo = {
        "haberes": [
            {"haber_id": 940, "valor_override": None, "cantidad": None},
            {"haber_id": 941, "valor_override": 50.0, "cantidad": None},
        ],
        "haberes_ad_hoc": [],
    }
    client.patch(f"/liquidaciones/{creada['id']}", json=nuevo, headers=headers_admin)

    # Verificar que los gastos siguen existiendo (regenerados, mismo total de filas).
    post = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    post_count = len([g for g in post if g.get("liquidacion_id") == creada["id"]])
    assert post_count == pre_count


# ---------------------------------------------------------------------------
# DELETE /liquidaciones/{id}
# ---------------------------------------------------------------------------


def test_delete_liquidacion_cascada_borra_haberes_detalle_y_gastos(client, headers_admin):
    creada = client.post("/liquidaciones", json=_payload_basico(), headers=headers_admin).json()

    r = client.delete(f"/liquidaciones/{creada['id']}", headers=headers_admin)
    assert r.status_code == 204

    # Liquidación no existe.
    r2 = client.get(f"/liquidaciones/{creada['id']}", headers=headers_admin)
    assert r2.status_code == 404

    # Gastos asociados ya no aparecen con ese liquidacion_id.
    todos = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    assert not any(g.get("liquidacion_id") == creada["id"] for g in todos)


def test_delete_liquidacion_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/liquidaciones/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr tests para confirmar fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_liquidaciones.py -v`
Expected: FAIL en todos.

- [ ] **Step 3: Crear `backend/routers/liquidaciones.py`**

```python
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    ClaseProrrateo,
    ConceptoLiquidacion,
    Empleado,
    FormaPago,
    Gasto,
    Haber,
    LiquidacionDetalle,
    LiquidacionEmpleado,
    LiquidacionHaber,
    Rol,
    Rubro,
    TipoConcepto,
    TipoHaber,
)
from ..schemas import (
    LiquidacionEmpleadoActualizar,
    LiquidacionEmpleadoCrear,
    LiquidacionEmpleadoOut,
)

router = APIRouter(prefix="/liquidaciones", tags=["Personal"])


def _clase_default(db: Session) -> int:
    """Primera clase de prorrateo activa por id. Decisión MVP — Fase 4 puede configurarla."""
    cid = db.scalar(
        select(ClaseProrrateo.id)
        .where(ClaseProrrateo.activa == True)  # noqa: E712
        .order_by(ClaseProrrateo.id.asc())
    )
    if cid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay clases de prorrateo activas. Cargá al menos una antes de liquidar.",
        )
    return cid


def _resolver_haberes(
    db: Session,
    empleado: Empleado,
    haberes_input: list,
    haberes_ad_hoc: list,
) -> list[LiquidacionHaber]:
    """Convierte los items del payload en filas LiquidacionHaber con monto calculado."""
    snapshots: list[LiquidacionHaber] = []
    orden = 0

    for item in haberes_input:
        haber = db.get(Haber, item.haber_id)
        if haber is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El haber id={item.haber_id} no existe.",
            )

        if haber.tipo == TipoHaber.monto_fijo:
            valor = item.valor_override if item.valor_override is not None else haber.valor_default
            monto = valor
            cantidad = None
        elif haber.tipo == TipoHaber.porcentaje_sobre_basico:
            valor = item.valor_override if item.valor_override is not None else haber.valor_default
            monto = empleado.sueldo_basico * valor / 100
            cantidad = None
        elif haber.tipo == TipoHaber.cantidad_x_valor:
            valor = item.valor_override if item.valor_override is not None else haber.valor_default
            if item.cantidad is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El haber '{haber.nombre}' requiere `cantidad`.",
                )
            cantidad = item.cantidad
            monto = cantidad * valor
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de haber desconocido: {haber.tipo}",
            )

        snapshots.append(
            LiquidacionHaber(
                nombre=haber.nombre,
                tipo=haber.tipo,
                valor=valor,
                cantidad=cantidad,
                monto=monto,
                orden=orden,
            )
        )
        orden += 1

    for ad_hoc in haberes_ad_hoc:
        snapshots.append(
            LiquidacionHaber(
                nombre=ad_hoc.nombre,
                tipo=None,
                valor=None,
                cantidad=None,
                monto=ad_hoc.monto,
                orden=orden,
            )
        )
        orden += 1

    return snapshots


def _aplicar_conceptos(db: Session, sueldo_bruto: float) -> list[LiquidacionDetalle]:
    """Calcula los descuentos y contribuciones aplicables al bruto."""
    conceptos = db.scalars(
        select(ConceptoLiquidacion)
        .where(ConceptoLiquidacion.activo == True)  # noqa: E712
        .order_by(ConceptoLiquidacion.orden.asc(), ConceptoLiquidacion.nombre.asc())
    ).all()

    return [
        LiquidacionDetalle(
            concepto_nombre=c.nombre,
            concepto_tipo=c.tipo,
            porcentaje_aplicado=c.porcentaje,
            monto=sueldo_bruto * c.porcentaje / 100,
            proveedor_id=c.proveedor_id,
            orden=c.orden,
        )
        for c in conceptos
    ]


def _generar_gastos(
    db: Session,
    liquidacion: LiquidacionEmpleado,
    empleado: Empleado,
    clase_id: int,
) -> None:
    """Crea N Gastos: uno al empleado por el sueldo neto, uno por proveedor único."""
    anio, mes = map(int, liquidacion.periodo.split("-"))
    fecha_pago = date(anio, mes, 1)

    descuentos_total = sum(
        d.monto for d in liquidacion.detalle if d.concepto_tipo == TipoConcepto.descuento
    )
    sueldo_neto = liquidacion.sueldo_bruto - descuentos_total

    # 1) Sueldo neto al empleado
    db.add(
        Gasto(
            periodo=liquidacion.periodo,
            rubro=Rubro.sueldos_y_cargas_sociales,
            clase_prorrateo_id=clase_id,
            proveedor_id=empleado.proveedor_id,
            concepto=f"Sueldo neto - {empleado.nombre_completo}",
            monto=sueldo_neto,
            forma_pago=FormaPago.transferencia,
            fecha_pago=fecha_pago,
            liquidacion_id=liquidacion.id,
        )
    )

    # 2) Un gasto por proveedor (agrupa los detalles)
    por_proveedor: dict[int, list[LiquidacionDetalle]] = defaultdict(list)
    for d in liquidacion.detalle:
        if d.proveedor_id is not None:
            por_proveedor[d.proveedor_id].append(d)

    for proveedor_id, items in por_proveedor.items():
        nombres = ", ".join(d.concepto_nombre for d in items)
        total = sum(d.monto for d in items)
        db.add(
            Gasto(
                periodo=liquidacion.periodo,
                rubro=Rubro.sueldos_y_cargas_sociales,
                clase_prorrateo_id=clase_id,
                proveedor_id=proveedor_id,
                concepto=nombres,
                monto=total,
                forma_pago=FormaPago.transferencia,
                fecha_pago=fecha_pago,
                liquidacion_id=liquidacion.id,
            )
        )


def _calcular_y_guardar(
    db: Session,
    liquidacion: LiquidacionEmpleado,
    empleado: Empleado,
    payload: LiquidacionEmpleadoCrear | LiquidacionEmpleadoActualizar,
) -> None:
    """Centraliza el cálculo (POST y PATCH lo usan)."""
    haberes_snap = _resolver_haberes(db, empleado, payload.haberes, payload.haberes_ad_hoc)
    liquidacion.haberes = haberes_snap
    liquidacion.sueldo_bruto = sum(h.monto for h in haberes_snap)
    liquidacion.detalle = _aplicar_conceptos(db, liquidacion.sueldo_bruto)


def _eager_load_liquidacion(db: Session, liquidacion_id: int) -> LiquidacionEmpleado | None:
    """Recarga la liquidación con haberes y detalle eager-loaded."""
    return db.get(LiquidacionEmpleado, liquidacion_id)


@router.get(
    "",
    response_model=list[LiquidacionEmpleadoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar liquidaciones",
)
def listar_liquidaciones(
    periodo: str | None = Query(default=None),
    empleado_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[LiquidacionEmpleado]:
    stmt = select(LiquidacionEmpleado).order_by(
        LiquidacionEmpleado.periodo.desc(), LiquidacionEmpleado.id.desc()
    )
    if periodo is not None:
        stmt = stmt.where(LiquidacionEmpleado.periodo == periodo)
    if empleado_id is not None:
        stmt = stmt.where(LiquidacionEmpleado.empleado_id == empleado_id)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=LiquidacionEmpleadoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear liquidación con cálculo automático",
)
def crear_liquidacion(
    payload: LiquidacionEmpleadoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> LiquidacionEmpleado:
    empleado = db.get(Empleado, payload.empleado_id)
    if empleado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )

    duplicada = db.scalar(
        select(LiquidacionEmpleado.id).where(
            LiquidacionEmpleado.empleado_id == payload.empleado_id,
            LiquidacionEmpleado.periodo == payload.periodo,
        )
    )
    if duplicada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una liquidación para ese empleado en ese período.",
        )

    clase_id = _clase_default(db)

    liquidacion = LiquidacionEmpleado(
        empleado_id=empleado.id,
        periodo=payload.periodo,
        sueldo_bruto=0,
    )
    db.add(liquidacion)
    db.flush()

    _calcular_y_guardar(db, liquidacion, empleado, payload)
    db.flush()
    _generar_gastos(db, liquidacion, empleado, clase_id)

    db.commit()
    db.refresh(liquidacion)
    return liquidacion


@router.get(
    "/{liquidacion_id}",
    response_model=LiquidacionEmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener liquidación",
)
def obtener_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> LiquidacionEmpleado:
    liq = db.get(LiquidacionEmpleado, liquidacion_id)
    if liq is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La liquidación solicitada no existe.",
        )
    return liq


@router.patch(
    "/{liquidacion_id}",
    response_model=LiquidacionEmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar liquidación (recálcula y regenera gastos)",
)
def actualizar_liquidacion(
    liquidacion_id: int,
    payload: LiquidacionEmpleadoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> LiquidacionEmpleado:
    liq = db.get(LiquidacionEmpleado, liquidacion_id)
    if liq is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La liquidación solicitada no existe.",
        )

    empleado = db.get(Empleado, liq.empleado_id)
    clase_id = _clase_default(db)

    # Borrar gastos viejos asociados.
    db.query(Gasto).filter(Gasto.liquidacion_id == liq.id).delete(synchronize_session=False)

    _calcular_y_guardar(db, liq, empleado, payload)
    db.flush()
    _generar_gastos(db, liq, empleado, clase_id)

    db.commit()
    db.refresh(liq)
    return liq


@router.delete(
    "/{liquidacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar liquidación (cascade haberes/detalle + gastos asociados)",
)
def eliminar_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Response:
    liq = db.get(LiquidacionEmpleado, liquidacion_id)
    if liq is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La liquidación solicitada no existe.",
        )

    # Borrar gastos asociados manualmente (FK SET NULL no los elimina).
    db.query(Gasto).filter(Gasto.liquidacion_id == liq.id).delete(synchronize_session=False)
    db.delete(liq)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Registrar router en `backend/main.py`**

Sumar `liquidaciones` al import alfabético y `app.include_router(liquidaciones.router)` después del último include.

- [ ] **Step 5: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_liquidaciones.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_liquidaciones.py backend/routers/liquidaciones.py backend/main.py
git commit -m "feat(liquidaciones): cálculo automático con snapshot + generación de N Gastos por liquidación"
```

---

## Fase C — OpenAPI

### Task 8: Documentar endpoints nuevos en `openapi.yaml`

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Agregar tag "Personal" si no existe en la sección `tags:`**

```yaml
  - name: Personal
    description: Empleados, haberes, conceptos de liquidación y liquidaciones mensuales
```

- [ ] **Step 2: Agregar paths nuevos antes del bloque `# COMPONENTS`**

> Por el volumen, se agregan los 4 grupos de paths en bloque. Cada uno con los mismos response refs estándar (`NoAutenticado`, `AccesoDenegado`, `NoEncontrado`, `PedidoInvalido`) que ya existen en `components.responses`.

Insertar este YAML completo:

```yaml
  /empleados:
    get:
      tags: [Personal]
      summary: Listar empleados (admin)
      security: [{ bearerAuth: [] }]
      parameters:
        - in: query
          name: activo
          required: false
          schema: { type: boolean, default: true }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { type: array, items: { $ref: '#/components/schemas/EmpleadoOut' } }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
    post:
      tags: [Personal]
      summary: Crear empleado
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/EmpleadoCrear' }
      responses:
        '201':
          description: Creado
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EmpleadoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
        '409':
          description: CUIL duplicado.
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }

  /empleados/{empleado_id}:
    parameters:
      - in: path
        name: empleado_id
        required: true
        schema: { type: integer }
    get:
      tags: [Personal]
      summary: Obtener empleado
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EmpleadoOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Personal]
      summary: Editar empleado
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/EmpleadoActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EmpleadoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Personal]
      summary: Eliminar empleado (soft si tiene liquidaciones)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: Soft-delete
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EmpleadoOut' }
        '204': { description: Hard-delete }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /haberes:
    get:
      tags: [Personal]
      summary: Listar haberes (catálogo)
      security: [{ bearerAuth: [] }]
      parameters:
        - in: query
          name: activo
          required: false
          schema: { type: boolean }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { type: array, items: { $ref: '#/components/schemas/HaberOut' } }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
    post:
      tags: [Personal]
      summary: Crear haber
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/HaberCrear' }
      responses:
        '201':
          description: Creado
          content:
            application/json:
              schema: { $ref: '#/components/schemas/HaberOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '409':
          description: Nombre duplicado.
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }

  /haberes/{haber_id}:
    parameters:
      - in: path
        name: haber_id
        required: true
        schema: { type: integer }
    get:
      tags: [Personal]
      summary: Obtener haber
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/HaberOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Personal]
      summary: Editar haber
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/HaberActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/HaberOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Personal]
      summary: Desactivar haber (soft-delete)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/HaberOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /conceptos-liquidacion:
    get:
      tags: [Personal]
      summary: Listar conceptos de liquidación
      security: [{ bearerAuth: [] }]
      parameters:
        - in: query
          name: activo
          required: false
          schema: { type: boolean }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { type: array, items: { $ref: '#/components/schemas/ConceptoLiquidacionOut' } }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
    post:
      tags: [Personal]
      summary: Crear concepto
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ConceptoLiquidacionCrear' }
      responses:
        '201':
          description: Creado
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConceptoLiquidacionOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
        '409':
          description: Nombre duplicado.
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }

  /conceptos-liquidacion/{concepto_id}:
    parameters:
      - in: path
        name: concepto_id
        required: true
        schema: { type: integer }
    get:
      tags: [Personal]
      summary: Obtener concepto
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConceptoLiquidacionOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Personal]
      summary: Editar concepto
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ConceptoLiquidacionActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConceptoLiquidacionOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Personal]
      summary: Desactivar concepto (soft-delete)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConceptoLiquidacionOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /liquidaciones:
    get:
      tags: [Personal]
      summary: Listar liquidaciones
      security: [{ bearerAuth: [] }]
      parameters:
        - in: query
          name: periodo
          required: false
          schema: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        - in: query
          name: empleado_id
          required: false
          schema: { type: integer, minimum: 1 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { type: array, items: { $ref: '#/components/schemas/LiquidacionEmpleadoOut' } }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
    post:
      tags: [Personal]
      summary: Crear liquidación (calcula bruto + descuentos + contribuciones + genera Gastos)
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/LiquidacionEmpleadoCrear' }
      responses:
        '201':
          description: Creada
          content:
            application/json:
              schema: { $ref: '#/components/schemas/LiquidacionEmpleadoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
        '409':
          description: Ya existe liquidación para ese empleado en ese período.
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }

  /liquidaciones/{liquidacion_id}:
    parameters:
      - in: path
        name: liquidacion_id
        required: true
        schema: { type: integer }
    get:
      tags: [Personal]
      summary: Obtener liquidación con haberes y detalle
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/LiquidacionEmpleadoOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Personal]
      summary: Editar liquidación (recálcula y regenera Gastos)
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/LiquidacionEmpleadoActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/LiquidacionEmpleadoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Personal]
      summary: Eliminar liquidación (cascade borra haberes/detalle/gastos)
      security: [{ bearerAuth: [] }]
      responses:
        '204': { description: Eliminada }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
```

- [ ] **Step 3: Agregar schemas al final de `openapi.yaml`**

Append este bloque al final:

```yaml

    EmpleadoOut:
      type: object
      required: [id, nombre_completo, cuil, categoria, fecha_ingreso, sueldo_basico, proveedor_id, activo]
      properties:
        id: { type: integer }
        nombre_completo: { type: string }
        cuil: { type: string }
        categoria:
          type: string
          enum: [encargado_permanente_con_vivienda, encargado_permanente_sin_vivienda, encargado_suplente, ayudante]
        fecha_ingreso: { type: string, format: date }
        fecha_egreso: { type: string, format: date, nullable: true }
        sueldo_basico: { type: number, exclusiveMinimum: 0 }
        proveedor_id: { type: integer }
        activo: { type: boolean }

    EmpleadoCrear:
      type: object
      required: [nombre_completo, cuil, categoria, fecha_ingreso, sueldo_basico, proveedor_id]
      properties:
        nombre_completo: { type: string, minLength: 1, maxLength: 255 }
        cuil: { type: string, pattern: '^\d{2}-\d{8}-\d{1}$' }
        categoria:
          type: string
          enum: [encargado_permanente_con_vivienda, encargado_permanente_sin_vivienda, encargado_suplente, ayudante]
        fecha_ingreso: { type: string, format: date }
        fecha_egreso: { type: string, format: date, nullable: true }
        sueldo_basico: { type: number, exclusiveMinimum: 0 }
        proveedor_id: { type: integer, minimum: 1 }

    EmpleadoActualizar:
      type: object
      properties:
        nombre_completo: { type: string, minLength: 1, maxLength: 255, nullable: true }
        categoria:
          type: string
          enum: [encargado_permanente_con_vivienda, encargado_permanente_sin_vivienda, encargado_suplente, ayudante]
          nullable: true
        fecha_ingreso: { type: string, format: date, nullable: true }
        fecha_egreso: { type: string, format: date, nullable: true }
        sueldo_basico: { type: number, exclusiveMinimum: 0, nullable: true }
        proveedor_id: { type: integer, minimum: 1, nullable: true }
        activo: { type: boolean, nullable: true }

    HaberOut:
      type: object
      required: [id, nombre, tipo, valor_default, orden, activo]
      properties:
        id: { type: integer }
        nombre: { type: string }
        tipo: { type: string, enum: [monto_fijo, porcentaje_sobre_basico, cantidad_x_valor] }
        valor_default: { type: number, minimum: 0 }
        orden: { type: integer, minimum: 0 }
        activo: { type: boolean }

    HaberCrear:
      type: object
      required: [nombre, tipo]
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120 }
        tipo: { type: string, enum: [monto_fijo, porcentaje_sobre_basico, cantidad_x_valor] }
        valor_default: { type: number, minimum: 0, default: 0 }
        orden: { type: integer, minimum: 0, default: 0 }

    HaberActualizar:
      type: object
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120, nullable: true }
        tipo:
          type: string
          enum: [monto_fijo, porcentaje_sobre_basico, cantidad_x_valor]
          nullable: true
        valor_default: { type: number, minimum: 0, nullable: true }
        orden: { type: integer, minimum: 0, nullable: true }
        activo: { type: boolean, nullable: true }

    ConceptoLiquidacionOut:
      type: object
      required: [id, nombre, tipo, porcentaje, orden, activo]
      properties:
        id: { type: integer }
        nombre: { type: string }
        tipo: { type: string, enum: [descuento, contribucion] }
        porcentaje: { type: number, minimum: 0, maximum: 100 }
        proveedor_id: { type: integer, nullable: true }
        orden: { type: integer, minimum: 0 }
        activo: { type: boolean }

    ConceptoLiquidacionCrear:
      type: object
      required: [nombre, tipo, porcentaje]
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120 }
        tipo: { type: string, enum: [descuento, contribucion] }
        porcentaje: { type: number, minimum: 0, maximum: 100 }
        proveedor_id: { type: integer, minimum: 1, nullable: true }
        orden: { type: integer, minimum: 0, default: 0 }

    ConceptoLiquidacionActualizar:
      type: object
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120, nullable: true }
        tipo: { type: string, enum: [descuento, contribucion], nullable: true }
        porcentaje: { type: number, minimum: 0, maximum: 100, nullable: true }
        proveedor_id: { type: integer, minimum: 1, nullable: true }
        orden: { type: integer, minimum: 0, nullable: true }
        activo: { type: boolean, nullable: true }

    LiquidacionHaberItem:
      type: object
      required: [haber_id]
      properties:
        haber_id: { type: integer, minimum: 1 }
        valor_override: { type: number, minimum: 0, nullable: true }
        cantidad: { type: number, minimum: 0, nullable: true }

    LiquidacionHaberAdHoc:
      type: object
      required: [nombre, monto]
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120 }
        monto: { type: number, exclusiveMinimum: 0 }

    LiquidacionEmpleadoCrear:
      type: object
      required: [empleado_id, periodo]
      properties:
        empleado_id: { type: integer, minimum: 1 }
        periodo: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        haberes:
          type: array
          items: { $ref: '#/components/schemas/LiquidacionHaberItem' }
          default: []
        haberes_ad_hoc:
          type: array
          items: { $ref: '#/components/schemas/LiquidacionHaberAdHoc' }
          default: []

    LiquidacionEmpleadoActualizar:
      type: object
      properties:
        haberes:
          type: array
          items: { $ref: '#/components/schemas/LiquidacionHaberItem' }
          default: []
        haberes_ad_hoc:
          type: array
          items: { $ref: '#/components/schemas/LiquidacionHaberAdHoc' }
          default: []

    LiquidacionHaberOut:
      type: object
      required: [id, nombre, monto, orden]
      properties:
        id: { type: integer }
        nombre: { type: string }
        tipo:
          type: string
          enum: [monto_fijo, porcentaje_sobre_basico, cantidad_x_valor]
          nullable: true
        valor: { type: number, nullable: true }
        cantidad: { type: number, nullable: true }
        monto: { type: number }
        orden: { type: integer }

    LiquidacionDetalleOut:
      type: object
      required: [id, concepto_nombre, concepto_tipo, porcentaje_aplicado, monto, orden]
      properties:
        id: { type: integer }
        concepto_nombre: { type: string }
        concepto_tipo: { type: string, enum: [descuento, contribucion] }
        porcentaje_aplicado: { type: number }
        monto: { type: number }
        proveedor_id: { type: integer, nullable: true }
        orden: { type: integer }

    LiquidacionEmpleadoOut:
      type: object
      required: [id, empleado_id, periodo, sueldo_bruto, fecha_creacion, haberes, detalle]
      properties:
        id: { type: integer }
        empleado_id: { type: integer }
        periodo: { type: string }
        sueldo_bruto: { type: number }
        fecha_creacion: { type: string, format: date-time }
        haberes:
          type: array
          items: { $ref: '#/components/schemas/LiquidacionHaberOut' }
        detalle:
          type: array
          items: { $ref: '#/components/schemas/LiquidacionDetalleOut' }
```

- [ ] **Step 4: Validar YAML**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 5: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): endpoints de empleados, haberes, conceptos-liquidacion y liquidaciones"
```

---

## Fase D — Seed inicial

### Task 9: Extender `backend/seed.py` con datos de Personal

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Actualizar imports**

Sumar (alfabético) en `from .models import (...)`: `CategoriaEmpleado`, `ConceptoLiquidacion`, `Empleado`, `Haber`, `TipoConcepto`, `TipoHaber`.

- [ ] **Step 2: Sumar bloque de seed Fase 3 después del bloque de Fase 2**

Justo antes del `db.add_all([Peticion(...), Peticion(...)])` final, agregar:

```python
    # ----- Fase 3: 4 proveedores institucionales -----
    afip = Proveedor(razon_social="AFIP", nombre_fantasia="AFIP", cuit="30-00000001-7")
    arca = Proveedor(razon_social="ARCA", nombre_fantasia="ARCA", cuit="30-00000002-5")
    fateryh = Proveedor(razon_social="FATERYH", nombre_fantasia="FATERYH", cuit="30-00000003-3")
    suterh_prov = Proveedor(razon_social="SUTERH", nombre_fantasia="SUTERH", cuit="30-00000004-1")
    db.add_all([afip, arca, fateryh, suterh_prov])
    db.flush()

    # ----- Fase 3: proveedor + empleado de ejemplo -----
    prov_empleado = Proveedor(razon_social="Pérez, Juan", nombre_fantasia="Pérez Juan", cuit="20-12345678-9")
    db.add(prov_empleado)
    db.flush()

    empleado_ej = Empleado(
        nombre_completo="Juan Pérez",
        cuil="20-12345678-9",
        categoria=CategoriaEmpleado.encargado_permanente_sin_vivienda,
        fecha_ingreso=date(2020, 1, 1),
        fecha_egreso=None,
        sueldo_basico=1000000.0,
        proveedor_id=prov_empleado.id,
        activo=True,
    )
    db.add(empleado_ej)
    db.flush()

    # ----- Fase 3: 6 haberes SUTERH -----
    db.add_all([
        Haber(nombre="Básico", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=100.0, orden=1, activo=True),
        Haber(nombre="Antigüedad", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=1.0, orden=2, activo=True),
        Haber(nombre="Presentismo", tipo=TipoHaber.porcentaje_sobre_basico, valor_default=8.33, orden=3, activo=True),
        Haber(nombre="Adicional vivienda", tipo=TipoHaber.monto_fijo, valor_default=0.0, orden=4, activo=True),
        Haber(nombre="Horas extra 50%", tipo=TipoHaber.cantidad_x_valor, valor_default=0.0, orden=5, activo=True),
        Haber(nombre="Horas extra 100%", tipo=TipoHaber.cantidad_x_valor, valor_default=0.0, orden=6, activo=True),
    ])

    # ----- Fase 3: 12 conceptos SUTERH (paritarias 2026 referencia) -----
    db.add_all([
        # Descuentos (salen del bruto)
        ConceptoLiquidacion(nombre="Jubilación", tipo=TipoConcepto.descuento, porcentaje=11.0, proveedor_id=afip.id, orden=1, activo=True),
        ConceptoLiquidacion(nombre="ISSPJ Ley 19032", tipo=TipoConcepto.descuento, porcentaje=3.0, proveedor_id=afip.id, orden=2, activo=True),
        ConceptoLiquidacion(nombre="OSPERyHA", tipo=TipoConcepto.descuento, porcentaje=2.55, proveedor_id=afip.id, orden=3, activo=True),
        ConceptoLiquidacion(nombre="ANSSAL", tipo=TipoConcepto.descuento, porcentaje=0.45, proveedor_id=afip.id, orden=4, activo=True),
        ConceptoLiquidacion(nombre="Caja Protección Familia", tipo=TipoConcepto.descuento, porcentaje=1.0, proveedor_id=fateryh.id, orden=5, activo=True),
        ConceptoLiquidacion(nombre="Cuota Sindical SUTERH", tipo=TipoConcepto.descuento, porcentaje=2.0, proveedor_id=suterh_prov.id, orden=6, activo=True),
        ConceptoLiquidacion(nombre="FMVDD art. 27 CCT", tipo=TipoConcepto.descuento, porcentaje=1.75, proveedor_id=fateryh.id, orden=7, activo=True),
        # Contribuciones (paga el consorcio aparte)
        ConceptoLiquidacion(nombre="AFIP F931", tipo=TipoConcepto.contribucion, porcentaje=16.0, proveedor_id=afip.id, orden=10, activo=True),
        ConceptoLiquidacion(nombre="ARCA VEP", tipo=TipoConcepto.contribucion, porcentaje=10.78, proveedor_id=arca.id, orden=11, activo=True),
        ConceptoLiquidacion(nombre="FATERYH", tipo=TipoConcepto.contribucion, porcentaje=8.535, proveedor_id=fateryh.id, orden=12, activo=True),
        ConceptoLiquidacion(nombre="FATERYH-SERACARH", tipo=TipoConcepto.contribucion, porcentaje=0.5, proveedor_id=fateryh.id, orden=13, activo=True),
        ConceptoLiquidacion(nombre="SUTERH patronal", tipo=TipoConcepto.contribucion, porcentaje=4.51, proveedor_id=suterh_prov.id, orden=14, activo=True),
    ])
```

- [ ] **Step 3: Verificar que el seed corre**

Detener uvicorn si está corriendo. Luego:

```bash
rm -f consorcio.db
./.venv/Scripts/python.exe -c "
import os
os.environ['SEED_ENABLED'] = 'true'
os.environ['SEED_DEFAULT_PASSWORD'] = 'admin1234'
from backend.database import SessionLocal, engine, Base
from backend.seed import seed_if_empty
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_if_empty(db)
from backend.models import Empleado, Haber, ConceptoLiquidacion, Proveedor
db = SessionLocal()
print('empleados:', db.query(Empleado).count())
print('haberes:', db.query(Haber).count())
print('conceptos:', db.query(ConceptoLiquidacion).count())
print('proveedores:', db.query(Proveedor).count())
db.close()
"
```
Expected: `empleados: 1`, `haberes: 6`, `conceptos: 12`, `proveedores: 10` (5 originales de Fase 1 + 4 institucionales + 1 del empleado).

- [ ] **Step 4: Run suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 5: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): 4 proveedores institucionales + empleado de ejemplo + 6 haberes + 12 conceptos SUTERH"
```

---

## Fase E — Frontend

### Task 10: API clients

**Files:**
- Create: `frontend/src/api/empleados.js`
- Create: `frontend/src/api/haberes.js`
- Create: `frontend/src/api/conceptosLiquidacion.js`
- Create: `frontend/src/api/liquidaciones.js`

- [ ] **Step 1: Crear `frontend/src/api/empleados.js`**

```javascript
import { apiFetch } from "./client";

export function listarEmpleados({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/empleados${qs}`);
}

export function crearEmpleado(payload) {
  return apiFetch("/empleados", { method: "POST", body: payload });
}

export function obtenerEmpleado(id) {
  return apiFetch(`/empleados/${id}`);
}

export function actualizarEmpleado(id, payload) {
  return apiFetch(`/empleados/${id}`, { method: "PATCH", body: payload });
}

export function eliminarEmpleado(id) {
  return apiFetch(`/empleados/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Crear `frontend/src/api/haberes.js`**

```javascript
import { apiFetch } from "./client";

export function listarHaberes({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/haberes${qs}`);
}

export function crearHaber(payload) {
  return apiFetch("/haberes", { method: "POST", body: payload });
}

export function obtenerHaber(id) {
  return apiFetch(`/haberes/${id}`);
}

export function actualizarHaber(id, payload) {
  return apiFetch(`/haberes/${id}`, { method: "PATCH", body: payload });
}

export function eliminarHaber(id) {
  return apiFetch(`/haberes/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Crear `frontend/src/api/conceptosLiquidacion.js`**

```javascript
import { apiFetch } from "./client";

export function listarConceptos({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/conceptos-liquidacion${qs}`);
}

export function crearConcepto(payload) {
  return apiFetch("/conceptos-liquidacion", { method: "POST", body: payload });
}

export function obtenerConcepto(id) {
  return apiFetch(`/conceptos-liquidacion/${id}`);
}

export function actualizarConcepto(id, payload) {
  return apiFetch(`/conceptos-liquidacion/${id}`, { method: "PATCH", body: payload });
}

export function eliminarConcepto(id) {
  return apiFetch(`/conceptos-liquidacion/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 4: Crear `frontend/src/api/liquidaciones.js`**

```javascript
import { apiFetch } from "./client";

export function listarLiquidaciones({ periodo, empleado_id } = {}) {
  const qs = new URLSearchParams();
  if (periodo) qs.set("periodo", periodo);
  if (empleado_id) qs.set("empleado_id", empleado_id);
  const s = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/liquidaciones${s}`);
}

export function crearLiquidacion(payload) {
  return apiFetch("/liquidaciones", { method: "POST", body: payload });
}

export function obtenerLiquidacion(id) {
  return apiFetch(`/liquidaciones/${id}`);
}

export function actualizarLiquidacion(id, payload) {
  return apiFetch(`/liquidaciones/${id}`, { method: "PATCH", body: payload });
}

export function eliminarLiquidacion(id) {
  return apiFetch(`/liquidaciones/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 5: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/empleados.js frontend/src/api/haberes.js frontend/src/api/conceptosLiquidacion.js frontend/src/api/liquidaciones.js
git commit -m "feat(frontend/api): clients para empleados, haberes, conceptos-liquidacion y liquidaciones"
```

---

### Task 11: Pantalla Empleados (Configuración)

**Files:**
- Create: `frontend/src/screens/Empleados.jsx`

- [ ] **Step 1: Crear `frontend/src/screens/Empleados.jsx`**

```jsx
import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import {
  listarEmpleados,
  crearEmpleado,
  actualizarEmpleado,
  eliminarEmpleado,
} from "../api/empleados";
import { listarProveedores } from "../api/proveedores";

const CATEGORIAS = [
  { value: "encargado_permanente_con_vivienda", label: "Encargado permanente con vivienda" },
  { value: "encargado_permanente_sin_vivienda", label: "Encargado permanente sin vivienda" },
  { value: "encargado_suplente", label: "Encargado suplente" },
  { value: "ayudante", label: "Ayudante" },
];

function labelCategoria(v) {
  return CATEGORIAS.find((c) => c.value === v)?.label || v;
}

export default function Empleados() {
  const [empleados, setEmpleados] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  async function cargarCatalogos() {
    const r = await listarProveedores({ activo: true });
    if (r.status === 200) setProveedores(r.data);
  }

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarEmpleados(filtro);
    if (r.status === 200) {
      setEmpleados(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los empleados.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(e) {
    const r = e.activo
      ? await eliminarEmpleado(e.id)
      : await actualizarEmpleado(e.id, { activo: true });
    if (r.status === 200 || r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  function proveedorPorId(id) {
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Empleados</h2>
        <div className="cabecera-acciones">
          <label className="filtro-checkbox">
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Mostrar inactivos
          </label>
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            + Nuevo empleado
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {empleados.length === 0 && <p>No hay empleados con esos filtros.</p>}

      <ul className="lista-config">
        {empleados.map((e) => (
          <li key={e.id}>
            <Tarjeta>
              <h3>{e.nombre_completo}</h3>
              <p className="meta">CUIL: {e.cuil}</p>
              <p className="meta">Categoría: {labelCategoria(e.categoria)}</p>
              <p className="meta">Sueldo básico: ${e.sueldo_basico.toLocaleString("es-AR")}</p>
              <p className="meta">Ingresó: {e.fecha_ingreso}</p>
              <p className="meta">Proveedor: {proveedorPorId(e.proveedor_id)}</p>
              <p className="meta">Estado: {e.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", empleado: e })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(e)}>
                  {e.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalEmpleado
          titulo="Nuevo empleado"
          proveedores={proveedores}
          permiteEditarCuil
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearEmpleado(datos);
            if (r.status === 201) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al crear.";
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalEmpleado
          titulo={`Editar ${modal.empleado.nombre_completo}`}
          inicial={modal.empleado}
          proveedores={proveedores}
          permiteEditarCuil={false}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const { cuil: _ignored, ...resto } = datos;
            const r = await actualizarEmpleado(modal.empleado.id, resto);
            if (r.status === 200) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al editar.";
          }}
        />
      )}
    </main>
  );
}

function ModalEmpleado({ titulo, inicial, proveedores, permiteEditarCuil, onCerrar, onGuardar }) {
  const valorInicial = inicial
    ? {
        nombre_completo: inicial.nombre_completo,
        cuil: inicial.cuil,
        categoria: inicial.categoria,
        fecha_ingreso: inicial.fecha_ingreso,
        fecha_egreso: inicial.fecha_egreso || "",
        sueldo_basico: String(inicial.sueldo_basico),
        proveedor_id: inicial.proveedor_id,
      }
    : {
        nombre_completo: "",
        cuil: "",
        categoria: "encargado_permanente_sin_vivienda",
        fecha_ingreso: "",
        fecha_egreso: "",
        sueldo_basico: "",
        proveedor_id: proveedores[0]?.id ?? "",
      };

  const [form, setForm] = useState(valorInicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function set(campo, valor) {
    setForm({ ...form, [campo]: valor });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = {
      nombre_completo: form.nombre_completo,
      cuil: form.cuil,
      categoria: form.categoria,
      fecha_ingreso: form.fecha_ingreso,
      fecha_egreso: form.fecha_egreso || null,
      sueldo_basico: Number(form.sueldo_basico),
      proveedor_id: Number(form.proveedor_id),
    };
    const err = await onGuardar(payload);
    if (err) {
      setError(err);
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Nombre completo <input value={form.nombre_completo}
            onChange={(e) => set("nombre_completo", e.target.value)} maxLength={255} required /></label>
          <label>CUIL <input value={form.cuil}
            onChange={(e) => set("cuil", e.target.value)}
            disabled={!permiteEditarCuil}
            placeholder="20-12345678-9"
            pattern="\d{2}-\d{8}-\d{1}"
            required /></label>
          <label>Categoría <select value={form.categoria} onChange={(e) => set("categoria", e.target.value)} required>
            {CATEGORIAS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select></label>
          <label>Fecha ingreso <input type="date" value={form.fecha_ingreso}
            onChange={(e) => set("fecha_ingreso", e.target.value)} required /></label>
          <label>Fecha egreso (opcional) <input type="date" value={form.fecha_egreso}
            onChange={(e) => set("fecha_egreso", e.target.value)} /></label>
          <label>Sueldo básico <input type="number" min="0.01" step="0.01"
            value={form.sueldo_basico} onChange={(e) => set("sueldo_basico", e.target.value)} required /></label>
          <label>Proveedor asociado <select value={form.proveedor_id}
            onChange={(e) => set("proveedor_id", e.target.value)} required>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select></label>

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/Empleados.jsx
git commit -m "feat(frontend): pantalla Empleados con CRUD (Configuración)"
```

---

### Task 12: Pantalla Haberes (Configuración)

**Files:**
- Create: `frontend/src/screens/Haberes.jsx`

- [ ] **Step 1: Crear `frontend/src/screens/Haberes.jsx`**

```jsx
import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import {
  listarHaberes,
  crearHaber,
  actualizarHaber,
  eliminarHaber,
} from "../api/haberes";

const TIPOS = [
  { value: "monto_fijo", label: "Monto fijo", unidadValor: "Monto" },
  { value: "porcentaje_sobre_basico", label: "Porcentaje sobre básico", unidadValor: "Porcentaje (%)" },
  { value: "cantidad_x_valor", label: "Cantidad × valor", unidadValor: "Valor por unidad" },
];

function labelTipo(v) {
  return TIPOS.find((t) => t.value === v)?.label || v;
}

export default function Haberes() {
  const [haberes, setHaberes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarHaberes(filtro);
    if (r.status === 200) {
      setHaberes(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los haberes.");
    }
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(h) {
    const r = h.activo
      ? await eliminarHaber(h.id)
      : await actualizarHaber(h.id, { activo: true });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Haberes</h2>
        <div className="cabecera-acciones">
          <label className="filtro-checkbox">
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Mostrar inactivos
          </label>
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            + Nuevo haber
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {haberes.length === 0 && <p>No hay haberes para mostrar.</p>}

      <ul className="lista-config">
        {haberes.map((h) => (
          <li key={h.id}>
            <Tarjeta>
              <h3>{h.nombre}</h3>
              <p className="meta">Tipo: {labelTipo(h.tipo)}</p>
              <p className="meta">Valor default: {h.valor_default}</p>
              <p className="meta">Orden: {h.orden}</p>
              <p className="meta">Estado: {h.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", haber: h })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(h)}>
                  {h.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalHaber
          titulo="Nuevo haber"
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearHaber(datos);
            if (r.status === 201) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al crear.";
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalHaber
          titulo={`Editar ${modal.haber.nombre}`}
          inicial={modal.haber}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await actualizarHaber(modal.haber.id, datos);
            if (r.status === 200) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al editar.";
          }}
        />
      )}
    </main>
  );
}

function ModalHaber({ titulo, inicial, onCerrar, onGuardar }) {
  const valorInicial = inicial
    ? { nombre: inicial.nombre, tipo: inicial.tipo, valor_default: String(inicial.valor_default), orden: String(inicial.orden) }
    : { nombre: "", tipo: "monto_fijo", valor_default: "0", orden: "0" };

  const [form, setForm] = useState(valorInicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function set(campo, valor) {
    setForm({ ...form, [campo]: valor });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = {
      nombre: form.nombre,
      tipo: form.tipo,
      valor_default: Number(form.valor_default),
      orden: Number(form.orden),
    };
    const err = await onGuardar(payload);
    if (err) {
      setError(err);
      setGuardando(false);
    }
  }

  const unidad = TIPOS.find((t) => t.value === form.tipo)?.unidadValor || "Valor";

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Nombre <input value={form.nombre}
            onChange={(e) => set("nombre", e.target.value)} maxLength={120} required /></label>
          <label>Tipo <select value={form.tipo} onChange={(e) => set("tipo", e.target.value)} required>
            {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select></label>
          <label>{unidad} <input type="number" min="0" step="0.01"
            value={form.valor_default} onChange={(e) => set("valor_default", e.target.value)} required /></label>
          <label>Orden <input type="number" min="0"
            value={form.orden} onChange={(e) => set("orden", e.target.value)} required /></label>

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/Haberes.jsx
git commit -m "feat(frontend): pantalla Haberes con CRUD (Configuración)"
```

---

### Task 13: Pantalla ConceptosLiquidacion (Configuración)

**Files:**
- Create: `frontend/src/screens/ConceptosLiquidacion.jsx`

- [ ] **Step 1: Crear `frontend/src/screens/ConceptosLiquidacion.jsx`**

```jsx
import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import {
  listarConceptos,
  crearConcepto,
  actualizarConcepto,
  eliminarConcepto,
} from "../api/conceptosLiquidacion";
import { listarProveedores } from "../api/proveedores";

const TIPOS = [
  { value: "descuento", label: "Descuento" },
  { value: "contribucion", label: "Contribución" },
];

function labelTipo(v) {
  return TIPOS.find((t) => t.value === v)?.label || v;
}

export default function ConceptosLiquidacion() {
  const [conceptos, setConceptos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  async function cargarCatalogos() {
    const r = await listarProveedores({ activo: true });
    if (r.status === 200) setProveedores(r.data);
  }

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarConceptos(filtro);
    if (r.status === 200) {
      setConceptos(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los conceptos.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(c) {
    const r = c.activo
      ? await eliminarConcepto(c.id)
      : await actualizarConcepto(c.id, { activo: true });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  function proveedorPorId(id) {
    if (id === null || id === undefined) return "—";
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Conceptos de liquidación</h2>
        <div className="cabecera-acciones">
          <label className="filtro-checkbox">
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Mostrar inactivos
          </label>
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            + Nuevo concepto
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {conceptos.length === 0 && <p>No hay conceptos para mostrar.</p>}

      <ul className="lista-config">
        {conceptos.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>{c.nombre}</h3>
              <p className="meta">Tipo: {labelTipo(c.tipo)}</p>
              <p className="meta">Porcentaje: {c.porcentaje}%</p>
              <p className="meta">Proveedor: {proveedorPorId(c.proveedor_id)}</p>
              <p className="meta">Estado: {c.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", concepto: c })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(c)}>
                  {c.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalConcepto
          titulo="Nuevo concepto"
          proveedores={proveedores}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearConcepto(datos);
            if (r.status === 201) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al crear.";
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalConcepto
          titulo={`Editar ${modal.concepto.nombre}`}
          inicial={modal.concepto}
          proveedores={proveedores}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await actualizarConcepto(modal.concepto.id, datos);
            if (r.status === 200) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al editar.";
          }}
        />
      )}
    </main>
  );
}

function ModalConcepto({ titulo, inicial, proveedores, onCerrar, onGuardar }) {
  const valorInicial = inicial
    ? {
        nombre: inicial.nombre,
        tipo: inicial.tipo,
        porcentaje: String(inicial.porcentaje),
        proveedor_id: inicial.proveedor_id ?? "",
        orden: String(inicial.orden),
      }
    : { nombre: "", tipo: "descuento", porcentaje: "0", proveedor_id: "", orden: "0" };

  const [form, setForm] = useState(valorInicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function set(campo, valor) {
    setForm({ ...form, [campo]: valor });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = {
      nombre: form.nombre,
      tipo: form.tipo,
      porcentaje: Number(form.porcentaje),
      proveedor_id: form.proveedor_id ? Number(form.proveedor_id) : null,
      orden: Number(form.orden),
    };
    const err = await onGuardar(payload);
    if (err) {
      setError(err);
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Nombre <input value={form.nombre}
            onChange={(e) => set("nombre", e.target.value)} maxLength={120} required /></label>
          <label>Tipo <select value={form.tipo} onChange={(e) => set("tipo", e.target.value)} required>
            {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select></label>
          <label>Porcentaje (0–100) <input type="number" min="0" max="100" step="0.0001"
            value={form.porcentaje} onChange={(e) => set("porcentaje", e.target.value)} required /></label>
          <label>Proveedor (opcional)
            <select value={form.proveedor_id} onChange={(e) => set("proveedor_id", e.target.value)}>
              <option value="">— Sin proveedor —</option>
              {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
            </select>
          </label>
          <p className="meta">Sin proveedor: el concepto se calcula pero no genera un Gasto separado.</p>
          <label>Orden <input type="number" min="0"
            value={form.orden} onChange={(e) => set("orden", e.target.value)} required /></label>

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/ConceptosLiquidacion.jsx
git commit -m "feat(frontend): pantalla ConceptosLiquidacion con CRUD (Configuración)"
```

---

### Task 14: Pantalla Liquidaciones (Expensas y pagos)

**Files:**
- Create: `frontend/src/screens/Liquidaciones.jsx`

> Pantalla más compleja: tabs Del mes / Historial, modal con lista editable de haberes, preview de cálculo, regeneración.

- [ ] **Step 1: Crear `frontend/src/screens/Liquidaciones.jsx`**

```jsx
import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import Tabs from "../components/Tabs";
import {
  listarLiquidaciones,
  crearLiquidacion,
  actualizarLiquidacion,
  eliminarLiquidacion,
} from "../api/liquidaciones";
import { listarEmpleados } from "../api/empleados";
import { listarHaberes } from "../api/haberes";

const TABS = [
  { path: "/liquidaciones", label: "Del mes", end: true },
  { path: "/liquidaciones/historial", label: "Historial" },
];

function periodoActual() {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

export default function Liquidaciones({ vistaHistorial = false }) {
  const [liquidaciones, setLiquidaciones] = useState([]);
  const [empleados, setEmpleados] = useState([]);
  const [haberes, setHaberes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [filtroPeriodo, setFiltroPeriodo] = useState(vistaHistorial ? "" : periodoActual());
  const [filtroEmpleado, setFiltroEmpleado] = useState("");
  const [modal, setModal] = useState(null);

  async function cargarCatalogos() {
    const [rE, rH] = await Promise.all([
      listarEmpleados({ activo: true }),
      listarHaberes({ activo: true }),
    ]);
    if (rE.status === 200) setEmpleados(rE.data);
    if (rH.status === 200) setHaberes(rH.data);
  }

  async function recargar() {
    setCargando(true);
    const filtros = {};
    if (filtroPeriodo) filtros.periodo = filtroPeriodo;
    if (filtroEmpleado) filtros.empleado_id = filtroEmpleado;
    const r = await listarLiquidaciones(filtros);
    if (r.status === 200) {
      setLiquidaciones(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar las liquidaciones.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [filtroPeriodo, filtroEmpleado]);

  function empleadoPorId(id) {
    return empleados.find((e) => e.id === id)?.nombre_completo || `Empleado #${id}`;
  }

  async function handleBorrar(liq) {
    if (!confirm("¿Eliminar la liquidación? Se borrarán sus gastos asociados.")) return;
    const r = await eliminarLiquidacion(liq.id);
    if (r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al eliminar.");
  }

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Liquidaciones</h2>
      </header>
      <Tabs tabs={TABS} />

      <section className="filtros-gastos">
        <label>Período <input
          type="month"
          value={filtroPeriodo}
          onChange={(e) => setFiltroPeriodo(e.target.value)}
        /></label>
        {vistaHistorial && (
          <label>Empleado <select value={filtroEmpleado}
            onChange={(e) => setFiltroEmpleado(e.target.value)}>
            <option value="">Todos</option>
            {empleados.map((e) => <option key={e.id} value={e.id}>{e.nombre_completo}</option>)}
          </select></label>
        )}
      </section>

      <div className="cabecera-acciones">
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          + Cargar liquidación
        </button>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {cargando && <p>Cargando…</p>}
      {!cargando && liquidaciones.length === 0 && <p>No hay liquidaciones con esos filtros.</p>}

      <ul className="lista-config">
        {liquidaciones.map((liq) => {
          const descuentos = liq.detalle.filter((d) => d.concepto_tipo === "descuento");
          const contribuciones = liq.detalle.filter((d) => d.concepto_tipo === "contribucion");
          const totalDescuentos = descuentos.reduce((s, d) => s + d.monto, 0);
          const totalContrib = contribuciones.reduce((s, d) => s + d.monto, 0);
          const neto = liq.sueldo_bruto - totalDescuentos;
          const total = liq.sueldo_bruto + totalContrib;
          return (
            <li key={liq.id}>
              <Tarjeta>
                <h3>{empleadoPorId(liq.empleado_id)} — {liq.periodo}</h3>
                <p className="meta">Bruto: ${liq.sueldo_bruto.toLocaleString("es-AR")} · Neto: ${neto.toLocaleString("es-AR")} · Total liquidación: ${total.toLocaleString("es-AR")}</p>
                <details>
                  <summary>Ver desglose</summary>
                  <p><strong>Haberes:</strong></p>
                  <ul className="lista-coeficientes">
                    {liq.haberes.map((h) => (
                      <li key={h.id}>{h.nombre}: ${h.monto.toLocaleString("es-AR")}</li>
                    ))}
                  </ul>
                  <p><strong>Descuentos:</strong></p>
                  <ul className="lista-coeficientes">
                    {descuentos.map((d) => (
                      <li key={d.id}>{d.concepto_nombre} ({d.porcentaje_aplicado}%): ${d.monto.toLocaleString("es-AR")}</li>
                    ))}
                  </ul>
                  <p><strong>Contribuciones:</strong></p>
                  <ul className="lista-coeficientes">
                    {contribuciones.map((d) => (
                      <li key={d.id}>{d.concepto_nombre} ({d.porcentaje_aplicado}%): ${d.monto.toLocaleString("es-AR")}</li>
                    ))}
                  </ul>
                </details>
                <div className="tarjeta-acciones">
                  <button type="button" onClick={() => setModal({ tipo: "editar", liquidacion: liq })}>
                    Editar
                  </button>
                  <button type="button" className="boton-borrar" onClick={() => handleBorrar(liq)}>
                    Eliminar
                  </button>
                </div>
              </Tarjeta>
            </li>
          );
        })}
      </ul>

      {modal && (
        <ModalLiquidacion
          tipo={modal.tipo}
          inicial={modal.liquidacion}
          empleados={empleados}
          haberes={haberes}
          periodoDefault={filtroPeriodo || periodoActual()}
          onCerrar={() => setModal(null)}
          onGuardado={() => {
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalLiquidacion({ tipo, inicial, empleados, haberes, periodoDefault, onCerrar, onGuardado }) {
  const esEditar = tipo === "editar";
  const [empleadoId, setEmpleadoId] = useState(inicial?.empleado_id || empleados[0]?.id || "");
  const [periodo, setPeriodo] = useState(inicial?.periodo || periodoDefault);

  // Lista editable de haberes seleccionados.
  const haberesIniciales = inicial
    ? inicial.haberes
        .filter((h) => h.tipo !== null)
        .map((h) => {
          const cat = haberes.find((x) => x.nombre === h.nombre);
          return {
            haber_id: cat?.id ?? null,
            tipo: h.tipo,
            valor_override: h.valor ?? "",
            cantidad: h.cantidad ?? "",
          };
        })
        .filter((x) => x.haber_id !== null)
    : haberes.slice(0, 2).map((h) => ({
        haber_id: h.id,
        tipo: h.tipo,
        valor_override: "",
        cantidad: "",
      }));

  const adHocIniciales = inicial
    ? inicial.haberes.filter((h) => h.tipo === null).map((h) => ({ nombre: h.nombre, monto: String(h.monto) }))
    : [];

  const [items, setItems] = useState(haberesIniciales);
  const [adHoc, setAdHoc] = useState(adHocIniciales);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function actualizarItem(idx, campo, valor) {
    const copia = [...items];
    copia[idx] = { ...copia[idx], [campo]: valor };
    setItems(copia);
  }

  function quitarItem(idx) {
    setItems(items.filter((_, i) => i !== idx));
  }

  function agregarItem() {
    const noUsados = haberes.filter((h) => !items.some((i) => i.haber_id === h.id));
    if (noUsados.length === 0) return;
    setItems([...items, { haber_id: noUsados[0].id, tipo: noUsados[0].tipo, valor_override: "", cantidad: "" }]);
  }

  function actualizarAdHoc(idx, campo, valor) {
    const copia = [...adHoc];
    copia[idx] = { ...copia[idx], [campo]: valor };
    setAdHoc(copia);
  }

  function quitarAdHoc(idx) {
    setAdHoc(adHoc.filter((_, i) => i !== idx));
  }

  function agregarAdHoc() {
    setAdHoc([...adHoc, { nombre: "", monto: "" }]);
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);

    const payload = {
      empleado_id: Number(empleadoId),
      periodo,
      haberes: items.map((i) => ({
        haber_id: Number(i.haber_id),
        valor_override: i.valor_override === "" ? null : Number(i.valor_override),
        cantidad: i.cantidad === "" ? null : Number(i.cantidad),
      })),
      haberes_ad_hoc: adHoc
        .filter((a) => a.nombre && a.monto)
        .map((a) => ({ nombre: a.nombre, monto: Number(a.monto) })),
    };

    // Editar no incluye empleado_id ni periodo (inmutables).
    const r = esEditar
      ? await actualizarLiquidacion(inicial.id, { haberes: payload.haberes, haberes_ad_hoc: payload.haberes_ad_hoc })
      : await crearLiquidacion(payload);

    if (r.status === 200 || r.status === 201) {
      onGuardado();
      return;
    }
    setError(r.data?.detail || "No se pudo guardar.");
    setGuardando(false);
  }

  function nombreHaber(id) {
    return haberes.find((h) => h.id === id)?.nombre || "?";
  }

  function tipoHaber(id) {
    return haberes.find((h) => h.id === id)?.tipo;
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{esEditar ? "Editar liquidación" : "Cargar liquidación"}</h3>
        <form onSubmit={onSubmit}>
          <label>Empleado
            <select value={empleadoId} onChange={(e) => setEmpleadoId(e.target.value)} disabled={esEditar} required>
              {empleados.map((e) => <option key={e.id} value={e.id}>{e.nombre_completo}</option>)}
            </select>
          </label>
          <label>Período <input type="month" value={periodo}
            onChange={(e) => setPeriodo(e.target.value)} disabled={esEditar} required /></label>

          <fieldset>
            <legend>Haberes</legend>
            {items.map((item, idx) => {
              const tipo = tipoHaber(item.haber_id);
              return (
                <div key={idx} style={{ marginBlockEnd: "0.5rem", border: "1px solid var(--color-text)", padding: "0.5rem", borderRadius: 4 }}>
                  <p className="meta">{nombreHaber(item.haber_id)}</p>
                  {tipo === "porcentaje_sobre_basico" && (
                    <label>Porcentaje <input type="number" min="0" step="0.0001"
                      value={item.valor_override} onChange={(e) => actualizarItem(idx, "valor_override", e.target.value)}
                      placeholder="usa el default" /></label>
                  )}
                  {tipo === "monto_fijo" && (
                    <label>Monto <input type="number" min="0" step="0.01"
                      value={item.valor_override} onChange={(e) => actualizarItem(idx, "valor_override", e.target.value)}
                      placeholder="usa el default" /></label>
                  )}
                  {tipo === "cantidad_x_valor" && (
                    <>
                      <label>Cantidad <input type="number" min="0" step="0.01"
                        value={item.cantidad} onChange={(e) => actualizarItem(idx, "cantidad", e.target.value)}
                        required /></label>
                      <label>Valor por unidad <input type="number" min="0" step="0.01"
                        value={item.valor_override} onChange={(e) => actualizarItem(idx, "valor_override", e.target.value)}
                        placeholder="usa el default" /></label>
                    </>
                  )}
                  <button type="button" onClick={() => quitarItem(idx)}>Quitar</button>
                </div>
              );
            })}
            <button type="button" onClick={agregarItem}>+ Agregar haber</button>
          </fieldset>

          <fieldset>
            <legend>Haberes ad-hoc (ej. SAC)</legend>
            {adHoc.map((a, idx) => (
              <div key={idx} style={{ marginBlockEnd: "0.5rem" }}>
                <label>Nombre <input value={a.nombre}
                  onChange={(e) => actualizarAdHoc(idx, "nombre", e.target.value)} maxLength={120} required /></label>
                <label>Monto <input type="number" min="0.01" step="0.01"
                  value={a.monto} onChange={(e) => actualizarAdHoc(idx, "monto", e.target.value)} required /></label>
                <button type="button" onClick={() => quitarAdHoc(idx)}>Quitar</button>
              </div>
            ))}
            <button type="button" onClick={agregarAdHoc}>+ Agregar ad-hoc</button>
          </fieldset>

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/Liquidaciones.jsx
git commit -m "feat(frontend): pantalla Liquidaciones con tabs, modal de cálculo y haberes ad-hoc"
```

---

### Task 15: Rutas + Sidebar

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Agregar imports y rutas en `App.jsx`**

Sumar imports:

```javascript
import Empleados from "./screens/Empleados";
import Haberes from "./screens/Haberes";
import ConceptosLiquidacion from "./screens/ConceptosLiquidacion";
import Liquidaciones from "./screens/Liquidaciones";
```

Y dentro del `<Routes>` (antes del catch-all `*`):

```jsx
<Route path="empleados" element={<Empleados />} />
<Route path="haberes" element={<Haberes />} />
<Route path="conceptos-liquidacion" element={<ConceptosLiquidacion />} />
<Route path="liquidaciones" element={<Liquidaciones />} />
<Route path="liquidaciones/historial" element={<Liquidaciones vistaHistorial />} />
```

- [ ] **Step 2: Sumar items al sidebar en `Sidebar.jsx`**

En el array `SECCIONES`:
- En "Expensas y pagos", agregar como cuarto item:
  ```javascript
  {
    ruta: "/liquidaciones",
    nombre: "Liquidaciones",
    rolesPermitidos: ["administracion"],
  },
  ```
- En "Configuración", agregar al final (5°, 6°, 7° items):
  ```javascript
  {
    ruta: "/empleados",
    nombre: "Empleados",
    rolesPermitidos: ["administracion"],
  },
  {
    ruta: "/haberes",
    nombre: "Haberes",
    rolesPermitidos: ["administracion"],
  },
  {
    ruta: "/conceptos-liquidacion",
    nombre: "Conceptos de liquidación",
    rolesPermitidos: ["administracion"],
  },
  ```

- [ ] **Step 3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat(frontend): rutas y sidebar Fase 3 (Liquidaciones, Empleados, Haberes, Conceptos)"
```

---

## Fase F — Verificación final y merge

### Task 16: Smoke test full + merge

- [ ] **Step 1: Correr suite backend completa**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 2: Build de producción frontend**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Validar OpenAPI**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 4: Revisar diff del branch**

Run: `git log master..HEAD --oneline`
Run: `git diff master..HEAD --stat`

- [ ] **Step 5: Smoke test manual del frontend (recomendado)**

Backend + frontend en dos terminales:
- `./.venv/Scripts/python.exe -m uvicorn backend.main:app --reload --port 8000`
- `cd frontend && npm run dev`

Probá como admin:
1. Sidebar tiene "Liquidaciones" en Expensas y pagos, y "Empleados" + "Haberes" + "Conceptos de liquidación" en Configuración.
2. `/empleados` muestra el empleado seed (Juan Pérez).
3. `/haberes` muestra 6 haberes SUTERH.
4. `/conceptos-liquidacion` muestra 12 conceptos SUTERH.
5. `/liquidaciones` con período actual vacío. Botón "+ Cargar liquidación".
6. Cargar liquidación: elegir empleado (Juan), período actual, dejar haberes Básico + Antigüedad, guardar → aparece en la lista con bruto y neto calculados.
7. Editar liquidación → cambiar antigüedad % → guardar → bruto recalcula.
8. Ir a `/gastos` con filtro del mismo período → aparecen los N Gastos generados por la liquidación con pill o info que vienen de una liquidación.
9. Eliminar la liquidación → los gastos asociados desaparecen.
10. Logout, login depto → ningún item nuevo en sidebar.

- [ ] **Step 6: Consultar al usuario sobre merge**

> "Fase 3 terminada. Suite verde + build OK + smoke test pasó. ¿Mergeo a master con `--no-ff`?"

Esperar confirmación. Si OK:

```bash
git checkout master
git merge --no-ff feature/expensas-fase3 -m "Merge feature/expensas-fase3: encargado y cargas sociales (Fase 3)"
git branch -d feature/expensas-fase3
```
