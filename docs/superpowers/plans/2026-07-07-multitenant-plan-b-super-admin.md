# Multitenant Plan B — Super-Admin (Impersonate + Audit + Métricas) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el super-admin backend: CRUD de administraciones, reset-password para usuarios de un tenant, impersonate con JWT temporal + banner y audit log, métricas globales, y endpoint de audit log.

**Architecture:** Router dedicado `/super-admin/*` con require_roles(Rol.super_admin). Audit log en la tabla `audit_log_super_admin` (ya sembrada en Plan A). Impersonate emite un JWT con claim `impersonated_by`; una dependencia FastAPI aplicada al router principal detecta ese claim en operaciones mutantes y las persiste en el audit log con body redactado. Bloqueo duro: rutas `/super-admin/*` (excepto `/impersonate/end`) rechazan JWT impersonado con 403.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · PyJWT (HS256, ya en uso) · pytest.

---

## File Structure

**Nuevos archivos:**
- `backend/audit.py` — helpers para crear entradas de audit log + redactor de campos sensibles.
- `backend/routers/super_admin.py` — todos los endpoints `/super-admin/*` en un archivo (chico, coherente).
- `backend/middleware/impersonate_audit.py` — middleware ASGI que loguea mutaciones cuando el JWT tiene `impersonated_by`.
- `tests/test_super_admin_administraciones.py`
- `tests/test_super_admin_impersonate.py`
- `tests/test_super_admin_metricas_audit.py`

**Archivos modificados:**
- `backend/auth.py` — `create_access_token` acepta `impersonated_by`; `get_current_user` lo expone; `CurrentUser` gana el campo.
- `backend/main.py` — registra router + middleware.
- `backend/schemas.py` — schemas del super-admin (AdministracionCrear/Actualizar/Out, ResetPasswordOut, ImpersonateStartIn/Out, MetricasOut, AuditLogOut).
- `openapi.yaml` — endpoints super-admin documentados, tag nuevo.
- `README.md` — nota corta sobre Plan B.

---

## Task 1: Helpers de audit log

**Files:**
- Create: `backend/audit.py`
- Test: `tests/test_super_admin_metricas_audit.py` (parte)

- [ ] **Step 1: Escribir tests unitarios del redactor y del helper**

```python
# tests/test_super_admin_metricas_audit.py
import json
from backend.audit import redactar_payload, crear_audit_log_entry
from backend.models import AuditLogSuperAdmin


def test_redactar_reemplaza_claves_sensibles():
    payload = {
        "email": "a@b.com",
        "password": "secreta123",
        "api_token": "abcd",
        "detalle": {"secret_key": "XYZ", "algo": "ok"},
    }
    r = redactar_payload(payload)
    assert r["email"] == "a@b.com"
    assert r["password"] == "[REDACTED]"
    assert r["api_token"] == "[REDACTED]"
    assert r["detalle"]["secret_key"] == "[REDACTED]"
    assert r["detalle"]["algo"] == "ok"


def test_redactar_trunca_a_500_caracteres():
    payload = {"big": "x" * 600}
    r = redactar_payload(payload)
    # El truncado se hace sobre el string serializado, no sobre cada campo.
    s = json.dumps(r)
    assert len(s) <= 500


def test_crear_audit_log_entry_persiste(db):
    entry = crear_audit_log_entry(
        db,
        super_admin_usuario_id=5,
        accion="test_accion",
        administracion_id_afectada=1,
        motivo="test motivo",
        detalles={"path": "/foo"},
    )
    db.commit()
    assert entry.id is not None
    assert entry.accion == "test_accion"
    row = db.get(AuditLogSuperAdmin, entry.id)
    assert row.motivo == "test motivo"
```

- [ ] **Step 2: Verificar que el test falla (no existe backend/audit.py)**

```
pytest tests/test_super_admin_metricas_audit.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar `backend/audit.py`**

```python
"""Helpers para el audit log del super-admin.

- `redactar_payload`: convierte un dict a un dict serializable con campos
  sensibles reemplazados por "[REDACTED]" y truncado a 500 caracteres.
- `crear_audit_log_entry`: persiste una fila en `audit_log_super_admin`.
  No commitea; el caller decide.
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLogSuperAdmin

_CLAVES_SENSIBLES = re.compile(r"password|token|secret", re.IGNORECASE)
_MAX_LEN = 500


def _redactar_recursivo(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED]" if _CLAVES_SENSIBLES.search(k) else _redactar_recursivo(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redactar_recursivo(x) for x in obj]
    return obj


def redactar_payload(payload: Any) -> Any:
    """Redacta claves sensibles y trunca la serialización a 500 chars."""
    red = _redactar_recursivo(payload)
    s = json.dumps(red, default=str, ensure_ascii=False)
    if len(s) <= _MAX_LEN:
        return red
    # Trunca sobre la serialización y devuelve string.
    return s[:_MAX_LEN - 3] + "..."


def crear_audit_log_entry(
    db: Session,
    *,
    super_admin_usuario_id: int,
    accion: str,
    administracion_id_afectada: int | None = None,
    motivo: str | None = None,
    detalles: Any | None = None,
) -> AuditLogSuperAdmin:
    """Persiste una entrada de audit log. No commitea."""
    detalles_str: str | None = None
    if detalles is not None:
        red = redactar_payload(detalles)
        detalles_str = red if isinstance(red, str) else json.dumps(red, default=str, ensure_ascii=False)

    entry = AuditLogSuperAdmin(
        super_admin_usuario_id=super_admin_usuario_id,
        accion=accion,
        administracion_id_afectada=administracion_id_afectada,
        motivo=motivo,
        detalles=detalles_str,
    )
    db.add(entry)
    db.flush()
    return entry
```

- [ ] **Step 4: Correr los tests**

```
pytest tests/test_super_admin_metricas_audit.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add backend/audit.py tests/test_super_admin_metricas_audit.py
git commit -m "feat(backend): audit log helpers para super-admin (Plan B - Task 1)"
```

---

## Task 2: Extensión JWT con claim impersonated_by

**Files:**
- Modify: `backend/auth.py`

- [ ] **Step 1: Test — un token con impersonated_by expone el claim**

Agregar a `tests/test_auth.py`:

```python
def test_create_access_token_soporta_impersonated_by():
    from backend.auth import create_access_token, decode_token
    tok = create_access_token(
        user_id=2, rol=Rol.departamento, departamento_id=1, impersonated_by=5
    )
    claims = decode_token(tok)
    assert claims["sub"] == "2"
    assert claims["impersonated_by"] == 5
```

Y otro:

```python
def test_get_current_user_expone_impersonated_by(client):
    from backend.auth import create_access_token
    from backend.models import Rol
    tok = create_access_token(
        user_id=2, rol=Rol.departamento, departamento_id=1, impersonated_by=5,
    )
    r = client.get("/peticiones", headers={"Authorization": f"Bearer {tok}", "X-Consorcio-Id": "1"})
    # Con impersonate el request debe funcionar como el user impersonado.
    assert r.status_code == 200
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

- [ ] **Step 3: Extender `backend/auth.py`**

Agregar el kwarg `impersonated_by` a `create_access_token` y persistirlo en el payload JWT. Agregar el campo al dataclass `CurrentUser`. `get_current_user` lo pobla desde `claims.get("impersonated_by")`.

Buscar en `backend/auth.py` la firma actual de `create_access_token` y hacer:

```python
def create_access_token(
    *,
    user_id: int,
    rol: Rol,
    departamento_id: int | None,
    ttl_minutes: int | None = None,
    impersonated_by: int | None = None,
) -> str:
    payload = {
        "sub": str(user_id),
        "rol": rol.value if hasattr(rol, "value") else rol,
        "departamento_id": departamento_id,
        "jti": uuid.uuid4().hex,
        "exp": datetime.utcnow() + timedelta(minutes=ttl_minutes or get_settings().JWT_TTL_MIN),
    }
    if impersonated_by is not None:
        payload["impersonated_by"] = impersonated_by
    return jwt.encode(payload, get_settings().SECRET_KEY, algorithm="HS256")
```

Y actualizar `CurrentUser`:

```python
@dataclass(frozen=True)
class CurrentUser:
    id: int
    rol: Rol
    departamento_id: int | None
    jti: str
    exp: int
    impersonated_by: int | None = None
```

En `get_current_user` agregar:
```python
impersonated_by=claims.get("impersonated_by"),
```

- [ ] **Step 4: Correr suite completa; nada debe romperse**

```
pytest -q
```

- [ ] **Step 5: Commit**

```
git add backend/auth.py tests/test_auth.py
git commit -m "feat(backend): JWT claim impersonated_by + CurrentUser (Plan B - Task 2)"
```

---

## Task 3: Router super-admin — GET/GET-by-id administraciones

**Files:**
- Create: `backend/routers/super_admin.py`
- Modify: `backend/main.py` (registrar router)
- Modify: `backend/schemas.py` (schemas de Administracion)
- Test: `tests/test_super_admin_administraciones.py`

- [ ] **Step 1: Tests**

```python
# tests/test_super_admin_administraciones.py
def test_get_administraciones_sin_token_devuelve_401(client):
    r = client.get("/super-admin/administraciones")
    assert r.status_code == 401


def test_get_administraciones_como_admin_devuelve_403(client, headers_admin):
    r = client.get("/super-admin/administraciones", headers=headers_admin)
    assert r.status_code == 403


def test_get_administraciones_como_super_admin_devuelve_lista(client, headers_super_admin):
    r = client.get("/super-admin/administraciones", headers=headers_super_admin)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Al menos la Administración Test del seed.
    assert any(a["razon_social"] == "Administración Test" for a in data)


def test_get_administracion_by_id_devuelve_detalle(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/1", headers=headers_super_admin)
    assert r.status_code == 200
    assert r.json()["id"] == 1


def test_get_administracion_inexistente_devuelve_404(client, headers_super_admin):
    r = client.get("/super-admin/administraciones/9999", headers=headers_super_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr los tests para confirmar que fallan** (404 en todos por endpoint no registrado)

- [ ] **Step 3: Agregar schemas en `backend/schemas.py`**

```python
class AdministracionOut(BaseModel):
    id: int
    razon_social: str
    cuit: str
    email_contacto: str
    activa: bool
    plan: str
    fecha_creacion: datetime

    class Config:
        from_attributes = True


class AdministracionCrear(BaseModel):
    razon_social: str = Field(min_length=1, max_length=255)
    cuit: str = Field(min_length=1, max_length=13)
    email_contacto: EmailStr = Field(max_length=255)
    admin_email: EmailStr = Field(max_length=255)
    admin_password_inicial: str = Field(min_length=8, max_length=128)


class AdministracionActualizar(BaseModel):
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    email_contacto: EmailStr | None = None
    plan: str | None = Field(default=None, max_length=50)
```

- [ ] **Step 4: Crear `backend/routers/super_admin.py`**

```python
"""Endpoints del rol super_admin: administraciones, impersonate, métricas, audit log.

Todos requieren rol super_admin y son operacionales fuera del scope de
X-Consorcio-Id (no lo exigen). El bloqueo de rutas /super-admin/* durante
un JWT impersonado se enforcea en la dependencia _bloquear_impersonate_activo.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Administracion, Rol
from ..schemas import AdministracionOut

router = APIRouter(prefix="/super-admin", tags=["SuperAdmin"])


def _bloquear_impersonate_activo(user: CurrentUser = Depends(require_roles(Rol.super_admin))) -> CurrentUser:
    """El JWT impersonado no da acceso a /super-admin/* (excepto impersonate/end,
    que lo declara directamente sin esta dep)."""
    if user.impersonated_by is not None:
        raise HTTPException(status_code=403, detail="operacion_no_permitida_durante_impersonate")
    return user


@router.get(
    "/administraciones",
    response_model=list[AdministracionOut],
    status_code=status.HTTP_200_OK,
    summary="Listar administraciones",
)
def listar_administraciones(
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> list[Administracion]:
    return list(db.scalars(select(Administracion).order_by(Administracion.razon_social.asc())).all())


@router.get(
    "/administraciones/{administracion_id}",
    response_model=AdministracionOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener administración por id",
)
def obtener_administracion(
    administracion_id: int,
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> Administracion:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")
    return admin
```

- [ ] **Step 5: Registrar el router en `backend/main.py`**

Agregar en la sección de routers:
```python
from .routers import super_admin as super_admin_router  # noqa: E402
app.include_router(super_admin_router.router)
```

- [ ] **Step 6: Correr los tests**

Expected: 5 passed.

- [ ] **Step 7: Commit**

```
git add backend/routers/super_admin.py backend/main.py backend/schemas.py tests/test_super_admin_administraciones.py
git commit -m "feat(backend): super-admin GET administraciones (Plan B - Task 3)"
```

---

## Task 4: POST /super-admin/administraciones (crea admin + primer usuario)

**Files:**
- Modify: `backend/routers/super_admin.py`

- [ ] **Step 1: Tests**

```python
def test_post_administracion_crea_tenant_y_usuario_admin(client, headers_super_admin, db):
    body = {
        "razon_social": "Estudio Nuevo SA",
        "cuit": "30-77777777-7",
        "email_contacto": "info@estudio-nuevo.local",
        "admin_email": "boss@estudio-nuevo.local",
        "admin_password_inicial": "temporal-2026",
    }
    r = client.post("/super-admin/administraciones", json=body, headers=headers_super_admin)
    assert r.status_code == 201
    out = r.json()
    assert out["razon_social"] == "Estudio Nuevo SA"
    assert out["activa"] is True

    # Se creó el usuario admin, con must_change_password=True.
    from backend.models import Usuario, Rol
    u = db.query(Usuario).filter_by(email="boss@estudio-nuevo.local").one()
    assert u.rol == Rol.administracion
    assert u.administracion_id == out["id"]
    assert u.must_change_password is True


def test_post_administracion_cuit_duplicado_devuelve_409(client, headers_super_admin):
    body = {
        "razon_social": "Duplicada",
        "cuit": "30-11111111-1",  # ya existe (seed)
        "email_contacto": "dup@test.local",
        "admin_email": "dup_admin@test.local",
        "admin_password_inicial": "temporal-2026",
    }
    r = client.post("/super-admin/administraciones", json=body, headers=headers_super_admin)
    assert r.status_code == 409


def test_post_administracion_genera_audit_log(client, headers_super_admin, db):
    body = {
        "razon_social": "Audit Test",
        "cuit": "30-55555555-5",
        "email_contacto": "audit@test.local",
        "admin_email": "audit_admin@test.local",
        "admin_password_inicial": "temporal-2026",
    }
    r = client.post("/super-admin/administraciones", json=body, headers=headers_super_admin)
    assert r.status_code == 201
    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="crear_admin").all()
    assert len(entries) >= 1
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

- [ ] **Step 3: Implementar en `super_admin.py`**

Agregar imports y endpoint:

```python
from ..audit import crear_audit_log_entry
from ..models import Administracion, Rol, Usuario
from ..schemas import AdministracionCrear
from ..security import hash_password


@router.post(
    "/administraciones",
    response_model=AdministracionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear administración (+ primer usuario admin)",
)
def crear_administracion(
    payload: AdministracionCrear,
    db: Session = Depends(get_db),
    sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> Administracion:
    # Validar CUIT único
    existente = db.scalar(select(Administracion.id).where(Administracion.cuit == payload.cuit))
    if existente is not None:
        raise HTTPException(status_code=409, detail="Ya existe una administración con ese CUIT.")

    # Validar email admin único (por Usuario.email UNIQUE).
    email_en_uso = db.scalar(select(Usuario.id).where(Usuario.email == payload.admin_email))
    if email_en_uso is not None:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email.")

    admin_tenant = Administracion(
        razon_social=payload.razon_social,
        cuit=payload.cuit,
        email_contacto=payload.email_contacto,
    )
    db.add(admin_tenant)
    db.flush()

    usuario_admin = Usuario(
        email=payload.admin_email,
        password_hash=hash_password(payload.admin_password_inicial),
        rol=Rol.administracion,
        administracion_id=admin_tenant.id,
        must_change_password=True,
    )
    db.add(usuario_admin)
    db.flush()

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=sa.id,
        accion="crear_admin",
        administracion_id_afectada=admin_tenant.id,
        detalles={"razon_social": payload.razon_social, "admin_email": payload.admin_email},
    )
    db.commit()
    db.refresh(admin_tenant)
    return admin_tenant
```

- [ ] **Step 4: Correr los tests**

- [ ] **Step 5: Commit**

```
git add backend/routers/super_admin.py tests/test_super_admin_administraciones.py
git commit -m "feat(backend): super-admin POST administraciones con audit log (Plan B - Task 4)"
```

---

## Task 5: PATCH /super-admin/administraciones/{id}

**Files:**
- Modify: `backend/routers/super_admin.py`

- [ ] **Step 1: Tests**

```python
def test_patch_administracion_cambia_razon_social(client, headers_super_admin, db):
    r = client.patch(
        "/super-admin/administraciones/1",
        json={"razon_social": "Administración Test Editada"},
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    assert r.json()["razon_social"] == "Administración Test Editada"

    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="editar_admin").all()
    assert len(entries) >= 1


def test_patch_administracion_inexistente_devuelve_404(client, headers_super_admin):
    r = client.patch(
        "/super-admin/administraciones/9999",
        json={"razon_social": "X"},
        headers=headers_super_admin,
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Implementación**

```python
from ..schemas import AdministracionActualizar


@router.patch(
    "/administraciones/{administracion_id}",
    response_model=AdministracionOut,
    status_code=status.HTTP_200_OK,
    summary="Editar administración",
)
def actualizar_administracion(
    administracion_id: int,
    payload: AdministracionActualizar,
    db: Session = Depends(get_db),
    sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> Administracion:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")

    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(admin, campo, valor)

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=sa.id,
        accion="editar_admin",
        administracion_id_afectada=admin.id,
        detalles=cambios,
    )
    db.commit()
    db.refresh(admin)
    return admin
```

- [ ] **Step 3: Correr los tests + commit**

```
git add backend/routers/super_admin.py backend/schemas.py tests/test_super_admin_administraciones.py
git commit -m "feat(backend): super-admin PATCH administraciones (Plan B - Task 5)"
```

---

## Task 6: POST /super-admin/administraciones/{id}/suspender (toggle)

**Files:**
- Modify: `backend/routers/super_admin.py`

- [ ] **Step 1: Tests**

```python
def test_suspender_administracion_toggle_activa(client, headers_super_admin, db):
    # Activa → suspendida
    r1 = client.post("/super-admin/administraciones/1/suspender", headers=headers_super_admin)
    assert r1.status_code == 200
    assert r1.json()["activa"] is False

    # Suspendida → activa
    r2 = client.post("/super-admin/administraciones/1/suspender", headers=headers_super_admin)
    assert r2.status_code == 200
    assert r2.json()["activa"] is True

    from backend.models import AuditLogSuperAdmin
    acciones = {e.accion for e in db.query(AuditLogSuperAdmin).all()}
    assert "suspender_admin" in acciones
    assert "reactivar_admin" in acciones


def test_login_de_usuario_de_administracion_suspendida_devuelve_403(client, headers_super_admin):
    from tests.conftest import TEST_PASSWORD
    # Suspender la administración 1
    client.post("/super-admin/administraciones/1/suspender", headers=headers_super_admin)
    # Intentar login como admin@test.local (usuario de admin 1)
    r = client.post("/auth/login", json={"email": "admin@test.local", "password": TEST_PASSWORD})
    assert r.status_code == 403
    assert r.json()["detail"] == "administracion_suspendida"
```

Verificar previamente que `backend/routers/auth.py` ya devuelve `403 administracion_suspendida` (implementado en Plan A). Si no, ajustar.

- [ ] **Step 2: Implementación**

```python
@router.post(
    "/administraciones/{administracion_id}/suspender",
    response_model=AdministracionOut,
    status_code=status.HTTP_200_OK,
    summary="Toggle activa/suspendida",
)
def toggle_suspender_administracion(
    administracion_id: int,
    db: Session = Depends(get_db),
    sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> Administracion:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")
    admin.activa = not admin.activa
    accion = "reactivar_admin" if admin.activa else "suspender_admin"
    crear_audit_log_entry(
        db,
        super_admin_usuario_id=sa.id,
        accion=accion,
        administracion_id_afectada=admin.id,
    )
    db.commit()
    db.refresh(admin)
    return admin
```

- [ ] **Step 3: Correr los tests + commit**

```
git add backend/routers/super_admin.py tests/test_super_admin_administraciones.py
git commit -m "feat(backend): super-admin toggle suspender (Plan B - Task 6)"
```

---

## Task 7: POST /super-admin/administraciones/{id}/reset-password/{user_id}

**Files:**
- Modify: `backend/routers/super_admin.py`
- Modify: `backend/schemas.py`

- [ ] **Step 1: Tests**

```python
def test_reset_password_genera_password_temporal_y_setea_must_change(client, headers_super_admin, db):
    from backend.models import Usuario
    r = client.post(
        "/super-admin/administraciones/1/reset-password/1",
        headers=headers_super_admin,
    )
    assert r.status_code == 200
    out = r.json()
    assert "password_temporal" in out
    assert len(out["password_temporal"]) >= 12

    db.expire_all()
    u = db.get(Usuario, 1)
    assert u.must_change_password is True

    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="reset_password").all()
    assert len(entries) >= 1
    # No debe guardarse la password en el detalle.
    for e in entries:
        assert "temporal" not in (e.detalles or "").lower() or "REDACTED" in (e.detalles or "")


def test_reset_password_usuario_de_otra_administracion_devuelve_404(client, headers_super_admin, db):
    # Crear una admin 2 y un user en ella
    from backend.models import Administracion, Usuario, Rol
    from backend.security import hash_password
    a2 = Administracion(razon_social="A2", cuit="30-4-2", email_contacto="a2@x")
    db.add(a2); db.flush()
    u2 = Usuario(email="u2@x", password_hash=hash_password("x"), rol=Rol.administracion,
                 administracion_id=a2.id)
    db.add(u2); db.commit()

    # Reset de u2 pero contra admin 1 → 404
    r = client.post(
        f"/super-admin/administraciones/1/reset-password/{u2.id}",
        headers=headers_super_admin,
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Schema en `backend/schemas.py`**

```python
class ResetPasswordOut(BaseModel):
    password_temporal: str
```

- [ ] **Step 3: Implementación**

```python
import secrets
from ..schemas import ResetPasswordOut
from ..security import hash_password


@router.post(
    "/administraciones/{administracion_id}/reset-password/{user_id}",
    response_model=ResetPasswordOut,
    status_code=status.HTTP_200_OK,
    summary="Reset password de un usuario",
)
def reset_password_usuario(
    administracion_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> ResetPasswordOut:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")
    u = db.get(Usuario, user_id)
    if u is None or u.administracion_id != administracion_id:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en esta administración.")

    nueva = secrets.token_urlsafe(12)
    u.password_hash = hash_password(nueva)
    u.must_change_password = True

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=sa.id,
        accion="reset_password",
        administracion_id_afectada=administracion_id,
        detalles={"usuario_id": user_id, "email": u.email},
    )
    db.commit()
    return ResetPasswordOut(password_temporal=nueva)
```

- [ ] **Step 4: Correr los tests + commit**

```
git add backend/routers/super_admin.py backend/schemas.py tests/test_super_admin_administraciones.py
git commit -m "feat(backend): super-admin reset-password (Plan B - Task 7)"
```

---

## Task 8: POST /super-admin/impersonate/start

**Files:**
- Modify: `backend/routers/super_admin.py`
- Modify: `backend/schemas.py`
- Test: `tests/test_super_admin_impersonate.py`

- [ ] **Step 1: Tests**

```python
# tests/test_super_admin_impersonate.py
from tests.conftest import TEST_PASSWORD


def test_impersonate_start_devuelve_jwt_15min(client, headers_super_admin, db):
    body = {"usuario_id": 2, "motivo": "Ticket #123 - no aparecen expensas julio"}
    r = client.post("/super-admin/impersonate/start", json=body, headers=headers_super_admin)
    assert r.status_code == 200
    out = r.json()
    assert "access_token" in out
    assert out["expires_in"] == 15 * 60
    assert out["impersonated_user_id"] == 2

    from backend.models import AuditLogSuperAdmin
    e = db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_start").order_by(
        AuditLogSuperAdmin.id.desc()).first()
    assert e is not None
    assert e.motivo == body["motivo"]


def test_impersonate_start_motivo_muy_corto_devuelve_400(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "corto"}
    r = client.post("/super-admin/impersonate/start", json=body, headers=headers_super_admin)
    assert r.status_code == 400


def test_impersonate_start_sin_motivo_devuelve_400(client, headers_super_admin):
    r = client.post("/super-admin/impersonate/start", json={"usuario_id": 2}, headers=headers_super_admin)
    assert r.status_code == 400


def test_impersonate_start_super_admin_no_impersonable(client, headers_super_admin, db):
    # No se puede impersonar a otro super_admin.
    from backend.models import Usuario, Rol
    from backend.security import hash_password
    sa2 = Usuario(email="sa2@x", password_hash=hash_password("x"), rol=Rol.super_admin)
    db.add(sa2); db.commit()

    r = client.post(
        "/super-admin/impersonate/start",
        json={"usuario_id": sa2.id, "motivo": "no debería funcionar"},
        headers=headers_super_admin,
    )
    assert r.status_code == 400


def test_impersonate_activo_no_puede_iniciar_otro(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "primer impersonate valido"}
    r1 = client.post("/super-admin/impersonate/start", json=body, headers=headers_super_admin)
    token = r1.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}"}

    # Con JWT impersonado, /impersonate/start debería estar bloqueado (rol admin != super_admin).
    r2 = client.post("/super-admin/impersonate/start", json=body, headers=headers_imp)
    # El user impersonado es depto → 403 (require_roles).
    assert r2.status_code == 403
```

- [ ] **Step 2: Schemas**

```python
class ImpersonateStartIn(BaseModel):
    usuario_id: int = Field(ge=1)
    motivo: str = Field(min_length=10, max_length=500)


class ImpersonateStartOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    impersonated_user_id: int
```

- [ ] **Step 3: Implementación**

```python
from ..auth import create_access_token
from ..schemas import ImpersonateStartIn, ImpersonateStartOut

_IMPERSONATE_TTL_MIN = 15


@router.post(
    "/impersonate/start",
    response_model=ImpersonateStartOut,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión de impersonate",
)
def impersonate_start(
    payload: ImpersonateStartIn,
    db: Session = Depends(get_db),
    sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> ImpersonateStartOut:
    target = db.get(Usuario, payload.usuario_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if target.rol == Rol.super_admin:
        raise HTTPException(status_code=400, detail="No se puede impersonar a otro super_admin.")

    tok = create_access_token(
        user_id=target.id,
        rol=target.rol,
        departamento_id=target.departamento_id,
        ttl_minutes=_IMPERSONATE_TTL_MIN,
        impersonated_by=sa.id,
    )

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=sa.id,
        accion="impersonate_start",
        administracion_id_afectada=target.administracion_id,
        motivo=payload.motivo,
        detalles={"usuario_impersonado_id": target.id, "email": target.email, "rol": target.rol.value},
    )
    db.commit()

    return ImpersonateStartOut(
        access_token=tok,
        expires_in=_IMPERSONATE_TTL_MIN * 60,
        impersonated_user_id=target.id,
    )
```

- [ ] **Step 4: Correr los tests + commit**

```
git add backend/routers/super_admin.py backend/schemas.py tests/test_super_admin_impersonate.py
git commit -m "feat(backend): super-admin impersonate start (Plan B - Task 8)"
```

---

## Task 9: POST /super-admin/impersonate/end

**Files:**
- Modify: `backend/routers/super_admin.py`

- [ ] **Step 1: Tests**

```python
def test_impersonate_end_revoca_el_token(client, headers_super_admin):
    body = {"usuario_id": 2, "motivo": "test motivo válido"}
    r1 = client.post("/super-admin/impersonate/start", json=body, headers=headers_super_admin)
    token = r1.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}"}

    r_end = client.post("/super-admin/impersonate/end", headers=headers_imp)
    assert r_end.status_code == 204

    # El token quedó revocado.
    r_after = client.get("/peticiones", headers={**headers_imp, "X-Consorcio-Id": "1"})
    assert r_after.status_code == 401


def test_impersonate_end_sin_claim_impersonated_by_devuelve_400(client, headers_admin):
    # Un JWT normal (sin impersonated_by) no puede llamar a /end.
    r = client.post("/super-admin/impersonate/end", headers=headers_admin)
    assert r.status_code == 400
```

- [ ] **Step 2: Implementación**

```python
from ..auth import get_current_user, revocar_jti


@router.post(
    "/impersonate/end",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión de impersonate",
)
def impersonate_end(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if user.impersonated_by is None:
        raise HTTPException(status_code=400, detail="El token actual no es de impersonate.")

    # Revocar el jti del token impersonado.
    revocar_jti(user.jti)

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=user.impersonated_by,
        accion="impersonate_end",
        detalles={"usuario_impersonado_id": user.id, "jti": user.jti},
    )
    db.commit()
```

Verificar que existe una helper `revocar_jti` en `backend/auth.py` o `backend/blacklist.py`. Si `revocar_jti` no existe, usar `_blacklist.add(user.jti)`:

```python
from ..blacklist import add as blacklist_add
# ...
blacklist_add(user.jti)
```

- [ ] **Step 3: Correr los tests + commit**

```
git add backend/routers/super_admin.py tests/test_super_admin_impersonate.py
git commit -m "feat(backend): super-admin impersonate end (Plan B - Task 9)"
```

---

## Task 10: Middleware audit para acciones durante impersonate

**Files:**
- Create: `backend/middleware/__init__.py` (vacío)
- Create: `backend/middleware/impersonate_audit.py`
- Modify: `backend/main.py` (registrar middleware)

- [ ] **Step 1: Tests**

```python
def test_mutacion_durante_impersonate_queda_en_audit_log(client, headers_super_admin, db):
    # Impersonar user 2 (departamento).
    body = {"usuario_id": 1, "motivo": "test audit middleware"}
    r_start = client.post("/super-admin/impersonate/start", json=body, headers=headers_super_admin)
    token = r_start.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    # POST /amenities (mutación) durante impersonate.
    r_post = client.post(
        "/amenities",
        json={"nombre": "Amenity durante impersonate", "descripcion": "audit"},
        headers=headers_imp,
    )
    assert r_post.status_code == 201

    from backend.models import AuditLogSuperAdmin
    entries = db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").all()
    assert len(entries) >= 1
    match = [e for e in entries if "/amenities" in (e.detalles or "")]
    assert match


def test_get_durante_impersonate_NO_queda_en_audit_log(client, headers_super_admin, db):
    body = {"usuario_id": 1, "motivo": "test audit no loguea GET"}
    r_start = client.post("/super-admin/impersonate/start", json=body, headers=headers_super_admin)
    token = r_start.json()["access_token"]
    headers_imp = {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}

    from backend.models import AuditLogSuperAdmin
    before = db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").count()

    client.get("/amenities", headers=headers_imp)
    client.get("/expensas", headers=headers_imp)

    after = db.query(AuditLogSuperAdmin).filter_by(accion="impersonate_mutacion").count()
    assert after == before
```

- [ ] **Step 2: Implementación del middleware**

`backend/middleware/__init__.py`:
```python
# marker de package
```

`backend/middleware/impersonate_audit.py`:
```python
"""Middleware que loguea acciones mutantes cuando el JWT tiene claim
impersonated_by. GETs no se loguean (el impersonate_start ya deja constancia)."""
from __future__ import annotations

import json

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..audit import crear_audit_log_entry
from ..config import get_settings
from ..database import SessionLocal
from ..models import Departamento, Usuario

_MUTANTES = {"POST", "PUT", "PATCH", "DELETE"}


class ImpersonateAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if request.method not in _MUTANTES:
            return response
        if response.status_code >= 400:
            return response  # No auditar fallos.

        auth = request.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            return response
        token = auth.removeprefix("Bearer ").strip()

        try:
            claims = jwt.decode(
                token, get_settings().SECRET_KEY, algorithms=["HS256"],
                options={"verify_exp": False},  # ya validado por get_current_user
            )
        except jwt.PyJWTError:
            return response

        impersonated_by = claims.get("impersonated_by")
        if impersonated_by is None:
            return response

        try:
            body_bytes = await request.body()
        except Exception:
            body_bytes = b""

        body_repr: object
        if body_bytes:
            try:
                body_repr = json.loads(body_bytes)
            except Exception:
                body_repr = body_bytes[:200].decode(errors="replace")
        else:
            body_repr = None

        # Consorcio y administración afectados (best-effort).
        cid_raw = request.headers.get("X-Consorcio-Id")
        administracion_id_afectada: int | None = None

        db = SessionLocal()
        try:
            usuario_id = int(claims.get("sub", "0"))
            u = db.get(Usuario, usuario_id) if usuario_id else None
            if u is not None:
                if u.administracion_id:
                    administracion_id_afectada = u.administracion_id
                elif u.departamento_id:
                    d = db.get(Departamento, u.departamento_id)
                    if d is not None:
                        from ..models import Consorcio
                        c = db.get(Consorcio, d.consorcio_id)
                        if c is not None:
                            administracion_id_afectada = c.administracion_id

            crear_audit_log_entry(
                db,
                super_admin_usuario_id=impersonated_by,
                accion="impersonate_mutacion",
                administracion_id_afectada=administracion_id_afectada,
                detalles={
                    "method": request.method,
                    "path": request.url.path,
                    "consorcio_id": cid_raw,
                    "body": body_repr,
                    "status": response.status_code,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return response
```

- [ ] **Step 3: Registrar en `backend/main.py`**

```python
from .middleware.impersonate_audit import ImpersonateAuditMiddleware
# ...
app.add_middleware(ImpersonateAuditMiddleware)
```

- [ ] **Step 4: Correr los tests + commit**

Nota: el middleware lee `await request.body()` que puede consumir el stream. Si eso rompe el pipeline, mover el logging a *después* de que FastAPI serializó todo — de hecho ya lo hacemos post `call_next`. Si aún así rompe, cachear el body en un scope antes de `call_next` con `request._body = await request.body()`.

```
git add backend/middleware/ backend/main.py tests/test_super_admin_impersonate.py
git commit -m "feat(backend): middleware audit mutaciones impersonate (Plan B - Task 10)"
```

---

## Task 11: GET /super-admin/metricas

**Files:**
- Modify: `backend/routers/super_admin.py`
- Modify: `backend/schemas.py`
- Test: `tests/test_super_admin_metricas_audit.py`

- [ ] **Step 1: Tests**

```python
def test_get_metricas_devuelve_agregados(client, headers_super_admin):
    r = client.get("/super-admin/metricas", headers=headers_super_admin)
    assert r.status_code == 200
    m = r.json()
    assert set(m.keys()) >= {
        "administraciones", "consorcios", "departamentos",
        "expensas_ultimo_mes", "impersonates_ultimos_30_dias"
    }
    assert m["administraciones"]["total"] >= 1
    assert m["consorcios"]["total"] >= 1


def test_get_metricas_como_admin_devuelve_403(client, headers_admin):
    r = client.get("/super-admin/metricas", headers=headers_admin)
    assert r.status_code == 403
```

- [ ] **Step 2: Schema**

```python
class MetricasOut(BaseModel):
    administraciones: dict
    consorcios: dict
    departamentos: dict
    expensas_ultimo_mes: dict
    impersonates_ultimos_30_dias: int
```

- [ ] **Step 3: Implementación**

```python
from datetime import datetime, timedelta

from sqlalchemy import func
from ..models import Consorcio, Departamento, Expensa, AuditLogSuperAdmin
from ..schemas import MetricasOut


@router.get(
    "/metricas",
    response_model=MetricasOut,
    status_code=status.HTTP_200_OK,
    summary="Métricas globales de la plataforma",
)
def obtener_metricas(
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> MetricasOut:
    admins_activas = db.scalar(select(func.count(Administracion.id)).where(Administracion.activa == True)) or 0  # noqa
    admins_susp = db.scalar(select(func.count(Administracion.id)).where(Administracion.activa == False)) or 0  # noqa
    consorcios_total = db.scalar(select(func.count(Consorcio.id))) or 0
    deptos_total = db.scalar(select(func.count(Departamento.id))) or 0

    hoy = datetime.utcnow().date()
    inicio_mes = hoy.replace(day=1)
    exp_last_month_count = db.scalar(
        select(func.count(Expensa.id)).where(Expensa.periodo == inicio_mes.strftime("%Y-%m"))
    ) or 0
    exp_last_month_monto = db.scalar(
        select(func.coalesce(func.sum(Expensa.monto_primer_vencimiento), 0.0)).where(
            Expensa.periodo == inicio_mes.strftime("%Y-%m")
        )
    ) or 0.0

    hace_30 = datetime.utcnow() - timedelta(days=30)
    imp_ultimos = db.scalar(
        select(func.count(AuditLogSuperAdmin.id)).where(
            AuditLogSuperAdmin.accion == "impersonate_start",
            AuditLogSuperAdmin.fecha >= hace_30,
        )
    ) or 0

    return MetricasOut(
        administraciones={
            "activas": admins_activas,
            "suspendidas": admins_susp,
            "total": admins_activas + admins_susp,
        },
        consorcios={"total": consorcios_total},
        departamentos={"total": deptos_total},
        expensas_ultimo_mes={"emitidas": exp_last_month_count, "monto_total": float(exp_last_month_monto)},
        impersonates_ultimos_30_dias=imp_ultimos,
    )
```

- [ ] **Step 4: Commit**

```
git add backend/routers/super_admin.py backend/schemas.py tests/test_super_admin_metricas_audit.py
git commit -m "feat(backend): super-admin metricas (Plan B - Task 11)"
```

---

## Task 12: GET /super-admin/audit-log con filtros + paginación

**Files:**
- Modify: `backend/routers/super_admin.py`
- Modify: `backend/schemas.py`

- [ ] **Step 1: Tests**

```python
def test_get_audit_log_devuelve_lista_ordenada_desc(client, headers_super_admin, db):
    # Sembrar entradas explícitas.
    from backend.audit import crear_audit_log_entry
    for i in range(3):
        crear_audit_log_entry(db, super_admin_usuario_id=5, accion=f"test_accion_{i}")
    db.commit()

    r = client.get("/super-admin/audit-log", headers=headers_super_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3
    # Ordenado por fecha desc.
    fechas = [entry["fecha"] for entry in data]
    assert fechas == sorted(fechas, reverse=True)


def test_audit_log_filtra_por_accion(client, headers_super_admin, db):
    from backend.audit import crear_audit_log_entry
    crear_audit_log_entry(db, super_admin_usuario_id=5, accion="ejemplo_unico_123")
    db.commit()

    r = client.get("/super-admin/audit-log?accion=ejemplo_unico_123", headers=headers_super_admin)
    assert r.status_code == 200
    data = r.json()
    assert all(e["accion"] == "ejemplo_unico_123" for e in data)
    assert len(data) >= 1


def test_audit_log_pagina_con_limit_offset(client, headers_super_admin, db):
    from backend.audit import crear_audit_log_entry
    for i in range(10):
        crear_audit_log_entry(db, super_admin_usuario_id=5, accion="pag_test")
    db.commit()

    r1 = client.get("/super-admin/audit-log?accion=pag_test&limit=5", headers=headers_super_admin)
    r2 = client.get("/super-admin/audit-log?accion=pag_test&limit=5&offset=5", headers=headers_super_admin)
    assert len(r1.json()) == 5
    assert len(r2.json()) == 5
    ids1 = {e["id"] for e in r1.json()}
    ids2 = {e["id"] for e in r2.json()}
    assert ids1.isdisjoint(ids2)
```

- [ ] **Step 2: Schema**

```python
class AuditLogEntryOut(BaseModel):
    id: int
    super_admin_usuario_id: int
    accion: str
    administracion_id_afectada: int | None
    motivo: str | None
    detalles: str | None
    fecha: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Implementación**

```python
from ..schemas import AuditLogEntryOut


@router.get(
    "/audit-log",
    response_model=list[AuditLogEntryOut],
    status_code=status.HTTP_200_OK,
    summary="Audit log paginado",
)
def listar_audit_log(
    accion: str | None = Query(default=None),
    administracion_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> list[AuditLogSuperAdmin]:
    stmt = select(AuditLogSuperAdmin).order_by(
        AuditLogSuperAdmin.fecha.desc(), AuditLogSuperAdmin.id.desc()
    )
    if accion is not None:
        stmt = stmt.where(AuditLogSuperAdmin.accion == accion)
    if administracion_id is not None:
        stmt = stmt.where(AuditLogSuperAdmin.administracion_id_afectada == administracion_id)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())
```

- [ ] **Step 4: Commit**

```
git add backend/routers/super_admin.py backend/schemas.py tests/test_super_admin_metricas_audit.py
git commit -m "feat(backend): super-admin audit-log GET (Plan B - Task 12)"
```

---

## Task 13: OpenAPI + README

**Files:**
- Modify: `openapi.yaml`
- Modify: `README.md`

- [ ] **Step 1: Agregar tag `SuperAdmin` en `openapi.yaml`**

En la sección `tags:`:
```yaml
  - name: SuperAdmin
    description: Endpoints del super-admin (CRUD tenants, impersonate, métricas, audit log)
```

- [ ] **Step 2: Documentar los 12 endpoints en `openapi.yaml`**

Bajo `paths:`, agrupar los endpoints de super-admin. Para cada uno declarar summary, tags: [SuperAdmin], responses 200/201/204, 401, 403, 404, 409 y schema request/response. Referencias a schemas nuevos (`AdministracionOut`, `AdministracionCrear`, etc.).

- [ ] **Step 3: Actualizar README.md**

Agregar en la sección "Multitenant SaaS" un párrafo corto:

```markdown
### Plan B — Super-Admin (completado)

- CRUD `/super-admin/administraciones` (list, get, crear, editar, toggle activa).
- Reset password de usuarios con `must_change_password=True` (audit).
- Impersonate: `POST /super-admin/impersonate/start` genera un JWT de 15 min con
  claim `impersonated_by`; `POST /super-admin/impersonate/end` lo revoca. Todas
  las mutaciones durante impersonate quedan en `audit_log_super_admin`.
- `GET /super-admin/metricas` (agregados globales).
- `GET /super-admin/audit-log` con filtros por acción y administración.
```

- [ ] **Step 4: Validar YAML + correr suite completa**

```
python -c "import yaml; yaml.safe_load(open('openapi.yaml', encoding='utf-8'))"
pytest -q
```

- [ ] **Step 5: Commit**

```
git add openapi.yaml README.md
git commit -m "docs: openapi + readme para super-admin (Plan B - Task 13)"
```

---

## Self-Review (checklist)

- [ ] Cada tarea produce cambios auto-contenidos y un commit.
- [ ] Los tests se escriben antes de la implementación (TDD).
- [ ] Los endpoints declaran `response_model`, `status_code` y `summary`.
- [ ] El middleware no rompe el flujo cuando el token está ausente o el body está vacío.
- [ ] `impersonate_start` requiere motivo min 10 chars.
- [ ] `impersonate_end` revoca el JTI (blacklist) y persiste la entrada.
- [ ] Rutas `/super-admin/*` (excepto `/impersonate/end`) rechazan JWT impersonado con 403.
- [ ] Métricas: agregados sin drill-down por tenant.
- [ ] Audit log: filtros por acción y administración, paginado.
- [ ] OpenAPI y README actualizados.
