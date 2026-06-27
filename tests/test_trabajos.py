from backend.models import EstadoPeticion, EstadoPresupuesto, Peticion, Presupuesto, Proveedor, Trabajo


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


def test_listar_trabajos_admin_devuelve_200(client, headers_admin):
    r = client.get("/trabajos", headers=headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_listar_trabajos_como_departamento_devuelve_403(client, headers_depto_a):
    r = client.get("/trabajos", headers=headers_depto_a)
    assert r.status_code == 403


def test_listar_trabajos_sin_token_devuelve_401(client):
    r = client.get("/trabajos")
    assert r.status_code == 401


def test_obtener_trabajo_admin_devuelve_200(client, headers_admin):
    trabajo = client.post(
        "/trabajos",
        json={"peticion_id": 10, "descripcion": "Trabajo para obtener"},
        headers=headers_admin,
    ).json()
    r = client.get(f"/trabajos/{trabajo['id']}", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == trabajo["id"]
    assert body["descripcion"] == "Trabajo para obtener"


def test_obtener_trabajo_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/trabajos/9999", headers=headers_admin)
    assert r.status_code == 404


def test_completar_sin_presupuesto_aprobado_devuelve_409(client, headers_admin, db_session):
    t = Trabajo(descripcion="Sin ppto")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    r = client.post(f"/trabajos/{t.id}/completar", headers=headers_admin)
    assert r.status_code == 409


def test_completar_con_aprobado_devuelve_payload(client, headers_admin, db_session):
    t = Trabajo(descripcion="Con ppto")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    prov = db_session.query(Proveedor).first()
    p = Presupuesto(
        trabajo_id=t.id,
        proveedor_id=prov.id,
        monto=5000,
        estado=EstadoPresupuesto.aprobado,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    t.presupuesto_aprobado_id = p.id
    db_session.commit()

    r = client.post(f"/trabajos/{t.id}/completar", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["proveedor_id"] == prov.id
    assert body["monto"] == 5000
    assert body["trabajo_id"] == t.id


def test_cancelar_trabajo_devuelve_204(client, headers_admin, db_session):
    t = Trabajo(descripcion="Para cancelar")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    r = client.post(f"/trabajos/{t.id}/cancelar", headers=headers_admin)
    assert r.status_code == 204

    db_session.refresh(t)
    assert t.estado == "cancelado"


def test_crear_trabajo_desde_peticion_marca_convertida(client, headers_admin, db_session):
    """POST /trabajos con peticion_id marca la petición como convertida_en_trabajo."""
    p = Peticion(
        departamento_id=1,
        titulo="Para convertir",
        descripcion="x",
        estado=EstadoPeticion.abierta,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    r = client.post(
        "/trabajos",
        json={
            "peticion_id": p.id,
            "descripcion": "Trabajo desde petición",
        },
        headers=headers_admin,
    )
    assert r.status_code == 201

    db_session.refresh(p)
    assert p.estado == EstadoPeticion.convertida_en_trabajo
