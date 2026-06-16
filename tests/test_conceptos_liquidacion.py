_CONCEPTO_NUEVO = {
    "nombre": "FATERYH Test",
    "tipo": "contribucion",
    "porcentaje": 8.535,
    "proveedor_id": 600,
    "orden": 20,
}


# ---------------------------------------------------------------------------
# GET /conceptos-liquidacion
# ---------------------------------------------------------------------------


def test_listar_conceptos_sin_token_devuelve_401(client):
    r = client.get("/conceptos-liquidacion")
    assert r.status_code == 401


def test_listar_conceptos_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/conceptos-liquidacion", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_conceptos_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/conceptos-liquidacion", headers=headers_admin)
    assert r.status_code == 200
    nombres = {c["nombre"] for c in r.json()}
    assert "Jubilación Test" in nombres


# ---------------------------------------------------------------------------
# POST /conceptos-liquidacion
# ---------------------------------------------------------------------------


def test_crear_concepto_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/conceptos-liquidacion", json=_CONCEPTO_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["nombre"] == "FATERYH Test"


def test_crear_concepto_nombre_duplicado_devuelve_409(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, nombre="Jubilación Test")
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_concepto_porcentaje_fuera_de_rango_devuelve_400(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, porcentaje=150)
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_concepto_proveedor_inexistente_devuelve_404(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, proveedor_id=9999)
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_concepto_sin_proveedor_es_201(client, headers_admin):
    payload = dict(_CONCEPTO_NUEVO, proveedor_id=None)
    r = client.post("/conceptos-liquidacion", json=payload, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["proveedor_id"] is None


# ---------------------------------------------------------------------------
# PATCH, DELETE
# ---------------------------------------------------------------------------


def test_patch_concepto_actualiza_porcentaje(client, headers_admin):
    r = client.patch("/conceptos-liquidacion/950", json={"porcentaje": 12.0}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["porcentaje"] == 12.0


def test_patch_concepto_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/conceptos-liquidacion/9999", json={"porcentaje": 1}, headers=headers_admin)
    assert r.status_code == 404


def test_delete_concepto_es_soft_delete(client, headers_admin):
    r = client.delete("/conceptos-liquidacion/950", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False


def test_delete_concepto_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/conceptos-liquidacion/9999", headers=headers_admin)
    assert r.status_code == 404
