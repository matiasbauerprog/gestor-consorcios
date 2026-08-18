"""Endpoints del rol super_admin (Plan B): CRUD administraciones, reset-password,
impersonate, métricas y audit log.

Todos requieren rol super_admin. El JWT impersonado NO da acceso a /super-admin/*
(excepto /impersonate/end): la dep `_bloquear_impersonate_activo` lo enforcea.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import blacklist
from ..audit import crear_audit_log_entry
from ..auth import CurrentUser, create_access_token, get_current_user, require_roles
from ..database import get_db
from ..models import (
    Administracion,
    AuditLogSuperAdmin,
    Consorcio,
    Departamento,
    ErrorRegistrado,
    Expensa,
    Rol,
    Usuario,
)
from ..schemas import (
    AdministracionActualizar,
    AdministracionCrear,
    AdministracionOut,
    AuditLogEntryOut,
    ErrorRegistradoOut,
    ImpersonateStartIn,
    ImpersonateStartOut,
    MetricasOut,
    ModulosAdministracionIn,
    ModulosAdministracionOut,
    ResetPasswordOut,
    UsuarioAdminOut,
)
from ..modulos import MODULOS, modulos_habilitados_de
from ..security import hash_password

router = APIRouter(prefix="/super-admin", tags=["SuperAdmin"])

_IMPERSONATE_TTL_MIN = 15


def _bloquear_impersonate_activo(
    user: CurrentUser = Depends(require_roles(Rol.super_admin)),
) -> CurrentUser:
    """Rechaza el JWT impersonado en rutas /super-admin/*.

    El JWT impersonado tiene `sub` = usuario_impersonado (rol distinto de
    super_admin), así que require_roles(Rol.super_admin) ya lo bloquea. Esta dep
    queda para claridad y para tests que puedan construir un JWT super_admin +
    impersonated_by (edge case defensivo)."""
    if user.impersonated_by is not None:
        raise HTTPException(
            status_code=403,
            detail="operacion_no_permitida_durante_impersonate",
        )
    return user


# ---------------------------------------------------------------------------
# CRUD administraciones
# ---------------------------------------------------------------------------


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
    return list(
        db.scalars(select(Administracion).order_by(Administracion.razon_social.asc())).all()
    )


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
    cuit_existente = db.scalar(
        select(Administracion.id).where(Administracion.cuit == payload.cuit)
    )
    if cuit_existente is not None:
        raise HTTPException(
            status_code=409, detail="Ya existe una administración con ese CUIT."
        )
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
        detalles={
            "razon_social": payload.razon_social,
            "admin_email": payload.admin_email,
        },
    )
    db.commit()
    db.refresh(admin_tenant)
    return admin_tenant


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


# ---------------------------------------------------------------------------
# Listar usuarios de una administración
# ---------------------------------------------------------------------------


@router.get(
    "/administraciones/{administracion_id}/usuarios",
    response_model=list[UsuarioAdminOut],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios de una administración",
)
def listar_usuarios_de_administracion(
    administracion_id: int,
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> list[Usuario]:
    admin = db.get(Administracion, administracion_id)
    if admin is None:
        raise HTTPException(status_code=404, detail="Administración no encontrada.")
    return (
        db.query(Usuario)
        .filter(Usuario.administracion_id == administracion_id)
        .order_by(Usuario.rol, Usuario.email)
        .all()
    )


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------


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
        raise HTTPException(
            status_code=404, detail="Usuario no encontrado en esta administración."
        )

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


# ---------------------------------------------------------------------------
# Impersonate
# ---------------------------------------------------------------------------


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
        raise HTTPException(
            status_code=400, detail="No se puede impersonar a otro super_admin."
        )

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
        detalles={
            "usuario_impersonado_id": target.id,
            "email": target.email,
            "rol": target.rol.value,
        },
    )
    db.commit()

    return ImpersonateStartOut(
        access_token=tok,
        expires_in=_IMPERSONATE_TTL_MIN * 60,
        impersonated_user_id=target.id,
    )


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
        raise HTTPException(
            status_code=400, detail="El token actual no es de impersonate."
        )

    blacklist.revoke(user.jti, user.exp)

    crear_audit_log_entry(
        db,
        super_admin_usuario_id=user.impersonated_by,
        accion="impersonate_end",
        detalles={"usuario_impersonado_id": user.id, "jti": user.jti},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


@router.get(
    "/errores",
    response_model=list[ErrorRegistradoOut],
    status_code=status.HTTP_200_OK,
    summary="Últimos errores inesperados del sistema",
)
def listar_errores(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> list[ErrorRegistrado]:
    return list(
        db.scalars(
            select(ErrorRegistrado)
            .order_by(ErrorRegistrado.ocurrido_at.desc(), ErrorRegistrado.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.get(
    "/errores/{codigo}",
    response_model=ErrorRegistradoOut,
    status_code=status.HTTP_200_OK,
    summary="Buscar un error por su código",
)
def obtener_error(
    codigo: str,
    db: Session = Depends(get_db),
    _sa: CurrentUser = Depends(_bloquear_impersonate_activo),
) -> ErrorRegistrado:
    # El código se dicta por teléfono: se acepta en minúsculas y con espacios
    # de más, que es como llega la mitad de las veces.
    normalizado = codigo.strip().upper()
    error = db.scalar(
        select(ErrorRegistrado).where(ErrorRegistrado.codigo == normalizado)
    )
    if error is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay ningún error con el código {normalizado}.",
        )
    return error


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
    admins_activas = (
        db.scalar(
            select(func.count(Administracion.id)).where(Administracion.activa == True)  # noqa: E712
        )
        or 0
    )
    admins_susp = (
        db.scalar(
            select(func.count(Administracion.id)).where(Administracion.activa == False)  # noqa: E712
        )
        or 0
    )
    consorcios_total = db.scalar(select(func.count(Consorcio.id))) or 0
    deptos_total = db.scalar(select(func.count(Departamento.id))) or 0

    hoy = datetime.now(timezone.utc).date()
    periodo_actual = hoy.strftime("%Y-%m")
    exp_last_month_count = (
        db.scalar(select(func.count(Expensa.id)).where(Expensa.periodo == periodo_actual))
        or 0
    )
    exp_last_month_monto = (
        db.scalar(
            select(func.coalesce(func.sum(Expensa.monto_primer_vencimiento), 0.0)).where(
                Expensa.periodo == periodo_actual
            )
        )
        or 0.0
    )

    hace_30 = datetime.now(timezone.utc) - timedelta(days=30)
    imp_ultimos = (
        db.scalar(
            select(func.count(AuditLogSuperAdmin.id)).where(
                AuditLogSuperAdmin.accion == "impersonate_start",
                AuditLogSuperAdmin.fecha >= hace_30,
            )
        )
        or 0
    )

    return MetricasOut(
        administraciones={
            "activas": admins_activas,
            "suspendidas": admins_susp,
            "total": admins_activas + admins_susp,
        },
        consorcios={"total": consorcios_total},
        departamentos={"total": deptos_total},
        expensas_ultimo_mes={
            "emitidas": exp_last_month_count,
            "monto_total": float(exp_last_month_monto),
        },
        impersonates_ultimos_30_dias=imp_ultimos,
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@router.get(
    "/audit-log",
    response_model=list[AuditLogEntryOut],
    status_code=status.HTTP_200_OK,
    summary="Audit log paginado",
)
def listar_audit_log(
    accion: str | None = Query(default=None, max_length=80),
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
