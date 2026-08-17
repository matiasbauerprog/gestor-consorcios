from datetime import datetime, time, timedelta

from tests.conftest import HOY, RESERVA_DESDE, RESERVA_HASTA, RESERVA_INICIO

# ---------------------------------------------------------------------------
# GET /amenities/{id}/disponibilidad
# ---------------------------------------------------------------------------


def test_disponibilidad_sin_token_devuelve_401(client):
    r = client.get(f"/amenities/300/disponibilidad?desde={RESERVA_DESDE}&hasta={RESERVA_HASTA}")
    assert r.status_code == 401


def test_disponibilidad_amenity_inexistente_devuelve_404(client, headers_admin):
    r = client.get(
        f"/amenities/9999/disponibilidad?desde={RESERVA_DESDE}&hasta={RESERVA_HASTA}",
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
    # Seed: SUM tiene una reserva RESERVA_INICIO 14:00–17:00.
    r = client.get(
        f"/amenities/300/disponibilidad?desde={RESERVA_DESDE}&hasta={RESERVA_HASTA}",
        headers=headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["amenity_id"] == 300
    assert len(body["bloques"]) == 1
    bloque = body["bloques"][0]
    assert bloque["disponible"] is False
    assert bloque["inicio"].startswith(RESERVA_INICIO.strftime("%Y-%m-%dT14:00"))
    assert bloque["fin"].startswith(RESERVA_INICIO.strftime("%Y-%m-%dT17:00"))


def test_disponibilidad_departamento_puede_consultar(client, headers_depto_b):
    r = client.get(
        f"/amenities/300/disponibilidad?desde={RESERVA_DESDE}&hasta={RESERVA_HASTA}",
        headers=headers_depto_b,
    )
    assert r.status_code == 200
    assert len(r.json()["bloques"]) == 1


def test_disponibilidad_representante_puede_consultar(client, headers_representante):
    r = client.get(
        f"/amenities/300/disponibilidad?desde={RESERVA_DESDE}&hasta={RESERVA_HASTA}",
        headers=headers_representante,
    )
    assert r.status_code == 200


def test_disponibilidad_sin_reservas_devuelve_lista_vacia(client, headers_admin):
    # Laundry no tiene reservas.
    r = client.get(
        f"/amenities/301/disponibilidad?desde={RESERVA_DESDE}&hasta={RESERVA_HASTA}",
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


from datetime import datetime

_PAYLOAD_OK = {
    "inicio": datetime.combine(HOY + timedelta(days=20), time(18, 0)).isoformat(),
    "fin": datetime.combine(HOY + timedelta(days=20), time(22, 0)).isoformat(),
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


def test_reserva_representante_devuelve_403(client, headers_representante):
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": "2026-09-01T10:00:00", "fin": "2026-09-01T11:00:00"},
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_reserva_ignora_usuario_id_del_body(client, headers_admin):
    # Fecha relativa a hoy, como el resto del archivo: con la fecha fija que
    # tenía antes ("2026-08-11") el test empezó a fallar solo el día que esa
    # fecha quedó en el pasado, porque el endpoint rechaza reservar hacia atrás.
    inicio = datetime.combine(HOY + timedelta(days=20), time(10, 0))
    r = client.post(
        "/amenities/301/reservas",
        json={
            "inicio": inicio.isoformat(),
            "fin": (inicio + timedelta(hours=1)).isoformat(),
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


# ---- Anti-solapamiento (409). Reserva existente en SUM: RESERVA_INICIO 14:00–17:00 ----


def _hora(offset_horas):
    """Horario absoluto derivado del ancla de la reserva sembrada (14:00)."""
    return (RESERVA_INICIO + timedelta(hours=offset_horas)).isoformat()


def test_reserva_solape_total_devuelve_409(client, headers_admin):
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(0), "fin": _hora(3)},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_solape_parcial_inicio_devuelve_409(client, headers_admin):
    # Nueva 13–15 choca con 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(-1), "fin": _hora(1)},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_solape_parcial_fin_devuelve_409(client, headers_admin):
    # Nueva 16–18 choca con 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(2), "fin": _hora(4)},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_contenida_dentro_de_existente_devuelve_409(client, headers_admin):
    # Nueva 15–16 está dentro de 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(1), "fin": _hora(2)},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_contiene_a_existente_devuelve_409(client, headers_admin):
    # Nueva 13–18 contiene a 14–17.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(-1), "fin": _hora(4)},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_reserva_adyacente_antes_devuelve_201(client, headers_admin):
    # Nueva 11–14 termina justo cuando empieza la existente — no solapa.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(-3), "fin": _hora(0)},
        headers=headers_admin,
    )
    assert r.status_code == 201


def test_reserva_adyacente_despues_devuelve_201(client, headers_admin):
    # Nueva 17–20 empieza justo cuando termina la existente — no solapa.
    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": _hora(3), "fin": _hora(6)},
        headers=headers_admin,
    )
    assert r.status_code == 201


def test_reserva_mismo_horario_otro_amenity_no_solapa(client, headers_admin):
    # Mismo horario que la reserva existente, pero amenity distinto.
    r = client.post(
        "/amenities/301/reservas",
        json={"inicio": _hora(0), "fin": _hora(3)},
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


def test_crear_amenity_persiste_precio_reserva_y_reglas(client, headers_admin):
    # Regresion: crear_amenity solo copiaba nombre/descripcion del payload al
    # modelo, así que precio_reserva (y el resto de las reglas) quedaban en
    # None sin importar lo que mandara el cliente — silencioso, sin 400/409,
    # porque el schema los valida bien; el bug estaba en el mapeo al modelo.
    # Con precio_reserva en None, una reserva de depto nunca genera cargo en
    # cuenta corriente (backend/routers/amenities.py:280).
    r = client.post("/amenities", json={
        "nombre": "Quincho",
        "precio_reserva": 15_000.0,
        "duracion_maxima_horas": 4,
        "anticipacion_maxima_dias": 30,
        "max_reservas_activas_por_depto": 2,
        "horas_minimas_cancelacion": 48,
    }, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["precio_reserva"] == 15_000.0
    assert body["duracion_maxima_horas"] == 4
    assert body["anticipacion_maxima_dias"] == 30
    assert body["max_reservas_activas_por_depto"] == 2
    assert body["horas_minimas_cancelacion"] == 48


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


# ---------------------------------------------------------------------------
# DELETE /amenities/{id} (soft-delete) + filtro activo en GET
# ---------------------------------------------------------------------------


def test_delete_amenity_admin_devuelve_200_y_marca_inactivo(client, headers_admin, db_session):
    from backend.models import Amenity
    r = client.delete("/amenities/301", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 301
    assert body["activo"] is False
    db_session.expire_all()
    a = db_session.get(Amenity, 301)
    assert a.activo is False


def test_delete_amenity_ya_inactivo_devuelve_409(client, headers_admin, db_session):
    from backend.models import Amenity
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    r = client.delete("/amenities/301", headers=headers_admin)
    assert r.status_code == 409


def test_delete_amenity_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.delete("/amenities/301", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_amenities_no_admin_solo_ve_activos(client, headers_depto_a, db_session):
    from backend.models import Amenity
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    r = client.get("/amenities", headers=headers_depto_a)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert 300 in ids
    assert 301 not in ids


def test_listar_amenities_admin_con_incluir_inactivos_ve_todos(client, headers_admin, db_session):
    from backend.models import Amenity
    a = db_session.get(Amenity, 301)
    a.activo = False
    db_session.commit()
    r = client.get("/amenities?incluir_inactivos=true", headers=headers_admin)
    ids = [x["id"] for x in r.json()]
    assert 300 in ids
    assert 301 in ids


def test_reserva_cross_midnight_es_valida(client, headers_admin, db_session):
    """Reservar el SUM 22:00 → 04:00 del día siguiente debe funcionar.
    El fin es un datetime completo con la fecha del día siguiente, no un
    'time' relativo a la misma fecha."""
    from datetime import datetime, timedelta
    # SUM (id=300) es el amenity del seed. Uso un horario futuro.
    inicio = (datetime.now() + timedelta(days=7)).replace(hour=22, minute=0, second=0, microsecond=0)
    fin = inicio + timedelta(hours=6)  # 04:00 del día siguiente
    assert fin.date() > inicio.date(), "el fin debe caer al día siguiente"

    r = client.post(
        "/amenities/300/reservas",
        json={"inicio": inicio.isoformat(), "fin": fin.isoformat()},
        headers=headers_admin,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # Devuelve el fin al día siguiente
    assert body["inicio"].startswith(inicio.date().isoformat())
    assert body["fin"].startswith(fin.date().isoformat())
