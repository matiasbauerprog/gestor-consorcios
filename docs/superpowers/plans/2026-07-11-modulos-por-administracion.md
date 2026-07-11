# Módulos habilitables por Administración (super_admin) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El rol `super_admin` puede habilitar/deshabilitar módulos funcionales por Administración (cliente SaaS); el backend devuelve 403 `modulo_no_habilitado` en endpoints de módulos apagados y el frontend oculta los ítems del sidebar.

**Architecture:** Columna `modulos_habilitados` (JSON text, `NULL` = todos habilitados) en `administraciones`. Un módulo nuevo `backend/modulos.py` define el catálogo de 8 módulos y la dependency-factory `require_modulo(key)` que se agrega como dependencia router-level en los 14 routers gateados. Dos endpoints nuevos en `/super-admin` (GET/PUT módulos) con audit log. El frontend recibe `modulos_habilitados` dentro de `ConsorcioOut` (el Sidebar ya hace `GET /consorcios/{id}`) y filtra ítems; el panel super_admin gana un modal de toggles.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + SQLite (migración idempotente al startup), Pydantic v2, React + Vite, pytest.

---

## Catálogo de módulos (contrato)

| Key | Sidebar | Routers backend gateados |
|---|---|---|
| `comunicacion` | Comunicación | `comunicados.py` |
| `cobranzas` | Mi cuenta, Cobranzas, Cuentas corrientes | `expensas.py`, `comprobantes.py`, `movimientos.py` |
| `gastos` | Gastos | `gastos.py`, `gastos_habituales.py` |
| `finanzas` | Tesorería | `estado_financiero.py`, `cajas.py`, `transferencias_caja.py` |
| `operacion` | Peticiones, Trabajos, Trabajos recurrentes | `peticiones.py`, `trabajos.py`, `presupuestos.py`, `trabajos_recurrentes.py` |
| `espacios_comunes` | Reservas, Amenities | `amenities.py`, `reservas.py` |
| `reportes` | Reportes (4 pantallas) | `reportes.py` |
| `personal` | Personal (4 pantallas) | `empleados.py`, `haberes.py`, `conceptos_liquidacion.py`, `liquidaciones.py` |

**NO gateados (core, siempre activos):** `auth`, `me`, `usuarios`, `departamentos`, `padron`, `coeficientes`, `clases_prorrateo`, `proveedores`, `configuracion`, `consorcios`, `periodos` (cross-cutting: lo usan Expensas y Gastos), `notificaciones`, `super_admin`.

**Notas de diseño:**
- `NULL` en la columna = todos los módulos habilitados (backward-compatible, y si mañana se agrega un módulo nuevo las administraciones sin override lo reciben gratis).
- El flag existente `Consorcio.usa_personal_propio` NO se toca: es un refinamiento del admin por consorcio; el módulo `personal` es el switch del super_admin por administración. Ambos deben estar en true para ver el grupo Personal.
- `require_modulo` depende de `get_consorcio_activo`, así que hereda todos sus chequeos (X-Consorcio-Id, must_change_password, suspensión). FastAPI cachea deps por request: no hay query duplicada de `get_consorcio_activo`.

---

### Task 1: Modelo + migración idempotente de la columna

**Files:**
- Modify: `backend/models.py` (imports línea 4-15 y clase `Administracion` línea ~956)
- Modify: `backend/main.py` (nueva `_migrar_administracion_modulos()` junto a `_migrar_usuario_activa`, línea ~58, y llamada en `lifespan` línea ~108)
- Test: `tests/test_super_admin_modulos.py` (nuevo)

- [ ] **Step 1: Escribir el test que falla** — crear `tests/test_super_admin_modulos.py`:

```python
"""Tests de módulos habilitables por administración (super_admin)."""


def test_administracion_tiene_columna_modulos(db_session):
    from backend.models import Administracion

    a = db_session.get(Administracion, 1)
    assert a is not None
    assert a.modulos_habilitados is None  # NULL = todos habilitados
```

- [ ] **Step 2: Verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: FAIL con `AttributeError: ... object has no attribute 'modulos_habilitados'`

- [ ] **Step 3: Implementar** — en `backend/models.py`:

Agregar `Text` al import de sqlalchemy (línea 4-15):

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
    Text,
    UniqueConstraint,
    func,
)
```

En la clase `Administracion` (después de `plan`, línea ~964):

```python
    # JSON array de keys de módulos habilitados; NULL = todos habilitados.
    modulos_habilitados: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
```

En `backend/main.py`, después de `_migrar_usuario_activa` (línea ~67):

```python
def _migrar_administracion_modulos() -> None:
    """ALTER TABLE idempotente: agrega modulos_habilitados a administraciones."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(administraciones)"))}
        if cols and "modulos_habilitados" not in cols:
            conn.execute(text(
                "ALTER TABLE administraciones ADD COLUMN modulos_habilitados TEXT"
            ))
```

Y en `lifespan` (línea ~108), después de `_migrar_pk_periodos_cerrados()`:

```python
    _migrar_administracion_modulos()
```

- [ ] **Step 4: Verificar que pasa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/main.py tests/test_super_admin_modulos.py
git commit -m "feat(saas): columna modulos_habilitados en administraciones + migracion idempotente"
```

---

### Task 2: Catálogo de módulos + dependency `require_modulo`

**Files:**
- Create: `backend/modulos.py`
- Test: `tests/test_super_admin_modulos.py` (agregar)

- [ ] **Step 1: Escribir tests que fallan** — agregar a `tests/test_super_admin_modulos.py`:

```python
def test_catalogo_de_modulos():
    from backend.modulos import MODULOS

    assert MODULOS == (
        "comunicacion", "cobranzas", "gastos", "finanzas",
        "operacion", "espacios_comunes", "reportes", "personal",
    )


def test_modulos_habilitados_de_null_devuelve_todos(db_session):
    from backend.models import Administracion
    from backend.modulos import MODULOS, modulos_habilitados_de

    a = db_session.get(Administracion, 1)
    assert modulos_habilitados_de(a) == set(MODULOS)


def test_modulos_habilitados_de_parsea_json(db_session):
    from backend.models import Administracion
    from backend.modulos import modulos_habilitados_de

    a = db_session.get(Administracion, 1)
    a.modulos_habilitados = '["gastos", "cobranzas"]'
    assert modulos_habilitados_de(a) == {"gastos", "cobranzas"}
```

- [ ] **Step 2: Verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.modulos'`

- [ ] **Step 3: Crear `backend/modulos.py`**

```python
"""Catálogo de módulos habilitables por administración (control de super_admin).

`require_modulo(key)` es una dependency-factory router-level: hereda los
chequeos de `get_consorcio_activo` (header, password, suspensión) y suma el
gate del módulo. NULL en `Administracion.modulos_habilitados` = todos activos.
"""
from __future__ import annotations

import json

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Administracion, Consorcio
from .tenant import get_consorcio_activo

MODULOS = (
    "comunicacion",
    "cobranzas",
    "gastos",
    "finanzas",
    "operacion",
    "espacios_comunes",
    "reportes",
    "personal",
)


def modulos_habilitados_de(admin: Administracion) -> set[str]:
    if admin.modulos_habilitados is None:
        return set(MODULOS)
    return set(json.loads(admin.modulos_habilitados))


def require_modulo(modulo: str):
    if modulo not in MODULOS:
        raise ValueError(f"Módulo desconocido: {modulo}")

    def dep(
        cid: int = Depends(get_consorcio_activo),
        db: Session = Depends(get_db),
    ) -> int:
        admin = db.scalar(
            select(Administracion)
            .join(Consorcio, Consorcio.administracion_id == Administracion.id)
            .where(Consorcio.id == cid)
        )
        if admin is None or modulo not in modulos_habilitados_de(admin):
            raise HTTPException(status_code=403, detail="modulo_no_habilitado")
        return cid

    return dep
```

- [ ] **Step 4: Verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/modulos.py tests/test_super_admin_modulos.py
git commit -m "feat(saas): catalogo de modulos + dependency require_modulo"
```

---

### Task 3: Endpoints super_admin GET/PUT módulos (OpenAPI-first)

**Files:**
- Modify: `openapi.yaml` (después del path `/super-admin/administraciones/{administracion_id}/reset-password/{user_id}`, línea ~3933)
- Modify: `backend/schemas.py` (después de `AdministracionActualizar`, línea ~1166)
- Modify: `backend/routers/super_admin.py` (nueva sección después del CRUD, línea ~213)
- Test: `tests/test_super_admin_modulos.py` (agregar)

- [ ] **Step 1: Documentar en `openapi.yaml`** (regla openapi-first — ANTES del código). Agregar bajo la sección de paths de super-admin, una sola entrada de path con ambos verbos:

```yaml
  /super-admin/administraciones/{administracion_id}/modulos:
    get:
      tags: [SuperAdmin]
      summary: Obtener módulos habilitados de una administración
      security:
        - bearerAuth: []
      parameters:
        - name: administracion_id
          in: path
          required: true
          schema: { type: integer }
      responses:
        "200":
          description: Módulos disponibles y habilitados
          content:
            application/json:
              schema:
                type: object
                properties:
                  disponibles:
                    type: array
                    items: { type: string }
                  habilitados:
                    type: array
                    items: { type: string }
        "401": { description: Token ausente o inválido }
        "403": { description: Rol sin permisos }
        "404": { description: Administración no encontrada }
    put:
      tags: [SuperAdmin]
      summary: Reemplazar módulos habilitados de una administración
      security:
        - bearerAuth: []
      parameters:
        - name: administracion_id
          in: path
          required: true
          schema: { type: integer }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [habilitados]
              properties:
                habilitados:
                  type: array
                  items: { type: string }
      responses:
        "200":
          description: Módulos actualizados
        "400": { description: Módulo desconocido en la lista }
        "401": { description: Token ausente o inválido }
        "403": { description: Rol sin permisos }
        "404": { description: Administración no encontrada }
```

- [ ] **Step 2: Escribir tests que fallan** — agregar a `tests/test_super_admin_modulos.py`:

```python
def test_get_modulos_default_todos(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/1/modulos", headers=headers_super_admin)
    assert r.status_code == 200
    body = r.json()
    assert set(body["disponibles"]) == set(body["habilitados"])
    assert "gastos" in body["habilitados"]


def test_put_modulos_persiste_subset(client, headers_super_admin):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["comunicacion", "cobranzas"]},
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    assert sorted(r.json()["habilitados"]) == ["cobranzas", "comunicacion"]

    r2 = client.get("/super-admin/administraciones/1/modulos", headers=headers_super_admin)
    assert sorted(r2.json()["habilitados"]) == ["cobranzas", "comunicacion"]


def test_put_modulo_desconocido_devuelve_400(client, headers_super_admin):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["inventado"]},
        headers=headers_super_admin,
    )
    assert r.status_code == 400


def test_put_modulos_admin_normal_devuelve_403(client, headers_admin):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["gastos"]},
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_get_modulos_administracion_inexistente_devuelve_404(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/999/modulos", headers=headers_super_admin)
    assert r.status_code == 404


def test_put_modulos_genera_audit_log(client, headers_super_admin):
    client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": ["gastos"]},
        headers=headers_super_admin,
    )
    r = client.get(
        "/super-admin/audit-log?accion=editar_modulos", headers=headers_super_admin
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["administracion_id_afectada"] == 1
```

- [ ] **Step 3: Verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: los 6 tests nuevos FAIL con 404 (ruta no existe) o similar.

- [ ] **Step 4: Schemas** — en `backend/schemas.py` después de `AdministracionActualizar` (línea ~1166):

```python
class ModulosAdministracionIn(BaseModel):
    habilitados: list[str]


class ModulosAdministracionOut(BaseModel):
    disponibles: list[str]
    habilitados: list[str]
```

- [ ] **Step 5: Endpoints** — en `backend/routers/super_admin.py`:

Sumar imports: en el bloque `from ..schemas import (...)` agregar `ModulosAdministracionIn, ModulosAdministracionOut`; y debajo del bloque de imports existente agregar:

```python
import json

from ..modulos import MODULOS, modulos_habilitados_de
```

Nueva sección después de `toggle_suspender_administracion` (línea ~213):

```python
# ---------------------------------------------------------------------------
# Módulos habilitados
# ---------------------------------------------------------------------------


@router.get(
    "/administraciones/{administracion_id}/modulos",
    response_model=ModulosAdministracionOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener módulos habilitados de una administración",
)
def obtener_modulos_administracion(
    administracion_id: int,
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> ModulosAdministracionOut:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")
    return ModulosAdministracionOut(
        disponibles=list(MODULOS),
        habilitados=sorted(modulos_habilitados_de(admin)),
    )


@router.put(
    "/administraciones/{administracion_id}/modulos",
    response_model=ModulosAdministracionOut,
    status_code=status.HTTP_200_OK,
    summary="Reemplazar módulos habilitados de una administración",
)
def actualizar_modulos_administracion(
    administracion_id: int,
    payload: ModulosAdministracionIn,
    db: Session = Depends(get_db),
    sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> ModulosAdministracionOut:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")

    desconocidos = set(payload.habilitados) - set(MODULOS)
    if desconocidos:
        raise HTTPException(
            status_code=400,
            detail=f"Módulos desconocidos: {', '.join(sorted(desconocidos))}",
        )

    habilitados = sorted(set(payload.habilitados))
    admin.modulos_habilitados = json.dumps(habilitados)

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=sa.id,
        accion="editar_modulos",
        administracion_id_afectada=admin.id,
        detalles={"habilitados": habilitados},
    )
    db.commit()
    return ModulosAdministracionOut(disponibles=list(MODULOS), habilitados=habilitados)
```

- [ ] **Step 6: Verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: PASS (10 tests)

- [ ] **Step 7: Commit**

```bash
git add openapi.yaml backend/schemas.py backend/routers/super_admin.py tests/test_super_admin_modulos.py
git commit -m "feat(saas): endpoints GET/PUT modulos por administracion con audit log"
```

---

### Task 4: Aplicar el gate 403 a los 14 routers

**Files:**
- Modify: `backend/routers/comunicados.py:13`, `expensas.py:24`, `comprobantes.py:40`, `movimientos.py` (línea del APIRouter), `gastos.py:35`, `gastos_habituales.py:15`, `estado_financiero.py:16`, `cajas.py:13`, `transferencias_caja.py:15`, `peticiones.py:14`, `trabajos.py:28`, `presupuestos.py:22`, `trabajos_recurrentes.py:20`, `amenities.py:21`, `reservas.py:15`, `reportes.py:35`, `empleados.py:11`, `haberes.py:11`, `conceptos_liquidacion.py:15`, `liquidaciones.py:36`
- Test: `tests/test_super_admin_modulos.py` (agregar)

- [ ] **Step 1: Escribir tests que fallan** — agregar a `tests/test_super_admin_modulos.py`:

```python
def _deshabilitar(client, headers_super_admin, *modulos_activos):
    r = client.put(
        "/super-admin/administraciones/1/modulos",
        json={"habilitados": list(modulos_activos)},
        headers=headers_super_admin,
    )
    assert r.status_code == 200


def test_modulo_deshabilitado_devuelve_403(client, headers_admin, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "comunicacion")  # gastos queda OFF
    r = client.get("/gastos", headers=headers_admin)
    assert r.status_code == 403
    assert r.json()["detail"] == "modulo_no_habilitado"


def test_modulo_habilitado_sigue_funcionando(client, headers_admin, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "comunicacion")
    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200


def test_gate_aplica_tambien_a_departamentos(client, headers_depto_a, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "gastos")  # cobranzas OFF
    r = client.get("/movimientos/mi-cuenta", headers=headers_depto_a)
    assert r.status_code == 403
    assert r.json()["detail"] == "modulo_no_habilitado"


def test_rehabilitar_modulo_restaura_acceso(client, headers_admin, headers_super_admin):
    _deshabilitar(client, headers_super_admin, "comunicacion")
    assert client.get("/gastos", headers=headers_admin).status_code == 403
    _deshabilitar(client, headers_super_admin, *__import__("backend.modulos", fromlist=["MODULOS"]).MODULOS)
    assert client.get("/gastos", headers=headers_admin).status_code == 200
```

Nota: si `GET /gastos` requiere query params obligatorios, ajustar la URL según la firma real del endpoint (mirar `backend/routers/gastos.py`); lo que se asserta es 403 vs no-403.

- [ ] **Step 2: Verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: los 4 tests nuevos FAIL (devuelven 200 donde se espera 403).

- [ ] **Step 3: Aplicar el gate router-level.** En cada router listado, agregar el import y la dependencia. Patrón (ejemplo `backend/routers/gastos.py:35`):

```python
from ..modulos import require_modulo
```

y cambiar la línea del APIRouter:

```python
router = APIRouter(
    prefix="/gastos",
    tags=["Gastos"],
    dependencies=[Depends(require_modulo("gastos"))],
)
```

Mapa exacto archivo → key (repetir el patrón en cada uno):

| Archivo | key |
|---|---|
| `comunicados.py` | `comunicacion` |
| `expensas.py`, `comprobantes.py`, `movimientos.py` | `cobranzas` |
| `gastos.py`, `gastos_habituales.py` | `gastos` |
| `estado_financiero.py`, `cajas.py`, `transferencias_caja.py` | `finanzas` |
| `peticiones.py`, `trabajos.py`, `presupuestos.py`, `trabajos_recurrentes.py` | `operacion` |
| `amenities.py`, `reservas.py` | `espacios_comunes` |
| `reportes.py` | `reportes` |
| `empleados.py`, `haberes.py`, `conceptos_liquidacion.py`, `liquidaciones.py` | `personal` |

Verificar que cada archivo ya importe `Depends` de fastapi (todos lo hacen — usan `Depends(get_db)`).

**Ojo:** `presupuestos.py` y `trabajos.py` comparten `prefix="/trabajos"` — ambos van con key `operacion`, no hay conflicto.

- [ ] **Step 4: Correr los tests nuevos**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Correr la suite COMPLETA** (regresión crítica: el gate router-level exige que todos los endpoints de esos routers pasen por `get_consorcio_activo`; si algún endpoint no mandaba X-Consorcio-Id en tests, acá explota)

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos PASS. Si algún test viejo falla con 400 "X-Consorcio-Id requerido", ese endpoint no era tenant-scoped: evaluar si corresponde moverlo fuera del gate (excepción puntual con `dependencies` por-endpoint en vez de router-level) y documentar la decisión en el commit.

- [ ] **Step 6: Commit**

```bash
git add backend/routers tests/test_super_admin_modulos.py
git commit -m "feat(saas): gate 403 modulo_no_habilitado en 20 routers segun modulos de la administracion"
```

---

### Task 5: `ConsorcioOut.modulos_habilitados` (para el Sidebar)

**Files:**
- Modify: `backend/schemas.py` (clase `ConsorcioOut` — buscar `class ConsorcioOut`)
- Test: `tests/test_super_admin_modulos.py` (agregar)

- [ ] **Step 1: Escribir test que falla**

```python
def test_consorcio_out_incluye_modulos(client, headers_admin, headers_super_admin):
    r = client.get("/consorcios/1", headers=headers_admin)
    assert r.status_code == 200
    from backend.modulos import MODULOS
    assert set(r.json()["modulos_habilitados"]) == set(MODULOS)

    _deshabilitar(client, headers_super_admin, "comunicacion", "cobranzas")
    r2 = client.get("/consorcios/1", headers=headers_admin)
    assert sorted(r2.json()["modulos_habilitados"]) == ["cobranzas", "comunicacion"]
```

- [ ] **Step 2: Verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py::test_consorcio_out_incluye_modulos -v`
Expected: FAIL con `KeyError: 'modulos_habilitados'`

- [ ] **Step 3: Implementar** — en `backend/schemas.py`, dentro de `class ConsorcioOut` agregar el campo y un validator (mismo patrón que `ComprobanteOut.departamento_codigo`):

```python
    modulos_habilitados: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _derivar_modulos(cls, data):
        if hasattr(data, "administracion") and data.administracion is not None:
            from .modulos import modulos_habilitados_de

            object.__setattr__ = object.__setattr__  # no-op para claridad
            valores = sorted(modulos_habilitados_de(data.administracion))
            d = {c: getattr(data, c) for c in data.__mapper__.columns.keys()}
            d["modulos_habilitados"] = valores
            return d
        return data
```

**Simplificación preferida** (usar esta si `ComprobanteOut` usa el patrón dict): copiar EXACTAMENTE el patrón que ya usa `ComprobanteOut.departamento_codigo` en el mismo archivo, cambiando `departamento.codigo` por `sorted(modulos_habilitados_de(data.administracion))`. Requiere que `Consorcio` tenga la relationship `administracion`; si `backend/models.py` no la define (solo existe el back_populates en `Administracion.consorcios`), agregar en `class Consorcio`:

```python
    administracion: Mapped["Administracion"] = relationship(back_populates="consorcios")
```

- [ ] **Step 4: Verificar que pasa + suite completa**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_super_admin_modulos.py tests/test_consorcios.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py backend/models.py tests/test_super_admin_modulos.py
git commit -m "feat(saas): ConsorcioOut expone modulos_habilitados de la administracion"
```

---

### Task 6: Sidebar — filtrar ítems por módulos habilitados

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Agregar key `modulo` a cada ítem de `SECCIONES`** (líneas 9-170). Mapa ruta → módulo:

```
/comunicados → "comunicacion"
/mi-cuenta, /cobranzas, /cuentas-corrientes → "cobranzas"
/gastos → "gastos"
/tesoreria → "finanzas"
/peticiones, /trabajos, /trabajos-recurrentes → "operacion"
/reservas, /amenities → "espacios_comunes"
/reportes/* (los 4) → "reportes"
/liquidaciones, /haberes, /conceptos-liquidacion, /empleados → "personal"
ítems de Configuración → sin key (siempre visibles)
```

Ejemplo del cambio (aplicar igual en todos):

```javascript
      {
        ruta: "/gastos",
        nombre: "Gastos",
        rolesPermitidos: ["administracion"],
        modulo: "gastos",
      },
```

- [ ] **Step 2: Estado + fetch.** El `useEffect` de la línea 206 ya llama `obtenerConsorcio(consorcioActivoId)` — capturar también los módulos:

```javascript
  const [modulosHabilitados, setModulosHabilitados] = useState(null); // null = cargando → mostrar todo
```

y dentro del `useEffect`, después del bloque de `usa_personal_propio`:

```javascript
      if (c.status === 200 && Array.isArray(c.data?.modulos_habilitados)) {
        setModulosHabilitados(c.data.modulos_habilitados);
      }
```

- [ ] **Step 3: Filtrar.** En `seccionesVisibles` (línea 222), dentro del `.filter((m) => {...})` agregar antes del `return true`:

```javascript
      // Módulo deshabilitado por super_admin para esta administración.
      if (m.modulo && modulosHabilitados !== null && !modulosHabilitados.includes(m.modulo)) {
        return false;
      }
```

- [ ] **Step 4: Verificación manual + build**

Run: `cd frontend && npm run build`
Expected: build OK sin warnings nuevos.

Luego `npm run dev` + login como super_admin → deshabilitar "Gastos" a la administración 1 → login como admin del consorcio 1 → el ítem Gastos no aparece y `GET /gastos` directo da 403. (La UI del super_admin llega en Task 7; para esta verificación usar `curl` o Swagger `/docs` para el PUT.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "feat(saas): sidebar filtra modulos deshabilitados por super_admin"
```

---

### Task 7: Panel super_admin — modal de módulos

**Files:**
- Modify: `frontend/src/api/superAdmin.js`
- Modify: `frontend/src/screens/SuperAdminAdministraciones.jsx`

- [ ] **Step 1: API helpers** — agregar a `frontend/src/api/superAdmin.js`:

```javascript
export async function obtenerModulos(administracionId) {
  return apiFetch(`/super-admin/administraciones/${administracionId}/modulos`);
}

export async function guardarModulos(administracionId, habilitados) {
  return apiFetch(`/super-admin/administraciones/${administracionId}/modulos`, {
    method: "PUT",
    body: { habilitados },
  });
}
```

- [ ] **Step 2: Modal** — en `frontend/src/screens/SuperAdminAdministraciones.jsx`, importar los helpers nuevos (línea 4-12) y agregar el componente antes de `ModalMotivoImpersonate` (línea ~118):

```javascript
const MODULOS_LABELS = {
  comunicacion: "Comunicación",
  cobranzas: "Cobranzas y cuentas corrientes",
  gastos: "Gastos del consorcio",
  finanzas: "Tesorería y finanzas",
  operacion: "Peticiones y trabajos",
  espacios_comunes: "Espacios comunes (reservas)",
  reportes: "Reportes",
  personal: "Personal y liquidaciones",
};

function ModalModulos({ administracion, onCerrar, onFeedback }) {
  const [disponibles, setDisponibles] = useState([]);
  const [habilitados, setHabilitados] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    (async () => {
      const r = await obtenerModulos(administracion.id);
      if (r.status === 200) {
        setDisponibles(r.data.disponibles);
        setHabilitados(new Set(r.data.habilitados));
      } else {
        setErr(r.data?.detail || "No se pudieron cargar los módulos.");
      }
      setLoading(false);
    })();
  }, [administracion.id]);

  function toggle(key) {
    setHabilitados((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function guardar(e) {
    e.preventDefault();
    setErr(null);
    setGuardando(true);
    const r = await guardarModulos(administracion.id, [...habilitados]);
    setGuardando(false);
    if (r.status === 200) {
      onFeedback(`Módulos actualizados para ${administracion.razon_social}.`);
      onCerrar();
      return;
    }
    setErr(r.data?.detail || "No se pudieron guardar los módulos.");
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>Módulos — {administracion.razon_social}</h2>
          <button type="button" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        {loading ? (
          <p>Cargando…</p>
        ) : (
          <form onSubmit={guardar}>
            <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "0.5rem" }}>
              {disponibles.map((key) => (
                <li key={key}>
                  <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={habilitados.has(key)}
                      onChange={() => toggle(key)}
                    />
                    {MODULOS_LABELS[key] || key}
                  </label>
                </li>
              ))}
            </ul>
            {err && <p role="alert" className="login-error">{err}</p>}
            <div className="modal-acciones">
              <button type="button" onClick={onCerrar}>
                Cancelar
              </button>
              <button type="submit" disabled={guardando}>
                {guardando ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Botón + estado en la pantalla.** En el componente principal (línea ~320): agregar estado `const [modalModulosDe, setModalModulosDe] = useState(null);`, un botón junto a "Gestionar usuarios" (línea ~435):

```javascript
                  <button type="button" onClick={() => setModalModulosDe(a)}>
                    Módulos
                  </button>
```

y el render del modal junto a los otros modales (línea ~456):

```javascript
      {modalModulosDe && (
        <ModalModulos
          administracion={modalModulosDe}
          onCerrar={() => setModalModulosDe(null)}
          onFeedback={setFeedback}
        />
      )}
```

- [ ] **Step 4: Verificación en browser**

Run: `cd frontend && npm run build` → Expected: build OK.
Luego con dev server: login super_admin → Administraciones → botón "Módulos" → desmarcar "Gastos del consorcio" → Guardar → login admin → sidebar sin Gastos → rehabilitar → reaparece. Probar también a 375px de ancho (regla mobile-first).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/superAdmin.js frontend/src/screens/SuperAdminAdministraciones.jsx
git commit -m "feat(saas): panel super_admin para habilitar/deshabilitar modulos por administracion"
```

---

### Task 8: Regresión final

- [ ] **Step 1: Suite backend completa**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todos PASS (~890 tests).

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit final si quedó algo suelto; NO push sin confirmación del usuario.**

---

## Self-Review (ya aplicada)

- **Cobertura:** modelo+migración (T1), catálogo+gate (T2), endpoints superadmin+openapi+audit (T3), enforcement 403 en routers (T4), exposición al frontend (T5), sidebar (T6), panel superadmin (T7), regresión (T8). ✓
- **Consistencia de nombres:** `modulos_habilitados` (columna/campo), `require_modulo`, `modulos_habilitados_de`, `MODULOS`, detail `"modulo_no_habilitado"`, acción de audit `"editar_modulos"` — usados idénticos en todas las tasks. ✓
- **Riesgo conocido:** Task 4 Step 5 puede revelar endpoints no tenant-scoped dentro de routers gateados; la mitigación está documentada en el propio step.
- **Nota Task 5:** el validator debe copiar el patrón real de `ComprobanteOut` del archivo — el snippet alternativo del Step 3 es la guía si el patrón difiere.
