# Plan A — Backend Multitenant Core

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Segmentar el backend por `consorcio_id` sin romper el frontend actual ni cambiar el motor de DB. Al terminar, la app funciona idéntico a hoy (con un consorcio "Demo" adoptado por la migración), pero por dentro cada request está atada a un `X-Consorcio-Id` y no hay leak de datos entre consorcios.

**Architecture:** Discriminator column (`consorcio_id`) en cada tabla operacional. Dependency FastAPI `get_consorcio_activo` que resuelve el header `X-Consorcio-Id`, valida acceso del usuario, y devuelve el int. Cada router operacional agrega esa dep + filtra sus queries. Nuevo rol `super_admin` (sin funcionalidad todavía — solo el enum + la fila en `usuarios`). Migración idempotente vía script separado (SQLite no soporta `ALTER TABLE ADD COLUMN NOT NULL FK`, usamos patrón table-rebuild).

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (`Mapped`, `mapped_column`), SQLite, pytest, `passlib`, `pyjwt`. Frontend intacto en este plan.

**Spec de referencia:** `docs/superpowers/specs/2026-07-06-multitenant-saas-design.md` (secciones 2, 3, 4, 7, 8.1, 8.2, 8.5).

**Fuera de este plan (Plan B, C, D):**

- Endpoints `POST/GET/PATCH /consorcios` (van a Plan B).
- Endpoints `/super-admin/*` (Plan B).
- Impersonate + audit log middleware (Plan B).
- Métricas y audit log endpoints (Plan B).
- Frontend admin y super-admin (C y D).
- Feature flag `usa_personal_propio` en el sidebar (frontend, Plan C).

---

## File Structure

**Archivos nuevos:**

- `backend/tenant.py` — dependency `get_consorcio_activo` y helpers.
- `backend/migrate_multitenant.py` — script CLI de migración idempotente.
- `backend/seed_super_admin.py` — script CLI seed idempotente.
- `tests/test_migracion_multitenant.py` — tests del script de migración.
- `tests/test_tenant.py` — tests dedicados del resolver.
- `tests/test_seed_super_admin.py` — tests del seed.
- `tests/test_me_consorcios.py` — tests de `/me/consorcios`.
- `tests/test_cambiar_password.py` — tests de `/me/cambiar-password` + enforcement.
- `tests/test_login_administracion_suspendida.py` — chequeo 403 al login.
- `tests/test_aislamiento_multitenant.py` — batería paramétrica por router.

**Archivos a modificar:**

- `backend/models.py` — nuevos modelos `Administracion`, `Consorcio`, `AuditLogSuperAdmin`, nuevo enum `Rol.super_admin`, cambios en `Usuario` y `Departamento`, `consorcio_id` en 25+ tablas, uniques scoped.
- `backend/routers/auth.py` — chequeo `administracion_suspendida` en `POST /auth/login`.
- `backend/routers/usuarios.py` — nuevos endpoints `GET /me/consorcios` y `POST /me/cambiar-password`.
- `backend/routers/*.py` — cada router operacional agrega `cid: int = Depends(get_consorcio_activo)` y filtra queries por `consorcio_id`.
- `backend/seed.py` — hace que su seed use la administración+consorcio Demo.
- `tests/conftest.py` — fixtures `headers_*` agregan `X-Consorcio-Id`; nueva fixture `headers_super_admin`; nueva fixture `dos_consorcios`.

**Archivos con deprecación controlada:**

- `backend/routers/configuracion.py` — sigue funcionando (redirige lecturas/escrituras al consorcio activo derivado del `X-Consorcio-Id`). No se elimina en este plan.

---

## Fase 1 — Nuevos modelos (independientes)

### Task 1: Enum `Rol.super_admin` + modelo `Administracion`

**Files:**
- Modify: `backend/models.py:21-24` (enum `Rol`) y al final del archivo (nuevo modelo).
- Test: `tests/test_migracion_multitenant.py::test_puede_crear_administracion`.

- [ ] **Step 1: Escribir test failing**

```python
# tests/test_migracion_multitenant.py
from backend.models import Administracion, Rol


def test_rol_super_admin_existe():
    assert Rol.super_admin.value == "super_admin"


def test_puede_crear_administracion(db_empty):
    a = Administracion(
        razon_social="Estudio X",
        cuit="30-11111111-1",
        email_contacto="x@estudio.com",
    )
    db_empty.add(a)
    db_empty.commit()
    assert a.id is not None
    assert a.activa is True
    assert a.plan == "free"
```

- [ ] **Step 2: Correr test para verificar failing**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migracion_multitenant.py::test_rol_super_admin_existe -v`

Expected: FAIL con `AttributeError: super_admin`.

- [ ] **Step 3: Implementar**

En `backend/models.py`, agregar `super_admin = "super_admin"` al enum `Rol`:

```python
class Rol(str, enum.Enum):
    administracion = "administracion"
    representante = "representante"
    departamento = "departamento"
    super_admin = "super_admin"
```

Y al final del archivo, nuevo modelo:

```python
class Administracion(Base):
    __tablename__ = "administraciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    cuit: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    email_contacto: Mapped[str] = mapped_column(String(255), nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    consorcios: Mapped[list["Consorcio"]] = relationship(back_populates="administracion")
```

- [ ] **Step 4: Correr tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migracion_multitenant.py -v`

Expected: PASS ambos.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/test_migracion_multitenant.py
git commit -m "feat(backend): agregar Rol.super_admin y modelo Administracion"
```

---

### Task 2: Modelo `Consorcio` (reemplaza `ConfiguracionConsorcio`)

**Files:**
- Modify: `backend/models.py` (agregar clase `Consorcio` después de `Administracion`).
- Test: `tests/test_migracion_multitenant.py::test_puede_crear_consorcio`.

**Consideraciones:**
- Absorbe todos los campos actuales de `ConfiguracionConsorcio`.
- Suma `administracion_id`, `nombre`, `usa_personal_propio`, `fecha_creacion`.
- `ConfiguracionConsorcio` se mantiene por ahora (se droppea en Task 16).

- [ ] **Step 1: Escribir test failing**

```python
def test_puede_crear_consorcio(db_empty):
    from backend.models import Administracion, Consorcio

    admin = Administracion(razon_social="X", cuit="30-11-1", email_contacto="x@x.com")
    db_empty.add(admin); db_empty.flush()
    c = Consorcio(
        administracion_id=admin.id,
        nombre="Edificio 1",
        consorcio_domicilio="Av. Test 100",
        consorcio_cuit="30-99-9",
        admin_nombre="Admin X",
        admin_domicilio="Of. 1",
        admin_email="x@x.com",
        admin_telefono="1111",
        admin_cuit="20-11-1",
        admin_rpa="0001",
        admin_situacion_fiscal="Monotributo",
        banco_titular="X",
        banco_nombre="Banco X",
        banco_numero_cuenta="000-0",
        banco_cbu="0" * 22,
    )
    db_empty.add(c); db_empty.commit()
    assert c.id is not None
    assert c.usa_personal_propio is True
    assert c.dia_primer_vencimiento == 10
```

- [ ] **Step 2: Verificar failing**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migracion_multitenant.py::test_puede_crear_consorcio -v`
Expected: FAIL con `ImportError` en `Consorcio`.

- [ ] **Step 3: Implementar**

En `backend/models.py`, después de `class Administracion`:

```python
class Consorcio(Base):
    __tablename__ = "consorcios"

    id: Mapped[int] = mapped_column(primary_key=True)
    administracion_id: Mapped[int] = mapped_column(
        ForeignKey("administraciones.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    usa_personal_propio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Datos del consorcio (heredado de ConfiguracionConsorcio)
    consorcio_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    consorcio_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    consorcio_convenio_suterh: Mapped[str | None] = mapped_column(String(50))

    # Administración
    admin_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_domicilio: Mapped[str] = mapped_column(String(500), nullable=False)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_telefono: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_cuit: Mapped[str] = mapped_column(String(13), nullable=False)
    admin_rpa: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_situacion_fiscal: Mapped[str] = mapped_column(String(100), nullable=False)

    # Banco
    banco_titular: Mapped[str] = mapped_column(String(255), nullable=False)
    banco_nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    banco_sucursal: Mapped[str | None] = mapped_column(String(50))
    banco_numero_cuenta: Mapped[str] = mapped_column(String(50), nullable=False)
    banco_cbu: Mapped[str] = mapped_column(String(22), nullable=False)
    banco_alias: Mapped[str | None] = mapped_column(String(50))

    # Vencimientos
    dia_primer_vencimiento: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dias_entre_vencimientos: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    recargo_segundo_vencimiento_pct: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    tasa_interes_mensual_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    caja_default_pagos_id: Mapped[int | None] = mapped_column(ForeignKey("cajas.id"), nullable=True)
    reportes_visibles_a_depto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    administracion: Mapped["Administracion"] = relationship(back_populates="consorcios")
```

- [ ] **Step 4: Correr tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migracion_multitenant.py -v`
Expected: PASS 3 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/test_migracion_multitenant.py
git commit -m "feat(backend): modelo Consorcio (paralelo a ConfiguracionConsorcio)"
```

---

### Task 3: Modelo `AuditLogSuperAdmin`

**Files:**
- Modify: `backend/models.py` (nuevo modelo al final).
- Test: `tests/test_migracion_multitenant.py::test_puede_crear_audit_log`.

- [ ] **Step 1: Escribir test failing**

```python
def test_puede_crear_audit_log(db_empty):
    from backend.models import AuditLogSuperAdmin, Usuario, Rol
    from backend.security import hash_password

    u = Usuario(email="sa@x.com", password_hash=hash_password("x"), rol=Rol.super_admin)
    db_empty.add(u); db_empty.flush()
    log = AuditLogSuperAdmin(
        super_admin_usuario_id=u.id,
        accion="crear_admin",
        motivo=None,
    )
    db_empty.add(log); db_empty.commit()
    assert log.id is not None
```

- [ ] **Step 2: Verificar failing** — Run tests, esperar `ImportError`.

- [ ] **Step 3: Implementar**

```python
class AuditLogSuperAdmin(Base):
    __tablename__ = "audit_log_super_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    super_admin_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    accion: Mapped[str] = mapped_column(String(80), nullable=False)
    administracion_id_afectada: Mapped[int | None] = mapped_column(
        ForeignKey("administraciones.id", ondelete="SET NULL"), nullable=True
    )
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detalles: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
```

- [ ] **Step 4: Correr tests** — todos verde.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(backend): modelo AuditLogSuperAdmin"
```

---

### Task 4: `Usuario`: `administracion_id`, `consorcio_id`, `must_change_password`

**Files:**
- Modify: `backend/models.py` (clase `Usuario`).
- Test: `tests/test_migracion_multitenant.py::test_usuario_super_admin`, `::test_usuario_representante_con_consorcio`.

**Consideraciones:**
- Constraints por rol se validan a nivel schema Pydantic (Plan B) o CHECK SQL. En este task solo columnas nullable — la lógica de gating se implementa en la migración y en el resolver.

- [ ] **Step 1: Escribir tests failing**

```python
def test_usuario_super_admin(db_empty):
    from backend.models import Usuario, Rol
    from backend.security import hash_password

    u = Usuario(
        email="sa@x.com",
        password_hash=hash_password("x"),
        rol=Rol.super_admin,
    )
    db_empty.add(u); db_empty.commit()
    assert u.administracion_id is None
    assert u.consorcio_id is None
    assert u.must_change_password is False


def test_usuario_representante_con_consorcio(db_empty):
    from backend.models import Administracion, Consorcio, Usuario, Rol
    from backend.security import hash_password

    admin = Administracion(razon_social="X", cuit="30-11-1", email_contacto="x@x.com")
    db_empty.add(admin); db_empty.flush()
    c = Consorcio(administracion_id=admin.id, nombre="C",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22)
    db_empty.add(c); db_empty.flush()
    u = Usuario(
        email="rep@x.com", password_hash=hash_password("x"),
        rol=Rol.representante, consorcio_id=c.id,
    )
    db_empty.add(u); db_empty.commit()
    assert u.consorcio_id == c.id
```

- [ ] **Step 2: Verificar failing** — FAIL con `AttributeError` en `consorcio_id` o `must_change_password`.

- [ ] **Step 3: Implementar**

Modificar `class Usuario`:

```python
class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[Rol] = mapped_column(SqlEnum(Rol, name="rol"), nullable=False)
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id", ondelete="RESTRICT"),
        nullable=True,
    )
    administracion_id: Mapped[int | None] = mapped_column(
        ForeignKey("administraciones.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    consorcio_id: Mapped[int | None] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    departamento: Mapped["Departamento | None"] = relationship(back_populates="usuarios")
```

- [ ] **Step 4: Correr tests** — Todos PASS.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(backend): Usuario suma administracion_id, consorcio_id y must_change_password"
```

---

## Fase 2 — Migración de tablas existentes

### Task 5: Esqueleto de `migrate_multitenant.py` + idempotencia + admin+consorcio Demo

**Files:**
- Create: `backend/migrate_multitenant.py`.
- Test: `tests/test_migracion_multitenant.py::test_migracion_crea_demo_si_no_hay_datos`, `::test_migracion_es_idempotente`.

- [ ] **Step 1: Escribir tests failing**

```python
def test_migracion_crea_demo_si_no_hay_datos(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Administracion, Consorcio

    migrar(db_empty)

    admins = db_empty.query(Administracion).all()
    consorcios = db_empty.query(Consorcio).all()
    assert len(admins) == 1
    assert admins[0].razon_social == "Administración Demo"
    assert len(consorcios) == 1
    assert consorcios[0].administracion_id == admins[0].id


def test_migracion_es_idempotente(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Administracion

    migrar(db_empty)
    migrar(db_empty)  # segunda pasada no debe explotar ni duplicar
    assert db_empty.query(Administracion).count() == 1
```

- [ ] **Step 2: Verificar failing** — Run: `pytest tests/test_migracion_multitenant.py -k migracion -v`. FAIL: `ImportError` en `migrate_multitenant`.

- [ ] **Step 3: Implementar esqueleto**

```python
# backend/migrate_multitenant.py
"""
Migración idempotente a multitenant.

- Crea administracion "Demo" + consorcio "Demo" si no existen.
- Adopta datos existentes bajo esos IDs.
- Idempotente: correr N veces es equivalente a correr 1 vez.

Uso: python -m backend.migrate_multitenant
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import SessionLocal
from .models import Administracion, Consorcio, ConfiguracionConsorcio

logger = logging.getLogger(__name__)


def ya_migrado(db: Session) -> bool:
    """Devuelve True si ya existe al menos una administración."""
    return db.query(Administracion).first() is not None


def _crear_demo(db: Session) -> tuple[Administracion, Consorcio]:
    admin = Administracion(
        razon_social="Administración Demo",
        cuit="30-00000000-0",
        email_contacto="demo@example.com",
    )
    db.add(admin); db.flush()

    cfg = db.query(ConfiguracionConsorcio).first() if _tabla_existe(db, "configuracion_consorcio") else None
    if cfg is not None:
        c = Consorcio(
            administracion_id=admin.id,
            nombre=cfg.consorcio_nombre,
            consorcio_domicilio=cfg.consorcio_domicilio,
            consorcio_cuit=cfg.consorcio_cuit,
            consorcio_convenio_suterh=cfg.consorcio_convenio_suterh,
            admin_nombre=cfg.admin_nombre,
            admin_domicilio=cfg.admin_domicilio,
            admin_email=cfg.admin_email,
            admin_telefono=cfg.admin_telefono,
            admin_cuit=cfg.admin_cuit,
            admin_rpa=cfg.admin_rpa,
            admin_situacion_fiscal=cfg.admin_situacion_fiscal,
            banco_titular=cfg.banco_titular,
            banco_nombre=cfg.banco_nombre,
            banco_sucursal=cfg.banco_sucursal,
            banco_numero_cuenta=cfg.banco_numero_cuenta,
            banco_cbu=cfg.banco_cbu,
            banco_alias=cfg.banco_alias,
            dia_primer_vencimiento=cfg.dia_primer_vencimiento,
            dias_entre_vencimientos=cfg.dias_entre_vencimientos,
            recargo_segundo_vencimiento_pct=cfg.recargo_segundo_vencimiento_pct,
            tasa_interes_mensual_pct=cfg.tasa_interes_mensual_pct,
            caja_default_pagos_id=cfg.caja_default_pagos_id,
            reportes_visibles_a_depto=cfg.reportes_visibles_a_depto,
        )
    else:
        c = Consorcio(
            administracion_id=admin.id,
            nombre="Consorcio Demo",
            consorcio_domicilio="Sin domicilio",
            consorcio_cuit="30-00000000-0",
            admin_nombre="Demo",
            admin_domicilio="Sin domicilio",
            admin_email="demo@example.com",
            admin_telefono="0",
            admin_cuit="30-00000000-0",
            admin_rpa="0000",
            admin_situacion_fiscal="Monotributo",
            banco_titular="Demo",
            banco_nombre="Banco Demo",
            banco_numero_cuenta="0-0",
            banco_cbu="0" * 22,
        )
    db.add(c); db.flush()
    return admin, c


def _tabla_existe(db: Session, nombre: str) -> bool:
    r = db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": nombre},
    ).first()
    return r is not None


def migrar(db: Session) -> None:
    if ya_migrado(db):
        logger.info("Ya migrado a multitenant, nada que hacer.")
        return

    admin, consorcio = _crear_demo(db)
    logger.info(f"Creados admin #{admin.id} y consorcio #{consorcio.id}")
    # Las tareas 6-16 popularán consorcio_id en las tablas operacionales.
    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        migrar(db)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr tests** — Ambos PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/migrate_multitenant.py tests/test_migracion_multitenant.py
git commit -m "feat(backend): script migrate_multitenant esqueleto + idempotencia"
```

---

### Task 6: Migración: agregar `consorcio_id` a `departamentos` (patrón table-rebuild)

**Contexto SQLite:** `ALTER TABLE ADD COLUMN NOT NULL` sin default no está permitido. Estrategia por tabla:
1. `ALTER TABLE X ADD COLUMN consorcio_id INTEGER` (nullable, sin FK todavía).
2. `UPDATE X SET consorcio_id = :cid`.
3. Table-rebuild: crear tabla nueva con constraint NOT NULL + FK, copiar datos, drop vieja, rename nueva, recrear índices.

Para simplificar en SQLite y evitar 25 rebuilds, adoptamos una estrategia mixta:

- SQLite hoy no fuerza FKs sin `PRAGMA foreign_keys=ON` en cada conexión. Nuestra config lo activa. Sin embargo, la constraint NOT NULL sí se puede agregar sin rebuild si popularmos primero y después usamos `CREATE INDEX` + validación app-side.
- **Decisión:** en este script, `consorcio_id` queda como `INTEGER NOT NULL` a nivel modelo SQLAlchemy (para que el ORM valide), y a nivel DB queda como INTEGER indexado. La constraint estricta NOT NULL DB-nivel se aplica solo a las tablas creadas después de la migración (drops+recreates son costosos). Los tests de aislamiento (Task 35) garantizan el comportamiento correcto.

**Files:**
- Modify: `backend/migrate_multitenant.py` (nueva función `_agregar_columna_consorcio_id`).
- Test: `tests/test_migracion_multitenant.py::test_migracion_agrega_consorcio_id_a_departamentos`.

- [ ] **Step 1: Escribir test failing**

```python
def test_migracion_agrega_consorcio_id_a_departamentos(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Departamento
    from sqlalchemy import text

    # Sembrar 2 deptos existentes SIN consorcio_id (simulando pre-migración)
    db_empty.execute(text(
        "INSERT INTO departamentos (id, codigo, descripcion) VALUES (1, 'UF-1', 'A'), (2, 'UF-2', 'B')"
    ))
    db_empty.commit()

    migrar(db_empty)

    deptos = db_empty.query(Departamento).order_by(Departamento.id).all()
    assert len(deptos) == 2
    assert all(d.consorcio_id == 1 for d in deptos)  # consorcio Demo id=1
```

- [ ] **Step 2: Verificar failing** — Test FAIL: `Departamento` todavía no tiene `consorcio_id`.

- [ ] **Step 3: Implementar**

Primero agregar `consorcio_id` a `class Departamento` en `backend/models.py`:

```python
class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    consorcio_id: Mapped[int] = mapped_column(
        ForeignKey("consorcios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    codigo: Mapped[str] = mapped_column(String(32), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        UniqueConstraint("consorcio_id", "codigo", name="uq_depto_consorcio_codigo"),
    )

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="departamento")
    peticiones: Mapped[list["Peticion"]] = relationship(back_populates="departamento")
    expensas: Mapped[list["Expensa"]] = relationship(back_populates="departamento")
    comprobantes: Mapped[list["Comprobante"]] = relationship(back_populates="departamento")
    movimientos_cuenta: Mapped[list["MovimientoCuenta"]] = relationship(back_populates="departamento")
    coeficientes: Mapped[list["CoeficienteDepartamento"]] = relationship(
        back_populates="departamento", cascade="all, delete-orphan"
    )
```

Después en `backend/migrate_multitenant.py`, agregar helper y llamarlo dentro de `migrar()`:

```python
def _adoptar_tabla(db: Session, tabla: str, cid: int) -> None:
    """Agrega columna consorcio_id (si falta) y setea todas las filas al cid."""
    # ¿Ya tiene la columna?
    cols = db.execute(text(f"PRAGMA table_info({tabla})")).all()
    tiene_col = any(c[1] == "consorcio_id" for c in cols)
    if not tiene_col:
        db.execute(text(f"ALTER TABLE {tabla} ADD COLUMN consorcio_id INTEGER"))
    # Popular filas huérfanas
    db.execute(
        text(f"UPDATE {tabla} SET consorcio_id = :cid WHERE consorcio_id IS NULL"),
        {"cid": cid},
    )
    # Crear índice si no existe
    db.execute(text(
        f"CREATE INDEX IF NOT EXISTS ix_{tabla}_consorcio_id ON {tabla}(consorcio_id)"
    ))


def migrar(db: Session) -> None:
    if ya_migrado(db):
        logger.info("Ya migrado a multitenant, nada que hacer.")
        return

    admin, consorcio = _crear_demo(db)
    cid = consorcio.id

    _adoptar_tabla(db, "departamentos", cid)
    logger.info(f"Adoptada tabla departamentos bajo consorcio #{cid}")

    db.commit()
```

- [ ] **Step 4: Correr tests** — PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/migrate_multitenant.py tests/test_migracion_multitenant.py
git commit -m "feat(backend): migrar departamentos con consorcio_id"
```

---

### Task 7: Migración batch — grupo Expensas (`expensas`, `expensa_detalle`, `movimientos_cuenta`, `comprobantes`, `periodos_cerrados`)

**Files:**
- Modify: `backend/models.py` (agregar `consorcio_id` a las 5 clases).
- Modify: `backend/migrate_multitenant.py` (llamar `_adoptar_tabla` para cada una).
- Test: `tests/test_migracion_multitenant.py::test_migracion_adopta_grupo_expensas`.

- [ ] **Step 1: Escribir test failing**

```python
def test_migracion_adopta_grupo_expensas(db_empty):
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    # Sembrar depto pre-migración
    db_empty.execute(text(
        "INSERT INTO departamentos (id, codigo, descripcion) VALUES (1, 'UF-1', 'A')"
    ))
    # Sembrar filas pre-migración en las 5 tablas del grupo
    db_empty.execute(text(
        "INSERT INTO expensas (id, departamento_id, periodo, monto_primer_vencimiento, "
        "fecha_primer_vencimiento, monto_segundo_vencimiento, fecha_segundo_vencimiento, saldo_anterior) "
        "VALUES (10, 1, '2026-05', 1000, '2026-07-10', 1070, '2026-07-20', 0)"
    ))
    # ... resto de inserts para las otras 4 tablas (dejarlas mínimas)
    db_empty.commit()

    migrar(db_empty)

    r = db_empty.execute(text("SELECT consorcio_id FROM expensas WHERE id=10")).first()
    assert r[0] == 1
```

- [ ] **Step 2: Verificar failing** — FAIL.

- [ ] **Step 3: Implementar**

En `backend/models.py`, agregar `consorcio_id: Mapped[int] = mapped_column(ForeignKey("consorcios.id"), nullable=False, index=True)` a las clases `Expensa`, `ExpensaDetalle`, `Comprobante`, `MovimientoCuenta`, `PeriodoCerrado`.

**Nota especial `expensas`:** actualizar el `UniqueConstraint`:

```python
__table_args__ = (
    UniqueConstraint("consorcio_id", "departamento_id", "periodo",
                     name="uq_expensa_consorcio_depto_periodo"),
)
```

En `backend/migrate_multitenant.py`, dentro de `migrar()` extender la lista:

```python
GRUPO_EXPENSAS = ("expensas", "expensa_detalle", "movimientos_cuenta",
                  "comprobantes", "periodos_cerrados")
for tabla in GRUPO_EXPENSAS:
    _adoptar_tabla(db, tabla, cid)
    logger.info(f"Adoptada tabla {tabla} bajo consorcio #{cid}")
```

- [ ] **Step 4: Correr tests** — PASS.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(backend): migrar grupo expensas con consorcio_id"
```

---

### Task 8: Migración batch — grupo Gastos (`gastos`, `gastos_habituales`)

**Files:** análogo a Task 7. Agregar `consorcio_id` a `Gasto` y `GastoHabitual`; llamar `_adoptar_tabla` para las 2 tablas.

- [ ] **Step 1: Test failing** — mismo patrón que Task 7 pero sobre `gastos`.
- [ ] **Step 2: Verificar failing**.
- [ ] **Step 3: Implementar** — agregar `consorcio_id` a los dos modelos y a la lista en `migrar()`.
- [ ] **Step 4: Correr tests**.
- [ ] **Step 5:** `git commit -am "feat(backend): migrar grupo gastos con consorcio_id"`.

---

### Task 9: Migración batch — grupo Tareas (`peticiones`, `trabajos`, `trabajos_recurrentes`, `presupuestos`)

**Files:** análogo. Test sobre `peticiones`.

- [ ] **Step 1: Test failing**.
- [ ] **Step 2: Verificar failing**.
- [ ] **Step 3: Implementar** — 4 modelos, 4 líneas en `migrar()`.
- [ ] **Step 4: Correr tests**.
- [ ] **Step 5:** `git commit -am "feat(backend): migrar grupo tareas con consorcio_id"`.

---

### Task 10: Migración batch — grupo Comunidad (`comunicados`, `amenities`, `reservas`)

**Files:** análogo. Test sobre `comunicados`.

**Nota:** `amenities` cambia unique de `nombre` global a `(consorcio_id, nombre)`. `Reserva` recibe `consorcio_id` FK.

- [ ] **Step 1-5:** patrón standard. Commit: `feat(backend): migrar grupo comunidad con consorcio_id`.

---

### Task 11: Migración batch — grupo Tesorería (`cajas`, `movimientos_caja`, `transferencias_caja`)

**Nota:** `cajas.nombre` unique pasa a `(consorcio_id, nombre)`.

- [ ] **Step 1-5:** patrón standard. Commit: `feat(backend): migrar grupo tesoreria con consorcio_id`.

---

### Task 12: Migración batch — grupo Catálogos (`clases_prorrateo`, `coeficientes_departamento`, `proveedores`)

**Notas:**
- `clases_prorrateo.codigo` pasa a unique `(consorcio_id, codigo)`.
- `proveedores.cuit` pasa a unique `(consorcio_id, cuit)`.
- `coeficientes_departamento` ya está scoped implícitamente vía `departamento_id` (que ahora tiene `consorcio_id`), pero le sumamos `consorcio_id` explícito para simplificar queries.

- [ ] **Step 1-5:** patrón standard. Commit: `feat(backend): migrar grupo catalogos con consorcio_id`.

---

### Task 13: Migración batch — grupo Personal (`empleados`, `haberes`, `conceptos_liquidacion`, `liquidaciones_empleado`, `liquidaciones_haber`, `liquidaciones_detalle`)

**Notas:**
- `empleados.cuil` pasa a unique `(consorcio_id, cuil)`.
- `haberes.nombre`, `conceptos_liquidacion.nombre` pasan a unique `(consorcio_id, nombre)`.

- [ ] **Step 1-5:** patrón standard. Commit: `feat(backend): migrar grupo personal con consorcio_id`.

---

### Task 14: Migración batch — grupo Notificaciones (`notificaciones`)

**Nota:** Notificaciones no cambia mucho — solo agrega `consorcio_id` (el usuario ya está atado a un consorcio).

- [ ] **Step 1-5:** patrón standard. Commit: `feat(backend): migrar notificaciones con consorcio_id`.

---

### Task 15: Migración: asignar `administracion_id` a usuarios admin + drop `configuracion_consorcio`

**Files:**
- Modify: `backend/migrate_multitenant.py`.
- Test: `tests/test_migracion_multitenant.py::test_migracion_asigna_administracion_a_admins`, `::test_migracion_dropea_configuracion_consorcio`.

- [ ] **Step 1: Escribir tests failing**

```python
def test_migracion_asigna_administracion_a_admins(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Rol, Usuario
    from backend.security import hash_password
    from sqlalchemy import text

    # Sembrar admin pre-migración
    db_empty.execute(text(
        "INSERT INTO usuarios (id, email, password_hash, rol) "
        "VALUES (1, 'admin@x.com', :h, 'administracion')"
    ), {"h": hash_password("x")})
    db_empty.commit()

    migrar(db_empty)

    u = db_empty.query(Usuario).filter(Usuario.email == "admin@x.com").first()
    assert u.administracion_id == 1


def test_migracion_dropea_configuracion_consorcio(db_empty):
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    migrar(db_empty)
    r = db_empty.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='configuracion_consorcio'"
    )).first()
    assert r is None
```

- [ ] **Step 2: Verificar failing**.

- [ ] **Step 3: Implementar**

En `backend/migrate_multitenant.py`, al final de `migrar()` antes del commit:

```python
# 5. Asignar administracion_id a usuarios admin
db.execute(
    text("UPDATE usuarios SET administracion_id = :aid WHERE rol = 'administracion'"),
    {"aid": admin.id},
)

# 6. Drop configuracion_consorcio (si existe)
if _tabla_existe(db, "configuracion_consorcio"):
    db.execute(text("DROP TABLE configuracion_consorcio"))
    logger.info("Tabla configuracion_consorcio eliminada")
```

- [ ] **Step 4: Correr tests** — PASS.

- [ ] **Step 5: Commit** — `feat(backend): migracion asigna administracion a admins y dropea configuracion`.

---

### Task 16: Quitar modelo `ConfiguracionConsorcio` de `models.py`

**Files:**
- Modify: `backend/models.py` (borrar clase `ConfiguracionConsorcio`).
- Modify: `tests/conftest.py` (borrar el import y su uso en `_seed`).
- Modify: `backend/routers/configuracion.py` (adaptar a leer/escribir `Consorcio`).

**Consideraciones:** este cambio es más grande. El router de configuración pasa a resolver el consorcio activo del header y trabaja contra `Consorcio` en vez de `ConfiguracionConsorcio`. La adaptación se hace acá para no dejar el modelo huérfano.

- [ ] **Step 1: Escribir test failing**

```python
# tests/test_configuracion.py — asegurarse que GET /configuracion sigue funcionando (con header X-Consorcio-Id)
def test_get_configuracion_devuelve_datos_del_consorcio_activo(client, headers_admin):
    r = client.get("/configuracion", headers={**headers_admin, "X-Consorcio-Id": "1"})
    assert r.status_code == 200
    assert r.json()["consorcio_nombre"] == "Consorcio Test"
```

*(Nota: el fixture `headers_admin` ya se actualiza en Task 23 para incluir el header por default. Este test explicita el header por claridad.)*

- [ ] **Step 2: Verificar failing** — FAIL: `configuracion` todavía consulta `ConfiguracionConsorcio`.

- [ ] **Step 3: Implementar**

En `backend/routers/configuracion.py`, reemplazar `ConfiguracionConsorcio` por `Consorcio` y agregar dep `get_consorcio_activo`. Ejemplo mínimo:

```python
from ..tenant import get_consorcio_activo
from ..models import Consorcio

@router.get("/configuracion", response_model=ConfiguracionOut)
def obtener_configuracion(
    db: Session = Depends(get_db),
    cid: int = Depends(get_consorcio_activo),
):
    c = db.query(Consorcio).filter(Consorcio.id == cid).first()
    if c is None:
        raise HTTPException(404)
    return _consorcio_a_configuracion_out(c)
```

El schema `ConfiguracionOut` sigue igual — usamos un mapper `_consorcio_a_configuracion_out` que copia los mismos campos. El schema Pydantic no cambia (retrocompat frontend).

En `backend/models.py`, eliminar `class ConfiguracionConsorcio`.

En `tests/conftest.py`, reemplazar el bloque `ConfiguracionConsorcio(...)` del seed por `Consorcio(...)` y sembrar antes una `Administracion`. Ver detalle exacto en Task 23.

- [ ] **Step 4: Correr tests** — todos los tests de configuración deben pasar.

- [ ] **Step 5: Commit** — `refactor(backend): eliminar ConfiguracionConsorcio, /configuracion trabaja contra Consorcio`.

---

### Task 17: Test integral de migración fresh + con datos

**Files:**
- Modify: `tests/test_migracion_multitenant.py` (agregar test end-to-end).

- [ ] **Step 1: Escribir test**

```python
def test_migracion_end_to_end_con_datos_variados(db_empty):
    """
    Simula una DB con datos productivos (single-tenant hoy) y verifica que
    después de migrar todo tiene consorcio_id = 1.
    """
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    # Sembrar dataset chico: 2 deptos, 3 expensas, 1 gasto, 1 caja, 1 comunicado, 1 proveedor, etc.
    scripts = [
        "INSERT INTO departamentos (id, codigo, descripcion) VALUES (1, 'UF-1', 'A'), (2, 'UF-2', 'B')",
        "INSERT INTO expensas (id, departamento_id, periodo, monto_primer_vencimiento, "
        "  fecha_primer_vencimiento, monto_segundo_vencimiento, fecha_segundo_vencimiento, saldo_anterior) "
        "  VALUES (1, 1, '2026-05', 1000, '2026-07-10', 1070, '2026-07-20', 0), "
        "         (2, 2, '2026-05', 1200, '2026-07-10', 1284, '2026-07-20', 0), "
        "         (3, 1, '2026-06', 1100, '2026-08-10', 1177, '2026-08-20', 0)",
        "INSERT INTO cajas (id, nombre, tipo, saldo_inicial, activa) "
        "  VALUES (1, 'Banco', 'banco', 0, 1)",
        "INSERT INTO proveedores (id, razon_social, cuit, activo) "
        "  VALUES (1, 'X', '30-11-1', 1)",
        # ... otros
    ]
    for s in scripts:
        db_empty.execute(text(s))
    db_empty.commit()

    migrar(db_empty)

    # Todas las filas de todas las tablas operacionales tienen consorcio_id = 1
    tablas = ["departamentos", "expensas", "cajas", "proveedores"]  # subset representativo
    for tabla in tablas:
        rows = db_empty.execute(text(f"SELECT consorcio_id FROM {tabla}")).all()
        assert all(r[0] == 1 for r in rows), f"{tabla} tiene filas sin consorcio_id"
```

- [ ] **Step 2: Correr tests** — PASS.

- [ ] **Step 3: Commit** — `test(backend): E2E migracion con datos variados`.

---

## Fase 3 — Seed super_admin

### Task 18: Script `seed_super_admin.py` + tests

**Files:**
- Create: `backend/seed_super_admin.py`.
- Test: `tests/test_seed_super_admin.py`.

- [ ] **Step 1: Escribir tests failing**

```python
# tests/test_seed_super_admin.py
import os
import pytest
from backend.models import Rol, Usuario


def test_seed_crea_super_admin_si_no_existe(db_empty, monkeypatch):
    from backend.seed_super_admin import seed
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "sa@x.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "1234567890ab")

    seed(db_empty)

    u = db_empty.query(Usuario).filter(Usuario.email == "sa@x.com").first()
    assert u is not None
    assert u.rol == Rol.super_admin
    assert u.administracion_id is None
    assert u.departamento_id is None


def test_seed_es_idempotente(db_empty, monkeypatch):
    from backend.seed_super_admin import seed
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "sa@x.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "1234567890ab")

    seed(db_empty)
    seed(db_empty)  # segunda vez, no explota

    count = db_empty.query(Usuario).filter(Usuario.rol == Rol.super_admin).count()
    assert count == 1


def test_seed_falla_sin_env_vars(db_empty, monkeypatch):
    monkeypatch.delenv("SUPER_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("SUPER_ADMIN_PASSWORD", raising=False)
    from backend.seed_super_admin import seed

    with pytest.raises(RuntimeError, match="SUPER_ADMIN_EMAIL"):
        seed(db_empty)


def test_seed_force_resetea_password(db_empty, monkeypatch):
    from backend.seed_super_admin import seed
    from backend.security import verify_password

    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "sa@x.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "primera-pass-12")
    seed(db_empty)

    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "segunda-pass-12")
    seed(db_empty, force=True)

    u = db_empty.query(Usuario).filter(Usuario.email == "sa@x.com").first()
    assert verify_password("segunda-pass-12", u.password_hash)
```

- [ ] **Step 2: Verificar failing** — `ImportError`.

- [ ] **Step 3: Implementar**

```python
# backend/seed_super_admin.py
"""
Seed idempotente del super_admin.

Uso: SUPER_ADMIN_EMAIL=x SUPER_ADMIN_PASSWORD=y python -m backend.seed_super_admin [--force]
"""
import argparse
import logging
import os
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Rol, Usuario
from .security import hash_password

logger = logging.getLogger(__name__)


def seed(db: Session, *, force: bool = False) -> Usuario:
    email = os.environ.get("SUPER_ADMIN_EMAIL")
    password = os.environ.get("SUPER_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("SUPER_ADMIN_EMAIL y SUPER_ADMIN_PASSWORD son requeridos")

    existente = db.query(Usuario).filter(Usuario.rol == Rol.super_admin).first()
    if existente is not None:
        if force:
            existente.password_hash = hash_password(password)
            existente.email = email
            db.commit()
            logger.info(f"Password del super_admin reseteado (--force)")
            return existente
        logger.info(f"Super_admin ya existe ({existente.email}), nada que hacer")
        return existente

    u = Usuario(
        email=email,
        password_hash=hash_password(password),
        rol=Rol.super_admin,
    )
    db.add(u); db.commit()
    logger.info(f"Super_admin creado: {email}")
    return u


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Resetear password si existe")
    args = parser.parse_args()
    with SessionLocal() as db:
        seed(db, force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr tests** — PASS.

- [ ] **Step 5: Commit** — `feat(backend): seed_super_admin idempotente`.

---

## Fase 4 — Auth actualizado y endpoints `/me/*`

### Task 19: Chequeo `administracion_suspendida` en `POST /auth/login`

**Files:**
- Modify: `backend/routers/auth.py`.
- Test: `tests/test_login_administracion_suspendida.py`.

- [ ] **Step 1: Escribir test failing**

```python
# tests/test_login_administracion_suspendida.py
def test_login_falla_si_administracion_suspendida(client, db_session):
    from backend.models import Administracion, Rol, Usuario
    from backend.security import hash_password

    admin_tenant = db_session.query(Administracion).first()
    admin_tenant.activa = False
    db_session.commit()

    # El admin del seed (id=1) pertenece a este tenant
    r = client.post("/auth/login", json={
        "email": "admin@test.local",
        "password": "test-pass-1234",
    })
    assert r.status_code == 403
    assert r.json()["detail"] == "administracion_suspendida"
```

*(Nota: este test asume que el fixture `_seed` ya sembró la administración Demo y asignó `admin.administracion_id=1`. Ver Task 23 para el nuevo seed.)*

- [ ] **Step 2: Verificar failing**.

- [ ] **Step 3: Implementar**

En `backend/routers/auth.py`, en la función de login, después de verificar credenciales, agregar:

```python
def _administracion_activa_para(db: Session, user: Usuario) -> bool:
    if user.rol == Rol.super_admin:
        return True
    if user.rol == Rol.administracion:
        aid = user.administracion_id
    elif user.rol == Rol.representante:
        c = db.query(Consorcio).filter(Consorcio.id == user.consorcio_id).first()
        aid = c.administracion_id if c else None
    elif user.rol == Rol.departamento:
        d = db.query(Departamento).filter(Departamento.id == user.departamento_id).first()
        c = db.query(Consorcio).filter(Consorcio.id == d.consorcio_id).first() if d else None
        aid = c.administracion_id if c else None
    else:
        return True
    if aid is None:
        return True
    admin_tenant = db.query(Administracion).filter(Administracion.id == aid).first()
    return admin_tenant is not None and admin_tenant.activa

# dentro del handler:
if not _administracion_activa_para(db, user):
    raise HTTPException(status_code=403, detail="administracion_suspendida")
```

- [ ] **Step 4: Correr tests** — PASS.

- [ ] **Step 5: Commit** — `feat(backend): login rechaza administracion suspendida`.

---

### Task 20: `GET /me/consorcios`

**Files:**
- Modify: `backend/routers/usuarios.py`.
- Test: `tests/test_me_consorcios.py`.

- [ ] **Step 1: Escribir test failing**

```python
def test_me_consorcios_admin_ve_todos_los_del_tenant(client, headers_admin, db_session):
    from backend.models import Administracion, Consorcio
    a = db_session.query(Administracion).first()
    # crear un segundo consorcio del mismo tenant
    c2 = Consorcio(
        administracion_id=a.id, nombre="Consorcio 2",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22,
    )
    db_session.add(c2); db_session.commit()

    r = client.get("/me/consorcios", headers=headers_admin)
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert ids == {1, c2.id}


def test_me_consorcios_depto_ve_solo_el_suyo(client, headers_depto_a):
    r = client.get("/me/consorcios", headers=headers_depto_a)
    assert r.status_code == 200
    consorcios = r.json()
    assert len(consorcios) == 1
    assert consorcios[0]["id"] == 1
```

- [ ] **Step 2: Verificar failing**.

- [ ] **Step 3: Implementar**

En `backend/routers/usuarios.py`, agregar endpoint (schema Pydantic mínimo):

```python
class ConsorcioMini(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True


@router.get("/me/consorcios", response_model=list[ConsorcioMini])
def listar_mis_consorcios(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    u = db.query(Usuario).filter(Usuario.id == user.id).first()
    if u.rol == Rol.administracion:
        cs = db.query(Consorcio).filter(
            Consorcio.administracion_id == u.administracion_id
        ).order_by(Consorcio.nombre).all()
    elif u.rol == Rol.representante:
        cs = db.query(Consorcio).filter(Consorcio.id == u.consorcio_id).all()
    elif u.rol == Rol.departamento:
        d = db.query(Departamento).filter(Departamento.id == u.departamento_id).first()
        cs = [db.query(Consorcio).filter(Consorcio.id == d.consorcio_id).first()] if d else []
    else:
        cs = []
    return cs
```

- [ ] **Step 4: Correr tests** — PASS.

- [ ] **Step 5: Commit** — `feat(backend): endpoint GET /me/consorcios`.

---

### Task 21: `POST /me/cambiar-password` + enforcement `must_change_password`

**Files:**
- Modify: `backend/routers/usuarios.py`.
- Test: `tests/test_cambiar_password.py`.

- [ ] **Step 1: Escribir tests failing**

```python
def test_cambiar_password_ok(client, headers_admin, db_session):
    from backend.models import Usuario
    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.must_change_password = True
    db_session.commit()

    r = client.post("/me/cambiar-password", headers=headers_admin, json={
        "password_actual": "test-pass-1234",
        "password_nueva": "otra-pass-1234",
    })
    assert r.status_code == 204

    db_session.refresh(u)
    assert u.must_change_password is False


def test_cambiar_password_valida_actual(client, headers_admin):
    r = client.post("/me/cambiar-password", headers=headers_admin, json={
        "password_actual": "wrong-pass",
        "password_nueva": "otra-pass-1234",
    })
    assert r.status_code == 400


def test_endpoints_bloqueados_si_must_change_password(client, headers_admin, db_session):
    from backend.models import Usuario
    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.must_change_password = True
    db_session.commit()

    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 403
    assert r.json()["detail"] == "cambio_password_requerido"
```

- [ ] **Step 2: Verificar failing**.

- [ ] **Step 3: Implementar**

**A)** Endpoint en `backend/routers/usuarios.py`:

```python
class CambiarPasswordIn(BaseModel):
    password_actual: str = Field(min_length=1)
    password_nueva: str = Field(min_length=8, max_length=200)


@router.post("/me/cambiar-password", status_code=204)
def cambiar_password(
    body: CambiarPasswordIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    u = db.query(Usuario).filter(Usuario.id == user.id).first()
    if not verify_password(body.password_actual, u.password_hash):
        raise HTTPException(400, "credenciales invalidas")
    u.password_hash = hash_password(body.password_nueva)
    u.must_change_password = False
    db.commit()
    return Response(status_code=204)
```

**B)** Enforcement: nueva dependency en `backend/tenant.py` (se crea en Task 22) que chequea `must_change_password`. Por ahora agregar chequeo simple en `get_current_user` (o wrapper) — decisión de diseño: preferimos un middleware.

**Decisión pragmática:** agregar el chequeo en el resolver `get_consorcio_activo` (Task 22), que es el punto por el que pasa todo endpoint operacional. Endpoints exentos (`/me/cambiar-password`, `/auth/*`, `/me/consorcios`) no lo tienen. Reordenar: hacer Task 21 en 2 pasos:
- 21a: implementar el endpoint (steps 3A arriba). Test `test_cambiar_password_ok` y `test_cambiar_password_valida_actual` pasan.
- 21b: dejar `test_endpoints_bloqueados_si_must_change_password` como XFAIL hasta Task 22.

En el test, marcarlo `@pytest.mark.xfail(reason="enforcement en Task 22")`. Después en Task 22 se saca el xfail.

- [ ] **Step 4: Correr tests** — Los dos primeros PASS, el tercero XFAIL.

- [ ] **Step 5: Commit** — `feat(backend): POST /me/cambiar-password`.

---

## Fase 5 — Tenant resolver

### Task 22: `backend/tenant.py` con `get_consorcio_activo` + enforcement de `must_change_password`

**Files:**
- Create: `backend/tenant.py`.
- Test: `tests/test_tenant.py`.
- Modify: `tests/test_cambiar_password.py` (quitar el `xfail`).

- [ ] **Step 1: Escribir tests failing**

```python
# tests/test_tenant.py
import pytest
from fastapi import HTTPException, Request
from backend.tenant import get_consorcio_activo
from backend.auth import CurrentUser
from backend.models import Rol


def _fake_request(headers: dict) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_resolver_falla_sin_header(db_session, headers_admin):
    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 400


def test_resolver_admin_ok_para_su_consorcio(db_session):
    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    cid = get_consorcio_activo(req, user, db_session)
    assert cid == 1


def test_resolver_admin_403_para_consorcio_de_otro_tenant(db_session):
    from backend.models import Administracion, Consorcio
    # crear un 2do tenant + consorcio
    a2 = Administracion(razon_social="Otro", cuit="30-99-9", email_contacto="o@o.com")
    db_session.add(a2); db_session.flush()
    c2 = Consorcio(administracion_id=a2.id, nombre="Otro",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22)
    db_session.add(c2); db_session.commit()

    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": str(c2.id)})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403


def test_resolver_depto_ok_para_su_consorcio(db_session):
    user = CurrentUser(id=2, rol=Rol.departamento, departamento_id=1, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    cid = get_consorcio_activo(req, user, db_session)
    assert cid == 1


def test_resolver_super_admin_403(db_session):
    from backend.models import Usuario
    from backend.security import hash_password
    sa = Usuario(id=99, email="sa@x.com", password_hash=hash_password("x"), rol=Rol.super_admin)
    db_session.add(sa); db_session.commit()
    user = CurrentUser(id=99, rol=Rol.super_admin, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403


def test_resolver_bloquea_must_change_password(db_session):
    from backend.models import Usuario
    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.must_change_password = True
    db_session.commit()

    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403
    assert exc.value.detail == "cambio_password_requerido"
```

- [ ] **Step 2: Verificar failing** — `ImportError` en `backend.tenant`.

- [ ] **Step 3: Implementar**

```python
# backend/tenant.py
"""
Dependency FastAPI que resuelve el consorcio activo del header X-Consorcio-Id
y valida que el usuario autenticado tenga acceso.
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .database import get_db
from .models import Consorcio, Departamento, Rol, Usuario


def get_consorcio_activo(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """
    Resuelve X-Consorcio-Id del header, valida acceso, devuelve el ID.

    - Chequea must_change_password: 403 con detail="cambio_password_requerido".
    - super_admin: 403 (no opera directo en consorcios; usa impersonate — Plan B).
    - admin: 200 si el consorcio pertenece a su administracion_id.
    - representante: 200 si el consorcio es el suyo.
    - departamento: 200 si el consorcio es el de su departamento.
    """
    raw = request.headers.get("X-Consorcio-Id") or request.headers.get("x-consorcio-id")
    if not raw:
        raise HTTPException(400, "X-Consorcio-Id requerido")
    try:
        cid = int(raw)
    except ValueError:
        raise HTTPException(400, "X-Consorcio-Id invalido")

    u = db.query(Usuario).filter(Usuario.id == user.id).first()
    if u is None:
        raise HTTPException(401)
    if u.must_change_password:
        raise HTTPException(403, "cambio_password_requerido")

    if u.rol == Rol.administracion:
        ok = db.query(Consorcio.id).filter(
            Consorcio.id == cid,
            Consorcio.administracion_id == u.administracion_id,
        ).first() is not None
    elif u.rol == Rol.representante:
        ok = u.consorcio_id == cid
    elif u.rol == Rol.departamento:
        d = db.query(Departamento).filter(Departamento.id == u.departamento_id).first()
        ok = d is not None and d.consorcio_id == cid
    else:
        # super_admin u otro
        raise HTTPException(403, "rol_sin_scope_de_consorcio")

    if not ok:
        raise HTTPException(403, "sin acceso a este consorcio")
    return cid
```

En `tests/test_cambiar_password.py`, sacar el `@pytest.mark.xfail`.

- [ ] **Step 4: Correr tests** — Todos PASS. Incluir el test que ahora sí pasa: `test_endpoints_bloqueados_si_must_change_password`.

- [ ] **Step 5: Commit** — `feat(backend): tenant.get_consorcio_activo + enforcement de must_change_password`.

---

### Task 23: Fixtures `headers_*` inyectan `X-Consorcio-Id`; seed adaptado

**Files:**
- Modify: `tests/conftest.py`.

**Objetivo:** que los tests existentes sigan funcionando. Cambios:
1. `_seed` crea una `Administracion` (id=1) + `Consorcio` (id=1) al arrancar. Todos los datos sembrados llevan `consorcio_id=1`.
2. `admin` (usuario id=1) tiene `administracion_id=1`.
3. `representante` (usuario id=4) tiene `consorcio_id=1`.
4. Fixtures `headers_admin`, `headers_depto_a`, `headers_depto_b`, `headers_representante` devuelven un dict que incluye `X-Consorcio-Id: 1`.
5. Nueva fixture `headers_super_admin` (usuario nuevo id=5, rol super_admin, sin `X-Consorcio-Id`).

- [ ] **Step 1: Ver el estado actual del conftest** (leer, no test).

- [ ] **Step 2: Modificar `_seed`**

Antes de crear `depto_a`, agregar:

```python
from backend.models import Administracion, Consorcio  # sumar al import

admin_tenant = Administracion(
    id=1,
    razon_social="Administración Test",
    cuit="30-11111111-1",
    email_contacto="admin@test.local",
)
db.add(admin_tenant); db.flush()

consorcio = Consorcio(
    id=1,
    administracion_id=1,
    nombre="Consorcio Test",
    consorcio_domicilio="Av. Test 100",
    consorcio_cuit="30-99999999-9",
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
    caja_default_pagos_id=None,
)
db.add(consorcio); db.flush()
```

Y a cada instancia sembrada (Departamento, Peticion, Expensa, etc.) agregar `consorcio_id=1`.

Al usuario `admin` agregar `administracion_id=1`.

Al usuario `repre` agregar `consorcio_id=1`.

Reemplazar el bloque `ConfiguracionConsorcio(...)` por nada (ya no existe — Task 16 lo eliminó del modelo).

Cambiar `caja_seed`: agregar `consorcio_id=1`. Ojo con `Consorcio.caja_default_pagos_id`: lo actualizamos post-flush:

```python
consorcio.caja_default_pagos_id = 900
```

- [ ] **Step 3: Modificar fixtures `headers_*`**

```python
@pytest.fixture()
def headers_admin() -> dict[str, str]:
    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    return {
        "Authorization": f"Bearer {token}",
        "X-Consorcio-Id": "1",
    }


@pytest.fixture()
def headers_depto_a() -> dict[str, str]:
    token = create_access_token(user_id=2, rol=Rol.departamento, departamento_id=1)
    return {
        "Authorization": f"Bearer {token}",
        "X-Consorcio-Id": "1",
    }


# idem headers_depto_b y headers_representante

@pytest.fixture()
def headers_super_admin(db_session) -> dict[str, str]:
    from backend.models import Rol, Usuario
    from backend.security import hash_password
    sa = Usuario(
        id=5, email="sa@test.local",
        password_hash=hash_password("test-pass-1234"),
        rol=Rol.super_admin,
    )
    db_session.add(sa); db_session.commit()
    token = create_access_token(user_id=5, rol=Rol.super_admin, departamento_id=None)
    return {"Authorization": f"Bearer {token}"}  # sin X-Consorcio-Id
```

- [ ] **Step 4: Correr toda la suite**

Run: `./.venv/Scripts/python.exe -m pytest -x`

Esperado: la mayoría de tests PASS. Los routers operacionales **fallarán** porque todavía no tienen la dep `get_consorcio_activo` (Tasks 24-33). Si al ejecutar aparecen muchos test failures de routers, dejar así — se van corrigiendo en las próximas tasks. Verificar que al menos los tests de **auth**, **migración**, **seed**, **tenant**, **cambiar-password**, **me-consorcios** pasan.

- [ ] **Step 5: Commit** — `test: conftest siembra administracion+consorcio y fixtures inyectan X-Consorcio-Id`.

---

## Fase 6 — Adaptar routers operacionales

**Patrón común para todas las tareas de esta fase:**

Cada router del grupo:

1. Agregar import: `from ..tenant import get_consorcio_activo`.
2. Cada endpoint operacional agrega parameter `cid: int = Depends(get_consorcio_activo)`.
3. Cada query pasa a filtrar por `consorcio_id == cid`.
4. Cada INSERT/CREATE setea `consorcio_id=cid` en el objeto nuevo.
5. Los tests existentes ya pasan `X-Consorcio-Id` via fixtures (Task 23). No hay que modificar tests salvo si algún test testeaba explícitamente el 400 sin header.

**Ejemplo canónico (aplicable a todos):**

Antes:
```python
@router.get("/comunicados")
def listar_comunicados(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante, Rol.departamento)),
):
    return db.query(Comunicado).order_by(Comunicado.fecha_publicacion.desc()).all()
```

Después:
```python
@router.get("/comunicados")
def listar_comunicados(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
):
    return db.query(Comunicado).filter(
        Comunicado.consorcio_id == cid
    ).order_by(Comunicado.fecha_publicacion.desc()).all()
```

Al crear:
```python
c = Comunicado(
    consorcio_id=cid,
    titulo=body.titulo,
    cuerpo=body.cuerpo,
    autor_id=user.id,
)
```

### Task 24: Router `comunicados`

**Files:**
- Modify: `backend/routers/comunicados.py`.
- Verify: `tests/test_comunicados.py` (deben pasar sin cambios).

- [ ] **Step 1: Correr tests actuales**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_comunicados.py -v`
Expected: probablemente rojos (falta el filtro y setter).

- [ ] **Step 2: Implementar el patrón canónico**

Modificar cada endpoint del router (`listar`, `crear`, `borrar`, etc.) siguiendo el patrón.

- [ ] **Step 3: Correr tests** — PASS.

- [ ] **Step 4: Test extra de aislamiento**

Agregar a `tests/test_comunicados.py`:

```python
def test_admin_no_ve_comunicados_de_otro_consorcio(client, db_session, headers_admin):
    from backend.models import Administracion, Consorcio, Comunicado
    a2 = Administracion(razon_social="Otro", cuit="30-99-9", email_contacto="o@o.com")
    db_session.add(a2); db_session.flush()
    c2 = Consorcio(administracion_id=a2.id, nombre="Otro",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22)
    db_session.add(c2); db_session.flush()
    db_session.add(Comunicado(consorcio_id=c2.id, titulo="Secreto", cuerpo="No debería verse", autor_id=1))
    db_session.commit()

    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200
    titulos = [c["titulo"] for c in r.json()]
    assert "Secreto" not in titulos
```

- [ ] **Step 5: Commit** — `feat(backend): router comunicados scoped por consorcio`.

---

### Task 25: Routers grupo expensas (`expensas`, `comprobantes`, `movimientos`, `periodos`)

- [ ] **Step 1: Correr tests actuales del grupo** — anotar failures.
- [ ] **Step 2: Aplicar patrón canónico a cada router**.
- [ ] **Step 3: Correr tests** — PASS.
- [ ] **Step 4: Sumar 1 test de aislamiento por router (mismo patrón que Task 24 step 4)**.
- [ ] **Step 5: Commit** — `feat(backend): grupo expensas scoped por consorcio`.

---

### Task 26: Routers grupo gastos (`gastos`, `gastos_habituales`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo gastos scoped por consorcio`.

---

### Task 27: Routers grupo tareas (`peticiones`, `trabajos`, `trabajos_recurrentes`, `presupuestos`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo tareas scoped por consorcio`.

---

### Task 28: Routers grupo amenities/reservas (`amenities`, `reservas`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo amenities/reservas scoped por consorcio`.

---

### Task 29: Routers grupo tesorería (`cajas`, `transferencias_caja`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo tesoreria scoped por consorcio`.

---

### Task 30: Routers grupo catálogos (`clases_prorrateo`, `proveedores`, `departamentos`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo catalogos scoped por consorcio`.

---

### Task 31: Routers grupo personal (`empleados`, `haberes`, `conceptos_liquidacion`, `liquidaciones`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo personal scoped por consorcio`.

---

### Task 32: Routers grupo reportes (`reportes`, `estado_financiero`)

Steps 1-5 patrón standard. Commit: `feat(backend): grupo reportes scoped por consorcio`.

---

### Task 33: Router notificaciones

Steps 1-5 patrón standard. Commit: `feat(backend): notificaciones scoped por consorcio`.

---

## Fase 7 — Tests globales de aislamiento

### Task 34: Fixture `dos_consorcios` en `conftest.py`

**Files:**
- Modify: `tests/conftest.py`.

- [ ] **Step 1: Escribir fixture**

```python
@pytest.fixture()
def dos_consorcios(db_session):
    """
    Segundo tenant + segundo consorcio + admin/depto/rep asociados,
    para tests de aislamiento cross-tenant.
    Devuelve dict con IDs y headers de ambos lados.
    """
    from backend.models import Administracion, Consorcio, Departamento, Usuario, Rol
    from backend.security import hash_password
    from backend.auth import create_access_token

    a2 = Administracion(id=2, razon_social="Otro Estudio", cuit="30-22222222-2",
                        email_contacto="otro@x.com")
    db_session.add(a2); db_session.flush()
    c2 = Consorcio(id=2, administracion_id=2, nombre="Consorcio 2",
        consorcio_domicilio="D2", consorcio_cuit="30-88-8", admin_nombre="A2",
        admin_domicilio="D2", admin_email="a2@x.com", admin_telefono="2",
        admin_cuit="20-22-2", admin_rpa="0002", admin_situacion_fiscal="RI",
        banco_titular="C2", banco_nombre="B2", banco_numero_cuenta="0-2",
        banco_cbu="1" * 22)
    db_session.add(c2); db_session.flush()

    depto2 = Departamento(id=10, consorcio_id=2, codigo="UF-2A")
    db_session.add(depto2); db_session.flush()

    admin2 = Usuario(id=20, email="admin2@test.local",
                     password_hash=hash_password("test-pass-1234"),
                     rol=Rol.administracion, administracion_id=2)
    depto2_u = Usuario(id=21, email="depto2@test.local",
                       password_hash=hash_password("test-pass-1234"),
                       rol=Rol.departamento, departamento_id=10)
    db_session.add_all([admin2, depto2_u]); db_session.commit()

    return {
        "consorcio_1": {
            "id": 1,
            "headers_admin": {
                "Authorization": f"Bearer {create_access_token(1, Rol.administracion, None)}",
                "X-Consorcio-Id": "1",
            },
        },
        "consorcio_2": {
            "id": 2,
            "headers_admin": {
                "Authorization": f"Bearer {create_access_token(20, Rol.administracion, None)}",
                "X-Consorcio-Id": "2",
            },
            "headers_depto": {
                "Authorization": f"Bearer {create_access_token(21, Rol.departamento, 10)}",
                "X-Consorcio-Id": "2",
            },
        },
    }
```

- [ ] **Step 2: Commit** — `test: fixture dos_consorcios para aislamiento cross-tenant`.

---

### Task 35: Test paramétrico de aislamiento

**Files:**
- Create: `tests/test_aislamiento_multitenant.py`.

- [ ] **Step 1: Escribir tests**

```python
# tests/test_aislamiento_multitenant.py
import pytest


ENDPOINTS_LISTADO = [
    "/comunicados",
    "/expensas",
    "/comprobantes",
    "/gastos",
    "/gastos-habituales",
    "/peticiones",
    "/trabajos",
    "/reservas",
    "/cajas",
    "/clases-prorrateo",
    "/proveedores",
    "/departamentos",
    "/empleados",
    "/haberes",
    "/conceptos-liquidacion",
    "/amenities",
]


@pytest.mark.parametrize("endpoint", ENDPOINTS_LISTADO)
def test_endpoint_sin_header_devuelve_400(client, headers_admin, endpoint):
    h = {k: v for k, v in headers_admin.items() if k != "X-Consorcio-Id"}
    r = client.get(endpoint, headers=h)
    assert r.status_code == 400


@pytest.mark.parametrize("endpoint", ENDPOINTS_LISTADO)
def test_endpoint_con_consorcio_ajeno_devuelve_403(client, dos_consorcios, endpoint):
    h = dos_consorcios["consorcio_1"]["headers_admin"].copy()
    h["X-Consorcio-Id"] = "2"  # admin del tenant 1 intenta acceder al consorcio 2
    r = client.get(endpoint, headers=h)
    assert r.status_code == 403


def test_admin_solo_lista_del_propio_consorcio(client, dos_consorcios):
    """Cada admin solo ve el listado de su consorcio."""
    r1 = client.get("/comunicados", headers=dos_consorcios["consorcio_1"]["headers_admin"])
    r2 = client.get("/comunicados", headers=dos_consorcios["consorcio_2"]["headers_admin"])
    assert r1.status_code == 200 and r2.status_code == 200
    # El consorcio 2 no tiene comunicados sembrados; el 1 sí (del seed base)
    assert len(r1.json()) >= 1
    assert len(r2.json()) == 0
```

- [ ] **Step 2: Correr** — Todo PASS.

- [ ] **Step 3: Commit** — `test: aislamiento paramétrico cross-tenant por endpoint`.

---

## Fase 8 — Documentación

### Task 36: README con sección "Migración a multitenant"

**Files:**
- Modify: `README.md` (raíz).

- [ ] **Step 1: Agregar sección al final del README:**

```markdown
## Migración a multitenant

Después de pull de esta versión, corré una única vez:

```
python -m backend.migrate_multitenant
SUPER_ADMIN_EMAIL=root@sistema.com SUPER_ADMIN_PASSWORD=<pass> python -m backend.seed_super_admin
```

La migración es idempotente: podés correrla más de una vez sin problema.

Los datos existentes quedan bajo la administración "Demo" y el consorcio "Demo"
(id=1 en ambos casos).
```

- [ ] **Step 2: Commit** — `docs: README con instrucciones de migración`.

---

### Task 37: OpenAPI — parámetro reusable `ConsorcioIdHeader`

**Files:**
- Modify: `openapi.yaml`.

**Nota:** el `openapi.yaml` del proyecto se mantiene manual (no auto-generado por FastAPI). Agregar el header reusable y aplicarlo a los endpoints operacionales.

- [ ] **Step 1: Agregar en `components.parameters`:**

```yaml
components:
  parameters:
    ConsorcioIdHeader:
      name: X-Consorcio-Id
      in: header
      required: true
      schema:
        type: integer
      description: |
        ID del consorcio activo. Requerido en todo endpoint operacional.
        El backend valida que el usuario autenticado tenga acceso a este consorcio.
```

- [ ] **Step 2: Aplicar `$ref` en cada endpoint operacional:**

```yaml
paths:
  /comunicados:
    get:
      parameters:
        - $ref: "#/components/parameters/ConsorcioIdHeader"
      # ... resto igual
```

Repetir para todos los endpoints operacionales del spec (los mismos que se modificaron en la Fase 6). Los exentos (`/auth/*`, `/me`, `/me/consorcios`, `/me/cambiar-password`) NO reciben el header.

- [ ] **Step 3: Agregar los nuevos endpoints** `GET /me/consorcios` y `POST /me/cambiar-password` al spec.

- [ ] **Step 4: Agregar códigos de error nuevos:**

```yaml
components:
  schemas:
    ErrorConsorcioIdRequerido:
      type: object
      properties:
        detail:
          type: string
          enum: ["X-Consorcio-Id requerido", "X-Consorcio-Id invalido"]
    ErrorSinAccesoConsorcio:
      type: object
      properties:
        detail:
          type: string
          enum: ["sin acceso a este consorcio", "cambio_password_requerido",
                 "administracion_suspendida"]
```

Aplicar como `responses` 400 y 403 en los endpoints.

- [ ] **Step 5: Commit** — `docs(openapi): X-Consorcio-Id + endpoints /me/*`.

---

## Definition of Done

Al terminar todas las tareas:

1. Correr `pytest -v`: todos los tests pasan.
2. Correr `python -m backend.migrate_multitenant`: idempotente, sale rápido.
3. Correr `SUPER_ADMIN_EMAIL=x SUPER_ADMIN_PASSWORD=y python -m backend.seed_super_admin`: idempotente.
4. Arrancar el server (`uvicorn backend.main:app --reload`) y verificar que el frontend actual sigue funcionando (login → comunicados → expensas → gastos). El admin del seed ve todo como antes (porque tiene 1 solo consorcio y el header `X-Consorcio-Id: 1` lo agrega ¡el frontend! **NO** — el frontend actual no manda el header; hay que agregarlo en Plan C).
5. **Excepción**: durante Plan A, para probar manualmente desde el frontend actual, agregar temporalmente al fetch wrapper del frontend: `headers['X-Consorcio-Id'] = '1'` (hack de debugging). Esto queda formalizado en Plan C.

**Al terminar Plan A, el frontend NO funciona sin ese hack.** Es el trade-off aceptado: el plan A cambia el contrato del backend. La opción alternativa (mantener `X-Consorcio-Id` opcional con default 1) fue descartada porque erosiona la seguridad y complica la remoción después.

## Riesgos y observaciones

- **SQLite `ALTER TABLE`**: la migración usa el approach "columna nullable + populate + índice". No forzamos `NOT NULL` a nivel DB (usaríamos table-rebuild). El ORM sí exige NOT NULL, así que en la práctica el sistema no permite crear filas sin `consorcio_id`. Los tests de aislamiento son la garantía dura.
- **`representante.consorcio_id`**: se agrega la columna, pero el fixture actual del seed no lo asigna. En Task 23 el `repre` sembrado recibe `consorcio_id=1`.
- **`must_change_password` enforcement**: se aplica solo en el resolver `get_consorcio_activo`. Endpoints exentos (`/me/cambiar-password`, `/me/consorcios`, `/auth/*`) permiten operar sin este chequeo — es intencional, sino nunca podría cambiar la password.
- **Seed base**: si un test necesita 0 consorcios (para el flow `/bienvenida` de Plan C), usa `db_empty` en vez de `db_session`.
- **JWT: desviación deliberada del spec.** El spec §4.2 dice "JWT solo lleva `sub`". El plan mantiene el JWT actual (con `rol` y `departamento_id`) porque cambiarlo implicaría refactor de `CurrentUser`, `create_access_token`, `decode_token` y ~28 fixtures/tests. El resolver hace lookup a la DB para `must_change_password` y `administracion_id`, así que la seguridad no se degrada. La simplificación a `sub`-only queda como refactor opcional futuro (no bloqueante).
- **Uniques globales viejos en DB (SQLite)**: los `UniqueConstraint` compuestos que agregamos en el modelo (ej: `(consorcio_id, codigo)` en `departamentos`) conviven con los uniques inline pre-migración (ej: `codigo UNIQUE` en la definición vieja de la tabla). SQLite no los elimina en `ALTER TABLE`. Consecuencia práctica: si sembrás dos consorcios y en cada uno intentás un depto con código "1A", el INSERT falla por el unique viejo global. **Mitigación en Plan A:** para los tests, los consorcios usan códigos distintos ("UF-1", "UF-2A"). **Fix definitivo:** table-rebuild de las tablas afectadas (departamentos, proveedores, amenities, clases_prorrateo, cajas, haberes, conceptos_liquidacion, empleados). Se difiere a un plan de hardening posterior — no bloquea Plan A porque no rompe el flow multitenant.
