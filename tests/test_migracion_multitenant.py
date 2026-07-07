from backend.models import Administracion, Rol


def test_rol_super_admin_existe():
    assert Rol.super_admin.value == "super_admin"


def test_puede_crear_administracion(db_empty):
    a = Administracion(
        razon_social="Estudio X",
        cuit="30-11111111-1",
        email_contacto="x@estudio.com",
    )
    db_empty.add(a)
    db_empty.commit()
    assert a.id is not None
    assert a.activa is True
    assert a.plan == "free"


def test_puede_crear_consorcio(db_empty):
    from backend.models import Administracion, Consorcio

    admin = Administracion(razon_social="X", cuit="30-11-1", email_contacto="x@x.com")
    db_empty.add(admin); db_empty.flush()
    c = Consorcio(
        administracion_id=admin.id,
        nombre="Edificio 1",
        consorcio_domicilio="Av. Test 100",
        consorcio_cuit="30-99-9",
        admin_nombre="Admin X",
        admin_domicilio="Of. 1",
        admin_email="x@x.com",
        admin_telefono="1111",
        admin_cuit="20-11-1",
        admin_rpa="0001",
        admin_situacion_fiscal="Monotributo",
        banco_titular="X",
        banco_nombre="Banco X",
        banco_numero_cuenta="000-0",
        banco_cbu="0" * 22,
    )
    db_empty.add(c); db_empty.commit()
    assert c.id is not None
    assert c.usa_personal_propio is True
    assert c.dia_primer_vencimiento == 10


def test_puede_crear_audit_log(db_empty):
    from backend.models import AuditLogSuperAdmin, Usuario, Rol
    from backend.security import hash_password

    u = Usuario(email="sa@x.com", password_hash=hash_password("x"), rol=Rol.super_admin)
    db_empty.add(u); db_empty.flush()
    log = AuditLogSuperAdmin(
        super_admin_usuario_id=u.id,
        accion="crear_admin",
        motivo=None,
    )
    db_empty.add(log); db_empty.commit()
    assert log.id is not None


def test_usuario_super_admin(db_empty):
    from backend.models import Usuario, Rol
    from backend.security import hash_password

    u = Usuario(
        email="sa@x.com",
        password_hash=hash_password("x"),
        rol=Rol.super_admin,
    )
    db_empty.add(u); db_empty.commit()
    assert u.administracion_id is None
    assert u.consorcio_id is None
    assert u.must_change_password is False


def test_usuario_representante_con_consorcio(db_empty):
    from backend.models import Administracion, Consorcio, Usuario, Rol
    from backend.security import hash_password

    admin = Administracion(razon_social="X", cuit="30-11-1", email_contacto="x@x.com")
    db_empty.add(admin); db_empty.flush()
    c = Consorcio(administracion_id=admin.id, nombre="C",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22)
    db_empty.add(c); db_empty.flush()
    u = Usuario(
        email="rep@x.com", password_hash=hash_password("x"),
        rol=Rol.representante, consorcio_id=c.id,
    )
    db_empty.add(u); db_empty.commit()
    assert u.consorcio_id == c.id
