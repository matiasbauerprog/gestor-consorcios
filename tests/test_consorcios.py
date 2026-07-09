"""Tests del router /consorcios (Plan D)."""


def _body_crear(nombre="Consorcio Nuevo", cuit="30-99999999-1"):
    return {
        "nombre": nombre,
        "consorcio_domicilio": "Av. Nueva 123",
        "consorcio_cuit": cuit,
        "consorcio_convenio_suterh": "0001",
        "usa_personal_propio": True,
        "admin_nombre": "Admin Nuevo",
        "admin_domicilio": "Oficina 5",
        "admin_email": "adm@nuevo.local",
        "admin_telefono": "11-5555-5555",
        "admin_cuit": "20-11111111-1",
        "admin_rpa": "0001",
        "admin_situacion_fiscal": "Monotributo",
        "banco_titular": "Consorcio Nuevo",
        "banco_nombre": "Banco Nuevo",
        "banco_sucursal": "001",
        "banco_numero_cuenta": "123-456789/0",
        "banco_cbu": "0000000000000000000001",
        "banco_alias": "consorcio.nuevo",
        "dia_primer_vencimiento": 10,
        "dias_entre_vencimientos": 10,
        "recargo_segundo_vencimiento_pct": 7.0,
        "tasa_interes_mensual_pct": 3.0,
        "reportes_visibles_a_depto": False,
    }


# ---------------------------------------------------------------------------
# GET /consorcios
# ---------------------------------------------------------------------------


def test_listar_consorcios_sin_token_devuelve_401(client):
    r = client.get("/consorcios")
    assert r.status_code == 401


def test_listar_consorcios_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/consorcios", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_consorcios_como_admin_devuelve_los_del_tenant(client, headers_admin):
    r = client.get("/consorcios", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert any(c["nombre"] == "Consorcio Test" for c in data)


def test_listar_consorcios_no_muestra_los_de_otra_administracion(
    client, dos_consorcios
):
    # Admin de c1 lista → solo ve el consorcio de su administración (id=1).
    r = client.get("/consorcios", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert 1 in ids
    assert 2 not in ids

    # Admin de c2 → solo ve el suyo (id=2).
    r2 = client.get("/consorcios", headers=dos_consorcios["headers_admin_c2"])
    ids2 = {c["id"] for c in r2.json()}
    assert 2 in ids2
    assert 1 not in ids2


# ---------------------------------------------------------------------------
# POST /consorcios
# ---------------------------------------------------------------------------


def test_post_consorcio_crea_y_genera_caja_default(client, headers_admin, db):
    r = client.post("/consorcios", json=_body_crear(), headers=headers_admin)
    assert r.status_code == 201
    out = r.json()
    assert out["nombre"] == "Consorcio Nuevo"
    assert out["administracion_id"] == 1
    assert out["caja_default_pagos_id"] is not None

    from backend.models import Caja
    caja = db.get(Caja, out["caja_default_pagos_id"])
    assert caja is not None
    assert caja.consorcio_id == out["id"]
    assert caja.nombre == "Banco principal"


def test_post_consorcio_cuit_duplicado_en_la_misma_admin_devuelve_409(
    client, headers_admin
):
    body = _body_crear(cuit="30-42424242-4")
    r1 = client.post("/consorcios", json=body, headers=headers_admin)
    assert r1.status_code == 201

    r2 = client.post("/consorcios", json=_body_crear(cuit="30-42424242-4"),
                     headers=headers_admin)
    assert r2.status_code == 409


def test_post_consorcio_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/consorcios", json=_body_crear(), headers=headers_depto_a)
    assert r.status_code == 403


def test_post_consorcio_body_incompleto_devuelve_400(client, headers_admin):
    r = client.post("/consorcios", json={"nombre": "X"}, headers=headers_admin)
    assert r.status_code == 400


def test_post_consorcio_persiste_usa_personal_propio(client, headers_admin):
    body = _body_crear(cuit="30-11223344-5")
    body["usa_personal_propio"] = False
    r = client.post("/consorcios", json=body, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["usa_personal_propio"] is False


# ---------------------------------------------------------------------------
# GET /consorcios/{id}
# ---------------------------------------------------------------------------


def test_get_consorcio_admin_del_tenant_devuelve_200(client, headers_admin):
    r = client.get("/consorcios/1", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["id"] == 1


def test_get_consorcio_ajeno_para_admin_devuelve_404(client, dos_consorcios):
    r = client.get(
        "/consorcios/2", headers=dos_consorcios["headers_admin_c1"]
    )
    assert r.status_code == 404


def test_get_consorcio_del_depto_propio_devuelve_200(client, headers_depto_a):
    r = client.get("/consorcios/1", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["id"] == 1


def test_get_consorcio_ajeno_para_depto_devuelve_404(client, dos_consorcios):
    # depto de c1 pide c2.
    r = client.get(
        "/consorcios/2", headers=dos_consorcios["headers_depto_c1"]
    )
    assert r.status_code == 404


def test_get_consorcio_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/consorcios/9999", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /consorcios/{id}
# ---------------------------------------------------------------------------


def test_patch_consorcio_cambia_nombre(client, headers_admin, db):
    r = client.patch(
        "/consorcios/1", json={"nombre": "Consorcio Renombrado"}, headers=headers_admin
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Consorcio Renombrado"


def test_patch_consorcio_ajeno_devuelve_404(client, dos_consorcios):
    r = client.patch(
        "/consorcios/2",
        json={"nombre": "hack"},
        headers=dos_consorcios["headers_admin_c1"],
    )
    assert r.status_code == 404


def test_patch_consorcio_como_depto_devuelve_403(client, headers_depto_a):
    r = client.patch(
        "/consorcios/1", json={"nombre": "hack"}, headers=headers_depto_a
    )
    assert r.status_code == 403


def test_patch_consorcio_caja_default_de_otro_consorcio_devuelve_400(
    client, headers_admin, dos_consorcios, db
):
    # dos_consorcios crea caja id=901 en consorcio 2.
    r = client.patch(
        "/consorcios/1",
        json={"caja_default_pagos_id": 901},
        headers=headers_admin,
    )
    assert r.status_code == 400
