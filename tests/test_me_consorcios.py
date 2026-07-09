def test_me_consorcios_admin_ve_todos_los_del_tenant(client, headers_admin, db_session):
    from backend.models import Administracion, Consorcio, Usuario

    # Asignar admin_id=1 al admin del seed (Task 23 lo hace automáticamente)
    u = db_session.query(Usuario).filter(Usuario.email == "admin@test.local").first()
    u.administracion_id = 1
    db_session.commit()

    # Agregar un segundo consorcio al mismo tenant
    a = db_session.get(Administracion, 1)
    c2 = Consorcio(
        administracion_id=a.id, nombre="Consorcio 2",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22,
    )
    db_session.add(c2)
    db_session.commit()

    r = client.get("/me/consorcios", headers=headers_admin)
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert 1 in ids
    assert c2.id in ids


def test_me_consorcios_depto_ve_solo_el_suyo(client, headers_depto_a):
    r = client.get("/me/consorcios", headers=headers_depto_a)
    assert r.status_code == 200
    consorcios = r.json()
    assert len(consorcios) == 1
    assert consorcios[0]["id"] == 1


def test_me_consorcios_sin_token_devuelve_401(client):
    r = client.get("/me/consorcios")
    assert r.status_code == 401
