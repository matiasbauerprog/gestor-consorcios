from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import ConceptoLiquidacion, Proveedor, Rol
from ..modulos import require_modulo
from ..tenant import get_consorcio_activo
from ..schemas import (
    ConceptoLiquidacionActualizar,
    ConceptoLiquidacionCrear,
    ConceptoLiquidacionOut,
)

router = APIRouter(
    prefix="/conceptos-liquidacion",
    tags=["Personal"],
    dependencies=[Depends(require_modulo("personal"))],
)


def _validar_proveedor(db: Session, cid: int, proveedor_id: int | None) -> None:
    if proveedor_id is None:
        return
    p = db.get(Proveedor, proveedor_id)
    if p is None or p.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


@router.get(
    "",
    response_model=list[ConceptoLiquidacionOut],
    status_code=status.HTTP_200_OK,
    summary="Listar conceptos de liquidación",
)
def listar_conceptos(
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[ConceptoLiquidacion]:
    stmt = select(ConceptoLiquidacion).where(ConceptoLiquidacion.consorcio_id == cid).order_by(
        ConceptoLiquidacion.orden.asc(), ConceptoLiquidacion.nombre.asc()
    )
    if activo is not None:
        stmt = stmt.where(ConceptoLiquidacion.activo == activo)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear concepto",
)
def crear_concepto(
    payload: ConceptoLiquidacionCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ConceptoLiquidacion:
    duplicado = db.scalar(
        select(ConceptoLiquidacion.id).where(
            ConceptoLiquidacion.nombre == payload.nombre,
            ConceptoLiquidacion.consorcio_id == cid,
        )
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un concepto con ese nombre.",
        )

    _validar_proveedor(db, cid, payload.proveedor_id)

    concepto = ConceptoLiquidacion(
        consorcio_id=cid,
        nombre=payload.nombre,
        tipo=payload.tipo,
        porcentaje=payload.porcentaje,
        proveedor_id=payload.proveedor_id,
        orden=payload.orden,
        activo=True,
    )
    db.add(concepto)
    db.commit()
    db.refresh(concepto)
    return concepto


@router.get(
    "/{concepto_id}",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener concepto",
)
def obtener_concepto(
    concepto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ConceptoLiquidacion:
    concepto = db.get(ConceptoLiquidacion, concepto_id)
    if concepto is None or concepto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El concepto solicitado no existe.",
        )
    return concepto


@router.patch(
    "/{concepto_id}",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_200_OK,
    summary="Editar concepto",
)
def actualizar_concepto(
    concepto_id: int,
    payload: ConceptoLiquidacionActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ConceptoLiquidacion:
    concepto = db.get(ConceptoLiquidacion, concepto_id)
    if concepto is None or concepto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El concepto solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)
    if "proveedor_id" in cambios:
        _validar_proveedor(db, cid, cambios["proveedor_id"])

    for campo, valor in cambios.items():
        setattr(concepto, campo, valor)

    db.commit()
    db.refresh(concepto)
    return concepto


@router.delete(
    "/{concepto_id}",
    response_model=ConceptoLiquidacionOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar concepto (soft-delete)",
)
def eliminar_concepto(
    concepto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> ConceptoLiquidacion:
    concepto = db.get(ConceptoLiquidacion, concepto_id)
    if concepto is None or concepto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El concepto solicitado no existe.",
        )

    concepto.activo = False
    db.commit()
    db.refresh(concepto)
    return concepto
