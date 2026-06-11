# ---------------------------------------------------------------------------
# GET /departamentos
# ---------------------------------------------------------------------------


def test_listar_departamentos_sin_token_devuelve_401(client):
    r = client.get("/departamentos")
    assert r.status_code == 401


def test_listar_departamentos_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.get("/departamentos", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_departamentos_como_representante_devuelve_403(client, headers_representante):
    r = client.get("/departamentos", headers=headers_representante)
    assert r.status_code == 403


def test_listar_departamentos_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/departamentos", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    codigos = {d["codigo"] for d in data}
    assert codigos == {"UF-1A", "UF-2B"}


# ---------------------------------------------------------------------------
# POST /departamentos
# ---------------------------------------------------------------------------


_DEPTO_NUEVO = {"codigo": "UF-3C", "descripcion": "Piso 3, Unidad C"}


def test_crear_depto_sin_token_devuelve_401(client):
    r = client.post("/departamentos", json=_DEPTO_NUEVO)
    assert r.status_code == 401


def test_crear_depto_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post("/departamentos", json=_DEPTO_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_depto_como_representante_devuelve_403(client, headers_representante):
    r = client.post("/departamentos", json=_DEPTO_NUEVO, headers=headers_representante)
    assert r.status_code == 403


def test_crear_depto_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/departamentos", json=_DEPTO_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["codigo"] == "UF-3C"
    assert body["descripcion"] == "Piso 3, Unidad C"
    assert isinstance(body["id"], int)


def test_crear_depto_aparece_en_listado(client, headers_admin):
    client.post("/departamentos", json=_DEPTO_NUEVO, headers=headers_admin)
    r = client.get("/departamentos", headers=headers_admin)
    codigos = {d["codigo"] for d in r.json()}
    assert "UF-3C" in codigos


def test_crear_depto_codigo_duplicado_devuelve_409(client, headers_admin):
    # UF-1A ya existe en el seed.
    r = client.post(
        "/departamentos",
        json={"codigo": "UF-1A", "descripcion": "Otro"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_depto_sin_descripcion_es_201(client, headers_admin):
    r = client.post("/departamentos", json={"codigo": "UF-9Z"}, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["descripcion"] is None


def test_crear_depto_sin_codigo_devuelve_400(client, headers_admin):
    r = client.post(
        "/departamentos",
        json={"descripcion": "Sin código"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_depto_codigo_vacio_devuelve_400(client, headers_admin):
    r = client.post(
        "/departamentos",
        json={"codigo": "", "descripcion": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /departamentos/{id}
# ---------------------------------------------------------------------------


def test_patch_depto_sin_token_devuelve_401(client):
    r = client.patch("/departamentos/1", json={"descripcion": "x"})
    assert r.status_code == 401


def test_patch_depto_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.patch("/departamentos/1", json={"descripcion": "x"}, headers=headers_depto_a)
    assert r.status_code == 403


def test_patch_depto_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/departamentos/9999",
        json={"descripcion": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_patch_depto_actualiza_descripcion(client, headers_admin):
    r = client.patch(
        "/departamentos/1",
        json={"descripcion": "Depto A — renovado"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["descripcion"] == "Depto A — renovado"
    # codigo no editable: queda igual.
    assert r.json()["codigo"] == "UF-1A"


def test_patch_depto_codigo_en_body_es_ignorado(client, headers_admin):
    # El schema DepartamentoActualizar no define `codigo` — Pydantic ignora campos
    # desconocidos por defecto, así que el patch no debe modificarlo.
    r = client.patch(
        "/departamentos/1",
        json={"codigo": "UF-HACK", "descripcion": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["codigo"] == "UF-1A"


def test_patch_depto_body_vacio_es_noop(client, headers_admin):
    r = client.patch("/departamentos/1", json={}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["codigo"] == "UF-1A"


def test_crear_depto_y_usar_para_expensa_y_usuario(client, headers_admin):
    # Integración: el departamento recién creado debe poder usarse en endpoints
    # que validan FK contra `departamentos` (ej. crear expensa).
    creado = client.post(
        "/departamentos",
        json={"codigo": "UF-4D", "descripcion": "Test integración"},
        headers=headers_admin,
    ).json()
    r = client.post(
        "/expensas",
        json={
            "departamento_id": creado["id"],
            "periodo": "2026-07",
            "monto": 50000.0,
            "fecha_vencimiento": "2026-08-10",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["departamento_id"] == creado["id"]
