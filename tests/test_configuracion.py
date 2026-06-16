_PAYLOAD_VALIDO = {
    "consorcio_nombre": "Consorcio Editado",
    "consorcio_domicilio": "Av. Nueva 999",
    "consorcio_cuit": "30-88888888-8",
    "consorcio_convenio_suterh": "SUTERH-12345",
    "admin_nombre": "Admin Editado",
    "admin_domicilio": "Otra Calle 111",
    "admin_email": "nuevo@admin.local",
    "admin_telefono": "11-2222-3333",
    "admin_cuit": "20-22222222-2",
    "admin_rpa": "9999",
    "admin_situacion_fiscal": "Responsable Inscripto",
    "banco_titular": "Consorcio Editado",
    "banco_nombre": "Banco Nuevo",
    "banco_sucursal": "002",
    "banco_numero_cuenta": "111-2222222/3",
    "banco_cbu": "1111111111111111111111",
    "banco_alias": "CONSORCIO.NUEVO",
}


# ---------------------------------------------------------------------------
# GET /configuracion (admin + depto)
# ---------------------------------------------------------------------------


def test_get_configuracion_sin_token_devuelve_401(client):
    r = client.get("/configuracion")
    assert r.status_code == 401


def test_get_configuracion_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/configuracion", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["consorcio_nombre"] == "Consorcio Test"
    assert body["banco_cbu"] == "0000000000000000000000"


def test_get_configuracion_como_depto_devuelve_200(client, headers_depto_a):
    # Depto puede leer (necesita datos bancarios).
    r = client.get("/configuracion", headers=headers_depto_a)
    assert r.status_code == 200


def test_get_configuracion_como_representante_devuelve_200(client, headers_representante):
    r = client.get("/configuracion", headers=headers_representante)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# PUT /configuracion (solo admin)
# ---------------------------------------------------------------------------


def test_put_configuracion_sin_token_devuelve_401(client):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO)
    assert r.status_code == 401


def test_put_configuracion_como_depto_devuelve_403(client, headers_depto_a):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO, headers=headers_depto_a)
    assert r.status_code == 403


def test_put_configuracion_como_representante_devuelve_403(client, headers_representante):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO, headers=headers_representante)
    assert r.status_code == 403


def test_put_configuracion_como_admin_actualiza(client, headers_admin):
    r = client.put("/configuracion", json=_PAYLOAD_VALIDO, headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["consorcio_nombre"] == "Consorcio Editado"
    assert body["banco_cbu"] == "1111111111111111111111"

    # Verificar persistencia.
    r2 = client.get("/configuracion", headers=headers_admin)
    assert r2.json()["consorcio_nombre"] == "Consorcio Editado"


def test_put_configuracion_cuit_invalido_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["consorcio_cuit"] = "ABC"
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_configuracion_cbu_largo_invalido_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["banco_cbu"] = "123"  # CBU debe tener exactamente 22 chars
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_configuracion_email_corto_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["admin_email"] = "x"
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400
