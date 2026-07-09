"""Tests del endpoint POST /periodos/{periodo}/enviar-pdfs."""
from datetime import date

import pytest

from backend.models import (
    CoeficienteDepartamento,
    Expensa,
    FormaPago,
    Gasto,
    PeriodoCerrado,
    Rubro,
)


def test_admin_envia_pdfs_periodo_cerrado(client, headers_admin, db_session):
    """Período cerrado: envía sin necesidad de confirmar."""
    # Setup: crear gastos y cerrar período
    proveedor_id = 600
    clase_id = 500

    db_session.add(CoeficienteDepartamento(consorcio_id=1, departamento_id=1, clase_prorrateo_id=clase_id, porcentaje=50
    ))
    db_session.add(CoeficienteDepartamento(consorcio_id=1, departamento_id=2, clase_prorrateo_id=clase_id, porcentaje=50
    ))
    db_session.add(Gasto(consorcio_id=1, periodo="2026-06", monto=1000, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=clase_id, departamento_id=None,
        proveedor_id=proveedor_id, concepto="Luz",
        forma_pago=FormaPago.efectivo, caja_id=900,
        fecha_pago=date(2026, 6, 10),
    ))
    db_session.commit()

    # Cerrar período
    r = client.post("/periodos/2026-06/cerrar", json={}, headers=headers_admin)
    assert r.status_code == 201

    # Ahora enviar PDFs
    r = client.post(
        "/periodos/2026-06/enviar-pdfs",
        json={"confirmar_sin_cerrar": False},
        headers=headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert "enviados" in body
    assert "fallaron" in body
    assert "errores" in body


def test_envio_periodo_no_cerrado_devuelve_409(client, headers_admin, db_session):
    """Sin confirmar y período no cerrado → 409."""
    # Crear expensa en período NO cerrado
    expensa = Expensa(consorcio_id=1, departamento_id=1, periodo="2030-12",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento=date(2030, 12, 10),
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento=date(2030, 12, 20),
        saldo_anterior=0,
    )
    db_session.add(expensa)
    db_session.commit()
    r = client.post(
        "/periodos/2030-12/enviar-pdfs",
        json={"confirmar_sin_cerrar": False},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_envio_periodo_no_cerrado_con_confirmar_ok(client, headers_admin, db_session):
    """Con confirmar_sin_cerrar=true, envía aunque no esté cerrado."""
    expensa = Expensa(consorcio_id=1, departamento_id=1, periodo="2031-01",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento=date(2031, 1, 10),
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento=date(2031, 1, 20),
        saldo_anterior=0,
    )
    db_session.add(expensa)
    db_session.commit()
    r = client.post(
        "/periodos/2031-01/enviar-pdfs",
        json={"confirmar_sin_cerrar": True},
        headers=headers_admin,
    )
    assert r.status_code == 200


def test_periodo_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/periodos/9999-12/enviar-pdfs",
        json={"confirmar_sin_cerrar": True},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_envio_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post(
        "/periodos/2026-05/enviar-pdfs",
        json={"confirmar_sin_cerrar": True},
        headers=headers_depto_a,
    )
    assert r.status_code == 403
