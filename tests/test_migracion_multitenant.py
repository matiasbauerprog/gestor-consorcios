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
