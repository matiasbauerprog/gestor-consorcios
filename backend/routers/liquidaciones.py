from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..database import get_db
from ..models import (
    Caja,
    ClaseProrrateo,
    ConceptoLiquidacion,
    Empleado,
    FormaPago,
    Gasto,
    Haber,
    LiquidacionDetalle,
    LiquidacionEmpleado,
    LiquidacionHaber,
    MovimientoCaja,
    PeriodoCerrado,
    Rol,
    Rubro,
    TipoConcepto,
    TipoHaber,
    TipoMovimientoCaja,
)
from ..modulos import require_modulo
from ..tenant import get_consorcio_activo
from ..schemas import (
    LiquidacionEmpleadoActualizar,
    LiquidacionEmpleadoCrear,
    LiquidacionEmpleadoOut,
)

router = APIRouter(
    prefix="/liquidaciones",
    tags=["Personal"],
    dependencies=[Depends(require_modulo("personal"))],
)


def _bloquear_si_periodo_cerrado(db: Session, cid: int, periodo: str) -> None:
    """Si el consorcio ya cerró el período, levanta 409."""
    if db.get(PeriodoCerrado, (periodo, cid)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )


def _clase_default(db: Session, cid: int) -> int:
    """Primera clase de prorrateo activa DEL CONSORCIO. Decisión MVP."""
    clase_id = db.scalar(
        select(ClaseProrrateo.id)
        .where(
            ClaseProrrateo.activa == True,  # noqa: E712
            ClaseProrrateo.consorcio_id == cid,
        )
        .order_by(ClaseProrrateo.id.asc())
    )
    if clase_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay clases de prorrateo activas. Cargá al menos una antes de liquidar.",
        )
    return clase_id


def _validar_caja_activa(db: Session, cid: int, caja_id: int) -> Caja:
    """Valida que la caja exista, sea del consorcio y esté activa."""
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja {caja_id} no encontrada.",
        )
    if not caja.activa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La caja '{caja.nombre}' está inactiva.",
        )
    return caja


def _crear_movimiento_para_gasto(db: Session, gasto: Gasto) -> None:
    """Crea un MovimientoCaja egreso asociado al gasto."""
    db.add(
        MovimientoCaja(
            consorcio_id=gasto.consorcio_id,
            caja_id=gasto.caja_id,
            fecha=gasto.fecha_pago,
            tipo=TipoMovimientoCaja.egreso,
            monto=gasto.monto,
            descripcion=gasto.concepto or f"Gasto {gasto.id}",
            gasto_id=gasto.id,
        )
    )


def _borrar_movimientos_de_gastos(db: Session, gasto_ids: list[int]) -> None:
    """Borra MovimientoCaja asociados a una lista de gastos.

    Flush explícito: sin él SQLAlchemy puede reordenar y ejecutar el DELETE
    del Gasto padre antes que el del MovimientoCaja hijo → viola la FK.
    """
    if not gasto_ids:
        return
    movs = db.scalars(
        select(MovimientoCaja).where(MovimientoCaja.gasto_id.in_(gasto_ids))
    ).all()
    for m in movs:
        db.delete(m)
    if movs:
        db.flush()


def _resolver_haberes(
    db: Session,
    empleado: Empleado,
    haberes_input: list,
    haberes_ad_hoc: list,
    cid: int,
) -> list[LiquidacionHaber]:
    """Convierte los items del payload en filas LiquidacionHaber con monto calculado."""
    snapshots: list[LiquidacionHaber] = []
    orden = 0

    for item in haberes_input:
        haber = db.get(Haber, item.haber_id)
        if haber is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El haber id={item.haber_id} no existe.",
            )

        if haber.tipo == TipoHaber.monto_fijo:
            valor = item.valor_override if item.valor_override is not None else haber.valor_default
            monto = valor
            cantidad = None
        elif haber.tipo == TipoHaber.porcentaje_sobre_basico:
            valor = item.valor_override if item.valor_override is not None else haber.valor_default
            monto = empleado.sueldo_basico * valor / 100
            cantidad = None
        elif haber.tipo == TipoHaber.cantidad_x_valor:
            valor = item.valor_override if item.valor_override is not None else haber.valor_default
            if item.cantidad is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El haber '{haber.nombre}' requiere `cantidad`.",
                )
            cantidad = item.cantidad
            monto = cantidad * valor
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de haber desconocido: {haber.tipo}",
            )

        snapshots.append(
            LiquidacionHaber(
                consorcio_id=cid,
                nombre=haber.nombre,
                tipo=haber.tipo,
                valor=valor,
                cantidad=cantidad,
                monto=monto,
                orden=orden,
            )
        )
        orden += 1

    for ad_hoc in haberes_ad_hoc:
        snapshots.append(
            LiquidacionHaber(
                consorcio_id=cid,
                nombre=ad_hoc.nombre,
                tipo=None,
                valor=None,
                cantidad=None,
                monto=ad_hoc.monto,
                orden=orden,
            )
        )
        orden += 1

    return snapshots


def _aplicar_conceptos(db: Session, sueldo_bruto: float, cid: int) -> list[LiquidacionDetalle]:
    """Calcula los descuentos y contribuciones aplicables al bruto."""
    conceptos = db.scalars(
        select(ConceptoLiquidacion)
        .where(
            ConceptoLiquidacion.consorcio_id == cid,
            ConceptoLiquidacion.activo == True,  # noqa: E712
        )
        .order_by(ConceptoLiquidacion.orden.asc(), ConceptoLiquidacion.nombre.asc())
    ).all()

    return [
        LiquidacionDetalle(
            consorcio_id=cid,
            concepto_nombre=c.nombre,
            concepto_tipo=c.tipo,
            porcentaje_aplicado=c.porcentaje,
            monto=sueldo_bruto * c.porcentaje / 100,
            proveedor_id=c.proveedor_id,
            orden=c.orden,
        )
        for c in conceptos
    ]


def _generar_gastos(
    db: Session,
    liquidacion: LiquidacionEmpleado,
    empleado: Empleado,
    clase_id: int,
    caja_id: int,
    cid: int,
) -> None:
    """Crea N Gastos: uno al empleado por el sueldo neto, uno por proveedor único.
    Cada gasto genera su MovimientoCaja egreso asociado."""
    anio, mes = map(int, liquidacion.periodo.split("-"))
    fecha_pago = date(anio, mes, 1)

    descuentos_total = sum(
        d.monto for d in liquidacion.detalle if d.concepto_tipo == TipoConcepto.descuento
    )
    sueldo_neto = liquidacion.sueldo_bruto - descuentos_total

    # 1) Sueldo neto al empleado
    gasto_sueldo = Gasto(
        consorcio_id=cid,
        periodo=liquidacion.periodo,
        rubro=Rubro.sueldos_y_cargas_sociales,
        clase_prorrateo_id=clase_id,
        proveedor_id=empleado.proveedor_id,
        concepto=f"Sueldo neto - {empleado.nombre_completo}",
        monto=sueldo_neto,
        forma_pago=FormaPago.transferencia,
        fecha_pago=fecha_pago,
        liquidacion_id=liquidacion.id,
        caja_id=caja_id,
    )
    db.add(gasto_sueldo)
    db.flush()
    _crear_movimiento_para_gasto(db, gasto_sueldo)

    # 2) Un gasto por proveedor (agrupa los detalles)
    por_proveedor: dict[int, list[LiquidacionDetalle]] = defaultdict(list)
    for d in liquidacion.detalle:
        if d.proveedor_id is not None:
            por_proveedor[d.proveedor_id].append(d)

    for proveedor_id, items in por_proveedor.items():
        nombres = ", ".join(d.concepto_nombre for d in items)
        total = sum(d.monto for d in items)
        gasto_proveedor = Gasto(
            consorcio_id=cid,
            periodo=liquidacion.periodo,
            rubro=Rubro.sueldos_y_cargas_sociales,
            clase_prorrateo_id=clase_id,
            proveedor_id=proveedor_id,
            concepto=nombres,
            monto=total,
            forma_pago=FormaPago.transferencia,
            fecha_pago=fecha_pago,
            liquidacion_id=liquidacion.id,
            caja_id=caja_id,
        )
        db.add(gasto_proveedor)
        db.flush()
        _crear_movimiento_para_gasto(db, gasto_proveedor)


def _calcular_y_guardar(
    db: Session,
    liquidacion: LiquidacionEmpleado,
    empleado: Empleado,
    payload: LiquidacionEmpleadoCrear | LiquidacionEmpleadoActualizar,
    cid: int,
) -> None:
    """Centraliza el cálculo (POST y PATCH lo usan)."""
    haberes_snap = _resolver_haberes(db, empleado, payload.haberes, payload.haberes_ad_hoc, cid)
    liquidacion.haberes = haberes_snap
    liquidacion.sueldo_bruto = sum(h.monto for h in haberes_snap)
    liquidacion.detalle = _aplicar_conceptos(db, liquidacion.sueldo_bruto, cid)


def _eager_load_liquidacion(db: Session, liquidacion_id: int) -> LiquidacionEmpleado | None:
    """Recarga la liquidación con haberes y detalle eager-loaded."""
    return db.get(LiquidacionEmpleado, liquidacion_id)


@router.get(
    "",
    response_model=list[LiquidacionEmpleadoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar liquidaciones",
)
def listar_liquidaciones(
    periodo: str | None = Query(default=None),
    empleado_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[LiquidacionEmpleado]:
    stmt = select(LiquidacionEmpleado).where(LiquidacionEmpleado.consorcio_id == cid).order_by(
        LiquidacionEmpleado.periodo.desc(), LiquidacionEmpleado.id.desc()
    )
    if periodo is not None:
        stmt = stmt.where(LiquidacionEmpleado.periodo == periodo)
    if empleado_id is not None:
        stmt = stmt.where(LiquidacionEmpleado.empleado_id == empleado_id)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=LiquidacionEmpleadoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear liquidación con cálculo automático",
)
def crear_liquidacion(
    payload: LiquidacionEmpleadoCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> LiquidacionEmpleado:
    # Bloquear si el período está cerrado
    _bloquear_si_periodo_cerrado(db, cid, payload.periodo)

    # Validar caja
    _validar_caja_activa(db, cid, payload.caja_id)

    empleado = db.get(Empleado, payload.empleado_id)
    if empleado is None or empleado.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El empleado solicitado no existe.",
        )

    duplicada = db.scalar(
        select(LiquidacionEmpleado.id).where(
            LiquidacionEmpleado.empleado_id == payload.empleado_id,
            LiquidacionEmpleado.periodo == payload.periodo,
        )
    )
    if duplicada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una liquidación para ese empleado en ese período.",
        )

    clase_id = _clase_default(db, cid)

    liquidacion = LiquidacionEmpleado(
        consorcio_id=cid,
        empleado_id=empleado.id,
        periodo=payload.periodo,
        sueldo_bruto=0,
        caja_id=payload.caja_id,
    )
    db.add(liquidacion)
    db.flush()

    _calcular_y_guardar(db, liquidacion, empleado, payload, cid)
    db.flush()
    _generar_gastos(db, liquidacion, empleado, clase_id, payload.caja_id, cid)

    db.commit()
    db.refresh(liquidacion)
    return liquidacion


@router.get(
    "/{liquidacion_id}",
    response_model=LiquidacionEmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener liquidación",
)
def obtener_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> LiquidacionEmpleado:
    liq = db.get(LiquidacionEmpleado, liquidacion_id)
    if liq is None or liq.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La liquidación solicitada no existe.",
        )
    return liq


@router.patch(
    "/{liquidacion_id}",
    response_model=LiquidacionEmpleadoOut,
    status_code=status.HTTP_200_OK,
    summary="Editar liquidación (recálcula y regenera gastos)",
)
def actualizar_liquidacion(
    liquidacion_id: int,
    payload: LiquidacionEmpleadoActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> LiquidacionEmpleado:
    liq = db.get(LiquidacionEmpleado, liquidacion_id)
    if liq is None or liq.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La liquidación solicitada no existe.",
        )

    # Bloquear si el período de la liquidación está cerrado
    _bloquear_si_periodo_cerrado(db, cid, liq.periodo)

    empleado = db.get(Empleado, liq.empleado_id)
    clase_id = _clase_default(db, cid)

    # Usar caja_id del payload si viene, sino usar la de la liquidación actual
    caja_id = payload.caja_id if payload.caja_id is not None else liq.caja_id
    _validar_caja_activa(db, cid, caja_id)

    # Actualizar caja_id si cambió
    if payload.caja_id is not None:
        liq.caja_id = payload.caja_id

    # Recolectar IDs de gastos viejos antes de borrarlos
    gastos_viejos = db.scalars(
        select(Gasto.id).where(Gasto.liquidacion_id == liq.id)
    ).all()
    gasto_ids_viejos = list(gastos_viejos)

    # Borrar movimientos viejos
    _borrar_movimientos_de_gastos(db, gasto_ids_viejos)

    # Borrar gastos viejos asociados
    db.query(Gasto).filter(Gasto.liquidacion_id == liq.id).delete(synchronize_session=False)

    _calcular_y_guardar(db, liq, empleado, payload, cid)
    db.flush()
    _generar_gastos(db, liq, empleado, clase_id, caja_id, cid)

    db.commit()
    db.refresh(liq)
    return liq


@router.delete(
    "/{liquidacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar liquidación (cascade haberes/detalle + gastos asociados)",
)
def eliminar_liquidacion(
    liquidacion_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Response:
    liq = db.get(LiquidacionEmpleado, liquidacion_id)
    if liq is None or liq.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La liquidación solicitada no existe.",
        )

    # Bloquear si el período de la liquidación está cerrado
    _bloquear_si_periodo_cerrado(db, cid, liq.periodo)

    # Recolectar IDs de gastos asociados
    gastos_ids = db.scalars(
        select(Gasto.id).where(Gasto.liquidacion_id == liq.id)
    ).all()
    gasto_ids_list = list(gastos_ids)

    # Borrar movimientos de caja asociados a los gastos
    _borrar_movimientos_de_gastos(db, gasto_ids_list)

    # Borrar gastos asociados manualmente (FK SET NULL no los elimina).
    db.query(Gasto).filter(Gasto.liquidacion_id == liq.id).delete(synchronize_session=False)
    db.delete(liq)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
