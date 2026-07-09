def test_login_falla_si_administracion_suspendida(client, db_session):
    from backend.models import Administracion, Usuario

    # El fixture ya asignó administracion_id=1 al admin. Pero el fixture actual
    # no lo hace explícito para admin — se hace en Task 23. Por ahora asignamos manualmente.
    admin = db_session.query(Usuario).filter(Usuario.email == "admin@test.local").first()
    admin.administracion_id = 1
    db_session.commit()

    tenant = db_session.get(Administracion, 1)
    tenant.activa = False
    db_session.commit()

    r = client.post("/auth/login", json={
        "email": "admin@test.local",
        "password": "test-pass-1234",
    })
    assert r.status_code == 403
    assert r.json()["detail"] == "administracion_suspendida"


def test_login_super_admin_no_bloqueado_por_activa(client, db_session):
    from backend.models import Rol, Usuario
    from backend.security import hash_password

    sa = Usuario(
        email="sa@x.com",
        password_hash=hash_password("test-pass-1234"),
        rol=Rol.super_admin,
    )
    db_session.add(sa)
    db_session.commit()

    r = client.post("/auth/login", json={
        "email": "sa@x.com",
        "password": "test-pass-1234",
    })
    assert r.status_code == 200
