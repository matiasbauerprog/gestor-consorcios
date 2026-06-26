"""Router de reportes (lectura) — Fase 6b.

Acceso: admin + representante + departamento. Solo GET.
"""
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user
from ..database import get_db
from ..models import ConfiguracionConsorcio
from ..pdf import (
    generar_pdf_estado_financiero,
    generar_pdf_gastos_periodo,
    generar_pdf_lista_proveedores,
    generar_pdf_morosos,
)
from ..reportes import (
    calcular_estado_financiero,
    calcular_gastos_del_periodo,
    calcular_lista_proveedores,
    calcular_morosos,
)
from ..schemas import (
    EstadoFinancieroReporteOut,
    GastosDelPeriodoReporteOut,
    ItemMorosoOut,
    ItemProveedorOut,
)

router = APIRouter(prefix="/reportes", tags=["Reportes"])


# === Morosos ===

@router.get("/morosos", response_model=list[ItemMorosoOut])
def listar_morosos(
    solo_deudores: bool = True,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_morosos(db, solo_deudores=solo_deudores)


@router.get("/morosos/pdf")
def pdf_morosos(
    solo_deudores: bool = True,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    items = calcular_morosos(db, solo_deudores=solo_deudores)
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_morosos(items, date.today(), config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="morosos.pdf"'},
    )


# === Estado financiero ===

@router.get("/estado-financiero", response_model=EstadoFinancieroReporteOut)
def obtener_estado_financiero(
    fecha_corte: date | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_estado_financiero(db, fecha_corte or date.today())


@router.get("/estado-financiero/pdf")
def pdf_estado_financiero(
    fecha_corte: date | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    rep = calcular_estado_financiero(db, fecha_corte or date.today())
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_estado_financiero(rep, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="estado-financiero.pdf"'},
    )


# === Gastos del período ===

@router.get("/gastos/{periodo}", response_model=GastosDelPeriodoReporteOut)
def obtener_gastos_del_periodo(
    periodo: str,
    rubro: str | None = None,
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_gastos_del_periodo(db, periodo, rubro=rubro, proveedor_id=proveedor_id)


@router.get("/gastos/{periodo}/pdf")
def pdf_gastos_periodo(
    periodo: str,
    rubro: str | None = None,
    proveedor_id: int | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    rep = calcular_gastos_del_periodo(db, periodo, rubro=rubro, proveedor_id=proveedor_id)
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_gastos_periodo(rep, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="gastos-{periodo}.pdf"'},
    )


# === Lista de proveedores ===

@router.get("/proveedores", response_model=list[ItemProveedorOut])
def listar_proveedores(
    anio: int = date.today().year,
    periodo: str | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
):
    return calcular_lista_proveedores(db, anio=anio, periodo=periodo)


@router.get("/proveedores/pdf")
def pdf_proveedores(
    anio: int = date.today().year,
    periodo: str | None = None,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(get_current_user),
) -> Response:
    items = calcular_lista_proveedores(db, anio=anio, periodo=periodo)
    config = db.get(ConfiguracionConsorcio, 1)
    pdf = generar_pdf_lista_proveedores(items, anio, config)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="proveedores-{anio}.pdf"'},
    )
