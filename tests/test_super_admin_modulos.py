"""Tests de módulos habilitables por administración (super_admin)."""


def test_administracion_tiene_columna_modulos(db_session):
    from backend.models import Administracion

    a = db_session.get(Administracion, 1)
    assert a is not None
    assert a.modulos_habilitados is None  # NULL = todos habilitados


def test_catalogo_de_modulos():
    from backend.modulos import MODULOS

    assert MODULOS == (
        "comunicacion", "cobranzas", "gastos", "finanzas",
        "operacion", "espacios_comunes", "reportes", "personal",
    )


def test_modulos_habilitados_de_null_devuelve_todos(db_session):
    from backend.models import Administracion
    from backend.modulos import MODULOS, modulos_habilitados_de

    a = db_session.get(Administracion, 1)
    assert modulos_habilitados_de(a) == set(MODULOS)


def test_modulos_habilitados_de_parsea_json(db_session):
    from backend.models import Administracion
    from backend.modulos import modulos_habilitados_de

    a = db_session.get(Administracion, 1)
    a.modulos_habilitados = '["gastos", "cobranzas"]'
    assert modulos_habilitados_de(a) == {"gastos", "cobranzas"}
