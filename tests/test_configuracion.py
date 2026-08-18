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
    "dia_primer_vencimiento": 15,
    "dias_entre_vencimientos": 10,
    "recargo_segundo_vencimiento_pct": 7.0,
    "tasa_interes_mensual_pct": 3.0,
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


# ---------------------------------------------------------------------------
# Nuevos campos Fase 4 (vencimientos + intereses)
# ---------------------------------------------------------------------------


def test_get_configuracion_incluye_4_nuevos_campos(client, headers_admin):
    r = client.get("/configuracion", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "dia_primer_vencimiento" in body
    assert "dias_entre_vencimientos" in body
    assert "recargo_segundo_vencimiento_pct" in body
    assert "tasa_interes_mensual_pct" in body


def test_put_configuracion_dia_invalido_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["dia_primer_vencimiento"] = 30  # fuera de rango (>28)
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_put_configuracion_recargo_negativo_devuelve_400(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["recargo_segundo_vencimiento_pct"] = -1.0
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Nuevos campos Fase 5 (tesorería)
# ---------------------------------------------------------------------------


def test_get_configuracion_incluye_caja_default(client, headers_admin):
    """El GET incluye el campo caja_default_pagos_id (puede ser null si no fue seteado)."""
    r = client.get("/configuracion", headers=headers_admin)
    assert r.status_code == 200
    assert "caja_default_pagos_id" in r.json()


def test_put_configuracion_setear_caja_default(client, headers_admin):
    """PUT con caja_default_pagos_id válido lo persiste."""
    payload = dict(_PAYLOAD_VALIDO)
    payload["caja_default_pagos_id"] = 900  # caja sembrada en conftest
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["caja_default_pagos_id"] == 900


# ---------------------------------------------------------------------------
# Visibilidad de peticiones entre departamentos
# ---------------------------------------------------------------------------


def test_get_configuracion_incluye_visibilidad_de_peticiones(client, headers_admin):
    """Arranca en True: es el comportamiento que el sistema tuvo siempre."""
    r = client.get("/configuracion", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["peticiones_visibles_a_depto"] is True


def test_put_configuracion_apaga_visibilidad_de_peticiones(client, headers_admin):
    payload = dict(_PAYLOAD_VALIDO)
    payload["peticiones_visibles_a_depto"] = False
    r = client.put("/configuracion", json=payload, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["peticiones_visibles_a_depto"] is False

    r = client.get("/configuracion", headers=headers_admin)
    assert r.json()["peticiones_visibles_a_depto"] is False


def test_put_sin_el_campo_no_apaga_la_visibilidad(client, headers_admin):
    """Un PUT viejo (sin el campo nuevo) no debe apagar algo que nadie pidió
    apagar: por eso el default del schema de entrada es True y no False."""
    r = client.put("/configuracion", json=dict(_PAYLOAD_VALIDO), headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["peticiones_visibles_a_depto"] is True
