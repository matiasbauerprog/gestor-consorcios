from tests.conftest import TEST_PASSWORD


# ---------------------------------------------------------------------------
# POST /auth/login — happy paths
# ---------------------------------------------------------------------------


def test_login_admin_devuelve_200_con_token_y_user(client):
    r = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["token_type"] == "bearer"
    assert isinstance(body["expires_in"], int) and body["expires_in"] > 0
    assert body["user"]["id"] == 1
    assert body["user"]["email"] == "admin@test.local"
    assert body["user"]["rol"] == "administracion"
    assert body["user"]["departamento_id"] is None


def test_login_departamento_incluye_departamento_id(client):
    r = client.post(
        "/auth/login",
        json={"email": "a@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["rol"] == "departamento"
    assert body["user"]["departamento_id"] == 1


def test_login_representante_devuelve_200(client):
    r = client.post(
        "/auth/login",
        json={"email": "repre@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200
    assert r.json()["user"]["rol"] == "representante"


def test_login_token_obtenido_funciona_para_endpoints_protegidos(client):
    # Integración: login → usar el token devuelto contra /peticiones.
    r = client.post(
        "/auth/login",
        json={"email": "a@test.local", "password": TEST_PASSWORD},
    )
    token = r.json()["access_token"]

    r2 = client.get(
        "/peticiones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    # Depto A solo ve sus propias peticiones (id=10).
    data = r2.json()
    assert len(data) == 1
    assert data[0]["departamento_id"] == 1


# ---------------------------------------------------------------------------
# Credenciales inválidas (401)
# ---------------------------------------------------------------------------


def test_login_password_incorrecto_devuelve_401(client):
    r = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciales inválidas."


def test_login_email_inexistente_devuelve_401(client):
    r = client.post(
        "/auth/login",
        json={"email": "no-existe@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 401
    # Anti-enumeración: mismo mensaje que con password incorrecto.
    assert r.json()["detail"] == "Credenciales inválidas."


def test_login_no_filtra_existencia_por_mensaje(client):
    # Garantizamos que 401-password-malo y 401-email-inexistente devuelven
    # el mismo cuerpo: el atacante no puede distinguir si el email existe.
    r_bad_pwd = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "wrong"},
    )
    r_no_user = client.post(
        "/auth/login",
        json={"email": "ghost@test.local", "password": "wrong"},
    )
    assert r_bad_pwd.status_code == r_no_user.status_code == 401
    assert r_bad_pwd.json() == r_no_user.json()


# ---------------------------------------------------------------------------
# Body inválido (400)
# ---------------------------------------------------------------------------


def test_login_sin_email_devuelve_400(client):
    r = client.post("/auth/login", json={"password": TEST_PASSWORD})
    assert r.status_code == 400


def test_login_sin_password_devuelve_400(client):
    r = client.post("/auth/login", json={"email": "admin@test.local"})
    assert r.status_code == 400


def test_login_body_vacio_devuelve_400(client):
    r = client.post("/auth/login", json={})
    assert r.status_code == 400


def test_login_email_vacio_devuelve_400(client):
    r = client.post(
        "/auth/login",
        json={"email": "", "password": TEST_PASSWORD},
    )
    assert r.status_code == 400


def test_login_password_vacio_devuelve_400(client):
    r = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": ""},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


def _login(client, email: str = "admin@test.local") -> dict[str, str]:
    r = client.post(
        "/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_logout_sin_token_devuelve_401(client):
    r = client.post("/auth/logout")
    assert r.status_code == 401


def test_logout_token_invalido_devuelve_401(client):
    r = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert r.status_code == 401


def test_logout_con_token_valido_devuelve_204(client):
    headers = _login(client)
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 204
    # 204 no debe traer cuerpo.
    assert r.content == b""


def test_token_deslogueado_no_puede_acceder_a_endpoints_protegidos(client):
    headers = _login(client, "a@test.local")

    # Antes del logout: el token funciona contra /peticiones.
    r = client.get("/peticiones", headers=headers)
    assert r.status_code == 200

    # Logout: revoca el jti.
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 204

    # Después del logout: el mismo token debe ser rechazado.
    r = client.get("/peticiones", headers=headers)
    assert r.status_code == 401
    assert r.json()["detail"] == "Token revocado."


def test_logout_dos_veces_con_mismo_token_devuelve_401_la_segunda(client):
    headers = _login(client)

    r1 = client.post("/auth/logout", headers=headers)
    assert r1.status_code == 204

    # El segundo logout falla porque get_current_user ya rechaza el token.
    r2 = client.post("/auth/logout", headers=headers)
    assert r2.status_code == 401
    assert r2.json()["detail"] == "Token revocado."


def test_logout_no_afecta_otros_tokens_del_mismo_usuario(client):
    # Login dos veces → dos tokens distintos (jti distinto).
    headers_a = _login(client, "a@test.local")
    headers_b = _login(client, "a@test.local")
    assert headers_a["Authorization"] != headers_b["Authorization"]

    # Logout del primero.
    assert client.post("/auth/logout", headers=headers_a).status_code == 204

    # El primero queda revocado.
    assert client.get("/peticiones", headers=headers_a).status_code == 401

    # El segundo sigue siendo válido.
    r = client.get("/peticiones", headers=headers_b)
    assert r.status_code == 200


def test_logout_no_afecta_token_de_otro_usuario(client):
    headers_admin = _login(client, "admin@test.local")
    headers_depto = _login(client, "a@test.local")

    # Admin se desloguea.
    assert client.post("/auth/logout", headers=headers_admin).status_code == 204

    # Depto sigue pudiendo operar.
    r = client.get("/peticiones", headers=headers_depto)
    assert r.status_code == 200


def test_logout_y_login_de_nuevo_genera_jti_distinto(client):
    headers_1 = _login(client)
    client.post("/auth/logout", headers=headers_1)

    headers_2 = _login(client)
    # El nuevo token debe funcionar (jti distinto, no está en la blacklist).
    r = client.get("/peticiones", headers=headers_2)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /auth/cambiar-password
# ---------------------------------------------------------------------------


_NEW_PASSWORD = "nueva-pass-segura-2026"


def test_cambiar_password_sin_token_devuelve_401(client):
    r = client.post(
        "/auth/cambiar-password",
        json={"current_password": TEST_PASSWORD, "new_password": _NEW_PASSWORD},
    )
    assert r.status_code == 401


def test_cambiar_password_token_invalido_devuelve_401(client):
    r = client.post(
        "/auth/cambiar-password",
        json={"current_password": TEST_PASSWORD, "new_password": _NEW_PASSWORD},
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert r.status_code == 401


def test_cambiar_password_happy_path_devuelve_204(client):
    headers = _login(client)
    r = client.post(
        "/auth/cambiar-password",
        json={"current_password": TEST_PASSWORD, "new_password": _NEW_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 204
    assert r.content == b""


def test_cambiar_password_nueva_password_funciona_para_login(client):
    headers = _login(client, "a@test.local")
    assert (
        client.post(
            "/auth/cambiar-password",
            json={"current_password": TEST_PASSWORD, "new_password": _NEW_PASSWORD},
            headers=headers,
        ).status_code
        == 204
    )

    # La nueva password permite loguearse.
    r = client.post(
        "/auth/login",
        json={"email": "a@test.local", "password": _NEW_PASSWORD},
    )
    assert r.status_code == 200


def test_cambiar_password_vieja_password_deja_de_funcionar(client):
    headers = _login(client, "a@test.local")
    assert (
        client.post(
            "/auth/cambiar-password",
            json={"current_password": TEST_PASSWORD, "new_password": _NEW_PASSWORD},
            headers=headers,
        ).status_code
        == 204
    )

    # La password vieja ya no funciona en /auth/login.
    r = client.post(
        "/auth/login",
        json={"email": "a@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciales inválidas."


def test_cambiar_password_no_revoca_el_token_actual(client):
    headers = _login(client, "a@test.local")
    assert (
        client.post(
            "/auth/cambiar-password",
            json={"current_password": TEST_PASSWORD, "new_password": _NEW_PASSWORD},
            headers=headers,
        ).status_code
        == 204
    )

    # El token con el que cambió la pass sigue valiendo (sesión activa).
    r = client.get("/peticiones", headers=headers)
    assert r.status_code == 200


def test_cambiar_password_current_password_incorrecta_devuelve_401(client):
    headers = _login(client)
    r = client.post(
        "/auth/cambiar-password",
        json={"current_password": "pass-incorrecta", "new_password": _NEW_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "La contraseña actual es incorrecta."


def test_cambiar_password_current_password_incorrecta_no_modifica_nada(client):
    headers = _login(client, "a@test.local")
    client.post(
        "/auth/cambiar-password",
        json={"current_password": "pass-incorrecta", "new_password": _NEW_PASSWORD},
        headers=headers,
    )

    # La password original sigue funcionando.
    r = client.post(
        "/auth/login",
        json={"email": "a@test.local", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200


def test_cambiar_password_nueva_muy_corta_devuelve_400(client):
    headers = _login(client)
    r = client.post(
        "/auth/cambiar-password",
        json={"current_password": TEST_PASSWORD, "new_password": "corta"},
        headers=headers,
    )
    assert r.status_code == 400


def test_cambiar_password_body_sin_current_password_devuelve_400(client):
    headers = _login(client)
    r = client.post(
        "/auth/cambiar-password",
        json={"new_password": _NEW_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 400


def test_cambiar_password_body_sin_new_password_devuelve_400(client):
    headers = _login(client)
    r = client.post(
        "/auth/cambiar-password",
        json={"current_password": TEST_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 400


def test_cambiar_password_body_vacio_devuelve_400(client):
    headers = _login(client)
    r = client.post("/auth/cambiar-password", json={}, headers=headers)
    assert r.status_code == 400
