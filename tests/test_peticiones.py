def test_listar_sin_token_devuelve_401(client):
    r = client.get("/peticiones")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_listar_token_invalido_devuelve_401(client):
    r = client.get("/peticiones", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_departamento_ve_todas_las_peticiones(client, headers_depto_a):
    """Depto ve peticiones de TODOS los departamentos (transparencia)."""
    r = client.get("/peticiones", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    # Debe ver al menos sus peticiones y las de otros deptos
    assert len(data) >= 2
    deptos_ids = {p["departamento_id"] for p in data}
    assert 1 in deptos_ids  # su depto
    assert 2 in deptos_ids  # depto B


def test_admin_ve_todas_las_peticiones(client, headers_admin):
    r = client.get("/peticiones", headers=headers_admin)
    assert r.status_code == 200
    data = r.json()
    departamentos = {p["departamento_id"] for p in data}
    assert departamentos == {1, 2}


def test_representante_ve_todas_las_peticiones(client, headers_representante):
    r = client.get("/peticiones", headers=headers_representante)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_detalle_otro_depto_devuelve_403(client, headers_depto_a):
    # Petición id=11 pertenece a Depto B.
    r = client.get("/peticiones/11", headers=headers_depto_a)
    assert r.status_code == 403


def test_get_detalle_propio_depto_devuelve_200(client, headers_depto_a):
    r = client.get("/peticiones/10", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 1


def test_get_detalle_admin_puede_ver_cualquier_peticion(client, headers_admin):
    r = client.get("/peticiones/11", headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["departamento_id"] == 2


def test_get_detalle_no_existente_devuelve_404(client, headers_admin):
    r = client.get("/peticiones/9999", headers=headers_admin)
    assert r.status_code == 404


def test_crear_peticion_como_departamento_201(client, headers_depto_a):
    r = client.post(
        "/peticiones",
        json={"titulo": "Caños ruidosos", "descripcion": "Baño"},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    body = r.json()
    # departamento_id viene del token, NO del cuerpo
    assert body["departamento_id"] == 1
    assert body["estado"] == "abierta"


def test_crear_peticion_ignora_departamento_id_del_body(client, headers_depto_a):
    # Intento malicioso: enviar departamento_id ajeno en el body.
    r = client.post(
        "/peticiones",
        json={"titulo": "Hackeo", "descripcion": "Intento", "departamento_id": 2},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    # Aun cuando vino "departamento_id": 2 en el body, se asigna desde el token (=1).
    assert r.json()["departamento_id"] == 1


def test_crear_peticion_como_admin_devuelve_403(client, headers_admin):
    r = client.post(
        "/peticiones",
        json={"titulo": "x", "descripcion": "y"},
        headers=headers_admin,
    )
    assert r.status_code == 403


def test_crear_peticion_como_representante_devuelve_403(client, headers_representante):
    r = client.post(
        "/peticiones",
        json={"titulo": "x", "descripcion": "y"},
        headers=headers_representante,
    )
    assert r.status_code == 403


def test_crear_peticion_sin_token_devuelve_401(client):
    r = client.post("/peticiones", json={"titulo": "x", "descripcion": "y"})
    assert r.status_code == 401


def test_crear_peticion_body_invalido_devuelve_400(client, headers_depto_a):
    r = client.post("/peticiones", json={"titulo": ""}, headers=headers_depto_a)
    assert r.status_code == 400


def test_depto_patch_devuelve_403(client, headers_depto_a, db):
    """Depto NO puede cambiar el estado de una petición."""
    from backend.models import Peticion
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="X", descripcion="x")
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.patch(
        f"/peticiones/{p.id}",
        json={"estado": "rechazada"},
        headers=headers_depto_a,
    )
    assert r.status_code == 403


def test_admin_patch_cambia_estado_200(client, headers_admin, db):
    """Admin puede cambiar estado abierta → rechazada."""
    from backend.models import Peticion, EstadoPeticion
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="X", descripcion="x", estado=EstadoPeticion.abierta)
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.patch(
        f"/peticiones/{p.id}",
        json={"estado": "rechazada"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazada"


def test_patch_cambio_estado_dispara_notificacion(client, headers_admin, db):
    """Cambiar a rechazada debe crear Notificacion."""
    from backend.models import Peticion, EstadoPeticion, Notificacion
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="Notif test", descripcion="x", estado=EstadoPeticion.abierta)
    db.add(p)
    db.commit()
    db.refresh(p)
    before = db.query(Notificacion).count()
    r = client.patch(
        f"/peticiones/{p.id}",
        json={"estado": "rechazada"},
        headers=headers_admin,
    )
    assert r.status_code == 200
    after = db.query(Notificacion).count()
    assert after > before


def test_depto_delete_su_abierta_204(client, headers_depto_a, db):
    """Depto puede borrar su propia petición si está abierta."""
    from backend.models import Peticion, EstadoPeticion
    # headers_depto_a tiene departamento_id=1
    p = Peticion(
        consorcio_id=1,
        departamento_id=1,
        titulo="A borrar",
        descripcion="x",
        estado=EstadoPeticion.abierta,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_depto_a)
    assert r.status_code == 204


def test_depto_delete_su_convertida_409(client, headers_depto_a, db):
    """Si la petición pasó a convertida_en_trabajo, depto no puede borrarla."""
    from backend.models import Peticion, EstadoPeticion
    # headers_depto_a tiene departamento_id=1
    p = Peticion(
        consorcio_id=1,
        departamento_id=1,
        titulo="Convertida",
        descripcion="x",
        estado=EstadoPeticion.convertida_en_trabajo,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_depto_a)
    assert r.status_code == 409


def test_depto_delete_ajena_403(client, headers_depto_a, db):
    """Depto NO puede borrar petición de otro depto."""
    from backend.models import Peticion, EstadoPeticion
    # headers_depto_a tiene departamento_id=1, intentamos borrar una de depto 2
    p = Peticion(
        consorcio_id=1,
        departamento_id=2,
        titulo="ajena",
        descripcion="x",
        estado=EstadoPeticion.abierta,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_depto_a)
    assert r.status_code == 403


def test_admin_delete_cualquier_estado_204(client, headers_admin, db):
    """Admin puede borrar cualquier petición en cualquier estado."""
    from backend.models import Peticion, EstadoPeticion
    p = Peticion(
        consorcio_id=1,
        departamento_id=2,
        titulo="Convertida, pero admin la borra",
        descripcion="x",
        estado=EstadoPeticion.convertida_en_trabajo,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.delete(f"/peticiones/{p.id}", headers=headers_admin)
    assert r.status_code == 204


def test_delete_inexistente_404(client, headers_admin):
    """DELETE en petición que no existe retorna 404."""
    r = client.delete("/peticiones/9999", headers=headers_admin)
    assert r.status_code == 404


def test_admin_patch_guarda_el_motivo_del_rechazo(client, headers_admin, db):
    """El motivo viaja en el PATCH y queda en la petición para el depto."""
    from backend.models import Peticion, EstadoPeticion
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="X", descripcion="x", estado=EstadoPeticion.abierta)
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.patch(
        f"/peticiones/{p.id}",
        json={"estado": "rechazada", "motivo_rechazo": "Lo cubre la garantía del constructor."},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["motivo_rechazo"] == "Lo cubre la garantía del constructor."


def test_motivo_en_blanco_queda_en_null(client, headers_admin, db):
    """Un textarea con espacios no cuenta como motivo: la UI lee null."""
    from backend.models import Peticion, EstadoPeticion
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="X", descripcion="x", estado=EstadoPeticion.abierta)
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.patch(
        f"/peticiones/{p.id}",
        json={"estado": "rechazada", "motivo_rechazo": "   "},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["motivo_rechazo"] is None


def test_rechazar_sin_motivo_sigue_siendo_valido(client, headers_admin, db):
    """El campo es opcional: rechazar sin explicación no rompe el contrato."""
    from backend.models import Peticion, EstadoPeticion
    p = Peticion(consorcio_id=1, departamento_id=1, titulo="X", descripcion="x", estado=EstadoPeticion.abierta)
    db.add(p)
    db.commit()
    db.refresh(p)
    r = client.patch(f"/peticiones/{p.id}", json={"estado": "rechazada"}, headers=headers_admin)
    assert r.status_code == 200
    assert r.json()["motivo_rechazo"] is None


def test_depto_solo_ve_las_suyas_con_la_visibilidad_apagada(client, headers_depto_a, db):
    """Con `peticiones_visibles_a_depto` en False el listado se recorta al
    propio departamento. Es el mismo criterio que GET /peticiones/{id} ya
    aplicaba en el detalle."""
    from backend.models import Consorcio
    consorcio = db.get(Consorcio, 1)
    consorcio.peticiones_visibles_a_depto = False
    db.commit()

    r = client.get("/peticiones", headers=headers_depto_a)
    assert r.status_code == 200
    data = r.json()
    assert data, "el depto tiene que seguir viendo sus propias peticiones"
    assert {p["departamento_id"] for p in data} == {1}


def test_admin_y_representante_no_se_ven_afectados_por_la_visibilidad(
    client, headers_admin, headers_representante, db
):
    """Apagar el flag recorta a los departamentos, no a quien administra."""
    from backend.models import Consorcio
    consorcio = db.get(Consorcio, 1)
    consorcio.peticiones_visibles_a_depto = False
    db.commit()

    for headers in (headers_admin, headers_representante):
        r = client.get("/peticiones", headers=headers)
        assert r.status_code == 200
        assert {p["departamento_id"] for p in r.json()} == {1, 2}


def test_crear_peticion_avisa_al_admin_como_pendiente(client, headers_depto_a, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    n = db.query(Notificacion).filter_by(tipo="peticion_nueva").one()
    assert n.usuario_id == 1
    assert n.entidad_tipo == "peticion"
    assert n.entidad_id == pid
    assert "UF-1A" in n.mensaje


def test_rechazar_peticion_apaga_el_pendiente_del_admin(client, headers_depto_a, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 1

    client.patch(
        f"/peticiones/{pid}",
        json={"estado": "rechazada", "motivo_rechazo": "No corresponde"},
        headers=headers_admin,
    )
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0


def test_convertir_en_trabajo_apaga_el_pendiente(client, headers_depto_a, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]

    r2 = client.post(
        "/trabajos",
        json={"peticion_id": pid, "descripcion": "Arreglar caño"},
        headers=headers_admin,
    )
    assert r2.status_code == 201
    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0


def test_depto_borra_su_peticion_avisa_y_apaga_el_pendiente(client, headers_depto_a, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]

    r2 = client.delete(f"/peticiones/{pid}", headers=headers_depto_a)
    assert r2.status_code == 204

    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0
    n = db.query(Notificacion).filter_by(tipo="peticion_borrada_por_depto").one()
    assert n.usuario_id == 1
    assert "Filtración" in n.mensaje


def test_admin_borra_una_peticion_apaga_el_pendiente_sin_avisar(client, headers_depto_a, headers_admin, db):
    from backend.models import Notificacion

    r = client.post(
        "/peticiones",
        json={"titulo": "Filtración", "descripcion": "Cocina"},
        headers=headers_depto_a,
    )
    pid = r.json()["id"]

    client.delete(f"/peticiones/{pid}", headers=headers_admin)

    assert db.query(Notificacion).filter_by(tipo="peticion_nueva", leida=False).count() == 0
    assert db.query(Notificacion).filter_by(tipo="peticion_borrada_por_depto").count() == 0
