from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import get_db
from ..models import Consorcio, Rol
from ..schemas import ConfiguracionConsorcioActualizar, ConfiguracionConsorcioOut

router = APIRouter(prefix="/configuracion", tags=["Configuración"])

# En este plan A, todavía no tenemos get_consorcio_activo (llega en Task 22).
# Adaptamos manteniendo el comportamiento single-tenant: siempre operamos sobre
# el consorcio id=1 (el Demo adoptado por la migración). Después del Plan A el
# resolver X-Consorcio-Id reemplaza esta constante.
_CONSORCIO_ID = 1


def _consorcio_a_configuracion_out(c: Consorcio) -> dict:
    return {
        "id": c.id,
        "consorcio_nombre": c.nombre,
        "consorcio_domicilio": c.consorcio_domicilio,
        "consorcio_cuit": c.consorcio_cuit,
        "consorcio_convenio_suterh": c.consorcio_convenio_suterh,
        "admin_nombre": c.admin_nombre,
        "admin_domicilio": c.admin_domicilio,
        "admin_email": c.admin_email,
        "admin_telefono": c.admin_telefono,
        "admin_cuit": c.admin_cuit,
        "admin_rpa": c.admin_rpa,
        "admin_situacion_fiscal": c.admin_situacion_fiscal,
        "banco_titular": c.banco_titular,
        "banco_nombre": c.banco_nombre,
        "banco_sucursal": c.banco_sucursal,
        "banco_numero_cuenta": c.banco_numero_cuenta,
        "banco_cbu": c.banco_cbu,
        "banco_alias": c.banco_alias,
        "dia_primer_vencimiento": c.dia_primer_vencimiento,
        "dias_entre_vencimientos": c.dias_entre_vencimientos,
        "recargo_segundo_vencimiento_pct": c.recargo_segundo_vencimiento_pct,
        "tasa_interes_mensual_pct": c.tasa_interes_mensual_pct,
        "caja_default_pagos_id": c.caja_default_pagos_id,
        "reportes_visibles_a_depto": c.reportes_visibles_a_depto,
    }


@router.get(
    "",
    response_model=ConfiguracionConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener configuración del consorcio (singleton)",
)
def obtener_configuracion(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    c = db.get(Consorcio, _CONSORCIO_ID)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La configuración del consorcio no fue inicializada.",
        )
    return _consorcio_a_configuracion_out(c)


@router.put(
    "",
    response_model=ConfiguracionConsorcioOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar configuración del consorcio (singleton)",
)
def actualizar_configuracion(
    payload: ConfiguracionConsorcioActualizar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
):
    c = db.get(Consorcio, _CONSORCIO_ID)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La configuración del consorcio no fue inicializada.",
        )

    datos = payload.model_dump()
    # Mapear consorcio_nombre → nombre; el resto de campos son 1:1.
    c.nombre = datos.pop("consorcio_nombre")
    for campo, valor in datos.items():
        setattr(c, campo, valor)

    db.commit()
    db.refresh(c)
    return _consorcio_a_configuracion_out(c)
