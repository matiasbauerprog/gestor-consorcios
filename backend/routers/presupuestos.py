"""Router de presupuestos — Fase 11.

Anida bajo /trabajos/{trabajo_id}/presupuestos. Acceso admin/representante para
POST/PATCH/DELETE/aprobar/rechazar. GET: admin/representante/depto (lectura).
"""
import uuid
from datetime import date
from pathlib import Path as PathlibPath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..config import get_settings
from ..database import get_db
from ..models import EstadoPresupuesto, Presupuesto, Proveedor, Rol, Trabajo
from ..modulos import require_modulo
from ..schemas import PresupuestoActualizar, PresupuestoOut
from ..tenant import get_consorcio_activo

router = APIRouter(
    prefix="/trabajos",
    tags=["Presupuestos"],
    dependencies=[Depends(require_modulo("operacion"))],
)

ALLOWED_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_ARCHIVO_BYTES = 5 * 1024 * 1024  # 5MB


def _validar_trabajo(db: Session, cid: int, trabajo_id: int) -> Trabajo:
    t = db.get(Trabajo, trabajo_id)
    if t is None or t.consorcio_id != cid:
        raise HTTPException(404, "Trabajo no encontrado.")
    return t


def _validar_proveedor(db: Session, cid: int, proveedor_id: int) -> Proveedor:
    p = db.get(Proveedor, proveedor_id)
    if p is None or p.consorcio_id != cid:
        raise HTTPException(404, f"Proveedor {proveedor_id} no encontrado.")
    return p


def _guardar_archivo(archivo: UploadFile) -> str:
    """Guarda en uploads/presupuestos/ con nombre random. Devuelve path relativo a UPLOAD_DIR."""
    ext = PathlibPath(archivo.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Extensión no permitida ({ext}). Use PDF/JPG/PNG/WebP.")
    contenido = archivo.file.read()
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise HTTPException(400, "Archivo > 5MB.")
    settings = get_settings()
    target_dir = PathlibPath(settings.UPLOAD_DIR) / "presupuestos"
    target_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}{ext}"
    target_path = target_dir / nombre
    target_path.write_bytes(contenido)
    return str(PathlibPath("presupuestos") / nombre)


@router.get("/{trabajo_id}/presupuestos", response_model=list[PresupuestoOut])
def listar_presupuestos(
    trabajo_id: int,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
    cid: int = Depends(get_consorcio_activo),
):
    _validar_trabajo(db, cid, trabajo_id)
    return list(db.scalars(
        select(Presupuesto)
        .where(Presupuesto.trabajo_id == trabajo_id)
        .order_by(Presupuesto.fecha_presentacion)
    ).all())


@router.post("/{trabajo_id}/presupuestos", response_model=PresupuestoOut, status_code=201)
def crear_presupuesto(
    trabajo_id: int,
    proveedor_id: int = Form(...),
    monto: float = Form(..., gt=0),
    fecha_presentacion: str | None = Form(None),
    observaciones: str | None = Form(None),
    archivo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion, Rol.representante)),
    cid: int = Depends(get_consorcio_activo),
) -> PresupuestoOut:
    _validar_trabajo(db, cid, trabajo_id)
    _validar_proveedor(db, cid, proveedor_id)

    fecha = date.fromisoformat(fecha_presentacion) if fecha_presentacion else date.today()
    archivo_path = _guardar_archivo(archivo) if (archivo and archivo.filename) else None

    p = Presupuesto(
        consorcio_id=cid,
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


@router.patch("/{trabajo_id}/presupuestos/{presupuesto_id}", response_model=PresupuestoOut)
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
        _validar_proveedor(db, cid, payload.proveedor_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(p, campo, valor)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{trabajo_id}/presupuestos/{presupuesto_id}", status_code=204)
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


@router.post("/{trabajo_id}/presupuestos/{presupuesto_id}/aprobar", response_model=PresupuestoOut)
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
    # Rechazar todos los demás aprobados del mismo trabajo
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


@router.post("/{trabajo_id}/presupuestos/{presupuesto_id}/rechazar", response_model=PresupuestoOut)
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
