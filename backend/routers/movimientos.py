"""Endpoints de cuenta corriente y notas (crédito/débito)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..cuenta_corriente import calcular_estado_cuenta
from ..database import get_db
from ..models import Departamento, Expensa, MovimientoCuenta, Rol
from ..modulos import require_modulo
from ..recargos import devengar_recargos_y_marcar
from ..schemas import CuentaResumenOut, EstadoCuentaOut, MovimientoCuentaOut, NotaCrear
from ..tenant import get_consorcio_activo

router = APIRouter(
    tags=["Movimientos"],
    dependencies=[Depends(require_modulo("cobranzas"))],
)


def _cuenta(
    db: Session,
    departamento_id: int,
    desde: date | None,
    hasta: date | None,
) -> EstadoCuentaOut:
    # Devengamiento perezoso: leer la cuenta materializa los recargos vencidos.
    # Idempotente, así que repetir la lectura no duplica nada.
    if devengar_recargos_y_marcar(db, departamento_id):
        db.commit()

    estado = calcular_estado_cuenta(db, departamento_id)
    depto = db.get(Departamento, departamento_id)

    stmt = (
        select(MovimientoCuenta)
        .where(MovimientoCuenta.departamento_id == departamento_id)
        .order_by(MovimientoCuenta.fecha.desc(), MovimientoCuenta.id.desc())
    )
    if desde is not None:
        stmt = stmt.where(MovimientoCuenta.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(MovimientoCuenta.fecha <= hasta)

    movs = list(db.scalars(stmt).all())
    return EstadoCuentaOut(
        departamento_id=departamento_id,
        departamento_codigo=depto.codigo if depto else "",
        departamento_ubicacion=depto.descripcion if depto else None,
        saldo_total=estado.saldo_total,
        movimientos=[MovimientoCuentaOut.model_validate(m) for m in movs],
    )


@router.get(
    "/movimientos/mi-cuenta",
    response_model=EstadoCuentaOut,
    status_code=status.HTTP_200_OK,
    summary="Cuenta corriente del departamento autenticado",
)
def mi_cuenta(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.departamento)),
    _cid: int = Depends(get_consorcio_activo),
) -> EstadoCuentaOut:
    return _cuenta(db, user.departamento_id, desde, hasta)


@router.get(
    "/movimientos/cuentas",
    response_model=list[CuentaResumenOut],
    status_code=status.HTTP_200_OK,
    summary="Listado consolidado de saldos por departamento (admin)",
)
def listar_cuentas(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[CuentaResumenOut]:
    hoy = date.today()
    deptos = list(
        db.scalars(
            select(Departamento)
            .where(Departamento.consorcio_id == cid)
            .order_by(Departamento.codigo.asc())
        ).all()
    )

    # Set de depto_ids con al menos una expensa vencida (2do venc pasado).
    deptos_con_vencida = {
        r for (r,) in db.query(Expensa.departamento_id).filter(
            Expensa.consorcio_id == cid,
            Expensa.fecha_segundo_vencimiento < hoy,
        ).distinct().all()
    }

    # Devengamiento perezoso, un solo commit para todo el listado: hacerlo por
    # departamento sería una transacción por iteración.
    hubo_recargos = False
    for d in deptos:
        if devengar_recargos_y_marcar(db, d.id):
            hubo_recargos = True
    if hubo_recargos:
        db.commit()

    resultado = []
    for d in deptos:
        saldo = calcular_estado_cuenta(db, d.id).saldo_total
        en_mora = saldo > 0.005 and d.id in deptos_con_vencida
        resultado.append(CuentaResumenOut(
            departamento_id=d.id,
            codigo=d.codigo,
            ubicacion=d.descripcion,
            saldo_total=saldo,
            en_mora=en_mora,
        ))
    return resultado


@router.get(
    "/departamentos/{departamento_id}/cuenta",
    response_model=EstadoCuentaOut,
    status_code=status.HTTP_200_OK,
    summary="Cuenta corriente de un departamento (admin)",
)
def cuenta_departamento(
    departamento_id: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> EstadoCuentaOut:
    d = db.get(Departamento, departamento_id)
    if d is None or d.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )
    return _cuenta(db, departamento_id, desde, hasta)


@router.post(
    "/movimientos/nota",
    response_model=MovimientoCuentaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nota de crédito o débito (admin)",
)
def crear_nota(
    payload: NotaCrear,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> MovimientoCuenta:
    d = db.get(Departamento, payload.departamento_id)
    if d is None or d.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El departamento indicado no existe.",
        )

    mov = MovimientoCuenta(
        consorcio_id=cid,
        departamento_id=payload.departamento_id,
        fecha=payload.fecha or date.today(),
        tipo=payload.tipo,
        descripcion=payload.descripcion,
        monto=payload.monto,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov
