from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    ClaseProrrateo,
    Departamento,
    Gasto,
    GastoHabitual,
    Proveedor,
    Rol,
    Rubro,
)
from ..schemas import (
    CargarHabitualesIn,
    GastoActualizar,
    GastoCrear,
    GastoOut,
    PlanCuotasCrear,
)

router = APIRouter(prefix="/gastos", tags=["Gastos"])


def _sumar_un_mes(periodo: str) -> str:
    """Recibe 'YYYY-MM' y devuelve el mes siguiente como 'YYYY-MM'."""
    anio, mes = map(int, periodo.split("-"))
    mes += 1
    if mes == 13:
        mes = 1
        anio += 1
    return f"{anio:04d}-{mes:02d}"


def _sumar_un_mes_date(fecha: date) -> date:
    """Suma un mes a la fecha. Si el día no existe en el mes siguiente
    (ej. 31 de enero → febrero), usa el último día del mes."""
    import calendar
    anio = fecha.year
    mes = fecha.month + 1
    if mes == 13:
        mes = 1
        anio += 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    dia = min(fecha.day, ultimo_dia)
    return date(anio, mes, dia)


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


@router.post(
    "/plan-cuotas",
    response_model=list[GastoOut],
    status_code=status.HTTP_201_CREATED,
    summary="Crear plan de N cuotas (genera N gastos consecutivos)",
)
def crear_plan_cuotas(
    payload: PlanCuotasCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Gasto]:
    _validar_referencias(
        db,
        payload.clase_prorrateo_id,
        payload.departamento_id,
        payload.proveedor_id,
    )

    gastos: list[Gasto] = []
    periodo_actual = payload.periodo
    fecha_actual = payload.fecha_pago

    for i in range(payload.cuota_total):
        gasto = Gasto(
            periodo=periodo_actual,
            rubro=payload.rubro,
            clase_prorrateo_id=payload.clase_prorrateo_id,
            departamento_id=payload.departamento_id,
            proveedor_id=payload.proveedor_id,
            concepto=payload.concepto,
            monto=payload.monto,
            forma_pago=payload.forma_pago,
            fecha_pago=fecha_actual,
            numero_factura=payload.numero_factura,
            fecha_factura=payload.fecha_factura,
            cuota_actual=i + 1,
            cuota_total=payload.cuota_total,
        )
        db.add(gasto)
        gastos.append(gasto)

        periodo_actual = _sumar_un_mes(periodo_actual)
        fecha_actual = _sumar_un_mes_date(fecha_actual)

    db.commit()
    for g in gastos:
        db.refresh(g)
    return gastos


@router.post(
    "/cargar-habituales",
    response_model=list[GastoOut],
    status_code=status.HTTP_201_CREATED,
    summary="Materializar plantillas habituales activas en un período (idempotente)",
)
def cargar_habituales(
    payload: CargarHabitualesIn,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> list[Gasto]:
    anio, mes = map(int, payload.periodo.split("-"))
    fecha_pago_default = date(anio, mes, 1)

    # Plantillas activas que aún no tienen gasto generado en este período.
    plantillas_activas = db.scalars(
        select(GastoHabitual).where(GastoHabitual.activa == True)  # noqa: E712
    ).all()

    ids_ya_generadas = set(
        db.scalars(
            select(Gasto.gasto_habitual_id).where(
                Gasto.periodo == payload.periodo,
                Gasto.gasto_habitual_id.is_not(None),
            )
        ).all()
    )

    nuevos: list[Gasto] = []
    for plantilla in plantillas_activas:
        if plantilla.id in ids_ya_generadas:
            continue
        gasto = Gasto(
            periodo=payload.periodo,
            rubro=plantilla.rubro,
            clase_prorrateo_id=plantilla.clase_prorrateo_id,
            departamento_id=None,
            proveedor_id=plantilla.proveedor_id,
            concepto=plantilla.concepto,
            monto=plantilla.monto,
            forma_pago=plantilla.forma_pago,
            fecha_pago=fecha_pago_default,
            gasto_habitual_id=plantilla.id,
        )
        db.add(gasto)
        nuevos.append(gasto)

    db.commit()
    for g in nuevos:
        db.refresh(g)
    return nuevos
