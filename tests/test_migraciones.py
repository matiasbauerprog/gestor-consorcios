"""Guardas del versionado de esquema.

El valor de estos tests no es cubrir Alembic (ya está testeado upstream), sino
garantizar dos invariantes propias:
  1. Alembic usa la DATABASE_URL de la app, no una hardcodeada en el .ini.
  2. Los modelos y las migraciones no se despegan nunca.
"""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from backend.database import Base
import backend.models  # noqa: F401 — puebla Base.metadata

RAIZ = Path(__file__).resolve().parents[1]
ALEMBIC_INI = RAIZ / "alembic.ini"
MIGRATIONS_DIR = RAIZ / "backend" / "migrations"


def alembic_config(url: str) -> Config:
    """Config de Alembic apuntada a una base concreta.

    Se fuerza `script_location` a ruta absoluta porque pytest puede correr
    desde cualquier cwd y el valor relativo del .ini no resolvería.
    """
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def test_el_ini_no_hardcodea_la_url_de_la_base():
    """La URL sale de Settings. Si alguien la escribe en el .ini, una config
    de producción podría apuntar sin querer a la base de desarrollo."""
    contenido = ALEMBIC_INI.read_text(encoding="utf-8")
    lineas_url = [
        ln.strip()
        for ln in contenido.splitlines()
        if ln.strip().startswith("sqlalchemy.url")
        and not ln.strip().startswith("#")
    ]
    assert lineas_url == [], f"alembic.ini no debe fijar la URL: {lineas_url}"


def test_env_toma_la_url_de_settings():
    """env.py debe inyectar Settings.DATABASE_URL en la config de Alembic."""
    env_py = (MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8")
    assert "get_settings" in env_py
    assert "DATABASE_URL" in env_py
    assert "render_as_batch=True" in env_py, (
        "SQLite no soporta la mayoría de los ALTER TABLE: sin batch mode "
        "cualquier migración de columna revienta en desarrollo."
    )


def _sin_tabla_de_versiones(name, type_, parent_names):
    """`alembic_version` es tabla interna de Alembic y no está en los modelos:
    sin este filtro el diff siempre reportaría que sobra."""
    return not (type_ == "table" and name == "alembic_version")


def test_las_migraciones_reproducen_exactamente_los_modelos(tmp_path):
    """Construye la base corriendo TODAS las migraciones y la compara contra
    los modelos. Si alguien agrega una columna a models.py y se olvida de
    generar la revisión, esto falla acá y no en producción.

    Si este test falla, el arreglo va en una migración nueva — nunca en
    aflojar el test.
    """
    db = tmp_path / "deriva.db"
    url = f"sqlite:///{db}"

    command.upgrade(alembic_config(url), "head")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={
                    "compare_type": True,
                    "include_name": _sin_tabla_de_versiones,
                    "render_as_batch": True,
                },
            )
            diferencias = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()

    assert diferencias == [], (
        "Los modelos y las migraciones se despegaron. Generá la revisión que "
        "falta con:\n"
        '  alembic revision --autogenerate -m "<que cambiaste>"\n'
        f"Diferencias detectadas: {diferencias}"
    )


def test_el_arranque_no_crea_el_esquema():
    """El esquema lo crea Alembic, no el arranque de la app.

    Mientras `create_all` siga en el lifespan, una base de producción a la que
    le falte una columna se ve 'sana' al arrancar y explota recién cuando
    alguien toca esa columna.
    """
    main_py = (RAIZ / "backend" / "main.py").read_text(encoding="utf-8")
    assert "create_all" not in main_py, (
        "backend/main.py no debe crear tablas: eso lo hace `alembic upgrade head`."
    )
    assert "_migrar_" not in main_py, (
        "Las migraciones a mano se reemplazaron por revisiones de Alembic."
    )


def test_el_reset_de_demo_reconstruye_el_esquema():
    """`_resetear_esquema` borra las tablas; algo tiene que volver a crearlas.
    Antes lo hacía el `create_all` del lifespan, que ya no existe."""
    seed_demo = (RAIZ / "backend" / "seed_demo.py").read_text(encoding="utf-8")
    assert "alembic" in seed_demo.lower(), (
        "generar_dataset_demo(reset=True) debe aplicar las migraciones después "
        "de resetear el esquema, o la demo queda sin tablas."
    )


def test_hay_exactamente_un_head():
    """Dos heads significan historial ramificado: `upgrade head` falla y el
    deploy se cae. Pasa al mergear dos ramas que agregaron migraciones."""
    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    heads = script.get_heads()
    assert len(heads) == 1, (
        f"Hay {len(heads)} heads de migración: {heads}. Unificalos con "
        "`alembic merge`."
    )
