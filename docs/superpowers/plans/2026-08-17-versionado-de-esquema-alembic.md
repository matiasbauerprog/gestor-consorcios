# Versionado del esquema con Alembic — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `create_all()` + las nueve funciones `_migrar_*` escritas a mano por Alembic como única fuente de verdad del esquema, de modo que agregar una columna sea un comando versionado que corre igual en SQLite y en Postgres.

**Architecture:** Alembic vive en `backend/migrations/`, lee `DATABASE_URL` de `Settings` (nunca de `alembic.ini`) y usa `Base.metadata` como objetivo de autogeneración. Una revisión base autogenerada reproduce las 32 tablas actuales. El arranque del deploy corre `alembic upgrade head` antes de levantar uvicorn. Los tests siguen creando el esquema con `create_all()` porque son en memoria y no necesitan historial — y un test de deriva garantiza que ese atajo nunca se despegue de las migraciones reales.

**Tech Stack:** Alembic 1.13+ · SQLAlchemy 2.0 · FastAPI · pytest · SQLite (dev/test) y PostgreSQL (producción).

**Spec:** `docs/superpowers/specs/2026-08-17-listo-para-cliente-real.md` (Frente 1)

## Global Constraints

- Python 3.11+. Alembic se agrega a `requirements.txt` como `alembic>=1.13`.
- Las migraciones deben correr **igual en SQLite y en PostgreSQL**. Nada de `PRAGMA` ni de SQL específico de un motor fuera de un branch explícito por dialecto.
- `render_as_batch=True` es obligatorio: SQLite no admite la mayoría de los `ALTER TABLE` y Alembic los emula recreando la tabla.
- La URL de la base **nunca** se escribe en `alembic.ini`. Sale siempre de `backend.config.get_settings().DATABASE_URL`.
- Los 1082 tests existentes deben seguir en verde al terminar cada tarea. Comando: `./.venv/Scripts/python.exe -m pytest -q`
- Nombres de archivo, tablas, columnas y mensajes en español, como el resto del repo.
- Commits frecuentes: uno por tarea como mínimo.

## Contexto que el implementador necesita saber

**Cómo se crea hoy el esquema.** `backend/main.py:230` llama a `Base.metadata.create_all(bind=engine)` en el lifespan de FastAPI, y a continuación corre nueve funciones `_migrar_*` (`backend/main.py:59-229`) que hacen `ALTER TABLE` idempotentes leyendo `PRAGMA table_info`.

**El detalle que hace urgente esta tarea.** Esas nueve funciones están dentro de un `if get_settings().DATABASE_URL.startswith("sqlite")` (`backend/main.py:232`). **En PostgreSQL no corre ninguna.** En producción el esquema saldría exclusivamente de `create_all()`, que crea tablas nuevas pero *nunca* agrega columnas a tablas existentes. Hoy no explota porque no hay ninguna base PostgreSQL viva: la demo pública corre entera en el navegador desde el 2026-08-16 y no usa backend. El agujero está al 100% latente y se estrena con el primer cliente — la primera columna que se agregue después del alta no va a existir en su base, la app va a arrancar normalmente, y va a fallar recién cuando alguien abra la pantalla que usa ese dato.

**Dependencia no obvia.** `backend/seed_demo.py:1274` levanta `TestClient(app)` y depende de que el lifespan haga `create_all` para reconstruir el esquema después de `_resetear_esquema`. Si se saca `create_all` del lifespan sin tocar esto, se rompe la regeneración del dataset de la demo (`python -m backend.seed_demo --reset --exportar`), que es como se produce `frontend/src/demo/dataset.json`. Ya no corre en ningún cron —la demo no tiene backend— pero sigue siendo el único camino para actualizar la demo. Lo cubre la Tarea 5.

**Los tests no corren solos.** `.github/workflows/` sólo tiene `mirror-demo.yml` y `reset-demo-db.yml`. No hay CI que ejecute pytest. El test de deriva de la Tarea 2 es la pieza central de este plan y no sirve de nada si nadie lo corre: la Tarea 6 lo pone en CI.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `alembic.ini` (crear, raíz) | Config mínima: `script_location` y logging. **Sin** `sqlalchemy.url`. |
| `backend/migrations/env.py` (crear) | Puente entre Alembic y la app: inyecta `DATABASE_URL` desde `Settings`, expone `Base.metadata`, activa batch mode. |
| `backend/migrations/script.py.mako` (crear) | Plantilla estándar de Alembic. |
| `backend/migrations/versions/*.py` (crear) | Revisión base + revisiones futuras. |
| `backend/main.py` (modificar: 59-229, 228-241) | Se le quitan las nueve `_migrar_*` y el `create_all()`. Queda sólo el seed. |
| `backend/seed_demo.py` (modificar: ~1264) | Después de resetear el esquema, corre `alembic upgrade head`. |
| `Procfile` (modificar) | `alembic upgrade head` antes de uvicorn. |
| `tests/test_migraciones.py` (crear) | Configuración correcta + **test de deriva modelos ↔ migraciones**. |
| `.github/workflows/tests.yml` (crear) | Corre pytest en cada push y PR. |
| `requirements.txt` (modificar) | `alembic>=1.13`. |
| `README.md` (modificar) | Flujo "agregar una columna" y comando de puesta al día. |

---

### Task 1: Cablear Alembic contra la configuración de la app

**Files:**
- Create: `alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `tests/test_migraciones.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `backend.config.get_settings()` → `Settings.DATABASE_URL`; `backend.database.Base`.
- Produces: `alembic.ini` en la raíz y el paquete `backend/migrations/` utilizables por `alembic.config.Config` desde tests y desde `backend/seed_demo.py`. Expone a las tareas siguientes la función de test `alembic_config(url: str) -> Config`.

- [ ] **Step 1: Agregar la dependencia**

En `requirements.txt`, debajo de `sqlalchemy>=2.0`:

```
alembic>=1.13
```

Instalar: `./.venv/Scripts/python.exe -m pip install -r requirements.txt`

- [ ] **Step 2: Escribir el test de configuración (falla)**

Crear `tests/test_migraciones.py`:

```python
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
```

- [ ] **Step 3: Correr los tests y verificar que fallan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py -v`
Expected: FAIL — `alembic.ini` y `backend/migrations/env.py` no existen todavía.

- [ ] **Step 4: Generar el esqueleto de Alembic**

```bash
./.venv/Scripts/python.exe -m alembic init backend/migrations
```

Esto crea `alembic.ini` en la raíz y `backend/migrations/` con `env.py`, `script.py.mako` y `versions/`.

- [ ] **Step 5: Limpiar `alembic.ini`**

Dejar la línea `sqlalchemy.url` **comentada o borrada**. El bloque de arriba del archivo debe quedar así:

```ini
[alembic]
script_location = backend/migrations
prepend_sys_path = .
# La URL la inyecta env.py desde backend.config.Settings — NO definirla acá.
```

El resto del archivo (secciones `[loggers]`, `[handlers]`, `[formatters]`) queda como lo generó `alembic init`.

- [ ] **Step 6: Reescribir `backend/migrations/env.py`**

Reemplazar el contenido completo por:

```python
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
    fileConfig(config.config_file_name)

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
```

- [ ] **Step 7: Correr los tests y verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py -v`
Expected: PASS (2 tests).

- [ ] **Step 8: Verificar que Alembic arranca contra la app**

Run: `./.venv/Scripts/python.exe -m alembic current`
Expected: sale sin error y no imprime ninguna revisión (todavía no hay historial).

- [ ] **Step 9: Commit**

```bash
git add requirements.txt alembic.ini backend/migrations tests/test_migraciones.py
git commit -m "feat: cablear Alembic contra la configuracion de la app"
```

---

### Task 2: Revisión base y guarda de deriva entre modelos y migraciones

**Files:**
- Create: `backend/migrations/versions/<hash>_esquema_base.py` (autogenerado)
- Modify: `tests/test_migraciones.py`
- Modify (condicional, ver Step 4): `backend/models.py`

**Interfaces:**
- Consumes: `alembic_config(url: str) -> Config` de `tests/test_migraciones.py` (Tarea 1).
- Produces: la revisión base, cuyo identificador es el `head` sobre el que se apoya toda revisión futura. `alembic upgrade head` sobre una base vacía deja un esquema idéntico a `Base.metadata`.

Esta es la tarea central del plan. El test de deriva es lo que convierte a Alembic en una garantía en vez de en una convención que alguien va a olvidar.

- [ ] **Step 1: Escribir el test de deriva (falla)**

Agregar a `tests/test_migraciones.py`:

```python
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from backend.database import Base
import backend.models  # noqa: F401 — puebla Base.metadata


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


def test_hay_exactamente_un_head():
    """Dos heads significan historial ramificado: `upgrade head` falla y el
    deploy se cae. Pasa al mergear dos ramas que agregaron migraciones."""
    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    heads = script.get_heads()
    assert len(heads) == 1, (
        f"Hay {len(heads)} heads de migración: {heads}. Unificalos con "
        "`alembic merge`."
    )
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py -v -k "deriva or head"`
Expected: FAIL — no hay ninguna revisión, así que `upgrade head` no crea tablas y el diff reporta las 32 tablas faltantes.

- [ ] **Step 3: Autogenerar la revisión base contra una base vacía**

**Importante:** autogenerar contra una base que ya tiene tablas produce una revisión vacía. Hay que apuntar a una base nueva y descartable.

PowerShell:

```powershell
$env:DATABASE_URL = "sqlite:///./_baseline_tmp.db"
./.venv/Scripts/python.exe -m alembic revision --autogenerate -m "esquema base"
Remove-Item ./_baseline_tmp.db
```

- [ ] **Step 4: Revisar la revisión generada a ojo**

Abrir el archivo nuevo en `backend/migrations/versions/`. Verificar:

- Tiene `down_revision = None` (es la base del historial).
- Contiene `op.create_table` para las 32 tablas.
- Contiene los dos índices únicos que hoy crean las migraciones a mano:
  `uq_gasto_consorcio_periodo_habitual` sobre `gastos` y
  `uq_movimiento_depto_expensa_tipo` sobre `movimientos_cuenta`.
  Si **no** están, es porque viven sólo en `backend/main.py` y no en `models.py`.
  En ese caso agregarlos a `models.py` en el `__table_args__` de la tabla
  correspondiente y regenerar la revisión:

  ```python
  # en class Gasto
  __table_args__ = (
      UniqueConstraint(
          "consorcio_id", "periodo", "gasto_habitual_id",
          name="uq_gasto_consorcio_periodo_habitual",
      ),
  )

  # en class MovimientoCuenta
  __table_args__ = (
      UniqueConstraint(
          "departamento_id", "expensa_id", "tipo",
          name="uq_movimiento_depto_expensa_tipo",
      ),
  )
  ```

  Cuidado al agregarlos: si la tabla ya tenía `__table_args__`, sumar la tupla
  en vez de reemplazarla.
- `periodos_cerrados` tiene PK compuesta `(periodo, consorcio_id)`.

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py -v`
Expected: PASS (4 tests).

Si `test_las_migraciones_reproducen_exactamente_los_modelos` falla con diferencias
de `server_default` o de tipo, el arreglo es editar la revisión para que coincida
con el modelo. Sólo si la diferencia es demostrablemente un artefacto de cómo
SQLite representa el tipo se agrega una exclusión **puntual y comentada** al
`include_name` — nunca una exclusión amplia.

- [ ] **Step 6: Verificar que el suite completo sigue verde**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: 1086 passed (1082 previos + 4 nuevos).

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/versions tests/test_migraciones.py backend/models.py
git commit -m "feat: revision base de Alembic + guarda de deriva contra los modelos"
```

---

### Task 3: Sacar la creación de esquema del arranque de la app

**Files:**
- Modify: `backend/main.py` (borrar 59-229; reescribir el lifespan de 228-241)
- Modify: `tests/test_migraciones.py`

**Interfaces:**
- Consumes: la revisión base de la Tarea 2.
- Produces: un `lifespan` que sólo siembra, sin tocar el esquema. El esquema pasa a ser responsabilidad de `alembic upgrade head` (Tarea 4) y de `create_all()` en los tests, que se mantiene intacto en `tests/conftest.py:133`.

- [ ] **Step 1: Verificar que nada más importa las funciones a borrar**

Run: `grep -rn "_migrar_" --include=*.py .`
Expected: sólo apariciones dentro de `backend/main.py`. Si aparece en `tests/`, esos tests se borran junto con las funciones — la guarda de deriva de la Tarea 2 los reemplaza con creces.

- [ ] **Step 2: Escribir el test del lifespan (falla)**

Agregar a `tests/test_migraciones.py`:

```python
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
```

- [ ] **Step 3: Correr y verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py::test_el_arranque_no_crea_el_esquema -v`
Expected: FAIL — `create_all` sigue en `backend/main.py:230`.

- [ ] **Step 4: Borrar las nueve funciones de migración**

En `backend/main.py`, borrar íntegras las funciones `_migrar_usuario_activa`, `_migrar_pk_periodos_cerrados`, `_migrar_administracion_modulos`, `_migrar_expensa_recargo_evaluado`, `_migrar_gasto_pagado`, `_migrar_consorcio_peticiones_visibles`, `_migrar_motivo_rechazo`, `_migrar_unique_gasto_habitual_periodo` y `_migrar_unique_movimiento_expensa_tipo` (líneas 59-229).

Borrar también el import `from sqlalchemy import text` y el `Base` de `from .database import Base, SessionLocal, engine` **si** quedan sin uso. Verificar con:

```bash
grep -n "text(\|Base\.\|engine" backend/main.py
```

- [ ] **Step 5: Reescribir el lifespan**

Reemplazar el lifespan por:

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    """El esquema NO se crea acá: lo aplica `alembic upgrade head` antes de que
    arranque el proceso web (ver Procfile). Así el despliegue falla ruidosamente
    si una migración no se puede aplicar, en vez de arrancar con un esquema
    incompleto y romper recién cuando alguien toca la columna que falta."""
    if get_settings().SEED_ENABLED:
        with SessionLocal() as db:
            seed_if_empty(db)
            if get_settings().SUPER_ADMIN_EMAIL and get_settings().SUPER_ADMIN_PASSWORD:
                seed_super_admin(db)
    yield
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde. `tests/conftest.py:133` sigue haciendo su propio `create_all()` sobre la base en memoria, así que los tests no dependen del lifespan para tener esquema.

- [ ] **Step 7: Commit**

```bash
git add backend/main.py tests/test_migraciones.py
git commit -m "refactor: el arranque ya no crea el esquema, lo hace Alembic"
```

---

### Task 4: El despliegue y el desarrollo local corren las migraciones

**Files:**
- Modify: `Procfile`
- Modify: `README.md`

**Interfaces:**
- Consumes: la revisión base (Tarea 2) y el lifespan limpio (Tarea 3).
- Produces: `alembic upgrade head` como paso obligatorio previo al arranque, tanto en Render como en desarrollo.

- [ ] **Step 1: Actualizar el Procfile**

Reemplazar el contenido de `Procfile` por:

```
web: alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

El `&&` es deliberado: si la migración falla, el servidor **no** arranca. Un
despliegue caído y visible es preferible a uno que sirve tráfico contra un
esquema a medio migrar.

- [ ] **Step 2: Verificar el ciclo completo sobre una base limpia**

```bash
rm -f ./_verificacion.db
DATABASE_URL="sqlite:///./_verificacion.db" ./.venv/Scripts/python.exe -m alembic upgrade head
DATABASE_URL="sqlite:///./_verificacion.db" ./.venv/Scripts/python.exe -m alembic current
```

Expected: `current` imprime el identificador de la revisión base con `(head)`.

- [ ] **Step 3: Verificar que la app levanta contra esa base**

```bash
DATABASE_URL="sqlite:///./_verificacion.db" SEED_ENABLED=false ./.venv/Scripts/python.exe -c "
from fastapi.testclient import TestClient
from backend.main import app
with TestClient(app) as c:
    r = c.get('/health')
    print(r.status_code, r.json())
"
rm -f ./_verificacion.db
```

Expected: `200` y el cuerpo del health check.

- [ ] **Step 4: Documentar el flujo en el README**

Agregar en `README.md`, después de la sección de levantar el backend:

````markdown
### Esquema de la base

El esquema lo maneja **Alembic**. La app no crea tablas al arrancar.

Poner la base al día (hay que correrlo la primera vez y después de cada `git pull`):

```bash
alembic upgrade head
```

**Agregar o cambiar una columna:**

1. Editar `backend/models.py`.
2. Generar la revisión: `alembic revision --autogenerate -m "descripción del cambio"`
3. **Leer el archivo generado.** La autogeneración acierta casi siempre pero no
   siempre: revisar renombres (los detecta como borrar + crear, y eso pierde datos)
   y los `server_default` de columnas nuevas `NOT NULL` sobre tablas con filas.
4. Aplicarla: `alembic upgrade head`
5. Correr `pytest tests/test_migraciones.py` — la guarda de deriva confirma que
   la migración y los modelos quedaron alineados.
6. Commitear el archivo de revisión junto con el cambio de `models.py`.

**Una base que ya tiene el esquema al día pero nunca vio Alembic** (por ejemplo un
`consorcio.db` local de antes de esta migración) se marca como al día sin
re-aplicar nada:

```bash
alembic stamp head
```
````

- [ ] **Step 5: Commit**

```bash
git add Procfile README.md
git commit -m "feat: el despliegue aplica las migraciones antes de arrancar"
```

---

### Task 5: El reset de la demo aplica migraciones en vez de depender del arranque

**Files:**
- Modify: `backend/seed_demo.py` (en `generar_dataset_demo`, ~línea 1264)
- Modify: `tests/test_migraciones.py`

**Interfaces:**
- Consumes: la revisión base (Tarea 2) y el lifespan sin `create_all` (Tarea 3).
- Produces: `generar_dataset_demo(reset=True)` reconstruye el esquema por su cuenta vía `_aplicar_migraciones() -> None`.

Sin esta tarea, `python -m backend.seed_demo --reset --exportar` —el único camino
para regenerar `frontend/src/demo/dataset.json`, que es lo que muestra la demo
pública— falla: `_resetear_esquema` borra las tablas y el `TestClient` ya no las
vuelve a crear.

- [ ] **Step 1: Escribir el test (falla)**

Agregar a `tests/test_migraciones.py`:

```python
def test_el_reset_de_demo_reconstruye_el_esquema():
    """`_resetear_esquema` borra las tablas; algo tiene que volver a crearlas.
    Antes lo hacía el `create_all` del lifespan, que ya no existe."""
    seed_demo = (RAIZ / "backend" / "seed_demo.py").read_text(encoding="utf-8")
    assert "alembic" in seed_demo.lower(), (
        "generar_dataset_demo(reset=True) debe aplicar las migraciones después "
        "de resetear el esquema, o la demo queda sin tablas."
    )
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py::test_el_reset_de_demo_reconstruye_el_esquema -v`
Expected: FAIL.

- [ ] **Step 3: Aplicar migraciones después del reset**

En `backend/seed_demo.py`, dentro de `generar_dataset_demo`, reemplazar el bloque:

```python
    if reset:
        print("[demo] reset: borrando todas las tablas")
        _resetear_esquema(engine)
```

por:

```python
    if reset:
        print("[demo] reset: borrando todas las tablas")
        _resetear_esquema(engine)
        print("[demo] aplicando migraciones")
        _aplicar_migraciones()
```

Y agregar la función auxiliar inmediatamente arriba de `generar_dataset_demo`:

```python
def _aplicar_migraciones() -> None:
    """Deja el esquema al día con `alembic upgrade head`.

    Se llama en proceso (no por subprocess) para que herede la DATABASE_URL ya
    resuelta por Settings: el cron pasa la URL por variable de entorno y un
    subprocess podría leer un .env distinto.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    raiz = Path(__file__).resolve().parents[1]
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "backend" / "migrations"))
    command.upgrade(cfg, "head")
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migraciones.py tests/test_seed_demo.py -v`
Expected: PASS.

- [ ] **Step 5: Verificar el reset de punta a punta sobre SQLite**

```bash
DATABASE_URL="sqlite:///./demo_verificacion.db" DEMO_MODE=true SEED_ENABLED=false \
DEMO_SEED_PASSWORD="VerificacionLocal2026!" \
SUPER_ADMIN_EMAIL="sa@demo.local" SUPER_ADMIN_PASSWORD="VerificacionSA2026!" \
./.venv/Scripts/python.exe -m backend.seed_demo --reset
```

Expected: termina sin error y reporta el dataset generado.
Limpieza: `rm -f ./demo_verificacion.db`

- [ ] **Step 6: Commit**

```bash
git add backend/seed_demo.py tests/test_migraciones.py
git commit -m "fix: el reset de la demo aplica migraciones tras borrar el esquema"
```

---

### Task 6: Correr los tests en CI

**Files:**
- Create: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: el suite completo, incluida la guarda de deriva de la Tarea 2.
- Produces: ejecución automática en cada push y pull request.

La guarda de deriva sólo protege si corre sin que nadie se acuerde de correrla.

- [ ] **Step 1: Crear el workflow**

```yaml
name: Tests

on:
  push:
    branches: ['**']
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Instalar dependencias
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Correr el suite
        env:
          SECRET_KEY: clave-solo-para-ci-de-al-menos-32-caracteres
          SEED_ENABLED: 'false'
          DEMO_MODE: 'false'
        run: pytest -q
```

- [ ] **Step 2: Verificar que el suite pasa con esas variables**

Run: `SECRET_KEY=clave-solo-para-ci-de-al-menos-32-caracteres SEED_ENABLED=false DEMO_MODE=false ./.venv/Scripts/python.exe -m pytest -q`
Expected: todo verde.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: correr el suite de tests en cada push y PR"
```

- [ ] **Step 4: Verificación final del frente**

```bash
./.venv/Scripts/python.exe -m pytest -q
grep -rn "create_all" backend/main.py
./.venv/Scripts/python.exe -m alembic heads
```

Expected: suite completo en verde; `create_all` sin resultados en `backend/main.py`; un único head.

---

## Self-Review

**Cobertura de la spec (Frente 1):**

| Requisito de la spec | Tarea |
|---|---|
| Incorporar Alembic leyendo `DATABASE_URL` desde `Settings` | 1 |
| Revisión base que refleje `models.py` | 2 |
| `alembic stamp` para bases existentes | 4 (documentado en README) |
| Retirar las nueve `_migrar_*` y `create_all()` del lifespan | 3 |
| `alembic upgrade head` en el despliegue | 4 |
| `create_all()` sólo en tests | 3 (se deja intacto `conftest.py`) + 2 (guarda de deriva) |
| Documentar el flujo "agregar una columna" | 4 |

Agregados sobre la spec, con justificación: la Tarea 5 (reset de la demo) es una
dependencia que la spec no había detectado y que rompería la demo cada 6 horas;
la Tarea 6 (CI) es lo que hace real a la guarda de deriva.

**Consistencia de nombres:** `alembic_config(url)` se define en la Tarea 1 y se
usa con esa firma en las Tareas 2 y 5. `_aplicar_migraciones()` se define y se
usa sólo dentro de la Tarea 5. `_sin_tabla_de_versiones(name, type_, parent_names)`
respeta la firma que Alembic espera para `include_name`.

**Riesgo residual conocido:** la autogeneración de Alembic no detecta renombres
de columna (los emite como borrar + crear, lo que pierde datos). El paso 3 del
flujo documentado en el README lo advierte explícitamente. Con datos reales de un
cliente, toda revisión que toque una columna existente se revisa a mano antes de
aplicarse.
