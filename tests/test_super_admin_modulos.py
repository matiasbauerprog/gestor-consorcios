"""Tests de módulos habilitables por administración (super_admin)."""


def test_administracion_tiene_columna_modulos(db_session):
    from backend.models import Administracion

    a = db_session.get(Administracion, 1)
    assert a is not None
    assert a.modulos_habilitados is None  # NULL = todos habilitados
