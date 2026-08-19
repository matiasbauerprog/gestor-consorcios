from datetime import date

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..cierre import periodo_cerrado_en
from ..database import get_db
from ..models import (
    Caja,
    ClaseProrrateo,
    Departamento,
    EstadoTrabajo,
    Gasto,
    GastoHabitual,
    MovimientoCaja,
    Peticion,
    PeriodoCerrado,
    Proveedor,
    Rol,
    Rubro,
    TipoMovimientoCaja,
    Trabajo,
)
from ..modulos import require_modulo
from ..notificaciones import emitir
from ..notificaciones.catalogo import TRABAJO_COMPLETADO
from ..tenant import get_consorcio_activo
from ..schemas import (
    CargarHabitualesIn,
    GastoActualizar,
    GastoCrear,
    GastoOut,
    GastoPagar,
    PlanCuotasCrear,
)

router = APIRouter(
    prefix="/gastos",
    tags=["Gastos"],
    dependencies=[Depends(require_modulo("gastos"))],
)


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
    cid: int,
    clase_id: int | None,
    depto_id: int | None,
    proveedor_id: int,
) -> None:
    if clase_id is not None:
        clase = db.get(ClaseProrrateo, clase_id)
        if clase is None or clase.consorcio_id != cid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La clase de prorrateo indicada no existe.",
            )
    if depto_id is not None:
        depto = db.get(Departamento, depto_id)
        if depto is None or depto.consorcio_id != cid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El departamento indicado no existe.",
            )
    prov = db.get(Proveedor, proveedor_id)
    if prov is None or prov.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El proveedor indicado no existe.",
        )


_PERIODO_PATTERN_GASTO = r"^\d{4}-(0[1-9]|1[0-2])$"


def _bloquear_si_periodo_cerrado(db: Session, cid: int, periodo: str) -> None:
    """Si el consorcio ya cerró el período, levanta 409."""
    if db.get(PeriodoCerrado, (periodo, cid)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El período {periodo} está cerrado y no admite cambios.",
        )


def _validar_caja_activa(db: Session, cid: int, caja_id: int) -> Caja:
    """Valida que la caja exista, sea del consorcio y esté activa."""
    caja = db.get(Caja, caja_id)
    if caja is None or caja.consorcio_id != cid:
        raise HTTPException(404, f"Caja {caja_id} no encontrada.")
    if not caja.activa:
        raise HTTPException(400, f"La caja '{caja.nombre}' está inactiva.")
    return caja


def _crear_movimiento_para_gasto(db: Session, gasto: Gasto) -> None:
    """Crea el MovimientoCaja egreso asociado a un Gasto."""
    db.add(MovimientoCaja(
        consorcio_id=gasto.consorcio_id,
        caja_id=gasto.caja_id,
        fecha=gasto.fecha_pago,
        tipo=TipoMovimientoCaja.egreso,
        monto=gasto.monto,
        descripcion=gasto.concepto or f"Gasto {gasto.id}",
        gasto_id=gasto.id,
    ))


def _borrar_movimiento_de_gasto(db: Session, gasto_id: int) -> None:
    """Borra el/los MovimientoCaja asociados a un Gasto.

    Flush explícito: garantiza que el DELETE de MovimientoCaja corra ANTES
    que el DELETE del Gasto padre. Sin él SQLAlchemy puede reordenarlos y
    violar la FK movimientos_caja.gasto_id → gastos.id.
    """
    movs = db.scalars(
        select(MovimientoCaja).where(MovimientoCaja.gasto_id == gasto_id)
    ).all()
    for m in movs:
        db.delete(m)
    if movs:
        db.flush()


def _materializar_habituales(db: Session, cid: int, periodo: str) -> list[Gasto]:
    """Crea los gastos que faltan para las plantillas activas del período.

    Idempotente: una plantilla que ya generó su gasto en ese período se saltea.
    Los gastos nacen SIN pagar y SIN MovimientoCaja — la plantilla dice cuánto
    se espera gastar, no cuánto se gastó. El egreso de caja lo produce
    POST /gastos/{id}/pagar cuando llega la factura real.

    No hace commit: el llamador decide la transacción.
    """
    anio, mes = map(int, periodo.split("-"))
    fecha_provisoria = date(anio, mes, 1)

    plantillas_activas = db.scalars(
        select(GastoHabitual).where(
            GastoHabitual.consorcio_id == cid,
            GastoHabitual.activa == True,  # noqa: E712
        )
    ).all()

    ids_ya_generadas = set(
        db.scalars(
            select(Gasto.gasto_habitual_id).where(
                Gasto.consorcio_id == cid,
                Gasto.periodo == periodo,
                Gasto.gasto_habitual_id.is_not(None),
            )
        ).all()
    )

    nuevos: list[Gasto] = []
    for plantilla in plantillas_activas:
        if plantilla.id in ids_ya_generadas:
            continue
        # Savepoint por plantilla: si otra request ganó la carrera entre el
        # chequeo y el INSERT, la única que sobrevive es la suya y acá se
        # descarta la propia sin arrastrar el resto de la transacción.
        savepoint = db.begin_nested()
        gasto = Gasto(
            consorcio_id=cid,
            periodo=periodo,
            rubro=plantilla.rubro,
            clase_prorrateo_id=plantilla.clase_prorrateo_id,
            departamento_id=None,
            proveedor_id=plantilla.proveedor_id,
            concepto=plantilla.concepto,
            monto=plantilla.monto,
            forma_pago=plantilla.forma_pago,
            caja_id=plantilla.caja_id,
            fecha_pago=fecha_provisoria,
            pagado=False,
            gasto_habitual_id=plantilla.id,
        )
        db.add(gasto)
        try:
            db.flush()
        except IntegrityError:
            savepoint.rollback()
            continue
        savepoint.commit()
        nuevos.append(gasto)
    return nuevos


def _corresponde_materializar(db: Session, cid: int, periodo: str | None) -> bool:
    """Sólo se materializan recurrentes en un período consultable y vivo.

    - Período cerrado: ya liquidó sus expensas; agregarle gastos las dejaría
      inconsistentes.
    - Período futuro: navegar con las flechas hasta 2030 devengaría de golpe
      los recurrentes de todos los meses intermedios.
    """
    if periodo is None:
        return False
    if periodo > date.today().strftime("%Y-%m"):
        return False
    return not periodo_cerrado_en(db, cid, periodo)


@router.get(
    "",
    response_model=list[GastoOut],
    status_code=status.HTTP_200_OK,
    summary="Listar gastos del consorcio (materializa recurrentes pendientes)",
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
    cid: int = Depends(get_consorcio_activo),
) -> list[Gasto]:
    # Efecto de escritura deliberado en un GET: materializa las plantillas
    # recurrentes que falten. La alternativa es un scheduler, que el proyecto
    # no tiene. La operación es idempotente, así que repetir el GET no duplica.
    if _corresponde_materializar(db, cid, periodo):
        if _materializar_habituales(db, cid, periodo):
            db.commit()

    stmt = (
        select(Gasto)
        .where(Gasto.consorcio_id == cid)
        .order_by(Gasto.pagado.asc(), Gasto.fecha_pago.desc(), Gasto.id.desc())
    )
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
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Gasto:
    _bloquear_si_periodo_cerrado(db, cid, payload.periodo)
    _validar_caja_activa(db, cid, payload.caja_id)
    _validar_referencias(
        db, cid,
        payload.clase_prorrateo_id,
        payload.departamento_id,
        payload.proveedor_id,
    )

    gasto = Gasto(
        consorcio_id=cid,
        periodo=payload.periodo,
        rubro=payload.rubro,
        clase_prorrateo_id=payload.clase_prorrateo_id,
        departamento_id=payload.departamento_id,
        proveedor_id=payload.proveedor_id,
        concepto=payload.concepto,
        monto=payload.monto,
        forma_pago=payload.forma_pago,
        caja_id=payload.caja_id,
        fecha_pago=payload.fecha_pago,
        numero_factura=payload.numero_factura,
        fecha_factura=payload.fecha_factura,
        cuota_actual=payload.cuota_actual,
        cuota_total=payload.cuota_total,
    )
    db.add(gasto)
    db.flush()
    _crear_movimiento_para_gasto(db, gasto)

    # Integración Fase 11: si vino trabajo_id, marcar el trabajo finalizado
    if payload.trabajo_id:
        t = db.get(Trabajo, payload.trabajo_id)
        if t is None or t.consorcio_id != cid:
            raise HTTPException(404, f"Trabajo {payload.trabajo_id} no encontrado.")
        t.gasto_id = gasto.id
        t.estado = EstadoTrabajo.finalizado

        if t.peticion_id:
            pet = db.get(Peticion, t.peticion_id)
            if pet:
                emitir(
                    db, TRABAJO_COMPLETADO,
                    consorcio_id=cid,
                    contexto={"titulo": pet.titulo},
                    actor_usuario_id=user.id,
                    departamento_id=pet.departamento_id,
                    tareas=tareas,
                )

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
    cid: int = Depends(get_consorcio_activo),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None or gasto.consorcio_id != cid:
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
    cid: int = Depends(get_consorcio_activo),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None or gasto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )

    # Bloquear si el período actual está cerrado
    _bloquear_si_periodo_cerrado(db, cid, gasto.periodo)

    # Si se intenta cambiar el período, también bloquear si el nuevo período está cerrado
    cambios = payload.model_dump(exclude_unset=True)
    if "periodo" in cambios:
        _bloquear_si_periodo_cerrado(db, cid, cambios["periodo"])

    # Validar caja si cambia
    if payload.caja_id is not None:
        _validar_caja_activa(db, cid, payload.caja_id)

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
        _validar_referencias(db, cid, nueva_clase, nuevo_depto, nuevo_prov)

    for campo, valor in cambios.items():
        setattr(gasto, campo, valor)

    # Un gasto sin pagar no tiene movimiento de caja que rehacer. Recrearlo acá
    # le adelantaría el egreso a un gasto que todavía no se pagó.
    if gasto.pagado:
        _borrar_movimiento_de_gasto(db, gasto.id)
        _crear_movimiento_para_gasto(db, gasto)

    db.commit()
    db.refresh(gasto)
    return gasto


@router.post(
    "/{gasto_id}/pagar",
    response_model=GastoOut,
    status_code=status.HTTP_200_OK,
    summary="Confirmar el pago de un gasto devengado",
)
def pagar_gasto(
    gasto_id: int,
    payload: GastoPagar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None or gasto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    if gasto.pagado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El gasto ya figura como pagado.",
        )
    # El cierre sólo ADVIERTE sobre gastos impagos, así que cerrar por encima de
    # ellos es un flujo esperado y la factura puede llegar después. Confirmar el
    # pago por el mismo monto no toca nada de lo ya prorrateado, así que se
    # permite; cambiar el monto sí lo tocaría y sigue bloqueado.
    if db.get(PeriodoCerrado, (gasto.periodo, cid)) is not None:
        if abs(payload.monto - gasto.monto) > 0.005:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"El período {gasto.periodo} está cerrado: el monto prorrateado "
                    "a los departamentos ya no puede cambiar. Registrá la diferencia "
                    "como un gasto aparte en un período abierto."
                ),
            )

    _validar_caja_activa(db, cid, payload.caja_id)

    gasto.monto = payload.monto
    gasto.fecha_pago = payload.fecha_pago
    gasto.caja_id = payload.caja_id
    gasto.pagado = True
    db.flush()
    _crear_movimiento_para_gasto(db, gasto)

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
    cid: int = Depends(get_consorcio_activo),
) -> Response:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None or gasto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    _bloquear_si_periodo_cerrado(db, cid, gasto.periodo)
    _borrar_movimiento_de_gasto(db, gasto_id)
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
    cid: int = Depends(get_consorcio_activo),
) -> list[Gasto]:
    # Bloquear si el período inicial está cerrado
    _bloquear_si_periodo_cerrado(db, cid, payload.periodo)

    # Validar caja una sola vez
    _validar_caja_activa(db, cid, payload.caja_id)

    _validar_referencias(
        db, cid,
        payload.clase_prorrateo_id,
        payload.departamento_id,
        payload.proveedor_id,
    )

    gastos: list[Gasto] = []
    periodo_actual = payload.periodo
    fecha_actual = payload.fecha_pago

    for i in range(payload.cuota_total):
        gasto = Gasto(
            consorcio_id=cid,
            periodo=periodo_actual,
            rubro=payload.rubro,
            clase_prorrateo_id=payload.clase_prorrateo_id,
            departamento_id=payload.departamento_id,
            proveedor_id=payload.proveedor_id,
            concepto=payload.concepto,
            monto=payload.monto,
            forma_pago=payload.forma_pago,
            caja_id=payload.caja_id,
            fecha_pago=fecha_actual,
            numero_factura=payload.numero_factura,
            fecha_factura=payload.fecha_factura,
            cuota_actual=i + 1,
            cuota_total=payload.cuota_total,
        )
        # Bloquear si alguno de los períodos consecutivos está cerrado
        _bloquear_si_periodo_cerrado(db, cid, periodo_actual)
        db.add(gasto)
        db.flush()
        _crear_movimiento_para_gasto(db, gasto)
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
    cid: int = Depends(get_consorcio_activo),
) -> list[Gasto]:
    _bloquear_si_periodo_cerrado(db, cid, payload.periodo)
    nuevos = _materializar_habituales(db, cid, payload.periodo)
    db.commit()
    for g in nuevos:
        db.refresh(g)
    return nuevos
