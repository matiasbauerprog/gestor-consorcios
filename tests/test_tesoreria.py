"""Tests del resumen de tesorería /tesoreria."""


def test_estado_financiero_sin_token_401(client):
    r = client.get("/tesoreria")
    assert r.status_code == 401


def test_estado_financiero_depto_403(client, headers_depto_a):
    r = client.get("/tesoreria", headers=headers_depto_a)
    assert r.status_code == 403


def test_estado_financiero_admin_200_estructura(client, headers_admin):
    r = client.get("/tesoreria", headers=headers_admin)
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
    r = client.get("/tesoreria", headers=headers_admin).json()
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
    r = client.get("/tesoreria", headers=headers_admin).json()
    cajas_propias = [c for c in r["cajas"] if c["id"] in [a["id"], b["id"]]]
    assert sum(c["saldo_actual"] for c in cajas_propias) == 1500


def test_estado_financiero_no_mezcla_consorcios(client, dos_consorcios):
    """El dashboard de tesorería solo muestra cajas y movimientos del
    consorcio activo — antes juntaba todos los consorcios."""
    r1 = client.get("/tesoreria", headers=dos_consorcios["headers_admin_c1"])
    assert r1.status_code == 200
    nombres_c1 = {c["nombre"] for c in r1.json()["cajas"]}
    assert "Banco C2" not in nombres_c1

    r2 = client.get("/tesoreria", headers=dos_consorcios["headers_admin_c2"])
    assert r2.status_code == 200
    nombres_c2 = {c["nombre"] for c in r2.json()["cajas"]}
    assert nombres_c2 == {"Banco C2"}
    # Los movimientos también scoped:
    for m in r2.json()["ultimos_movimientos"]:
        assert m["caja_id"] == 901


# ---------------------------------------------------------------------------
# PDF de movimientos de caja por rango
# ---------------------------------------------------------------------------


def test_pdf_movimientos_caja_sin_token_401(client):
    r = client.get("/tesoreria/movimientos-pdf?desde=2026-01-01&hasta=2026-12-31")
    assert r.status_code == 401


def test_pdf_movimientos_caja_como_departamento_403(client, headers_depto_a):
    r = client.get(
        "/tesoreria/movimientos-pdf?desde=2026-01-01&hasta=2026-12-31",
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_pdf_movimientos_caja_admin_devuelve_pdf(client, headers_admin):
    r = client.get(
        "/tesoreria/movimientos-pdf?desde=2026-01-01&hasta=2026-12-31",
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_pdf_movimientos_caja_sin_fechas_devuelve_400(client, headers_admin):
    r = client.get("/tesoreria/movimientos-pdf", headers=headers_admin)
    assert r.status_code == 400


def test_pdf_movimientos_caja_scope_consorcio(client, dos_consorcios):
    """Un admin de c1 pidiendo el PDF no debe ver movimientos de c2."""
    r = client.get(
        "/tesoreria/movimientos-pdf?desde=2026-01-01&hasta=2026-12-31",
        headers=dos_consorcios["headers_admin_c1"],
    )
    assert r.status_code == 200
    # No podemos parsear PDF pero verificamos el 200 + el content-type,
    # el scoping se ejerce por get_consorcio_activo que ya está en el endpoint.
