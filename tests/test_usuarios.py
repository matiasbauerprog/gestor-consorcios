from tests.conftest import TEST_PASSWORD


# ---------------------------------------------------------------------------
# GET /usuarios
# ---------------------------------------------------------------------------


def test_listar_usuarios_sin_token_devuelve_401(client):
    r = client.get("/usuarios")
    assert r.status_code == 401


def test_listar_usuarios_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.get("/usuarios", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_usuarios_como_representante_devuelve_403(client, headers_representante):
    r = client.get("/usuarios", headers=headers_representante)
    assert r.status_code == 403


def test_listar_usuarios_como_admin_devuelve_seed(client, headers_admin):
    r = client.get("/usuarios", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 4
    emails = {u["email"] for u in data}
    assert emails == {
        "admin@test.local",
        "a@test.local",
        "b@test.local",
        "repre@test.local",
    }


def test_listar_usuarios_no_incluye_password_hash(client, headers_admin):
    r = client.get("/usuarios", headers=headers_admin)
    for usuario in r.json():
        assert "password_hash" not in usuario
        assert "password" not in usuario


# ---------------------------------------------------------------------------
# POST /usuarios — happy paths
# ---------------------------------------------------------------------------


_USUARIO_DEPTO_NUEVO = {
    "email": "nuevo-depto@test.local",
    "password": "pass-segura-1234",
    "rol": "departamento",
    "departamento_id": 1,
}

_USUARIO_REPRE_NUEVO = {
    "email": "nuevo-repre@test.local",
    "password": "pass-segura-1234",
    "rol": "representante",
}


def test_crear_usuario_sin_token_devuelve_401(client):
    r = client.post("/usuarios", json=_USUARIO_DEPTO_NUEVO)
    assert r.status_code == 401


def test_crear_usuario_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post("/usuarios", json=_USUARIO_DEPTO_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_usuario_como_representante_devuelve_403(client, headers_representante):
    r = client.post("/usuarios", json=_USUARIO_DEPTO_NUEVO, headers=headers_representante)
    assert r.status_code == 403


def test_crear_usuario_departamento_devuelve_201(client, headers_admin):
    r = client.post("/usuarios", json=_USUARIO_DEPTO_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "nuevo-depto@test.local"
    assert body["rol"] == "departamento"
    assert body["departamento_id"] == 1
    assert isinstance(body["id"], int)
    # La respuesta no debe filtrar credenciales.
    assert "password" not in body
    assert "password_hash" not in body


def test_crear_usuario_representante_devuelve_201(client, headers_admin):
    r = client.post("/usuarios", json=_USUARIO_REPRE_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["rol"] == "representante"
    assert body["departamento_id"] is None


def test_crear_usuario_administracion_devuelve_201(client, headers_admin):
    payload = {
        "email": "otro-admin@test.local",
        "password": "pass-segura-1234",
        "rol": "administracion",
    }
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["rol"] == "administracion"


def test_crear_usuario_nuevo_puede_loguearse(client, headers_admin):
    client.post("/usuarios", json=_USUARIO_DEPTO_NUEVO, headers=headers_admin)
    r = client.post(
        "/auth/login",
        json={"email": "nuevo-depto@test.local", "password": "pass-segura-1234"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["rol"] == "departamento"
    assert r.json()["user"]["departamento_id"] == 1


# ---------------------------------------------------------------------------
# POST /usuarios — validaciones rol↔depto
# ---------------------------------------------------------------------------


def test_crear_usuario_departamento_sin_depto_id_devuelve_400(client, headers_admin):
    payload = {
        "email": "x@test.local",
        "password": "pass-segura-1234",
        "rol": "departamento",
    }
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_usuario_admin_con_depto_id_devuelve_400(client, headers_admin):
    payload = {
        "email": "x@test.local",
        "password": "pass-segura-1234",
        "rol": "administracion",
        "departamento_id": 1,
    }
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_usuario_representante_con_depto_id_devuelve_400(client, headers_admin):
    payload = {
        "email": "x@test.local",
        "password": "pass-segura-1234",
        "rol": "representante",
        "departamento_id": 1,
    }
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /usuarios — otros errores
# ---------------------------------------------------------------------------


def test_crear_usuario_depto_inexistente_devuelve_404(client, headers_admin):
    payload = {**_USUARIO_DEPTO_NUEVO, "departamento_id": 9999}
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 404


def test_crear_usuario_email_duplicado_devuelve_409(client, headers_admin):
    payload = {**_USUARIO_DEPTO_NUEVO, "email": "a@test.local"}
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 409


def test_crear_usuario_password_corta_devuelve_400(client, headers_admin):
    payload = {**_USUARIO_DEPTO_NUEVO, "password": "corta"}
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_usuario_rol_invalido_devuelve_400(client, headers_admin):
    payload = {**_USUARIO_DEPTO_NUEVO, "rol": "superadmin"}
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 400


def test_crear_usuario_body_incompleto_devuelve_400(client, headers_admin):
    r = client.post(
        "/usuarios",
        json={"email": "x@test.local"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /usuarios/{id}
# ---------------------------------------------------------------------------


def test_patch_usuario_sin_token_devuelve_401(client):
    r = client.patch("/usuarios/2", json={"email": "x@test.local"})
    assert r.status_code == 401


def test_patch_usuario_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.patch(
        "/usuarios/2",
        json={"email": "x@test.local"},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_patch_usuario_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/usuarios/9999",
        json={"email": "x@test.local"},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_patch_usuario_actualiza_email(client, headers_admin):
    r = client.patch(
        "/usuarios/2",
        json={"email": "nuevo-email@test.local"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["email"] == "nuevo-email@test.local"


def test_patch_usuario_email_nuevo_permite_login(client, headers_admin):
    client.patch(
        "/usuarios/2",
        json={"email": "nuevo-email@test.local"},
        headers=headers_admin,
    )
    # La password no cambió, sigue funcionando.
    r = client.post(
        "/auth/login",
        json={"email": "nuevo-email@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200


def test_patch_usuario_email_duplicado_devuelve_409(client, headers_admin):
    # Renombrar usuario 2 al email del usuario 3 → conflicto.
    r = client.patch(
        "/usuarios/2",
        json={"email": "b@test.local"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_patch_usuario_mismo_email_es_noop(client, headers_admin):
    # Patch al mismo email no debe disparar 409 espurio.
    r = client.patch(
        "/usuarios/2",
        json={"email": "a@test.local"},
        headers=headers_admin,
    )
    assert r.status_code == 200


def test_patch_usuario_cambiar_departamento_id(client, headers_admin):
    # User 2 está en depto 1; lo movemos al depto 2.
    r = client.patch(
        "/usuarios/2",
        json={"departamento_id": 2},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 2


def test_patch_usuario_depto_inexistente_devuelve_404(client, headers_admin):
    r = client.patch(
        "/usuarios/2",
        json={"departamento_id": 9999},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_patch_usuario_promover_repre_a_depto_requiere_depto_id(client, headers_admin):
    # User 4 (repre, sin depto). Cambiar solo rol → estado inconsistente → 400.
    r = client.patch(
        "/usuarios/4",
        json={"rol": "departamento"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_patch_usuario_promover_repre_a_depto_con_depto_id_funciona(client, headers_admin):
    # User 4 (repre, sin depto) → departamento + departamento_id en el mismo PATCH.
    r = client.patch(
        "/usuarios/4",
        json={"rol": "departamento", "departamento_id": 1},
        headers=headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rol"] == "departamento"
    assert body["departamento_id"] == 1


def test_patch_usuario_demover_depto_a_admin_requiere_limpiar_depto_id(client, headers_admin):
    # User 2 (depto, depto_id=1). Cambiar solo rol → estado inconsistente → 400.
    r = client.patch(
        "/usuarios/2",
        json={"rol": "administracion"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_patch_usuario_demover_depto_a_admin_con_depto_id_null_funciona(client, headers_admin):
    r = client.patch(
        "/usuarios/2",
        json={"rol": "administracion", "departamento_id": None},
        headers=headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rol"] == "administracion"
    assert body["departamento_id"] is None


def test_patch_usuario_body_vacio_es_noop(client, headers_admin):
    r = client.patch("/usuarios/2", json={}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["email"] == "a@test.local"
    assert r.json()["rol"] == "departamento"


def test_patch_usuario_no_acepta_cambio_de_password(client, headers_admin):
    # El schema UsuarioActualizar no incluye `password`. Pydantic la ignora.
    # La password sigue siendo la original.
    client.patch(
        "/usuarios/2",
        json={"password": "esto-no-debe-aplicarse"},
        headers=headers_admin,
    )
    r = client.post(
        "/auth/login",
        json={"email": "a@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200
