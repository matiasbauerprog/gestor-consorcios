# ---------------------------------------------------------------------------
# GET /proveedores
# ---------------------------------------------------------------------------


def test_listar_proveedores_sin_token_devuelve_401(client):
    r = client.get("/proveedores")
    assert r.status_code == 401


def test_listar_proveedores_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/proveedores", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_proveedores_default_solo_activos(client, headers_admin):
    r = client.get("/proveedores", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert all(p["activo"] is True for p in data)
    cuits = {p["cuit"] for p in data}
    assert "30-12345678-9" in cuits


def test_listar_proveedores_inactivos_via_query(client, headers_admin):
    # Desactivamos el del seed.
    client.delete("/proveedores/600", headers=headers_admin)

    # Por default no aparece.
    r = client.get("/proveedores", headers=headers_admin)
    cuits = {p["cuit"] for p in r.json()}
    assert "30-12345678-9" not in cuits

    # Con ?activo=false aparece.
    r2 = client.get("/proveedores?activo=false", headers=headers_admin)
    cuits2 = {p["cuit"] for p in r2.json()}
    assert "30-12345678-9" in cuits2


# ---------------------------------------------------------------------------
# POST /proveedores
# ---------------------------------------------------------------------------


_PROV_NUEVO = {
    "razon_social": "Nuevo Proveedor SRL",
    "nombre_fantasia": "NP",
    "cuit": "30-55555555-5",
    "direccion": "Av. Siempreviva 742",
}


def test_crear_proveedor_sin_token_devuelve_401(client):
    r = client.post("/proveedores", json=_PROV_NUEVO)
    assert r.status_code == 401


def test_crear_proveedor_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/proveedores", json=_PROV_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_proveedor_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/proveedores", json=_PROV_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["razon_social"] == "Nuevo Proveedor SRL"
    assert body["cuit"] == "30-55555555-5"
    assert body["activo"] is True


def test_crear_proveedor_cuit_duplicado_devuelve_409(client, headers_admin):
    r = client.post(
        "/proveedores",
        json={"razon_social": "Otro", "cuit": "30-12345678-9"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_proveedor_cuit_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/proveedores",
        json={"razon_social": "X", "cuit": "ABC"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /proveedores/{id}
# ---------------------------------------------------------------------------


def test_obtener_proveedor_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/proveedores/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_proveedor_existente_devuelve_200(client, headers_admin):
    r = client.get("/proveedores/600", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["cuit"] == "30-12345678-9"


# ---------------------------------------------------------------------------
# PATCH /proveedores/{id}
# ---------------------------------------------------------------------------


def test_patch_proveedor_cambia_razon_social(client, headers_admin):
    r = client.patch(
        "/proveedores/600",
        json={"razon_social": "Proveedor Renombrado SA"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["razon_social"] == "Proveedor Renombrado SA"
    # cuit no editable.
    assert r.json()["cuit"] == "30-12345678-9"


def test_patch_proveedor_cuit_en_body_es_ignorado(client, headers_admin):
    r = client.patch(
        "/proveedores/600",
        json={"cuit": "99-99999999-9", "direccion": "Nueva dir"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["cuit"] == "30-12345678-9"


def test_patch_proveedor_reactivar(client, headers_admin):
    client.delete("/proveedores/600", headers=headers_admin)
    r = client.patch("/proveedores/600", json={"activo": True}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is True


def test_patch_proveedor_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/proveedores/9999",
        json={"razon_social": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /proveedores/{id} — soft-delete siempre
# ---------------------------------------------------------------------------


def test_delete_proveedor_es_soft_delete(client, headers_admin):
    r = client.delete("/proveedores/600", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    # Sigue existiendo.
    r2 = client.get("/proveedores/600", headers=headers_admin)
    assert r2.status_code == 200
    assert r2.json()["activo"] is False


def test_delete_proveedor_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/proveedores/9999", headers=headers_admin)
    assert r.status_code == 404
