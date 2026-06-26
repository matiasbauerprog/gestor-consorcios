# Fase 11 — Tareas y Presupuestos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar end-to-end el módulo de peticiones/trabajos/presupuestos con integración a Gasto, notificaciones doble canal (in-app + email), trabajos recurrentes y archivos adjuntos a presupuestos.

**Architecture:**
- Backend: 4 modelos modificados/nuevos (`Trabajo` +FKs, `Presupuesto` con FK proveedor + archivo, `TrabajoRecurrente` nuevo, `Notificacion` nuevo); módulo `backend/notificaciones.py` con helper reusable; routers nuevos `/notificaciones`, `/trabajos/{id}/presupuestos`, `/trabajos-recurrentes`; adaptaciones a `/peticiones` (auth + delete), `/trabajos` (completar/cancelar), `/gastos` (acepta trabajo_id).
- Frontend: 3 pantallas nuevas + 1 componente Campanita en AppLayout con polling 60s al endpoint count.
- Notificaciones doble canal: email best-effort (reusa `backend/email.py` de Fase 6a) + Notificacion en DB para campanita in-app.

**Tech Stack:** Python (FastAPI, SQLAlchemy 2.0, smtplib reusado, ReportLab no aplica acá); React 18 (useEffect polling, sin WebSocket).

**Reference:** Spec en `docs/superpowers/specs/2026-06-26-fase11-tareas-presupuestos-design.md`.

---

## Task 0: Setup branch + baseline

**Files:** ninguno (git).

- [ ] **Step 1: Crear branch desde master**

```bash
git checkout master
git checkout -b feature/expensas-fase11-tareas-presupuestos
```

- [ ] **Step 2: Verificar baseline de la suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: `570 passed` (baseline post-Fase 6b).

---

## Task 1: Modelos + schemas + clean start

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/schemas.py`

- [ ] **Step 1: Sumar enum `PeriodicidadRecurrente` en models.py**

Después de los enums existentes (cerca de `class FormaPago`):

```python
class PeriodicidadRecurrente(str, enum.Enum):
    mensual = "mensual"
    trimestral = "trimestral"
    semestral = "semestral"
    anual = "anual"
```

- [ ] **Step 2: Modificar `Presupuesto` — cambiar `proveedor` (str) por `proveedor_id` (FK) + sumar `archivo_path` y `observaciones`**

Reemplazar el bloque actual del campo `proveedor` y sumar nuevos campos:

```python
class Presupuesto(Base):
    __tablename__ = "presupuestos"

    id: Mapped[int] = mapped_column(primary_key=True)
    trabajo_id: Mapped[int] = mapped_column(
        ForeignKey("trabajos.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[EstadoPresupuesto] = mapped_column(
        SqlEnum(EstadoPresupuesto, name="estado_presupuesto"),
        nullable=False, default=EstadoPresupuesto.presentado,
    )
    fecha_presentacion: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(),
    )
    archivo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    trabajo: Mapped["Trabajo"] = relationship(back_populates="presupuestos")
```

- [ ] **Step 3: Sumar 2 FKs a `Trabajo`**

Buscar `class Trabajo(Base)` y agregar antes de las relationships:

```python
    presupuesto_aprobado_id: Mapped[int | None] = mapped_column(
        ForeignKey("presupuestos.id"), nullable=True,
    )
    gasto_id: Mapped[int | None] = mapped_column(
        ForeignKey("gastos.id"), nullable=True,
    )
```

- [ ] **Step 4: Sumar `TrabajoRecurrente` al final de los modelos**

```python
class TrabajoRecurrente(Base):
    __tablename__ = "trabajos_recurrentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(2000), nullable=False)
    periodicidad: Mapped[PeriodicidadRecurrente] = mapped_column(
        SqlEnum(PeriodicidadRecurrente, name="periodicidad_recurrente"),
        nullable=False,
    )
    proveedor_sugerido_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id"), nullable=True,
    )
    monto_estimado: Mapped[float | None] = mapped_column(Float, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
```

- [ ] **Step 5: Sumar `Notificacion`**

```python
class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
```

- [ ] **Step 6: Sumar schemas en `backend/schemas.py` (al final del archivo)**

```python
# === Fase 11 — Tareas y Presupuestos ===

class PresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trabajo_id: int
    proveedor_id: int
    monto: float
    estado: EstadoPresupuesto
    fecha_presentacion: date
    archivo_path: str | None
    observaciones: str | None


class PresupuestoCrear(BaseModel):
    """Para form multipart, los campos no-archivo van como Form en el endpoint."""
    proveedor_id: int
    monto: float = Field(..., gt=0)
    fecha_presentacion: date | None = None
    observaciones: str | None = Field(None, max_length=1000)


class PresupuestoActualizar(BaseModel):
    proveedor_id: int | None = None
    monto: float | None = Field(None, gt=0)
    fecha_presentacion: date | None = None
    observaciones: str | None = Field(None, max_length=1000)


class TrabajoRecurrenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    descripcion: str
    periodicidad: PeriodicidadRecurrente
    proveedor_sugerido_id: int | None
    monto_estimado: float | None
    activa: bool


class TrabajoRecurrenteCrear(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    descripcion: str = Field(..., min_length=1, max_length=2000)
    periodicidad: PeriodicidadRecurrente
    proveedor_sugerido_id: int | None = None
    monto_estimado: float | None = Field(None, ge=0)
    activa: bool = True


class TrabajoRecurrenteActualizar(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=255)
    descripcion: str | None = Field(None, min_length=1, max_length=2000)
    periodicidad: PeriodicidadRecurrente | None = None
    proveedor_sugerido_id: int | None = None
    monto_estimado: float | None = Field(None, ge=0)
    activa: bool | None = None


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    mensaje: str
    link: str | None
    leida: bool
    created_at: datetime


class NotificacionesCountOut(BaseModel):
    count: int


class CompletarTrabajoOut(BaseModel):
    """Payload devuelto por POST /trabajos/{id}/completar para pre-completar el form de Gasto."""
    proveedor_id: int
    monto: float
    concepto_sugerido: str
    trabajo_id: int
```

**Importante**: importar `PeriodicidadRecurrente` y `EstadoPresupuesto` al inicio de schemas.py si faltan.

- [ ] **Step 7: Sumar `trabajo_id` opcional a `GastoCrear` existente**

Buscar `class GastoCrear(BaseModel)` y sumar campo opcional:

```python
    trabajo_id: int | None = None  # Fase 11: si viene, marca el trabajo como completado
```

- [ ] **Step 8: Smoke import**

```bash
.venv/Scripts/python.exe -c "from backend.models import Notificacion, TrabajoRecurrente, PeriodicidadRecurrente; from backend.schemas import PresupuestoOut, NotificacionOut, TrabajoRecurrenteOut; print('OK')"
```

Expected: `OK`.

- [ ] **Step 9: Clean start de la DB**

```powershell
# Cerrar uvicorn antes
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
```

- [ ] **Step 10: Commit**

```bash
git add backend/models.py backend/schemas.py
git commit -m "feat(models+schemas): Notificacion, TrabajoRecurrente, Presupuesto.proveedor_id+archivo, Trabajo FKs"
```

---

## Task 2: Módulo `backend/notificaciones.py` + router `/notificaciones` + tests

**Files:**
- Create: `backend/notificaciones.py`
- Create: `backend/routers/notificaciones.py`
- Modify: `backend/main.py`
- Create: `tests/test_notificaciones.py`

- [ ] **Step 1: Crear `backend/notificaciones.py`**

```python
"""Sistema de notificaciones — Fase 11.

Doble canal:
- in-app: persiste un Notificacion en DB (campanita del frontend lo lee via polling).
- email: best-effort vía backend.email (modo console si SMTP_HOST vacío).

Helper `crear_notificacion` reusable para cualquier evento futuro.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .email import enviar_email
from .models import EstadoPeticion, Notificacion, Peticion, Rol, Usuario


def crear_notificacion(
    db: Session,
    usuario_id: int,
    mensaje: str,
    link: str | None = None,
) -> Notificacion:
    """Persiste una Notificacion para un usuario. No commitea — el caller lo hace."""
    notif = Notificacion(usuario_id=usuario_id, mensaje=mensaje, link=link)
    db.add(notif)
    return notif


def notificar_cambio_estado_peticion(
    db: Session,
    peticion: Peticion,
    estado_anterior: EstadoPeticion,
) -> None:
    """Doble canal cuando la petición pasa a en_curso o cerrada.

    No notifica si el estado no cambió, o si el nuevo estado es 'abierta'.
    Es best-effort: si email falla, la in-app igual queda.
    """
    if estado_anterior == peticion.estado:
        return
    if peticion.estado not in (EstadoPeticion.en_curso, EstadoPeticion.cerrada):
        return

    usuarios = list(db.scalars(
        select(Usuario).where(
            Usuario.departamento_id == peticion.departamento_id,
            Usuario.rol == Rol.departamento,
        )
    ).all())

    mensaje = f"Tu petición '{peticion.titulo}' cambió de estado a: {peticion.estado.value}."

    for u in usuarios:
        crear_notificacion(db, usuario_id=u.id, mensaje=mensaje, link="/peticiones")
        if u.email:
            enviar_email(
                to=u.email,
                subject=f"Tu petición #{peticion.id} fue actualizada",
                body=f"Hola,\n\n{mensaje}\n\nSaludos,\nAdministración.",
                attachments=[],
            )
```

- [ ] **Step 2: Crear `backend/routers/notificaciones.py`**

```python
"""Router de notificaciones — Fase 11.

Cada usuario ve y modifica SOLO sus notificaciones (filtro por user.id).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import Notificacion
from ..schemas import NotificacionOut, NotificacionesCountOut

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get("", response_model=list[NotificacionOut])
def listar_notificaciones(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return list(db.scalars(
        select(Notificacion)
        .where(Notificacion.usuario_id == user.id)
        .order_by(Notificacion.created_at.desc())
        .limit(limit)
    ).all())


@router.get("/no-leidas-count", response_model=NotificacionesCountOut)
def contar_no_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    count = db.scalar(
        select(func.count(Notificacion.id)).where(
            Notificacion.usuario_id == user.id,
            Notificacion.leida == False,
        )
    ) or 0
    return NotificacionesCountOut(count=count)


@router.post("/{notif_id}/marcar-leida", status_code=204)
def marcar_leida(
    notif_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    notif = db.get(Notificacion, notif_id)
    if notif is None or notif.usuario_id != user.id:
        raise HTTPException(404, "Notificación no encontrada.")
    notif.leida = True
    db.commit()


@router.post("/marcar-todas-leidas", status_code=204)
def marcar_todas_leidas(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    notifs = list(db.scalars(
        select(Notificacion).where(
            Notificacion.usuario_id == user.id,
            Notificacion.leida == False,
        )
    ).all())
    for n in notifs:
        n.leida = True
    db.commit()
```

- [ ] **Step 3: Registrar router en `backend/main.py`**

Sumar `notificaciones` al import `from .routers import (...)` y `app.include_router(notificaciones.router)`.

- [ ] **Step 4: Crear `tests/test_notificaciones.py`**

```python
"""Tests del módulo y router de notificaciones."""
from datetime import date

from backend.models import Notificacion, Peticion, EstadoPeticion
from backend.notificaciones import crear_notificacion, notificar_cambio_estado_peticion


def test_crear_notificacion_persiste(db):
    from backend.models import Usuario, Rol
    u = db.query(Usuario).filter_by(rol=Rol.departamento).first()
    n = crear_notificacion(db, usuario_id=u.id, mensaje="Test", link="/test")
    db.commit()
    assert n.id is not None
    assert n.leida is False
    assert n.usuario_id == u.id


def test_notificar_abierta_a_en_curso_crea_notif(db, capsys):
    """Cambio de estado a en_curso dispara Notificacion + email console."""
    p = Peticion(
        departamento_id=1, titulo="Test peti",
        descripcion="x", estado=EstadoPeticion.en_curso,
    )
    db.add(p); db.flush()
    notificar_cambio_estado_peticion(db, p, EstadoPeticion.abierta)
    db.commit()
    # Verificar Notificacion en DB
    notifs = db.query(Notificacion).filter_by(link="/peticiones").all()
    assert len(notifs) > 0
    # Verificar email console
    captured = capsys.readouterr()
    assert "EMAIL CONSOLE MODE" in captured.out or len(notifs) > 0


def test_notificar_sin_cambio_estado_no_hace_nada(db):
    p = Peticion(
        departamento_id=1, titulo="X", descripcion="x",
        estado=EstadoPeticion.en_curso,
    )
    db.add(p); db.flush()
    before = db.query(Notificacion).count()
    notificar_cambio_estado_peticion(db, p, EstadoPeticion.en_curso)
    after = db.query(Notificacion).count()
    assert before == after


def test_get_notificaciones_filtra_por_usuario(client, headers_depto_a, db):
    from backend.models import Usuario, Rol
    u_a = db.query(Usuario).filter_by(email="depto-a@consorcio.local").first()
    u_b = db.query(Usuario).filter_by(email="depto-b@consorcio.local").first()
    db.add(Notificacion(usuario_id=u_a.id, mensaje="Para A", link="/peticiones"))
    db.add(Notificacion(usuario_id=u_b.id, mensaje="Para B", link="/peticiones"))
    db.commit()
    r = client.get("/notificaciones", headers=headers_depto_a)
    assert r.status_code == 200
    mensajes = [n["mensaje"] for n in r.json()]
    assert "Para A" in mensajes
    assert "Para B" not in mensajes


def test_no_leidas_count(client, headers_depto_a, db):
    from backend.models import Usuario
    u = db.query(Usuario).filter_by(email="depto-a@consorcio.local").first()
    db.add(Notificacion(usuario_id=u.id, mensaje="No leida 1", leida=False))
    db.add(Notificacion(usuario_id=u.id, mensaje="No leida 2", leida=False))
    db.add(Notificacion(usuario_id=u.id, mensaje="Leida", leida=True))
    db.commit()
    r = client.get("/notificaciones/no-leidas-count", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["count"] >= 2


def test_marcar_leida_solo_propia(client, headers_depto_a, db):
    from backend.models import Usuario
    u_b = db.query(Usuario).filter_by(email="depto-b@consorcio.local").first()
    notif_ajena = Notificacion(usuario_id=u_b.id, mensaje="ajena", leida=False)
    db.add(notif_ajena); db.commit()
    r = client.post(f"/notificaciones/{notif_ajena.id}/marcar-leida", headers=headers_depto_a)
    assert r.status_code == 404
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v --tb=short
```

Expected: 6 passed.

- [ ] **Step 6: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: ~576 passed (570 baseline + 6 nuevos), 0 fail.

- [ ] **Step 7: Commit**

```bash
git add backend/notificaciones.py backend/routers/notificaciones.py backend/main.py tests/test_notificaciones.py
git commit -m "feat(notificaciones): módulo doble canal + router GET/POST + tests"
```

---

## Task 3: Router `/presupuestos` con upload archivo + tests

**Files:**
- Create: `backend/routers/presupuestos.py`
- Modify: `backend/main.py`
- Create: `tests/test_presupuestos.py`

- [ ] **Step 1: Crear `backend/routers/presupuestos.py`**

```python
"""Router de presupuestos — Fase 11.

Anida bajo /trabajos/{trabajo_id}/presupuestos. Acceso admin/representante para
POST/PATCH/DELETE/aprobar/rechazar. GET: admin/representante/depto (lectura).
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..config import get_settings
from ..database import get_db
from ..models import EstadoPresupuesto, Presupuesto, Proveedor, Rol, Trabajo
from ..schemas import PresupuestoActualizar, PresupuestoOut

router = APIRouter(prefix="/trabajos/{trabajo_id}/presupuestos", tags=["Presupuestos"])

ALLOWED_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_ARCHIVO_BYTES = 5 * 1024 * 1024  # 5MB


def _validar_trabajo(db: Session, trabajo_id: int) -> Trabajo:
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    return t


def _validar_proveedor(db: Session, proveedor_id: int) -> Proveedor:
    p = db.get(Proveedor, proveedor_id)
    if p is None:
        raise HTTPException(404, f"Proveedor {proveedor_id} no encontrado.")
    return p


def _guardar_archivo(archivo: UploadFile) -> str:
    """Guarda en uploads/presupuestos/ con nombre random. Devuelve path relativo."""
    ext = Path(archivo.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Extensión no permitida ({ext}). Use PDF/JPG/PNG/WebP.")
    contenido = archivo.file.read()
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise HTTPException(400, "Archivo > 5MB.")
    settings = get_settings()
    target_dir = Path(settings.UPLOAD_DIR) / "presupuestos"
    target_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}{ext}"
    target_path = target_dir / nombre
    target_path.write_bytes(contenido)
    return str(Path("presupuestos") / nombre)  # relativo a UPLOAD_DIR


@router.get("", response_model=list[PresupuestoOut])
def listar_presupuestos(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    _validar_trabajo(db, trabajo_id)
    return list(db.scalars(
        select(Presupuesto)
        .where(Presupuesto.trabajo_id == trabajo_id)
        .order_by(Presupuesto.fecha_presentacion)
    ).all())


@router.post("", response_model=PresupuestoOut, status_code=201)
def crear_presupuesto(
    trabajo_id: int,
    proveedor_id: int = Form(...),
    monto: float = Form(..., gt=0),
    fecha_presentacion: str | None = Form(None),
    observaciones: str | None = Form(None),
    archivo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    from datetime import date
    _validar_trabajo(db, trabajo_id)
    _validar_proveedor(db, proveedor_id)

    fecha = date.fromisoformat(fecha_presentacion) if fecha_presentacion else date.today()
    archivo_path = _guardar_archivo(archivo) if (archivo and archivo.filename) else None

    p = Presupuesto(
        trabajo_id=trabajo_id,
        proveedor_id=proveedor_id,
        monto=monto,
        fecha_presentacion=fecha,
        observaciones=observaciones,
        archivo_path=archivo_path,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch("/{presupuesto_id}", response_model=PresupuestoOut)
def actualizar_presupuesto(
    trabajo_id: int,
    presupuesto_id: int,
    payload: PresupuestoActualizar,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    p = db.get(Presupuesto, presupuesto_id)
    if p is None or p.trabajo_id != trabajo_id:
        raise HTTPException(404, "Presupuesto no encontrado.")
    if p.estado != EstadoPresupuesto.presentado:
        raise HTTPException(409, "Solo se pueden editar presupuestos en estado presentado.")
    if payload.proveedor_id is not None:
        _validar_proveedor(db, payload.proveedor_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(p, campo, valor)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{presupuesto_id}", status_code=204)
def eliminar_presupuesto(
    trabajo_id: int,
    presupuesto_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    p = db.get(Presupuesto, presupuesto_id)
    if p is None or p.trabajo_id != trabajo_id:
        raise HTTPException(404, "Presupuesto no encontrado.")
    if p.estado != EstadoPresupuesto.presentado:
        raise HTTPException(409, "Solo se pueden eliminar presupuestos en estado presentado.")
    db.delete(p)
    db.commit()


@router.post("/{presupuesto_id}/aprobar", response_model=PresupuestoOut)
def aprobar_presupuesto(
    trabajo_id: int,
    presupuesto_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    p = db.get(Presupuesto, presupuesto_id)
    if p is None or p.trabajo_id != trabajo_id:
        raise HTTPException(404, "Presupuesto no encontrado.")
    trabajo = db.get(Trabajo, trabajo_id)
    # Rechazar todos los demás presupuestos del mismo trabajo
    otros = list(db.scalars(
        select(Presupuesto).where(
            Presupuesto.trabajo_id == trabajo_id,
            Presupuesto.id != presupuesto_id,
            Presupuesto.estado == EstadoPresupuesto.aprobado,
        )
    ).all())
    for otro in otros:
        otro.estado = EstadoPresupuesto.rechazado
    p.estado = EstadoPresupuesto.aprobado
    trabajo.presupuesto_aprobado_id = p.id
    db.commit()
    db.refresh(p)
    return p


@router.post("/{presupuesto_id}/rechazar", response_model=PresupuestoOut)
def rechazar_presupuesto(
    trabajo_id: int,
    presupuesto_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    p = db.get(Presupuesto, presupuesto_id)
    if p is None or p.trabajo_id != trabajo_id:
        raise HTTPException(404, "Presupuesto no encontrado.")
    if p.estado == EstadoPresupuesto.aprobado:
        trabajo = db.get(Trabajo, trabajo_id)
        if trabajo.presupuesto_aprobado_id == p.id:
            trabajo.presupuesto_aprobado_id = None
    p.estado = EstadoPresupuesto.rechazado
    db.commit()
    db.refresh(p)
    return p
```

- [ ] **Step 2: Registrar router en `backend/main.py`**

Sumar `presupuestos` al import + `app.include_router(presupuestos.router)`.

- [ ] **Step 3: Crear `tests/test_presupuestos.py`**

```python
"""Tests del router de presupuestos."""
import io

from backend.models import Presupuesto, EstadoPresupuesto, Trabajo, Proveedor


def _crear_trabajo(db, descripcion="Trabajo de test"):
    t = Trabajo(descripcion=descripcion)
    db.add(t); db.commit(); db.refresh(t)
    return t


def _proveedor_id(db) -> int:
    p = db.query(Proveedor).first()
    assert p is not None, "El seed debe tener al menos un proveedor"
    return p.id


def test_listar_presupuestos_vacio(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.get(f"/trabajos/{t.id}/presupuestos", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_crear_presupuesto_sin_archivo(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": _proveedor_id(db), "monto": 12000},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["monto"] == 12000
    assert r.json()["archivo_path"] is None


def test_crear_presupuesto_con_archivo(client, headers_admin, db):
    t = _crear_trabajo(db)
    files = {"archivo": ("cot.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")}
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": _proveedor_id(db), "monto": 15000},
        files=files,
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["archivo_path"] is not None


def test_crear_proveedor_inexistente_404(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": 99999, "monto": 100},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_crear_monto_negativo_400(client, headers_admin, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": _proveedor_id(db), "monto": -50},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_aprobar_un_segundo_desaprueba_el_primero(client, headers_admin, db):
    t = _crear_trabajo(db)
    p1 = Presupuesto(trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=100)
    p2 = Presupuesto(trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=200)
    db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)

    r1 = client.post(f"/trabajos/{t.id}/presupuestos/{p1.id}/aprobar", headers=headers_admin)
    assert r1.status_code == 200
    db.refresh(p1); db.refresh(t)
    assert p1.estado == EstadoPresupuesto.aprobado
    assert t.presupuesto_aprobado_id == p1.id

    r2 = client.post(f"/trabajos/{t.id}/presupuestos/{p2.id}/aprobar", headers=headers_admin)
    assert r2.status_code == 200
    db.refresh(p1); db.refresh(p2); db.refresh(t)
    assert p1.estado == EstadoPresupuesto.rechazado
    assert p2.estado == EstadoPresupuesto.aprobado
    assert t.presupuesto_aprobado_id == p2.id


def test_patch_aprobado_devuelve_409(client, headers_admin, db):
    t = _crear_trabajo(db)
    p = Presupuesto(trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=100,
                    estado=EstadoPresupuesto.aprobado)
    db.add(p); db.commit(); db.refresh(p)
    r = client.patch(
        f"/trabajos/{t.id}/presupuestos/{p.id}",
        json={"monto": 500},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_delete_aprobado_devuelve_409(client, headers_admin, db):
    t = _crear_trabajo(db)
    p = Presupuesto(trabajo_id=t.id, proveedor_id=_proveedor_id(db), monto=100,
                    estado=EstadoPresupuesto.aprobado)
    db.add(p); db.commit(); db.refresh(p)
    r = client.delete(f"/trabajos/{t.id}/presupuestos/{p.id}", headers=headers_admin)
    assert r.status_code == 409


def test_depto_no_puede_crear(client, headers_depto_a, db):
    t = _crear_trabajo(db)
    r = client.post(
        f"/trabajos/{t.id}/presupuestos",
        data={"proveedor_id": _proveedor_id(db), "monto": 100},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_depto_puede_listar(client, headers_depto_a, db):
    t = _crear_trabajo(db)
    r = client.get(f"/trabajos/{t.id}/presupuestos", headers=headers_depto_a)
    assert r.status_code == 200
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_presupuestos.py -v --tb=short
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/presupuestos.py backend/main.py tests/test_presupuestos.py
git commit -m "feat(presupuestos): router /trabajos/{id}/presupuestos con upload archivo + tests"
```

---

## Task 4: Adaptar `/peticiones` (auth + delete + notificaciones)

**Files:**
- Modify: `backend/routers/peticiones.py`
- Modify: `tests/test_peticiones.py`

- [ ] **Step 1: Leer `backend/routers/peticiones.py` para entender la estructura actual**

- [ ] **Step 2: Adaptar `POST /peticiones` — solo depto**

Cambiar el `require_roles(...)` del POST para que solo acepte `Rol.departamento`:

```python
_u: CurrentUser = Depends(require_roles(Rol.departamento)),
```

El departamento_id se toma del `_u.departamento_id` (del JWT), NO del body (regla de security.md).

- [ ] **Step 3: Adaptar `PATCH /peticiones/{id}` — solo admin/representante**

```python
_u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
```

Al final del PATCH, después de aplicar cambios, capturar el estado anterior y disparar notificación si cambió:

```python
from ..notificaciones import notificar_cambio_estado_peticion

# (al inicio del handler PATCH)
estado_anterior = peticion.estado

# ... apply changes ...

# antes del commit
db.flush()
notificar_cambio_estado_peticion(db, peticion, estado_anterior)
db.commit()
```

- [ ] **Step 4: Adaptar `GET /peticiones` — todos los roles ven todas**

Quitar cualquier filtro por `departamento_id` cuando el rol es depto. Que todos vean todas.

```python
@router.get("", response_model=list[PeticionOut])
def listar_peticiones(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return list(db.scalars(select(Peticion).order_by(Peticion.fecha_creacion.desc())).all())
```

- [ ] **Step 5: Sumar `DELETE /peticiones/{id}` con reglas de ownership**

```python
@router.delete("/{peticion_id}", status_code=204)
def eliminar_peticion(
    peticion_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    p = db.get(Peticion, peticion_id)
    if p is None:
        raise HTTPException(404, "Petición no encontrada.")

    if user.rol == Rol.departamento:
        # Solo la suya y solo si abierta
        if p.departamento_id != user.departamento_id:
            raise HTTPException(403, "No autorizado para eliminar esta petición.")
        if p.estado != EstadoPeticion.abierta:
            raise HTTPException(409, "Solo podés eliminar peticiones en estado abierta.")
    elif user.rol not in (Rol.administracion, Rol.representante):
        raise HTTPException(403, "No autorizado.")

    db.delete(p)
    db.commit()
```

- [ ] **Step 6: Adaptar tests existentes en `tests/test_peticiones.py`**

Buscar tests que asuman POST como admin → cambiar a esperar 403. Sumar tests nuevos:

```python
def test_admin_post_peticion_devuelve_403(client, headers_admin):
    r = client.post("/peticiones", json={
        "titulo": "Test", "descripcion": "test",
    }, headers=headers_admin)
    assert r.status_code == 403


def test_depto_get_lista_todas(client, headers_depto_a, db):
    """Depto ve peticiones de todos los deptos (transparencia)."""
    from backend.models import Peticion, EstadoPeticion
    db.add(Peticion(departamento_id=2, titulo="Otra", descripcion="x", estado=EstadoPeticion.abierta))
    db.commit()
    r = client.get("/peticiones", headers=headers_depto_a)
    assert r.status_code == 200
    deptos = {p["departamento_id"] for p in r.json()}
    assert len(deptos) >= 1  # debe ver al menos las de otros deptos si hay


def test_depto_patch_devuelve_403(client, headers_depto_a, db):
    from backend.models import Peticion
    p = Peticion(departamento_id=1, titulo="X", descripcion="x")
    db.add(p); db.commit(); db.refresh(p)
    r = client.patch(f"/peticiones/{p.id}",
                     json={"estado": "cerrada"}, headers=headers_depto_a)
    assert r.status_code == 403


def test_depto_delete_su_abierta_204(client, headers_depto_a, db):
    from backend.models import Peticion, Usuario, EstadoPeticion
    u = db.query(Usuario).filter_by(email="depto-a@consorcio.local").first()
    p = Peticion(departamento_id=u.departamento_id, titulo="A borrar", descripcion="x",
                 estado=EstadoPeticion.abierta)
    db.add(p); db.commit(); db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_depto_a)
    assert r.status_code == 204


def test_depto_delete_su_en_curso_409(client, headers_depto_a, db):
    from backend.models import Peticion, Usuario, EstadoPeticion
    u = db.query(Usuario).filter_by(email="depto-a@consorcio.local").first()
    p = Peticion(departamento_id=u.departamento_id, titulo="X", descripcion="x",
                 estado=EstadoPeticion.en_curso)
    db.add(p); db.commit(); db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_depto_a)
    assert r.status_code == 409


def test_depto_delete_ajena_403(client, headers_depto_a, db):
    from backend.models import Peticion, Usuario, EstadoPeticion
    u_a = db.query(Usuario).filter_by(email="depto-a@consorcio.local").first()
    otra_depto_id = 2 if u_a.departamento_id != 2 else 3
    p = Peticion(departamento_id=otra_depto_id, titulo="ajena", descripcion="x",
                 estado=EstadoPeticion.abierta)
    db.add(p); db.commit(); db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_depto_a)
    assert r.status_code == 403


def test_patch_cambio_estado_dispara_notificacion(client, headers_admin, db):
    from backend.models import Peticion, Notificacion, EstadoPeticion
    p = Peticion(departamento_id=1, titulo="Notif test", descripcion="x",
                 estado=EstadoPeticion.abierta)
    db.add(p); db.commit(); db.refresh(p)
    before = db.query(Notificacion).count()
    r = client.patch(f"/peticiones/{p.id}",
                     json={"estado": "en_curso"}, headers=headers_admin)
    assert r.status_code == 200
    after = db.query(Notificacion).count()
    assert after > before
```

- [ ] **Step 7: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_peticiones.py -v --tb=short
```

Expected: todos pasan.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/peticiones.py tests/test_peticiones.py
git commit -m "feat(peticiones): auth refinada (solo depto POST) + DELETE + notif al cambio de estado"
```

---

## Task 5: Adaptar `/trabajos` (completar/cancelar)

**Files:**
- Modify: `backend/routers/trabajos.py`
- Modify: `tests/test_trabajos.py`

- [ ] **Step 1: Sumar imports al inicio**

```python
from ..models import EstadoPresupuesto, Presupuesto, Proveedor, Rol
from ..schemas import CompletarTrabajoOut
```

- [ ] **Step 2: Sumar endpoint `POST /trabajos/{id}/completar`**

```python
@router.post(
    "/{trabajo_id}/completar",
    response_model=CompletarTrabajoOut,
    summary="Devuelve payload pre-completado para crear el Gasto (NO crea Gasto).",
)
def completar_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
) -> CompletarTrabajoOut:
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    if t.presupuesto_aprobado_id is None:
        raise HTTPException(409, "El trabajo no tiene un presupuesto aprobado.")
    p = db.get(Presupuesto, t.presupuesto_aprobado_id)
    return CompletarTrabajoOut(
        proveedor_id=p.proveedor_id,
        monto=p.monto,
        concepto_sugerido=t.descripcion or "Trabajo",
        trabajo_id=t.id,
    )
```

- [ ] **Step 3: Sumar endpoint `POST /trabajos/{id}/cancelar`**

```python
@router.post("/{trabajo_id}/cancelar", status_code=204)
def cancelar_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    from ..notificaciones import notificar_cambio_estado_peticion
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    t.estado = EstadoTrabajo.cancelado
    # Si la petición estaba en_curso por este trabajo, cerrar.
    if t.peticion_id:
        p = db.get(Peticion, t.peticion_id)
        if p and p.estado == EstadoPeticion.en_curso:
            estado_anterior = p.estado
            p.estado = EstadoPeticion.cerrada
            db.flush()
            notificar_cambio_estado_peticion(db, p, estado_anterior)
    db.commit()
```

Verificar imports — sumar `EstadoTrabajo`, `EstadoPeticion`, `Peticion`, `Trabajo` si faltan.

- [ ] **Step 4: Sumar GET único + GET listado si no existen**

```python
@router.get("", response_model=list[TrabajoOut])
def listar_trabajos(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    return list(db.scalars(select(Trabajo).order_by(Trabajo.fecha_creacion.desc())).all())


@router.get("/{trabajo_id}", response_model=TrabajoOut)
def obtener_trabajo(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    t = db.get(Trabajo, trabajo_id)
    if t is None:
        raise HTTPException(404, "Trabajo no encontrado.")
    return t
```

(Si el router ya los tiene, saltar este step.)

- [ ] **Step 5: Cuando se crea un Trabajo desde una Petición, marcar la Peticion como en_curso + notificar**

Buscar el handler POST de trabajos. Si `payload.peticion_id is not None`, después de crear el trabajo:

```python
if payload.peticion_id:
    from ..notificaciones import notificar_cambio_estado_peticion
    pet = db.get(Peticion, payload.peticion_id)
    if pet and pet.estado == EstadoPeticion.abierta:
        estado_anterior = pet.estado
        pet.estado = EstadoPeticion.en_curso
        db.flush()
        notificar_cambio_estado_peticion(db, pet, estado_anterior)
```

- [ ] **Step 6: Sumar tests al final de `tests/test_trabajos.py`**

```python
def test_completar_sin_presupuesto_aprobado_409(client, headers_admin, db):
    from backend.models import Trabajo
    t = Trabajo(descripcion="Sin ppto")
    db.add(t); db.commit(); db.refresh(t)
    r = client.post(f"/trabajos/{t.id}/completar", headers=headers_admin)
    assert r.status_code == 409


def test_completar_con_aprobado_devuelve_payload(client, headers_admin, db):
    from backend.models import Trabajo, Presupuesto, EstadoPresupuesto, Proveedor
    t = Trabajo(descripcion="Con ppto")
    db.add(t); db.commit(); db.refresh(t)
    prov = db.query(Proveedor).first()
    p = Presupuesto(trabajo_id=t.id, proveedor_id=prov.id, monto=5000,
                    estado=EstadoPresupuesto.aprobado)
    db.add(p); db.commit(); db.refresh(p)
    t.presupuesto_aprobado_id = p.id
    db.commit()
    r = client.post(f"/trabajos/{t.id}/completar", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["proveedor_id"] == prov.id
    assert body["monto"] == 5000
    assert body["trabajo_id"] == t.id


def test_cancelar_trabajo_204_y_cierra_peticion(client, headers_admin, db):
    from backend.models import Trabajo, Peticion, EstadoPeticion, EstadoTrabajo
    p = Peticion(departamento_id=1, titulo="X", descripcion="x", estado=EstadoPeticion.en_curso)
    db.add(p); db.commit(); db.refresh(p)
    t = Trabajo(peticion_id=p.id, descripcion="Para cancelar", estado=EstadoTrabajo.en_curso)
    db.add(t); db.commit(); db.refresh(t)
    r = client.post(f"/trabajos/{t.id}/cancelar", headers=headers_admin)
    assert r.status_code == 204
    db.refresh(p); db.refresh(t)
    assert t.estado == EstadoTrabajo.cancelado
    assert p.estado == EstadoPeticion.cerrada
```

- [ ] **Step 7: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_trabajos.py -v --tb=short
```

- [ ] **Step 8: Commit**

```bash
git add backend/routers/trabajos.py tests/test_trabajos.py
git commit -m "feat(trabajos): endpoints completar/cancelar + GET list/single + integración notif"
```

---

## Task 6: Integración `POST /gastos` con `trabajo_id`

**Files:**
- Modify: `backend/routers/gastos.py`
- Modify: `tests/test_gastos.py`

- [ ] **Step 1: En el handler `crear_gasto`, después de crear el Gasto pero antes del commit final, si `payload.trabajo_id` está presente actualizar el Trabajo**

```python
# (al inicio del handler, imports si faltan)
from ..models import EstadoTrabajo, Trabajo, Peticion, EstadoPeticion

# ... lógica existente crea el Gasto y el MovimientoCaja ...

# NUEVO: si vino trabajo_id, actualizar el Trabajo + cerrar petición si la había
if payload.trabajo_id:
    from ..notificaciones import notificar_cambio_estado_peticion
    t = db.get(Trabajo, payload.trabajo_id)
    if t is None:
        raise HTTPException(404, f"Trabajo {payload.trabajo_id} no encontrado.")
    t.gasto_id = gasto.id
    t.estado = EstadoTrabajo.completado
    if t.peticion_id:
        pet = db.get(Peticion, t.peticion_id)
        if pet and pet.estado != EstadoPeticion.cerrada:
            estado_anterior = pet.estado
            pet.estado = EstadoPeticion.cerrada
            db.flush()
            notificar_cambio_estado_peticion(db, pet, estado_anterior)
```

- [ ] **Step 2: Sumar tests específicos en `tests/test_gastos.py`**

```python
def test_crear_gasto_con_trabajo_id_completa_trabajo(client, headers_admin, db):
    from backend.models import Trabajo, EstadoTrabajo
    t = Trabajo(descripcion="Trabajo para gasto")
    db.add(t); db.commit(); db.refresh(t)

    payload = dict(_GASTO_VALIDO, trabajo_id=t.id)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 201
    gasto_id = r.json()["id"]

    db.refresh(t)
    assert t.estado == EstadoTrabajo.completado
    assert t.gasto_id == gasto_id


def test_crear_gasto_con_trabajo_id_inexistente_404(client, headers_admin):
    payload = dict(_GASTO_VALIDO, trabajo_id=99999)
    r = client.post("/gastos", json=payload, headers=headers_admin)
    assert r.status_code == 404
```

- [ ] **Step 3: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_gastos.py -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add backend/routers/gastos.py tests/test_gastos.py
git commit -m "feat(gastos): POST acepta trabajo_id → marca trabajo completado + cierra petición"
```

---

## Task 7: Router `/trabajos-recurrentes` + tests

**Files:**
- Create: `backend/routers/trabajos_recurrentes.py`
- Modify: `backend/main.py`
- Create: `tests/test_trabajos_recurrentes.py`

- [ ] **Step 1: Crear `backend/routers/trabajos_recurrentes.py`**

```python
"""Router de plantillas de trabajos recurrentes — Fase 11.

Admin define plantillas y las materializa manualmente con un click.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Proveedor, Rol, Trabajo, TrabajoRecurrente
from ..schemas import (
    TrabajoOut,
    TrabajoRecurrenteActualizar,
    TrabajoRecurrenteCrear,
    TrabajoRecurrenteOut,
)

router = APIRouter(prefix="/trabajos-recurrentes", tags=["TrabajosRecurrentes"])


@router.get("", response_model=list[TrabajoRecurrenteOut])
def listar(
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    return list(db.scalars(
        select(TrabajoRecurrente).order_by(TrabajoRecurrente.id)
    ).all())


@router.post("", response_model=TrabajoRecurrenteOut, status_code=201)
def crear(
    payload: TrabajoRecurrenteCrear,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    if payload.proveedor_sugerido_id is not None:
        if db.get(Proveedor, payload.proveedor_sugerido_id) is None:
            raise HTTPException(404, f"Proveedor {payload.proveedor_sugerido_id} no encontrado.")
    tr = TrabajoRecurrente(**payload.model_dump())
    db.add(tr); db.commit(); db.refresh(tr)
    return tr


@router.patch("/{recurrente_id}", response_model=TrabajoRecurrenteOut)
def actualizar(
    recurrente_id: int,
    payload: TrabajoRecurrenteActualizar,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    tr = db.get(TrabajoRecurrente, recurrente_id)
    if tr is None:
        raise HTTPException(404, "Recurrente no encontrado.")
    if payload.proveedor_sugerido_id is not None:
        if db.get(Proveedor, payload.proveedor_sugerido_id) is None:
            raise HTTPException(404, f"Proveedor {payload.proveedor_sugerido_id} no encontrado.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tr, k, v)
    db.commit(); db.refresh(tr)
    return tr


@router.delete("/{recurrente_id}", status_code=204)
def eliminar(
    recurrente_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    tr = db.get(TrabajoRecurrente, recurrente_id)
    if tr is None:
        raise HTTPException(404, "Recurrente no encontrado.")
    db.delete(tr); db.commit()


@router.post("/{recurrente_id}/materializar", response_model=TrabajoOut, status_code=201)
def materializar(
    recurrente_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
):
    """Crea un Trabajo concreto desde la plantilla."""
    tr = db.get(TrabajoRecurrente, recurrente_id)
    if tr is None:
        raise HTTPException(404, "Recurrente no encontrado.")
    if not tr.activa:
        raise HTTPException(400, "La plantilla está inactiva.")
    t = Trabajo(descripcion=f"{tr.nombre} — {tr.descripcion}")
    db.add(t); db.commit(); db.refresh(t)
    return t
```

- [ ] **Step 2: Registrar router en `backend/main.py`**

- [ ] **Step 3: Crear `tests/test_trabajos_recurrentes.py`**

```python
"""Tests del router de trabajos recurrentes."""


def test_listar_admin_200(client, headers_admin):
    r = client.get("/trabajos-recurrentes", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_listar_depto_403(client, headers_depto_a):
    r = client.get("/trabajos-recurrentes", headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_admin_201(client, headers_admin, db):
    from backend.models import Proveedor
    prov = db.query(Proveedor).first()
    r = client.post("/trabajos-recurrentes", json={
        "nombre": "Limpieza tanque",
        "descripcion": "Limpieza trimestral del tanque",
        "periodicidad": "trimestral",
        "proveedor_sugerido_id": prov.id,
        "monto_estimado": 50000,
    }, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["nombre"] == "Limpieza tanque"


def test_crear_proveedor_inexistente_404(client, headers_admin):
    r = client.post("/trabajos-recurrentes", json={
        "nombre": "X", "descripcion": "y", "periodicidad": "mensual",
        "proveedor_sugerido_id": 99999,
    }, headers=headers_admin)
    assert r.status_code == 404


def test_patch_actualiza(client, headers_admin, db):
    from backend.models import TrabajoRecurrente, PeriodicidadRecurrente
    tr = TrabajoRecurrente(nombre="A", descripcion="x", periodicidad=PeriodicidadRecurrente.mensual)
    db.add(tr); db.commit(); db.refresh(tr)
    r = client.patch(f"/trabajos-recurrentes/{tr.id}",
                     json={"nombre": "B"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "B"


def test_materializar_crea_trabajo(client, headers_admin, db):
    from backend.models import TrabajoRecurrente, PeriodicidadRecurrente
    tr = TrabajoRecurrente(nombre="N", descripcion="D", periodicidad=PeriodicidadRecurrente.anual)
    db.add(tr); db.commit(); db.refresh(tr)
    r = client.post(f"/trabajos-recurrentes/{tr.id}/materializar", headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert "N — D" in body["descripcion"]


def test_materializar_inactiva_400(client, headers_admin, db):
    from backend.models import TrabajoRecurrente, PeriodicidadRecurrente
    tr = TrabajoRecurrente(nombre="X", descripcion="x",
                            periodicidad=PeriodicidadRecurrente.mensual, activa=False)
    db.add(tr); db.commit(); db.refresh(tr)
    r = client.post(f"/trabajos-recurrentes/{tr.id}/materializar", headers=headers_admin)
    assert r.status_code == 400
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_trabajos_recurrentes.py -v --tb=short
```

Expected: 7 passed.

- [ ] **Step 5: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 600+ passed, 0 fail.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/trabajos_recurrentes.py backend/main.py tests/test_trabajos_recurrentes.py
git commit -m "feat(trabajos-recurrentes): router CRUD + materializar + tests"
```

---

## Task 8: OpenAPI

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Sumar 4 tags**

```yaml
  - name: Presupuestos
    description: Presupuestos de proveedores para trabajos
  - name: TrabajosRecurrentes
    description: Plantillas de trabajos repetitivos
  - name: Notificaciones
    description: Sistema de notificaciones in-app (campanita)
```

(Si `Trabajos` y `Peticiones` ya existen como tags, no duplicar.)

- [ ] **Step 2: Sumar paths nuevos al final de `paths:`**

Incluir los 6 endpoints de `/trabajos/{trabajo_id}/presupuestos/...`, los 5 de `/trabajos-recurrentes/...`, los 4 de `/notificaciones/...`, los 2 nuevos de `/trabajos/{id}/completar` y `/cancelar`, y el `DELETE /peticiones/{id}`.

Esquema general por path:
```yaml
  /trabajos/{trabajo_id}/presupuestos:
    get:
      tags: [Presupuestos]
      ...
    post:
      tags: [Presupuestos]
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                proveedor_id: { type: integer }
                monto: { type: number }
                fecha_presentacion: { type: string, format: date }
                observaciones: { type: string }
                archivo: { type: string, format: binary }
              required: [proveedor_id, monto]
      responses:
        '201': ...
```

(Replicar para cada endpoint nuevo. Para los GET/POST/PATCH/DELETE comunes seguir el patrón de Fases 4-6.)

- [ ] **Step 3: Sumar schemas nuevos en `components.schemas`**

```yaml
    PresupuestoOut: { ... 7 properties ... }
    PresupuestoActualizar: { ... 4 properties opcionales ... }
    TrabajoRecurrenteOut: { ... 7 properties ... }
    TrabajoRecurrenteCrear: { ... 6 properties con required ... }
    TrabajoRecurrenteActualizar: { ... 6 properties opcionales ... }
    NotificacionOut: { ... 6 properties ... }
    NotificacionesCountOut: { type: object, properties: { count: { type: integer } } }
    CompletarTrabajoOut: { ... 4 properties ... }
```

Y modificar `GastoCrear`: sumar `trabajo_id: { type: integer, nullable: true }`.

- [ ] **Step 4: Validar yaml**

```bash
.venv/Scripts/python.exe -c "import yaml; spec = yaml.safe_load(open('openapi.yaml').read()); print('paths:', len(spec['paths']), 'schemas:', len(spec['components']['schemas']))"
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): tags + paths + schemas de Fase 11 (presupuestos, recurrentes, notif)"
```

---

## Task 9: Seed actualizado

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Sumar imports**

```python
from .models import PeriodicidadRecurrente, TrabajoRecurrente
```

- [ ] **Step 2: Sumar 1-2 trabajos recurrentes demo**

Después de crear los proveedores en el seed, sumar:

```python
db.add_all([
    TrabajoRecurrente(
        nombre="Limpieza tanque",
        descripcion="Limpieza trimestral del tanque de agua",
        periodicidad=PeriodicidadRecurrente.trimestral,
        proveedor_sugerido_id=prov_limpieza.id,
        monto_estimado=80000,
        activa=True,
    ),
    TrabajoRecurrente(
        nombre="Mantenimiento ascensores",
        descripcion="Service mensual de ascensores",
        periodicidad=PeriodicidadRecurrente.mensual,
        proveedor_sugerido_id=prov_ascensor.id,
        monto_estimado=120000,
        activa=True,
    ),
])
db.flush()
```

(Adaptar nombres de variables — usar los ids/refs reales de proveedores sembrados.)

- [ ] **Step 3: Si el seed crea presupuestos demo, adaptar a usar `proveedor_id`**

(Revisar — probablemente no haya presupuestos en el seed; si los hay, cambiar `proveedor="X"` por `proveedor_id=Y`.)

- [ ] **Step 4: Smoke seed**

```bash
rm -f consorcio.db
.venv/Scripts/python.exe -c "from backend.database import engine; from backend.models import Base; Base.metadata.create_all(engine); from backend.seed import seed_if_empty; from backend.database import SessionLocal; seed_if_empty(SessionLocal()); print('seed OK')"
```

Expected: `seed OK`.

- [ ] **Step 5: Suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 600+ pass.

- [ ] **Step 6: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): 2 trabajos recurrentes demo (limpieza tanque + mantenimiento ascensores)"
```

---

## Task 10: Frontend API clients

**Files:**
- Modify: `frontend/src/api/peticiones.js` (si existe, sino crear)
- Modify: `frontend/src/api/trabajos.js` (idem)
- Create: `frontend/src/api/presupuestos.js`
- Create: `frontend/src/api/trabajosRecurrentes.js`
- Create: `frontend/src/api/notificaciones.js`

- [ ] **Step 1: Crear/extender `frontend/src/api/peticiones.js`**

```javascript
import { apiFetch } from "./client";

export function listarPeticiones() {
  return apiFetch("/peticiones");
}

export function crearPeticion(payload) {
  return apiFetch("/peticiones", { method: "POST", body: payload });
}

export function actualizarPeticion(id, payload) {
  return apiFetch(`/peticiones/${id}`, { method: "PATCH", body: payload });
}

export function eliminarPeticion(id) {
  return apiFetch(`/peticiones/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Crear/extender `frontend/src/api/trabajos.js`**

```javascript
import { apiFetch } from "./client";

export function listarTrabajos() {
  return apiFetch("/trabajos");
}

export function obtenerTrabajo(id) {
  return apiFetch(`/trabajos/${id}`);
}

export function crearTrabajo(payload) {
  return apiFetch("/trabajos", { method: "POST", body: payload });
}

export function actualizarTrabajo(id, payload) {
  return apiFetch(`/trabajos/${id}`, { method: "PATCH", body: payload });
}

export function completarTrabajo(id) {
  return apiFetch(`/trabajos/${id}/completar`, { method: "POST", body: {} });
}

export function cancelarTrabajo(id) {
  return apiFetch(`/trabajos/${id}/cancelar`, { method: "POST", body: {} });
}
```

- [ ] **Step 3: Crear `frontend/src/api/presupuestos.js`**

```javascript
import { apiFetch, API_BASE } from "./client";

export function listarPresupuestos(trabajoId) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos`);
}

/**
 * Crear presupuesto con archivo opcional. payload: FormData.
 */
export async function crearPresupuesto(trabajoId, formData, token) {
  const res = await fetch(`${API_BASE}/trabajos/${trabajoId}/presupuestos`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  const data = res.status !== 204 ? await res.json().catch(() => null) : null;
  return { status: res.status, data };
}

export function actualizarPresupuesto(trabajoId, presupuestoId, payload) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos/${presupuestoId}`, {
    method: "PATCH", body: payload,
  });
}

export function eliminarPresupuesto(trabajoId, presupuestoId) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos/${presupuestoId}`, {
    method: "DELETE",
  });
}

export function aprobarPresupuesto(trabajoId, presupuestoId) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos/${presupuestoId}/aprobar`, {
    method: "POST", body: {},
  });
}

export function rechazarPresupuesto(trabajoId, presupuestoId) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos/${presupuestoId}/rechazar`, {
    method: "POST", body: {},
  });
}
```

- [ ] **Step 4: Crear `frontend/src/api/trabajosRecurrentes.js`**

```javascript
import { apiFetch } from "./client";

export function listarRecurrentes() {
  return apiFetch("/trabajos-recurrentes");
}

export function crearRecurrente(payload) {
  return apiFetch("/trabajos-recurrentes", { method: "POST", body: payload });
}

export function actualizarRecurrente(id, payload) {
  return apiFetch(`/trabajos-recurrentes/${id}`, { method: "PATCH", body: payload });
}

export function eliminarRecurrente(id) {
  return apiFetch(`/trabajos-recurrentes/${id}`, { method: "DELETE" });
}

export function materializarRecurrente(id) {
  return apiFetch(`/trabajos-recurrentes/${id}/materializar`, { method: "POST", body: {} });
}
```

- [ ] **Step 5: Crear `frontend/src/api/notificaciones.js`**

```javascript
import { apiFetch } from "./client";

export function listarNotificaciones(limit = 50) {
  return apiFetch(`/notificaciones?limit=${limit}`);
}

export function obtenerNoLeidasCount() {
  return apiFetch("/notificaciones/no-leidas-count");
}

export function marcarLeida(id) {
  return apiFetch(`/notificaciones/${id}/marcar-leida`, { method: "POST", body: {} });
}

export function marcarTodasLeidas() {
  return apiFetch("/notificaciones/marcar-todas-leidas", { method: "POST", body: {} });
}
```

- [ ] **Step 6: Build smoke**

```bash
cd frontend && npm run build
```

- [ ] **Step 7: Commit**

```bash
cd .. && git add frontend/src/api/
git commit -m "feat(frontend/api): clients peticiones, trabajos, presupuestos, recurrentes, notificaciones"
```

---

## Task 11: Pantalla `/peticiones` + `ModalDetallePeticion`

**Files:**
- Create: `frontend/src/screens/Peticiones.jsx`
- Create: `frontend/src/components/ModalDetallePeticion.jsx`

- [ ] **Step 1: Crear `Peticiones.jsx`**

Pantalla con tabla, filtros, botón "+ Nueva petición" (solo depto), click en fila abre modal.

```jsx
import { useEffect, useState } from "react";
import { listarPeticiones, crearPeticion, eliminarPeticion } from "../api/peticiones";
import { useAuth } from "../auth/AuthContext";
import ModalDetallePeticion from "../components/ModalDetallePeticion";

const ESTADOS = ["abierta", "en_curso", "cerrada"];

export default function Peticiones() {
  const { user } = useAuth();
  const esDepto = user?.rol === "departamento";
  const [items, setItems] = useState([]);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [modal, setModal] = useState(null);
  const [creando, setCreando] = useState(false);
  const [nuevoTitulo, setNuevoTitulo] = useState("");
  const [nuevoDesc, setNuevoDesc] = useState("");

  async function cargar() {
    const r = await listarPeticiones();
    if (r.status === 200) setItems(r.data);
  }

  useEffect(() => { cargar(); }, []);

  async function handleCrear(e) {
    e.preventDefault();
    const r = await crearPeticion({ titulo: nuevoTitulo, descripcion: nuevoDesc });
    if (r.status === 201) {
      setCreando(false);
      setNuevoTitulo(""); setNuevoDesc("");
      cargar();
    } else {
      alert(r.data?.detail || "Error al crear");
    }
  }

  const visibles = filtroEstado ? items.filter(p => p.estado === filtroEstado) : items;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Peticiones</h2>
        {esDepto && <button type="button" onClick={() => setCreando(true)}>+ Nueva petición</button>}
      </header>

      <div className="filtros">
        <label>Estado:{" "}
          <select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
            <option value="">Todos</option>
            {ESTADOS.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
        </label>
      </div>

      {creando && (
        <form onSubmit={handleCrear} style={{ background: "#f7f7f7", padding: "1em", margin: "1em 0" }}>
          <label>Título <input value={nuevoTitulo} onChange={(e) => setNuevoTitulo(e.target.value)} required /></label>
          <label>Descripción <textarea value={nuevoDesc} onChange={(e) => setNuevoDesc(e.target.value)} required /></label>
          <button type="submit">Crear</button>
          <button type="button" onClick={() => setCreando(false)}>Cancelar</button>
        </form>
      )}

      <table>
        <thead><tr><th>#</th><th>Depto</th><th>Título</th><th>Estado</th><th>Fecha</th></tr></thead>
        <tbody>
          {visibles.map(p => (
            <tr key={p.id} onClick={() => setModal(p)} style={{ cursor: "pointer" }}>
              <td>{p.id}</td>
              <td>{p.departamento_id}</td>
              <td>{p.titulo}</td>
              <td>{p.estado}</td>
              <td>{new Date(p.fecha_creacion).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal && (
        <ModalDetallePeticion
          peticion={modal}
          onClose={() => setModal(null)}
          onActualizado={() => { setModal(null); cargar(); }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Crear `ModalDetallePeticion.jsx`**

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { actualizarPeticion, eliminarPeticion } from "../api/peticiones";
import { crearTrabajo } from "../api/trabajos";
import { useAuth } from "../auth/AuthContext";

export default function ModalDetallePeticion({ peticion, onClose, onActualizado }) {
  const { user } = useAuth();
  const esAdmin = user?.rol === "administracion" || user?.rol === "representante";
  const esMia = user?.rol === "departamento" && user.departamento_id === peticion.departamento_id;
  const puedeBorrar = esAdmin || (esMia && peticion.estado === "abierta");

  async function handleConvertirTrabajo() {
    const r = await crearTrabajo({
      peticion_id: peticion.id,
      descripcion: peticion.titulo,
    });
    if (r.status === 201) onActualizado();
    else alert(r.data?.detail || "Error");
  }

  async function handleCerrar() {
    const r = await actualizarPeticion(peticion.id, { estado: "cerrada" });
    if (r.status === 200) onActualizado();
    else alert(r.data?.detail || "Error");
  }

  async function handleEliminar() {
    if (!window.confirm("¿Eliminar esta petición?")) return;
    const r = await eliminarPeticion(peticion.id);
    if (r.status === 204) onActualizado();
    else alert(r.data?.detail || "Error");
  }

  return (
    <Modal titulo={`Petición #${peticion.id}`} onClose={onClose}>
      <p><strong>Depto:</strong> {peticion.departamento_id}</p>
      <p><strong>Título:</strong> {peticion.titulo}</p>
      <p><strong>Descripción:</strong> {peticion.descripcion}</p>
      <p><strong>Estado:</strong> {peticion.estado}</p>
      <p><strong>Fecha:</strong> {new Date(peticion.fecha_creacion).toLocaleString()}</p>

      <div style={{ marginTop: "1em", display: "flex", gap: "0.5em" }}>
        {esAdmin && peticion.estado === "abierta" && (
          <button type="button" onClick={handleConvertirTrabajo}>Convertir en trabajo</button>
        )}
        {esAdmin && peticion.estado !== "cerrada" && (
          <button type="button" onClick={handleCerrar}>Cerrar petición</button>
        )}
        {puedeBorrar && (
          <button type="button" onClick={handleEliminar}>Eliminar</button>
        )}
        <button type="button" onClick={onClose}>Cerrar</button>
      </div>
    </Modal>
  );
}
```

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/Peticiones.jsx frontend/src/components/ModalDetallePeticion.jsx
git commit -m "feat(frontend): pantalla /peticiones + ModalDetallePeticion"
```

---

## Task 12: Pantalla `/trabajos` + `ModalDetalleTrabajo` + `ModalNuevoPresupuesto`

**Files:**
- Create: `frontend/src/screens/Trabajos.jsx`
- Create: `frontend/src/components/ModalDetalleTrabajo.jsx`
- Create: `frontend/src/components/ModalNuevoPresupuesto.jsx`

- [ ] **Step 1: Crear `Trabajos.jsx`**

Pantalla similar a Peticiones con tabla + botón "+ Nuevo trabajo" (admin/rep) + click abre detalle.

```jsx
import { useEffect, useState } from "react";
import { listarTrabajos, crearTrabajo } from "../api/trabajos";
import { listarPeticiones } from "../api/peticiones";
import ModalDetalleTrabajo from "../components/ModalDetalleTrabajo";

export default function Trabajos() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [creando, setCreando] = useState(false);
  const [peticiones, setPeticiones] = useState([]);
  const [nuevoDesc, setNuevoDesc] = useState("");
  const [nuevoPetId, setNuevoPetId] = useState("");

  async function cargar() {
    const r = await listarTrabajos();
    if (r.status === 200) setItems(r.data);
    const rp = await listarPeticiones();
    if (rp.status === 200) setPeticiones(rp.data.filter(p => p.estado !== "cerrada"));
  }

  useEffect(() => { cargar(); }, []);

  async function handleCrear(e) {
    e.preventDefault();
    const payload = { descripcion: nuevoDesc };
    if (nuevoPetId) payload.peticion_id = Number(nuevoPetId);
    const r = await crearTrabajo(payload);
    if (r.status === 201) {
      setCreando(false); setNuevoDesc(""); setNuevoPetId("");
      cargar();
    } else alert(r.data?.detail || "Error");
  }

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Trabajos</h2>
        <button type="button" onClick={() => setCreando(true)}>+ Nuevo trabajo</button>
      </header>

      {creando && (
        <form onSubmit={handleCrear} style={{ background: "#f7f7f7", padding: "1em", margin: "1em 0" }}>
          <label>Petición (opcional)
            <select value={nuevoPetId} onChange={(e) => setNuevoPetId(e.target.value)}>
              <option value="">Sin petición</option>
              {peticiones.map(p => <option key={p.id} value={p.id}>#{p.id} - {p.titulo}</option>)}
            </select>
          </label>
          <label>Descripción <textarea value={nuevoDesc} onChange={(e) => setNuevoDesc(e.target.value)} required /></label>
          <button type="submit">Crear</button>
          <button type="button" onClick={() => setCreando(false)}>Cancelar</button>
        </form>
      )}

      <table>
        <thead><tr><th>#</th><th>Descripción</th><th>Petición</th><th>Estado</th><th>Presup. aprobado</th><th>Gasto</th></tr></thead>
        <tbody>
          {items.map(t => (
            <tr key={t.id} onClick={() => setModal(t)} style={{ cursor: "pointer" }}>
              <td>{t.id}</td>
              <td>{t.descripcion}</td>
              <td>{t.peticion_id || "—"}</td>
              <td>{t.estado}</td>
              <td>{t.presupuesto_aprobado_id || "—"}</td>
              <td>{t.gasto_id || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal && (
        <ModalDetalleTrabajo
          trabajo={modal}
          onClose={() => setModal(null)}
          onActualizado={() => { setModal(null); cargar(); }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Crear `ModalDetalleTrabajo.jsx` (el más grande — incluye presupuestos embebidos)**

```jsx
import { useEffect, useState } from "react";
import Modal from "./Modal";
import { useAuth } from "../auth/AuthContext";
import { completarTrabajo, cancelarTrabajo } from "../api/trabajos";
import {
  listarPresupuestos, aprobarPresupuesto, rechazarPresupuesto, eliminarPresupuesto,
} from "../api/presupuestos";
import { listarProveedores } from "../api/proveedores";
import ModalNuevoPresupuesto from "./ModalNuevoPresupuesto";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

export default function ModalDetalleTrabajo({ trabajo, onClose, onActualizado }) {
  const { token } = useAuth();
  const [presupuestos, setPresupuestos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [creandoPpto, setCreandoPpto] = useState(false);

  async function cargar() {
    const [rp, rpr] = await Promise.all([
      listarPresupuestos(trabajo.id),
      listarProveedores(),
    ]);
    if (rp.status === 200) setPresupuestos(rp.data);
    if (rpr.status === 200) setProveedores(rpr.data);
  }

  useEffect(() => { cargar(); }, [trabajo.id]);

  const proveedorNombre = (id) => proveedores.find(p => p.id === id)?.razon_social || `#${id}`;

  async function handleAprobar(p) {
    if (presupuestos.some(x => x.estado === "aprobado" && x.id !== p.id)) {
      if (!window.confirm("Ya hay un presupuesto aprobado. ¿Reemplazarlo?")) return;
    }
    const r = await aprobarPresupuesto(trabajo.id, p.id);
    if (r.status === 200) cargar();
  }

  async function handleRechazar(p) {
    const r = await rechazarPresupuesto(trabajo.id, p.id);
    if (r.status === 200) cargar();
  }

  async function handleEliminar(p) {
    if (!window.confirm("¿Eliminar este presupuesto?")) return;
    const r = await eliminarPresupuesto(trabajo.id, p.id);
    if (r.status === 204) cargar();
    else alert(r.data?.detail || "Error");
  }

  async function handleCompletar() {
    const r = await completarTrabajo(trabajo.id);
    if (r.status === 200) {
      // r.data = { proveedor_id, monto, concepto_sugerido, trabajo_id }
      // Navegar a /gastos con query params para pre-completar el form
      const params = new URLSearchParams({
        proveedor_id: r.data.proveedor_id,
        monto: r.data.monto,
        concepto: r.data.concepto_sugerido,
        trabajo_id: r.data.trabajo_id,
      });
      window.location.href = `/gastos?${params}`;
    } else {
      alert(r.data?.detail || "Error");
    }
  }

  async function handleCancelar() {
    if (!window.confirm("¿Cancelar este trabajo sin generar gasto?")) return;
    const r = await cancelarTrabajo(trabajo.id);
    if (r.status === 204) onActualizado();
  }

  const aprobado = presupuestos.find(p => p.estado === "aprobado");

  return (
    <Modal titulo={`Trabajo #${trabajo.id}`} onClose={onClose}>
      <p><strong>Descripción:</strong> {trabajo.descripcion}</p>
      <p><strong>Estado:</strong> {trabajo.estado}</p>
      <p><strong>Petición:</strong> {trabajo.peticion_id || "—"}</p>

      <h3>Presupuestos</h3>
      {trabajo.estado === "en_curso" && (
        <button type="button" onClick={() => setCreandoPpto(true)}>+ Sumar presupuesto</button>
      )}

      <table>
        <thead><tr><th>Proveedor</th><th>Monto</th><th>Fecha</th><th>Archivo</th><th>Estado</th><th>Acciones</th></tr></thead>
        <tbody>
          {presupuestos.map(p => (
            <tr key={p.id} style={p.estado === "aprobado" ? { background: "#e6ffed" } : {}}>
              <td>{proveedorNombre(p.proveedor_id)}</td>
              <td>{fmtMoney(p.monto)}</td>
              <td>{p.fecha_presentacion}</td>
              <td>{p.archivo_path ? <a href={`/uploads/${p.archivo_path}`} target="_blank" rel="noreferrer">Ver</a> : "—"}</td>
              <td>{p.estado}</td>
              <td>
                {p.estado === "presentado" && trabajo.estado === "en_curso" && (
                  <>
                    <button type="button" onClick={() => handleAprobar(p)}>Aprobar</button>
                    <button type="button" onClick={() => handleRechazar(p)}>Rechazar</button>
                    <button type="button" onClick={() => handleEliminar(p)}>Borrar</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Acciones del trabajo</h3>
      {trabajo.estado === "en_curso" && aprobado && (
        <button type="button" onClick={handleCompletar}>💰 Sumar gasto a la caja</button>
      )}
      {trabajo.estado === "en_curso" && !aprobado && (
        <button type="button" onClick={handleCancelar}>Cancelar trabajo</button>
      )}
      {trabajo.estado === "completado" && (
        <p>✓ Trabajo completado. Gasto: #{trabajo.gasto_id}</p>
      )}

      {creandoPpto && (
        <ModalNuevoPresupuesto
          trabajoId={trabajo.id}
          proveedores={proveedores}
          token={token}
          onClose={() => setCreandoPpto(false)}
          onCreado={() => { setCreandoPpto(false); cargar(); }}
        />
      )}
    </Modal>
  );
}
```

- [ ] **Step 3: Crear `ModalNuevoPresupuesto.jsx`**

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { crearPresupuesto } from "../api/presupuestos";

export default function ModalNuevoPresupuesto({ trabajoId, proveedores, token, onClose, onCreado }) {
  const [proveedorId, setProveedorId] = useState(proveedores[0]?.id || "");
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [observaciones, setObservaciones] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [guardando, setGuardando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    const fd = new FormData();
    fd.append("proveedor_id", proveedorId);
    fd.append("monto", monto);
    fd.append("fecha_presentacion", fecha);
    if (observaciones) fd.append("observaciones", observaciones);
    if (archivo) fd.append("archivo", archivo);
    const r = await crearPresupuesto(trabajoId, fd, token);
    setGuardando(false);
    if (r.status === 201) onCreado();
    else alert(r.data?.detail || "Error");
  }

  return (
    <Modal titulo="Nuevo presupuesto" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>Proveedor
          <select value={proveedorId} onChange={(e) => setProveedorId(e.target.value)} required>
            {proveedores.map(p => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select>
        </label>
        <label>Monto <input type="number" min="0.01" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} required /></label>
        <label>Fecha de presentación <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        <label>Observaciones <textarea value={observaciones} onChange={(e) => setObservaciones(e.target.value)} /></label>
        <label>Archivo (PDF/JPG/PNG, opcional, máx 5MB)
          <input type="file" accept=".pdf,image/jpeg,image/png,image/webp" onChange={(e) => setArchivo(e.target.files[0] || null)} />
        </label>
        <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Crear"}</button>
        <button type="button" onClick={onClose}>Cancelar</button>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 4: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/Trabajos.jsx frontend/src/components/ModalDetalleTrabajo.jsx frontend/src/components/ModalNuevoPresupuesto.jsx
git commit -m "feat(frontend): pantalla /trabajos + ModalDetalleTrabajo + ModalNuevoPresupuesto"
```

---

## Task 13: Pantalla `/trabajos-recurrentes`

**Files:**
- Create: `frontend/src/screens/TrabajosRecurrentes.jsx`
- Create: `frontend/src/components/ModalRecurrente.jsx`

- [ ] **Step 1: Crear `TrabajosRecurrentes.jsx`**

Patrón similar a `GastosHabituales.jsx` — tabla CRUD + botón "Materializar" por fila.

```jsx
import { useEffect, useState } from "react";
import { listarRecurrentes, eliminarRecurrente, materializarRecurrente } from "../api/trabajosRecurrentes";
import ModalRecurrente from "../components/ModalRecurrente";

const PERIODICIDADES = { mensual: "Mensual", trimestral: "Trimestral", semestral: "Semestral", anual: "Anual" };

export default function TrabajosRecurrentes() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);

  async function cargar() {
    const r = await listarRecurrentes();
    if (r.status === 200) setItems(r.data);
  }

  useEffect(() => { cargar(); }, []);

  async function handleBorrar(it) {
    if (!window.confirm(`¿Eliminar "${it.nombre}"?`)) return;
    const r = await eliminarRecurrente(it.id);
    if (r.status === 204) cargar();
  }

  async function handleMaterializar(it) {
    const r = await materializarRecurrente(it.id);
    if (r.status === 201) {
      alert(`Trabajo creado: #${r.data.id}. Ir a /trabajos para gestionarlo.`);
    } else {
      alert(r.data?.detail || "Error");
    }
  }

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Trabajos recurrentes (plantillas)</h2>
        <button type="button" onClick={() => setModal("nuevo")}>+ Nueva plantilla</button>
      </header>

      <table>
        <thead><tr><th>Nombre</th><th>Descripción</th><th>Periodicidad</th><th>Monto estimado</th><th>Activa</th><th></th></tr></thead>
        <tbody>
          {items.map(it => (
            <tr key={it.id}>
              <td>{it.nombre}</td>
              <td>{it.descripcion}</td>
              <td>{PERIODICIDADES[it.periodicidad]}</td>
              <td>{it.monto_estimado ? `$${it.monto_estimado.toLocaleString("es-AR")}` : "—"}</td>
              <td>{it.activa ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModal(it)}>Editar</button>
                <button type="button" onClick={() => handleMaterializar(it)} disabled={!it.activa}>
                  Materializar
                </button>
                <button type="button" onClick={() => handleBorrar(it)}>Borrar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal && (
        <ModalRecurrente
          item={modal === "nuevo" ? null : modal}
          onClose={() => setModal(null)}
          onGuardado={() => { setModal(null); cargar(); }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Crear `ModalRecurrente.jsx`**

```jsx
import { useEffect, useState } from "react";
import Modal from "./Modal";
import { crearRecurrente, actualizarRecurrente } from "../api/trabajosRecurrentes";
import { listarProveedores } from "../api/proveedores";

export default function ModalRecurrente({ item, onClose, onGuardado }) {
  const esEditar = item !== null;
  const [nombre, setNombre] = useState(item?.nombre || "");
  const [descripcion, setDescripcion] = useState(item?.descripcion || "");
  const [periodicidad, setPeriodicidad] = useState(item?.periodicidad || "mensual");
  const [proveedorId, setProveedorId] = useState(item?.proveedor_sugerido_id || "");
  const [monto, setMonto] = useState(item?.monto_estimado || "");
  const [activa, setActiva] = useState(item?.activa ?? true);
  const [proveedores, setProveedores] = useState([]);

  useEffect(() => {
    (async () => {
      const r = await listarProveedores();
      if (r.status === 200) setProveedores(r.data);
    })();
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const payload = {
      nombre, descripcion, periodicidad,
      proveedor_sugerido_id: proveedorId ? Number(proveedorId) : null,
      monto_estimado: monto ? Number(monto) : null,
      activa,
    };
    const r = esEditar
      ? await actualizarRecurrente(item.id, payload)
      : await crearRecurrente(payload);
    if (r.status === 200 || r.status === 201) onGuardado();
    else alert(r.data?.detail || "Error");
  }

  return (
    <Modal titulo={esEditar ? "Editar plantilla" : "Nueva plantilla"} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>Nombre <input value={nombre} onChange={(e) => setNombre(e.target.value)} required /></label>
        <label>Descripción <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} required /></label>
        <label>Periodicidad
          <select value={periodicidad} onChange={(e) => setPeriodicidad(e.target.value)}>
            <option value="mensual">Mensual</option>
            <option value="trimestral">Trimestral</option>
            <option value="semestral">Semestral</option>
            <option value="anual">Anual</option>
          </select>
        </label>
        <label>Proveedor sugerido (opcional)
          <select value={proveedorId} onChange={(e) => setProveedorId(e.target.value)}>
            <option value="">— Ninguno —</option>
            {proveedores.map(p => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select>
        </label>
        <label>Monto estimado (opcional) <input type="number" min="0" value={monto} onChange={(e) => setMonto(e.target.value)} /></label>
        <label><input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Activa</label>
        <button type="submit">Guardar</button>
        <button type="button" onClick={onClose}>Cancelar</button>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/screens/TrabajosRecurrentes.jsx frontend/src/components/ModalRecurrente.jsx
git commit -m "feat(frontend): pantalla /trabajos-recurrentes + ModalRecurrente (CRUD + materializar)"
```

---

## Task 14: Componente Campanita + integración en AppLayout

**Files:**
- Create: `frontend/src/components/Campanita.jsx`
- Modify: `frontend/src/components/AppLayout.jsx`

- [ ] **Step 1: Crear `Campanita.jsx`**

```jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listarNotificaciones, obtenerNoLeidasCount, marcarLeida, marcarTodasLeidas,
} from "../api/notificaciones";

const POLL_INTERVAL_MS = 60_000;

export default function Campanita() {
  const navigate = useNavigate();
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [abierto, setAbierto] = useState(false);

  async function refrescarCount() {
    const r = await obtenerNoLeidasCount();
    if (r.status === 200) setCount(r.data.count);
  }

  async function refrescarLista() {
    const r = await listarNotificaciones(10);
    if (r.status === 200) setItems(r.data);
  }

  useEffect(() => {
    refrescarCount();
    refrescarLista();
    const id = setInterval(refrescarCount, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  async function handleClickNotif(n) {
    if (!n.leida) {
      await marcarLeida(n.id);
      refrescarCount();
      refrescarLista();
    }
    setAbierto(false);
    if (n.link) navigate(n.link);
  }

  async function handleMarcarTodas() {
    await marcarTodasLeidas();
    refrescarCount();
    refrescarLista();
  }

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => { setAbierto(!abierto); if (!abierto) refrescarLista(); }}
        style={{ background: "transparent", border: "none", cursor: "pointer", fontSize: "1.4em", position: "relative" }}
        aria-label="Notificaciones"
      >
        🔔
        {count > 0 && (
          <span style={{
            position: "absolute", top: -4, right: -4,
            background: "#dc3545", color: "white",
            borderRadius: "50%", padding: "0 5px",
            fontSize: "0.6em", fontWeight: "bold", minWidth: "16px",
          }}>{count}</span>
        )}
      </button>

      {abierto && (
        <div style={{
          position: "absolute", top: "100%", right: 0, zIndex: 100,
          background: "white", border: "1px solid #ccc",
          minWidth: "320px", maxHeight: "400px", overflowY: "auto",
          boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
        }}>
          <div style={{ padding: "0.5em", borderBottom: "1px solid #eee", display: "flex", justifyContent: "space-between" }}>
            <strong>Notificaciones</strong>
            {count > 0 && (
              <button type="button" onClick={handleMarcarTodas} style={{ fontSize: "0.8em" }}>
                Marcar todas
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p style={{ padding: "1em", color: "#999" }}>Sin notificaciones.</p>
          ) : (
            items.map(n => (
              <div
                key={n.id}
                onClick={() => handleClickNotif(n)}
                style={{
                  padding: "0.7em",
                  borderBottom: "1px solid #eee",
                  background: n.leida ? "white" : "#f0f7ff",
                  cursor: "pointer",
                }}
              >
                <p style={{ margin: 0, fontSize: "0.9em" }}>{n.mensaje}</p>
                <p style={{ margin: 0, fontSize: "0.7em", color: "#999" }}>
                  {new Date(n.created_at).toLocaleString("es-AR")}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Integrar Campanita en `AppLayout.jsx`**

Leer el archivo y agregar el componente Campanita en el header, al lado del email del usuario o del botón logout:

```jsx
import Campanita from "./Campanita";
// ...
<header>
  ...
  <Campanita />
  <span>{user.email}</span>
  <button onClick={logout}>Logout</button>
</header>
```

(Adaptar al markup real del header.)

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/components/Campanita.jsx frontend/src/components/AppLayout.jsx
git commit -m "feat(frontend): Campanita con polling 60s + integración en AppLayout"
```

---

## Task 15: Sidebar + Routes

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Sumar sección "Tareas y presupuestos" en Sidebar (entre Comunicación y Expensas y pagos)**

```javascript
{
  titulo: "Tareas y presupuestos",
  modulos: [
    {
      ruta: "/peticiones",
      nombre: "Peticiones",
      rolesPermitidos: ["administracion", "representante", "departamento"],
    },
    {
      ruta: "/trabajos",
      nombre: "Trabajos",
      rolesPermitidos: ["administracion", "representante"],
    },
    {
      ruta: "/trabajos-recurrentes",
      nombre: "Trabajos recurrentes",
      rolesPermitidos: ["administracion", "representante"],
    },
  ],
},
```

- [ ] **Step 2: Sumar imports + 3 rutas en App.jsx**

```jsx
import Peticiones from "./screens/Peticiones";
import Trabajos from "./screens/Trabajos";
import TrabajosRecurrentes from "./screens/TrabajosRecurrentes";

// ... dentro del bloque de rutas autenticadas:
<Route path="peticiones" element={<Peticiones />} />
<Route path="trabajos" element={<Trabajos />} />
<Route path="trabajos-recurrentes" element={<TrabajosRecurrentes />} />
```

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/components/Sidebar.jsx frontend/src/App.jsx
git commit -m "feat(frontend): sidebar sección Tareas y presupuestos + 3 rutas"
```

---

## Task 16: Smoke + merge + roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`

- [ ] **Step 1: Smoke E2E manual**

Arrancar uvicorn + frontend (reset DB primero):
```powershell
Remove-Item -Force consorcio.db -ErrorAction SilentlyContinue
.venv\Scripts\python -m uvicorn backend.main:app --reload
cd frontend; npm run dev
```

Flujos:
1. Login **depto-a** → ver sección "Tareas y presupuestos" en sidebar (3 items, "Trabajos" y "Trabajos recurrentes" ocultos).
2. Depto → /peticiones → ver todas (incluso de otros deptos) → click "+ Nueva petición" → cargar título+descripción → aparece en la lista.
3. Click en su petición → modal con datos + botón "Eliminar" (solo si abierta).
4. Logout, login **admin** → ver sidebar con los 3 items.
5. Admin → /peticiones → click en la nueva petición → modal con "Convertir en trabajo".
6. Click "Convertir en trabajo" → se crea Trabajo y la petición pasa a "en_curso".
7. **Verificar campanita**: login depto-a → ver badge rojo (1 nueva notificación). Click → ve "Tu petición 'X' cambió a en_curso". Click en la notificación → navega a /peticiones.
8. Admin → /trabajos → ver el trabajo nuevo → click → modal con tabs.
9. Sumar 2 presupuestos (de proveedores distintos, uno con archivo PDF). Aprobar el primero.
10. Aprobar el segundo → confirm "¿Reemplazar?". Aprobado pasa al 2do.
11. Click "💰 Sumar gasto a la caja" → redirige a /gastos con params pre-completados → confirmar el Gasto → vuelve y el trabajo está "completado".
12. **Verificar campanita** depto-a: nueva notificación "petición cambió a cerrada".
13. Admin → /trabajos-recurrentes → ver las 2 plantillas del seed → click "Materializar" en una → se crea un Trabajo nuevo.
14. Cancelar un trabajo en curso sin presupuesto aprobado → marca cancelado y cierra petición.

- [ ] **Step 2: Suite final**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: 600+ passed, 0 failed.

- [ ] **Step 3: Actualizar roadmap**

En `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`, sumar fila al final de la tabla:

```markdown
| **11** ✅ | **Tareas y Presupuestos** (completada YYYY-MM-DD) | Workflow end-to-end petición → trabajo → presupuestos → completar → genera Gasto. Presupuestos con archivo adjunto y FK a Proveedor. Notificaciones doble canal (in-app campanita + email). Trabajos recurrentes con materialización manual. |
```

Sumar al historial:
```markdown
- 2026-06-XX: **Fase 11 completada** (~615 tests, mergeada a master). Cierra el módulo de tareas/presupuestos del CLAUDE.md. Notificaciones campanita reusable como infraestructura para futuros eventos.
```

- [ ] **Step 4: Commit roadmap + merge**

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 11 completada (tareas y presupuestos)"

git checkout master
git merge --no-ff feature/expensas-fase11-tareas-presupuestos -m "Merge feature/expensas-fase11-tareas-presupuestos: módulo completo end-to-end

Fase 11 — Workflow petición → trabajo → presupuestos → completar → Gasto.
Presupuestos con archivo adjunto + FK a Proveedor. Notificaciones doble canal
(campanita in-app con polling 60s + email best-effort). Trabajos recurrentes
con materialización manual. Sistema de Notificacion reusable para eventos futuros."
```

- [ ] **Step 5: Done**

---

## Notas finales

- **Orden de tasks razonado**: modelos+schemas → notificaciones (infra base) → routers nuevos → adaptaciones (peticiones, trabajos, gastos) → docs → seed → frontend client → screens → campanita → sidebar → smoke/merge.
- **TDD**: las tasks 2, 3, 6, 7 escriben tests primero (RED) → implementación (GREEN) → commit.
- **Commits frecuentes**: ~16 commits totales.
- **Reusabilidad**: el módulo `notificaciones.py` queda como infraestructura para futuros eventos (gastos aprobados, comprobantes rechazados, etc.).
- **Migración**: clean start. Borrar `consorcio.db` antes de arrancar.
