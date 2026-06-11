# ---------------------------------------------------------------------------
# GET /amenities/{id}/disponibilidad
# ---------------------------------------------------------------------------


def test_disponibilidad_sin_token_devuelve_401(client):
    r = client.get("/amenities/300/disponibilidad?desde=2026-07-01&hasta=2026-07-31")
    assert r.status_code == 401


def test_disponibilidad_amenity_inexistente_devuelve_404(client, headers_admin):
    r = client.get(
        "/amenities/9999/disponibilidad?desde=2026-07-01&hasta=2026-07-31",
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_disponibilidad_desde_posterior_a_hasta_devuelve_400(client, headers_admin):
    r = client.get(
        "/amenities/300/disponibilidad?desde=2026-07-31&hasta=2026-07-01",
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_disponibilidad_desde_invalido_devuelve_400(client, headers_admin):
    r = client.get(
        "/amenities/300/disponibilidad?desde=no-es-fecha&hasta=2026-07-31",
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_disponibilidad_sin_parametros_obligatorios_devuelve_400(client, headers_admin):
    r = client.get("/amenities/300/disponibilidad", headers=headers_admin)
    assert r.status_code == 400


def test_disponibilidad_admin_ve_reservas_en_rango(client, headers_admin):
    # Seed: SUM tiene una reserva el 2026-07-15 14:00–17:00.
    r = client.get(
        "/amenities/300/disponibilidad?desde=2026-07-01&hasta=2026-07-31",
        headers=headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["amenity_id"] == 300
    assert len(body["bloques"]) == 1
    bloque = body["bloques"][0]
    assert bloque["disponible"] is False
    assert bloque["inicio"].startswith("2026-07-15T14:00")
    assert bloque["fin"].startswith("2026-07-15T17:00")


def test_disponibilidad_departamento_puede_consultar(client, headers_depto_b):
    r = client.get(
        "/amenities/300/disponibilidad?desde=2026-07-01&hasta=2026-07-31",
        headers=headers_depto_b,
    )
    assert r.status_code == 200
    assert len(r.json()["bloques"]) == 1


def test_disponibilidad_representante_puede_consultar(client, headers_representante):
    r = client.get(
        "/amenities/300/disponibilidad?desde=2026-07-01&hasta=2026-07-31",
        headers=headers_representante,
    )
    assert r.status_code == 200


def test_disponibilidad_sin_reservas_devuelve_lista_vacia(client, headers_admin):
    # Laundry no tiene reservas.
    r = client.get(
        "/amenities/301/disponibilidad?desde=2026-07-01&hasta=2026-07-31",
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json() == {"amenity_id": 301, "bloques": []}


def test_disponibilidad_rango_fuera_de_reservas_existentes(client, headers_admin):
    # SUM tiene reserva en julio. Consultar enero → lista vacía.
    r = client.get(
        "/amenities/300/disponibilidad?desde=2026-01-01&hasta=2026-01-31",
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["bloques"] == []


# ---------------------------------------------------------------------------
# POST /amenities/{id}/reservas
# ---------------------------------------------------------------------------


_PAYLOAD_OK = {
    "inicio": "2026-08-10T18:00:00",
    "fin": "2026-08-10T22:00:00",
}


def test_reserva_sin_token_devuelve_401(client):
    r = client.post("/amenities/300/reservas", json=_PAYLOAD_OK)
    assert r.status_code == 401


def test_reserva_amenity_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/amenities/9999/reservas",
        json=_PAYLOAD_OK,
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_reserva_admin_devuelve_201(client, headers_admin):
    r = client.post("/amenities/300/reservas", json=_PAYLOAD_OK, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["amenity_id"] == 300
    # usuario_id NUNCA del body — viene del token (admin id=1).
    assert body["usuario_id"] == 1
    assert body["estado"] == "confirmada"
    assert isinstance(body["id"], int)


def test_reserva_departamento_devuelve_201(client, headers_depto_b):
    r = client.post(
        "/amenities/301/reservas",
        json=_PAYLOAD_OK,
        headers=headers_depto_b,
    )
    assert r.status_code == 201
    assert r.json()["usuario_id"] == 3


def test_reserva_representante_devuelve_201(client, headers_representante):
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": "2026-09-01T10:00:00", "fin": "2026-09-01T11:00:00"},
        headers=headers_representante,
    )
    assert r.status_code == 201
    assert r.json()["usuario_id"] == 4


def test_reserva_ignora_usuario_id_del_body(client, headers_admin):
    r = client.post(
        "/amenities/301/reservas",
        json={
            "inicio": "2026-08-11T10:00:00",
            "fin": "2026-08-11T11:00:00",
            "usuario_id": 9999,
        },
        headers=headers_admin,
    )
    assert r.status_code == 201
    # Se asigna desde el token (=1), ignora el body.
    assert r.json()["usuario_id"] == 1


# ---- Validación de fechas inconsistentes (400) ----


def test_reserva_inicio_posterior_a_fin_devuelve_400(client, headers_admin):
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-08-10T22:00:00", "fin": "2026-08-10T18:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_reserva_inicio_igual_a_fin_devuelve_400(client, headers_admin):
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-08-10T18:00:00", "fin": "2026-08-10T18:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_reserva_body_incompleto_devuelve_400(client, headers_admin):
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-08-10T18:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---- Anti-solapamiento (409). Reserva existente en SUM: 2026-07-15 14:00–17:00 ----


def test_reserva_solape_total_devuelve_409(client, headers_admin):
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T14:00:00", "fin": "2026-07-15T17:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_solape_parcial_inicio_devuelve_409(client, headers_admin):
    # Nueva 13–15 choca con 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T13:00:00", "fin": "2026-07-15T15:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_solape_parcial_fin_devuelve_409(client, headers_admin):
    # Nueva 16–18 choca con 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T16:00:00", "fin": "2026-07-15T18:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_contenida_dentro_de_existente_devuelve_409(client, headers_admin):
    # Nueva 15–16 está dentro de 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T15:00:00", "fin": "2026-07-15T16:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_contiene_a_existente_devuelve_409(client, headers_admin):
    # Nueva 13–18 contiene a 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T13:00:00", "fin": "2026-07-15T18:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_adyacente_antes_devuelve_201(client, headers_admin):
    # Nueva 11–14 termina justo cuando empieza la existente — no solapa.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T11:00:00", "fin": "2026-07-15T14:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 201


def test_reserva_adyacente_despues_devuelve_201(client, headers_admin):
    # Nueva 17–20 empieza justo cuando termina la existente — no solapa.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": "2026-07-15T17:00:00", "fin": "2026-07-15T20:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 201


def test_reserva_mismo_horario_otro_amenity_no_solapa(client, headers_admin):
    # Mismo horario que la reserva existente, pero amenity distinto.
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": "2026-07-15T14:00:00", "fin": "2026-07-15T17:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /amenities (acceso abierto a autenticados)
# ---------------------------------------------------------------------------


def test_listar_amenities_sin_token_devuelve_401(client):
    r = client.get("/amenities")
    assert r.status_code == 401


def test_listar_amenities_admin_devuelve_seed(client, headers_admin):
    r = client.get("/amenities", headers=headers_admin)
    assert r.status_code == 200
    nombres = {a["nombre"] for a in r.json()}
    assert nombres == {"SUM", "Laundry"}


def test_listar_amenities_departamento_puede_consultar(client, headers_depto_a):
    r = client.get("/amenities", headers=headers_depto_a)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /amenities (Administracion)
# ---------------------------------------------------------------------------


_AMENITY_NUEVO = {"nombre": "Parrilla", "descripcion": "Parrilla en azotea"}


def test_crear_amenity_sin_token_devuelve_401(client):
    r = client.post("/amenities", json=_AMENITY_NUEVO)
    assert r.status_code == 401


def test_crear_amenity_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post("/amenities", json=_AMENITY_NUEVO, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_amenity_como_representante_devuelve_403(client, headers_representante):
    r = client.post("/amenities", json=_AMENITY_NUEVO, headers=headers_representante)
    assert r.status_code == 403


def test_crear_amenity_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/amenities", json=_AMENITY_NUEVO, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Parrilla"
    assert body["descripcion"] == "Parrilla en azotea"
    assert isinstance(body["id"], int)


def test_crear_amenity_aparece_en_listado(client, headers_admin):
    client.post("/amenities", json=_AMENITY_NUEVO, headers=headers_admin)
    r = client.get("/amenities", headers=headers_admin)
    nombres = {a["nombre"] for a in r.json()}
    assert "Parrilla" in nombres


def test_crear_amenity_nombre_duplicado_devuelve_409(client, headers_admin):
    # SUM ya existe en el seed.
    r = client.post(
        "/amenities",
        json={"nombre": "SUM", "descripcion": "Otro SUM"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_amenity_sin_descripcion_es_201(client, headers_admin):
    r = client.post("/amenities", json={"nombre": "Bicicletero"}, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["descripcion"] is None


def test_crear_amenity_sin_nombre_devuelve_400(client, headers_admin):
    r = client.post("/amenities", json={"descripcion": "Sin nombre"}, headers=headers_admin)
    assert r.status_code == 400


def test_crear_amenity_se_puede_reservar_de_inmediato(client, headers_admin):
    creado = client.post("/amenities", json=_AMENITY_NUEVO, headers=headers_admin).json()
    r = client.post(
        f"/amenities/{creado['id']}/reservas",
        json={"inicio": "2026-09-10T10:00:00", "fin": "2026-09-10T12:00:00"},
        headers=headers_admin,
    )
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# PATCH /amenities/{id} (Administracion)
# ---------------------------------------------------------------------------


def test_patch_amenity_sin_token_devuelve_401(client):
    r = client.patch("/amenities/300", json={"descripcion": "x"})
    assert r.status_code == 401


def test_patch_amenity_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.patch("/amenities/300", json={"descripcion": "x"}, headers=headers_depto_a)
    assert r.status_code == 403


def test_patch_amenity_inexistente_devuelve_404(client, headers_admin):
    r = client.patch("/amenities/9999", json={"descripcion": "x"}, headers=headers_admin)
    assert r.status_code == 404


def test_patch_amenity_actualiza_descripcion(client, headers_admin):
    r = client.patch(
        "/amenities/300",
        json={"descripcion": "Salón de usos múltiples renovado"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["descripcion"] == "Salón de usos múltiples renovado"
    # El nombre no debe cambiar si no se envió.
    assert r.json()["nombre"] == "SUM"


def test_patch_amenity_actualiza_nombre(client, headers_admin):
    r = client.patch("/amenities/300", json={"nombre": "Salón SUM"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Salón SUM"


def test_patch_amenity_nombre_colisiona_con_otro_devuelve_409(client, headers_admin):
    # Intentar renombrar SUM (300) a "Laundry" (301) → conflicto.
    r = client.patch("/amenities/300", json={"nombre": "Laundry"}, headers=headers_admin)
    assert r.status_code == 409


def test_patch_amenity_mismo_nombre_es_no_op_devuelve_200(client, headers_admin):
    # Renombrar SUM a "SUM" no debe disparar 409.
    r = client.patch("/amenities/300", json={"nombre": "SUM"}, headers=headers_admin)
    assert r.status_code == 200


def test_patch_amenity_body_vacio_no_falla(client, headers_admin):
    # PATCH parcial: body vacío es no-op válido.
    r = client.patch("/amenities/300", json={}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "SUM"
