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


def test_migracion_crea_demo_si_no_hay_datos(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Administracion, Consorcio

    migrar(db_empty)

    admins = db_empty.query(Administracion).all()
    consorcios = db_empty.query(Consorcio).all()
    assert len(admins) == 1
    assert admins[0].razon_social == "Administración Demo"
    assert len(consorcios) == 1
    assert consorcios[0].administracion_id == admins[0].id


def test_migracion_es_idempotente(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Administracion

    migrar(db_empty)
    migrar(db_empty)  # segunda pasada no debe explotar ni duplicar
    assert db_empty.query(Administracion).count() == 1


def test_migracion_agrega_consorcio_id_a_departamentos(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Departamento
    from sqlalchemy import text

    # Simular estado pre-migración: recrear tabla sin consorcio_id.
    db_empty.execute(text("DROP TABLE departamentos"))
    db_empty.execute(text(
        "CREATE TABLE departamentos (id INTEGER PRIMARY KEY, codigo VARCHAR(32) UNIQUE NOT NULL, descripcion VARCHAR(255))"
    ))
    db_empty.execute(text(
        "INSERT INTO departamentos (id, codigo, descripcion) VALUES (1, 'UF-1', 'A'), (2, 'UF-2', 'B')"
    ))
    db_empty.commit()

    migrar(db_empty)

    deptos = db_empty.query(Departamento).order_by(Departamento.id).all()
    assert len(deptos) == 2
    assert all(d.consorcio_id == 1 for d in deptos)  # consorcio Demo id=1


def test_migracion_adopta_grupo_expensas(db_empty):
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    # Recrear las tablas del grupo sin consorcio_id (simulando pre-migración).
    db_empty.execute(text("DROP TABLE expensas"))
    db_empty.execute(text(
        "CREATE TABLE expensas ("
        "id INTEGER PRIMARY KEY, "
        "departamento_id INTEGER NOT NULL, "
        "periodo VARCHAR(7) NOT NULL, "
        "monto_primer_vencimiento FLOAT NOT NULL, "
        "fecha_primer_vencimiento DATE NOT NULL, "
        "monto_segundo_vencimiento FLOAT NOT NULL, "
        "fecha_segundo_vencimiento DATE NOT NULL, "
        "saldo_anterior FLOAT NOT NULL DEFAULT 0"
        ")"
    ))
    db_empty.execute(text("DROP TABLE departamentos"))
    db_empty.execute(text(
        "CREATE TABLE departamentos ("
        "id INTEGER PRIMARY KEY, "
        "codigo VARCHAR(32) NOT NULL, "
        "descripcion VARCHAR(255))"
    ))
    db_empty.execute(text(
        "INSERT INTO departamentos (id, codigo) VALUES (1, 'UF-1')"
    ))
    db_empty.execute(text(
        "INSERT INTO expensas (id, departamento_id, periodo, monto_primer_vencimiento, "
        "  fecha_primer_vencimiento, monto_segundo_vencimiento, fecha_segundo_vencimiento, saldo_anterior) "
        "  VALUES (10, 1, '2026-05', 1000, '2026-07-10', 1070, '2026-07-20', 0)"
    ))
    db_empty.commit()

    migrar(db_empty)

    r = db_empty.execute(text("SELECT consorcio_id FROM expensas WHERE id=10")).first()
    assert r[0] == 1


def test_migracion_adopta_grupo_gastos(db_empty):
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    db_empty.execute(text("DROP TABLE gastos"))
    db_empty.execute(text(
        "CREATE TABLE gastos ("
        "id INTEGER PRIMARY KEY, "
        "periodo VARCHAR(7) NOT NULL, "
        "rubro VARCHAR NOT NULL, "
        "clase_prorrateo_id INTEGER, "
        "departamento_id INTEGER, "
        "proveedor_id INTEGER NOT NULL, "
        "concepto VARCHAR(500) NOT NULL, "
        "monto FLOAT NOT NULL, "
        "forma_pago VARCHAR NOT NULL, "
        "caja_id INTEGER NOT NULL, "
        "fecha_pago DATE NOT NULL"
        ")"
    ))
    db_empty.execute(text(
        "INSERT INTO gastos (id, periodo, rubro, proveedor_id, concepto, monto, forma_pago, caja_id, fecha_pago) "
        "VALUES (1, '2026-05', 'servicios_publicos', 1, 'test', 100, 'transferencia', 1, '2026-05-01')"
    ))
    db_empty.commit()

    migrar(db_empty)

    r = db_empty.execute(text("SELECT consorcio_id FROM gastos WHERE id=1")).first()
    assert r[0] == 1


def test_migracion_asigna_administracion_a_admins(db_empty):
    from backend.migrate_multitenant import migrar
    from backend.models import Rol, Usuario
    from backend.security import hash_password
    from sqlalchemy import text

    # Sembrar admin pre-migración (sin administracion_id)
    db_empty.execute(text(
        "INSERT INTO usuarios (id, email, password_hash, rol, must_change_password) "
        "VALUES (1, 'admin@x.com', :h, 'administracion', 0)"
    ), {"h": hash_password("x")})
    db_empty.commit()

    migrar(db_empty)

    u = db_empty.query(Usuario).filter(Usuario.email == "admin@x.com").first()
    assert u.administracion_id == 1


def test_migracion_dropea_configuracion_consorcio(db_empty):
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    # No hay ConfiguracionConsorcio en db_empty (fue removido del modelo),
    # así que este test verifica el comportamiento con la tabla ausente.
    migrar(db_empty)
    r = db_empty.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='configuracion_consorcio'"
    )).first()
    assert r is None


def test_migracion_end_to_end_con_datos_variados(db_empty):
    """
    Simula una DB con datos productivos (single-tenant) y verifica que después
    de migrar todo tiene consorcio_id = 1.
    """
    from backend.migrate_multitenant import migrar
    from sqlalchemy import text

    # Recrear tablas base sin consorcio_id para simular pre-migración
    db_empty.execute(text("DROP TABLE departamentos"))
    db_empty.execute(text(
        "CREATE TABLE departamentos ("
        "id INTEGER PRIMARY KEY, "
        "codigo VARCHAR(32) NOT NULL, "
        "descripcion VARCHAR(255))"
    ))
    db_empty.execute(text("DROP TABLE proveedores"))
    db_empty.execute(text(
        "CREATE TABLE proveedores ("
        "id INTEGER PRIMARY KEY, "
        "razon_social VARCHAR(255) NOT NULL, "
        "cuit VARCHAR(13) NOT NULL, "
        "activo BOOLEAN NOT NULL DEFAULT 1)"
    ))
    db_empty.execute(text("DROP TABLE cajas"))
    db_empty.execute(text(
        "CREATE TABLE cajas ("
        "id INTEGER PRIMARY KEY, "
        "nombre VARCHAR(100) NOT NULL, "
        "tipo VARCHAR NOT NULL, "
        "saldo_inicial FLOAT NOT NULL DEFAULT 0, "
        "activa BOOLEAN NOT NULL DEFAULT 1, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    ))
    # Sembrar datos legacy
    db_empty.execute(text(
        "INSERT INTO departamentos (id, codigo, descripcion) VALUES "
        "(1, 'UF-1', 'A'), (2, 'UF-2', 'B')"
    ))
    db_empty.execute(text(
        "INSERT INTO proveedores (id, razon_social, cuit) VALUES "
        "(1, 'X', '30-11111111-1')"
    ))
    db_empty.execute(text(
        "INSERT INTO cajas (id, nombre, tipo, saldo_inicial, activa) VALUES "
        "(1, 'Banco', 'banco', 0, 1)"
    ))
    db_empty.commit()

    migrar(db_empty)

    tablas = ["departamentos", "proveedores", "cajas"]
    for tabla in tablas:
        rows = db_empty.execute(text(f"SELECT consorcio_id FROM {tabla}")).all()
        assert all(r[0] == 1 for r in rows), f"{tabla} tiene filas sin consorcio_id"
