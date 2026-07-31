"""Tests del modo demo.

`backend.main.app` se construye con DEMO_MODE=false (conftest fuerza
DATABASE_URL=sqlite:///:memory:, que no contiene 'demo'), así que la ruta no
está registrada ahí. Para testear el router montamos una app mínima con la
misma dependency de DB que usa el resto del suite.
"""
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app as app_real
from backend.main import validation_exception_handler
from backend.routers import demo


@pytest.fixture()
def client_demo(db_session):
    app = FastAPI()
    # La app mínima necesita el mismo conversor RequestValidationError -> 400
    # que backend/main.py registra en la app real; sin él, Pydantic devuelve
    # su 422 por defecto y la convención del proyecto (400, no 422) no aplica.
    # Reusamos la función real en vez de reimplementarla.
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(demo.router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c


def test_ruta_demo_no_registrada_en_la_app_real():
    # Candado 2: sin DEMO_MODE la ruta no existe (404, no 403).
    paths = {getattr(r, "path", None) for r in app_real.routes}
    assert "/auth/demo-login" not in paths


def test_demo_login_rol_fuera_de_la_lista_blanca_devuelve_400(client_demo):
    # Candado 3: solo se aceptan los tres strings fijos.
    r = client_demo.post("/auth/demo-login", json={"rol": "super_admin"})
    assert r.status_code == 400


def test_demo_login_no_acepta_email(client_demo):
    r = client_demo.post("/auth/demo-login", json={"email": "admin@demo.local"})
    assert r.status_code == 400


def test_demo_login_administracion_devuelve_token(client_demo, db_session):
    # El conftest siembra admin@consorcio.local, no el usuario demo: lo creamos
    # explicitamente para poder afirmar 200 sin ambiguedad.
    from backend.models import Rol, Usuario
    from backend.security import hash_password

    db_session.add(Usuario(
        email="admin@demo.local",
        password_hash=hash_password("irrelevante-para-demo-login"),
        rol=Rol.administracion,
        administracion_id=1,
        departamento_id=None,
    ))
    db_session.commit()

    r = client_demo.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "admin@demo.local"
    assert body["user"]["rol"] == "administracion"


def test_demo_login_sin_dataset_devuelve_503(client_demo, db_session):
    from sqlalchemy import text

    from backend.models import Usuario

    # El seed de conftest no crea admin@demo.local, así que ya alcanzaría con
    # no tocar nada. Igual vaciamos usuarios para blindar el test contra
    # cambios futuros del seed. El seed siembra Comunicado/Reserva con FK
    # RESTRICT hacia usuarios, así que hay que apagar el chequeo de FK para
    # el DELETE masivo (mismo patrón que el teardown de db_session en
    # conftest.py).
    db_session.execute(text("PRAGMA foreign_keys=OFF"))
    db_session.query(Usuario).delete()
    db_session.commit()
    db_session.execute(text("PRAGMA foreign_keys=ON"))

    r = client_demo.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 503
