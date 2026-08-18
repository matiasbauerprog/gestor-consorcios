"""Guardas del versionado de esquema.

El valor de estos tests no es cubrir Alembic (ya está testeado upstream), sino
garantizar dos invariantes propias:
  1. Alembic usa la DATABASE_URL de la app, no una hardcodeada en el .ini.
  2. Los modelos y las migraciones no se despegan nunca.
"""
from pathlib import Path

from alembic.config import Config

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
