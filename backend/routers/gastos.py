from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    ClaseProrrateo,
    Departamento,
    Gasto,
    Proveedor,
    Rol,
    Rubro,
)
from ..schemas import GastoActualizar, GastoCrear, GastoOut

router = APIRouter(prefix="/gastos", tags=["Gastos"])


def _validar_referencias(
    db: Session,
    clase_id: int | None,
    depto_id: int | None,
    proveedor_id: int,
) -> None:
    if clase_id is not None and db.get(ClaseProrrateo, clase_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase de prorrateo indicada no existe.",
        )
    if depto_id is not None and db.get(Departamento, depto_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )
    if db.get(Proveedor, proveedor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


_PERIODO_PATTERN_GASTO = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get(
    "",
    response_model=list[GastoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar gastos del consorcio",
)
def listar_gastos(
    periodo: str | None = Query(default=None, pattern=_PERIODO_PATTERN_GASTO),
    rubro: Rubro | None = Query(default=None),
    clase_prorrateo_id: int | None = Query(default=None, gt=0),
    departamento_id: int | None = Query(default=None, gt=0),
    proveedor_id: int | None = Query(default=None, gt=0),
    gasto_habitual_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Gasto]:
    stmt = select(Gasto).order_by(Gasto.fecha_pago.desc(), Gasto.id.desc())
    if periodo is not None:
        stmt = stmt.where(Gasto.periodo == periodo)
    if rubro is not None:
        stmt = stmt.where(Gasto.rubro == rubro)
    if clase_prorrateo_id is not None:
        stmt = stmt.where(Gasto.clase_prorrateo_id == clase_prorrateo_id)
    if departamento_id is not None:
        stmt = stmt.where(Gasto.departamento_id == departamento_id)
    if proveedor_id is not None:
        stmt = stmt.where(Gasto.proveedor_id == proveedor_id)
    if gasto_habitual_id is not None:
        stmt = stmt.where(Gasto.gasto_habitual_id == gasto_habitual_id)
    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=GastoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un gasto",
)
def crear_gasto(
    payload: GastoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Gasto:
    _validar_referencias(
        db,
        payload.clase_prorrateo_id,
        payload.departamento_id,
        payload.proveedor_id,
    )

    gasto = Gasto(
        periodo=payload.periodo,
        rubro=payload.rubro,
        clase_prorrateo_id=payload.clase_prorrateo_id,
        departamento_id=payload.departamento_id,
        proveedor_id=payload.proveedor_id,
        concepto=payload.concepto,
        monto=payload.monto,
        forma_pago=payload.forma_pago,
        fecha_pago=payload.fecha_pago,
        numero_factura=payload.numero_factura,
        fecha_factura=payload.fecha_factura,
        cuota_actual=payload.cuota_actual,
        cuota_total=payload.cuota_total,
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return gasto


@router.get(
    "/{gasto_id}",
    response_model=GastoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener gasto",
)
def obtener_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    return gasto


@router.patch(
    "/{gasto_id}",
    response_model=GastoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar gasto",
)
def actualizar_gasto(
    gasto_id: int,
    payload: GastoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)

    # Validar excluyencia clase/depto si alguno cambia.
    nueva_clase = cambios.get("clase_prorrateo_id", gasto.clase_prorrateo_id)
    nuevo_depto = cambios.get("departamento_id", gasto.departamento_id)
    if (nueva_clase is None) == (nuevo_depto is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe indicarse exactamente uno de `clase_prorrateo_id` o `departamento_id`.",
        )

    # Validar consistencia de cuotas si alguno cambia.
    nueva_ca = cambios.get("cuota_actual", gasto.cuota_actual)
    nuevo_ct = cambios.get("cuota_total", gasto.cuota_total)
    if (nueva_ca is None) != (nuevo_ct is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`cuota_actual` y `cuota_total` deben ir ambos o ninguno.",
        )
    if nueva_ca is not None and nuevo_ct is not None and nueva_ca > nuevo_ct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`cuota_actual` no puede exceder `cuota_total`.",
        )

    nuevo_prov = cambios.get("proveedor_id", gasto.proveedor_id)
    if (
        "clase_prorrateo_id" in cambios
        or "departamento_id" in cambios
        or "proveedor_id" in cambios
    ):
        _validar_referencias(db, nueva_clase, nuevo_depto, nuevo_prov)

    for campo, valor in cambios.items():
        setattr(gasto, campo, valor)

    db.commit()
    db.refresh(gasto)
    return gasto


@router.delete(
    "/{gasto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar gasto",
)
def eliminar_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> Response:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    db.delete(gasto)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
