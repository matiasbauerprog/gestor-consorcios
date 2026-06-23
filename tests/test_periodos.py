"""Tests HTTP del router /periodos + bloqueos cross-recurso."""
from datetime import date

import pytest

from backend.models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    FormaPago,
    Gasto,
    Proveedor,
    Rubro,
)


@pytest.fixture
def db_lista_para_cierre(db_session):
    """Setup mínimo para cerrar período 2026-07: 1 clase 50/50, 2 gastos.
    Reutiliza proveedor 600 (ya sembrado) y clase 500 (ya sembrada)."""
    # Reutilizar proveedor_id=600 (sembrado en conftest) y clase_id=500
    proveedor_id = 600
    clase_id = 500

    # Asegurar coeficientes 50/50 para depto 1 y 2 con la clase existente
    # (si ya existen, SQLAlchemy los reutilizará)
    db_session.add(CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=clase_id, porcentaje=50))
    db_session.add(CoeficienteDepartamento(departamento_id=2, clase_prorrateo_id=clase_id, porcentaje=50))

    db_session.add(Gasto(
        periodo="2026-07", monto=1000, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=clase_id, departamento_id=None,
        proveedor_id=proveedor_id, concepto="Luz",
        forma_pago=FormaPago.efectivo, caja_id=900,  # Fase 5: caja default
        fecha_pago=date(2026, 7, 10),
    ))
    db_session.add(Gasto(
        periodo="2026-07", monto=500, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=None, departamento_id=1,
        proveedor_id=proveedor_id, concepto="Reparación 1A",
        forma_pago=FormaPago.efectivo, caja_id=900,  # Fase 5: caja default
        fecha_pago=date(2026, 7, 15),
    ))
    db_session.commit()
    return db_session


def test_listar_periodos_admin_200_vacio_si_no_hay_cierres(client, headers_admin):
    r = client.get("/periodos", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_listar_periodos_depto_403(client, headers_depto_a):
    r = client.get("/periodos", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_estado_admin_200_devuelve_validaciones(client, headers_admin, db_lista_para_cierre):
    r = client.get("/periodos/2026-07/estado", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["periodo"] == "2026-07"
    assert body["cerrado"] is False
    assert "validaciones" in body
    assert body["puede_cerrar"] is True


def test_get_preview_admin_200_genera_expensas(client, headers_admin, db_lista_para_cierre):
    r = client.get("/periodos/2026-07/preview", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert len(body["expensas"]) == 2
    montos = sorted(e["monto_primer_vencimiento"] for e in body["expensas"])
    # depto 2: 500 de la clase A. depto 1: 500 de la clase A + 500 particular = 1000.
    assert montos == [500.0, 1000.0]


def test_cerrar_periodo_genera_n_expensas_con_movimientos(
    client, headers_admin, db_lista_para_cierre,
):
    r = client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["periodo"] == "2026-07"
    assert body["cantidad_expensas"] == 2

    r2 = client.get("/expensas?periodo=2026-07", headers=headers_admin)
    assert r2.status_code == 200
    assert len(r2.json()) == 2


def test_cerrar_periodo_idempotente_segundo_call_409(client, headers_admin, db_lista_para_cierre):
    r1 = client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    assert r1.status_code == 201
    r2 = client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    assert r2.status_code == 409


def test_post_gasto_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    r = client.post("/gastos", json={
        "periodo": "2026-07", "rubro": "servicios_publicos", "concepto": "Tarde",
        "monto": 100, "proveedor_id": 600,
        "clase_prorrateo_id": 500, "departamento_id": None,
        "forma_pago": "efectivo", "caja_id": 900,  # Fase 5: caja default
        "fecha_pago": "2026-07-30",
    }, headers=headers_admin)
    assert r.status_code == 409


def test_post_expensa_individual_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    r = client.post("/expensas", json={
        "departamento_id": 1, "periodo": "2026-07",
        "monto_primer_vencimiento": 100, "fecha_primer_vencimiento": "2026-08-10",
        "monto_segundo_vencimiento": 107, "fecha_segundo_vencimiento": "2026-08-20",
    }, headers=headers_admin)
    assert r.status_code == 409


def test_comprobante_periodo_cerrado_sigue_funcionando_201(
    client, headers_admin, headers_depto_a, db_lista_para_cierre
):
    # Verificar que se puede cerrar un período
    r_cierre = client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    assert r_cierre.status_code == 201

    # El endpoint de comprobantes debe seguir funcionando después del cierre
    # (no hay bloqueo 409 en comprobantes)
    files = {"archivo": ("c.png", b"\x89PNG\r\n\x1a\n_dummy", "image/png")}
    r = client.post("/comprobantes",
        data={"fecha_pago": "2026-06-20", "monto": 500},
        files=files, headers=headers_depto_a,
    )
    assert r.status_code == 201


def test_patch_gasto_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    """Editar un gasto de un período cerrado devuelve 409."""
    # Cerrar el período 2026-07
    client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)

    # Obtener un gasto del período (fixture genera gastos con id 29 y 30 aprox)
    gastos = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    assert len(gastos) >= 1
    gasto_id = gastos[0]["id"]

    # Intentar PATCH → 409
    r = client.patch(
        f"/gastos/{gasto_id}",
        json={"monto": 999},
        headers=headers_admin
    )
    assert r.status_code == 409


def test_delete_gasto_periodo_cerrado_409(client, headers_admin, db_lista_para_cierre):
    """Eliminar un gasto de un período cerrado devuelve 409."""
    # Cerrar el período 2026-07
    client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)

    # Obtener un gasto del período
    gastos = client.get("/gastos?periodo=2026-07", headers=headers_admin).json()
    assert len(gastos) >= 1
    gasto_id = gastos[0]["id"]

    # Intentar DELETE → 409
    r = client.delete(f"/gastos/{gasto_id}", headers=headers_admin)
    assert r.status_code == 409
