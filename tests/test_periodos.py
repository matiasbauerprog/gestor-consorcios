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
    db_session.add(CoeficienteDepartamento(consorcio_id=1, departamento_id=1, clase_prorrateo_id=clase_id, porcentaje=50))
    db_session.add(CoeficienteDepartamento(consorcio_id=1, departamento_id=2, clase_prorrateo_id=clase_id, porcentaje=50))

    db_session.add(Gasto(consorcio_id=1, periodo="2026-07", monto=1000, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=clase_id, departamento_id=None,
        proveedor_id=proveedor_id, concepto="Luz",
        forma_pago=FormaPago.efectivo, caja_id=900,  # Fase 5: caja default
        fecha_pago=date(2026, 7, 10),
    ))
    db_session.add(Gasto(consorcio_id=1, periodo="2026-07", monto=500, rubro=Rubro.servicios_publicos,
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


# ---------------------------------------------------------------------------
# Multitenant: el cierre es por consorcio, no global
# ---------------------------------------------------------------------------


@pytest.fixture
def c2_lista_para_cierre(db_session, dos_consorcios):
    """Setup para cerrar 2026-07 en el consorcio 2: clase + coeficiente 100%
    para el depto 3 + un gasto."""
    clase_c2 = ClaseProrrateo(
        id=560, consorcio_id=2, codigo="A", nombre="Ordinarias c2", activa=True
    )
    db_session.add(clase_c2)
    db_session.add(Proveedor(
        id=660, consorcio_id=2, razon_social="Proveedor C2", cuit="30-66000000-6", activo=True
    ))
    db_session.flush()
    db_session.add(CoeficienteDepartamento(
        consorcio_id=2, departamento_id=3, clase_prorrateo_id=560, porcentaje=100
    ))
    db_session.add(Gasto(
        consorcio_id=2, periodo="2026-07", monto=2000, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=560, departamento_id=None,
        proveedor_id=660, concepto="Luz c2",
        forma_pago=FormaPago.efectivo, caja_id=901,
        fecha_pago=date(2026, 7, 10),
    ))
    db_session.commit()
    return dos_consorcios


def test_cierre_de_un_consorcio_no_bloquea_gastos_del_otro(
    client, headers_admin, db_lista_para_cierre, c2_lista_para_cierre,
):
    """c1 cierra 2026-07; el admin de c2 tiene que poder seguir cargando
    gastos en su propio 2026-07 (el cierre no es global)."""
    r = client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    assert r.status_code == 201

    r2 = client.post("/gastos", json={
        "periodo": "2026-07", "rubro": "servicios_publicos", "concepto": "Gas c2",
        "monto": 100, "clase_prorrateo_id": 560, "proveedor_id": 660,
        "forma_pago": "efectivo", "caja_id": 901, "fecha_pago": "2026-07-12",
    }, headers=c2_lista_para_cierre["headers_admin_c2"])
    assert r2.status_code == 201


def test_ambos_consorcios_pueden_cerrar_el_mismo_periodo(
    client, headers_admin, db_lista_para_cierre, c2_lista_para_cierre,
):
    r1 = client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    assert r1.status_code == 201

    r2 = client.post(
        "/periodos/2026-07/cerrar", json={},
        headers=c2_lista_para_cierre["headers_admin_c2"],
    )
    assert r2.status_code == 201

    # Cada uno registró SU cierre.
    l1 = client.get("/periodos", headers=headers_admin).json()
    l2 = client.get("/periodos", headers=c2_lista_para_cierre["headers_admin_c2"]).json()
    assert len(l1) == 1 and l1[0]["cantidad_expensas"] == 2
    assert len(l2) == 1 and l2[0]["cantidad_expensas"] == 1


def test_cierre_propio_sigue_bloqueando_gastos(client, headers_admin, db_lista_para_cierre):
    """Regresión: el cierre del propio consorcio sigue bloqueando con 409."""
    client.post("/periodos/2026-07/cerrar", json={}, headers=headers_admin)
    r = client.post("/gastos", json={
        "periodo": "2026-07", "rubro": "servicios_publicos", "concepto": "Tarde",
        "monto": 100, "clase_prorrateo_id": 500, "proveedor_id": 600,
        "forma_pago": "efectivo", "caja_id": 900, "fecha_pago": "2026-07-12",
    }, headers=headers_admin)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Notificación de expensa emitida al cerrar el período
# ---------------------------------------------------------------------------


def test_cerrar_periodo_notifica_la_expensa_a_cada_depto(client, headers_admin, db_session):
    from backend.models import (
        CoeficienteDepartamento, FormaPago, Gasto, Notificacion, Rubro,
    )

    db_session.add(CoeficienteDepartamento(
        consorcio_id=1, departamento_id=1, clase_prorrateo_id=500, porcentaje=50,
    ))
    db_session.add(CoeficienteDepartamento(
        consorcio_id=1, departamento_id=2, clase_prorrateo_id=500, porcentaje=50,
    ))
    db_session.add(Gasto(
        consorcio_id=1, periodo="2026-06", monto=1000, rubro=Rubro.servicios_publicos,
        clase_prorrateo_id=500, departamento_id=None, proveedor_id=600,
        concepto="Luz", forma_pago=FormaPago.efectivo, caja_id=900,
        fecha_pago=date(2026, 6, 10),
    ))
    db_session.commit()

    r = client.post("/periodos/2026-06/cerrar", json={}, headers=headers_admin)
    assert r.status_code == 201

    ns = db_session.query(Notificacion).filter_by(tipo="expensa_emitida").all()
    assert sorted(n.usuario_id for n in ns) == [2, 3]
    assert all("2026-06" in n.mensaje for n in ns)
