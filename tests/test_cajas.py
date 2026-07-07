"""Tests HTTP del router /cajas."""
from datetime import date

from backend.models import MovimientoCaja, TipoMovimientoCaja


def test_listar_cajas_sin_token_devuelve_401(client):
    r = client.get("/cajas")
    assert r.status_code == 401


def test_listar_cajas_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/cajas", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_cajas_como_admin_200(client, headers_admin):
    r = client.get("/cajas", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_crear_caja_admin_201(client, headers_admin):
    payload = {"nombre": "Caja Test Nueva", "tipo": "banco", "saldo_inicial": 5000}
    r = client.post("/cajas", json=payload, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Caja Test Nueva"
    assert body["tipo"] == "banco"
    assert body["saldo_inicial"] == 5000
    assert body["saldo_actual"] == 5000
    assert body["activa"] is True


def test_crear_caja_nombre_duplicado_400(client, headers_admin):
    payload = {"nombre": "Caja Duplicada", "tipo": "efectivo"}
    r1 = client.post("/cajas", json=payload, headers=headers_admin)
    assert r1.status_code == 201
    r2 = client.post("/cajas", json=payload, headers=headers_admin)
    assert r2.status_code == 400


def test_patch_caja_actualiza_nombre(client, headers_admin):
    p = client.post("/cajas", json={"nombre": "Original", "tipo": "otro"}, headers=headers_admin).json()
    r = client.patch(f"/cajas/{p['id']}", json={"nombre": "Renombrada"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Renombrada"


def test_delete_caja_sin_movimientos_204(client, headers_admin):
    p = client.post("/cajas", json={"nombre": "Borrable", "tipo": "otro"}, headers=headers_admin).json()
    r = client.delete(f"/cajas/{p['id']}", headers=headers_admin)
    assert r.status_code == 204


def test_delete_caja_con_movimientos_409(client, headers_admin, db_session):
    p = client.post("/cajas", json={"nombre": "Con movs", "tipo": "banco"}, headers=headers_admin).json()
    db_session.add(MovimientoCaja(consorcio_id=1, caja_id=p["id"], fecha=date.today(), tipo=TipoMovimientoCaja.ajuste,
        monto=100, descripcion="test ajuste"
    ))
    db_session.commit()
    r = client.delete(f"/cajas/{p['id']}", headers=headers_admin)
    assert r.status_code == 409


def test_saldo_actual_refleja_movimientos(client, headers_admin, db_session):
    p = client.post("/cajas", json={"nombre": "Saldo Test", "tipo": "banco", "saldo_inicial": 1000}, headers=headers_admin).json()
    caja_id = p["id"]
    db_session.add_all([
        MovimientoCaja(consorcio_id=1, caja_id=caja_id, fecha=date.today(), tipo=TipoMovimientoCaja.ingreso, monto=500, descripcion="x"),
        MovimientoCaja(consorcio_id=1, caja_id=caja_id, fecha=date.today(), tipo=TipoMovimientoCaja.egreso, monto=200, descripcion="x"),
        MovimientoCaja(consorcio_id=1, caja_id=caja_id, fecha=date.today(), tipo=TipoMovimientoCaja.ajuste, monto=-50, descripcion="x"),
    ])
    db_session.commit()
    r = client.get("/cajas", headers=headers_admin)
    cajas = r.json()
    nueva = next(c for c in cajas if c["id"] == caja_id)
    # 1000 + 500 - 200 - 50 = 1250
    assert nueva["saldo_actual"] == 1250
