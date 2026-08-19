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
    t = Trabajo(consorcio_id=1, descripcion="Sin ppto")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    r = client.post(f"/trabajos/{t.id}/completar", headers=headers_admin)
    assert r.status_code == 409


def test_completar_con_aprobado_devuelve_payload(client, headers_admin, db_session):
    t = Trabajo(consorcio_id=1, descripcion="Con ppto")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    prov = db_session.query(Proveedor).first()
    p = Presupuesto(consorcio_id=1, trabajo_id=t.id,
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
    t = Trabajo(consorcio_id=1, descripcion="Para cancelar")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    r = client.post(f"/trabajos/{t.id}/cancelar", headers=headers_admin)
    assert r.status_code == 204

    db_session.refresh(t)
    assert t.estado == "cancelado"


def test_cancelar_trabajo_con_peticion_marca_peticion_cancelada(
    client, headers_admin, db_session
):
    """Si el trabajo vino de una petición, al cancelarlo la petición también
    pasa a cancelada (no queda huérfana en convertida_en_trabajo)."""
    from backend.models import Notificacion

    p = Peticion(consorcio_id=1, departamento_id=1,
        titulo="A cancelar via trabajo",
        descripcion="x",
        estado=EstadoPeticion.abierta,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    # Crear trabajo desde la petición → petición pasa a convertida_en_trabajo.
    r = client.post(
        "/trabajos",
        json={"peticion_id": p.id, "descripcion": "trabajo"},
        headers=headers_admin,
    )
    assert r.status_code == 201
    trabajo_id = r.json()["id"]
    db_session.refresh(p)
    assert p.estado == EstadoPeticion.convertida_en_trabajo

    # Cancelar el trabajo → la petición cascadea a cancelada y se notifica.
    notifs_antes = db_session.query(Notificacion).count()
    r = client.post(f"/trabajos/{trabajo_id}/cancelar", headers=headers_admin)
    assert r.status_code == 204

    db_session.refresh(p)
    assert p.estado == EstadoPeticion.cancelada

    notifs_despues = db_session.query(Notificacion).count()
    assert notifs_despues > notifs_antes


def test_cancelar_trabajo_sin_peticion_no_explota(
    client, headers_admin, db_session
):
    """Trabajo "desde cero" (sin peticion_id) se cancela sin tocar peticiones."""
    t = Trabajo(consorcio_id=1, descripcion="sin peticion")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    r = client.post(f"/trabajos/{t.id}/cancelar", headers=headers_admin)
    assert r.status_code == 204
    db_session.refresh(t)
    assert t.estado == "cancelado"


def test_crear_trabajo_desde_peticion_marca_convertida(client, headers_admin, db_session):
    """POST /trabajos con peticion_id marca la petición como convertida_en_trabajo."""
    p = Peticion(consorcio_id=1, departamento_id=1,
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


def test_crear_trabajo_desde_peticion_notifica_al_depto(
    client, headers_admin, db_session
):
    """Al aceptar (convertir en trabajo) una petición, el depto dueño recibe
    una notificación in-app en la campanita."""
    from backend.models import Notificacion

    p = Peticion(consorcio_id=1, departamento_id=1,
        titulo="Aviso al depto",
        descripcion="x",
        estado=EstadoPeticion.abierta,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    notifs_antes = db_session.query(Notificacion).count()

    r = client.post(
        "/trabajos",
        json={"peticion_id": p.id, "descripcion": "ok"},
        headers=headers_admin,
    )
    assert r.status_code == 201

    notifs = list(
        db_session.query(Notificacion)
        .filter(Notificacion.mensaje.contains("convertida_en_trabajo"))
        .all()
    )
    assert len(notifs) >= 1
    assert db_session.query(Notificacion).count() > notifs_antes


def test_el_trabajo_informa_su_presupuesto_aprobado_y_su_gasto(client, headers_admin):
    """Sin estos dos campos, las columnas "Presup. aprobado" y "Gasto" de la
    pantalla de Trabajos muestran un guión para siempre: el modelo los tiene,
    pero la respuesta no los devolvía."""
    r = client.post("/trabajos", headers=headers_admin,
                    json={"descripcion": "Cambio de luminaria del pasillo"})
    assert r.status_code == 201
    cuerpo = r.json()
    assert "presupuesto_aprobado_id" in cuerpo
    assert "gasto_id" in cuerpo
    assert cuerpo["presupuesto_aprobado_id"] is None
    assert cuerpo["gasto_id"] is None

    listado = client.get("/trabajos", headers=headers_admin).json()
    assert "presupuesto_aprobado_id" in listado[0]
    assert "gasto_id" in listado[0]


def test_convertir_dos_veces_la_misma_peticion_avisa_una_sola_vez(
    client, headers_admin, db_session
):
    """`crear_trabajo` pisa el estado sin mirar de dónde viene.

    Sin comparar contra el estado de origen, un doble clic en "convertir en
    trabajo" le manda al departamento dos avisos idénticos y dos correos.
    """
    from backend.models import Notificacion

    p = Peticion(
        consorcio_id=1, departamento_id=1, titulo="Convertir dos veces",
        descripcion="x", estado=EstadoPeticion.abierta,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    def _avisos() -> int:
        return (
            db_session.query(Notificacion)
            .filter_by(tipo="peticion_estado_cambiado")
            .filter(Notificacion.mensaje.contains("Convertir dos veces"))
            .count()
        )

    r1 = client.post(
        "/trabajos",
        json={"peticion_id": p.id, "descripcion": "primer trabajo"},
        headers=headers_admin,
    )
    assert r1.status_code == 201
    assert _avisos() == 1

    r2 = client.post(
        "/trabajos",
        json={"peticion_id": p.id, "descripcion": "segundo trabajo"},
        headers=headers_admin,
    )
    assert r2.status_code == 201
    assert _avisos() == 1
