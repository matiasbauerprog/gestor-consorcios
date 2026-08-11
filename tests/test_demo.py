"""Tests del modo demo.

`backend.main.app` se construye con DEMO_MODE=false (conftest fuerza
DATABASE_URL=sqlite:///:memory:, que no contiene 'demo'), así que la ruta no
está registrada ahí. Para testear el router montamos una app mínima con la
misma dependency de DB que usa el resto del suite.
"""
import os
import subprocess
import sys
from pathlib import Path

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.database import get_db
from backend.main import app as app_real
from backend.main import validation_exception_handler
from backend.models import Administracion, Rol, Usuario
from backend.routers import demo
from backend.routers import auth as auth_router
from backend.security import hash_password

PASSWORD_DEMO = "irrelevante-para-demo-login"


def _crear_usuario_demo(
    db_session,
    email: str,
    rol: Rol,
    *,
    activa: bool = True,
    departamento_id: int | None = None,
    administracion_id: int | None = None,
    password: str = PASSWORD_DEMO,
) -> Usuario:
    usuario = Usuario(
        email=email,
        password_hash=hash_password(password),
        rol=rol,
        administracion_id=administracion_id,
        departamento_id=departamento_id,
        activa=activa,
    )
    db_session.add(usuario)
    db_session.commit()
    return usuario


@pytest.fixture()
def client_demo(db_session, monkeypatch):
    # El handler tiene su propia defensa en profundidad (`if not
    # get_settings().DEMO_MODE: raise 404`, ver backend/routers/demo.py) que
    # no depende de cómo se montó el router. Como esta app mínima no pasa por
    # el `if` de backend/main.py, hay que reflejar DEMO_MODE=true en el mismo
    # objeto Settings cacheado para poder ejercitar el resto del handler.
    # Mismo patrón que `_temp_upload_dir` en conftest.py (monkeypatch sobre el
    # singleton de get_settings(), sin reconstruir Settings()).
    monkeypatch.setattr(get_settings(), "DEMO_MODE", True)

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


def _obtener_rutas_app(app):
    paths = set()
    for r in app.routes:
        if hasattr(r, "path"):
            paths.add(r.path)
        if hasattr(r, "routes"):
            for sub in r.routes:
                if hasattr(sub, "path"):
                    paths.add(sub.path)
        if hasattr(r, "original_router"):
            for sub in r.original_router.routes:
                if hasattr(sub, "path"):
                    paths.add(sub.path)
    return paths


def test_ruta_demo_no_registrada_en_la_app_real():
    # Candado 2 (caso negativo): sin DEMO_MODE la ruta no existe (404, no 403).
    paths = _obtener_rutas_app(app_real)
    assert "/auth/demo-login" not in paths


def test_ruta_demo_se_registra_cuando_demo_mode_es_true(tmp_path):
    """Candado 2 (caso positivo).

    El test anterior aserta ausencia, que es el estado por defecto: si se
    borrara por completo el bloque `if get_settings().DEMO_MODE: ...` de
    backend/main.py (no solo si se invirtiera la condición), esa prueba
    seguiría pasando sin detectar que el mecanismo de registro desapareció.
    Esta prueba cierra ese hueco verificando la rama contraria.

    Corre en un subproceso con un intérprete nuevo porque `backend.main` ya
    está importado en este proceso de test con DEMO_MODE=false resuelto a
    nivel de módulo (el `if` se evalúa una única vez, al importar) — no hay
    forma de reevaluar la rama `True` sin un proceso aislado.
    """
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "demo.db"  # nombre con "demo": pasa el candado 1
    script = (
        "import backend.main as m\n"
        "paths = set()\n"
        "for r in m.app.routes:\n"
        "    if hasattr(r, 'path'): paths.add(r.path)\n"
        "    if hasattr(r, 'routes'):\n"
        "        for sub in r.routes:\n"
        "            if hasattr(sub, 'path'): paths.add(sub.path)\n"
        "    if hasattr(r, 'original_router'):\n"
        "        for sub in r.original_router.routes:\n"
        "            if hasattr(sub, 'path'): paths.add(sub.path)\n"
        "print('/auth/demo-login' in paths)\n"
    )
    env = os.environ.copy()
    env.update({
        "SECRET_KEY": "test-secret-key-for-pytest-only-32-bytes-minimum",
        "SEED_ENABLED": "false",
        "DEMO_MODE": "true",
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    })
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True", result.stderr


def test_demo_login_handler_devuelve_404_si_demo_mode_es_false(db_session):
    # Candado 2, segunda capa (I1): a diferencia de client_demo (que fuerza
    # DEMO_MODE=true vía monkeypatch), acá montamos el router SIN tocar
    # get_settings() -queda en su default de test, false (conftest). Esto
    # ejercita la línea de defensa en profundidad del propio handler,
    # independiente del mecanismo de registro condicional de main.py: si
    # alguna vez el router se registrara sin pasar por ese `if`, esta
    # primera línea del handler igual corta con 404.
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(demo.router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        r = c.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 404


def test_demo_login_rol_fuera_de_la_lista_blanca_devuelve_400(client_demo):
    # Candado 3: solo se aceptan los tres strings fijos.
    r = client_demo.post("/auth/demo-login", json={"rol": "super_admin"})
    assert r.status_code == 400


def test_demo_login_no_acepta_email(client_demo):
    r = client_demo.post("/auth/demo-login", json={"email": "admin@demo.local"})
    assert r.status_code == 400


def test_demo_login_administracion_devuelve_token(client_demo, db_session):
    # El conftest siembra admin@test.local, no el usuario demo: lo creamos
    # explicitamente para poder afirmar 200 sin ambiguedad.
    _crear_usuario_demo(db_session, "admin@demo.local", Rol.administracion, administracion_id=1)

    r = client_demo.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "admin@demo.local"
    assert body["user"]["rol"] == "administracion"


def test_demo_login_propietario_al_dia_devuelve_token(client_demo, db_session):
    # Cobertura de los otros dos roles del selector: un typo en el email de
    # _USUARIOS_DEMO quedaría invisible hasta la Task 4 si solo se ejercita
    # "administracion".
    _crear_usuario_demo(db_session, "uf01a@demo.local", Rol.departamento, departamento_id=1)

    r = client_demo.post("/auth/demo-login", json={"rol": "propietario_al_dia"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "uf01a@demo.local"
    assert body["user"]["rol"] == "departamento"


def test_demo_login_propietario_moroso_devuelve_token(client_demo, db_session):
    _crear_usuario_demo(db_session, "uf03c@demo.local", Rol.departamento, departamento_id=2)

    r = client_demo.post("/auth/demo-login", json={"rol": "propietario_moroso"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "uf03c@demo.local"
    assert body["user"]["rol"] == "departamento"


def test_demo_login_sin_dataset_devuelve_503(client_demo, db_session):
    from sqlalchemy import text

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


def test_demo_login_usuario_con_rol_equivocado_no_emite_token(client_demo, db_session):
    # Candado extra: el rol real sale de user.rol en la base, no de la
    # lista blanca. Si admin@demo.local terminara con un rol distinto al que
    # el selector "administracion" promete (seed mal generado, o una mutación
    # posterior vía POST /usuarios), no debe emitirse un token con ese
    # alcance — ni ampliado ni distinto.
    _crear_usuario_demo(db_session, "admin@demo.local", Rol.departamento, departamento_id=1)

    r = client_demo.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 503


def test_demo_login_usuario_inactivo_devuelve_403(client_demo, db_session):
    # Mismo gate que /auth/login (backend/routers/auth.py: `if not
    # user.activa`): demo-login no debe emitir token para un usuario
    # suspendido por su admin.
    _crear_usuario_demo(
        db_session, "admin@demo.local", Rol.administracion,
        administracion_id=1, activa=False,
    )

    r = client_demo.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 403
    assert r.json()["detail"] == "usuario_suspendido"


def test_demo_login_administracion_suspendida_devuelve_403(client_demo, db_session):
    # Mismo gate que /auth/login: `_administracion_activa_para`. Si el tenant
    # del usuario demo está inactivo, no se emite token.
    admin_tenant = db_session.get(Administracion, 1)
    admin_tenant.activa = False
    db_session.commit()

    _crear_usuario_demo(db_session, "admin@demo.local", Rol.administracion, administracion_id=1)

    r = client_demo.post("/auth/demo-login", json={"rol": "administracion"})
    assert r.status_code == 403
    assert r.json()["detail"] == "administracion_suspendida"


def test_demo_login_mismo_alcance_y_ttl_que_login_normal(db_session, monkeypatch):
    """Compara el token de demo-login con el de un /auth/login real para el
    mismo usuario: mismos claims (rol, departamento_id) y mismo TTL. Si
    demo-login alguna vez divergiera del alcance o la expiración de un login
    genuino, esta prueba lo detecta."""
    monkeypatch.setattr(get_settings(), "DEMO_MODE", True)
    _crear_usuario_demo(db_session, "admin@demo.local", Rol.administracion, administracion_id=1)

    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(auth_router.router)
    app.include_router(demo.router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        r_normal = c.post("/auth/login", json={"email": "admin@demo.local", "password": PASSWORD_DEMO})
        r_demo = c.post("/auth/demo-login", json={"rol": "administracion"})

    assert r_normal.status_code == 200
    assert r_demo.status_code == 200

    settings = get_settings()
    claims_normal = pyjwt.decode(
        r_normal.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    claims_demo = pyjwt.decode(
        r_demo.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )

    assert claims_normal["rol"] == claims_demo["rol"]
    assert claims_normal["departamento_id"] == claims_demo["departamento_id"]
    # TTL real (exp - iat), no solo el `expires_in` del body -que en los dos
    # endpoints sale de la misma expresión `settings.JWT_EXPIRES_MIN * 60` y
    # por sí solo no probaría nada- sino el que efectivamente quedó firmado
    # adentro de cada token.
    assert claims_normal["exp"] - claims_normal["iat"] == claims_demo["exp"] - claims_demo["iat"]
    assert r_normal.json()["expires_in"] == r_demo.json()["expires_in"]
