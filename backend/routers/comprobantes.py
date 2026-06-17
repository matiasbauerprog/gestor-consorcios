from datetime import date, datetime, timezone

from fastapi import (
    APIRouter,
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
from ..database import get_db
from ..models import (
    Comprobante,
    EstadoComprobante,
    MovimientoCuenta,
    Rol,
    TipoMovimiento,
)
from ..schemas import ComprobanteActualizar, ComprobanteOut
from ..storage import guardar_imagen_comprobante

router = APIRouter(prefix="/comprobantes", tags=["Expensas"])


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
) -> list[Comprobante]:
    stmt = (
        select(Comprobante)
        .where(Comprobante.eliminado_at.is_(None))
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


@router.post(
    "",
    response_model=ComprobanteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Presentar comprobante de pago",
)
def presentar_comprobante(
    fecha_pago: date = Form(...),
    monto: float = Form(..., gt=0),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
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

    archivo_path = guardar_imagen_comprobante(archivo)

    comprobante = Comprobante(
        departamento_id=user.departamento_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_path=archivo_path,
        estado=EstadoComprobante.pendiente_verificacion,
    )
    db.add(comprobante)
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
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Comprobante:
    comprobante = db.get(Comprobante, comprobante_id)
    if comprobante is None or comprobante.eliminado_at is not None:
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

    # Aprobar genera el ingreso contable en la cuenta corriente del depto.
    if payload.estado == EstadoComprobante.aprobado:
        db.add(
            MovimientoCuenta(
                departamento_id=comprobante.departamento_id,
                fecha=comprobante.fecha_pago,
                tipo=TipoMovimiento.pago_recibido,
                descripcion=f"Pago comprobante #{comprobante.id}",
                monto=comprobante.monto,
                comprobante_id=comprobante.id,
            )
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
) -> None:
    comprobante = db.get(Comprobante, comprobante_id)
    if comprobante is None or comprobante.eliminado_at is not None:
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

    comprobante.eliminado_at = datetime.now(timezone.utc)
    db.commit()
