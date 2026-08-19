"""Resolución de audiencias a listas de usuarios concretos."""
import pytest

from backend.models import Rol, Usuario
from backend.notificaciones.catalogo import Audiencia
from backend.notificaciones.destinatarios import resolver_destinatarios


def test_departamento_devuelve_los_usuarios_de_ese_depto(db):
    us = resolver_destinatarios(
        db, Audiencia.DEPARTAMENTO,
        consorcio_id=1, departamento_id=1, excluir_usuario_id=None,
    )
    assert [u.id for u in us] == [2]


def test_departamento_sin_departamento_id_explota(db):
    with pytest.raises(ValueError):
        resolver_destinatarios(
            db, Audiencia.DEPARTAMENTO,
            consorcio_id=1, departamento_id=None, excluir_usuario_id=None,
        )


def test_administracion_devuelve_los_admin_de_esa_administracion(db):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=1, departamento_id=None, excluir_usuario_id=None,
    )
    assert [u.id for u in us] == [1]


def test_administracion_ignora_admins_de_otra_administracion(db, dos_consorcios):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=1, departamento_id=None, excluir_usuario_id=None,
    )
    ids = [u.id for u in us]
    assert 1 in ids
    assert 6 not in ids  # admin del consorcio 2


def test_excluye_al_actor(db):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=1, departamento_id=None, excluir_usuario_id=1,
    )
    assert us == []


def test_ignora_usuarios_dados_de_baja(db):
    u = db.get(Usuario, 2)
    u.activa = False
    db.flush()
    us = resolver_destinatarios(
        db, Audiencia.DEPARTAMENTO,
        consorcio_id=1, departamento_id=1, excluir_usuario_id=None,
    )
    assert us == []


def test_consorcio_inexistente_no_devuelve_nada(db):
    us = resolver_destinatarios(
        db, Audiencia.ADMINISTRACION,
        consorcio_id=999, departamento_id=None, excluir_usuario_id=None,
    )
    assert us == []
