def test_listar_sin_token_devuelve_401(client):
    r = client.get("/peticiones")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_listar_token_invalido_devuelve_401(client):
    r = client.get("/peticiones", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_departamento_solo_ve_sus_peticiones(client, headers_depto_a):
    r = client.get("/peticiones", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["departamento_id"] == 1
    assert data[0]["titulo"] == "Filtración A"


def test_admin_ve_todas_las_peticiones(client, headers_admin):
    r = client.get("/peticiones", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    departamentos = {p["departamento_id"] for p in data}
    assert departamentos == {1, 2}


def test_representante_ve_todas_las_peticiones(client, headers_representante):
    r = client.get("/peticiones", headers=headers_representante)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_detalle_otro_depto_devuelve_403(client, headers_depto_a):
    # Petición id=11 pertenece a Depto B.
    r = client.get("/peticiones/11", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_detalle_propio_depto_devuelve_200(client, headers_depto_a):
    r = client.get("/peticiones/10", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 1


def test_get_detalle_admin_puede_ver_cualquier_peticion(client, headers_admin):
    r = client.get("/peticiones/11", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 2


def test_get_detalle_no_existente_devuelve_404(client, headers_admin):
    r = client.get("/peticiones/9999", headers=headers_admin)
    assert r.status_code == 404


def test_crear_peticion_como_departamento_201(client, headers_depto_a):
    r = client.post(
        "/peticiones",
        json={"titulo": "Caños ruidosos", "descripcion": "Baño"},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    # departamento_id viene del token, NO del cuerpo
    assert body["departamento_id"] == 1
    assert body["estado"] == "abierta"


def test_crear_peticion_ignora_departamento_id_del_body(client, headers_depto_a):
    # Intento malicioso: enviar departamento_id ajeno en el body.
    r = client.post(
        "/peticiones",
        json={"titulo": "Hackeo", "descripcion": "Intento", "departamento_id": 2},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    # Aun cuando vino "departamento_id": 2 en el body, se asigna desde el token (=1).
    assert r.json()["departamento_id"] == 1


def test_crear_peticion_como_admin_devuelve_403(client, headers_admin):
    r = client.post(
        "/peticiones",
        json={"titulo": "x", "descripcion": "y"},
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_crear_peticion_como_representante_devuelve_403(client, headers_representante):
    r = client.post(
        "/peticiones",
        json={"titulo": "x", "descripcion": "y"},
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_crear_peticion_sin_token_devuelve_401(client):
    r = client.post("/peticiones", json={"titulo": "x", "descripcion": "y"})
    assert r.status_code == 401


def test_crear_peticion_body_invalido_devuelve_400(client, headers_depto_a):
    r = client.post("/peticiones", json={"titulo": ""}, headers=headers_depto_a)
    assert r.status_code == 400
