_HABER_NUEVO = {
    "nombre": "Premio Producción",
    "tipo": "monto_fijo",
    "valor_default": 50000.0,
    "orden": 99,
}


# ---------------------------------------------------------------------------
# GET /haberes
# ---------------------------------------------------------------------------


def test_listar_haberes_sin_token_devuelve_401(client):
    r = client.get("/haberes")
    assert r.status_code == 401


def test_listar_haberes_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/haberes", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_haberes_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/haberes", headers=headers_admin)
    assert r.status_code == 200
    nombres = {h["nombre"] for h in r.json()}
    assert "Básico Test" in nombres


def test_listar_haberes_ordenados(client, headers_admin):
    r = client.get("/haberes", headers=headers_admin)
    ordenes = [h["orden"] for h in r.json()]
    assert ordenes == sorted(ordenes)


# ---------------------------------------------------------------------------
# POST /haberes
# ---------------------------------------------------------------------------


def test_crear_haber_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/haberes", json=_HABER_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Premio Producción"
    assert body["activo"] is True


def test_crear_haber_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/haberes", json=_HABER_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_haber_nombre_duplicado_devuelve_409(client, headers_admin):
    payload = dict(_HABER_NUEVO, nombre="Básico Test")
    r = client.post("/haberes", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_haber_tipo_invalido_devuelve_400(client, headers_admin):
    payload = dict(_HABER_NUEVO, tipo="invalido")
    r = client.post("/haberes", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_haber_valor_negativo_devuelve_400(client, headers_admin):
    payload = dict(_HABER_NUEVO, valor_default=-10)
    r = client.post("/haberes", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /haberes/{id}
# ---------------------------------------------------------------------------


def test_obtener_haber_existente_devuelve_200(client, headers_admin):
    r = client.get("/haberes/940", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Básico Test"


def test_obtener_haber_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/haberes/9999", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /haberes/{id}
# ---------------------------------------------------------------------------


def test_patch_haber_actualiza_valor(client, headers_admin):
    r = client.patch("/haberes/940", json={"valor_default": 105.0}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["valor_default"] == 105.0


def test_patch_haber_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/haberes/9999", json={"valor_default": 1}, headers=headers_admin)
    assert r.status_code == 404


def test_patch_haber_desactiva(client, headers_admin):
    r = client.patch("/haberes/940", json={"activo": False}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False


# ---------------------------------------------------------------------------
# DELETE /haberes/{id} — soft-delete siempre
# ---------------------------------------------------------------------------


def test_delete_haber_es_soft_delete(client, headers_admin):
    r = client.delete("/haberes/940", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    # Sigue existiendo.
    r2 = client.get("/haberes/940", headers=headers_admin)
    assert r2.status_code == 200


def test_delete_haber_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/haberes/9999", headers=headers_admin)
    assert r.status_code == 404
