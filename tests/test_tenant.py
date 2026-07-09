"""Tests dedicados al resolver get_consorcio_activo."""
import pytest
from fastapi import HTTPException, Request

from backend.auth import CurrentUser
from backend.models import Rol
from backend.tenant import get_consorcio_activo


def _fake_request(headers: dict) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_resolver_falla_sin_header(db_session):
    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 400


def test_resolver_admin_ok_para_su_consorcio(db_session):
    from backend.models import Usuario
    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.administracion_id = 1
    db_session.commit()

    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    cid = get_consorcio_activo(req, user, db_session)
    assert cid == 1


def test_resolver_admin_403_para_consorcio_de_otro_tenant(db_session):
    from backend.models import Administracion, Consorcio, Usuario

    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.administracion_id = 1
    db_session.commit()

    a2 = Administracion(razon_social="Otro", cuit="30-99-9", email_contacto="o@o.com")
    db_session.add(a2); db_session.flush()
    c2 = Consorcio(
        administracion_id=a2.id, nombre="Otro",
        consorcio_domicilio="d", consorcio_cuit="c", admin_nombre="a",
        admin_domicilio="d", admin_email="a@a.com", admin_telefono="1",
        admin_cuit="c", admin_rpa="0", admin_situacion_fiscal="M",
        banco_titular="t", banco_nombre="n", banco_numero_cuenta="0",
        banco_cbu="0" * 22,
    )
    db_session.add(c2); db_session.commit()

    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": str(c2.id)})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403


def test_resolver_depto_ok_para_su_consorcio(db_session):
    user = CurrentUser(id=2, rol=Rol.departamento, departamento_id=1, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    cid = get_consorcio_activo(req, user, db_session)
    assert cid == 1


def test_resolver_super_admin_403(db_session):
    from backend.models import Usuario
    from backend.security import hash_password
    sa = Usuario(id=99, email="sa@x.com", password_hash=hash_password("x"), rol=Rol.super_admin)
    db_session.add(sa); db_session.commit()

    user = CurrentUser(id=99, rol=Rol.super_admin, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403


def test_resolver_bloquea_must_change_password(db_session):
    from backend.models import Usuario
    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.administracion_id = 1
    u.must_change_password = True
    db_session.commit()

    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403
    assert exc.value.detail == "cambio_password_requerido"


def test_resolver_bloquea_administracion_suspendida(db_session):
    from backend.models import Administracion, Usuario

    u = db_session.query(Usuario).filter(Usuario.id == 1).first()
    u.administracion_id = 1
    a1 = db_session.get(Administracion, 1)
    a1.activa = False
    db_session.commit()

    user = CurrentUser(id=1, rol=Rol.administracion, departamento_id=None, jti="x", exp=0)
    req = _fake_request({"x-consorcio-id": "1"})
    with pytest.raises(HTTPException) as exc:
        get_consorcio_activo(req, user, db_session)
    assert exc.value.status_code == 403
    assert exc.value.detail == "administracion_suspendida"
