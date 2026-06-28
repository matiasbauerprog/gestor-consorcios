# Fase 12 — Reservas de amenities — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extender el módulo de reservas con políticas por amenity (precio, duración, anticipación, límite por depto, plazo de cancelación), cobro automático vía MovimientoCuenta, notificaciones doble canal, soft-delete de amenity y frontend mobile-first completo.

**Architecture:** Backend FastAPI con SQLAlchemy 2.0 (Mapped) y Pydantic v2. Reusa infraestructura existente: MovimientoCuenta (cuenta corriente) para el cobro/reversa, `notificaciones.py` (campanita in-app + email best-effort) para alertas, patrón soft-delete con flag `activo`. Frontend React + Vite + react-router con 2 pantallas nuevas, 2 API clients y 1 modal. Todo el frontend es mobile-first con cards apiladas en `<600px`. Backend ~8 commits, frontend ~6 commits, docs/merge ~3.

**Tech Stack:** Python 3.14 + FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2 + pytest. React 18 + Vite + react-router-dom + fetch.

---

## Convenciones aplicables (del proyecto)

- **Auth:** identidad y rol siempre del JWT, nunca del body. `usuario_id`/`departamento_id` se ignoran si vienen en payloads.
- **Status codes:** 400 validación, 401 sin token, 403 rol incorrecto, 404 inexistente, 409 conflicto/estado.
- **Tests:** `pytest -v` (Windows: `.venv/Scripts/python.exe -m pytest -v`). FastAPI convierte RequestValidationError a 400, no 422.
- **OpenAPI-first:** documentar cambios en `openapi.yaml`. Path params usan nombre completo (`{amenity_id}`, `{reserva_id}`).
- **Mobile-first:** tablas → cards apiladas en `<600px`. Inputs nativos, sin scroll horizontal, targets ≥44px, sticky bottom CTA.
- **Clean start:** `consorcio.db` se regenera; sin migraciones reales. Seed crea datos demo.

---

## File Structure (mapa de cambios)

### Backend

| Archivo | Cambio | Responsabilidad |
|---|---|---|
| `backend/models.py` | Modificar | Sumar 5 campos a `Amenity` + 1 FK a `Reserva` |
| `backend/schemas.py` | Modificar | Extender `AmenityCrear/Actualizar/Out` con políticas; extender `ReservaOut` con `movimiento_cuenta_id` |
| `backend/routers/amenities.py` | Modificar | DELETE soft + filtro `activo` en GET + nuevas validaciones en POST reservas + cobro |
| `backend/routers/reservas.py` | Modificar | GET /{id} nuevo + reversa al cancelar + notificación admin-cancela-ajena |
| `backend/notificaciones.py` | Modificar | Sumar helper `notificar_reserva_creada` (solo email) y `notificar_reserva_cancelada_por_admin` (doble canal) |
| `backend/seed.py` | Modificar | Sumar 2 amenities demo (SUM con precio, Laundry gratuita) |
| `tests/conftest.py` | Modificar | Actualizar fixture amenities/reservas (los IDs 300/301/400 ya existen — solo sumar campos) |
| `tests/test_amenities.py` | Modificar | Sumar tests para soft-delete + filtro activos + nuevas validaciones |
| `tests/test_reservas.py` | Crear | Tests para GET /{id}, cobro, reversa, gating |
| `openapi.yaml` | Modificar | DELETE /amenities/{id}, GET /reservas/{id}, schemas extendidos |

### Frontend

| Archivo | Cambio | Responsabilidad |
|---|---|---|
| `frontend/src/api/amenities.js` | Crear | listar, crear, actualizar, eliminar (soft) |
| `frontend/src/api/reservas.js` | Crear | listar, obtener, crear (anidado), cancelar |
| `frontend/src/screens/Amenities.jsx` | Crear | CRUD amenities (admin only). Cards en mobile. |
| `frontend/src/screens/Reservas.jsx` | Crear | Selector + listas (próximas, mis) + form. Mobile-first. |
| `frontend/src/components/ModalAmenity.jsx` | Crear | Form crear/editar amenity con políticas |
| `frontend/src/components/Sidebar.jsx` | Modificar | Sumar sección "Espacios comunes" |
| `frontend/src/App.jsx` | Modificar | Sumar 2 rutas |
| `frontend/src/index.css` | Modificar | Sumar reglas mobile-first (sticky CTA, banner políticas colapsable) |

---

## Task 0: Branch + baseline

**Files:** ninguno

- [ ] **Step 1: Crear branch desde master limpio**

```bash
git checkout master
git pull --ff-only
git checkout -b feature/expensas-fase12-reservas
```

- [ ] **Step 2: Verificar suite verde antes de empezar**

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expected: `606 passed`.

- [ ] **Step 3: Verificar build frontend OK**

```bash
cd frontend && npm run build && cd ..
```

Expected: `✓ built in N`.

---

## Task 1: Modelos + schemas + clean start

**Files:**
- Modify: `backend/models.py:375-411` (Amenity, Reserva)
- Modify: `backend/schemas.py:193-241` (schemas reserva + amenity)
- Modify: `tests/conftest.py:221-231` (fixture amenities/reservas: agregar nuevos campos con None)

- [ ] **Step 1: Extender modelo `Amenity` con 5 campos de política**

En `backend/models.py`, reemplazar la clase `Amenity` (líneas 375-382):

```python
class Amenity(Base):
    __tablename__ = "amenities"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500))

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    precio_reserva: Mapped[float | None] = mapped_column(Float, nullable=True)
    duracion_maxima_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anticipacion_maxima_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_reservas_activas_por_depto: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horas_minimas_cancelacion: Mapped[int | None] = mapped_column(Integer, nullable=True)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="amenity")
```

Verificar que `Boolean`, `Float` e `Integer` ya estén importados al inicio del archivo (lo están, otros modelos los usan).

- [ ] **Step 2: Extender modelo `Reserva` con FK a MovimientoCuenta**

En `backend/models.py`, agregar campo dentro de la clase `Reserva` (después de `fecha_creacion`):

```python
    movimiento_cuenta_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_cuenta.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 3: Extender schemas Amenity en `backend/schemas.py`**

Reemplazar `AmenityOut`, `AmenityCrear` y `AmenityActualizar` (líneas 226-241) con:

```python
class AmenityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    activo: bool
    precio_reserva: float | None
    duracion_maxima_horas: int | None
    anticipacion_maxima_dias: int | None
    max_reservas_activas_por_depto: int | None
    horas_minimas_cancelacion: int | None


class AmenityCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    precio_reserva: float | None = Field(default=None, ge=0)
    duracion_maxima_horas: int | None = Field(default=None, gt=0)
    anticipacion_maxima_dias: int | None = Field(default=None, gt=0)
    max_reservas_activas_por_depto: int | None = Field(default=None, gt=0)
    horas_minimas_cancelacion: int | None = Field(default=None, ge=0)


class AmenityActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    activo: bool | None = None
    precio_reserva: float | None = Field(default=None, ge=0)
    duracion_maxima_horas: int | None = Field(default=None, gt=0)
    anticipacion_maxima_dias: int | None = Field(default=None, gt=0)
    max_reservas_activas_por_depto: int | None = Field(default=None, gt=0)
    horas_minimas_cancelacion: int | None = Field(default=None, ge=0)
```

- [ ] **Step 4: Extender `ReservaOut` con `movimiento_cuenta_id`**

En `backend/schemas.py`, reemplazar `ReservaOut` (líneas 204-212) con:

```python
class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amenity_id: int
    usuario_id: int
    inicio: datetime
    fin: datetime
    estado: EstadoReserva
    movimiento_cuenta_id: int | None
```

- [ ] **Step 5: Actualizar fixture en `tests/conftest.py`**

En `tests/conftest.py`, reemplazar la creación de los 2 amenities (líneas 221-222) con:

```python
            Amenity(
                id=300, nombre="SUM", descripcion="Salón de usos múltiples",
                activo=True,
            ),
            Amenity(
                id=301, nombre="Laundry", descripcion="Lavandería compartida",
                activo=True,
            ),
```

(Los demás campos quedan `None` por default — los tests existentes siguen pasando.)

- [ ] **Step 6: Borrar DB y correr suite**

```bash
rm -f consorcio.db
.venv/Scripts/python.exe -m pytest -q
```

Expected: `606 passed`. Si falla, es porque algún test viejo asume el shape viejo de `AmenityOut` o `ReservaOut`; ajustar.

- [ ] **Step 7: Commit**

```bash
git add backend/models.py backend/schemas.py tests/conftest.py
git commit -m "feat(reservas-fase12): models y schemas con políticas + FK movimiento"
```

---

## Task 2: Soft-delete amenity + filtro `activo` en GET

**Files:**
- Modify: `backend/routers/amenities.py:29-34` (GET list)
- Modify: `backend/routers/amenities.py` (sumar DELETE endpoint)
- Modify: `tests/test_amenities.py` (sumar tests)

- [ ] **Step 1: Escribir 3 tests fallantes en `tests/test_amenities.py`**

Agregar al final del archivo:

```python
def test_delete_amenity_admin_devuelve_200_y_marca_inactivo(client, headers_admin, db_session):
    from backend.models import Amenity
    r = client.delete("/amenities/301", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 301
    assert body["activo"] is False
    db_session.expire_all()
    a = db_session.get(Amenity, 301)
    assert a.activo is False


def test_delete_amenity_ya_inactivo_devuelve_409(client, headers_admin, db_session):
    from backend.models import Amenity
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    r = client.delete("/amenities/301", headers=headers_admin)
    assert r.status_code == 409


def test_delete_amenity_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.delete("/amenities/301", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_amenities_no_admin_solo_ve_activos(client, headers_depto_a, db_session):
    from backend.models import Amenity
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    r = client.get("/amenities", headers=headers_depto_a)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert 300 in ids
    assert 301 not in ids


def test_listar_amenities_admin_con_incluir_inactivos_ve_todos(client, headers_admin, db_session):
    from backend.models import Amenity
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    r = client.get("/amenities?incluir_inactivos=true", headers=headers_admin)
    ids = [x["id"] for x in r.json()]
    assert 300 in ids
    assert 301 in ids
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
.venv/Scripts/python.exe -m pytest tests/test_amenities.py::test_delete_amenity_admin_devuelve_200_y_marca_inactivo -v
```

Expected: FAIL con 405 Method Not Allowed (no existe DELETE).

- [ ] **Step 3: Sumar parámetro `incluir_inactivos` y filtro en GET**

En `backend/routers/amenities.py`, reemplazar `listar_amenities` (líneas 23-34):

```python
@router.get(
    "",
    response_model=list[AmenityOut],
    status_code=status.HTTP_200_OK,
    summary="Listar amenities",
)
def listar_amenities(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Amenity]:
    stmt = select(Amenity).order_by(Amenity.nombre.asc())
    # incluir_inactivos solo aplica para admin; para depto/representante se ignora.
    if not (incluir_inactivos and user.rol == Rol.administracion):
        stmt = stmt.where(Amenity.activo == True)  # noqa: E712
    return list(db.scalars(stmt).all())
```

- [ ] **Step 4: Sumar endpoint DELETE soft**

Al final de `backend/routers/amenities.py`, agregar:

```python
@router.delete(
    "/{amenity_id}",
    response_model=AmenityOut,
    status_code=status.HTTP_200_OK,
    summary="Dar de baja un amenity (soft-delete)",
)
def dar_de_baja_amenity(
    amenity_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Amenity:
    amenity = db.get(Amenity, amenity_id)
    if amenity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El amenity solicitado no existe.",
        )
    if not amenity.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El amenity ya está inactivo.",
        )
    amenity.activo = False
    db.commit()
    db.refresh(amenity)
    return amenity
```

- [ ] **Step 5: Correr tests del archivo**

```bash
.venv/Scripts/python.exe -m pytest tests/test_amenities.py -v
```

Expected: todos pasan (los 5 nuevos + los 47 existentes).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/amenities.py tests/test_amenities.py
git commit -m "feat(amenities): DELETE soft + filtro activo (admin con flag ve inactivos)"
```

---

## Task 3: Validaciones de política en POST reservas

**Files:**
- Modify: `backend/routers/amenities.py:151-196` (crear_reserva)
- Create: `tests/test_reservas.py` (archivo nuevo con tests TDD)

- [ ] **Step 1: Crear `tests/test_reservas.py` con tests fallantes**

```python
from datetime import datetime, timedelta

from backend.models import Amenity, EstadoReserva, Reserva


def _en_futuro(dias=1, horas=10, dur_horas=2):
    """Helper: devuelve (inicio, fin) en el futuro relativo a now."""
    inicio = datetime.now().replace(microsecond=0) + timedelta(days=dias, hours=horas)
    fin = inicio + timedelta(hours=dur_horas)
    return inicio.isoformat(), fin.isoformat()


def test_crear_reserva_como_representante_devuelve_403(client, headers_representante):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_crear_reserva_amenity_inactivo_devuelve_409(
    client, headers_depto_a, db_session
):
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 409


def test_crear_reserva_en_el_pasado_devuelve_400(client, headers_depto_a):
    pasado_inicio = (datetime.now() - timedelta(days=2)).isoformat()
    pasado_fin = (datetime.now() - timedelta(days=2, hours=-2)).isoformat()
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": pasado_inicio, "fin": pasado_fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_crear_reserva_supera_duracion_maxima_devuelve_400(
    client, headers_depto_a, db_session
):
    a = db_session.get(Amenity, 301)
    a.duracion_maxima_horas = 2
    db_session.commit()
    inicio, fin = _en_futuro(dur_horas=5)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_crear_reserva_supera_anticipacion_maxima_devuelve_400(
    client, headers_depto_a, db_session
):
    a = db_session.get(Amenity, 301)
    a.anticipacion_maxima_dias = 5
    db_session.commit()
    inicio, fin = _en_futuro(dias=10)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_crear_reserva_supera_max_activas_por_depto_devuelve_409(
    client, headers_depto_a, db_session
):
    a = db_session.get(Amenity, 301)
    a.max_reservas_activas_por_depto = 1
    db_session.commit()
    # 1ra reserva: OK
    inicio1, fin1 = _en_futuro(dias=2)
    r1 = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio1, "fin": fin1},
        headers=headers_depto_a,
    )
    assert r1.status_code == 201
    # 2da reserva del mismo depto al mismo amenity → 409
    inicio2, fin2 = _en_futuro(dias=5)
    r2 = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio2, "fin": fin2},
        headers=headers_depto_a,
    )
    assert r2.status_code == 409


def test_crear_reserva_admin_no_aplica_max_activas(
    client, headers_admin, db_session
):
    a = db_session.get(Amenity, 301)
    a.max_reservas_activas_por_depto = 1
    db_session.commit()
    inicio1, fin1 = _en_futuro(dias=2)
    inicio2, fin2 = _en_futuro(dias=5)
    assert client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio1, "fin": fin1},
        headers=headers_admin,
    ).status_code == 201
    # 2da reserva de admin → OK (no aplica límite)
    assert client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio2, "fin": fin2},
        headers=headers_admin,
    ).status_code == 201
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py -v
```

Expected: FAIL (varias razones, los endpoints aún no validan).

- [ ] **Step 3: Reescribir `crear_reserva` con nuevas validaciones**

En `backend/routers/amenities.py`, reemplazar `crear_reserva` (líneas 151-196). Primero agregar imports al inicio del archivo:

```python
from datetime import date, datetime, time, timezone
```

(Si ya está parcialmente, sumar lo que falte. `timezone` es nuevo si no estaba.)

Reemplazar `crear_reserva` con:

```python
@router.post(
    "/{amenity_id}/reservas",
    response_model=ReservaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar un amenity",
)
def crear_reserva(
    amenity_id: int,
    payload: ReservaCrear,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
) -> Reserva:
    amenity = db.get(Amenity, amenity_id)
    if amenity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El amenity solicitado no existe.",
        )

    if not amenity.activo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El amenity está inactivo.",
        )

    # Normalización: payload.inicio/fin pueden venir con tz o naive (FastAPI parse).
    # Comparamos en naive contra datetime.now() (que también es naive) para evitar
    # mezclar offsets — el front siempre manda local time naive.
    inicio_naive = payload.inicio.replace(tzinfo=None) if payload.inicio.tzinfo else payload.inicio
    fin_naive = payload.fin.replace(tzinfo=None) if payload.fin.tzinfo else payload.fin
    ahora = datetime.now().replace(microsecond=0)

    if inicio_naive <= ahora:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede reservar para el pasado.",
        )

    duracion_horas = (fin_naive - inicio_naive).total_seconds() / 3600
    if amenity.duracion_maxima_horas is not None and duracion_horas > amenity.duracion_maxima_horas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La duración supera el máximo permitido ({amenity.duracion_maxima_horas}h).",
        )

    if amenity.anticipacion_maxima_dias is not None:
        dias_anticipacion = (inicio_naive.date() - ahora.date()).days
        if dias_anticipacion > amenity.anticipacion_maxima_dias:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No se puede reservar con más de {amenity.anticipacion_maxima_dias} "
                    f"días de anticipación."
                ),
            )

    # Límite de reservas activas por depto. Solo aplica a rol departamento.
    if user.rol == Rol.departamento and amenity.max_reservas_activas_por_depto is not None:
        activas = db.scalar(
            select(func.count(Reserva.id)).where(
                Reserva.amenity_id == amenity_id,
                Reserva.usuario_id == user.id,
                Reserva.estado == EstadoReserva.confirmada,
                Reserva.inicio > ahora,
            )
        ) or 0
        if activas >= amenity.max_reservas_activas_por_depto:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya alcanzaste el máximo de reservas activas para este amenity "
                    f"({amenity.max_reservas_activas_por_depto})."
                ),
            )

    # Anti-solapamiento (ya existía).
    solape_id = db.scalar(
        select(Reserva.id).where(
            Reserva.amenity_id == amenity_id,
            Reserva.estado == EstadoReserva.confirmada,
            Reserva.inicio < fin_naive,
            Reserva.fin > inicio_naive,
        )
    )
    if solape_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El horario solicitado se superpone con una reserva existente.",
        )

    reserva = Reserva(
        amenity_id=amenity_id,
        usuario_id=user.id,
        inicio=inicio_naive,
        fin=fin_naive,
        estado=EstadoReserva.confirmada,
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva
```

Agregar `func` al import de sqlalchemy si no está:

```python
from sqlalchemy import func, select
```

- [ ] **Step 4: Correr tests del nuevo archivo**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py -v
```

Expected: los 7 tests pasan.

- [ ] **Step 5: Correr suite completa para confirmar no-regresión**

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expected: 613+ passed (606 base + 5 task 2 + 7 task 3 = 618, aunque algunos tests viejos de reservas podrían sumar/no contar).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/amenities.py tests/test_reservas.py
git commit -m "feat(reservas): validaciones de política (duración, anticipación, límite por depto)"
```

---

## Task 4: Cobro al confirmar (MovimientoCuenta)

**Files:**
- Modify: `backend/routers/amenities.py` (función `crear_reserva` — agregar bloque de cobro)
- Modify: `tests/test_reservas.py` (sumar 4 tests)

- [ ] **Step 1: Sumar tests fallantes**

Agregar a `tests/test_reservas.py`:

```python
def test_reservar_amenity_con_precio_genera_movimiento_cuenta(
    client, headers_depto_a, db_session
):
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 5000.0
    db_session.commit()

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["movimiento_cuenta_id"] is not None

    m = db_session.get(MovimientoCuenta, body["movimiento_cuenta_id"])
    assert m is not None
    assert m.tipo == TipoMovimiento.nota_debito
    assert m.monto == 5000.0
    assert m.departamento_id == 1  # depto_a
    assert "Laundry" in m.descripcion


def test_reservar_amenity_sin_precio_no_genera_movimiento(
    client, headers_depto_a, db_session
):
    a = db_session.get(Amenity, 301)
    assert a.precio_reserva is None  # SUM no tiene precio por default en fixture
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    assert r.json()["movimiento_cuenta_id"] is None


def test_reservar_admin_amenity_con_precio_no_genera_movimiento(
    client, headers_admin, db_session
):
    a = db_session.get(Amenity, 301)
    a.precio_reserva = 5000.0
    db_session.commit()
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["movimiento_cuenta_id"] is None


def test_movimiento_usa_fecha_de_hoy_no_inicio_reserva(
    client, headers_depto_a, db_session
):
    from datetime import date as date_cls
    from backend.models import MovimientoCuenta

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 3000.0
    db_session.commit()
    inicio, fin = _en_futuro(dias=30)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    mov_id = r.json()["movimiento_cuenta_id"]
    m = db_session.get(MovimientoCuenta, mov_id)
    assert m.fecha == date_cls.today()
```

- [ ] **Step 2: Correr tests — deben fallar**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py::test_reservar_amenity_con_precio_genera_movimiento_cuenta -v
```

Expected: FAIL (`movimiento_cuenta_id` viene null).

- [ ] **Step 3: Sumar bloque de cobro en `crear_reserva`**

En `backend/routers/amenities.py`, modificar `crear_reserva` — antes del `db.commit()` final, insertar:

```python
    # Cobro: solo si reservante es depto y el amenity tiene precio.
    if user.rol == Rol.departamento and amenity.precio_reserva is not None:
        movimiento = MovimientoCuenta(
            departamento_id=user.departamento_id,
            fecha=date.today(),
            tipo=TipoMovimiento.nota_debito,
            monto=amenity.precio_reserva,
            descripcion=f"Reserva {amenity.nombre} {inicio_naive.date().isoformat()}",
        )
        db.add(movimiento)
        db.flush()  # para obtener el id
        reserva.movimiento_cuenta_id = movimiento.id
```

Asegurar imports al inicio del archivo:

```python
from ..models import (
    Amenity, EstadoReserva, MovimientoCuenta, Reserva, Rol, TipoMovimiento,
)
```

- [ ] **Step 4: Correr tests de cobro**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py -v
```

Expected: los 11 tests pasan.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/amenities.py tests/test_reservas.py
git commit -m "feat(reservas): cobro automático al confirmar (MovimientoCuenta nota_debito)"
```

---

## Task 5: Reversa al cancelar

**Files:**
- Modify: `backend/routers/reservas.py:46-76` (cancelar)
- Modify: `tests/test_reservas.py` (sumar 4 tests)

- [ ] **Step 1: Sumar tests fallantes**

Agregar a `tests/test_reservas.py`:

```python
def test_cancelar_reserva_dueno_dentro_de_plazo_reversa_cargo(
    client, headers_depto_a, db_session
):
    from backend.models import MovimientoCuenta, TipoMovimiento

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    a.horas_minimas_cancelacion = 24
    db_session.commit()

    # Reserva en +5 días → bien dentro del plazo gratuito
    inicio, fin = _en_futuro(dias=5)
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    mov_inicial_id = r.json()["movimiento_cuenta_id"]

    # Cancelar
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    # Buscar la nota_credito reversora del mismo depto
    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.departamento_id == 1,
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
        MovimientoCuenta.monto == 4000.0,
    ).order_by(MovimientoCuenta.id.desc()).first()
    assert reversa is not None
    assert reversa.id != mov_inicial_id


def test_cancelar_reserva_dueno_fuera_de_plazo_no_reversa(
    client, headers_depto_a, db_session
):
    from backend.models import MovimientoCuenta, TipoMovimiento
    from datetime import datetime, timedelta

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    a.horas_minimas_cancelacion = 48  # 2 días
    db_session.commit()

    # Reserva en +12 horas → fuera del plazo de 48h
    inicio = (datetime.now() + timedelta(hours=12)).replace(microsecond=0).isoformat()
    fin = (datetime.now() + timedelta(hours=14)).replace(microsecond=0).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    reserva_id = r.json()["id"]

    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.departamento_id == 1,
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
    ).first()
    assert reversa is None


def test_cancelar_reserva_admin_cancela_ajena_siempre_reversa(
    client, headers_admin, headers_depto_a, db_session
):
    from backend.models import MovimientoCuenta, TipoMovimiento
    from datetime import datetime, timedelta

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    a.horas_minimas_cancelacion = 48  # plazo de 48h
    db_session.commit()

    # Depto reserva con +12h (fuera del plazo gratuito normalmente)
    inicio = (datetime.now() + timedelta(hours=12)).replace(microsecond=0).isoformat()
    fin = (datetime.now() + timedelta(hours=14)).replace(microsecond=0).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    # Admin cancela → reversa aunque esté fuera de plazo
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
    ).first()
    assert reversa is not None


def test_cancelar_reserva_sin_horas_minimas_siempre_reversa(
    client, headers_depto_a, db_session
):
    from backend.models import MovimientoCuenta, TipoMovimiento
    from datetime import datetime, timedelta

    a = db_session.get(Amenity, 301)
    a.precio_reserva = 4000.0
    # horas_minimas_cancelacion queda en None
    db_session.commit()

    inicio = (datetime.now() + timedelta(hours=1)).replace(microsecond=0).isoformat()
    fin = (datetime.now() + timedelta(hours=3)).replace(microsecond=0).isoformat()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    reversa = db_session.query(MovimientoCuenta).filter(
        MovimientoCuenta.tipo == TipoMovimiento.nota_credito,
    ).first()
    assert reversa is not None
```

- [ ] **Step 2: Correr — deben fallar**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py::test_cancelar_reserva_dueno_dentro_de_plazo_reversa_cargo -v
```

Expected: FAIL (no se crea reversa).

- [ ] **Step 3: Reescribir `cancelar_reserva` en `backend/routers/reservas.py`**

Reemplazar contenido completo del archivo:

```python
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import (
    Amenity, EstadoReserva, MovimientoCuenta, Reserva, Rol, TipoMovimiento,
)
from ..schemas import ReservaOut

router = APIRouter(prefix="/reservas", tags=["Amenities"])


@router.get(
    "",
    response_model=list[ReservaOut],
    status_code=status.HTTP_200_OK,
    summary="Listar reservas",
)
def listar_reservas(
    estado: EstadoReserva | None = Query(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Reserva]:
    stmt = select(Reserva).order_by(Reserva.inicio.desc(), Reserva.id.desc())
    if user.rol == Rol.departamento:
        stmt = stmt.where(Reserva.usuario_id == user.id)
    if estado is not None:
        stmt = stmt.where(Reserva.estado == estado)
    return list(db.scalars(stmt).all())


@router.delete(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Cancelar una reserva",
)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Reserva:
    reserva = db.get(Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva solicitada no existe.",
        )

    es_dueno = reserva.usuario_id == user.id
    es_admin = user.rol == Rol.administracion
    if not (es_dueno or es_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    if reserva.estado == EstadoReserva.cancelada:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La reserva ya está cancelada.",
        )

    reserva.estado = EstadoReserva.cancelada

    # Reversa del cargo, si tenía MovimientoCuenta asociado.
    if reserva.movimiento_cuenta_id is not None:
        amenity = db.get(Amenity, reserva.amenity_id)
        mov_original = db.get(MovimientoCuenta, reserva.movimiento_cuenta_id)
        reversar = False

        # Admin cancela reserva ajena → siempre reversa
        if es_admin and not es_dueno:
            reversar = True
        else:
            # Dueño cancela su propia: depende del plazo
            if amenity.horas_minimas_cancelacion is None:
                reversar = True
            else:
                horas_hasta_inicio = (reserva.inicio - datetime.now()).total_seconds() / 3600
                if horas_hasta_inicio >= amenity.horas_minimas_cancelacion:
                    reversar = True

        if reversar and mov_original is not None:
            nota_credito = MovimientoCuenta(
                departamento_id=mov_original.departamento_id,
                fecha=date.today(),
                tipo=TipoMovimiento.nota_credito,
                monto=mov_original.monto,
                descripcion=f"Reversa de reserva cancelada {reserva.inicio.date().isoformat()}",
            )
            db.add(nota_credito)

    db.commit()
    db.refresh(reserva)
    return reserva
```

- [ ] **Step 4: Correr tests del archivo**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py -v
```

Expected: 15 tests pasan.

- [ ] **Step 5: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expected: 626+ passed sin fallos.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reservas.py tests/test_reservas.py
git commit -m "feat(reservas): reversa al cancelar (con plazo, sin plazo, admin override)"
```

---

## Task 6: GET /reservas/{id}

**Files:**
- Modify: `backend/routers/reservas.py` (sumar endpoint GET single)
- Modify: `tests/test_reservas.py` (sumar 3 tests)

- [ ] **Step 1: Sumar tests fallantes**

```python
def test_obtener_reserva_dueno_devuelve_200(client, headers_depto_a):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    rg = client.get(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rg.status_code == 200
    assert rg.json()["id"] == reserva_id


def test_obtener_reserva_admin_devuelve_200(client, headers_admin, headers_depto_a):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    rg = client.get(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rg.status_code == 200


def test_obtener_reserva_ajena_como_depto_devuelve_403(
    client, headers_depto_a, headers_depto_b
):
    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]
    rg = client.get(f"/reservas/{reserva_id}", headers=headers_depto_b)
    assert rg.status_code == 403


def test_obtener_reserva_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/reservas/99999", headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 2: Correr — fallan con 405 o 404**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py::test_obtener_reserva_dueno_devuelve_200 -v
```

Expected: FAIL.

- [ ] **Step 3: Sumar endpoint en `backend/routers/reservas.py`**

Insertar entre `listar_reservas` y `cancelar_reserva`:

```python
@router.get(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de una reserva",
)
def obtener_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Reserva:
    reserva = db.get(Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva solicitada no existe.",
        )
    es_dueno = reserva.usuario_id == user.id
    es_admin = user.rol == Rol.administracion
    if not (es_dueno or es_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )
    return reserva
```

- [ ] **Step 4: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py -v
```

Expected: los 4 tests pasan.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/reservas.py tests/test_reservas.py
git commit -m "feat(reservas): GET /reservas/{id} con gating dueño/admin"
```

---

## Task 7: Notificaciones

**Files:**
- Modify: `backend/notificaciones.py` (sumar 2 helpers)
- Modify: `backend/routers/amenities.py` (llamar al helper de confirmación al final de crear_reserva)
- Modify: `backend/routers/reservas.py` (llamar al helper de admin-cancela al final de cancelar_reserva)
- Modify: `tests/test_reservas.py` (sumar 2 tests)

- [ ] **Step 1: Sumar tests fallantes**

```python
def test_admin_cancela_reserva_ajena_notifica_al_depto(
    client, headers_admin, headers_depto_a, db_session
):
    from backend.models import Notificacion

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    notif_antes = db_session.query(Notificacion).count()
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_admin)
    assert rc.status_code == 200

    notif_despues = db_session.query(Notificacion).count()
    assert notif_despues > notif_antes


def test_depto_cancela_su_reserva_no_genera_notificacion(
    client, headers_depto_a, db_session
):
    from backend.models import Notificacion

    inicio, fin = _en_futuro()
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": inicio, "fin": fin},
        headers=headers_depto_a,
    )
    reserva_id = r.json()["id"]

    notif_antes = db_session.query(Notificacion).count()
    rc = client.delete(f"/reservas/{reserva_id}", headers=headers_depto_a)
    assert rc.status_code == 200

    notif_despues = db_session.query(Notificacion).count()
    assert notif_despues == notif_antes
```

- [ ] **Step 2: Correr — fallan**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py::test_admin_cancela_reserva_ajena_notifica_al_depto -v
```

Expected: FAIL (notif_despues == notif_antes).

- [ ] **Step 3: Sumar helpers en `backend/notificaciones.py`**

Al final del archivo, agregar:

```python
def notificar_reserva_creada(
    db: Session,
    reserva,  # type: Reserva
    amenity_nombre: str,
    monto_cobrado: float | None,
) -> None:
    """Email-only al depto que reservó. Sin campanita (acaba de ver la confirmación)."""
    from .models import Rol, Usuario

    usuario = db.get(Usuario, reserva.usuario_id)
    if usuario is None or usuario.rol != Rol.departamento or not usuario.email:
        return

    fecha_str = reserva.inicio.strftime("%Y-%m-%d %H:%M")
    cuerpo = f"Tu reserva de {amenity_nombre} para el {fecha_str} fue confirmada."
    if monto_cobrado is not None:
        cuerpo += f"\nSe cargó ${monto_cobrado:.2f} a tu cuenta corriente."
    cuerpo += "\n\nSaludos,\nAdministración."

    enviar_email(
        to=usuario.email,
        subject=f"Reserva confirmada: {amenity_nombre}",
        body=cuerpo,
        attachments=[],
    )


def notificar_reserva_cancelada_por_admin(
    db: Session,
    reserva,  # type: Reserva
    amenity_nombre: str,
    monto_reversado: float | None,
) -> None:
    """Doble canal cuando admin cancela una reserva ajena."""
    from .models import Rol, Usuario

    usuarios = list(db.scalars(
        select(Usuario).where(
            Usuario.id == reserva.usuario_id,
            Usuario.rol == Rol.departamento,
        )
    ).all())

    if not usuarios:
        return

    fecha_str = reserva.inicio.strftime("%Y-%m-%d %H:%M")
    mensaje = f"La administración canceló tu reserva de {amenity_nombre} del {fecha_str}."
    if monto_reversado is not None:
        mensaje += f" Se reversó el cargo de ${monto_reversado:.2f}."

    for u in usuarios:
        crear_notificacion(db, usuario_id=u.id, mensaje=mensaje, link="/reservas")
        if u.email:
            enviar_email(
                to=u.email,
                subject=f"Tu reserva de {amenity_nombre} fue cancelada",
                body=f"Hola,\n\n{mensaje}\n\nSaludos,\nAdministración.",
                attachments=[],
            )
```

- [ ] **Step 4: Llamar al helper en `crear_reserva`**

En `backend/routers/amenities.py`, modificar `crear_reserva` — después de `db.refresh(reserva)` y antes del `return`:

```python
    from ..notificaciones import notificar_reserva_creada
    monto = amenity.precio_reserva if (user.rol == Rol.departamento and amenity.precio_reserva is not None) else None
    notificar_reserva_creada(db, reserva, amenity.nombre, monto)
```

(Import dentro de la función para evitar problemas circulares; el patrón se usa en otros routers.)

- [ ] **Step 5: Llamar al helper en `cancelar_reserva`**

En `backend/routers/reservas.py`, modificar `cancelar_reserva` — capturar `monto_reversado` durante la lógica de reversa y notificar al final.

Reemplazar el bloque `if reserva.movimiento_cuenta_id is not None:` y posterior `db.commit() / db.refresh / return` con:

```python
    monto_reversado = None
    if reserva.movimiento_cuenta_id is not None:
        amenity = db.get(Amenity, reserva.amenity_id)
        mov_original = db.get(MovimientoCuenta, reserva.movimiento_cuenta_id)
        reversar = False
        if es_admin and not es_dueno:
            reversar = True
        else:
            if amenity.horas_minimas_cancelacion is None:
                reversar = True
            else:
                horas_hasta_inicio = (reserva.inicio - datetime.now()).total_seconds() / 3600
                if horas_hasta_inicio >= amenity.horas_minimas_cancelacion:
                    reversar = True

        if reversar and mov_original is not None:
            nota_credito = MovimientoCuenta(
                departamento_id=mov_original.departamento_id,
                fecha=date.today(),
                tipo=TipoMovimiento.nota_credito,
                monto=mov_original.monto,
                descripcion=f"Reversa de reserva cancelada {reserva.inicio.date().isoformat()}",
            )
            db.add(nota_credito)
            monto_reversado = mov_original.monto

    if es_admin and not es_dueno:
        from ..notificaciones import notificar_reserva_cancelada_por_admin
        amenity_n = db.get(Amenity, reserva.amenity_id)
        notificar_reserva_cancelada_por_admin(db, reserva, amenity_n.nombre, monto_reversado)

    db.commit()
    db.refresh(reserva)
    return reserva
```

- [ ] **Step 6: Correr tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_reservas.py -v
```

Expected: los 2 tests nuevos pasan + todos los anteriores siguen.

- [ ] **Step 7: Commit**

```bash
git add backend/notificaciones.py backend/routers/amenities.py backend/routers/reservas.py tests/test_reservas.py
git commit -m "feat(reservas): notificaciones (email al reservar, doble canal cuando admin cancela ajena)"
```

---

## Task 8: OpenAPI + seed

**Files:**
- Modify: `openapi.yaml` (schemas + paths)
- Modify: `backend/seed.py` (sumar 2 amenities demo con políticas)

- [ ] **Step 1: Actualizar schema `Amenity` en `openapi.yaml`**

Buscar el schema `Amenity` (o `AmenityOut`) y reemplazar properties con:

```yaml
    Amenity:
      type: object
      required: [id, nombre, descripcion, activo, precio_reserva, duracion_maxima_horas, anticipacion_maxima_dias, max_reservas_activas_por_depto, horas_minimas_cancelacion]
      properties:
        id: { type: integer, format: int64 }
        nombre: { type: string }
        descripcion: { type: string, nullable: true }
        activo: { type: boolean }
        precio_reserva: { type: number, nullable: true }
        duracion_maxima_horas: { type: integer, nullable: true }
        anticipacion_maxima_dias: { type: integer, nullable: true }
        max_reservas_activas_por_depto: { type: integer, nullable: true }
        horas_minimas_cancelacion: { type: integer, nullable: true }

    AmenityCrear:
      type: object
      required: [nombre]
      properties:
        nombre: { type: string, minLength: 1, maxLength: 100 }
        descripcion: { type: string, maxLength: 500, nullable: true }
        precio_reserva: { type: number, minimum: 0, nullable: true }
        duracion_maxima_horas: { type: integer, exclusiveMinimum: 0, nullable: true }
        anticipacion_maxima_dias: { type: integer, exclusiveMinimum: 0, nullable: true }
        max_reservas_activas_por_depto: { type: integer, exclusiveMinimum: 0, nullable: true }
        horas_minimas_cancelacion: { type: integer, minimum: 0, nullable: true }

    AmenityActualizar:
      type: object
      properties:
        nombre: { type: string, minLength: 1, maxLength: 100, nullable: true }
        descripcion: { type: string, maxLength: 500, nullable: true }
        activo: { type: boolean, nullable: true }
        precio_reserva: { type: number, minimum: 0, nullable: true }
        duracion_maxima_horas: { type: integer, exclusiveMinimum: 0, nullable: true }
        anticipacion_maxima_dias: { type: integer, exclusiveMinimum: 0, nullable: true }
        max_reservas_activas_por_depto: { type: integer, exclusiveMinimum: 0, nullable: true }
        horas_minimas_cancelacion: { type: integer, minimum: 0, nullable: true }
```

- [ ] **Step 2: Extender `Reserva` schema**

```yaml
    Reserva:
      type: object
      required: [id, amenity_id, usuario_id, inicio, fin, estado, movimiento_cuenta_id]
      properties:
        id: { type: integer, format: int64 }
        amenity_id: { type: integer, format: int64 }
        usuario_id: { type: integer, format: int64 }
        inicio: { type: string, format: date-time }
        fin: { type: string, format: date-time }
        estado: { type: string, enum: [confirmada, cancelada] }
        movimiento_cuenta_id: { type: integer, format: int64, nullable: true }
```

- [ ] **Step 3: Sumar paths nuevos a `openapi.yaml`**

Sumar query param a GET /amenities (debajo de la definición existente):

```yaml
      parameters:
        - name: incluir_inactivos
          in: query
          required: false
          description: Si true y el caller es admin, devuelve también inactivos.
          schema: { type: boolean, default: false }
```

Sumar al final de paths o donde encajen:

```yaml
  /amenities/{amenity_id}:
    delete:
      tags: [Amenities]
      summary: Dar de baja un amenity (soft-delete)
      operationId: darDeBajaAmenity
      parameters:
        - name: amenity_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: Amenity dado de baja exitosamente.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Amenity'
        '401':
          $ref: '#/components/responses/NoAutenticado'
        '403':
          $ref: '#/components/responses/AccesoDenegado'
        '404':
          $ref: '#/components/responses/NoEncontrado'
        '409':
          description: El amenity ya estaba inactivo.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /reservas/{reserva_id}:
    get:
      tags: [Amenities]
      summary: Obtener detalle de una reserva
      operationId: obtenerReserva
      parameters:
        - name: reserva_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: Detalle de la reserva.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Reserva'
        '401':
          $ref: '#/components/responses/NoAutenticado'
        '403':
          $ref: '#/components/responses/AccesoDenegado'
        '404':
          $ref: '#/components/responses/NoEncontrado'
```

Si el path `/amenities/{amenity_id}` ya existe en el yaml (para PATCH), sumar `delete:` debajo de `patch:` en el mismo bloque (no duplicar la clave).

- [ ] **Step 4: Validar yaml**

```bash
.venv/Scripts/python.exe -c "import yaml; spec = yaml.safe_load(open('openapi.yaml').read()); print('paths:', len(spec['paths']), 'schemas:', len(spec['components']['schemas']))"
```

Expected: OK sin error.

- [ ] **Step 5: Sumar 2 amenities demo al seed**

En `backend/seed.py`, agregar import:

```python
from .models import (
    # ... existentes ...
    Amenity,
)
```

(Si ya está, no duplicar.)

Antes del `db.commit()` final, sumar:

```python
    # ----- Fase 12: amenities demo -----
    db.add_all([
        Amenity(
            nombre="SUM",
            descripcion="Salón de usos múltiples (eventos privados)",
            activo=True,
            precio_reserva=20000.0,
            duracion_maxima_horas=12,
            anticipacion_maxima_dias=60,
            max_reservas_activas_por_depto=2,
            horas_minimas_cancelacion=48,
        ),
        Amenity(
            nombre="Laundry",
            descripcion="Lavandería compartida",
            activo=True,
            precio_reserva=None,  # gratuito
            duracion_maxima_horas=3,
            anticipacion_maxima_dias=14,
            max_reservas_activas_por_depto=3,
            horas_minimas_cancelacion=None,  # cancelable siempre
        ),
    ])
    db.flush()
```

- [ ] **Step 6: Smoke seed**

```bash
rm -f consorcio.db
.venv/Scripts/python.exe -c "
import os
os.environ['DATABASE_URL'] = 'sqlite:///consorcio.db'
os.environ['SECRET_KEY'] = 'dev-key-1234567890-secret-please'
os.environ['SEED_DEFAULT_PASSWORD'] = 'testpw'
from backend.database import engine, SessionLocal
from backend.models import Base, Amenity
from backend.seed import seed_if_empty
Base.metadata.create_all(engine)
db = SessionLocal()
seed_if_empty(db)
for a in db.query(Amenity).all():
    print(f'  {a.id}: {a.nombre} activo={a.activo} precio={a.precio_reserva}')
"
rm -f consorcio.db
```

Expected: 2 amenities listados, SUM con precio, Laundry sin precio.

- [ ] **Step 7: Suite final**

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expected: 630+ passed.

- [ ] **Step 8: Commit**

```bash
git add openapi.yaml backend/seed.py
git commit -m "docs(openapi)+seed: Fase 12 schemas/paths y 2 amenities demo"
```

---

## Task 9: Frontend API clients

**Files:**
- Create: `frontend/src/api/amenities.js`
- Create: `frontend/src/api/reservas.js`

- [ ] **Step 1: Crear `frontend/src/api/amenities.js`**

```javascript
import { apiFetch } from "./client";

export function listarAmenities({ incluirInactivos = false } = {}) {
  const qs = incluirInactivos ? "?incluir_inactivos=true" : "";
  return apiFetch(`/amenities${qs}`);
}

export function crearAmenity(payload) {
  return apiFetch("/amenities", { method: "POST", body: payload });
}

export function actualizarAmenity(id, payload) {
  return apiFetch(`/amenities/${id}`, { method: "PATCH", body: payload });
}

export function darDeBajaAmenity(id) {
  return apiFetch(`/amenities/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Crear `frontend/src/api/reservas.js`**

```javascript
import { apiFetch } from "./client";

export function listarReservas({ estado } = {}) {
  const qs = estado ? `?estado=${estado}` : "";
  return apiFetch(`/reservas${qs}`);
}

export function obtenerReserva(id) {
  return apiFetch(`/reservas/${id}`);
}

export function crearReserva(amenityId, { inicio, fin }) {
  return apiFetch(`/amenities/${amenityId}/reservas`, {
    method: "POST",
    body: { inicio, fin },
  });
}

export function cancelarReserva(id) {
  return apiFetch(`/reservas/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Build smoke**

```bash
cd frontend && npm run build && cd ..
```

Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/amenities.js frontend/src/api/reservas.js
git commit -m "feat(frontend/api): clients amenities + reservas"
```

---

## Task 10: Pantalla `/amenities` + `ModalAmenity`

**Files:**
- Create: `frontend/src/screens/Amenities.jsx`
- Create: `frontend/src/components/ModalAmenity.jsx`

- [ ] **Step 1: Crear `ModalAmenity.jsx`**

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { crearAmenity, actualizarAmenity } from "../api/amenities";

export default function ModalAmenity({ item, onClose, onGuardado }) {
  const esEditar = item !== null;
  const [nombre, setNombre] = useState(item?.nombre || "");
  const [descripcion, setDescripcion] = useState(item?.descripcion || "");
  const [precio, setPrecio] = useState(item?.precio_reserva ?? "");
  const [duracion, setDuracion] = useState(item?.duracion_maxima_horas ?? "");
  const [anticipacion, setAnticipacion] = useState(item?.anticipacion_maxima_dias ?? "");
  const [maxActivas, setMaxActivas] = useState(item?.max_reservas_activas_por_depto ?? "");
  const [horasCancelacion, setHorasCancelacion] = useState(item?.horas_minimas_cancelacion ?? "");
  const [activa, setActiva] = useState(item?.activo ?? true);
  const [error, setError] = useState("");

  function num(v) {
    if (v === "" || v === null || v === undefined) return null;
    return Number(v);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const payload = {
      nombre,
      descripcion: descripcion || null,
      precio_reserva: num(precio),
      duracion_maxima_horas: num(duracion),
      anticipacion_maxima_dias: num(anticipacion),
      max_reservas_activas_por_depto: num(maxActivas),
      horas_minimas_cancelacion: num(horasCancelacion),
    };
    if (esEditar) payload.activo = activa;
    const r = esEditar
      ? await actualizarAmenity(item.id, payload)
      : await crearAmenity(payload);
    if (r.status === 200 || r.status === 201) onGuardado();
    else setError(r.data?.detail || "Error al guardar.");
  }

  return (
    <Modal titulo={esEditar ? "Editar amenity" : "Nuevo amenity"} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>Nombre <input value={nombre} onChange={(e) => setNombre(e.target.value)} required maxLength={100} /></label>
        <label>Descripción <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={500} rows={2} /></label>
        <label>Precio por reserva (vacío = gratuito) <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} /></label>
        <label>Duración máx (horas, vacío = sin límite) <input type="number" min="1" value={duracion} onChange={(e) => setDuracion(e.target.value)} /></label>
        <label>Anticipación máx (días, vacío = sin límite) <input type="number" min="1" value={anticipacion} onChange={(e) => setAnticipacion(e.target.value)} /></label>
        <label>Máx reservas activas por depto (vacío = sin límite) <input type="number" min="1" value={maxActivas} onChange={(e) => setMaxActivas(e.target.value)} /></label>
        <label>Horas mínimas para cancelación gratuita (vacío = siempre gratuita) <input type="number" min="0" value={horasCancelacion} onChange={(e) => setHorasCancelacion(e.target.value)} /></label>
        {esEditar && (
          <label><input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Activa</label>
        )}
        {error && <p className="error">{error}</p>}
        <div className="acciones">
          <button type="submit">Guardar</button>
          <button type="button" onClick={onClose}>Cancelar</button>
        </div>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 2: Crear `Amenities.jsx`**

```jsx
import { useEffect, useState } from "react";
import { listarAmenities, darDeBajaAmenity } from "../api/amenities";
import ModalAmenity from "../components/ModalAmenity";

export default function Amenities() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [incluirInactivos, setIncluirInactivos] = useState(false);
  const [error, setError] = useState("");

  async function cargar() {
    setError("");
    const r = await listarAmenities({ incluirInactivos });
    if (r.status === 200) setItems(r.data);
    else setError(r.data?.detail || "No se pudo cargar la lista.");
  }

  useEffect(() => { cargar(); }, [incluirInactivos]);

  async function handleDarDeBaja(a) {
    if (!window.confirm(`¿Dar de baja "${a.nombre}"?`)) return;
    const r = await darDeBajaAmenity(a.id);
    if (r.status === 200) cargar();
    else setError(r.data?.detail || "Error al dar de baja.");
  }

  const fmt = (v) => (v === null || v === undefined ? "—" : v);
  const fmtPrecio = (v) => (v === null || v === undefined ? "Gratis" : `$${Number(v).toLocaleString("es-AR")}`);

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Amenities</h2>
        <button type="button" onClick={() => setModal("nuevo")}>+ Nuevo amenity</button>
      </header>

      <section className="filtros">
        <label><input type="checkbox" checked={incluirInactivos} onChange={(e) => setIncluirInactivos(e.target.checked)} /> Mostrar inactivos</label>
      </section>

      {error && <p className="error">{error}</p>}

      <ul className="lista-cards">
        {items.length === 0 ? (
          <li className="vacio">Sin amenities.</li>
        ) : items.map((a) => (
          <li key={a.id} className={`card-amenity${a.activo ? "" : " inactivo"}`}>
            <h3>{a.nombre} {!a.activo && <small>(inactivo)</small>}</h3>
            {a.descripcion && <p>{a.descripcion}</p>}
            <dl className="amenity-policies">
              <div><dt>Precio:</dt><dd>{fmtPrecio(a.precio_reserva)}</dd></div>
              <div><dt>Duración máx:</dt><dd>{fmt(a.duracion_maxima_horas)} h</dd></div>
              <div><dt>Anticipación máx:</dt><dd>{fmt(a.anticipacion_maxima_dias)} días</dd></div>
              <div><dt>Máx activas por depto:</dt><dd>{fmt(a.max_reservas_activas_por_depto)}</dd></div>
              <div><dt>Cancelación gratuita ≥:</dt><dd>{fmt(a.horas_minimas_cancelacion)} h antes</dd></div>
            </dl>
            <div className="acciones">
              <button type="button" onClick={() => setModal(a)}>Editar</button>
              {a.activo && <button type="button" onClick={() => handleDarDeBaja(a)}>Dar de baja</button>}
            </div>
          </li>
        ))}
      </ul>

      {modal && (
        <ModalAmenity
          item={modal === "nuevo" ? null : modal}
          onClose={() => setModal(null)}
          onGuardado={() => { setModal(null); cargar(); }}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 3: Sumar reglas CSS en `frontend/src/index.css`**

Agregar al final del archivo (o en sección Reservas si se va a hacer):

```css
/* ---------- Cards de amenity (Fase 12) ---------- */
.lista-cards {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 1rem;
}

@media (min-width: 600px) {
  .lista-cards {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }
}

.card-amenity {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 1rem;
}

.card-amenity.inactivo {
  opacity: 0.6;
}

.card-amenity h3 {
  margin: 0 0 0.5rem 0;
}

.amenity-policies {
  margin: 0.5rem 0;
  font-size: 0.85rem;
}

.amenity-policies > div {
  display: flex;
  gap: 0.5rem;
  padding: 0.15rem 0;
}

.amenity-policies dt {
  font-weight: 600;
  color: var(--color-text-muted);
  margin: 0;
}

.amenity-policies dd {
  margin: 0;
}
```

- [ ] **Step 4: Build smoke**

```bash
cd frontend && npm run build && cd ..
```

Expected: build OK.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Amenities.jsx frontend/src/components/ModalAmenity.jsx frontend/src/index.css
git commit -m "feat(frontend): pantalla /amenities (CRUD admin + soft-delete + cards mobile-first)"
```

---

## Task 11: Pantalla `/reservas` — listas y selector

**Files:**
- Create: `frontend/src/screens/Reservas.jsx`

- [ ] **Step 1: Crear `Reservas.jsx` (versión parcial: selector + listas)**

```jsx
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listarAmenities } from "../api/amenities";
import { listarReservas, cancelarReserva } from "../api/reservas";
import { useAuth } from "../auth/AuthContext";

function fmtFecha(iso) {
  return new Date(iso).toLocaleString("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

export default function Reservas() {
  const { user } = useAuth();
  const esAdmin = user?.rol === "administracion";
  const esDepto = user?.rol === "departamento";

  const [amenities, setAmenities] = useState([]);
  const [amenityId, setAmenityId] = useState("");
  const [reservas, setReservas] = useState([]);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  async function cargarAmenities() {
    const r = await listarAmenities();
    if (r.status === 200) {
      setAmenities(r.data);
      if (!amenityId && r.data.length > 0) setAmenityId(String(r.data[0].id));
    }
  }

  async function cargarReservas() {
    const r = await listarReservas();
    if (r.status === 200) setReservas(r.data);
  }

  useEffect(() => { cargarAmenities(); cargarReservas(); }, []);

  const amenitySeleccionado = useMemo(
    () => amenities.find((a) => String(a.id) === amenityId) || null,
    [amenities, amenityId]
  );

  const ahora = useMemo(() => new Date(), []);

  const proximasDelAmenity = useMemo(() => {
    return reservas.filter((r) =>
      String(r.amenity_id) === amenityId &&
      r.estado === "confirmada" &&
      new Date(r.inicio) > ahora
    );
  }, [reservas, amenityId, ahora]);

  const misReservas = useMemo(() => {
    if (!esDepto) return [];
    return reservas
      .filter((r) => r.usuario_id === user.id)
      .slice(0, 20);
  }, [reservas, esDepto, user]);

  async function handleCancelar(r) {
    setError(""); setInfo("");
    const horasHasta = (new Date(r.inicio) - ahora) / 36e5;
    const plazo = amenitySeleccionado?.horas_minimas_cancelacion;
    if (plazo !== null && plazo !== undefined && horasHasta < plazo) {
      if (!window.confirm(`Estás cancelando con menos de ${plazo}h. NO se reintegrará el monto. ¿Confirmás?`)) return;
    } else {
      if (!window.confirm("¿Cancelar esta reserva?")) return;
    }
    const rc = await cancelarReserva(r.id);
    if (rc.status === 200) { setInfo("Reserva cancelada."); cargarReservas(); }
    else setError(rc.data?.detail || "Error al cancelar.");
  }

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Reservas</h2>
        {esAdmin && <Link to="/amenities">Gestionar amenities</Link>}
      </header>

      <section className="filtros">
        <label>Amenity: {" "}
          <select value={amenityId} onChange={(e) => setAmenityId(e.target.value)}>
            {amenities.map((a) => (
              <option key={a.id} value={a.id}>{a.nombre}</option>
            ))}
          </select>
        </label>
      </section>

      {info && <p className="info">{info}</p>}
      {error && <p className="error">{error}</p>}

      {/* placeholder: form de creación va en Task 12 */}

      <section>
        <h3>Próximas reservas (todos los deptos)</h3>
        <ul className="lista-cards">
          {proximasDelAmenity.length === 0 ? (
            <li className="vacio">Sin próximas reservas.</li>
          ) : proximasDelAmenity.map((r) => (
            <li key={r.id} className="card-reserva">
              <h4>{fmtFecha(r.inicio)} → {fmtFecha(r.fin)}</h4>
              <p>Depto del usuario #{r.usuario_id}</p>
            </li>
          ))}
        </ul>
      </section>

      {esDepto && (
        <section>
          <h3>Mis reservas</h3>
          <ul className="lista-cards">
            {misReservas.length === 0 ? (
              <li className="vacio">No tenés reservas.</li>
            ) : misReservas.map((r) => {
              const esFutura = new Date(r.inicio) > ahora;
              const activa = r.estado === "confirmada";
              return (
                <li key={r.id} className={`card-reserva${activa ? "" : " cancelada"}`}>
                  <h4>{fmtFecha(r.inicio)} → {fmtFecha(r.fin)}</h4>
                  <p>Estado: {r.estado}{r.movimiento_cuenta_id ? " — con cargo" : ""}</p>
                  {activa && esFutura && (
                    <button type="button" onClick={() => handleCancelar(r)}>Cancelar</button>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Sumar CSS card-reserva**

En `frontend/src/index.css` agregar:

```css
.card-reserva {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.75rem;
}

.card-reserva.cancelada {
  opacity: 0.5;
  text-decoration: line-through;
}

.card-reserva h4 {
  margin: 0 0 0.25rem 0;
  font-size: 0.95rem;
}
```

- [ ] **Step 3: Build smoke**

```bash
cd frontend && npm run build && cd ..
```

Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/Reservas.jsx frontend/src/index.css
git commit -m "feat(frontend): pantalla /reservas — selector amenity + listas (sin form aún)"
```

---

## Task 12: Pantalla `/reservas` — form de creación

**Files:**
- Modify: `frontend/src/screens/Reservas.jsx` (sumar form + banner políticas)
- Modify: `frontend/src/index.css` (sticky bottom CTA, banner colapsable)

- [ ] **Step 1: Sumar imports y estado del form en `Reservas.jsx`**

Modificar imports:

```jsx
import { crearReserva, ... } from "../api/reservas";
```

Sumar estado dentro del componente:

```jsx
const [fecha, setFecha] = useState("");
const [horaInicio, setHoraInicio] = useState("");
const [horaFin, setHoraFin] = useState("");
const [guardando, setGuardando] = useState(false);
const [bannerAbierto, setBannerAbierto] = useState(false);
```

- [ ] **Step 2: Sumar handler de creación**

```jsx
async function handleCrear(e) {
  e.preventDefault();
  setError(""); setInfo("");
  if (!fecha || !horaInicio || !horaFin) {
    setError("Completá fecha y horarios."); return;
  }
  if (horaFin <= horaInicio) {
    setError("La hora de fin debe ser posterior al inicio."); return;
  }
  const inicio = `${fecha}T${horaInicio}:00`;
  const fin = `${fecha}T${horaFin}:00`;

  // Validación cliente: duración
  const dur = (new Date(fin) - new Date(inicio)) / 36e5;
  if (amenitySeleccionado?.duracion_maxima_horas !== null &&
      amenitySeleccionado?.duracion_maxima_horas !== undefined &&
      dur > amenitySeleccionado.duracion_maxima_horas) {
    setError(`Duración supera el máximo (${amenitySeleccionado.duracion_maxima_horas}h).`);
    return;
  }

  setGuardando(true);
  const r = await crearReserva(amenitySeleccionado.id, { inicio, fin });
  setGuardando(false);
  if (r.status === 201) {
    setInfo("Reserva creada.");
    setFecha(""); setHoraInicio(""); setHoraFin("");
    cargarReservas();
  } else {
    setError(r.data?.detail || "Error al reservar.");
  }
}
```

- [ ] **Step 3: Sumar banner de políticas + form en el JSX**

Insertar después del `<section className="filtros">` y antes de "Próximas reservas":

```jsx
{amenitySeleccionado && (
  <section className={`banner-politicas${bannerAbierto ? " abierto" : ""}`}>
    <header onClick={() => setBannerAbierto(!bannerAbierto)}>
      <strong>{amenitySeleccionado.nombre}</strong>{" "}
      {amenitySeleccionado.precio_reserva
        ? `— $${Number(amenitySeleccionado.precio_reserva).toLocaleString("es-AR")} por reserva`
        : "— gratis"}{" "}
      <span className="banner-toggle">{bannerAbierto ? "▲" : "▼"}</span>
    </header>
    {bannerAbierto && (
      <ul>
        {amenitySeleccionado.duracion_maxima_horas && <li>Duración máx: {amenitySeleccionado.duracion_maxima_horas}h</li>}
        {amenitySeleccionado.anticipacion_maxima_dias && <li>Reservable hasta {amenitySeleccionado.anticipacion_maxima_dias} días en el futuro</li>}
        {amenitySeleccionado.max_reservas_activas_por_depto && <li>Máx {amenitySeleccionado.max_reservas_activas_por_depto} reservas activas por depto</li>}
        {amenitySeleccionado.horas_minimas_cancelacion !== null && amenitySeleccionado.horas_minimas_cancelacion !== undefined
          ? <li>Cancelación con reintegro: hasta {amenitySeleccionado.horas_minimas_cancelacion}h antes</li>
          : <li>Cancelable en cualquier momento</li>}
      </ul>
    )}
  </section>
)}

{amenitySeleccionado && (
  <form onSubmit={handleCrear} className="form-reserva">
    <h3>Nueva reserva</h3>
    <label>Fecha <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} required /></label>
    <label>Hora inicio <input type="time" value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} required /></label>
    <label>Hora fin <input type="time" value={horaFin} onChange={(e) => setHoraFin(e.target.value)} required /></label>
    <div className="cta-sticky">
      <button type="submit" disabled={guardando}>
        {guardando ? "Reservando…" : amenitySeleccionado.precio_reserva
          ? `Confirmar reserva ($${Number(amenitySeleccionado.precio_reserva).toLocaleString("es-AR")})`
          : "Confirmar reserva"}
      </button>
    </div>
  </form>
)}
```

- [ ] **Step 4: Sumar CSS para banner + form**

En `frontend/src/index.css`:

```css
.banner-politicas {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  margin: 0.75rem 0;
}

.banner-politicas header {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.banner-politicas .banner-toggle {
  margin-left: auto;
}

.banner-politicas ul {
  margin: 0.5rem 0 0 1rem;
  font-size: 0.85rem;
}

.form-reserva {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 1rem;
  margin: 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.form-reserva h3 {
  margin: 0;
}

.cta-sticky button {
  width: 100%;
  min-height: 48px;
}

@media (max-width: 599px) {
  .cta-sticky {
    position: sticky;
    bottom: 0;
    background: var(--color-surface);
    padding: 0.5rem 0;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
  }
}
```

- [ ] **Step 5: Build smoke**

```bash
cd frontend && npm run build && cd ..
```

Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/Reservas.jsx frontend/src/index.css
git commit -m "feat(frontend): /reservas form + banner políticas + sticky CTA mobile"
```

---

## Task 13: Sidebar + Routes

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Sumar sección "Espacios comunes" en Sidebar**

En `frontend/src/components/Sidebar.jsx`, dentro del array `SECCIONES`, insertar entre "Tareas y presupuestos" y "Expensas y pagos":

```javascript
  {
    titulo: "Espacios comunes",
    modulos: [
      {
        ruta: "/reservas",
        nombre: "Reservas",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/amenities",
        nombre: "Amenities",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
```

- [ ] **Step 2: Sumar 2 rutas en `App.jsx`**

```jsx
import Amenities from "./screens/Amenities";
import Reservas from "./screens/Reservas";
```

Dentro de las rutas autenticadas (con `RequireAuth`), antes de `<Route path="*" element={<NotFound />} />`:

```jsx
<Route path="reservas" element={<Reservas />} />
<Route path="amenities" element={<Amenities />} />
```

- [ ] **Step 3: Build smoke**

```bash
cd frontend && npm run build && cd ..
```

Expected: módulos transformados subió en 2.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.jsx frontend/src/App.jsx
git commit -m "feat(frontend): sidebar sección Espacios comunes + 2 rutas"
```

---

## Task 14: Smoke E2E manual

**Files:** ninguno (manual)

- [ ] **Step 1: Reset DB y arrancar servers**

```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
.venv\Scripts\python -m uvicorn backend.main:app --reload
# otra terminal:
cd frontend; npm run dev
```

- [ ] **Step 2: Login depto-a y probar flujos**

1. Sidebar muestra "Espacios comunes > Reservas". No muestra "Amenities" (admin only).
2. `/reservas`: selector con SUM y Laundry. Banner colapsable con precio $20.000, duración 12h, anticipación 60 días.
3. **Reservar SUM** para +3 días, 14-18h. Aparece "Reservada". Aparece en "Mis reservas" con "con cargo".
4. Ir a `/mi-cuenta` (cuenta corriente). Ver `nota_debito` de $20.000 con descripción "Reserva SUM YYYY-MM-DD" con fecha de hoy.
5. **Cancelar** la reserva. Confirma sin warning (estamos a >48h del inicio). Aparece en `/mi-cuenta` el `nota_credito` de $20.000.
6. Reservar SUM para mañana 10-12h. Cancelar: el modal **avisa que NO se reintegra** (estamos a <48h). Confirmar. Verificar en `/mi-cuenta`: NO hay reversa.

- [ ] **Step 3: Login admin y probar gestión**

7. `/amenities`: ver 2 amenities con políticas. Editar SUM, cambiar duración a 6h, guardar. Verificar.
8. Dar de baja Laundry. `/reservas` desde depto-a: ya no aparece Laundry en el selector.
9. Volver a admin, reactivar Laundry (PATCH activo=true).
10. Login admin → reservar SUM (no se cobra). Verificar.
11. Admin cancela una reserva de depto-a → notificación campanita aparece en sesión de depto-a + reversa creada.

- [ ] **Step 4: Validar mobile a 375px**

DevTools → device toolbar → iPhone SE.
- `/reservas`: cards apiladas, banner colapsable, CTA sticky abajo.
- `/amenities`: cards apiladas con políticas como pares label/value.
- Sin scroll horizontal en ninguna vista.

- [ ] **Step 5: Suite final**

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expected: ~640+ passed, 0 failed.

---

## Task 15: Roadmap + merge

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`

- [ ] **Step 1: Sumar fila al roadmap**

En la tabla de fases, después de la fila "11", agregar:

```markdown
| **12** ✅ | **Reservas de amenities** (completada YYYY-MM-DD) | Cierra el módulo "Reserva de espacios" del CLAUDE.md. Políticas configurables por amenity (precio, duración máx, anticipación, max activas por depto, plazo cancelación). Cobro automático vía MovimientoCuenta nota_debito al confirmar, reversa al cancelar con reglas de penalty. Soft-delete de amenity con flag activo. Notificaciones: email al depto al reservar, doble canal cuando admin cancela ajena. Frontend mobile-first: lista + form, sin calendario. |
```

(Reemplazar YYYY-MM-DD por la fecha real.)

Sumar al historial:

```markdown
- 2026-MM-DD: **Fase 12 completada** (~640 tests, branch `feature/expensas-fase12-reservas`). Cierra módulo de reservas del CLAUDE.md. Amenity gana 5 campos de política, Reserva gana FK a MovimientoCuenta. Cobro vía cuenta corriente reusando infra de Fase 3.5. Notificaciones doble canal reusando módulo de Fase 11. Frontend con 2 pantallas + 1 modal mobile-first.
```

- [ ] **Step 2: Commit roadmap**

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 12 completada (reservas de amenities)"
```

- [ ] **Step 3: Merge a master**

```bash
git checkout master
git merge --no-ff feature/expensas-fase12-reservas -m "Merge feature/expensas-fase12-reservas: módulo de reservas completo

Fase 12 — Reservas de amenities end-to-end. Políticas por amenity, cobro
vía MovimientoCuenta, soft-delete, notificaciones doble canal, frontend
mobile-first."
```

- [ ] **Step 4: Done**

---

## Notas finales

- **Orden de tasks**: modelos+schemas → soft-delete amenity → validaciones POST reservas → cobro → reversa → GET single → notif → docs/seed → frontend clients → screens → sidebar/routes → smoke/merge.
- **TDD**: tasks 2, 3, 4, 5, 6, 7 escriben tests primero (RED) → implementación (GREEN) → commit.
- **Commits frecuentes**: ~15 commits totales.
- **Reusabilidad**: el patrón de "cobro vía MovimientoCuenta + reversa al cancelar" queda como blueprint para futuros módulos con cobros automáticos (ej. multas, eventos).
- **Migración**: clean start. Borrar `consorcio.db` antes de arrancar.
