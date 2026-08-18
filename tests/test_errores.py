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
