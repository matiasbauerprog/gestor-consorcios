# Expensas — Fase 1: modelo de datos central — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introducir Rubros (enum), Clases de Prorrateo (CRUD), Coeficientes múltiples por depto (N:M), Proveedores (CRUD con soft-delete) y Configuración del Consorcio (singleton). Backend completo + 4 pantallas admin. Sin tocar `Expensa`/`Comprobante` (queda para Fase 4).

**Architecture:** Modelos nuevos en `backend/models.py`. Schemas en `backend/schemas.py`. 3 routers nuevos (`clases_prorrateo`, `proveedores`, `configuracion`) + extensión de `departamentos` con sub-endpoints de coeficientes. Frontend con 4 pantallas nuevas en sección "Configuración" del sidebar (admin-only). Clean start de DB (`consorcio.db` borrado y re-sembrado).

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + SQLite. React + Vite. Tests con pytest. Sin nuevas dependencias.

**Spec:** [docs/superpowers/specs/2026-06-16-expensas-fase1-modelo-central-design.md](../specs/2026-06-16-expensas-fase1-modelo-central-design.md)

**Errores de validación:** el proyecto convierte `RequestValidationError` (Pydantic) a HTTP **400**, no 422. Ver `backend/main.py:67`. Los tests asertan 400.

---

## Setup inicial

### Task 0: Branch + estado limpio

- [ ] **Step 1: Verificar estado y crear branch**

Run: `git status && git branch --show-current`
Expected: rama `master`, working tree limpio (los `package.json` / `package-lock.json` untracked pueden quedar).

```bash
git checkout -b feature/expensas-fase1
```

- [ ] **Step 2: Borrar `consorcio.db` local (clean start)**

Confirmar primero que `uvicorn` está detenido. Si está corriendo, detenerlo (Ctrl+C).

Run: `rm -f consorcio.db`
Expected: ningún output, comando exitoso.

- [ ] **Step 3: Confirmar que tests pasan en baseline**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos los tests existentes en verde (241 aprox). Si falla algo, parar y avisar.

---

## Fase A — Backend foundation

### Task 1: Modelos nuevos en `backend/models.py`

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Agregar el enum `Rubro` al final del bloque de enums**

En `backend/models.py`, después del último enum existente (`EstadoReserva`) y antes de la primera clase de tabla (`Departamento`), agregar:

```python
class Rubro(str, enum.Enum):
    sueldos_y_cargas_sociales = "sueldos_y_cargas_sociales"
    servicios_publicos = "servicios_publicos"
    abonos_y_servicios = "abonos_y_servicios"
    mantenimiento_partes_comunes = "mantenimiento_partes_comunes"
    trabajos_reparaciones_unidades = "trabajos_reparaciones_unidades"
    gastos_bancarios = "gastos_bancarios"
    gastos_administracion = "gastos_administracion"
    seguros = "seguros"
    gastos_generales = "gastos_generales"
```

- [ ] **Step 2: Agregar `ClaseProrrateo` al final del archivo**

```python
class ClaseProrrateo(Base):
    __tablename__ = "clases_prorrateo"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
        back_populates="clase"
    )
```

- [ ] **Step 3: Agregar `CoeficienteDepartamento` al final del archivo**

```python
class CoeficienteDepartamento(Base):
    __tablename__ = "coeficientes_departamento"
    __table_args__ = (
        UniqueConstraint(
            "departamento_id", "clase_prorrateo_id", name="uq_coef_depto_clase"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(
        ForeignKey("departamentos.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    clase_prorrateo_id: Mapped[int] = mapped_column(
        ForeignKey("clases_prorrateo.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)

    departamento: Mapped["Departamento"] = relationship(back_populates="coeficientes")
    clase: Mapped["ClaseProrrateo"] = relationship(back_populates="coeficientes")
```

- [ ] **Step 4: Agregar relación `coeficientes` a `Departamento`**

En la clase `Departamento` existente, después de la relación `expensas`, agregar:

```python
    coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
        back_populates="departamento", cascade="all, delete-orphan"
    )
```

- [ ] **Step 5: Agregar `Proveedor` al final del archivo**

```python
class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_fantasia: Mapped[str | None] = mapped_column(String(255))
    cuit: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 6: Agregar `ConfiguracionConsorcio` al final del archivo**

```python
class ConfiguracionConsorcio(Base):
    __tablename__ = "configuracion_consorcio"

    id: Mapped[int] = mapped_column(primary_key=True)

    # consorcio
    consorcio_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    consorcio_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    consorcio_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    consorcio_convenio_suterh: Mapped[str | None] = mapped_column(String(50))

    # administración
    admin_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_telefono: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    admin_rpa: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_situacion_fiscal: Mapped[str] = mapped_column(String(100), nullable=False)

    # banco
    banco_titular: Mapped[str] = mapped_column(String(255), nullable=False)
    banco_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    banco_sucursal: Mapped[str | None] = mapped_column(String(50))
    banco_numero_cuenta: Mapped[str] = mapped_column(String(50), nullable=False)
    banco_cbu: Mapped[str] = mapped_column(String(22), nullable=False)
    banco_alias: Mapped[str | None] = mapped_column(String(50))
```

- [ ] **Step 7: Verificar que la app importa OK**

Run: `./.venv/Scripts/python.exe -c "from backend.models import ClaseProrrateo, CoeficienteDepartamento, Proveedor, ConfiguracionConsorcio, Rubro; print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 8: Verificar que los tests existentes siguen pasando**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde (los tests existentes no deberían romperse — solo agregamos tablas nuevas).

- [ ] **Step 9: Commit**

```bash
git add backend/models.py
git commit -m "feat(models): Rubro enum + ClaseProrrateo + CoeficienteDepartamento + Proveedor + ConfiguracionConsorcio"
```

---

### Task 2: Schemas Pydantic en `backend/schemas.py`

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Agregar import al tope si falta**

En el bloque de imports de `..models`, sumar:

```python
from .models import (
    EstadoComprobante,
    EstadoExpensa,
    EstadoPeticion,
    EstadoPresupuesto,
    EstadoReserva,
    EstadoTrabajo,
    Rol,
    Rubro,  # ← nuevo
)
```

- [ ] **Step 2: Agregar schemas de `ClaseProrrateo` al final del archivo**

```python
class ClaseProrrateoCrear(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=8)
    nombre: str = Field(..., min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)


class ClaseProrrateoActualizar(BaseModel):
    # codigo es inmutable
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=500)
    activa: bool | None = None


class ClaseProrrateoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    descripcion: str | None
    activa: bool
```

- [ ] **Step 3: Agregar schemas de `Proveedor`**

```python
_CUIT_PATTERN = r"^\d{2}-\d{8}-\d{1}$"


class ProveedorCrear(BaseModel):
    razon_social: str = Field(..., min_length=1, max_length=255)
    nombre_fantasia: str | None = Field(default=None, max_length=255)
    cuit: str = Field(..., pattern=_CUIT_PATTERN)
    direccion: str | None = Field(default=None, max_length=500)


class ProveedorActualizar(BaseModel):
    # cuit es inmutable
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    nombre_fantasia: str | None = Field(default=None, max_length=255)
    direccion: str | None = Field(default=None, max_length=500)
    activo: bool | None = None


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    razon_social: str
    nombre_fantasia: str | None
    cuit: str
    direccion: str | None
    activo: bool
```

- [ ] **Step 4: Agregar schemas de `ConfiguracionConsorcio`**

```python
class ConfiguracionConsorcioActualizar(BaseModel):
    consorcio_nombre: str = Field(..., min_length=1, max_length=255)
    consorcio_domicilio: str = Field(..., min_length=1, max_length=500)
    consorcio_cuit: str = Field(..., pattern=_CUIT_PATTERN)
    consorcio_convenio_suterh: str | None = Field(default=None, max_length=50)

    admin_nombre: str = Field(..., min_length=1, max_length=255)
    admin_domicilio: str = Field(..., min_length=1, max_length=500)
    admin_email: str = Field(..., min_length=3, max_length=255)
    admin_telefono: str = Field(..., min_length=1, max_length=50)
    admin_cuit: str = Field(..., pattern=_CUIT_PATTERN)
    admin_rpa: str = Field(..., min_length=1, max_length=50)
    admin_situacion_fiscal: str = Field(..., min_length=1, max_length=100)

    banco_titular: str = Field(..., min_length=1, max_length=255)
    banco_nombre: str = Field(..., min_length=1, max_length=100)
    banco_sucursal: str | None = Field(default=None, max_length=50)
    banco_numero_cuenta: str = Field(..., min_length=1, max_length=50)
    banco_cbu: str = Field(..., min_length=22, max_length=22)
    banco_alias: str | None = Field(default=None, max_length=50)


class ConfiguracionConsorcioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consorcio_nombre: str
    consorcio_domicilio: str
    consorcio_cuit: str
    consorcio_convenio_suterh: str | None
    admin_nombre: str
    admin_domicilio: str
    admin_email: str
    admin_telefono: str
    admin_cuit: str
    admin_rpa: str
    admin_situacion_fiscal: str
    banco_titular: str
    banco_nombre: str
    banco_sucursal: str | None
    banco_numero_cuenta: str
    banco_cbu: str
    banco_alias: str | None
```

- [ ] **Step 5: Agregar schemas de coeficientes**

```python
class CoeficienteItem(BaseModel):
    clase_prorrateo_id: int = Field(..., gt=0)
    porcentaje: float = Field(..., ge=0, le=100)


class CoeficientesReemplazar(BaseModel):
    coeficientes: list[CoeficienteItem]

    @model_validator(mode="after")
    def _validar_clases_unicas(self) -> "CoeficientesReemplazar":
        ids = [c.clase_prorrateo_id for c in self.coeficientes]
        if len(ids) != len(set(ids)):
            raise ValueError("No puede repetirse `clase_prorrateo_id` en el payload.")
        return self


class CoeficienteOut(BaseModel):
    clase_prorrateo_id: int
    codigo: str
    nombre: str
    porcentaje: float
```

- [ ] **Step 6: Verificar imports**

Run: `./.venv/Scripts/python.exe -c "from backend.schemas import ClaseProrrateoCrear, ProveedorCrear, ConfiguracionConsorcioOut, CoeficientesReemplazar; print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 7: Commit**

```bash
git add backend/schemas.py
git commit -m "feat(schemas): schemas de ClaseProrrateo, Proveedor, ConfiguracionConsorcio y coeficientes"
```

---

### Task 3: Extender `tests/conftest.py` con fixtures mínimas

**Files:**
- Modify: `tests/conftest.py`

**Por qué:** los tests nuevos van a necesitar al menos 1 clase de prorrateo, 1 proveedor y 1 configuración pre-sembrados para algunos casos base. Los datos específicos (ej. 5 proveedores para probar listado) los crea cada test.

- [ ] **Step 1: Agregar imports al bloque `from backend.models`**

```python
from backend.models import (  # noqa: E402
    Amenity,
    ClaseProrrateo,
    ConfiguracionConsorcio,
    Comunicado,
    Departamento,
    EstadoExpensa,
    EstadoPeticion,
    EstadoReserva,
    Expensa,
    Peticion,
    Proveedor,
    Reserva,
    Rol,
    Usuario,
)
```

- [ ] **Step 2: Extender la función `_seed()` con datos nuevos**

Justo antes del `db.commit()` final de `_seed()`, agregar al `db.add_all([...])`:

```python
            # Fase 1: clase de prorrateo de ejemplo (id=500)
            ClaseProrrateo(
                id=500,
                codigo="A",
                nombre="Expensas ordinarias",
                descripcion="Prorrateo principal",
                activa=True,
            ),
            # Fase 1: proveedor de ejemplo (id=600)
            Proveedor(
                id=600,
                razon_social="Proveedor Test SA",
                nombre_fantasia="Test",
                cuit="30-12345678-9",
                direccion="Calle Falsa 123",
                activo=True,
            ),
            # Fase 1: configuración del consorcio (singleton id=1)
            ConfiguracionConsorcio(
                id=1,
                consorcio_nombre="Consorcio Test",
                consorcio_domicilio="Av. Test 100",
                consorcio_cuit="30-99999999-9",
                consorcio_convenio_suterh=None,
                admin_nombre="Admin Test",
                admin_domicilio="Oficinas 200",
                admin_email="admin@test.local",
                admin_telefono="11-1111-1111",
                admin_cuit="20-11111111-1",
                admin_rpa="0001",
                admin_situacion_fiscal="Monotributo",
                banco_titular="Consorcio Test",
                banco_nombre="Banco Test",
                banco_sucursal="001",
                banco_numero_cuenta="000-1234567/8",
                banco_cbu="0000000000000000000000",
                banco_alias=None,
            ),
```

- [ ] **Step 3: Verificar que los tests existentes siguen verdes**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test(conftest): seed mínimo de ClaseProrrateo, Proveedor y ConfiguracionConsorcio"
```

---

## Fase B — Routers backend con TDD

### Task 4: Router `clases_prorrateo` (TDD)

**Files:**
- Create: `tests/test_clases_prorrateo.py`
- Create: `backend/routers/clases_prorrateo.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Escribir el test file completo**

Crear `tests/test_clases_prorrateo.py`:

```python
# ---------------------------------------------------------------------------
# GET /clases-prorrateo
# ---------------------------------------------------------------------------


def test_listar_clases_sin_token_devuelve_401(client):
    r = client.get("/clases-prorrateo")
    assert r.status_code == 401


def test_listar_clases_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/clases-prorrateo", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_clases_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/clases-prorrateo", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    codigos = {c["codigo"] for c in data}
    assert "A" in codigos


# ---------------------------------------------------------------------------
# POST /clases-prorrateo
# ---------------------------------------------------------------------------


_CLASE_NUEVA = {"codigo": "B", "nombre": "Expensas extraordinarias", "descripcion": "Obras"}


def test_crear_clase_sin_token_devuelve_401(client):
    r = client.post("/clases-prorrateo", json=_CLASE_NUEVA)
    assert r.status_code == 401


def test_crear_clase_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/clases-prorrateo", json=_CLASE_NUEVA, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_clase_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/clases-prorrateo", json=_CLASE_NUEVA, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["codigo"] == "B"
    assert body["nombre"] == "Expensas extraordinarias"
    assert body["activa"] is True


def test_crear_clase_codigo_duplicado_devuelve_409(client, headers_admin):
    # "A" ya existe en el seed.
    r = client.post(
        "/clases-prorrateo",
        json={"codigo": "A", "nombre": "Otra"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_clase_sin_codigo_devuelve_400(client, headers_admin):
    r = client.post(
        "/clases-prorrateo",
        json={"nombre": "Sin código"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /clases-prorrateo/{id}
# ---------------------------------------------------------------------------


def test_obtener_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/clases-prorrateo/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_clase_existente_devuelve_200(client, headers_admin):
    r = client.get("/clases-prorrateo/500", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["codigo"] == "A"


# ---------------------------------------------------------------------------
# PATCH /clases-prorrateo/{id}
# ---------------------------------------------------------------------------


def test_patch_clase_cambia_nombre(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/500",
        json={"nombre": "Ordinarias - renombrada"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ordinarias - renombrada"
    # codigo no editable.
    assert r.json()["codigo"] == "A"


def test_patch_clase_desactiva(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/500",
        json={"activa": False},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["activa"] is False


def test_patch_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/9999",
        json={"nombre": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_patch_clase_codigo_en_body_es_ignorado(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/500",
        json={"codigo": "Z", "nombre": "X"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["codigo"] == "A"


# ---------------------------------------------------------------------------
# DELETE /clases-prorrateo/{id}
# ---------------------------------------------------------------------------


def test_delete_clase_sin_coeficientes_es_hard_delete(client, headers_admin):
    # Crear una clase nueva sin coeficientes asociados.
    creada = client.post(
        "/clases-prorrateo",
        json={"codigo": "X", "nombre": "Temporal"},
        headers=headers_admin,
    ).json()
    r = client.delete(f"/clases-prorrateo/{creada['id']}", headers=headers_admin)
    assert r.status_code == 204

    # Ya no existe.
    r2 = client.get(f"/clases-prorrateo/{creada['id']}", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_clase_con_coeficientes_es_soft_delete(client, headers_admin, db_session):
    # Asociar un coeficiente a la clase A=500 vía PUT /departamentos/.../coeficientes
    # (este endpoint se prueba en su propio archivo; acá lo creamos directo en DB para
    # aislar el test).
    from backend.models import CoeficienteDepartamento
    db_session.add(
        CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=500, porcentaje=50.0)
    )
    db_session.commit()

    r = client.delete("/clases-prorrateo/500", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False

    # Sigue existiendo, solo desactivada.
    r2 = client.get("/clases-prorrateo/500", headers=headers_admin)
    assert r2.status_code == 200


def test_delete_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/clases-prorrateo/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_clases_prorrateo.py -v`
Expected: FAIL en todos (router no existe → 404 por todas las rutas).

- [ ] **Step 3: Crear el router `backend/routers/clases_prorrateo.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import ClaseProrrateo, CoeficienteDepartamento, Rol
from ..schemas import (
    ClaseProrrateoActualizar,
    ClaseProrrateoCrear,
    ClaseProrrateoOut,
)

router = APIRouter(prefix="/clases-prorrateo", tags=["Configuración"])


@router.get(
    "",
    response_model=list[ClaseProrrateoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar clases de prorrateo",
)
def listar_clases(
    activa: bool | None = Query(default=None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[ClaseProrrateo]:
    stmt = select(ClaseProrrateo).order_by(ClaseProrrateo.codigo.asc())
    if activa is not None:
        stmt = stmt.where(ClaseProrrateo.activa == activa)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ClaseProrrateoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear clase de prorrateo",
)
def crear_clase(
    payload: ClaseProrrateoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ClaseProrrateo:
    duplicada = db.scalar(
        select(ClaseProrrateo.id).where(ClaseProrrateo.codigo == payload.codigo)
    )
    if duplicada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una clase con ese código.",
        )

    clase = ClaseProrrateo(
        codigo=payload.codigo,
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        activa=True,
    )
    db.add(clase)
    db.commit()
    db.refresh(clase)
    return clase


@router.get(
    "/{clase_prorrateo_id}",
    response_model=ClaseProrrateoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener clase de prorrateo",
)
def obtener_clase(
    clase_prorrateo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ClaseProrrateo:
    clase = db.get(ClaseProrrateo, clase_prorrateo_id)
    if clase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase solicitada no existe.",
        )
    return clase


@router.patch(
    "/{clase_prorrateo_id}",
    response_model=ClaseProrrateoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar clase de prorrateo",
)
def actualizar_clase(
    clase_prorrateo_id: int,
    payload: ClaseProrrateoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ClaseProrrateo:
    clase = db.get(ClaseProrrateo, clase_prorrateo_id)
    if clase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase solicitada no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(clase, campo, valor)

    db.commit()
    db.refresh(clase)
    return clase


@router.delete(
    "/{clase_prorrateo_id}",
    response_model=ClaseProrrateoOut | None,
    status_code=status.HTTP_200_OK,
    summary="Eliminar clase de prorrateo (hard si no tiene coeficientes; soft si tiene)",
)
def eliminar_clase(
    clase_prorrateo_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    from fastapi import Response

    clase = db.get(ClaseProrrateo, clase_prorrateo_id)
    if clase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase solicitada no existe.",
        )

    tiene_coeficientes = (
        db.scalar(
            select(CoeficienteDepartamento.id).where(
                CoeficienteDepartamento.clase_prorrateo_id == clase_prorrateo_id
            )
        )
        is not None
    )

    if tiene_coeficientes:
        clase.activa = False
        db.commit()
        db.refresh(clase)
        return clase

    db.delete(clase)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Registrar el router en `backend/main.py`**

Sumar el import (alfabético) y el `include_router`. Buscar en `backend/main.py` la zona donde se incluyen routers; agregar:

```python
from .routers import (
    amenities,
    auth,
    clases_prorrateo,  # ← nuevo
    comprobantes,
    ...
)
```

Y en la línea de `app.include_router(...)`:

```python
app.include_router(clases_prorrateo.router)
```

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_clases_prorrateo.py -v`
Expected: todos en verde.

- [ ] **Step 6: Smoke test full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 7: Commit**

```bash
git add tests/test_clases_prorrateo.py backend/routers/clases_prorrateo.py backend/main.py
git commit -m "feat(clases-prorrateo): CRUD admin-only con soft/hard delete según coeficientes"
```

---

### Task 5: Router `proveedores` (TDD)

**Files:**
- Create: `tests/test_proveedores.py`
- Create: `backend/routers/proveedores.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Escribir el test file completo**

Crear `tests/test_proveedores.py`:

```python
# ---------------------------------------------------------------------------
# GET /proveedores
# ---------------------------------------------------------------------------


def test_listar_proveedores_sin_token_devuelve_401(client):
    r = client.get("/proveedores")
    assert r.status_code == 401


def test_listar_proveedores_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/proveedores", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_proveedores_default_solo_activos(client, headers_admin):
    r = client.get("/proveedores", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert all(p["activo"] is True for p in data)
    cuits = {p["cuit"] for p in data}
    assert "30-12345678-9" in cuits


def test_listar_proveedores_inactivos_via_query(client, headers_admin):
    # Desactivamos el del seed.
    client.delete("/proveedores/600", headers=headers_admin)

    # Por default no aparece.
    r = client.get("/proveedores", headers=headers_admin)
    cuits = {p["cuit"] for p in r.json()}
    assert "30-12345678-9" not in cuits

    # Con ?activo=false aparece.
    r2 = client.get("/proveedores?activo=false", headers=headers_admin)
    cuits2 = {p["cuit"] for p in r2.json()}
    assert "30-12345678-9" in cuits2


# ---------------------------------------------------------------------------
# POST /proveedores
# ---------------------------------------------------------------------------


_PROV_NUEVO = {
    "razon_social": "Nuevo Proveedor SRL",
    "nombre_fantasia": "NP",
    "cuit": "30-55555555-5",
    "direccion": "Av. Siempreviva 742",
}


def test_crear_proveedor_sin_token_devuelve_401(client):
    r = client.post("/proveedores", json=_PROV_NUEVO)
    assert r.status_code == 401


def test_crear_proveedor_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/proveedores", json=_PROV_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_proveedor_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/proveedores", json=_PROV_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["razon_social"] == "Nuevo Proveedor SRL"
    assert body["cuit"] == "30-55555555-5"
    assert body["activo"] is True


def test_crear_proveedor_cuit_duplicado_devuelve_409(client, headers_admin):
    r = client.post(
        "/proveedores",
        json={"razon_social": "Otro", "cuit": "30-12345678-9"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_proveedor_cuit_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/proveedores",
        json={"razon_social": "X", "cuit": "ABC"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /proveedores/{id}
# ---------------------------------------------------------------------------


def test_obtener_proveedor_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/proveedores/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_proveedor_existente_devuelve_200(client, headers_admin):
    r = client.get("/proveedores/600", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["cuit"] == "30-12345678-9"


# ---------------------------------------------------------------------------
# PATCH /proveedores/{id}
# ---------------------------------------------------------------------------


def test_patch_proveedor_cambia_razon_social(client, headers_admin):
    r = client.patch(
        "/proveedores/600",
        json={"razon_social": "Proveedor Renombrado SA"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["razon_social"] == "Proveedor Renombrado SA"
    # cuit no editable.
    assert r.json()["cuit"] == "30-12345678-9"


def test_patch_proveedor_cuit_en_body_es_ignorado(client, headers_admin):
    r = client.patch(
        "/proveedores/600",
        json={"cuit": "99-99999999-9", "direccion": "Nueva dir"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["cuit"] == "30-12345678-9"


def test_patch_proveedor_reactivar(client, headers_admin):
    client.delete("/proveedores/600", headers=headers_admin)
    r = client.patch("/proveedores/600", json={"activo": True}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is True


def test_patch_proveedor_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/proveedores/9999",
        json={"razon_social": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /proveedores/{id} — soft-delete siempre
# ---------------------------------------------------------------------------


def test_delete_proveedor_es_soft_delete(client, headers_admin):
    r = client.delete("/proveedores/600", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    # Sigue existiendo.
    r2 = client.get("/proveedores/600", headers=headers_admin)
    assert r2.status_code == 200
    assert r2.json()["activo"] is False


def test_delete_proveedor_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/proveedores/9999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_proveedores.py -v`
Expected: FAIL en todos (router no existe).

- [ ] **Step 3: Crear el router `backend/routers/proveedores.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Proveedor, Rol
from ..schemas import ProveedorActualizar, ProveedorCrear, ProveedorOut

router = APIRouter(prefix="/proveedores", tags=["Configuración"])


@router.get(
    "",
    response_model=list[ProveedorOut],
    status_code=status.HTTP_200_OK,
    summary="Listar proveedores",
)
def listar_proveedores(
    activo: bool | None = Query(
        default=True, description="Filtrar por estado activo (default True)"
    ),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Proveedor]:
    stmt = select(Proveedor).order_by(Proveedor.razon_social.asc())
    if activo is not None:
        stmt = stmt.where(Proveedor.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ProveedorOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
)
def crear_proveedor(
    payload: ProveedorCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    duplicado = db.scalar(select(Proveedor.id).where(Proveedor.cuit == payload.cuit))
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proveedor con ese CUIT.",
        )

    prov = Proveedor(
        razon_social=payload.razon_social,
        nombre_fantasia=payload.nombre_fantasia,
        cuit=payload.cuit,
        direccion=payload.direccion,
        activo=True,
    )
    db.add(prov)
    db.commit()
    db.refresh(prov)
    return prov


@router.get(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener proveedor",
)
def obtener_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor solicitado no existe.",
        )
    return prov


@router.patch(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    status_code=status.HTTP_200_OK,
    summary="Editar proveedor",
)
def actualizar_proveedor(
    proveedor_id: int,
    payload: ProveedorActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(prov, campo, valor)

    db.commit()
    db.refresh(prov)
    return prov


@router.delete(
    "/{proveedor_id}",
    response_model=ProveedorOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar proveedor (soft-delete)",
)
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Proveedor:
    prov = db.get(Proveedor, proveedor_id)
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor solicitado no existe.",
        )
    prov.activo = False
    db.commit()
    db.refresh(prov)
    return prov
```

- [ ] **Step 4: Registrar el router en `backend/main.py`**

Sumar `proveedores` al import alfabético y `app.include_router(proveedores.router)`.

- [ ] **Step 5: Correr los tests + suite completa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_proveedores.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_proveedores.py backend/routers/proveedores.py backend/main.py
git commit -m "feat(proveedores): CRUD admin-only con soft-delete y CUIT único"
```

---

### Task 6: Router `configuracion` (TDD)

**Files:**
- Create: `tests/test_configuracion.py`
- Create: `backend/routers/configuracion.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Escribir el test file completo**

Crear `tests/test_configuracion.py`:

```python
_PAYLOAD_VALIDO = {
    "consorcio_nombre": "Consorcio Editado",
    "consorcio_domicilio": "Av. Nueva 999",
    "consorcio_cuit": "30-88888888-8",
    "consorcio_convenio_suterh": "SUTERH-12345",
    "admin_nombre": "Admin Editado",
    "admin_domicilio": "Otra Calle 111",
    "admin_email": "nuevo@admin.local",
    "admin_telefono": "11-2222-3333",
    "admin_cuit": "20-22222222-2",
    "admin_rpa": "9999",
    "admin_situacion_fiscal": "Responsable Inscripto",
    "banco_titular": "Consorcio Editado",
    "banco_nombre": "Banco Nuevo",
    "banco_sucursal": "002",
    "banco_numero_cuenta": "111-2222222/3",
    "banco_cbu": "1111111111111111111111",
    "banco_alias": "CONSORCIO.NUEVO",
}


# ---------------------------------------------------------------------------
# GET /configuracion (admin + depto)
# ---------------------------------------------------------------------------


def test_get_configuracion_sin_token_devuelve_401(client):
    r = client.get("/configuracion")
    assert r.status_code == 401


def test_get_configuracion_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/configuracion", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["consorcio_nombre"] == "Consorcio Test"
    assert body["banco_cbu"] == "0000000000000000000000"


def test_get_configuracion_como_depto_devuelve_200(client, headers_depto_a):
    # Depto puede leer (necesita datos bancarios).
    r = client.get("/configuracion", headers=headers_depto_a)
    assert r.status_code == 200


def test_get_configuracion_como_representante_devuelve_200(client, headers_representante):
    r = client.get("/configuracion", headers=headers_representante)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# PUT /configuracion (solo admin)
# ---------------------------------------------------------------------------


def test_put_configuracion_sin_token_devuelve_401(client):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO)
    assert r.status_code == 401


def test_put_configuracion_como_depto_devuelve_403(client, headers_depto_a):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO, headers=headers_depto_a)
    assert r.status_code == 403


def test_put_configuracion_como_representante_devuelve_403(client, headers_representante):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO, headers=headers_representante)
    assert r.status_code == 403


def test_put_configuracion_como_admin_actualiza(client, headers_admin):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO, headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["consorcio_nombre"] == "Consorcio Editado"
    assert body["banco_cbu"] == "1111111111111111111111"

    # Verificar persistencia.
    r2 = client.get("/configuracion", headers=headers_admin)
    assert r2.json()["consorcio_nombre"] == "Consorcio Editado"


def test_put_configuracion_cuit_invalido_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["consorcio_cuit"] = "ABC"
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_configuracion_cbu_largo_invalido_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["banco_cbu"] = "123"  # CBU debe tener exactamente 22 chars
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_configuracion_email_corto_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["admin_email"] = "x"
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400
```

- [ ] **Step 2: Correr tests para ver que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_configuracion.py -v`
Expected: FAIL (router no existe).

- [ ] **Step 3: Crear el router `backend/routers/configuracion.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import ConfiguracionConsorcio, Rol
from ..schemas import ConfiguracionConsorcioActualizar, ConfiguracionConsorcioOut

router = APIRouter(prefix="/configuracion", tags=["Configuración"])

_SINGLETON_ID = 1


@router.get(
    "",
    response_model=ConfiguracionConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener configuración del consorcio (singleton)",
)
def obtener_configuracion(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> ConfiguracionConsorcio:
    cfg = db.get(ConfiguracionConsorcio, _SINGLETON_ID)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La configuración del consorcio no fue inicializada.",
        )
    return cfg


@router.put(
    "",
    response_model=ConfiguracionConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar configuración del consorcio (singleton)",
)
def actualizar_configuracion(
    payload: ConfiguracionConsorcioActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> ConfiguracionConsorcio:
    cfg = db.get(ConfiguracionConsorcio, _SINGLETON_ID)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La configuración del consorcio no fue inicializada.",
        )

    for campo, valor in payload.model_dump().items():
        setattr(cfg, campo, valor)

    db.commit()
    db.refresh(cfg)
    return cfg
```

- [ ] **Step 4: Registrar el router en `backend/main.py`**

Sumar `configuracion` al import alfabético e `app.include_router(configuracion.router)`.

- [ ] **Step 5: Correr tests + suite completa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_configuracion.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 6: Commit**

```bash
git add tests/test_configuracion.py backend/routers/configuracion.py backend/main.py
git commit -m "feat(configuracion): singleton GET (todos) + PUT (admin) con validaciones"
```

---

### Task 7: Coeficientes en router `departamentos` (TDD)

**Files:**
- Modify: `tests/test_departamentos.py` (sumar bloque al final)
- Modify: `backend/routers/departamentos.py`

- [ ] **Step 1: Agregar tests al final de `tests/test_departamentos.py`**

Agregar al final del archivo:

```python
# ---------------------------------------------------------------------------
# GET /departamentos/{id}/coeficientes
# ---------------------------------------------------------------------------


def test_get_coeficientes_sin_token_devuelve_401(client):
    r = client.get("/departamentos/1/coeficientes")
    assert r.status_code == 401


def test_get_coeficientes_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/departamentos/1/coeficientes", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_coeficientes_depto_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/departamentos/9999/coeficientes", headers=headers_admin)
    assert r.status_code == 404


def test_get_coeficientes_sin_filas_devuelve_lista_vacia(client, headers_admin):
    r = client.get("/departamentos/1/coeficientes", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# PUT /departamentos/{id}/coeficientes (replace-all)
# ---------------------------------------------------------------------------


def test_put_coeficientes_sin_token_devuelve_401(client):
    r = client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 500, "porcentaje": 50.0}]},
    )
    assert r.status_code == 401


def test_put_coeficientes_como_depto_devuelve_403(client, headers_depto_a):
    r = client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": []},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_put_coeficientes_depto_inexistente_devuelve_404(client, headers_admin):
    r = client.put(
        "/departamentos/9999/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 500, "porcentaje": 25.0}]},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_put_coeficientes_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 9999, "porcentaje": 25.0}]},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_put_coeficientes_porcentaje_fuera_de_rango_devuelve_400(client, headers_admin):
    r = client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 500, "porcentaje": 150.0}]},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_put_coeficientes_clase_duplicada_devuelve_400(client, headers_admin):
    r = client.put(
        "/departamentos/1/coeficientes",
        json={
            "coeficientes": [
                {"clase_prorrateo_id": 500, "porcentaje": 25.0},
                {"clase_prorrateo_id": 500, "porcentaje": 75.0},
            ]
        },
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_put_coeficientes_crea_y_get_devuelve_filas(client, headers_admin):
    r = client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 500, "porcentaje": 33.3333}]},
        headers=headers_admin,
    )
    assert r.status_code == 200

    r2 = client.get("/departamentos/1/coeficientes", headers=headers_admin)
    data = r2.json()
    assert len(data) == 1
    assert data[0]["clase_prorrateo_id"] == 500
    assert data[0]["codigo"] == "A"
    assert data[0]["porcentaje"] == 33.3333


def test_put_coeficientes_replace_borra_los_previos(client, headers_admin):
    # Setup: poner uno.
    client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 500, "porcentaje": 50.0}]},
        headers=headers_admin,
    )
    # Crear otra clase.
    nueva = client.post(
        "/clases-prorrateo",
        json={"codigo": "BB", "nombre": "Otra"},
        headers=headers_admin,
    ).json()

    # Reemplazar con solo la nueva.
    client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": nueva["id"], "porcentaje": 80.0}]},
        headers=headers_admin,
    )

    r = client.get("/departamentos/1/coeficientes", headers=headers_admin)
    data = r.json()
    assert len(data) == 1
    assert data[0]["clase_prorrateo_id"] == nueva["id"]


def test_put_coeficientes_lista_vacia_borra_todo(client, headers_admin):
    # Setup.
    client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": [{"clase_prorrateo_id": 500, "porcentaje": 50.0}]},
        headers=headers_admin,
    )

    # Vaciar.
    r = client.put(
        "/departamentos/1/coeficientes",
        json={"coeficientes": []},
        headers=headers_admin,
    )
    assert r.status_code == 200

    r2 = client.get("/departamentos/1/coeficientes", headers=headers_admin)
    assert r2.json() == []
```

- [ ] **Step 2: Correr los tests nuevos para verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_departamentos.py -v -k coeficientes`
Expected: FAIL (endpoints no existen).

- [ ] **Step 3: Extender el router `backend/routers/departamentos.py`**

Sumar imports:

```python
from ..models import ClaseProrrateo, CoeficienteDepartamento, Departamento, Rol
from ..schemas import (
    CoeficienteOut,
    CoeficientesReemplazar,
    DepartamentoActualizar,
    DepartamentoCrear,
    DepartamentoOut,
)
```

Y al final del archivo, agregar los dos endpoints:

```python
@router.get(
    "/{departamento_id}/coeficientes",
    response_model=list[CoeficienteOut],
    status_code=status.HTTP_200_OK,
    summary="Listar coeficientes de prorrateo del departamento",
)
def listar_coeficientes(
    departamento_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[CoeficienteOut]:
    depto = db.get(Departamento, departamento_id)
    if depto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )

    stmt = (
        select(CoeficienteDepartamento, ClaseProrrateo)
        .join(ClaseProrrateo, CoeficienteDepartamento.clase_prorrateo_id == ClaseProrrateo.id)
        .where(CoeficienteDepartamento.departamento_id == departamento_id)
        .order_by(ClaseProrrateo.codigo.asc())
    )
    return [
        CoeficienteOut(
            clase_prorrateo_id=clase.id,
            codigo=clase.codigo,
            nombre=clase.nombre,
            porcentaje=coef.porcentaje,
        )
        for coef, clase in db.execute(stmt).all()
    ]


@router.put(
    "/{departamento_id}/coeficientes",
    response_model=list[CoeficienteOut],
    status_code=status.HTTP_200_OK,
    summary="Reemplazar todos los coeficientes del departamento",
)
def reemplazar_coeficientes(
    departamento_id: int,
    payload: CoeficientesReemplazar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[CoeficienteOut]:
    depto = db.get(Departamento, departamento_id)
    if depto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento solicitado no existe.",
        )

    # Validar que todas las clases referenciadas existan.
    ids_pedidos = {item.clase_prorrateo_id for item in payload.coeficientes}
    if ids_pedidos:
        existentes = db.scalars(
            select(ClaseProrrateo.id).where(ClaseProrrateo.id.in_(ids_pedidos))
        ).all()
        faltantes = ids_pedidos - set(existentes)
        if faltantes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clases inexistentes: {sorted(faltantes)}",
            )

    # Borrar todos los coeficientes actuales del depto.
    db.query(CoeficienteDepartamento).filter(
        CoeficienteDepartamento.departamento_id == departamento_id
    ).delete(synchronize_session=False)

    # Crear los nuevos.
    for item in payload.coeficientes:
        db.add(
            CoeficienteDepartamento(
                departamento_id=departamento_id,
                clase_prorrateo_id=item.clase_prorrateo_id,
                porcentaje=item.porcentaje,
            )
        )
    db.commit()

    # Devolver el estado nuevo.
    return listar_coeficientes(departamento_id, db, _user)
```

- [ ] **Step 4: Correr tests nuevos + suite completa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_departamentos.py -v && ./.venv/Scripts/python.exe -m pytest -q`
Expected: todos en verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_departamentos.py backend/routers/departamentos.py
git commit -m "feat(departamentos): GET/PUT coeficientes por depto (replace-all)"
```

---

## Fase C — OpenAPI

### Task 8: Documentar endpoints nuevos en `openapi.yaml`

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Localizar la sección `components.schemas` y agregar schemas nuevos**

En `openapi.yaml`, dentro de `components.schemas`, agregar:

```yaml
    ClaseProrrateoCrear:
      type: object
      required: [codigo, nombre]
      properties:
        codigo:
          type: string
          minLength: 1
          maxLength: 8
        nombre:
          type: string
          minLength: 1
          maxLength: 120
        descripcion:
          type: string
          maxLength: 500
          nullable: true

    ClaseProrrateoActualizar:
      type: object
      properties:
        nombre:
          type: string
          minLength: 1
          maxLength: 120
          nullable: true
        descripcion:
          type: string
          maxLength: 500
          nullable: true
        activa:
          type: boolean
          nullable: true

    ClaseProrrateoOut:
      type: object
      required: [id, codigo, nombre, activa]
      properties:
        id: { type: integer }
        codigo: { type: string }
        nombre: { type: string }
        descripcion: { type: string, nullable: true }
        activa: { type: boolean }

    ProveedorCrear:
      type: object
      required: [razon_social, cuit]
      properties:
        razon_social: { type: string, minLength: 1, maxLength: 255 }
        nombre_fantasia: { type: string, maxLength: 255, nullable: true }
        cuit: { type: string, pattern: '^\d{2}-\d{8}-\d{1}$' }
        direccion: { type: string, maxLength: 500, nullable: true }

    ProveedorActualizar:
      type: object
      properties:
        razon_social: { type: string, minLength: 1, maxLength: 255, nullable: true }
        nombre_fantasia: { type: string, maxLength: 255, nullable: true }
        direccion: { type: string, maxLength: 500, nullable: true }
        activo: { type: boolean, nullable: true }

    ProveedorOut:
      type: object
      required: [id, razon_social, cuit, activo]
      properties:
        id: { type: integer }
        razon_social: { type: string }
        nombre_fantasia: { type: string, nullable: true }
        cuit: { type: string }
        direccion: { type: string, nullable: true }
        activo: { type: boolean }

    ConfiguracionConsorcioOut:
      type: object
      required:
        - id
        - consorcio_nombre
        - consorcio_domicilio
        - consorcio_cuit
        - admin_nombre
        - admin_domicilio
        - admin_email
        - admin_telefono
        - admin_cuit
        - admin_rpa
        - admin_situacion_fiscal
        - banco_titular
        - banco_nombre
        - banco_numero_cuenta
        - banco_cbu
      properties:
        id: { type: integer }
        consorcio_nombre: { type: string }
        consorcio_domicilio: { type: string }
        consorcio_cuit: { type: string }
        consorcio_convenio_suterh: { type: string, nullable: true }
        admin_nombre: { type: string }
        admin_domicilio: { type: string }
        admin_email: { type: string }
        admin_telefono: { type: string }
        admin_cuit: { type: string }
        admin_rpa: { type: string }
        admin_situacion_fiscal: { type: string }
        banco_titular: { type: string }
        banco_nombre: { type: string }
        banco_sucursal: { type: string, nullable: true }
        banco_numero_cuenta: { type: string }
        banco_cbu: { type: string, minLength: 22, maxLength: 22 }
        banco_alias: { type: string, nullable: true }

    ConfiguracionConsorcioActualizar:
      allOf:
        - $ref: '#/components/schemas/ConfiguracionConsorcioOut'

    CoeficienteItem:
      type: object
      required: [clase_prorrateo_id, porcentaje]
      properties:
        clase_prorrateo_id: { type: integer, minimum: 1 }
        porcentaje: { type: number, minimum: 0, maximum: 100 }

    CoeficientesReemplazar:
      type: object
      required: [coeficientes]
      properties:
        coeficientes:
          type: array
          items: { $ref: '#/components/schemas/CoeficienteItem' }

    CoeficienteOut:
      type: object
      required: [clase_prorrateo_id, codigo, nombre, porcentaje]
      properties:
        clase_prorrateo_id: { type: integer }
        codigo: { type: string }
        nombre: { type: string }
        porcentaje: { type: number }
```

- [ ] **Step 2: Agregar los paths**

Al final de `paths:`, agregar:

```yaml
  /clases-prorrateo:
    get:
      tags: [Configuración]
      summary: Listar clases de prorrateo
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
                items: { $ref: '#/components/schemas/ClaseProrrateoOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
    post:
      tags: [Configuración]
      summary: Crear clase de prorrateo
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ClaseProrrateoCrear' }
      responses:
        '201':
          description: Creada
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ClaseProrrateoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '409': { $ref: '#/components/responses/Conflicto' }

  /clases-prorrateo/{clase_prorrateo_id}:
    parameters:
      - in: path
        name: clase_prorrateo_id
        required: true
        schema: { type: integer }
    get:
      tags: [Configuración]
      summary: Obtener clase
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ClaseProrrateoOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Configuración]
      summary: Editar clase
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ClaseProrrateoActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ClaseProrrateoOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Configuración]
      summary: Eliminar clase (hard si no tiene coeficientes; soft si tiene)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: Soft-delete (devuelve la clase desactivada)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ClaseProrrateoOut' }
        '204':
          description: Hard-delete
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /proveedores:
    get:
      tags: [Configuración]
      summary: Listar proveedores
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
              schema:
                type: array
                items: { $ref: '#/components/schemas/ProveedorOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
    post:
      tags: [Configuración]
      summary: Crear proveedor
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ProveedorCrear' }
      responses:
        '201':
          description: Creado
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ProveedorOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '409': { $ref: '#/components/responses/Conflicto' }

  /proveedores/{proveedor_id}:
    parameters:
      - in: path
        name: proveedor_id
        required: true
        schema: { type: integer }
    get:
      tags: [Configuración]
      summary: Obtener proveedor
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ProveedorOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    patch:
      tags: [Configuración]
      summary: Editar proveedor
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ProveedorActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ProveedorOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    delete:
      tags: [Configuración]
      summary: Desactivar proveedor (soft-delete)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK (proveedor desactivado)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ProveedorOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /configuracion:
    get:
      tags: [Configuración]
      summary: Obtener configuración del consorcio (todos los roles)
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConfiguracionConsorcioOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    put:
      tags: [Configuración]
      summary: Actualizar configuración del consorcio (admin)
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ConfiguracionConsorcioActualizar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConfiguracionConsorcioOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }

  /departamentos/{departamento_id}/coeficientes:
    parameters:
      - in: path
        name: departamento_id
        required: true
        schema: { type: integer }
    get:
      tags: [Administracion]
      summary: Listar coeficientes del departamento
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/CoeficienteOut' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
    put:
      tags: [Administracion]
      summary: Reemplazar todos los coeficientes del departamento
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CoeficientesReemplazar' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/CoeficienteOut' }
        '400': { $ref: '#/components/responses/PedidoInvalido' }
        '401': { $ref: '#/components/responses/NoAutenticado' }
        '403': { $ref: '#/components/responses/Prohibido' }
        '404': { $ref: '#/components/responses/NoEncontrado' }
```

> **Si `components.responses` (NoAutenticado, Prohibido, NoEncontrado, PedidoInvalido, Conflicto) no existen todavía**, agregalas siguiendo el patrón del resto del `openapi.yaml`. Si ya existen, reutilizalas.

- [ ] **Step 3: Validar el YAML**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml'))"`
Expected: ningún error.

- [ ] **Step 4: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): endpoints de clases-prorrateo, proveedores, configuracion, coeficientes"
```

---

## Fase D — Seed inicial

### Task 9: Extender `backend/seed.py`

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
    Peticion,
    Proveedor,
    Rol,
    Usuario,
)
```

- [ ] **Step 2: Agregar el seed nuevo después del `db.add_all([admin, user_a, user_b])` existente**

Justo antes del `db.add_all([Peticion(...), Peticion(...)])` existente, agregar:

```python
    # ----- Fase 1: clases de prorrateo -----
    clase_a = ClaseProrrateo(codigo="A", nombre="Expensas ordinarias", activa=True)
    clase_b = ClaseProrrateo(codigo="B", nombre="Expensas extraordinarias", activa=True)
    clase_c = ClaseProrrateo(codigo="C", nombre="Servicios diferenciados", activa=True)
    clase_d = ClaseProrrateo(codigo="D", nombre="Obras de frente", activa=True)
    db.add_all([clase_a, clase_b, clase_c, clase_d])
    db.flush()

    # ----- Fase 1: coeficientes para cada depto (clase A, 50% c/u) -----
    db.add_all([
        CoeficienteDepartamento(
            departamento_id=depto_a.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
        CoeficienteDepartamento(
            departamento_id=depto_b.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
    ])

    # ----- Fase 1: proveedores de ejemplo -----
    db.add_all([
        Proveedor(razon_social="Limpieza S.A.", nombre_fantasia="Limpieza", cuit="30-11111111-1"),
        Proveedor(razon_social="Ascensores SRL", nombre_fantasia="Ascensores", cuit="30-22222222-2"),
        Proveedor(razon_social="Seguros del Hogar", nombre_fantasia="SeguHogar", cuit="30-33333333-3"),
        Proveedor(razon_social="Banco Río", nombre_fantasia="Banco", cuit="30-44444444-4"),
        Proveedor(razon_social="Admin Consorcios", nombre_fantasia="Admin", cuit="30-55555555-5"),
    ])

    # ----- Fase 1: configuración singleton -----
    db.add(ConfiguracionConsorcio(
        id=1,
        consorcio_nombre="PENDIENTE",
        consorcio_domicilio="PENDIENTE",
        consorcio_cuit="00-00000000-0",
        consorcio_convenio_suterh=None,
        admin_nombre="PENDIENTE",
        admin_domicilio="PENDIENTE",
        admin_email="pendiente@local",
        admin_telefono="PENDIENTE",
        admin_cuit="00-00000000-0",
        admin_rpa="PENDIENTE",
        admin_situacion_fiscal="PENDIENTE",
        banco_titular="PENDIENTE",
        banco_nombre="PENDIENTE",
        banco_sucursal=None,
        banco_numero_cuenta="PENDIENTE",
        banco_cbu="0000000000000000000000",
        banco_alias=None,
    ))
```

- [ ] **Step 3: Arrancar uvicorn brevemente para confirmar que el seed corre sin errores**

> Pre-requisito: `consorcio.db` no debe existir (lo borramos en Task 0). Si quedó, borrarlo de nuevo.

Run en una terminal: `./.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000`
Esperar a que diga "Application startup complete" y luego Ctrl+C.

Expected: log "Seed completado..." sin errores. Si dice "SEED_DEFAULT_PASSWORD no definida — generada al vuelo: XXX", anotar la password para usar después.

- [ ] **Step 4: Verificar contenido del seed con un script rápido**

Run:
```bash
./.venv/Scripts/python.exe -c "
from backend.database import SessionLocal
from backend.models import ClaseProrrateo, Proveedor, ConfiguracionConsorcio, CoeficienteDepartamento
db = SessionLocal()
print('clases:', db.query(ClaseProrrateo).count())
print('proveedores:', db.query(Proveedor).count())
print('configuracion:', db.query(ConfiguracionConsorcio).count())
print('coeficientes:', db.query(CoeficienteDepartamento).count())
db.close()
"
```

Expected: `clases: 4`, `proveedores: 5`, `configuracion: 1`, `coeficientes: 2`.

- [ ] **Step 5: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): clases A/B/C/D, 5 proveedores, configuración placeholder y coeficientes"
```

---

## Fase E — Frontend

### Task 10: API clients frontend

**Files:**
- Create: `frontend/src/api/clasesProrrateo.js`
- Create: `frontend/src/api/proveedores.js`
- Create: `frontend/src/api/configuracion.js`
- Modify: `frontend/src/api/departamentos.js`

- [ ] **Step 1: Crear `frontend/src/api/clasesProrrateo.js`**

```javascript
import { apiFetch } from "./client";

export function listarClasesProrrateo({ activa } = {}) {
  const qs = activa === undefined ? "" : `?activa=${activa}`;
  return apiFetch(`/clases-prorrateo${qs}`);
}

export function crearClaseProrrateo(payload) {
  return apiFetch("/clases-prorrateo", { method: "POST", body: payload });
}

export function obtenerClaseProrrateo(id) {
  return apiFetch(`/clases-prorrateo/${id}`);
}

export function actualizarClaseProrrateo(id, payload) {
  return apiFetch(`/clases-prorrateo/${id}`, { method: "PATCH", body: payload });
}

export function eliminarClaseProrrateo(id) {
  return apiFetch(`/clases-prorrateo/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Crear `frontend/src/api/proveedores.js`**

```javascript
import { apiFetch } from "./client";

export function listarProveedores({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/proveedores${qs}`);
}

export function crearProveedor(payload) {
  return apiFetch("/proveedores", { method: "POST", body: payload });
}

export function obtenerProveedor(id) {
  return apiFetch(`/proveedores/${id}`);
}

export function actualizarProveedor(id, payload) {
  return apiFetch(`/proveedores/${id}`, { method: "PATCH", body: payload });
}

export function eliminarProveedor(id) {
  return apiFetch(`/proveedores/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Crear `frontend/src/api/configuracion.js`**

```javascript
import { apiFetch } from "./client";

export function obtenerConfiguracion() {
  return apiFetch("/configuracion");
}

export function actualizarConfiguracion(payload) {
  return apiFetch("/configuracion", { method: "PUT", body: payload });
}
```

- [ ] **Step 4: Extender `frontend/src/api/departamentos.js`**

Reemplazar el contenido por:

```javascript
import { apiFetch } from "./client";

export function listarDepartamentos() {
  return apiFetch("/departamentos");
}

export function crearDepartamento(payload) {
  return apiFetch("/departamentos", { method: "POST", body: payload });
}

export function actualizarDepartamento(id, payload) {
  return apiFetch(`/departamentos/${id}`, { method: "PATCH", body: payload });
}

export function listarCoeficientesDepartamento(id) {
  return apiFetch(`/departamentos/${id}/coeficientes`);
}

export function reemplazarCoeficientesDepartamento(id, coeficientes) {
  return apiFetch(`/departamentos/${id}/coeficientes`, {
    method: "PUT",
    body: { coeficientes },
  });
}
```

- [ ] **Step 5: Verificar que el bundle compila**

Run: `cd frontend && npm run build`
Expected: build OK sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/clasesProrrateo.js frontend/src/api/proveedores.js frontend/src/api/configuracion.js frontend/src/api/departamentos.js
git commit -m "feat(frontend/api): clients para clases-prorrateo, proveedores, configuracion y coeficientes"
```

---

### Task 11: Pantalla `Configuracion.jsx`

**Files:**
- Create: `frontend/src/screens/Configuracion.jsx`

- [ ] **Step 1: Crear la pantalla**

```jsx
import { useEffect, useState } from "react";
import { obtenerConfiguracion, actualizarConfiguracion } from "../api/configuracion";

const CAMPOS_VACIOS = {
  consorcio_nombre: "",
  consorcio_domicilio: "",
  consorcio_cuit: "",
  consorcio_convenio_suterh: "",
  admin_nombre: "",
  admin_domicilio: "",
  admin_email: "",
  admin_telefono: "",
  admin_cuit: "",
  admin_rpa: "",
  admin_situacion_fiscal: "",
  banco_titular: "",
  banco_nombre: "",
  banco_sucursal: "",
  banco_numero_cuenta: "",
  banco_cbu: "",
  banco_alias: "",
};

export default function Configuracion() {
  const [form, setForm] = useState(CAMPOS_VACIOS);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  useEffect(() => {
    obtenerConfiguracion()
      .then((data) => {
        const limpio = { ...CAMPOS_VACIOS };
        for (const k of Object.keys(CAMPOS_VACIOS)) {
          limpio[k] = data[k] ?? "";
        }
        setForm(limpio);
      })
      .catch((err) => setError(err.message || "Error al cargar"))
      .finally(() => setCargando(false));
  }, []);

  function cambiar(campo) {
    return (e) => {
      setForm({ ...form, [campo]: e.target.value });
      setMensaje(null);
    };
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    setMensaje(null);
    try {
      // Normalizar nullable → null si está vacío.
      const payload = { ...form };
      for (const k of ["consorcio_convenio_suterh", "banco_sucursal", "banco_alias"]) {
        if (payload[k] === "") payload[k] = null;
      }
      await actualizarConfiguracion(payload);
      setMensaje("Configuración guardada.");
    } catch (err) {
      setError(err.message || "Error al guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Datos del consorcio</h2>
      </header>

      <form onSubmit={onSubmit} className="formulario-configuracion">
        <fieldset>
          <legend>Consorcio</legend>
          <label>Nombre <input value={form.consorcio_nombre} onChange={cambiar("consorcio_nombre")} required /></label>
          <label>Domicilio <input value={form.consorcio_domicilio} onChange={cambiar("consorcio_domicilio")} required /></label>
          <label>CUIT <input value={form.consorcio_cuit} onChange={cambiar("consorcio_cuit")} placeholder="30-12345678-9" required /></label>
          <label>Convenio SUTERH <input value={form.consorcio_convenio_suterh} onChange={cambiar("consorcio_convenio_suterh")} /></label>
        </fieldset>

        <fieldset>
          <legend>Administración</legend>
          <label>Nombre <input value={form.admin_nombre} onChange={cambiar("admin_nombre")} required /></label>
          <label>Domicilio <input value={form.admin_domicilio} onChange={cambiar("admin_domicilio")} required /></label>
          <label>Email <input type="email" value={form.admin_email} onChange={cambiar("admin_email")} required /></label>
          <label>Teléfono <input value={form.admin_telefono} onChange={cambiar("admin_telefono")} required /></label>
          <label>CUIT <input value={form.admin_cuit} onChange={cambiar("admin_cuit")} required /></label>
          <label>RPA/C <input value={form.admin_rpa} onChange={cambiar("admin_rpa")} required /></label>
          <label>Situación fiscal <input value={form.admin_situacion_fiscal} onChange={cambiar("admin_situacion_fiscal")} required /></label>
        </fieldset>

        <fieldset>
          <legend>Datos bancarios</legend>
          <label>Titular <input value={form.banco_titular} onChange={cambiar("banco_titular")} required /></label>
          <label>Banco <input value={form.banco_nombre} onChange={cambiar("banco_nombre")} required /></label>
          <label>Sucursal <input value={form.banco_sucursal} onChange={cambiar("banco_sucursal")} /></label>
          <label>N° cuenta <input value={form.banco_numero_cuenta} onChange={cambiar("banco_numero_cuenta")} required /></label>
          <label>CBU <input value={form.banco_cbu} onChange={cambiar("banco_cbu")} minLength={22} maxLength={22} required /></label>
          <label>Alias <input value={form.banco_alias} onChange={cambiar("banco_alias")} /></label>
        </fieldset>

        {error && <p className="error">{error}</p>}
        {mensaje && <p className="exito">{mensaje}</p>}

        <button type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Agregar estilos al `frontend/src/index.css` (al final)**

```css
.cabecera-pantalla {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-block-end: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.formulario-configuracion fieldset {
  margin-block: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-text);
  border-radius: 6px;
}
.formulario-configuracion legend {
  font-weight: 600;
  padding-inline: 0.5rem;
}
.formulario-configuracion label {
  display: block;
  margin-block: 0.75rem;
}
.formulario-configuracion input {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.5rem;
  font-size: 1rem;
  min-height: 44px;
  box-sizing: border-box;
}
.exito {
  color: var(--color-primary);
  font-weight: 600;
}
```

> Verificar primero que `.cabecera-pantalla` y `.error` no existan ya. Run: `grep -n "cabecera-pantalla\|^\.error" frontend/src/index.css`. Si ya existen, no las dupliques.

- [ ] **Step 3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/Configuracion.jsx frontend/src/index.css
git commit -m "feat(frontend): pantalla Configuración (singleton del consorcio)"
```

---

### Task 12: Pantalla `ClasesProrrateo.jsx`

**Files:**
- Create: `frontend/src/screens/ClasesProrrateo.jsx`

- [ ] **Step 1: Crear la pantalla**

```jsx
import { useEffect, useState } from "react";
import {
  listarClasesProrrateo,
  crearClaseProrrateo,
  actualizarClaseProrrateo,
  eliminarClaseProrrateo,
} from "../api/clasesProrrateo";

export default function ClasesProrrateo() {
  const [clases, setClases] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null); // { tipo: "crear" } | { tipo: "editar", clase }

  function recargar() {
    setCargando(true);
    listarClasesProrrateo()
      .then(setClases)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    recargar();
  }, []);

  async function toggleActiva(clase) {
    try {
      await actualizarClaseProrrateo(clase.id, { activa: !clase.activa });
      recargar();
    } catch (err) {
      setError(err.message);
    }
  }

  async function borrar(clase) {
    if (!confirm(`¿Eliminar la clase "${clase.codigo}"?`)) return;
    try {
      await eliminarClaseProrrateo(clase.id);
      recargar();
    } catch (err) {
      setError(err.message);
    }
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Clases de prorrateo</h2>
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          Nueva clase
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Descripción</th>
            <th>Activa</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {clases.map((c) => (
            <tr key={c.id}>
              <td>{c.codigo}</td>
              <td>{c.nombre}</td>
              <td>{c.descripcion || "—"}</td>
              <td>{c.activa ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModal({ tipo: "editar", clase: c })}>Editar</button>
                <button type="button" onClick={() => toggleActiva(c)}>
                  {c.activa ? "Desactivar" : "Activar"}
                </button>
                <button type="button" onClick={() => borrar(c)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal?.tipo === "crear" && (
        <ModalForm
          titulo="Nueva clase"
          inicial={{ codigo: "", nombre: "", descripcion: "" }}
          permiteEditarCodigo
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            await crearClaseProrrateo(datos);
            setModal(null);
            recargar();
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalForm
          titulo={`Editar clase ${modal.clase.codigo}`}
          inicial={{
            codigo: modal.clase.codigo,
            nombre: modal.clase.nombre,
            descripcion: modal.clase.descripcion || "",
          }}
          permiteEditarCodigo={false}
          onCerrar={() => setModal(null)}
          onGuardar={async ({ nombre, descripcion }) => {
            await actualizarClaseProrrateo(modal.clase.id, {
              nombre,
              descripcion: descripcion || null,
            });
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalForm({ titulo, inicial, permiteEditarCodigo, onCerrar, onGuardar }) {
  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await onGuardar(form);
    } catch (err) {
      setError(err.message || "Error");
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Código
            <input
              value={form.codigo}
              onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              disabled={!permiteEditarCodigo}
              maxLength={8}
              required
            />
          </label>
          <label>Nombre
            <input
              value={form.nombre}
              onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              maxLength={120}
              required
            />
          </label>
          <label>Descripción
            <textarea
              value={form.descripcion}
              onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              maxLength={500}
            />
          </label>
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

- [ ] **Step 2: Agregar estilos `tabla` en `frontend/src/index.css` (si no existen)**

```css
.tabla {
  width: 100%;
  border-collapse: collapse;
}
.tabla th, .tabla td {
  padding: 0.75rem 0.5rem;
  border-block-end: 1px solid var(--color-text);
  text-align: left;
}
.tabla button {
  margin-right: 0.25rem;
}
```

> `.cabecera-pantalla` ya se agregó en Task 11; no la dupliques.

> Si `.modal-backdrop`, `.modal`, `.modal-acciones` ya existen en `index.css`, no las duplicar. Verificar con `grep`. Si no existen, agregar versión mínima:

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.modal {
  background: var(--color-bg);
  padding: 1.5rem;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-acciones {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
```

- [ ] **Step 3: Verificar build**

Run: `cd frontend && npm run build`
Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/ClasesProrrateo.jsx frontend/src/index.css
git commit -m "feat(frontend): pantalla ClasesProrrateo con CRUD + modal"
```

---

### Task 13: Pantalla `Proveedores.jsx`

**Files:**
- Create: `frontend/src/screens/Proveedores.jsx`

- [ ] **Step 1: Crear la pantalla**

```jsx
import { useEffect, useState } from "react";
import {
  listarProveedores,
  crearProveedor,
  actualizarProveedor,
  eliminarProveedor,
} from "../api/proveedores";

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    listarProveedores(filtro)
      .then(setProveedores)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(p) {
    try {
      if (p.activo) {
        await eliminarProveedor(p.id);
      } else {
        await actualizarProveedor(p.id, { activo: true });
      }
      recargar();
    } catch (err) {
      setError(err.message);
    }
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Proveedores</h2>
        <div>
          <label>
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Mostrar inactivos
          </label>
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            Nuevo proveedor
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="tabla">
        <thead>
          <tr>
            <th>Razón social</th>
            <th>Nombre fantasía</th>
            <th>CUIT</th>
            <th>Dirección</th>
            <th>Activo</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {proveedores.map((p) => (
            <tr key={p.id}>
              <td>{p.razon_social}</td>
              <td>{p.nombre_fantasia || "—"}</td>
              <td>{p.cuit}</td>
              <td>{p.direccion || "—"}</td>
              <td>{p.activo ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModal({ tipo: "editar", proveedor: p })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(p)}>
                  {p.activo ? "Desactivar" : "Activar"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal?.tipo === "crear" && (
        <ModalProveedor
          titulo="Nuevo proveedor"
          inicial={{ razon_social: "", nombre_fantasia: "", cuit: "", direccion: "" }}
          permiteEditarCuit
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const payload = {
              ...datos,
              nombre_fantasia: datos.nombre_fantasia || null,
              direccion: datos.direccion || null,
            };
            await crearProveedor(payload);
            setModal(null);
            recargar();
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalProveedor
          titulo={`Editar ${modal.proveedor.razon_social}`}
          inicial={{
            razon_social: modal.proveedor.razon_social,
            nombre_fantasia: modal.proveedor.nombre_fantasia || "",
            cuit: modal.proveedor.cuit,
            direccion: modal.proveedor.direccion || "",
          }}
          permiteEditarCuit={false}
          onCerrar={() => setModal(null)}
          onGuardar={async ({ razon_social, nombre_fantasia, direccion }) => {
            await actualizarProveedor(modal.proveedor.id, {
              razon_social,
              nombre_fantasia: nombre_fantasia || null,
              direccion: direccion || null,
            });
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalProveedor({ titulo, inicial, permiteEditarCuit, onCerrar, onGuardar }) {
  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await onGuardar(form);
    } catch (err) {
      setError(err.message || "Error");
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Razón social
            <input
              value={form.razon_social}
              onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              maxLength={255}
              required
            />
          </label>
          <label>Nombre fantasía
            <input
              value={form.nombre_fantasia}
              onChange={(e) => setForm({ ...form, nombre_fantasia: e.target.value })}
              maxLength={255}
            />
          </label>
          <label>CUIT
            <input
              value={form.cuit}
              onChange={(e) => setForm({ ...form, cuit: e.target.value })}
              disabled={!permiteEditarCuit}
              placeholder="30-12345678-9"
              pattern="\d{2}-\d{8}-\d{1}"
              required
            />
          </label>
          <label>Dirección
            <input
              value={form.direccion}
              onChange={(e) => setForm({ ...form, direccion: e.target.value })}
              maxLength={500}
            />
          </label>
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
Expected: OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/Proveedores.jsx
git commit -m "feat(frontend): pantalla Proveedores con CRUD, soft-delete y filtro inactivos"
```

---

### Task 14: Pantalla `Departamentos.jsx`

**Files:**
- Create: `frontend/src/screens/Departamentos.jsx`

- [ ] **Step 1: Crear la pantalla**

```jsx
import { useEffect, useState } from "react";
import {
  listarDepartamentos,
  listarCoeficientesDepartamento,
  reemplazarCoeficientesDepartamento,
} from "../api/departamentos";
import { listarClasesProrrateo } from "../api/clasesProrrateo";

export default function Departamentos() {
  const [departamentos, setDepartamentos] = useState([]);
  const [coeficientesPorDepto, setCoeficientesPorDepto] = useState({});
  const [clases, setClases] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null); // { departamento, coeficientes }

  async function recargar() {
    setCargando(true);
    try {
      const [deptos, clasesActivas] = await Promise.all([
        listarDepartamentos(),
        listarClasesProrrateo({ activa: true }),
      ]);
      setDepartamentos(deptos);
      setClases(clasesActivas);

      const coefs = {};
      for (const d of deptos) {
        coefs[d.id] = await listarCoeficientesDepartamento(d.id);
      }
      setCoeficientesPorDepto(coefs);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    recargar();
  }, []);

  function resumen(coefs) {
    if (!coefs || coefs.length === 0) return "—";
    return coefs.map((c) => `${c.codigo}: ${c.porcentaje}%`).join(" · ");
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Departamentos</h2>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Descripción</th>
            <th>Coeficientes</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {departamentos.map((d) => (
            <tr key={d.id}>
              <td>{d.codigo}</td>
              <td>{d.descripcion || "—"}</td>
              <td>{resumen(coeficientesPorDepto[d.id])}</td>
              <td>
                <button
                  type="button"
                  onClick={() => setModal({ departamento: d, coeficientes: coeficientesPorDepto[d.id] || [] })}
                >
                  Editar coeficientes
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal && (
        <ModalCoeficientes
          departamento={modal.departamento}
          coeficientesActuales={modal.coeficientes}
          clases={clases}
          onCerrar={() => setModal(null)}
          onGuardar={async (nuevos) => {
            await reemplazarCoeficientesDepartamento(modal.departamento.id, nuevos);
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalCoeficientes({ departamento, coeficientesActuales, clases, onCerrar, onGuardar }) {
  // mapa { clase_id: porcentaje } iniciado con los actuales y 0 para las que faltan.
  const inicial = {};
  for (const c of clases) inicial[c.id] = 0;
  for (const c of coeficientesActuales) inicial[c.clase_prorrateo_id] = c.porcentaje;

  const [valores, setValores] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      const payload = Object.entries(valores)
        .filter(([, v]) => v !== "" && v !== null && Number(v) > 0)
        .map(([clase_prorrateo_id, porcentaje]) => ({
          clase_prorrateo_id: Number(clase_prorrateo_id),
          porcentaje: Number(porcentaje),
        }));
      await onGuardar(payload);
    } catch (err) {
      setError(err.message);
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Coeficientes — {departamento.codigo}</h3>
        <form onSubmit={onSubmit}>
          {clases.map((c) => (
            <label key={c.id}>
              {c.codigo} — {c.nombre}
              <input
                type="number"
                step="0.0001"
                min="0"
                max="100"
                value={valores[c.id] ?? 0}
                onChange={(e) => setValores({ ...valores, [c.id]: e.target.value })}
              />
            </label>
          ))}
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
Expected: OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/screens/Departamentos.jsx
git commit -m "feat(frontend): pantalla Departamentos con edición de coeficientes"
```

---

### Task 15: Rutas + Sidebar nueva sección

**Files:**
- Modify: `frontend/src/App.jsx` (o donde estén las rutas)
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Localizar el archivo de rutas**

Run: `grep -rn "Routes\|createBrowserRouter\|<Route" frontend/src/ --include="*.jsx" | head -10`
Expected: ver el archivo principal de rutas (probablemente `App.jsx`).

- [ ] **Step 2: Agregar las 4 nuevas rutas**

En el archivo de rutas, agregar los imports:

```javascript
import Configuracion from "./screens/Configuracion";
import ClasesProrrateo from "./screens/ClasesProrrateo";
import Proveedores from "./screens/Proveedores";
import Departamentos from "./screens/Departamentos";
```

Y dentro del `<Routes>`, agregar (anidadas dentro del layout protegido si existe):

```jsx
<Route path="/configuracion" element={<Configuracion />} />
<Route path="/clases-prorrateo" element={<ClasesProrrateo />} />
<Route path="/proveedores" element={<Proveedores />} />
<Route path="/departamentos" element={<Departamentos />} />
```

- [ ] **Step 3: Agregar nueva sección "Configuración" al Sidebar**

En `frontend/src/components/Sidebar.jsx`, dentro del array `SECCIONES`, agregar al final:

```javascript
  {
    titulo: "Configuración",
    modulos: [
      {
        ruta: "/configuracion",
        nombre: "Datos del consorcio",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/clases-prorrateo",
        nombre: "Clases de prorrateo",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/proveedores",
        nombre: "Proveedores",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/departamentos",
        nombre: "Departamentos",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
```

- [ ] **Step 4: Verificar build**

Run: `cd frontend && npm run build`
Expected: OK.

- [ ] **Step 5: Smoke test manual del frontend (golden path)**

Run en una terminal: `./.venv/Scripts/python.exe -m uvicorn backend.main:app --reload --port 8000`
Run en otra terminal: `cd frontend && npm run dev`

En el browser:
1. Login como admin.
2. Sidebar muestra sección "Configuración" con 4 items.
3. Entrar a "Datos del consorcio" → ver placeholders → modificar y guardar → recargar → cambios persisten.
4. Entrar a "Clases de prorrateo" → ver A/B/C/D → crear una nueva → editarla → desactivarla → reactivarla → borrar la creada.
5. Entrar a "Proveedores" → ver los 5 del seed → crear uno → editarlo → desactivarlo → toggle "Mostrar inactivos" → reactivarlo.
6. Entrar a "Departamentos" → ver coeficientes (50% c/u del seed) → editar coeficientes de un depto → guardar → verificar que se reflejan en la columna.
7. Logout. Login como depto-a → sidebar NO muestra sección "Configuración".

Expected: todo funciona. Si algo falla, debugear y arreglar antes de continuar.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat(frontend): rutas + sección Configuración en sidebar (admin-only)"
```

---

## Fase F — Verificación final y merge

### Task 16: Smoke test full + merge a master

- [ ] **Step 1: Correr suite de tests backend completa**

Run: `./.venv/Scripts/python.exe -m pytest -v`
Expected: todos en verde, sin warnings nuevos.

- [ ] **Step 2: Build de frontend para producción**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Verificar OpenAPI**

Run: `./.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml')); print('OK')"`
Expected: imprime `OK`.

- [ ] **Step 4: Revisar diff completo del branch contra master**

Run: `git log master..HEAD --oneline`
Expected: ver la lista de commits (un commit por task).

Run: `git diff master..HEAD --stat`
Expected: lista de archivos modificados con líneas +/- por archivo.

- [ ] **Step 5: Invocar skill `finishing-a-development-branch`**

En este punto, parar y consultar al usuario qué hacer con el branch. Por convención del proyecto (revisar memoria `[[finishing-pattern]]` si existe), el patrón usual es:

```bash
git checkout master
git merge --no-ff feature/expensas-fase1
git branch -d feature/expensas-fase1
```

Pero NO mergear sin pedir explícitamente al usuario primero — preguntar:

> "Fase 1 terminada y verificada. Suite verde + build OK + smoke test manual OK. ¿Mergeo a master con `--no-ff` o preferís revisar el diff antes?"

Esperar respuesta del usuario antes de mergear.
