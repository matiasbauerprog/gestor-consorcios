# Expensas — Fase 2: gastos del consorcio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar carga de Gastos del consorcio (puntuales) y plantillas `GastoHabitual` (recurrentes), con endpoints especiales para planes en cuotas y materialización de habituales en un período. Sin tocar Expensa/Comprobante.

**Architecture:** 2 nuevas tablas (`gastos`, `gastos_habituales`), 1 enum (`FormaPago`). 2 routers nuevos. Frontend con pantalla `/gastos` con tabs internos `Únicos` / `Habituales` (componente `Tabs` reutilizable, mobile-first). Clean start no necesario — DB ya vacía desde Fase 1.

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + SQLite. React + Vite + React Router. Tests con pytest. Sin nuevas dependencias.

**Spec:** [docs/superpowers/specs/2026-06-16-expensas-fase2-gastos-design.md](../specs/2026-06-16-expensas-fase2-gastos-design.md)

**Errores de validación:** el proyecto convierte `RequestValidationError` (Pydantic) a HTTP **400**. Ver `backend/main.py:67`.

---

## Setup inicial

### Task 0: Branch + estado limpio

- [ ] **Step 1: Verificar estado y crear branch**

Run: `git status && git branch --show-current`
Expected: rama `master`, working tree puede tener `.claude/settings*.json` modificados y `package*.json` untracked (ignorables).

```bash
git checkout -b feature/expensas-fase2
```

- [ ] **Step 2: Borrar `consorcio.db` local si existe**

Detener uvicorn si está corriendo.

Run: `rm -f consorcio.db`
Expected: ningún output.

- [ ] **Step 3: Confirmar baseline verde**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 299 tests passing (post-Fase 1).

---

## Fase A — Backend foundation

### Task 1: Models en `backend/models.py`

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Agregar `FormaPago` enum al bloque de enums**

Después del último enum existente (`Rubro`) y antes de la primera clase de tabla, agregar:

```python
class FormaPago(str, enum.Enum):
    transferencia = "transferencia"
    debito_automatico = "debito_automatico"
    cheque = "cheque"
    efectivo = "efectivo"
    otro = "otro"
```

- [ ] **Step 2: Verificar que `Integer` está importado**

En el bloque de imports de `sqlalchemy`, asegurarse de que `Integer` esté listado. Si no está, agregarlo en orden alfabético:

```python
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
```

- [ ] **Step 3: Agregar `GastoHabitual` al final del archivo**

> **Por qué primero `GastoHabitual` y después `Gasto`:** la FK `gasto_habitual_id` de `Gasto` apunta a `gastos_habituales`. SQLAlchemy resuelve FKs por nombre de tabla, no por orden de clases, pero declarar primero la tabla referenciada es buena práctica.

```python
class GastoHabitual(Base):
    __tablename__ = "gastos_habituales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)
    clase_prorrateo_id: Mapped[int] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=False
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    forma_pago: Mapped[FormaPago] = mapped_column(
        SqlEnum(FormaPago, name="forma_pago"), nullable=False
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Agregar `Gasto` al final del archivo**

```python
class Gasto(Base):
    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo: Mapped[str] = mapped_column(String(7), index=True, nullable=False)
    rubro: Mapped[Rubro] = mapped_column(SqlEnum(Rubro, name="rubro"), nullable=False)

    # Excluyentes: clase_prorrateo_id O departamento_id, nunca ambos, nunca ninguno.
    # La excluyencia se valida en el schema Pydantic, no a nivel DB.
    clase_prorrateo_id: Mapped[int | None] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="RESTRICT"), nullable=True
    )
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"), nullable=True
    )

    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)

    forma_pago: Mapped[FormaPago] = mapped_column(
        SqlEnum(FormaPago, name="forma_pago"), nullable=False
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)

    numero_factura: Mapped[str | None] = mapped_column(String(50))
    fecha_factura: Mapped[date | None] = mapped_column(Date)

    cuota_actual: Mapped[int | None] = mapped_column(Integer)
    cuota_total: Mapped[int | None] = mapped_column(Integer)

    gasto_habitual_id: Mapped[int | None] = mapped_column(
        ForeignKey("gastos_habituales.id", ondelete="SET NULL")
    )

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Verificar imports y suite**

Run: `./.venv/Scripts/python.exe -c "from backend.models import FormaPago, Gasto, GastoHabitual; print('OK')"`
Expected: imprime `OK`.

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 299 tests passing.

- [ ] **Step 6: Commit**

```bash
git add backend/models.py
git commit -m "feat(models): FormaPago enum + Gasto + GastoHabitual"
```

---

### Task 2: Schemas Pydantic en `backend/schemas.py`

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Actualizar import de `..models` para sumar `FormaPago`**

En el bloque `from .models import (...)`, agregar `FormaPago` alfabéticamente:

```python
from .models import (
    EstadoComprobante,
    EstadoExpensa,
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoReserva,
    EstadoTrabajo,
    FormaPago,
    Rol,
    Rubro,
)
```

- [ ] **Step 2: Agregar schemas de `GastoHabitual` al final del archivo**

```python
class GastoHabitualCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    rubro: Rubro
    clase_prorrateo_id: int = Field(..., gt=0)
    proveedor_id: int = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=500)
    monto: float = Field(..., gt=0)
    forma_pago: FormaPago


class GastoHabitualActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    rubro: Rubro | None = None
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    concepto: str | None = Field(default=None, min_length=1, max_length=500)
    monto: float | None = Field(default=None, gt=0)
    forma_pago: FormaPago | None = None
    activa: bool | None = None


class GastoHabitualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    rubro: Rubro
    clase_prorrateo_id: int
    proveedor_id: int
    concepto: str
    monto: float
    forma_pago: FormaPago
    activa: bool
```

- [ ] **Step 3: Agregar schemas de `Gasto` al final del archivo**

```python
_PERIODO_PATTERN_GASTO = r"^\d{4}-(0[1-9]|1[0-2])$"


class GastoCrear(BaseModel):
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
    rubro: Rubro
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    departamento_id: int | None = Field(default=None, gt=0)
    proveedor_id: int = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=500)
    monto: float = Field(..., gt=0)
    forma_pago: FormaPago
    fecha_pago: date
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_actual: int | None = Field(default=None, ge=1)
    cuota_total: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validar_clase_o_depto(self) -> "GastoCrear":
        tiene_clase = self.clase_prorrateo_id is not None
        tiene_depto = self.departamento_id is not None
        if tiene_clase == tiene_depto:
            raise ValueError(
                "Debe indicarse exactamente uno de `clase_prorrateo_id` "
                "o `departamento_id` (excluyentes)."
            )
        return self

    @model_validator(mode="after")
    def _validar_cuotas(self) -> "GastoCrear":
        a = self.cuota_actual
        t = self.cuota_total
        if (a is None) != (t is None):
            raise ValueError(
                "`cuota_actual` y `cuota_total` deben ir ambos o ninguno."
            )
        if a is not None and t is not None and a > t:
            raise ValueError("`cuota_actual` no puede exceder `cuota_total`.")
        return self


class GastoActualizar(BaseModel):
    periodo: str | None = Field(default=None, pattern=_PERIODO_PATTERN_GASTO)
    rubro: Rubro | None = None
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    departamento_id: int | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    concepto: str | None = Field(default=None, min_length=1, max_length=500)
    monto: float | None = Field(default=None, gt=0)
    forma_pago: FormaPago | None = None
    fecha_pago: date | None = None
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_actual: int | None = Field(default=None, ge=1)
    cuota_total: int | None = Field(default=None, ge=1)


class GastoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    periodo: str
    rubro: Rubro
    clase_prorrateo_id: int | None
    departamento_id: int | None
    proveedor_id: int
    concepto: str
    monto: float
    forma_pago: FormaPago
    fecha_pago: date
    numero_factura: str | None
    fecha_factura: date | None
    cuota_actual: int | None
    cuota_total: int | None
    gasto_habitual_id: int | None


class PlanCuotasCrear(BaseModel):
    """Body para POST /gastos/plan-cuotas. Reutiliza casi todos los campos de
    GastoCrear pero exige cuota_total ≥ 2 (uno solo no es un plan)."""
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
    rubro: Rubro
    clase_prorrateo_id: int | None = Field(default=None, gt=0)
    departamento_id: int | None = Field(default=None, gt=0)
    proveedor_id: int = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=500)
    monto: float = Field(..., gt=0)
    forma_pago: FormaPago
    fecha_pago: date
    numero_factura: str | None = Field(default=None, max_length=50)
    fecha_factura: date | None = None
    cuota_total: int = Field(..., ge=2)

    @model_validator(mode="after")
    def _validar_clase_o_depto(self) -> "PlanCuotasCrear":
        if (self.clase_prorrateo_id is None) == (self.departamento_id is None):
            raise ValueError(
                "Debe indicarse exactamente uno de `clase_prorrateo_id` "
                "o `departamento_id` (excluyentes)."
            )
        return self


class CargarHabitualesIn(BaseModel):
    periodo: str = Field(..., pattern=_PERIODO_PATTERN_GASTO)
```

- [ ] **Step 4: Verificar imports**

Run: `./.venv/Scripts/python.exe -c "from backend.schemas import GastoCrear, GastoActualizar, GastoOut, PlanCuotasCrear, GastoHabitualCrear, GastoHabitualActualizar, GastoHabitualOut, CargarHabitualesIn; print('OK')"`
Expected: imprime `OK`.

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 299 tests passing.

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py
git commit -m "feat(schemas): Gasto + GastoHabitual + PlanCuotasCrear + CargarHabitualesIn"
```

---

### Task 3: Extender `tests/conftest.py` con fixtures de Fase 2

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Agregar imports al bloque `from backend.models`**

```python
from backend.models import (  # noqa: E402
    Amenity,
    ClaseProrrateo,
    Comunicado,
    ConfiguracionConsorcio,
    Departamento,
    EstadoExpensa,
    EstadoPeticion,
    EstadoReserva,
    Expensa,
    FormaPago,
    Gasto,
    GastoHabitual,
    Peticion,
    Proveedor,
    Reserva,
    Rol,
    Rubro,
    Usuario,
)
```

- [ ] **Step 2: Sumar al `db.add_all([...])` final del `_seed()` un `GastoHabitual` y un `Gasto`**

Justo antes del `db.commit()` final, dentro del `db.add_all([...])` existente, agregar:

```python
            # Fase 2: plantilla habitual de ejemplo (id=700)
            GastoHabitual(
                id=700,
                nombre="Plantilla Test",
                rubro=Rubro.abonos_y_servicios,
                clase_prorrateo_id=500,  # clase A sembrada en Fase 1
                proveedor_id=600,  # proveedor sembrado en Fase 1
                concepto="Servicio mensual de prueba",
                monto=10000.0,
                forma_pago=FormaPago.transferencia,
                activa=True,
            ),
            # Fase 2: gasto puntual de ejemplo (id=800), prorrateable por clase A
            Gasto(
                id=800,
                periodo="2026-06",
                rubro=Rubro.servicios_publicos,
                clase_prorrateo_id=500,
                departamento_id=None,
                proveedor_id=600,
                concepto="Luz pasillos",
                monto=15000.0,
                forma_pago=FormaPago.transferencia,
                fecha_pago=date(2026, 6, 10),
                numero_factura=None,
                fecha_factura=None,
                cuota_actual=None,
                cuota_total=None,
                gasto_habitual_id=None,
            ),
```

- [ ] **Step 3: Verificar suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 299 tests passing.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): seed mínimo de GastoHabitual y Gasto"
```

---

## Fase B — Routers backend con TDD

### Task 4: Router `gastos_habituales` (TDD)

**Files:**
- Create: `tests/test_gastos_habituales.py`
- Create: `backend/routers/gastos_habituales.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crear `tests/test_gastos_habituales.py`**

```python
# ---------------------------------------------------------------------------
# GET /gastos-habituales
# ---------------------------------------------------------------------------


def test_listar_habituales_sin_token_devuelve_401(client):
    r = client.get("/gastos-habituales")
    assert r.status_code == 401


def test_listar_habituales_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/gastos-habituales", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_habituales_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/gastos-habituales", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    nombres = {h["nombre"] for h in data}
    assert "Plantilla Test" in nombres


def test_listar_habituales_filtra_por_activa(client, headers_admin):
    # Crear una inactiva.
    creada = client.post(
        "/gastos-habituales",
        json={
            "nombre": "Plantilla Inactiva",
            "rubro": "abonos_y_servicios",
            "clase_prorrateo_id": 500,
            "proveedor_id": 600,
            "concepto": "x",
            "monto": 1000,
            "forma_pago": "transferencia",
        },
        headers=headers_admin,
    ).json()
    client.patch(f"/gastos-habituales/{creada['id']}", json={"activa": False}, headers=headers_admin)

    r = client.get("/gastos-habituales?activa=true", headers=headers_admin)
    assert all(h["activa"] for h in r.json())

    r2 = client.get("/gastos-habituales?activa=false", headers=headers_admin)
    assert all(not h["activa"] for h in r2.json())


# ---------------------------------------------------------------------------
# POST /gastos-habituales
# ---------------------------------------------------------------------------


_NUEVA = {
    "nombre": "Sueldo Encargado",
    "rubro": "sueldos_y_cargas_sociales",
    "clase_prorrateo_id": 500,
    "proveedor_id": 600,
    "concepto": "Sueldo mensual",
    "monto": 800000,
    "forma_pago": "transferencia",
}


def test_crear_habitual_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/gastos-habituales", json=_NUEVA, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Sueldo Encargado"
    assert body["activa"] is True


def test_crear_habitual_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/gastos-habituales", json=_NUEVA, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_habitual_monto_negativo_devuelve_400(client, headers_admin):
    payload = dict(_NUEVA, monto=-1)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_habitual_clase_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_NUEVA, clase_prorrateo_id=9999)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_habitual_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_NUEVA, proveedor_id=9999)
    r = client.post("/gastos-habituales", json=payload, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /gastos-habituales/{id}
# ---------------------------------------------------------------------------


def test_obtener_habitual_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/gastos-habituales/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_habitual_existente_devuelve_200(client, headers_admin):
    r = client.get("/gastos-habituales/700", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Plantilla Test"


# ---------------------------------------------------------------------------
# PATCH /gastos-habituales/{id}
# ---------------------------------------------------------------------------


def test_patch_habitual_cambia_nombre(client, headers_admin):
    r = client.patch("/gastos-habituales/700", json={"nombre": "Renombrada"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Renombrada"


def test_patch_habitual_desactiva(client, headers_admin):
    r = client.patch("/gastos-habituales/700", json={"activa": False}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False


def test_patch_habitual_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/gastos-habituales/9999", json={"nombre": "x"}, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /gastos-habituales/{id}
# ---------------------------------------------------------------------------


def test_delete_habitual_sin_gastos_es_hard_delete(client, headers_admin):
    creada = client.post("/gastos-habituales", json=_NUEVA, headers=headers_admin).json()
    r = client.delete(f"/gastos-habituales/{creada['id']}", headers=headers_admin)
    assert r.status_code == 204

    r2 = client.get(f"/gastos-habituales/{creada['id']}", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_habitual_con_gastos_es_soft_delete(client, headers_admin, db_session):
    from backend.models import Gasto as GastoModel, FormaPago as FP, Rubro as R
    from datetime import date as d
    db_session.add(
        GastoModel(
            periodo="2026-06",
            rubro=R.abonos_y_servicios,
            clase_prorrateo_id=500,
            proveedor_id=600,
            concepto="generado",
            monto=1000,
            forma_pago=FP.transferencia,
            fecha_pago=d(2026, 6, 1),
            gasto_habitual_id=700,
        )
    )
    db_session.commit()

    r = client.delete("/gastos-habituales/700", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False

    r2 = client.get("/gastos-habituales/700", headers=headers_admin)
    assert r2.status_code == 200


def test_delete_habitual_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/gastos-habituales/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr tests para ver que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos_habituales.py -v`
Expected: FAIL en todos (router no existe).

- [ ] **Step 3: Crear `backend/routers/gastos_habituales.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import ClaseProrrateo, Gasto, GastoHabitual, Proveedor, Rol
from ..schemas import (
    GastoHabitualActualizar,
    GastoHabitualCrear,
    GastoHabitualOut,
)

router = APIRouter(prefix="/gastos-habituales", tags=["Gastos"])


def _validar_referencias(db: Session, clase_id: int, proveedor_id: int) -> None:
    if db.get(ClaseProrrateo, clase_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase de prorrateo indicada no existe.",
        )
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


@router.get(
    "",
    response_model=list[GastoHabitualOut],
    status_code=status.HTTP_200_OK,
    summary="Listar plantillas de gastos habituales",
)
def listar_habituales(
    activa: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[GastoHabitual]:
    stmt = select(GastoHabitual).order_by(GastoHabitual.nombre.asc())
    if activa is not None:
        stmt = stmt.where(GastoHabitual.activa == activa)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=GastoHabitualOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear plantilla de gasto habitual",
)
def crear_habitual(
    payload: GastoHabitualCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> GastoHabitual:
    _validar_referencias(db, payload.clase_prorrateo_id, payload.proveedor_id)

    plantilla = GastoHabitual(
        nombre=payload.nombre,
        rubro=payload.rubro,
        clase_prorrateo_id=payload.clase_prorrateo_id,
        proveedor_id=payload.proveedor_id,
        concepto=payload.concepto,
        monto=payload.monto,
        forma_pago=payload.forma_pago,
        activa=True,
    )
    db.add(plantilla)
    db.commit()
    db.refresh(plantilla)
    return plantilla


@router.get(
    "/{gasto_habitual_id}",
    response_model=GastoHabitualOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener plantilla",
)
def obtener_habitual(
    gasto_habitual_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> GastoHabitual:
    plantilla = db.get(GastoHabitual, gasto_habitual_id)
    if plantilla is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La plantilla solicitada no existe.",
        )
    return plantilla


@router.patch(
    "/{gasto_habitual_id}",
    response_model=GastoHabitualOut,
    status_code=status.HTTP_200_OK,
    summary="Editar plantilla",
)
def actualizar_habitual(
    gasto_habitual_id: int,
    payload: GastoHabitualActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> GastoHabitual:
    plantilla = db.get(GastoHabitual, gasto_habitual_id)
    if plantilla is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La plantilla solicitada no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)

    # Validar FKs si cambian.
    nueva_clase = cambios.get("clase_prorrateo_id", plantilla.clase_prorrateo_id)
    nuevo_prov = cambios.get("proveedor_id", plantilla.proveedor_id)
    if "clase_prorrateo_id" in cambios or "proveedor_id" in cambios:
        _validar_referencias(db, nueva_clase, nuevo_prov)

    for campo, valor in cambios.items():
        setattr(plantilla, campo, valor)

    db.commit()
    db.refresh(plantilla)
    return plantilla


@router.delete(
    "/{gasto_habitual_id}",
    response_model=GastoHabitualOut | None,
    status_code=status.HTTP_200_OK,
    summary="Eliminar plantilla (hard si no tiene gastos; soft si tiene)",
)
def eliminar_habitual(
    gasto_habitual_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    plantilla = db.get(GastoHabitual, gasto_habitual_id)
    if plantilla is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La plantilla solicitada no existe.",
        )

    tiene_gastos = (
        db.scalar(select(Gasto.id).where(Gasto.gasto_habitual_id == gasto_habitual_id))
        is not None
    )

    if tiene_gastos:
        plantilla.activa = False
        db.commit()
        db.refresh(plantilla)
        return plantilla

    db.delete(plantilla)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Registrar router en `backend/main.py`**

Sumar `gastos_habituales` al import alfabético y al final de los `include_router`:

```python
from .routers import (
    amenities,
    auth,
    clases_prorrateo,
    comprobantes,
    comunicados,
    configuracion,
    departamentos,
    expensas,
    gastos_habituales,
    peticiones,
    proveedores,
    reservas,
    trabajos,
    usuarios,
)
```

Y agregar `app.include_router(gastos_habituales.router)` después del último include.

- [ ] **Step 5: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos_habituales.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: tests del archivo nuevos verdes + suite completa verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_gastos_habituales.py backend/routers/gastos_habituales.py backend/main.py
git commit -m "feat(gastos-habituales): CRUD admin-only con soft/hard delete según gastos asociados"
```

---

### Task 5: Router `gastos` — CRUD básico (TDD)

**Files:**
- Create: `tests/test_gastos.py`
- Create: `backend/routers/gastos.py`
- Modify: `backend/main.py`

> Endpoints en este task: GET / POST / GET id / PATCH / DELETE. Los endpoints `/plan-cuotas` y `/cargar-habituales` se suman en Tasks 6 y 7 respectivamente.

- [ ] **Step 1: Crear `tests/test_gastos.py` con tests del CRUD básico**

```python
from datetime import date


_GASTO_VALIDO = {
    "periodo": "2026-06",
    "rubro": "servicios_publicos",
    "clase_prorrateo_id": 500,
    "departamento_id": None,
    "proveedor_id": 600,
    "concepto": "Agua AYSA",
    "monto": 30000,
    "forma_pago": "transferencia",
    "fecha_pago": "2026-06-15",
}


# ---------------------------------------------------------------------------
# GET /gastos
# ---------------------------------------------------------------------------


def test_listar_gastos_sin_token_devuelve_401(client):
    r = client.get("/gastos")
    assert r.status_code == 401


def test_listar_gastos_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/gastos", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_gastos_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/gastos", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    conceptos = {g["concepto"] for g in data}
    assert "Luz pasillos" in conceptos


def test_listar_gastos_filtra_periodo(client, headers_admin):
    r = client.get("/gastos?periodo=2026-06", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["periodo"] == "2026-06" for g in r.json())


def test_listar_gastos_filtra_rubro(client, headers_admin):
    r = client.get("/gastos?rubro=servicios_publicos", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["rubro"] == "servicios_publicos" for g in r.json())


def test_listar_gastos_filtra_clase(client, headers_admin):
    r = client.get("/gastos?clase_prorrateo_id=500", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["clase_prorrateo_id"] == 500 for g in r.json())


def test_listar_gastos_filtra_proveedor(client, headers_admin):
    r = client.get("/gastos?proveedor_id=600", headers=headers_admin)
    assert r.status_code == 200
    assert all(g["proveedor_id"] == 600 for g in r.json())


# ---------------------------------------------------------------------------
# POST /gastos — happy paths y validaciones
# ---------------------------------------------------------------------------


def test_crear_gasto_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["concepto"] == "Agua AYSA"
    assert body["monto"] == 30000
    assert body["gasto_habitual_id"] is None


def test_crear_gasto_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/gastos", json=_GASTO_VALIDO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_gasto_clase_y_depto_juntos_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=500, departamento_id=1)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_ni_clase_ni_depto_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=None, departamento_id=None)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_particular_a_depto_es_201(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=None, departamento_id=1)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["departamento_id"] == 1
    assert r.json()["clase_prorrateo_id"] is None


def test_crear_gasto_monto_cero_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, monto=0)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_cuota_actual_sin_total_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, cuota_actual=1)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_cuota_actual_mayor_total_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, cuota_actual=5, cuota_total=3)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_periodo_invalido_devuelve_400(client, headers_admin):
    payload = dict(_GASTO_VALIDO, periodo="2026-13")
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_gasto_clase_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=9999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_gasto_depto_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, clase_prorrateo_id=None, departamento_id=9999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_gasto_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, proveedor_id=9999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /gastos/{id}
# ---------------------------------------------------------------------------


def test_obtener_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/gastos/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_gasto_existente_devuelve_200(client, headers_admin):
    r = client.get("/gastos/800", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["concepto"] == "Luz pasillos"


# ---------------------------------------------------------------------------
# PATCH /gastos/{id}
# ---------------------------------------------------------------------------


def test_patch_gasto_cambia_monto(client, headers_admin):
    r = client.patch("/gastos/800", json={"monto": 20000}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["monto"] == 20000


def test_patch_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/gastos/9999", json={"monto": 1}, headers=headers_admin)
    assert r.status_code == 404


def test_patch_gasto_monto_negativo_devuelve_400(client, headers_admin):
    r = client.patch("/gastos/800", json={"monto": -1}, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /gastos/{id}
# ---------------------------------------------------------------------------


def test_delete_gasto_es_hard_delete(client, headers_admin):
    r = client.delete("/gastos/800", headers=headers_admin)
    assert r.status_code == 204

    r2 = client.get("/gastos/800", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/gastos/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr tests para confirmar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v`
Expected: FAIL en todos (router no existe).

- [ ] **Step 3: Crear `backend/routers/gastos.py` con el CRUD básico**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    ClaseProrrateo,
    Departamento,
    Gasto,
    Proveedor,
    Rol,
    Rubro,
)
from ..schemas import GastoActualizar, GastoCrear, GastoOut

router = APIRouter(prefix="/gastos", tags=["Gastos"])


def _validar_referencias(
    db: Session,
    clase_id: int | None,
    depto_id: int | None,
    proveedor_id: int,
) -> None:
    if clase_id is not None and db.get(ClaseProrrateo, clase_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase de prorrateo indicada no existe.",
        )
    if depto_id is not None and db.get(Departamento, depto_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


_PERIODO_PATTERN_GASTO = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get(
    "",
    response_model=list[GastoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar gastos del consorcio",
)
def listar_gastos(
    periodo: str | None = Query(default=None, pattern=_PERIODO_PATTERN_GASTO),
    rubro: Rubro | None = Query(default=None),
    clase_prorrateo_id: int | None = Query(default=None, gt=0),
    departamento_id: int | None = Query(default=None, gt=0),
    proveedor_id: int | None = Query(default=None, gt=0),
    gasto_habitual_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Gasto]:
    stmt = select(Gasto).order_by(Gasto.fecha_pago.desc(), Gasto.id.desc())
    if periodo is not None:
        stmt = stmt.where(Gasto.periodo == periodo)
    if rubro is not None:
        stmt = stmt.where(Gasto.rubro == rubro)
    if clase_prorrateo_id is not None:
        stmt = stmt.where(Gasto.clase_prorrateo_id == clase_prorrateo_id)
    if departamento_id is not None:
        stmt = stmt.where(Gasto.departamento_id == departamento_id)
    if proveedor_id is not None:
        stmt = stmt.where(Gasto.proveedor_id == proveedor_id)
    if gasto_habitual_id is not None:
        stmt = stmt.where(Gasto.gasto_habitual_id == gasto_habitual_id)
    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=GastoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un gasto",
)
def crear_gasto(
    payload: GastoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Gasto:
    _validar_referencias(
        db,
        payload.clase_prorrateo_id,
        payload.departamento_id,
        payload.proveedor_id,
    )

    gasto = Gasto(
        periodo=payload.periodo,
        rubro=payload.rubro,
        clase_prorrateo_id=payload.clase_prorrateo_id,
        departamento_id=payload.departamento_id,
        proveedor_id=payload.proveedor_id,
        concepto=payload.concepto,
        monto=payload.monto,
        forma_pago=payload.forma_pago,
        fecha_pago=payload.fecha_pago,
        numero_factura=payload.numero_factura,
        fecha_factura=payload.fecha_factura,
        cuota_actual=payload.cuota_actual,
        cuota_total=payload.cuota_total,
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


@router.get(
    "/{gasto_id}",
    response_model=GastoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener gasto",
)
def obtener_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    return gasto


@router.patch(
    "/{gasto_id}",
    response_model=GastoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar gasto",
)
def actualizar_gasto(
    gasto_id: int,
    payload: GastoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)

    # Validar excluyencia clase/depto si alguno cambia.
    nueva_clase = cambios.get("clase_prorrateo_id", gasto.clase_prorrateo_id)
    nuevo_depto = cambios.get("departamento_id", gasto.departamento_id)
    if (nueva_clase is None) == (nuevo_depto is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe indicarse exactamente uno de `clase_prorrateo_id` o `departamento_id`.",
        )

    # Validar consistencia de cuotas si alguno cambia.
    nueva_ca = cambios.get("cuota_actual", gasto.cuota_actual)
    nuevo_ct = cambios.get("cuota_total", gasto.cuota_total)
    if (nueva_ca is None) != (nuevo_ct is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`cuota_actual` y `cuota_total` deben ir ambos o ninguno.",
        )
    if nueva_ca is not None and nuevo_ct is not None and nueva_ca > nuevo_ct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`cuota_actual` no puede exceder `cuota_total`.",
        )

    nuevo_prov = cambios.get("proveedor_id", gasto.proveedor_id)
    if (
        "clase_prorrateo_id" in cambios
        or "departamento_id" in cambios
        or "proveedor_id" in cambios
    ):
        _validar_referencias(db, nueva_clase, nuevo_depto, nuevo_prov)

    for campo, valor in cambios.items():
        setattr(gasto, campo, valor)

    db.commit()
    db.refresh(gasto)
    return gasto


@router.delete(
    "/{gasto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar gasto",
)
def eliminar_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Response:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    db.delete(gasto)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Registrar router en `backend/main.py`**

Sumar `gastos` al import alfabético y `app.include_router(gastos.router)` después del último include:

```python
from .routers import (
    amenities,
    auth,
    clases_prorrateo,
    comprobantes,
    comunicados,
    configuracion,
    departamentos,
    expensas,
    gastos,
    gastos_habituales,
    peticiones,
    proveedores,
    reservas,
    trabajos,
    usuarios,
)
```

- [ ] **Step 5: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: tests verdes + suite completa verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_gastos.py backend/routers/gastos.py backend/main.py
git commit -m "feat(gastos): CRUD admin-only con validación clase/depto excluyente y cuotas"
```

---

### Task 6: Endpoint `POST /gastos/plan-cuotas` (TDD)

**Files:**
- Modify: `tests/test_gastos.py` (sumar bloque)
- Modify: `backend/routers/gastos.py`

> Genera N gastos consecutivos a partir de un plan. Cuota i tiene `cuota_actual=i+1`, `cuota_total=N`, `periodo=periodo_base + i meses`, `fecha_pago=fecha_pago_base + i meses`.

- [ ] **Step 1: Sumar tests al final de `tests/test_gastos.py`**

```python
# ---------------------------------------------------------------------------
# POST /gastos/plan-cuotas
# ---------------------------------------------------------------------------


_PLAN_VALIDO = {
    "periodo": "2026-06",
    "rubro": "abonos_y_servicios",
    "clase_prorrateo_id": 500,
    "departamento_id": None,
    "proveedor_id": 600,
    "concepto": "Seguro anual",
    "monto": 50000,
    "forma_pago": "transferencia",
    "fecha_pago": "2026-06-10",
    "cuota_total": 3,
}


def test_plan_cuotas_sin_token_devuelve_401(client):
    r = client.post("/gastos/plan-cuotas", json=_PLAN_VALIDO)
    assert r.status_code == 401


def test_plan_cuotas_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/gastos/plan-cuotas", json=_PLAN_VALIDO, headers=headers_depto_a)
    assert r.status_code == 403


def test_plan_cuotas_crea_n_gastos_consecutivos(client, headers_admin):
    r = client.post("/gastos/plan-cuotas", json=_PLAN_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    gastos = r.json()
    assert len(gastos) == 3

    # Períodos consecutivos.
    assert [g["periodo"] for g in gastos] == ["2026-06", "2026-07", "2026-08"]

    # Cuotas numeradas correctamente.
    assert [g["cuota_actual"] for g in gastos] == [1, 2, 3]
    assert all(g["cuota_total"] == 3 for g in gastos)

    # Fechas de pago desplazadas 1 mes.
    assert [g["fecha_pago"] for g in gastos] == ["2026-06-10", "2026-07-10", "2026-08-10"]

    # Mismo concepto, monto, proveedor.
    assert all(g["concepto"] == "Seguro anual" for g in gastos)
    assert all(g["monto"] == 50000 for g in gastos)


def test_plan_cuotas_total_uno_devuelve_400(client, headers_admin):
    payload = dict(_PLAN_VALIDO, cuota_total=1)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_plan_cuotas_clase_y_depto_juntos_devuelve_400(client, headers_admin):
    payload = dict(_PLAN_VALIDO, clase_prorrateo_id=500, departamento_id=1)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_plan_cuotas_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_PLAN_VALIDO, proveedor_id=9999)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_plan_cuotas_cruza_anio(client, headers_admin):
    # Empezando en noviembre, 3 cuotas → nov, dic, ene del año siguiente.
    payload = dict(_PLAN_VALIDO, periodo="2026-11", fecha_pago="2026-11-15", cuota_total=3)
    r = client.post("/gastos/plan-cuotas", json=payload, headers=headers_admin)
    assert r.status_code == 201
    gastos = r.json()
    assert [g["periodo"] for g in gastos] == ["2026-11", "2026-12", "2027-01"]
    assert [g["fecha_pago"] for g in gastos] == ["2026-11-15", "2026-12-15", "2027-01-15"]
```

- [ ] **Step 2: Correr tests para confirmar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v -k plan_cuotas`
Expected: FAIL (endpoint no existe).

- [ ] **Step 3: Sumar imports y endpoint en `backend/routers/gastos.py`**

Agregar al import de `..schemas`:

```python
from ..schemas import GastoActualizar, GastoCrear, GastoOut, PlanCuotasCrear
```

Agregar este helper auxiliar al tope del archivo (después de los imports, antes de `_validar_referencias`):

```python
def _sumar_un_mes(periodo: str) -> str:
    """Recibe 'YYYY-MM' y devuelve el mes siguiente como 'YYYY-MM'."""
    anio, mes = map(int, periodo.split("-"))
    mes += 1
    if mes == 13:
        mes = 1
        anio += 1
    return f"{anio:04d}-{mes:02d}"


def _sumar_un_mes_date(fecha: date) -> date:
    """Suma un mes a la fecha. Si el día no existe en el mes siguiente
    (ej. 31 de enero → febrero), usa el último día del mes."""
    import calendar
    anio = fecha.year
    mes = fecha.month + 1
    if mes == 13:
        mes = 1
        anio += 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    dia = min(fecha.day, ultimo_dia)
    return date(anio, mes, dia)
```

Y sumar la importación de `date` y `Gasto` ya existentes (verificar). Si `date` no está importado, agregarlo:

```python
from datetime import date
```

Agregar el endpoint al final del archivo (después de `eliminar_gasto`):

```python
@router.post(
    "/plan-cuotas",
    response_model=list[GastoOut],
    status_code=status.HTTP_201_CREATED,
    summary="Crear plan de N cuotas (genera N gastos consecutivos)",
)
def crear_plan_cuotas(
    payload: PlanCuotasCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Gasto]:
    _validar_referencias(
        db,
        payload.clase_prorrateo_id,
        payload.departamento_id,
        payload.proveedor_id,
    )

    gastos: list[Gasto] = []
    periodo_actual = payload.periodo
    fecha_actual = payload.fecha_pago

    for i in range(payload.cuota_total):
        gasto = Gasto(
            periodo=periodo_actual,
            rubro=payload.rubro,
            clase_prorrateo_id=payload.clase_prorrateo_id,
            departamento_id=payload.departamento_id,
            proveedor_id=payload.proveedor_id,
            concepto=payload.concepto,
            monto=payload.monto,
            forma_pago=payload.forma_pago,
            fecha_pago=fecha_actual,
            numero_factura=payload.numero_factura,
            fecha_factura=payload.fecha_factura,
            cuota_actual=i + 1,
            cuota_total=payload.cuota_total,
        )
        db.add(gasto)
        gastos.append(gasto)

        periodo_actual = _sumar_un_mes(periodo_actual)
        fecha_actual = _sumar_un_mes_date(fecha_actual)

    db.commit()
    for g in gastos:
        db.refresh(g)
    return gastos
```

- [ ] **Step 4: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gastos.py backend/routers/gastos.py
git commit -m "feat(gastos): endpoint /plan-cuotas genera N gastos consecutivos"
```

---

### Task 7: Endpoint `POST /gastos/cargar-habituales` (TDD)

**Files:**
- Modify: `tests/test_gastos.py` (sumar bloque)
- Modify: `backend/routers/gastos.py`

> Idempotente: por cada plantilla activa, crea un gasto del período solo si aún no existe `(periodo, gasto_habitual_id=plantilla.id)`.

- [ ] **Step 1: Sumar tests al final de `tests/test_gastos.py`**

```python
# ---------------------------------------------------------------------------
# POST /gastos/cargar-habituales
# ---------------------------------------------------------------------------


def test_cargar_habituales_sin_token_devuelve_401(client):
    r = client.post("/gastos/cargar-habituales", json={"periodo": "2026-07"})
    assert r.status_code == 401


def test_cargar_habituales_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_cargar_habituales_genera_un_gasto_por_plantilla_activa(client, headers_admin):
    # En el seed hay 1 plantilla activa (id=700).
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    generados = r.json()
    assert len(generados) == 1
    assert generados[0]["periodo"] == "2026-07"
    assert generados[0]["gasto_habitual_id"] == 700
    assert generados[0]["concepto"] == "Servicio mensual de prueba"
    assert generados[0]["monto"] == 10000


def test_cargar_habituales_es_idempotente(client, headers_admin):
    # Primera llamada genera 1.
    r1 = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert len(r1.json()) == 1

    # Segunda llamada no genera nada (ya existe).
    r2 = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    assert r2.status_code == 201
    assert r2.json() == []


def test_cargar_habituales_ignora_plantillas_inactivas(client, headers_admin):
    # Desactivar la plantilla 700.
    client.patch("/gastos-habituales/700", json={"activa": False}, headers=headers_admin)

    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-08"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json() == []


def test_cargar_habituales_periodo_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "abc"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_cargar_habituales_usa_fecha_primer_dia_del_periodo(client, headers_admin):
    r = client.post(
        "/gastos/cargar-habituales",
        json={"periodo": "2026-07"},
        headers=headers_admin,
    )
    generado = r.json()[0]
    assert generado["fecha_pago"] == "2026-07-01"
```

- [ ] **Step 2: Correr tests para confirmar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v -k cargar_habituales`
Expected: FAIL (endpoint no existe).

- [ ] **Step 3: Sumar imports y endpoint en `backend/routers/gastos.py`**

Agregar `GastoHabitual` al import de `..models`:

```python
from ..models import (
    ClaseProrrateo,
    Departamento,
    Gasto,
    GastoHabitual,
    Proveedor,
    Rol,
    Rubro,
)
```

Agregar `CargarHabitualesIn` al import de `..schemas`:

```python
from ..schemas import (
    CargarHabitualesIn,
    GastoActualizar,
    GastoCrear,
    GastoOut,
    PlanCuotasCrear,
)
```

Agregar el endpoint al final del archivo (después de `crear_plan_cuotas`):

```python
@router.post(
    "/cargar-habituales",
    response_model=list[GastoOut],
    status_code=status.HTTP_201_CREATED,
    summary="Materializar plantillas habituales activas en un período (idempotente)",
)
def cargar_habituales(
    payload: CargarHabitualesIn,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Gasto]:
    anio, mes = map(int, payload.periodo.split("-"))
    fecha_pago_default = date(anio, mes, 1)

    # Plantillas activas que aún no tienen gasto generado en este período.
    plantillas_activas = db.scalars(
        select(GastoHabitual).where(GastoHabitual.activa == True)  # noqa: E712
    ).all()

    ids_ya_generadas = set(
        db.scalars(
            select(Gasto.gasto_habitual_id).where(
                Gasto.periodo == payload.periodo,
                Gasto.gasto_habitual_id.is_not(None),
            )
        ).all()
    )

    nuevos: list[Gasto] = []
    for plantilla in plantillas_activas:
        if plantilla.id in ids_ya_generadas:
            continue
        gasto = Gasto(
            periodo=payload.periodo,
            rubro=plantilla.rubro,
            clase_prorrateo_id=plantilla.clase_prorrateo_id,
            departamento_id=None,
            proveedor_id=plantilla.proveedor_id,
            concepto=plantilla.concepto,
            monto=plantilla.monto,
            forma_pago=plantilla.forma_pago,
            fecha_pago=fecha_pago_default,
            gasto_habitual_id=plantilla.id,
        )
        db.add(gasto)
        nuevos.append(gasto)

    db.commit()
    for g in nuevos:
        db.refresh(g)
    return nuevos
```

- [ ] **Step 4: Correr tests + suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gastos.py backend/routers/gastos.py
git commit -m "feat(gastos): endpoint /cargar-habituales materializa plantillas activas (idempotente)"
```

---

## Fase C — OpenAPI

### Task 8: Documentar endpoints nuevos en `openapi.yaml`

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Agregar paths nuevos antes del bloque `# COMPONENTS`**

Localizar el bloque `# ===========================================================================\n# COMPONENTS` en `openapi.yaml` y, justo antes de él, agregar:

```yaml
  /gastos:
    get:
      tags: [Gastos]
      summary: Listar gastos del consorcio (admin)
      security: [{ bearerAuth: [] }]
      parameters:
        - in: query
          name: periodo
          required: false
          schema: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        - in: query
          name: rubro
          required: false
          schema: { type: string }
        - in: query
          name: clase_prorrateo_id
          required: false
          schema: { type: integer, minimum: 1 }
        - in: query
          name: departamento_id
          required: false
          schema: { type: integer, minimum: 1 }
        - in: query
          name: proveedor_id
          required: false
          schema: { type: integer, minimum: 1 }
        - in: query
          name: gasto_habitual_id
          required: false
          schema: { type: integer, minimum: 1 }
        - in: query
          name: limit
          required: false
          schema: { type: integer, minimum: 1, maximum: 200, default: 50 }
        - in: query
          name: offset
          required: false
          schema: { type: integer, minimum: 0, default: 0 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/GastoOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
    post:
      tags: [Gastos]
      summary: Crear un gasto (admin)
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/GastoCrear' }
      responses:
        '201':
          description: Creado
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /gastos/plan-cuotas:
    post:
      tags: [Gastos]
      summary: Crear plan de N cuotas (admin)
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/PlanCuotasCrear' }
      responses:
        '201':
          description: N gastos creados
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/GastoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /gastos/cargar-habituales:
    post:
      tags: [Gastos]
      summary: Materializar plantillas habituales activas en un período (admin)
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CargarHabitualesIn' }
      responses:
        '201':
          description: Lista de gastos generados (puede ser vacía si todos ya estaban).
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/GastoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }

  /gastos/{gasto_id}:
    parameters:
      - in: path
        name: gasto_id
        required: true
        schema: { type: integer }
    get:
      tags: [Gastos]
      summary: Obtener gasto
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Gastos]
      summary: Editar gasto
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/GastoActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Gastos]
      summary: Eliminar gasto
      security: [{ bearerAuth: [] }]
      responses:
        '204': { description: Eliminado }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /gastos-habituales:
    get:
      tags: [Gastos]
      summary: Listar plantillas (admin)
      security: [{ bearerAuth: [] }]
      parameters:
        - in: query
          name: activa
          required: false
          schema: { type: boolean }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/GastoHabitualOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
    post:
      tags: [Gastos]
      summary: Crear plantilla
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/GastoHabitualCrear' }
      responses:
        '201':
          description: Creada
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoHabitualOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /gastos-habituales/{gasto_habitual_id}:
    parameters:
      - in: path
        name: gasto_habitual_id
        required: true
        schema: { type: integer }
    get:
      tags: [Gastos]
      summary: Obtener plantilla
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoHabitualOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Gastos]
      summary: Editar plantilla
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/GastoHabitualActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoHabitualOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Gastos]
      summary: Eliminar plantilla (hard si no tiene gastos; soft si tiene)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: Soft-delete
          content:
            application/json:
              schema: { $ref: '#/components/schemas/GastoHabitualOut' }
        '204': { description: Hard-delete }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/AccesoDenegado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
```

> Si el tag `Gastos` aún no existe en la sección `tags:` del comienzo del archivo, sumarlo:
> ```yaml
>   - name: Gastos
>     description: Gastos del consorcio y plantillas recurrentes
> ```

- [ ] **Step 2: Agregar schemas nuevos al final de `openapi.yaml`**

```bash
cat >> openapi.yaml <<'EOF'

    GastoOut:
      type: object
      required: [id, periodo, rubro, proveedor_id, concepto, monto, forma_pago, fecha_pago]
      properties:
        id: { type: integer }
        periodo: { type: string }
        rubro: { type: string }
        clase_prorrateo_id: { type: integer, nullable: true }
        departamento_id: { type: integer, nullable: true }
        proveedor_id: { type: integer }
        concepto: { type: string }
        monto: { type: number }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]
        fecha_pago: { type: string, format: date }
        numero_factura: { type: string, nullable: true }
        fecha_factura: { type: string, format: date, nullable: true }
        cuota_actual: { type: integer, nullable: true }
        cuota_total: { type: integer, nullable: true }
        gasto_habitual_id: { type: integer, nullable: true }

    GastoCrear:
      type: object
      required: [periodo, rubro, proveedor_id, concepto, monto, forma_pago, fecha_pago]
      properties:
        periodo: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        rubro: { type: string }
        clase_prorrateo_id: { type: integer, minimum: 1, nullable: true }
        departamento_id: { type: integer, minimum: 1, nullable: true }
        proveedor_id: { type: integer, minimum: 1 }
        concepto: { type: string, minLength: 1, maxLength: 500 }
        monto: { type: number, exclusiveMinimum: 0 }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]
        fecha_pago: { type: string, format: date }
        numero_factura: { type: string, maxLength: 50, nullable: true }
        fecha_factura: { type: string, format: date, nullable: true }
        cuota_actual: { type: integer, minimum: 1, nullable: true }
        cuota_total: { type: integer, minimum: 1, nullable: true }

    GastoActualizar:
      type: object
      properties:
        periodo: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$', nullable: true }
        rubro: { type: string, nullable: true }
        clase_prorrateo_id: { type: integer, minimum: 1, nullable: true }
        departamento_id: { type: integer, minimum: 1, nullable: true }
        proveedor_id: { type: integer, minimum: 1, nullable: true }
        concepto: { type: string, minLength: 1, maxLength: 500, nullable: true }
        monto: { type: number, exclusiveMinimum: 0, nullable: true }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]
          nullable: true
        fecha_pago: { type: string, format: date, nullable: true }
        numero_factura: { type: string, maxLength: 50, nullable: true }
        fecha_factura: { type: string, format: date, nullable: true }
        cuota_actual: { type: integer, minimum: 1, nullable: true }
        cuota_total: { type: integer, minimum: 1, nullable: true }

    PlanCuotasCrear:
      type: object
      required: [periodo, rubro, proveedor_id, concepto, monto, forma_pago, fecha_pago, cuota_total]
      properties:
        periodo: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }
        rubro: { type: string }
        clase_prorrateo_id: { type: integer, minimum: 1, nullable: true }
        departamento_id: { type: integer, minimum: 1, nullable: true }
        proveedor_id: { type: integer, minimum: 1 }
        concepto: { type: string, minLength: 1, maxLength: 500 }
        monto: { type: number, exclusiveMinimum: 0 }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]
        fecha_pago: { type: string, format: date }
        numero_factura: { type: string, maxLength: 50, nullable: true }
        fecha_factura: { type: string, format: date, nullable: true }
        cuota_total: { type: integer, minimum: 2 }

    CargarHabitualesIn:
      type: object
      required: [periodo]
      properties:
        periodo: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }

    GastoHabitualOut:
      type: object
      required: [id, nombre, rubro, clase_prorrateo_id, proveedor_id, concepto, monto, forma_pago, activa]
      properties:
        id: { type: integer }
        nombre: { type: string }
        rubro: { type: string }
        clase_prorrateo_id: { type: integer }
        proveedor_id: { type: integer }
        concepto: { type: string }
        monto: { type: number }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]
        activa: { type: boolean }

    GastoHabitualCrear:
      type: object
      required: [nombre, rubro, clase_prorrateo_id, proveedor_id, concepto, monto, forma_pago]
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120 }
        rubro: { type: string }
        clase_prorrateo_id: { type: integer, minimum: 1 }
        proveedor_id: { type: integer, minimum: 1 }
        concepto: { type: string, minLength: 1, maxLength: 500 }
        monto: { type: number, exclusiveMinimum: 0 }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]

    GastoHabitualActualizar:
      type: object
      properties:
        nombre: { type: string, minLength: 1, maxLength: 120, nullable: true }
        rubro: { type: string, nullable: true }
        clase_prorrateo_id: { type: integer, minimum: 1, nullable: true }
        proveedor_id: { type: integer, minimum: 1, nullable: true }
        concepto: { type: string, minLength: 1, maxLength: 500, nullable: true }
        monto: { type: number, exclusiveMinimum: 0, nullable: true }
        forma_pago:
          type: string
          enum: [transferencia, debito_automatico, cheque, efectivo, otro]
          nullable: true
        activa: { type: boolean, nullable: true }
EOF
```

- [ ] **Step 3: Validar YAML**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 4: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): endpoints de gastos, gastos-habituales, plan-cuotas y cargar-habituales"
```

---

## Fase D — Seed inicial

### Task 9: Extender `backend/seed.py` con plantillas y gastos de ejemplo

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Actualizar imports**

```python
from .models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    ConfiguracionConsorcio,
    Departamento,
    EstadoPeticion,
    FormaPago,
    Gasto,
    GastoHabitual,
    Peticion,
    Proveedor,
    Rol,
    Rubro,
    Usuario,
)
```

- [ ] **Step 2: Sumar bloque de seed de gastos al final, después del `db.add(ConfiguracionConsorcio(...))` existente y antes del `db.add_all([Peticion(...), ...])`**

```python
    # ----- Fase 2: plantillas de gastos habituales -----
    # Tomamos proveedores sembrados por id (orden de creación = orden alfabético del seed).
    proveedores_seed = db.scalars(
        select(Proveedor).order_by(Proveedor.id)
    ).all()
    prov_limpieza = proveedores_seed[0]
    prov_ascensor = proveedores_seed[1]
    prov_admin = proveedores_seed[4]

    plantilla_sueldo = GastoHabitual(
        nombre="Sueldo encargado",
        rubro=Rubro.sueldos_y_cargas_sociales,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_admin.id,
        concepto="Sueldo mensual del encargado",
        monto=800000.0,
        forma_pago=FormaPago.transferencia,
        activa=True,
    )
    plantilla_limpieza = GastoHabitual(
        nombre="Servicio de limpieza",
        rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_limpieza.id,
        concepto="Limpieza mensual de áreas comunes",
        monto=200000.0,
        forma_pago=FormaPago.transferencia,
        activa=True,
    )
    plantilla_ascensor = GastoHabitual(
        nombre="Mantenimiento ascensores",
        rubro=Rubro.abonos_y_servicios,
        clase_prorrateo_id=clase_a.id,
        proveedor_id=prov_ascensor.id,
        concepto="Mantenimiento mensual de ascensores",
        monto=50000.0,
        forma_pago=FormaPago.transferencia,
        activa=True,
    )
    db.add_all([plantilla_sueldo, plantilla_limpieza, plantilla_ascensor])
    db.flush()

    # ----- Fase 2: gastos puntuales de ejemplo (período 2026-06) -----
    from datetime import date as _date

    db.add_all([
        # Generado a partir de plantilla.
        Gasto(
            periodo="2026-06",
            rubro=Rubro.sueldos_y_cargas_sociales,
            clase_prorrateo_id=clase_a.id,
            proveedor_id=prov_admin.id,
            concepto="Sueldo mensual del encargado",
            monto=800000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=_date(2026, 6, 1),
            gasto_habitual_id=plantilla_sueldo.id,
        ),
        # Prorrateable puntual.
        Gasto(
            periodo="2026-06",
            rubro=Rubro.mantenimiento_partes_comunes,
            clase_prorrateo_id=clase_a.id,
            proveedor_id=prov_limpieza.id,
            concepto="Reparación cañería común",
            monto=120000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=_date(2026, 6, 8),
        ),
        # Particular a un depto.
        Gasto(
            periodo="2026-06",
            rubro=Rubro.trabajos_reparaciones_unidades,
            departamento_id=depto_a.id,
            proveedor_id=prov_limpieza.id,
            concepto="Arreglo plomería - UF 1A",
            monto=80000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=_date(2026, 6, 12),
        ),
        # En cuotas (cuota 1/3 cargada manualmente).
        Gasto(
            periodo="2026-06",
            rubro=Rubro.seguros,
            clase_prorrateo_id=clase_a.id,
            proveedor_id=prov_admin.id,
            concepto="Seguro anual - Cuota 1/3",
            monto=70000.0,
            forma_pago=FormaPago.transferencia,
            fecha_pago=_date(2026, 6, 5),
            cuota_actual=1,
            cuota_total=3,
        ),
    ])
```

- [ ] **Step 3: Verificar que el seed corre y que la suite sigue verde**

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
from backend.models import Gasto, GastoHabitual
db = SessionLocal()
print('gastos:', db.query(Gasto).count())
print('habituales:', db.query(GastoHabitual).count())
db.close()
"
```
Expected: `gastos: 4`, `habituales: 3`.

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: suite verde.

- [ ] **Step 4: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): 3 plantillas habituales y 4 gastos puntuales de ejemplo"
```

---

## Fase E — Frontend

### Task 10: API clients

**Files:**
- Create: `frontend/src/api/gastos.js`
- Create: `frontend/src/api/gastosHabituales.js`

- [ ] **Step 1: Crear `frontend/src/api/gastos.js`**

```javascript
import { apiFetch } from "./client";

export function listarGastos(filtros = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== null && v !== undefined && v !== "") qs.set(k, v);
  }
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/gastos${suffix}`);
}

export function crearGasto(payload) {
  return apiFetch("/gastos", { method: "POST", body: payload });
}

export function crearPlanCuotas(payload) {
  return apiFetch("/gastos/plan-cuotas", { method: "POST", body: payload });
}

export function cargarGastosHabituales(periodo) {
  return apiFetch("/gastos/cargar-habituales", {
    method: "POST",
    body: { periodo },
  });
}

export function obtenerGasto(id) {
  return apiFetch(`/gastos/${id}`);
}

export function actualizarGasto(id, payload) {
  return apiFetch(`/gastos/${id}`, { method: "PATCH", body: payload });
}

export function eliminarGasto(id) {
  return apiFetch(`/gastos/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Crear `frontend/src/api/gastosHabituales.js`**

```javascript
import { apiFetch } from "./client";

export function listarGastosHabituales({ activa } = {}) {
  const qs = activa === undefined ? "" : `?activa=${activa}`;
  return apiFetch(`/gastos-habituales${qs}`);
}

export function crearGastoHabitual(payload) {
  return apiFetch("/gastos-habituales", { method: "POST", body: payload });
}

export function obtenerGastoHabitual(id) {
  return apiFetch(`/gastos-habituales/${id}`);
}

export function actualizarGastoHabitual(id, payload) {
  return apiFetch(`/gastos-habituales/${id}`, { method: "PATCH", body: payload });
}

export function eliminarGastoHabitual(id) {
  return apiFetch(`/gastos-habituales/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/gastos.js frontend/src/api/gastosHabituales.js
git commit -m "feat(frontend/api): clients para gastos y gastos-habituales"
```

---

### Task 11: Componente `Tabs` reutilizable + CSS

**Files:**
- Create: `frontend/src/components/Tabs.jsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Crear `frontend/src/components/Tabs.jsx`**

```jsx
import { NavLink } from "react-router-dom";

// tabs: array de { path, label, end? }
// end=true en NavLink hace que el activo se evalúe con match exacto (evita que
// el tab "default" /gastos quede activo también cuando estás en /gastos/habituales).
export default function Tabs({ tabs }) {
  return (
    <nav className="tabs" aria-label="Subnavegación">
      {tabs.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.end}
          className={({ isActive }) => (isActive ? "tab activo" : "tab")}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Agregar estilos al final de `frontend/src/index.css`**

```css
/* Tabs reutilizables (mobile-first) */
.tabs {
  display: flex;
  margin-block-end: 1rem;
  border-bottom: 1px solid var(--color-text);
}
.tab {
  flex: 1;
  padding: 0.75rem 1rem;
  min-height: 44px;
  text-align: center;
  text-decoration: none;
  color: var(--color-text);
  border-bottom: 3px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}
.tab.activo {
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}
@media (min-width: 600px) {
  .tabs {
    justify-content: flex-start;
  }
  .tab {
    flex: 0 0 auto;
    min-width: 140px;
  }
}
```

- [ ] **Step 3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Tabs.jsx frontend/src/index.css
git commit -m "feat(frontend): componente Tabs reutilizable (mobile-first)"
```

---

### Task 12: Pantalla `/gastos` — tab Únicos

**Files:**
- Create: `frontend/src/screens/Gastos.jsx`

> Lista de gastos con filtros + modal "Nuevo gasto". El modal soporta carga normal y plan en cuotas (checkbox).

- [ ] **Step 1: Crear `frontend/src/screens/Gastos.jsx`**

```jsx
import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import Tabs from "../components/Tabs";
import {
  listarGastos,
  crearGasto,
  crearPlanCuotas,
  actualizarGasto,
  eliminarGasto,
  cargarGastosHabituales,
} from "../api/gastos";
import { listarClasesProrrateo } from "../api/clasesProrrateo";
import { listarProveedores } from "../api/proveedores";
import { listarDepartamentos } from "../api/departamentos";

const RUBROS = [
  { value: "sueldos_y_cargas_sociales", label: "Sueldos y cargas sociales" },
  { value: "servicios_publicos", label: "Servicios públicos" },
  { value: "abonos_y_servicios", label: "Abonos y servicios" },
  { value: "mantenimiento_partes_comunes", label: "Mantenimiento partes comunes" },
  { value: "trabajos_reparaciones_unidades", label: "Trabajos en unidades" },
  { value: "gastos_bancarios", label: "Gastos bancarios" },
  { value: "gastos_administracion", label: "Gastos de administración" },
  { value: "seguros", label: "Seguros" },
  { value: "gastos_generales", label: "Gastos generales" },
];

const FORMAS_PAGO = [
  { value: "transferencia", label: "Transferencia" },
  { value: "debito_automatico", label: "Débito automático" },
  { value: "cheque", label: "Cheque" },
  { value: "efectivo", label: "Efectivo" },
  { value: "otro", label: "Otro" },
];

const TABS = [
  { path: "/gastos", label: "Únicos", end: true },
  { path: "/gastos/habituales", label: "Habituales" },
];

function labelRubro(value) {
  return RUBROS.find((r) => r.value === value)?.label || value;
}

export default function Gastos() {
  const [gastos, setGastos] = useState([]);
  const [clases, setClases] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [departamentos, setDepartamentos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);

  const [filtros, setFiltros] = useState({
    periodo: "",
    rubro: "",
    clase_prorrateo_id: "",
    proveedor_id: "",
    departamento_id: "",
  });

  async function cargarCatalogos() {
    const [rClases, rProv, rDeptos] = await Promise.all([
      listarClasesProrrateo({ activa: true }),
      listarProveedores({ activo: true }),
      listarDepartamentos(),
    ]);
    if (rClases.status === 200) setClases(rClases.data);
    if (rProv.status === 200) setProveedores(rProv.data);
    if (rDeptos.status === 200) setDepartamentos(rDeptos.data);
  }

  async function recargar() {
    setCargando(true);
    const r = await listarGastos(filtros);
    if (r.status === 200) {
      setGastos(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los gastos.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [
    filtros.periodo,
    filtros.rubro,
    filtros.clase_prorrateo_id,
    filtros.proveedor_id,
    filtros.departamento_id,
  ]);

  function cambiarFiltro(campo, valor) {
    setFiltros({ ...filtros, [campo]: valor });
  }

  async function handleCargarHabituales() {
    if (!filtros.periodo) {
      setError("Seleccioná un período antes de cargar gastos habituales.");
      return;
    }
    const r = await cargarGastosHabituales(filtros.periodo);
    if (r.status === 201) {
      recargar();
      const n = r.data.length;
      setError(n === 0 ? "No había habituales nuevos para cargar." : null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los habituales.");
    }
  }

  async function handleBorrar(g) {
    if (!confirm(`¿Eliminar el gasto "${g.concepto}"?`)) return;
    const r = await eliminarGasto(g.id);
    if (r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "No se pudo eliminar.");
  }

  function proveedorPorId(id) {
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  function clasePorId(id) {
    return clases.find((c) => c.id === id)?.codigo || "—";
  }

  function deptoPorId(id) {
    const d = departamentos.find((x) => x.id === id);
    return d ? d.codigo : "—";
  }

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Gastos</h2>
      </header>
      <Tabs tabs={TABS} />

      <section className="filtros-gastos">
        <label>Período <input
          type="text"
          placeholder="2026-06"
          value={filtros.periodo}
          onChange={(e) => cambiarFiltro("periodo", e.target.value)}
        /></label>
        <label>Rubro <select
          value={filtros.rubro}
          onChange={(e) => cambiarFiltro("rubro", e.target.value)}
        >
          <option value="">Todos</option>
          {RUBROS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select></label>
        <label>Clase <select
          value={filtros.clase_prorrateo_id}
          onChange={(e) => cambiarFiltro("clase_prorrateo_id", e.target.value)}
        >
          <option value="">Todas</option>
          {clases.map((c) => <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
        </select></label>
        <label>Proveedor <select
          value={filtros.proveedor_id}
          onChange={(e) => cambiarFiltro("proveedor_id", e.target.value)}
        >
          <option value="">Todos</option>
          {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
        </select></label>
        <label>Departamento <select
          value={filtros.departamento_id}
          onChange={(e) => cambiarFiltro("departamento_id", e.target.value)}
        >
          <option value="">Todos</option>
          {departamentos.map((d) => <option key={d.id} value={d.id}>{d.codigo}</option>)}
        </select></label>
      </section>

      <div className="cabecera-acciones">
        <button type="button" onClick={handleCargarHabituales} disabled={!filtros.periodo}>
          Cargar gastos habituales del mes
        </button>
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          + Nuevo gasto
        </button>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {cargando && <p>Cargando…</p>}
      {!cargando && gastos.length === 0 && <p>No hay gastos con esos filtros.</p>}

      <ul className="lista-gastos">
        {gastos.map((g) => (
          <li key={g.id}>
            <Tarjeta>
              <h3>{labelRubro(g.rubro)} · {g.concepto}</h3>
              <p className="meta">
                ${g.monto.toLocaleString("es-AR")} · {g.periodo} · pagó {g.fecha_pago}
              </p>
              <p className="meta">Proveedor: {proveedorPorId(g.proveedor_id)}</p>
              <p className="meta">
                {g.clase_prorrateo_id !== null
                  ? <>Clase {clasePorId(g.clase_prorrateo_id)}</>
                  : <>Particular a {deptoPorId(g.departamento_id)}</>}
                {g.cuota_actual && <> · Cuota {g.cuota_actual}/{g.cuota_total}</>}
                {g.gasto_habitual_id && <> · Habitual</>}
              </p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", gasto: g })}>
                  Editar
                </button>
                <button type="button" className="boton-borrar" onClick={() => handleBorrar(g)}>
                  Eliminar
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal && (
        <ModalGasto
          tipo={modal.tipo}
          gastoInicial={modal.gasto}
          clases={clases}
          proveedores={proveedores}
          departamentos={departamentos}
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

function ModalGasto({ tipo, gastoInicial, clases, proveedores, departamentos, onCerrar, onGuardado }) {
  const esEditar = tipo === "editar";
  const inicial = gastoInicial
    ? {
        periodo: gastoInicial.periodo,
        rubro: gastoInicial.rubro,
        modo: gastoInicial.clase_prorrateo_id !== null ? "clase" : "depto",
        clase_prorrateo_id: gastoInicial.clase_prorrateo_id ?? "",
        departamento_id: gastoInicial.departamento_id ?? "",
        proveedor_id: gastoInicial.proveedor_id,
        concepto: gastoInicial.concepto,
        monto: String(gastoInicial.monto),
        forma_pago: gastoInicial.forma_pago,
        fecha_pago: gastoInicial.fecha_pago,
        numero_factura: gastoInicial.numero_factura || "",
        fecha_factura: gastoInicial.fecha_factura || "",
        cuota_actual: gastoInicial.cuota_actual ?? "",
        cuota_total: gastoInicial.cuota_total ?? "",
        es_plan: false,
        cuota_total_plan: "",
      }
    : {
        periodo: "",
        rubro: "abonos_y_servicios",
        modo: "clase",
        clase_prorrateo_id: clases[0]?.id ?? "",
        departamento_id: "",
        proveedor_id: proveedores[0]?.id ?? "",
        concepto: "",
        monto: "",
        forma_pago: "transferencia",
        fecha_pago: "",
        numero_factura: "",
        fecha_factura: "",
        cuota_actual: "",
        cuota_total: "",
        es_plan: false,
        cuota_total_plan: "",
      };

  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function set(campo, valor) {
    setForm({ ...form, [campo]: valor });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);

    const base = {
      periodo: form.periodo,
      rubro: form.rubro,
      clase_prorrateo_id: form.modo === "clase" ? Number(form.clase_prorrateo_id) : null,
      departamento_id: form.modo === "depto" ? Number(form.departamento_id) : null,
      proveedor_id: Number(form.proveedor_id),
      concepto: form.concepto,
      monto: Number(form.monto),
      forma_pago: form.forma_pago,
      fecha_pago: form.fecha_pago,
      numero_factura: form.numero_factura || null,
      fecha_factura: form.fecha_factura || null,
    };

    let r;
    if (esEditar) {
      r = await actualizarGasto(gastoInicial.id, {
        ...base,
        cuota_actual: form.cuota_actual ? Number(form.cuota_actual) : null,
        cuota_total: form.cuota_total ? Number(form.cuota_total) : null,
      });
      if (r.status === 200) {
        onGuardado();
        return;
      }
    } else if (form.es_plan) {
      r = await crearPlanCuotas({
        ...base,
        cuota_total: Number(form.cuota_total_plan),
      });
      if (r.status === 201) {
        onGuardado();
        return;
      }
    } else {
      r = await crearGasto({
        ...base,
        cuota_actual: form.cuota_actual ? Number(form.cuota_actual) : null,
        cuota_total: form.cuota_total ? Number(form.cuota_total) : null,
      });
      if (r.status === 201) {
        onGuardado();
        return;
      }
    }

    setError(r.data?.detail || "No se pudo guardar.");
    setGuardando(false);
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{esEditar ? "Editar gasto" : "Nuevo gasto"}</h3>
        <form onSubmit={onSubmit}>
          <label>Período <input
            type="text"
            placeholder="2026-06"
            value={form.periodo}
            onChange={(e) => set("periodo", e.target.value)}
            pattern="\d{4}-(0[1-9]|1[0-2])"
            required
          /></label>

          <label>Rubro <select value={form.rubro} onChange={(e) => set("rubro", e.target.value)} required>
            {RUBROS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select></label>

          <fieldset>
            <legend>Tipo de prorrateo</legend>
            <label>
              <input type="radio" name="modo" value="clase"
                checked={form.modo === "clase"} onChange={() => set("modo", "clase")} />
              Se prorratea (clase)
            </label>
            <label>
              <input type="radio" name="modo" value="depto"
                checked={form.modo === "depto"} onChange={() => set("modo", "depto")} />
              Particular a un departamento
            </label>
            {form.modo === "clase" && (
              <select value={form.clase_prorrateo_id}
                onChange={(e) => set("clase_prorrateo_id", e.target.value)} required>
                {clases.map((c) => <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
              </select>
            )}
            {form.modo === "depto" && (
              <select value={form.departamento_id}
                onChange={(e) => set("departamento_id", e.target.value)} required>
                <option value="">— Elegí uno —</option>
                {departamentos.map((d) => <option key={d.id} value={d.id}>{d.codigo}</option>)}
              </select>
            )}
          </fieldset>

          <label>Proveedor <select value={form.proveedor_id}
            onChange={(e) => set("proveedor_id", e.target.value)} required>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select></label>

          <label>Concepto <textarea value={form.concepto}
            onChange={(e) => set("concepto", e.target.value)} maxLength={500} required /></label>

          <label>Monto <input type="number" min="0.01" step="0.01"
            value={form.monto} onChange={(e) => set("monto", e.target.value)} required /></label>

          <label>Forma de pago <select value={form.forma_pago}
            onChange={(e) => set("forma_pago", e.target.value)} required>
            {FORMAS_PAGO.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select></label>

          <label>Fecha de pago <input type="date"
            value={form.fecha_pago} onChange={(e) => set("fecha_pago", e.target.value)} required /></label>

          <label>N° de factura (opcional) <input type="text" maxLength={50}
            value={form.numero_factura} onChange={(e) => set("numero_factura", e.target.value)} /></label>

          <label>Fecha de factura (opcional) <input type="date"
            value={form.fecha_factura} onChange={(e) => set("fecha_factura", e.target.value)} /></label>

          {!esEditar && (
            <fieldset>
              <legend>Plan de cuotas</legend>
              <label>
                <input type="checkbox"
                  checked={form.es_plan}
                  onChange={(e) => set("es_plan", e.target.checked)} />
                Es en cuotas (replicar a N períodos consecutivos)
              </label>
              {form.es_plan && (
                <label>Total de cuotas <input type="number" min="2"
                  value={form.cuota_total_plan}
                  onChange={(e) => set("cuota_total_plan", e.target.value)} required /></label>
              )}
            </fieldset>
          )}

          {esEditar && (
            <fieldset>
              <legend>Cuota (si aplica)</legend>
              <label>Cuota actual <input type="number" min="1"
                value={form.cuota_actual} onChange={(e) => set("cuota_actual", e.target.value)} /></label>
              <label>Cuota total <input type="number" min="1"
                value={form.cuota_total} onChange={(e) => set("cuota_total", e.target.value)} /></label>
            </fieldset>
          )}

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Sumar estilos al final de `frontend/src/index.css`**

```css
/* Pantalla Gastos */
.filtros-gastos {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-block-end: 1rem;
}
.filtros-gastos label {
  display: flex;
  flex-direction: column;
  font-size: 0.9rem;
  gap: 0.25rem;
}
.filtros-gastos input,
.filtros-gastos select {
  min-height: 44px;
  padding: 0.5rem;
}
.lista-gastos {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
@media (min-width: 960px) {
  .filtros-gastos {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .filtros-gastos label {
    flex: 1 1 200px;
  }
}
```

- [ ] **Step 3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/Gastos.jsx frontend/src/index.css
git commit -m "feat(frontend): pantalla Gastos (tab Únicos) con filtros, modal y plan de cuotas"
```

---

### Task 13: Pantalla `/gastos/habituales` — tab Habituales

**Files:**
- Create: `frontend/src/screens/GastosHabituales.jsx`

- [ ] **Step 1: Crear `frontend/src/screens/GastosHabituales.jsx`**

```jsx
import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import Tabs from "../components/Tabs";
import {
  listarGastosHabituales,
  crearGastoHabitual,
  actualizarGastoHabitual,
  eliminarGastoHabitual,
} from "../api/gastosHabituales";
import { listarClasesProrrateo } from "../api/clasesProrrateo";
import { listarProveedores } from "../api/proveedores";

const RUBROS = [
  { value: "sueldos_y_cargas_sociales", label: "Sueldos y cargas sociales" },
  { value: "servicios_publicos", label: "Servicios públicos" },
  { value: "abonos_y_servicios", label: "Abonos y servicios" },
  { value: "mantenimiento_partes_comunes", label: "Mantenimiento partes comunes" },
  { value: "trabajos_reparaciones_unidades", label: "Trabajos en unidades" },
  { value: "gastos_bancarios", label: "Gastos bancarios" },
  { value: "gastos_administracion", label: "Gastos de administración" },
  { value: "seguros", label: "Seguros" },
  { value: "gastos_generales", label: "Gastos generales" },
];

const FORMAS_PAGO = [
  { value: "transferencia", label: "Transferencia" },
  { value: "debito_automatico", label: "Débito automático" },
  { value: "cheque", label: "Cheque" },
  { value: "efectivo", label: "Efectivo" },
  { value: "otro", label: "Otro" },
];

const TABS = [
  { path: "/gastos", label: "Únicos", end: true },
  { path: "/gastos/habituales", label: "Habituales" },
];

function labelRubro(value) {
  return RUBROS.find((r) => r.value === value)?.label || value;
}

export default function GastosHabituales() {
  const [habituales, setHabituales] = useState([]);
  const [clases, setClases] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivas, setMostrarInactivas] = useState(false);
  const [modal, setModal] = useState(null);

  async function cargarCatalogos() {
    const [rClases, rProv] = await Promise.all([
      listarClasesProrrateo({ activa: true }),
      listarProveedores({ activo: true }),
    ]);
    if (rClases.status === 200) setClases(rClases.data);
    if (rProv.status === 200) setProveedores(rProv.data);
  }

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivas ? { activa: false } : { activa: true };
    const r = await listarGastosHabituales(filtro);
    if (r.status === 200) {
      setHabituales(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar las plantillas.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [mostrarInactivas]);

  async function toggleActiva(h) {
    const r = await actualizarGastoHabitual(h.id, { activa: !h.activa });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  async function borrar(h) {
    if (!confirm(`¿Eliminar la plantilla "${h.nombre}"?`)) return;
    const r = await eliminarGastoHabitual(h.id);
    if (r.status === 200 || r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al eliminar.");
  }

  function proveedorPorId(id) {
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  function clasePorId(id) {
    return clases.find((c) => c.id === id)?.codigo || "—";
  }

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Gastos</h2>
      </header>
      <Tabs tabs={TABS} />

      <div className="cabecera-acciones">
        <label className="filtro-checkbox">
          <input
            type="checkbox"
            checked={mostrarInactivas}
            onChange={(e) => setMostrarInactivas(e.target.checked)}
          />
          Mostrar inactivas
        </label>
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          + Nueva plantilla
        </button>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {cargando && <p>Cargando…</p>}
      {!cargando && habituales.length === 0 && <p>No hay plantillas para mostrar.</p>}

      <ul className="lista-config">
        {habituales.map((h) => (
          <li key={h.id}>
            <Tarjeta>
              <h3>{h.nombre} — ${h.monto.toLocaleString("es-AR")}</h3>
              <p className="meta">Rubro: {labelRubro(h.rubro)}</p>
              <p className="meta">Clase: {clasePorId(h.clase_prorrateo_id)}</p>
              <p className="meta">Proveedor: {proveedorPorId(h.proveedor_id)}</p>
              <p className="meta">Estado: {h.activa ? "Activa" : "Inactiva"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", habitual: h })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActiva(h)}>
                  {h.activa ? "Desactivar" : "Activar"}
                </button>
                <button type="button" className="boton-borrar" onClick={() => borrar(h)}>
                  Eliminar
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal && (
        <ModalHabitual
          tipo={modal.tipo}
          inicial={modal.habitual}
          clases={clases}
          proveedores={proveedores}
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

function ModalHabitual({ tipo, inicial, clases, proveedores, onCerrar, onGuardado }) {
  const esEditar = tipo === "editar";
  const valorInicial = inicial
    ? {
        nombre: inicial.nombre,
        rubro: inicial.rubro,
        clase_prorrateo_id: inicial.clase_prorrateo_id,
        proveedor_id: inicial.proveedor_id,
        concepto: inicial.concepto,
        monto: String(inicial.monto),
        forma_pago: inicial.forma_pago,
      }
    : {
        nombre: "",
        rubro: "abonos_y_servicios",
        clase_prorrateo_id: clases[0]?.id ?? "",
        proveedor_id: proveedores[0]?.id ?? "",
        concepto: "",
        monto: "",
        forma_pago: "transferencia",
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
      nombre: form.nombre,
      rubro: form.rubro,
      clase_prorrateo_id: Number(form.clase_prorrateo_id),
      proveedor_id: Number(form.proveedor_id),
      concepto: form.concepto,
      monto: Number(form.monto),
      forma_pago: form.forma_pago,
    };

    const r = esEditar
      ? await actualizarGastoHabitual(inicial.id, payload)
      : await crearGastoHabitual(payload);

    if (r.status === 200 || r.status === 201) {
      onGuardado();
      return;
    }
    setError(r.data?.detail || "No se pudo guardar.");
    setGuardando(false);
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{esEditar ? "Editar plantilla" : "Nueva plantilla"}</h3>
        <form onSubmit={onSubmit}>
          <label>Nombre <input value={form.nombre}
            onChange={(e) => set("nombre", e.target.value)} maxLength={120} required /></label>

          <label>Rubro <select value={form.rubro}
            onChange={(e) => set("rubro", e.target.value)} required>
            {RUBROS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select></label>

          <label>Clase <select value={form.clase_prorrateo_id}
            onChange={(e) => set("clase_prorrateo_id", e.target.value)} required>
            {clases.map((c) => <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
          </select></label>

          <label>Proveedor <select value={form.proveedor_id}
            onChange={(e) => set("proveedor_id", e.target.value)} required>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select></label>

          <label>Concepto <textarea value={form.concepto}
            onChange={(e) => set("concepto", e.target.value)} maxLength={500} required /></label>

          <label>Monto <input type="number" min="0.01" step="0.01"
            value={form.monto} onChange={(e) => set("monto", e.target.value)} required /></label>

          <label>Forma de pago <select value={form.forma_pago}
            onChange={(e) => set("forma_pago", e.target.value)} required>
            {FORMAS_PAGO.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select></label>

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar"}
            </button>
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
git add frontend/src/screens/GastosHabituales.jsx
git commit -m "feat(frontend): pantalla GastosHabituales (tab Habituales) con CRUD"
```

---

### Task 14: Rutas + Sidebar

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Agregar imports y rutas en `App.jsx`**

En la zona de imports de pantallas, agregar:

```javascript
import Gastos from "./screens/Gastos";
import GastosHabituales from "./screens/GastosHabituales";
```

Dentro del `<Routes>`, en el grupo de rutas protegidas (dentro del Route parent `/` con `AppLayout`), agregar:

```jsx
<Route path="gastos" element={<Gastos />} />
<Route path="gastos/habituales" element={<GastosHabituales />} />
```

Colocarlas antes del `<Route path="*" element={<NotFound />} />`.

- [ ] **Step 2: Sumar item al sidebar en `Sidebar.jsx`**

Dentro del array `SECCIONES`, en la sección "Expensas y pagos", agregar `Gastos` como tercer item:

```javascript
  {
    titulo: "Expensas y pagos",
    modulos: [
      {
        ruta: "/expensas",
        nombre: "Expensas",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/comprobantes",
        nombre: "Comprobantes",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/gastos",
        nombre: "Gastos",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
```

- [ ] **Step 3: Smoke test manual del frontend**

Arrancar backend + frontend en dos terminales:
- `./.venv/Scripts/python.exe -m uvicorn backend.main:app --reload --port 8000`
- `cd frontend && npm run dev`

En el navegador:
1. Login como admin.
2. Sidebar muestra "Gastos" en "Expensas y pagos".
3. Clic en "Gastos" → ves tab "Únicos" activo + tab "Habituales".
4. Listado muestra 4 gastos del seed con filtros funcionales (probar filtro por período "2026-06").
5. Botón "+ Nuevo gasto" abre modal → crear un gasto puntual prorrateable → aparece en la lista.
6. Marcar "Es en cuotas" + total=3 → submit → aparecen 3 gastos consecutivos.
7. Filtrar por período "2026-08" → clic "Cargar gastos habituales del mes" → aparecen 3 gastos generados.
8. Repetir clic en "Cargar habituales" → mensaje "No había habituales nuevos para cargar."
9. Cambiar a tab "Habituales" → ves las 3 plantillas. Crear una nueva → aparece. Desactivar y reactivar.
10. Logout. Login como depto-a → sidebar NO muestra "Gastos".

Expected: todo funciona. Si algo falla, debug y arreglar antes de continuar.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat(frontend): rutas /gastos y /gastos/habituales + item en sidebar (admin-only)"
```

---

## Fase F — Verificación final y merge

### Task 15: Smoke test full + merge

- [ ] **Step 1: Correr suite backend completa**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos los tests en verde, sin warnings nuevos.

- [ ] **Step 2: Build de producción frontend**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Validar OpenAPI**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 4: Revisar diff del branch**

Run: `git log master..HEAD --oneline`
Expected: lista de commits (uno por task).

Run: `git diff master..HEAD --stat`
Expected: archivos modificados con +/- por archivo.

- [ ] **Step 5: Consultar al usuario sobre merge**

> "Fase 2 terminada y verificada. Suite verde + build OK + smoke test manual OK. ¿Mergeo a master con `--no-ff` o preferís revisar el diff antes?"

Esperar respuesta. Si confirma:

```bash
git checkout master
git merge --no-ff feature/expensas-fase2 -m "Merge feature/expensas-fase2: gastos del consorcio (Fase 2)"
git branch -d feature/expensas-fase2
```
