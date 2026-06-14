# ---------------------------------------------------------------------------
# GET /comprobantes
# ---------------------------------------------------------------------------


from datetime import date
from backend.models import Comprobante, EstadoComprobante


def _crear_comprobante(db, expensa_id, fecha_pago, monto, estado):
    c = Comprobante(
        expensa_id=expensa_id,
        fecha_pago=fecha_pago,
        monto=monto,
        archivo_url=None,
        estado=estado,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_listar_comprobantes_sin_token_devuelve_401(client):
    r = client.get("/comprobantes")
    assert r.status_code == 401


def test_listar_comprobantes_como_representante_devuelve_403(client, headers_representante):
    r = client.get("/comprobantes", headers=headers_representante)
    assert r.status_code == 403


def test_listar_comprobantes_admin_devuelve_todos(client, headers_admin, db_session):
    _crear_comprobante(db_session, 100, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 101, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_listar_comprobantes_admin_filtra_por_estado(client, headers_admin, db_session):
    _crear_comprobante(db_session, 100, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)
    _crear_comprobante(db_session, 101, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)

    r = client.get("/comprobantes?estado=aprobado", headers=headers_admin)
    assert r.status_code == 200
    comprobantes = r.json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["estado"] == "aprobado"


def test_listar_comprobantes_admin_filtra_por_departamento(client, headers_admin, db_session):
    _crear_comprobante(db_session, 100, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)  # depto 1
    _crear_comprobante(db_session, 101, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)  # depto 2

    r = client.get("/comprobantes?departamento_id=1", headers=headers_admin)
    assert r.status_code == 200
    comprobantes = r.json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["expensa"]["departamento_id"] == 1


def test_listar_comprobantes_departamento_solo_ve_los_suyos(client, headers_depto_a, db_session):
    _crear_comprobante(db_session, 100, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)  # depto 1
    _crear_comprobante(db_session, 101, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)  # depto 2

    r = client.get("/comprobantes", headers=headers_depto_a)
    assert r.status_code == 200
    comprobantes = r.json()
    assert len(comprobantes) == 1
    assert comprobantes[0]["expensa"]["departamento_id"] == 1


def test_listar_comprobantes_departamento_ignora_query_de_otro_depto(client, headers_depto_a, db_session):
    _crear_comprobante(db_session, 100, date(2026, 5, 5), 85000, EstadoComprobante.aprobado)  # depto 1
    _crear_comprobante(db_session, 101, date(2026, 5, 6), 92000, EstadoComprobante.pendiente_verificacion)  # depto 2

    r = client.get("/comprobantes?departamento_id=2", headers=headers_depto_a)
    assert r.status_code == 200
    comprobantes = r.json()
    # Sigue devolviendo solo los de su propio depto.
    assert all(c["expensa"]["departamento_id"] == 1 for c in comprobantes)


# ---------------------------------------------------------------------------
# GET /expensas
# ---------------------------------------------------------------------------


def test_listar_expensas_sin_token_devuelve_401(client):
    r = client.get("/expensas")
    assert r.status_code == 401


def test_listar_expensas_como_representante_devuelve_403(client, headers_representante):
    r = client.get("/expensas", headers=headers_representante)
    assert r.status_code == 403


def test_listar_expensas_como_admin_devuelve_todas(client, headers_admin):
    r = client.get("/expensas", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    departamentos = {e["departamento_id"] for e in data}
    assert departamentos == {1, 2}


def test_listar_expensas_como_depto_a_devuelve_solo_propias(client, headers_depto_a):
    r = client.get("/expensas", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert all(e["departamento_id"] == 1 for e in data)


def test_listar_expensas_como_depto_b_devuelve_solo_propias(client, headers_depto_b):
    r = client.get("/expensas", headers=headers_depto_b)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert all(e["departamento_id"] == 2 for e in data)


def test_listar_expensas_como_depto_filtros_no_atraviesan_aislamiento(client, headers_depto_a):
    # Aunque el depto A pida periodo=2026-05 (en el que existen 2 expensas en total),
    # solo debe ver la suya: el aislamiento no se puede saltar vía filtros.
    r = client.get("/expensas?periodo=2026-05", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["departamento_id"] == 1


def test_listar_expensas_filtra_por_periodo(client, headers_admin):
    r = client.get("/expensas?periodo=2026-05", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get("/expensas?periodo=2026-01", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_expensas_filtra_por_estado(client, headers_admin):
    r = client.get("/expensas?estado=pendiente", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert all(e["estado"] == "pendiente" for e in r.json())

    r = client.get("/expensas?estado=pagada", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_expensas_paginacion_limit_offset(client, headers_admin):
    r = client.get("/expensas?limit=1&offset=0", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/expensas?limit=1&offset=1", headers=headers_admin)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/expensas?limit=1&offset=2", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_expensas_periodo_invalido_devuelve_400(client, headers_admin):
    r = client.get("/expensas?periodo=2026/05", headers=headers_admin)
    assert r.status_code == 400


def test_listar_expensas_estado_invalido_devuelve_400(client, headers_admin):
    r = client.get("/expensas?estado=inventado", headers=headers_admin)
    assert r.status_code == 400


def test_listar_expensas_limit_fuera_de_rango_devuelve_400(client, headers_admin):
    r = client.get("/expensas?limit=0", headers=headers_admin)
    assert r.status_code == 400

    r = client.get("/expensas?limit=999", headers=headers_admin)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /expensas
# ---------------------------------------------------------------------------


_EXPENSA_NUEVA = {
    "departamento_id": 1,
    "periodo": "2026-06",
    "monto": 87000.00,
    "fecha_vencimiento": "2026-07-10",
}


def test_crear_expensa_sin_token_devuelve_401(client):
    r = client.post("/expensas", json=_EXPENSA_NUEVA)
    assert r.status_code == 401


def test_crear_expensa_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post("/expensas", json=_EXPENSA_NUEVA, headers=headers_depto_a)
    assert r.status_code == 403


def test_crear_expensa_como_representante_devuelve_403(client, headers_representante):
    r = client.post("/expensas", json=_EXPENSA_NUEVA, headers=headers_representante)
    assert r.status_code == 403


def test_crear_expensa_como_admin_devuelve_201(client, headers_admin):
    r = client.post("/expensas", json=_EXPENSA_NUEVA, headers=headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["departamento_id"] == 1
    assert body["periodo"] == "2026-06"
    assert body["monto"] == 87000.00
    assert body["fecha_vencimiento"] == "2026-07-10"
    # estado siempre server-set a "pendiente", no se acepta del body.
    assert body["estado"] == "pendiente"
    assert isinstance(body["id"], int)


def test_crear_expensa_departamento_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "departamento_id": 9999},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_crear_expensa_duplicada_devuelve_409(client, headers_admin):
    # Expensa 100 (seed) ya existe para depto 1, periodo 2026-05.
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "periodo": "2026-05"},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_crear_expensa_periodo_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "periodo": "2026/06"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_expensa_monto_no_positivo_devuelve_400(client, headers_admin):
    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "monto": 0},
        headers=headers_admin,
    )
    assert r.status_code == 400

    r = client.post(
        "/expensas",
        json={**_EXPENSA_NUEVA, "monto": -1},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_expensa_body_incompleto_devuelve_400(client, headers_admin):
    r = client.post(
        "/expensas",
        json={"departamento_id": 1, "periodo": "2026-06"},
        headers=headers_admin,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /expensas/{id}
# ---------------------------------------------------------------------------


def test_obtener_expensa_sin_token_devuelve_401(client):
    r = client.get("/expensas/100")
    assert r.status_code == 401


def test_obtener_expensa_admin_puede_ver_cualquiera(client, headers_admin):
    r = client.get("/expensas/100", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 100
    assert body["departamento_id"] == 1
    assert body["periodo"] == "2026-05"
    assert body["estado"] == "pendiente"


def test_obtener_expensa_representante_puede_ver_cualquiera(client, headers_representante):
    r = client.get("/expensas/101", headers=headers_representante)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 2


def test_obtener_expensa_propio_depto_devuelve_200(client, headers_depto_a):
    r = client.get("/expensas/100", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 1


def test_obtener_expensa_otro_depto_devuelve_403(client, headers_depto_a):
    # Expensa 101 pertenece al depto B.
    r = client.get("/expensas/101", headers=headers_depto_a)
    assert r.status_code == 403


def test_obtener_expensa_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/expensas/9999", headers=headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /expensas/{id}/comprobantes
# ---------------------------------------------------------------------------


_PAYLOAD_OK = {
    "fecha_pago": "2026-05-28",
    "monto": 85000.00,
    "archivo_url": "https://files.local/comprobante.pdf",
}


def test_presentar_comprobante_sin_token_devuelve_401(client):
    r = client.post("/expensas/100/comprobantes", json=_PAYLOAD_OK)
    assert r.status_code == 401


def test_presentar_comprobante_como_departamento_dueno_201(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        json=_PAYLOAD_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["expensa_id"] == 100
    assert body["monto"] == 85000.00
    assert body["fecha_pago"] == "2026-05-28"
    assert body["archivo_url"] == _PAYLOAD_OK["archivo_url"]
    # Estado inicial siempre pendiente_verificacion, independiente del cuerpo.
    assert body["estado"] == "pendiente_verificacion"


def test_presentar_comprobante_sin_archivo_url_201(client, headers_depto_a):
    payload = {"fecha_pago": "2026-05-28", "monto": 85000.00}
    r = client.post("/expensas/100/comprobantes", json=payload, headers=headers_depto_a)
    assert r.status_code == 201
    assert r.json()["archivo_url"] is None


def test_presentar_comprobante_depto_ajeno_devuelve_403(client, headers_depto_a):
    # Expensa 101 pertenece al depto B; depto A no puede acceder.
    r = client.post(
        "/expensas/101/comprobantes",
        json=_PAYLOAD_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_presentar_comprobante_como_admin_devuelve_403(client, headers_admin):
    r = client.post(
        "/expensas/100/comprobantes",
        json=_PAYLOAD_OK,
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_presentar_comprobante_como_representante_devuelve_403(client, headers_representante):
    r = client.post(
        "/expensas/100/comprobantes",
        json=_PAYLOAD_OK,
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_presentar_comprobante_expensa_inexistente_devuelve_404(client, headers_depto_a):
    r = client.post(
        "/expensas/9999/comprobantes",
        json=_PAYLOAD_OK,
        headers=headers_depto_a,
    )
    assert r.status_code == 404


def test_presentar_comprobante_body_invalido_monto_negativo_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        json={"fecha_pago": "2026-05-28", "monto": -1},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_body_invalido_faltan_campos_devuelve_400(client, headers_depto_a):
    r = client.post(
        "/expensas/100/comprobantes",
        json={"monto": 1000},
        headers=headers_depto_a,
    )
    assert r.status_code == 400


def test_presentar_comprobante_devuelve_expensa_resumen(client, headers_depto_a):
    payload = {
        "fecha_pago": "2026-06-05",
        "monto": 85000.00,
        "archivo_url": None,
    }
    r = client.post("/expensas/100/comprobantes", json=payload, headers=headers_depto_a)
    assert r.status_code == 201
    body = r.json()
    assert "expensa" in body
    assert body["expensa"] is not None
    assert body["expensa"]["departamento_id"] == 1
    assert body["expensa"]["periodo"] == "2026-05"
    assert body["expensa"]["monto"] == 85000.00
