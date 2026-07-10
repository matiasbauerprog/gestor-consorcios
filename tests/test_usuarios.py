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


def test_listar_usuarios_scope_multitenant(client, dos_consorcios):
    # Admin de c1 solo debe ver usuarios de su consorcio (admin1, depto_a, depto_b, repre).
    # No debe ver admin2 ni depto_c2 aunque estén en la misma DB.
    r = client.get("/usuarios", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert emails == {
        "admin@test.local",
        "a@test.local",
        "b@test.local",
        "repre@test.local",
    }
    assert "admin_c2@test.local" not in emails
    assert "depto_c2@test.local" not in emails


def test_listar_usuarios_scope_admin_c2(client, dos_consorcios):
    # Admin de c2 solo ve usuarios de c2: admin2 y depto_c2.
    r = client.get("/usuarios", headers=dos_consorcios["headers_admin_c2"])
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert emails == {"admin_c2@test.local", "depto_c2@test.local"}


def test_listar_usuarios_incluye_activa_true_por_default(client, headers_admin):
    r = client.get("/usuarios", headers=headers_admin)
    assert r.status_code == 200
    for u in r.json():
        assert u["activa"] is True


def test_crear_usuario_fuerza_must_change_password(client, headers_admin):
    payload = {
        "email": "recien-creado@test.local",
        "password": "pass-inicial-1234",
        "rol": "departamento",
        "departamento_id": 1,
    }
    r = client.post("/usuarios", json=payload, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["must_change_password"] is True


# ---------------------------------------------------------------------------
# PATCH /usuarios/{id}/estado — suspender/reactivar
# ---------------------------------------------------------------------------


def test_patch_estado_sin_token_devuelve_401(client):
    r = client.patch("/usuarios/2/estado", json={"activa": False})
    assert r.status_code == 401


def test_patch_estado_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.patch("/usuarios/3/estado", json={"activa": False}, headers=headers_depto_a)
    assert r.status_code == 403


def test_patch_estado_como_representante_devuelve_403(client, headers_representante):
    r = client.patch("/usuarios/2/estado", json={"activa": False}, headers=headers_representante)
    assert r.status_code == 403


def test_patch_estado_suspende_usuario(client, headers_admin):
    r = client.patch("/usuarios/2/estado", json={"activa": False}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is False


def test_patch_estado_reactiva_usuario(client, headers_admin, db_session):
    from backend.models import Usuario
    u = db_session.get(Usuario, 2)
    u.activa = False
    db_session.commit()

    r = client.patch("/usuarios/2/estado", json={"activa": True}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["activa"] is True


def test_patch_estado_usuario_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/usuarios/9999/estado", json={"activa": False}, headers=headers_admin)
    assert r.status_code == 404


def test_patch_estado_body_invalido_devuelve_400(client, headers_admin):
    r = client.patch("/usuarios/2/estado", json={}, headers=headers_admin)
    assert r.status_code == 400


def test_patch_estado_no_puede_cambiar_usuario_de_otro_consorcio(client, dos_consorcios):
    # Admin de c1 intenta suspender al depto de c2 → 404 (no lo ve).
    r = client.patch(
        "/usuarios/7/estado",
        json={"activa": False},
        headers=dos_consorcios["headers_admin_c1"],
    )
    assert r.status_code == 404


def test_patch_estado_admin_no_puede_suspenderse_a_si_mismo(client, headers_admin):
    r = client.patch("/usuarios/1/estado", json={"activa": False}, headers=headers_admin)
    assert r.status_code == 400
    assert r.json()["detail"] == "no_puede_suspenderse_a_si_mismo"


# ---------------------------------------------------------------------------
# DELETE /usuarios/{id}
# ---------------------------------------------------------------------------


def test_delete_sin_token_devuelve_401(client):
    r = client.delete("/usuarios/2")
    assert r.status_code == 401


def test_delete_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.delete("/usuarios/3", headers=headers_depto_a)
    assert r.status_code == 403


def test_delete_como_representante_devuelve_403(client, headers_representante):
    r = client.delete("/usuarios/2", headers=headers_representante)
    assert r.status_code == 403


def test_delete_usuario_inexistente_devuelve_404(client, headers_admin):
    r = client.delete("/usuarios/9999", headers=headers_admin)
    assert r.status_code == 404


def test_delete_usuario_sin_actividad_devuelve_204(client, headers_admin, db_session):
    # Depto B (id=3) no tiene reservas en el seed, así que se puede borrar.
    from backend.models import Usuario
    r = client.delete("/usuarios/3", headers=headers_admin)
    assert r.status_code == 204
    assert db_session.get(Usuario, 3) is None


def test_delete_usuario_con_reserva_devuelve_409(client, headers_admin):
    # Depto A (id=2) tiene la reserva del seed (id=400).
    r = client.delete("/usuarios/2", headers=headers_admin)
    assert r.status_code == 409
    assert r.json()["detail"] == "usuario_con_actividad"


def test_delete_admin_no_puede_eliminarse_a_si_mismo(client, headers_admin):
    r = client.delete("/usuarios/1", headers=headers_admin)
    assert r.status_code == 400
    assert r.json()["detail"] == "no_puede_eliminarse_a_si_mismo"


def test_delete_no_puede_borrar_usuario_de_otro_consorcio(client, dos_consorcios):
    r = client.delete("/usuarios/7", headers=dos_consorcios["headers_admin_c1"])
    assert r.status_code == 404


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
