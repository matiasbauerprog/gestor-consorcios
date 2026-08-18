"""Entorno de Alembic para el sistema de consorcios.

Dos decisiones que no son las del template por defecto:

- La URL sale de `Settings`, no del .ini. Así una misma copia del repo migra
  la base que le corresponde según su .env / variables de entorno, y no hay
  forma de apuntar producción a la base equivocada por un .ini viejo.
- `render_as_batch=True` siempre. SQLite (desarrollo y tests) no admite casi
  ningún ALTER TABLE; Alembic lo emula recreando la tabla. En PostgreSQL el
  flag es inofensivo, así que se deja prendido en ambos y las revisiones son
  idénticas para los dos motores.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.config import get_settings
from backend.database import Base
import backend.models  # noqa: F401 — registra las 32 tablas en Base.metadata

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False es obligatorio acá: el default de
    # fileConfig es True, y apaga todos los loggers que ya existían. Como
    # `backend/seed_demo.py` corre `alembic upgrade` en proceso, sin esto la
    # aplicación queda muda justo después de migrar — incluido el registro de
    # errores, que es lo último que uno quiere perder.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# El '%' es el carácter de interpolación de ConfigParser: una password de
# Postgres que lo contenga rompe el parseo con un error incomprensible.
# Sólo se resuelve desde Settings si el llamador no fijó ya la URL (los
# tests y el reset de la demo la fijan a mano).
if not config.get_main_option("sqlalchemy.url", default=None):
    config.set_main_option(
        "sqlalchemy.url", get_settings().DATABASE_URL.replace("%", "%%")
    )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
