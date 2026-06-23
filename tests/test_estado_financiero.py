"""Tests del dashboard /estado-financiero."""


def test_estado_financiero_sin_token_401(client):
    r = client.get("/estado-financiero")
    assert r.status_code == 401


def test_estado_financiero_depto_403(client, headers_depto_a):
    r = client.get("/estado-financiero", headers=headers_depto_a)
    assert r.status_code == 403


def test_estado_financiero_admin_200_estructura(client, headers_admin):
    r = client.get("/estado-financiero", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "cajas" in body
    assert "total" in body
    assert "ultimos_movimientos" in body
    assert isinstance(body["cajas"], list)


def test_estado_financiero_excluye_cajas_inactivas(client, headers_admin):
    p = client.post(
        "/cajas",
        json={"nombre": "Caja Inactiva EF", "tipo": "banco", "saldo_inicial": 5000},
        headers=headers_admin
    ).json()
    client.patch(f"/cajas/{p['id']}", json={"activa": False}, headers=headers_admin)
    r = client.get("/estado-financiero", headers=headers_admin).json()
    ids = [c["id"] for c in r["cajas"]]
    assert p["id"] not in ids


def test_estado_financiero_total_es_suma_de_saldos(client, headers_admin):
    a = client.post(
        "/cajas",
        json={"nombre": "EF A", "tipo": "banco", "saldo_inicial": 1000},
        headers=headers_admin
    ).json()
    b = client.post(
        "/cajas",
        json={"nombre": "EF B", "tipo": "efectivo", "saldo_inicial": 500},
        headers=headers_admin
    ).json()
    r = client.get("/estado-financiero", headers=headers_admin).json()
    cajas_propias = [c for c in r["cajas"] if c["id"] in [a["id"], b["id"]]]
    assert sum(c["saldo_actual"] for c in cajas_propias) == 1500
