from backend.models import EstadoPeticion, Peticion


def test_crear_trabajo_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Reparar filtración"},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_crear_trabajo_sin_token_devuelve_401(client):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "x"},
    )
    assert r.status_code == 401


def test_crear_trabajo_admin_marca_peticion_como_convertida(client, headers_admin, db_session):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Reparar filtración"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["peticion_id"] == 10
    assert body["estado"] == "en_curso"

    db_session.expire_all()
    peticion = db_session.get(Peticion, 10)
    assert peticion.estado == EstadoPeticion.convertida_en_trabajo


def test_crear_trabajo_como_representante_201(client, headers_representante):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 11, "descripcion": "Cambiar luminaria"},
        headers=headers_representante,
    )
    assert r.status_code == 201


def test_crear_trabajo_peticion_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 9999, "descripcion": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_crear_trabajo_sin_peticion_id_se_crea_desde_cero(client, headers_admin):
    r = client.post(
        "/trabajos",
        json={"descripcion": "Mantenimiento programado"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["peticion_id"] is None
    assert body["estado"] == "en_curso"


def test_crear_trabajo_body_sin_descripcion_devuelve_400(client, headers_admin):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 10},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_trabajo_body_descripcion_vacia_devuelve_400(client, headers_admin):
    r = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": ""},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_crear_trabajo_body_peticion_id_invalido_devuelve_400(client, headers_admin):
    r = client.post(
        "/trabajos",
        json={"peticion_id": "no-es-un-int", "descripcion": "x"},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_registrar_presupuesto_como_departamento_devuelve_403(
    client, headers_admin, headers_depto_a
):
    # Primero crear un trabajo (rol admin).
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()

    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "Plomero S.A.", "monto": 15000},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_registrar_presupuesto_admin_default_estado_presentado(client, headers_admin):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "Plomero S.A.", "monto": 15000},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "presentado"


def test_registrar_presupuesto_admin_aprobado_true(client, headers_admin):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "Electricista", "monto": 8000, "aprobado": True},
        headers=headers_admin,
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "aprobado"


def test_registrar_presupuesto_trabajo_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/trabajos/9999/presupuestos",
        json={"proveedor": "X", "monto": 1},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_registrar_presupuesto_sin_token_devuelve_401(client, headers_admin):
    # Crear primero un trabajo para tener un id válido.
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "Plomero S.A.", "monto": 15000},
    )
    assert r.status_code == 401


def test_registrar_presupuesto_como_representante_devuelve_201(
    client, headers_admin, headers_representante
):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "Electricista", "monto": 8500},
        headers=headers_representante,
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "presentado"


def test_registrar_presupuesto_proveedor_vacio_devuelve_400(client, headers_admin):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "", "monto": 15000},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_registrar_presupuesto_monto_no_positivo_devuelve_400(client, headers_admin):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "X", "monto": 0},
        headers=headers_admin,
    )
    assert r.status_code == 400

    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "X", "monto": -100},
        headers=headers_admin,
    )
    assert r.status_code == 400


def test_registrar_presupuesto_body_incompleto_devuelve_400(client, headers_admin):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo"},
        headers=headers_admin,
    ).json()
    # Falta `monto`.
    r = client.post(
        f"/trabajos/{trabajo['id']}/presupuestos",
        json={"proveedor": "X"},
        headers=headers_admin,
    )
    assert r.status_code == 400
