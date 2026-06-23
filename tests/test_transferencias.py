"""Tests de POST/GET /transferencias-caja."""
from datetime import date


def _crear_caja(client, headers, nombre):
    return client.post(
        "/cajas", json={"nombre": nombre, "tipo": "banco", "saldo_inicial": 1000},
        headers=headers
    ).json()


def test_transferencia_genera_dos_movimientos(client, headers_admin):
    a = _crear_caja(client, headers_admin, "Origen A T6")
    b = _crear_caja(client, headers_admin, "Destino B T6")
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": b["id"],
        "monto": 300, "fecha": date.today().isoformat(),
        "descripcion": "Test transfer",
    }, headers=headers_admin)
    assert r.status_code == 201

    cajas = client.get("/cajas", headers=headers_admin).json()
    nueva_a = next(c for c in cajas if c["id"] == a["id"])
    nueva_b = next(c for c in cajas if c["id"] == b["id"])
    assert nueva_a["saldo_actual"] == 700
    assert nueva_b["saldo_actual"] == 1300


def test_transferencia_misma_caja_400(client, headers_admin):
    a = _crear_caja(client, headers_admin, "Solo Una T6")
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": a["id"],
        "monto": 100, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_admin)
    assert r.status_code == 400


def test_transferencia_monto_cero_400(client, headers_admin):
    a = _crear_caja(client, headers_admin, "A0 T6")
    b = _crear_caja(client, headers_admin, "B0 T6")
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": b["id"],
        "monto": 0, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_admin)
    assert r.status_code == 400


def test_transferencia_caja_inactiva_400(client, headers_admin):
    a = _crear_caja(client, headers_admin, "A inact T6")
    b = _crear_caja(client, headers_admin, "B inact T6")
    client.patch(f"/cajas/{a['id']}", json={"activa": False}, headers=headers_admin)
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": a["id"], "caja_destino_id": b["id"],
        "monto": 100, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_admin)
    assert r.status_code == 400


def test_transferencia_depto_403(client, headers_depto_a):
    r = client.post("/transferencias-caja", json={
        "caja_origen_id": 1, "caja_destino_id": 2,
        "monto": 100, "fecha": date.today().isoformat(), "descripcion": "x",
    }, headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_transferencias_admin_200(client, headers_admin):
    r = client.get("/transferencias-caja", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
