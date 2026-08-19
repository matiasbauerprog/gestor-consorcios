import re
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_roles
from ..cierre import calcular_preview_cierre
from ..database import get_db
from ..mail_service import enviar_email
from ..models import (
    Departamento,
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    PeriodoCerrado,
    Rol,
    TipoMovimiento,
    Usuario,
)
from ..notificaciones import emitir
from ..notificaciones.catalogo import EXPENSA_EMITIDA
from ..pdf import generar_pdf_boleta
from ..tenant import get_consorcio_activo
from ..schemas import (
    CerrarPeriodoIn,
    EnviarPdfsIn,
    EnviarPdfsOut,
    ErrorEnvioOut,
    EstadoCierreOut,
    ExpensaACrearOut,
    InteresACrearOut,
    LineaDetalleExpensaOut,
    PeriodoCerradoOut,
    PreviewCierreOut,
    ValidacionOut,
)

router = APIRouter(prefix="/periodos", tags=["Periodos"])

_PERIODO_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _preview_to_out(preview) -> PreviewCierreOut:
    return PreviewCierreOut(
        periodo=preview.periodo,
        cerrado=preview.cerrado,
        fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
        fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
        validaciones=[ValidacionOut(**v.__dict__) for v in preview.validaciones],
        puede_cerrar=preview.puede_cerrar,
        expensas=[
            ExpensaACrearOut(
                departamento_id=e.departamento_id,
                saldo_anterior=e.saldo_anterior,
                monto_primer_vencimiento=e.monto_primer_vencimiento,
                monto_segundo_vencimiento=e.monto_segundo_vencimiento,
                detalle=[
                    LineaDetalleExpensaOut(
                        rubro=d.rubro,
                        clase_prorrateo_id=d.clase_prorrateo_id,
                        departamento_origen_id=d.departamento_origen_id,
                        concepto=d.concepto,
                        monto=d.monto,
                    )
                    for d in e.detalle
                ],
            )
            for e in preview.expensas
        ],
        intereses=[InteresACrearOut(**i.__dict__) for i in preview.intereses],
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
    )


@router.get("", response_model=list[PeriodoCerradoOut], status_code=200)
def listar_periodos(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> list[PeriodoCerrado]:
    return list(db.scalars(
        select(PeriodoCerrado)
        .where(PeriodoCerrado.consorcio_id == cid)
        .order_by(PeriodoCerrado.fecha_cierre.desc())
    ).all())


@router.get("/{periodo}/estado", response_model=EstadoCierreOut, status_code=200)
def estado_periodo(
    periodo: str,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    _cid: int = Depends(get_consorcio_activo),
) -> EstadoCierreOut:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido. Use formato YYYY-MM.")
    preview = calcular_preview_cierre(db, _cid, periodo)
    return EstadoCierreOut(
        periodo=preview.periodo,
        cerrado=preview.cerrado,
        validaciones=[ValidacionOut(**v.__dict__) for v in preview.validaciones],
        puede_cerrar=preview.puede_cerrar,
    )


@router.get("/{periodo}/preview", response_model=PreviewCierreOut, status_code=200)
def preview_periodo(
    periodo: str,
    fecha_1: date | None = Query(default=None),
    fecha_2: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    _cid: int = Depends(get_consorcio_activo),
) -> PreviewCierreOut:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido.")
    if db.get(PeriodoCerrado, (periodo, _cid)) is not None:
        raise HTTPException(409, f"El período {periodo} ya fue cerrado.")
    preview = calcular_preview_cierre(db, _cid, periodo, fecha_1, fecha_2)
    return _preview_to_out(preview)


@router.post("/{periodo}/cerrar", response_model=PeriodoCerradoOut, status_code=201)
def cerrar_periodo(
    periodo: str,
    payload: CerrarPeriodoIn,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> PeriodoCerrado:
    if not re.fullmatch(_PERIODO_PATTERN, periodo):
        raise HTTPException(400, "Período inválido.")
    if db.get(PeriodoCerrado, (periodo, cid)) is not None:
        raise HTTPException(409, f"El período {periodo} ya fue cerrado.")

    preview = calcular_preview_cierre(
        db, cid, periodo,
        payload.fecha_primer_vencimiento,
        payload.fecha_segundo_vencimiento,
    )
    if not preview.puede_cerrar:
        raise HTTPException(409, "Hay validaciones bloqueantes pendientes para cerrar el período.")

    hoy = date.today()

    for it in preview.intereses:
        db.add(MovimientoCuenta(
            consorcio_id=cid,
            departamento_id=it.departamento_id,
            fecha=hoy,
            tipo=TipoMovimiento.interes_punitorio,
            descripcion=it.descripcion,
            monto=it.monto,
        ))
    db.flush()

    for exp in preview.expensas:
        e = Expensa(
            consorcio_id=cid,
            departamento_id=exp.departamento_id,
            periodo=periodo,
            monto_primer_vencimiento=exp.monto_primer_vencimiento,
            fecha_primer_vencimiento=preview.fecha_primer_vencimiento,
            monto_segundo_vencimiento=exp.monto_segundo_vencimiento,
            fecha_segundo_vencimiento=preview.fecha_segundo_vencimiento,
            saldo_anterior=exp.saldo_anterior,
        )
        db.add(e); db.flush()
        for d in exp.detalle:
            db.add(ExpensaDetalle(
                consorcio_id=cid,
                expensa_id=e.id,
                rubro=d.rubro,
                clase_prorrateo_id=d.clase_prorrateo_id,
                departamento_origen_id=d.departamento_origen_id,
                concepto=d.concepto,
                monto=d.monto,
            ))
        db.add(MovimientoCuenta(
            consorcio_id=cid,
            departamento_id=exp.departamento_id,
            fecha=hoy,
            tipo=TipoMovimiento.expensa_emitida,
            descripcion=f"Expensa {periodo}",
            monto=exp.monto_primer_vencimiento,
            expensa_id=e.id,
        ))

        # Cada unidad se entera de su propia expensa: una por departamento,
        # no un aviso genérico "se cerró el período".
        emitir(
            db, EXPENSA_EMITIDA,
            consorcio_id=cid,
            contexto={
                "periodo": periodo,
                "monto": exp.monto_primer_vencimiento,
                "vencimiento": preview.fecha_primer_vencimiento.isoformat(),
            },
            actor_usuario_id=user.id,
            departamento_id=exp.departamento_id,
            tareas=tareas,
        )

    cerrado = PeriodoCerrado(
        periodo=periodo,
        consorcio_id=cid,
        cerrado_por_usuario_id=user.id,
        total_expensado=preview.total_expensado,
        total_intereses=preview.total_intereses,
        cantidad_expensas=len(preview.expensas),
    )
    db.add(cerrado)
    db.commit()
    db.refresh(cerrado)
    return cerrado


@router.post(
    "/{periodo}/enviar-pdfs",
    response_model=EnviarPdfsOut,
    status_code=200,
    summary="Enviar boletas PDF por email a los deptos del período",
)
def enviar_pdfs_periodo(
    periodo: str,
    payload: EnviarPdfsIn,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
    _cid: int = Depends(get_consorcio_activo),
) -> EnviarPdfsOut:
    # 1. Buscar expensas del período
    expensas = list(db.scalars(
        select(Expensa).where(
            Expensa.periodo == periodo,
            Expensa.consorcio_id == _cid,
        )
    ).all())
    if not expensas:
        raise HTTPException(404, f"No hay expensas para el período {periodo}.")

    # 2. Si NO está cerrado y NO confirmó, 409
    cerrado = db.get(PeriodoCerrado, (periodo, _cid)) is not None
    if not cerrado and not payload.confirmar_sin_cerrar:
        raise HTTPException(
            status_code=409,
            detail=f"El período {periodo} no está cerrado. Para enviar igual, reenviá con confirmar_sin_cerrar=true.",
        )

    # 3. Iterar expensas y enviar
    enviados = 0
    errores: list[ErrorEnvioOut] = []
    for exp in expensas:
        # Resolver emails del depto: usuarios con rol=departamento de ese depto
        usuarios = list(db.scalars(
            select(Usuario).where(
                Usuario.departamento_id == exp.departamento_id,
                Usuario.rol == Rol.departamento,
            )
        ).all())
        emails = [u.email for u in usuarios if u.email]
        if not emails:
            errores.append(ErrorEnvioOut(
                depto_id=exp.departamento_id,
                email=None,
                motivo="Sin destinatarios (depto sin usuarios)",
            ))
            continue

        try:
            pdf = generar_pdf_boleta(exp, db)
        except Exception as e:
            errores.append(ErrorEnvioOut(
                depto_id=exp.departamento_id,
                email=", ".join(emails),
                motivo=f"Error generando PDF: {e}",
            ))
            continue

        subject = f"Boleta de expensa — {periodo}"
        body = (
            f"Estimado/a vecino/a,\n\n"
            f"Adjuntamos la boleta de expensas correspondiente al período {periodo}.\n\n"
            f"Saludos cordiales,\nLa administración."
        )
        attachment = (f"expensa-{periodo}-depto-{exp.departamento_id}.pdf", pdf, "application/pdf")

        # Enviar a cada email del depto (un mail por destinatario)
        for em in emails:
            ok = enviar_email(to=em, subject=subject, body=body, attachments=[attachment])
            if ok:
                enviados += 1
            else:
                errores.append(ErrorEnvioOut(
                    depto_id=exp.departamento_id,
                    email=em,
                    motivo="Error de envío SMTP (ver logs)",
                ))

    return EnviarPdfsOut(
        enviados=enviados,
        fallaron=len(errores),
        errores=errores,
    )
