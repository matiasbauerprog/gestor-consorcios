"""Registro de errores inesperados.

El objetivo del módulo no es "loguear": es que un error deje de ser un texto
anónimo y pase a ser rastreable. El vecino ve un código, lo dicta, y con eso se
llega a qué pasó, a quién y en qué consorcio.

Dos invariantes que se protegen acá y que son el corazón del diseño:
  - registrar nunca puede tapar el error original,
  - la salida del servidor tiene la traza aunque la base esté caída.
"""
import logging
from datetime import datetime, timedelta, timezone

from backend import errores
from backend.models import ErrorRegistrado


def test_el_codigo_no_usa_caracteres_ambiguos():
    """Se dicta por teléfono: 0/O y 1/I/L se confunden al escucharlos."""
    for _ in range(200):
        codigo = errores.generar_codigo()
        assert codigo.startswith("E-")
        cuerpo = codigo[2:]
        assert len(cuerpo) == 6
        assert not set(cuerpo) & set("O0I1L"), f"código ambiguo: {codigo}"


def test_dos_codigos_seguidos_no_se_repiten():
    assert len({errores.generar_codigo() for _ in range(500)}) == 500


def test_registrar_guarda_el_error_con_su_contexto(db_session):
    try:
        raise ValueError("algo se rompió")
    except ValueError as e:
        codigo = errores.registrar(
            e,
            ruta="/gastos",
            metodo="POST",
            usuario_id=1,
            rol="administracion",
            consorcio_id=1,
            db=db_session,
        )

    fila = db_session.query(ErrorRegistrado).one()
    assert fila.codigo == codigo
    assert fila.ruta == "/gastos"
    assert fila.metodo == "POST"
    assert fila.tipo == "ValueError"
    assert "algo se rompió" in fila.mensaje
    assert "ValueError" in fila.traza
    assert fila.usuario_id == 1
    assert fila.rol == "administracion"
    assert fila.consorcio_id == 1


def test_registrar_sirve_sin_usuario_identificado(db_session):
    """Un error antes de autenticar tiene que quedar registrado igual."""
    try:
        raise RuntimeError("sin sesión")
    except RuntimeError as e:
        errores.registrar(
            e, ruta="/auth/login", metodo="POST",
            usuario_id=None, rol=None, consorcio_id=None, db=db_session,
        )

    fila = db_session.query(ErrorRegistrado).one()
    assert fila.usuario_id is None
    assert fila.rol is None


def test_registrar_escribe_en_el_log_antes_de_tocar_la_base(db_session, caplog):
    """La salida del servidor es la fuente de verdad: sobrevive a todo."""
    with caplog.at_level(logging.ERROR):
        try:
            raise ValueError("visible en el log")
        except ValueError as e:
            codigo = errores.registrar(
                e, ruta="/x", metodo="GET",
                usuario_id=None, rol=None, consorcio_id=None, db=db_session,
            )

    texto = caplog.text
    assert codigo in texto, "el código tiene que estar en el log para poder cruzarlo"
    assert "visible en el log" in texto
    assert "ValueError" in texto


def test_si_la_base_falla_igual_devuelve_codigo_y_loguea(caplog):
    """Si el error ES la base, guardarlo en la base no va a funcionar. No puede
    perderse el rastro justo cuando más se necesita."""

    class _SesionRota:
        def add(self, _):
            raise RuntimeError("la base no responde")

        def commit(self):
            raise RuntimeError("la base no responde")

        def rollback(self):
            pass

    with caplog.at_level(logging.ERROR):
        try:
            raise ValueError("el error original")
        except ValueError as e:
            codigo = errores.registrar(
                e, ruta="/x", metodo="GET",
                usuario_id=None, rol=None, consorcio_id=None, db=_SesionRota(),
            )

    assert codigo.startswith("E-")
    assert "el error original" in caplog.text


def test_registrar_no_levanta_su_propia_excepcion():
    """Un fallo al registrar no puede convertirse en una segunda excepción que
    tape la original y le cambie la respuesta al usuario."""

    class _SesionQueExplota:
        def add(self, _):
            raise RuntimeError("boom")

        def commit(self):
            raise RuntimeError("boom")

        def rollback(self):
            raise RuntimeError("boom al hacer rollback")

    try:
        raise ValueError("original")
    except ValueError as e:
        codigo = errores.registrar(
            e, ruta="/x", metodo="GET",
            usuario_id=None, rol=None, consorcio_id=None, db=_SesionQueExplota(),
        )

    assert codigo.startswith("E-")


def test_el_mensaje_no_guarda_contraseñas(db_session):
    """Un error puede traer el payload en su mensaje. Se reutiliza el criterio
    de audit.py: tachar por nombre de campo."""
    try:
        raise ValueError("fallo al procesar {'email': 'a@b.c', 'password': 'secreta-123'}")
    except ValueError as e:
        errores.registrar(
            e, ruta="/auth/login", metodo="POST",
            usuario_id=None, rol=None, consorcio_id=None, db=db_session,
        )

    fila = db_session.query(ErrorRegistrado).one()
    assert "secreta-123" not in fila.mensaje
    assert "REDACTED" in fila.mensaje


def test_correr_alembic_en_proceso_no_apaga_el_registro_de_errores(tmp_path):
    """`fileConfig` apaga por defecto todos los loggers que ya existían, y el
    env.py de Alembic lo llama. Como `seed_demo` corre `alembic upgrade` en
    proceso, sin `disable_existing_loggers=False` la aplicación queda muda
    justo después de migrar — incluido esto, que es lo último que uno quiere
    perder.

    Se asserta sobre `.disabled` y no capturando la salida: fileConfig también
    reemplaza los manejadores de la raíz, así que cualquier captura se pierde
    igual y el test no distinguiría un logger apagado de uno sin manejador.
    """
    from alembic import command

    from tests.test_migraciones import alembic_config

    logger_errores = logging.getLogger("backend.errores")
    assert not logger_errores.disabled, "precondición: arranca habilitado"

    command.upgrade(alembic_config(f"sqlite:///{tmp_path / 'x.db'}"), "head")

    assert not logger_errores.disabled, (
        "Alembic apagó el logger de errores. Falta disable_existing_loggers="
        "False en el fileConfig de backend/migrations/env.py"
    )


# --- El manejador de errores no atrapados ----------------------------------


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def cliente_con_ruta_que_explota(db_session, monkeypatch):
    """App real con una ruta que revienta, y sin re-lanzar la excepción.

    `TestClient` por defecto re-lanza las excepciones del servidor en vez de
    dejar que el manejador responda, así que no se vería la respuesta que
    recibe el usuario.
    """
    from backend import main as main_module
    from backend.database import get_db
    from backend.main import app

    @app.get("/_boom_de_prueba")
    def _boom():
        raise ValueError("explosión de prueba")

    def _override():
        yield db_session

    class _SesionDePrueba:
        """Envuelve la session del test soportando `with`, y sin cerrarla.

        Hace falta parchear el nombre en `backend.main` y no en
        `backend.database`: main hace `from .database import SessionLocal`, así
        que tiene su propia referencia y parchear el módulo no le llega.
        """

        def __init__(self, s):
            self._s = s

        def __enter__(self):
            return self._s

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(main_module, "SessionLocal", lambda: _SesionDePrueba(db_session))

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
    app.router.routes = [
        r for r in app.router.routes
        if getattr(r, "path", None) != "/_boom_de_prueba"
    ]


def test_un_error_inesperado_devuelve_500_con_codigo(cliente_con_ruta_que_explota):
    r = cliente_con_ruta_que_explota.get("/_boom_de_prueba")

    assert r.status_code == 500
    assert r.json()["codigo"].startswith("E-")


def test_el_codigo_de_la_respuesta_es_el_que_quedo_guardado(
    cliente_con_ruta_que_explota, db_session
):
    """Es todo el punto: el vecino dicta el código y tiene que encontrarse."""
    codigo = cliente_con_ruta_que_explota.get("/_boom_de_prueba").json()["codigo"]

    fila = db_session.query(ErrorRegistrado).filter_by(codigo=codigo).one()
    assert fila.ruta == "/_boom_de_prueba"
    assert fila.tipo == "ValueError"


def test_la_respuesta_no_filtra_la_traza_al_usuario(cliente_con_ruta_que_explota):
    """El detalle técnico va al log y a la tabla, nunca al navegador."""
    cuerpo = cliente_con_ruta_que_explota.get("/_boom_de_prueba").text

    assert "Traceback" not in cuerpo
    assert "explosión de prueba" not in cuerpo
    assert "errores.py" not in cuerpo


def test_los_errores_esperados_siguen_saliendo_como_antes(client, headers_admin):
    """El manejador nuevo no debe capturar 404 ni validaciones: son parte del
    funcionamiento normal y ahogarían la tabla."""
    from backend.models import ErrorRegistrado as _E

    r = client.get("/gastos/999999", headers=headers_admin)

    assert r.status_code == 404
    assert "codigo" not in r.json()


# --- Consultarlos desde el panel de super admin ----------------------------


@pytest.fixture()
def tres_errores(db_session) -> list[str]:
    ahora = datetime.now(timezone.utc)
    filas = [
        ErrorRegistrado(
            codigo=f"E-AAAAA{n}", ocurrido_at=ahora - timedelta(minutes=n),
            ruta=f"/ruta-{n}", metodo="GET", tipo="ValueError",
            mensaje=f"mensaje {n}", traza=f"traza {n}",
            usuario_id=2, rol="departamento", consorcio_id=1,
        )
        for n in range(3)
    ]
    db_session.add_all(filas)
    db_session.commit()
    return [f.codigo for f in filas]


def test_el_super_admin_lista_los_errores_mas_nuevos_primero(
    client, headers_super_admin, tres_errores
):
    r = client.get("/super-admin/errores", headers=headers_super_admin)

    assert r.status_code == 200
    codigos = [e["codigo"] for e in r.json()]
    assert codigos == ["E-AAAAA0", "E-AAAAA1", "E-AAAAA2"]


def test_buscar_por_codigo_trae_la_traza_completa(
    client, headers_super_admin, tres_errores
):
    """El circuito entero: el vecino dicta el código y acá aparece todo."""
    r = client.get("/super-admin/errores/E-AAAAA1", headers=headers_super_admin)

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ruta"] == "/ruta-1"
    assert cuerpo["traza"] == "traza 1"
    assert cuerpo["rol"] == "departamento"


def test_un_codigo_inexistente_da_404(client, headers_super_admin):
    r = client.get("/super-admin/errores/E-NOEXIS", headers=headers_super_admin)
    assert r.status_code == 404


def test_un_admin_comun_no_ve_los_errores(client, headers_admin, tres_errores):
    """Son detalles técnicos del sistema: no se le muestran a un cliente."""
    assert client.get("/super-admin/errores", headers=headers_admin).status_code == 403
    assert (
        client.get("/super-admin/errores/E-AAAAA1", headers=headers_admin).status_code
        == 403
    )


def test_sin_token_tampoco(client, tres_errores):
    assert client.get("/super-admin/errores").status_code == 401


def test_sin_sentry_dsn_no_se_intenta_iniciar_nada(monkeypatch):
    """Sentry es opcional: sin DSN el sistema no puede depender de él."""
    from backend import main as main_module
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "SENTRY_DSN", "")
    main_module._iniciar_sentry()  # no debe levantar ni requerir el paquete


def test_un_sentry_roto_no_impide_arrancar(monkeypatch, caplog):
    """Si iniciar las alertas falla, el servicio tiene que levantar igual: sería
    absurdo que la herramienta de avisar errores tire el sistema."""
    from backend import main as main_module
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "SENTRY_DSN", "dsn-invalido")
    with caplog.at_level(logging.WARNING):
        main_module._iniciar_sentry()  # no levanta


def test_purgar_borra_solo_lo_mas_viejo_que_la_retencion(db_session):
    ahora = datetime.now(timezone.utc)
    db_session.add_all([
        ErrorRegistrado(
            codigo="E-VIEJO1", ocurrido_at=ahora - timedelta(days=100),
            ruta="/x", metodo="GET", tipo="E", mensaje="m", traza="t",
        ),
        ErrorRegistrado(
            codigo="E-NUEVO1", ocurrido_at=ahora - timedelta(days=10),
            ruta="/x", metodo="GET", tipo="E", mensaje="m", traza="t",
        ),
    ])
    db_session.commit()

    borrados = errores.purgar_viejos(db_session, dias=90)

    assert borrados == 1
    quedan = [e.codigo for e in db_session.query(ErrorRegistrado).all()]
    assert quedan == ["E-NUEVO1"]
