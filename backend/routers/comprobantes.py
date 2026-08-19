from datetime import date, datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..config import get_settings
from ..database import get_db
from ..models import (
    Caja,
    Comprobante,
    Consorcio,
    Departamento,
    EstadoComprobante,
    MovimientoCaja,
    MovimientoCuenta,
    Rol,
    TipoMovimiento,
    TipoMovimientoCaja,
)
from ..modulos import require_modulo
from ..notificaciones import emitir, resolver_pendiente
from ..notificaciones.catalogo import (
    COMPROBANTE_APROBADO,
    COMPROBANTE_PRESENTADO,
    COMPROBANTE_RECHAZADO,
)
from ..schemas import ArchivoUrlOut, ComprobanteActualizar, ComprobanteOut
from ..storage import firmar_clave, guardar_archivo
from ..tenant import get_consorcio_activo


def _descripcion_pago(comprobante: Comprobante) -> str:
    """Descripción legible del movimiento generado al aprobar un pago.
    Prefiere el código del depto (UF-XX) sobre el ID interno del comprobante."""
    codigo = comprobante.departamento.codigo if comprobante.departamento else "?"
    return f"Pago {codigo} - {comprobante.fecha_pago.isoformat()}"

router = APIRouter(
    prefix="/comprobantes",
    tags=["Expensas"],
    dependencies=[Depends(require_modulo("cobranzas"))],
)


@router.get(
    "",
    response_model=list[ComprobanteOut],
    status_code=status.HTTP_200_OK,
    summary="Listar comprobantes",
)
def listar_comprobantes(
    estado: EstadoComprobante | None = Query(default=None),
    departamento_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> list[Comprobante]:
    stmt = (
        select(Comprobante)
        .where(Comprobante.consorcio_id == cid, Comprobante.eliminado_at.is_(None))
        .order_by(Comprobante.fecha_creacion.desc(), Comprobante.id.desc())
    )

    # Aislamiento por unidad: el Departamento solo ve sus comprobantes. Cualquier
    # departamento_id en query es ignorado para deptos.
    if user.rol == Rol.departamento:
        stmt = stmt.where(Comprobante.departamento_id == user.departamento_id)
    elif departamento_id is not None:
        stmt = stmt.where(Comprobante.departamento_id == departamento_id)

    if estado is not None:
        stmt = stmt.where(Comprobante.estado == estado)

    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.get(
    "/{comprobante_id}/archivo",
    response_model=ArchivoUrlOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener la URL firmada del comprobante",
)
def url_del_comprobante(
    comprobante_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> ArchivoUrlOut:
    comprobante = db.get(Comprobante, comprobante_id)
    # Un 403 distinguido de un 404 le confirmaria al que prueba ids que ese
    # comprobante existe. Todo lo que no le corresponde al usuario es 404.
    if (
        comprobante is None
        or comprobante.consorcio_id != cid
        or comprobante.eliminado_at is not None
        or not comprobante.archivo_path
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado."
        )
    if (
        user.rol == Rol.departamento
        and comprobante.departamento_id != user.departamento_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comprobante no encontrado."
        )

    return ArchivoUrlOut(
        url=firmar_clave(comprobante.archivo_path),
        expira_en=get_settings().URL_FIRMADA_SEGUNDOS,
    )


@router.post(
    "",
    response_model=ComprobanteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Presentar comprobante de pago",
)
def presentar_comprobante(
    tareas: BackgroundTasks,
    fecha_pago: date = Form(...),
    monto: float = Form(..., gt=0),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> Comprobante:
    if fecha_pago > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de pago no puede ser futura.",
        )

    if not archivo.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo del comprobante es obligatorio.",
        )

    archivo_path = guardar_archivo(archivo, "comprobantes")

    comprobante = Comprobante(
        consorcio_id=cid,
        departamento_id=user.departamento_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_path=archivo_path,
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db.add(comprobante)
    db.flush()

    depto = db.get(Departamento, user.departamento_id)
    emitir(
        db, COMPROBANTE_PRESENTADO,
        consorcio_id=cid,
        contexto={
            "codigo_depto": depto.codigo if depto else "Un departamento",
            "monto": comprobante.monto,
        },
        actor_usuario_id=user.id,
        entidad_id=comprobante.id,
        tareas=tareas,
    )

    db.commit()
    db.refresh(comprobante)
    return comprobante


@router.patch(
    "/{comprobante_id}",
    response_model=ComprobanteOut,
    status_code=status.HTTP_200_OK,
    summary="Aprobar o rechazar un comprobante",
)
def actualizar_comprobante(
    comprobante_id: int,
    payload: ComprobanteActualizar,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Comprobante:
    comprobante = db.get(Comprobante, comprobante_id)
    if comprobante is None or comprobante.consorcio_id != cid or comprobante.eliminado_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comprobante solicitado no existe.",
        )

    # Estados terminales son inmutables — admin compensa errores con notas.
    if comprobante.estado != EstadoComprobante.pendiente_verificacion:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El comprobante ya fue verificado y no puede modificarse.",
        )

    comprobante.estado = payload.estado

    # El motivo sólo tiene sentido en un rechazo: en una aprobación se ignora,
    # aunque el body lo traiga. `strip()` evita que un textarea con espacios
    # cuente como motivo — o hay texto real o queda NULL.
    if payload.estado == EstadoComprobante.rechazado:
        motivo = (payload.motivo_rechazo or "").strip()
        comprobante.motivo_rechazo = motivo or None

    # Aprobar genera el ingreso contable en la cuenta corriente del depto.
    if payload.estado == EstadoComprobante.aprobado:
        # Resolver caja destino
        caja_destino_id = payload.caja_destino_id
        if caja_destino_id is None:
            cfg = db.get(Consorcio, cid)
            caja_destino_id = cfg.caja_default_pagos_id if cfg else None
        if caja_destino_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe indicar caja_destino_id (no hay default configurada)."
            )
        caja_dst = db.get(Caja, caja_destino_id)
        if caja_dst is None or caja_dst.consorcio_id != cid or not caja_dst.activa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Caja destino inválida o inactiva."
            )

        # Persistir en el comprobante
        comprobante.caja_destino_id = caja_destino_id

        # Generar MovimientoCuenta ingreso
        db.add(
            MovimientoCuenta(
                consorcio_id=cid,
                departamento_id=comprobante.departamento_id,
                fecha=comprobante.fecha_pago,
                tipo=TipoMovimiento.pago_recibido,
                descripcion=_descripcion_pago(comprobante),
                monto=comprobante.monto,
                comprobante_id=comprobante.id,
            )
        )

        # Generar MovimientoCaja ingreso
        db.add(
            MovimientoCaja(
                consorcio_id=cid,
                caja_id=caja_destino_id,
                fecha=comprobante.fecha_pago,
                tipo=TipoMovimientoCaja.ingreso,
                monto=comprobante.monto,
                descripcion=_descripcion_pago(comprobante),
                comprobante_id=comprobante.id,
            )
        )

    # El comprobante deja de estar esperando verificación: el pendiente del
    # admin se apaga para todos, lo haya resuelto quien lo haya resuelto.
    resolver_pendiente(
        db, consorcio_id=cid, entidad_tipo="comprobante", entidad_id=comprobante.id,
    )

    aprobado = comprobante.estado == EstadoComprobante.aprobado
    emitir(
        db,
        COMPROBANTE_APROBADO if aprobado else COMPROBANTE_RECHAZADO,
        consorcio_id=cid,
        contexto={
            "monto": comprobante.monto,
            "motivo": comprobante.motivo_rechazo,
        },
        actor_usuario_id=user.id,
        departamento_id=comprobante.departamento_id,
        tareas=tareas,
    )

    db.commit()
    db.refresh(comprobante)
    return comprobante


@router.delete(
    "/{comprobante_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete de un comprobante (oculta de la vista)",
)
def eliminar_comprobante(
    comprobante_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion, Rol.departamento)),
    cid: int = Depends(get_consorcio_activo),
) -> None:
    comprobante = db.get(Comprobante, comprobante_id)
    if comprobante is None or comprobante.consorcio_id != cid or comprobante.eliminado_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comprobante solicitado no existe.",
        )

    if (
        user.rol == Rol.departamento
        and comprobante.departamento_id != user.departamento_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder a este recurso.",
        )

    # El pendiente apunta a este comprobante y no puede quedar vivo señalando
    # algo que ya no existe. Va después de los chequeos de permiso, no antes:
    # así ninguna rama que termina en 403/404 lo toca (mismo criterio que
    # backend/routers/peticiones.py:208).
    resolver_pendiente(
        db, consorcio_id=cid, entidad_tipo="comprobante", entidad_id=comprobante.id,
    )

    comprobante.eliminado_at = datetime.now(timezone.utc)
    db.commit()
