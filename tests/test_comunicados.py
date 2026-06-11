# ---------------------------------------------------------------------------
# GET /comunicados
# ---------------------------------------------------------------------------


def test_listar_comunicados_sin_token_devuelve_401(client):
    r = client.get("/comunicados")
    assert r.status_code == 401


def test_listar_comunicados_admin_devuelve_200(client, headers_admin):
    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == 200
    assert data[0]["titulo"] == "Bienvenida"
    assert data[0]["autor_id"] == 1


def test_listar_comunicados_departamento_devuelve_200(client, headers_depto_a):
    r = client.get("/comunicados", headers=headers_depto_a)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_listar_comunicados_representante_devuelve_200(client, headers_representante):
    r = client.get("/comunicados", headers=headers_representante)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_listar_comunicados_orden_por_fecha_desc(client, headers_admin):
    # Crear 2 comunicados nuevos; el más reciente debe venir primero.
    client.post(
        "/comunicados",
        json={"titulo": "Segundo", "cuerpo": "x"},
        headers=headers_admin,
    )
    client.post(
        "/comunicados",
        json={"titulo": "Tercero", "cuerpo": "y"},
        headers=headers_admin,
    )
    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200
    titulos = [c["titulo"] for c in r.json()]
    # El último creado primero (orden por fecha_publicacion desc, id desc).
    assert titulos[0] == "Tercero"
    assert titulos[1] == "Segundo"
    assert titulos[2] == "Bienvenida"


def test_listar_comunicados_omite_los_eliminados(client, headers_admin, db_session):
    from datetime import datetime, timezone
    from backend.models import Comunicado

    # Marcar el comunicado sembrado (id=200) como eliminado.
    db_session.get(Comunicado, 200).eliminado_at = datetime.now(timezone.utc)
    db_session.commit()

    r = client.get("/comunicados", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# POST /comunicados
# ---------------------------------------------------------------------------


_PAYLOAD_OK = {"titulo": "Corte de agua", "cuerpo": "Mañana de 9 a 12."}


def test_crear_comunicado_sin_token_devuelve_401(client):
    r = client.post("/comunicados", json=_PAYLOAD_OK)
    assert r.status_code == 401


def test_crear_comunicado_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post("/comunicados", json=_PAYLOAD_OK, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_comunicado_como_representante_devuelve_403(client, headers_representante):
    r = client.post("/comunicados", json=_PAYLOAD_OK, headers=headers_representante)
    assert r.status_code == 403


def test_crear_comunicado_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/comunicados", json=_PAYLOAD_OK, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["titulo"] == "Corte de agua"
    assert body["cuerpo"] == "Mañana de 9 a 12."
    # autor_id viene del token (admin id=1), NO del body.
    assert body["autor_id"] == 1
    assert isinstance(body["id"], int)
    assert "fecha_publicacion" in body


def test_crear_comunicado_ignora_autor_id_del_body(client, headers_admin):
    r = client.post(
        "/comunicados",
        json={**_PAYLOAD_OK, "autor_id": 9999},
        headers=headers_admin,
    )
    assert r.status_code == 201
    # autor_id se asigna desde el token (=1), ignora el body.
    assert r.json()["autor_id"] == 1


def test_crear_comunicado_titulo_vacio_devuelve_400(client, headers_admin):
    r = client.post(
        "/comunicados",
        json={"titulo": "", "cuerpo": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_comunicado_cuerpo_vacio_devuelve_400(client, headers_admin):
    r = client.post(
        "/comunicados",
        json={"titulo": "x", "cuerpo": ""},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_comunicado_body_incompleto_devuelve_400(client, headers_admin):
    r = client.post(
        "/comunicados",
        json={"titulo": "Solo titulo"},
        headers=headers_admin,
    )
    assert r.status_code == 400
