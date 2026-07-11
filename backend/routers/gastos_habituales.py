from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import Caja, ClaseProrrateo, Gasto, GastoHabitual, Proveedor, Rol
from ..modulos import require_modulo
from ..tenant import get_consorcio_activo
from ..schemas import (
    GastoHabitualActualizar,
    GastoHabitualCrear,
    GastoHabitualOut,
)

router = APIRouter(
    prefix="/gastos-habituales",
    tags=["Gastos"],
    dependencies=[Depends(require_modulo("gastos"))],
)


def _validar_caja_activa(db: Session, cid: int, caja_id: int) -> Caja:
    """Validar que la caja existe, es del consorcio y está activa."""
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La caja con ID {caja_id} no existe.",
        )
    if not caja.activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La caja '{caja.nombre}' está inactiva.",
        )
    return caja


def _validar_referencias(db: Session, cid: int, clase_id: int, proveedor_id: int) -> None:
    clase = db.get(ClaseProrrateo, clase_id)
    if clase is None or clase.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La clase de prorrateo indicada no existe.",
        )
    prov = db.get(Proveedor, proveedor_id)
    if prov is None or prov.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


@router.get(
    "",
    response_model=list[GastoHabitualOut],
    status_code=status.HTTP_200_OK,
    summary="Listar plantillas de gastos habituales",
)
def listar_habituales(
    activa: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[GastoHabitual]:
    stmt = select(GastoHabitual).where(GastoHabitual.consorcio_id == cid).order_by(GastoHabitual.nombre.asc())
    if activa is not None:
        stmt = stmt.where(GastoHabitual.activa == activa)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=GastoHabitualOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear plantilla de gasto habitual",
)
def crear_habitual(
    payload: GastoHabitualCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> GastoHabitual:
    _validar_referencias(db, cid, payload.clase_prorrateo_id, payload.proveedor_id)
    _validar_caja_activa(db, cid, payload.caja_id)

    plantilla = GastoHabitual(
        consorcio_id=cid,
        nombre=payload.nombre,
        rubro=payload.rubro,
        clase_prorrateo_id=payload.clase_prorrateo_id,
        proveedor_id=payload.proveedor_id,
        concepto=payload.concepto,
        monto=payload.monto,
        forma_pago=payload.forma_pago,
        caja_id=payload.caja_id,
        activa=True,
    )
    db.add(plantilla)
    db.commit()
    db.refresh(plantilla)
    return plantilla


@router.get(
    "/{gasto_habitual_id}",
    response_model=GastoHabitualOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener plantilla",
)
def obtener_habitual(
    gasto_habitual_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> GastoHabitual:
    plantilla = db.get(GastoHabitual, gasto_habitual_id)
    if plantilla is None or plantilla.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La plantilla solicitada no existe.",
        )
    return plantilla


@router.patch(
    "/{gasto_habitual_id}",
    response_model=GastoHabitualOut,
    status_code=status.HTTP_200_OK,
    summary="Editar plantilla",
)
def actualizar_habitual(
    gasto_habitual_id: int,
    payload: GastoHabitualActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> GastoHabitual:
    plantilla = db.get(GastoHabitual, gasto_habitual_id)
    if plantilla is None or plantilla.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La plantilla solicitada no existe.",
        )

    cambios = payload.model_dump(exclude_unset=True)

    # Validar FKs si cambian.
    nueva_clase = cambios.get("clase_prorrateo_id", plantilla.clase_prorrateo_id)
    nuevo_prov = cambios.get("proveedor_id", plantilla.proveedor_id)
    if "clase_prorrateo_id" in cambios or "proveedor_id" in cambios:
        _validar_referencias(db, cid, nueva_clase, nuevo_prov)

    # Validar caja_id si cambia.
    if "caja_id" in cambios:
        _validar_caja_activa(db, cid, cambios["caja_id"])

    for campo, valor in cambios.items():
        setattr(plantilla, campo, valor)

    db.commit()
    db.refresh(plantilla)
    return plantilla


@router.delete(
    "/{gasto_habitual_id}",
    response_model=GastoHabitualOut | None,
    status_code=status.HTTP_200_OK,
    summary="Eliminar plantilla (hard si no tiene gastos; soft si tiene)",
)
def eliminar_habitual(
    gasto_habitual_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
):
    plantilla = db.get(GastoHabitual, gasto_habitual_id)
    if plantilla is None or plantilla.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La plantilla solicitada no existe.",
        )

    tiene_gastos = (
        db.scalar(select(Gasto.id).where(Gasto.gasto_habitual_id == gasto_habitual_id))
        is not None
    )

    if tiene_gastos:
        plantilla.activa = False
        db.commit()
        db.refresh(plantilla)
        return plantilla

    db.delete(plantilla)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
