# ---------------------------------------------------------------------------
# GET /clases-prorrateo
# ---------------------------------------------------------------------------


def test_listar_clases_sin_token_devuelve_401(client):
    r = client.get("/clases-prorrateo")
    assert r.status_code == 401


def test_listar_clases_como_depto_devuelve_403(client, headers_depto_a):
    r = client.get("/clases-prorrateo", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_clases_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/clases-prorrateo", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    codigos = {c["codigo"] for c in data}
    assert "A" in codigos


# ---------------------------------------------------------------------------
# POST /clases-prorrateo
# ---------------------------------------------------------------------------


_CLASE_NUEVA = {"codigo": "B", "nombre": "Expensas extraordinarias", "descripcion": "Obras"}


def test_crear_clase_sin_token_devuelve_401(client):
    r = client.post("/clases-prorrateo", json=_CLASE_NUEVA)
    assert r.status_code == 401


def test_crear_clase_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post("/clases-prorrateo", json=_CLASE_NUEVA, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_clase_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/clases-prorrateo", json=_CLASE_NUEVA, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["codigo"] == "B"
    assert body["nombre"] == "Expensas extraordinarias"
    assert body["activa"] is True


def test_crear_clase_codigo_duplicado_devuelve_409(client, headers_admin):
    # "A" ya existe en el seed.
    r = client.post(
        "/clases-prorrateo",
        json={"codigo": "A", "nombre": "Otra"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_clase_sin_codigo_devuelve_400(client, headers_admin):
    r = client.post(
        "/clases-prorrateo",
        json={"nombre": "Sin código"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /clases-prorrateo/{id}
# ---------------------------------------------------------------------------


def test_obtener_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/clases-prorrateo/9999", headers=headers_admin)
    assert r.status_code == 404


def test_obtener_clase_existente_devuelve_200(client, headers_admin):
    r = client.get("/clases-prorrateo/500", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["codigo"] == "A"


# ---------------------------------------------------------------------------
# PATCH /clases-prorrateo/{id}
# ---------------------------------------------------------------------------


def test_patch_clase_cambia_nombre(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/500",
        json={"nombre": "Ordinarias - renombrada"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ordinarias - renombrada"
    # codigo no editable.
    assert r.json()["codigo"] == "A"


def test_patch_clase_desactiva(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/500",
        json={"activa": False},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["activa"] is False


def test_patch_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/9999",
        json={"nombre": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_patch_clase_codigo_en_body_es_ignorado(client, headers_admin):
    r = client.patch(
        "/clases-prorrateo/500",
        json={"codigo": "Z", "nombre": "X"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["codigo"] == "A"


# ---------------------------------------------------------------------------
# DELETE /clases-prorrateo/{id}
# ---------------------------------------------------------------------------


def test_delete_clase_sin_coeficientes_es_hard_delete(client, headers_admin):
    # Crear una clase nueva sin coeficientes asociados.
    creada = client.post(
        "/clases-prorrateo",
        json={"codigo": "X", "nombre": "Temporal"},
        headers=headers_admin,
    ).json()
    r = client.delete(f"/clases-prorrateo/{creada['id']}", headers=headers_admin)
    assert r.status_code == 204

    # Ya no existe.
    r2 = client.get(f"/clases-prorrateo/{creada['id']}", headers=headers_admin)
    assert r2.status_code == 404


def test_delete_clase_con_coeficientes_es_soft_delete(client, headers_admin, db_session):
    # Asociar un coeficiente a la clase A=500 vía PUT /departamentos/.../coeficientes
    # (este endpoint se prueba en su propio archivo; acá lo creamos directo en DB para
    # aislar el test).
    from backend.models import CoeficienteDepartamento
    db_session.add(
        CoeficienteDepartamento(departamento_id=1, clase_prorrateo_id=500, porcentaje=50.0)
    )
    db_session.commit()

    r = client.delete("/clases-prorrateo/500", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False

    # Sigue existiendo, solo desactivada.
    r2 = client.get("/clases-prorrateo/500", headers=headers_admin)
    assert r2.status_code == 200


def test_delete_clase_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/clases-prorrateo/9999", headers=headers_admin)
    assert r.status_code == 404
