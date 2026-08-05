import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from sqlalchemy import text

from .config import get_settings
from .database import Base, SessionLocal, engine
from .middleware.impersonate_audit import ImpersonateAuditMiddleware
from .routers import (
    amenities,
    auth,
    cajas,
    clases_prorrateo,
    coeficientes,
    comprobantes,
    comunicados,
    conceptos_liquidacion,
    configuracion,
    consorcios,
    departamentos,
    empleados,
    estado_financiero,
    expensas,
    gastos,
    gastos_habituales,
    haberes,
    liquidaciones,
    me,
    movimientos,
    notificaciones,
    padron,
    periodos,
    peticiones,
    presupuestos,
    proveedores,
    reportes,
    reservas,
    super_admin,
    trabajos,
    trabajos_recurrentes,
    transferencias_caja,
    usuarios,
)
from .seed import seed_if_empty
from .seed_super_admin import seed as seed_super_admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _migrar_usuario_activa() -> None:
    """ALTER TABLE idempotente para bases existentes que no tienen la columna
    `activa`. `create_all` solo crea tablas nuevas, no agrega columnas."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(usuarios)"))}
        if "activa" not in cols:
            conn.execute(text(
                "ALTER TABLE usuarios ADD COLUMN activa BOOLEAN NOT NULL DEFAULT 1"
            ))


def _migrar_pk_periodos_cerrados() -> None:
    """Migra la PK de periodos_cerrados de (periodo) a (periodo, consorcio_id).
    SQLite no soporta ALTER de PK: se recrea la tabla copiando los datos.
    Idempotente: si consorcio_id ya es parte de la PK, no hace nada."""
    with engine.begin() as conn:
        info = list(conn.execute(text("PRAGMA table_info(periodos_cerrados)")))
        if not info:
            return  # la tabla no existe todavía; create_all la crea bien
        pk_cols = {r[1] for r in info if r[5] > 0}
        if "consorcio_id" in pk_cols:
            return  # ya migrada
        conn.execute(text("ALTER TABLE periodos_cerrados RENAME TO periodos_cerrados_old"))
        conn.execute(text("""
            CREATE TABLE periodos_cerrados (
                periodo VARCHAR(7) NOT NULL,
                consorcio_id INTEGER NOT NULL,
                fecha_cierre DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                cerrado_por_usuario_id INTEGER NOT NULL,
                total_expensado FLOAT NOT NULL,
                total_intereses FLOAT NOT NULL,
                cantidad_expensas INTEGER NOT NULL,
                PRIMARY KEY (periodo, consorcio_id),
                FOREIGN KEY(consorcio_id) REFERENCES consorcios (id) ON DELETE RESTRICT,
                FOREIGN KEY(cerrado_por_usuario_id) REFERENCES usuarios (id) ON DELETE RESTRICT
            )
        """))
        conn.execute(text("""
            INSERT INTO periodos_cerrados
            SELECT periodo, consorcio_id, fecha_cierre, cerrado_por_usuario_id,
                   total_expensado, total_intereses, cantidad_expensas
            FROM periodos_cerrados_old
        """))
        conn.execute(text("DROP TABLE periodos_cerrados_old"))
        logger.info("Migración PK periodos_cerrados → (periodo, consorcio_id) aplicada")


def _migrar_administracion_modulos() -> None:
    """ALTER TABLE idempotente: agrega modulos_habilitados a administraciones."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(administraciones)"))}
        if cols and "modulos_habilitados" not in cols:
            conn.execute(text(
                "ALTER TABLE administraciones ADD COLUMN modulos_habilitados TEXT"
            ))


def _migrar_expensa_recargo_evaluado() -> None:
    """ALTER TABLE idempotente: agrega `recargo_evaluado` a expensas. Las
    existentes arrancan en 0 y se evalúan una vez en la primera lectura."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(expensas)"))}
        if cols and "recargo_evaluado" not in cols:
            conn.execute(text(
                "ALTER TABLE expensas ADD COLUMN recargo_evaluado BOOLEAN NOT NULL DEFAULT 0"
            ))


def _migrar_gasto_pagado() -> None:
    """ALTER TABLE idempotente: agrega `pagado` a gastos. Los gastos existentes
    quedan en 1 — todos generaron su MovimientoCaja al crearse."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(gastos)"))}
        if cols and "pagado" not in cols:
            conn.execute(text(
                "ALTER TABLE gastos ADD COLUMN pagado BOOLEAN NOT NULL DEFAULT 1"
            ))


def _migrar_unique_gasto_habitual_periodo() -> None:
    """Índice único idempotente (consorcio_id, periodo, gasto_habitual_id) en
    gastos. Cierra la carrera de `_materializar_habituales`, que chequea y
    después inserta dentro de un GET.

    SQLite no admite agregar un UNIQUE por ALTER TABLE: se crea como índice.
    Si la base traía duplicados el CREATE fallaría y la app no arrancaría, así
    que se chequea antes y se avisa en vez de romper el arranque.
    """
    with engine.begin() as conn:
        if not list(conn.execute(text("PRAGMA table_info(gastos)"))):
            return  # la tabla no existe todavía; create_all la crea con el UNIQUE
        duplicados = conn.execute(text("""
            SELECT consorcio_id, periodo, gasto_habitual_id, COUNT(*) AS n
            FROM gastos
            WHERE gasto_habitual_id IS NOT NULL
            GROUP BY consorcio_id, periodo, gasto_habitual_id
            HAVING n > 1
        """)).fetchall()
        if duplicados:
            logger.warning(
                "No se creó uq_gasto_consorcio_periodo_habitual: hay %d grupos "
                "de gastos recurrentes duplicados que hay que resolver a mano.",
                len(duplicados),
            )
            return
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gasto_consorcio_periodo_habitual
            ON gastos (consorcio_id, periodo, gasto_habitual_id)
        """))


def _migrar_unique_movimiento_expensa_tipo() -> None:
    """Índice único idempotente (departamento_id, expensa_id, tipo) en
    movimientos_cuenta. Cierra la carrera de `recargos._devengar`.

    Los movimientos sin expensa llevan `expensa_id` NULL y SQLite trata cada
    NULL como distinto, así que el índice no los alcanza.
    """
    with engine.begin() as conn:
        if not list(conn.execute(text("PRAGMA table_info(movimientos_cuenta)"))):
            return
        duplicados = conn.execute(text("""
            SELECT departamento_id, expensa_id, tipo, COUNT(*) AS n
            FROM movimientos_cuenta
            WHERE expensa_id IS NOT NULL
            GROUP BY departamento_id, expensa_id, tipo
            HAVING n > 1
        """)).fetchall()
        if duplicados:
            logger.warning(
                "No se creó uq_movimiento_depto_expensa_tipo: hay %d grupos de "
                "movimientos duplicados por expensa que hay que resolver a mano.",
                len(duplicados),
            )
            return
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_depto_expensa_tipo
            ON movimientos_cuenta (departamento_id, expensa_id, tipo)
        """))


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if get_settings().DATABASE_URL.startswith("sqlite"):
        _migrar_usuario_activa()
        _migrar_pk_periodos_cerrados()
        _migrar_administracion_modulos()
        _migrar_expensa_recargo_evaluado()
        _migrar_gasto_pagado()
        _migrar_unique_gasto_habitual_periodo()
        _migrar_unique_movimiento_expensa_tipo()
    if get_settings().SEED_ENABLED:
        with SessionLocal() as db:
            seed_if_empty(db)
            if get_settings().SUPER_ADMIN_EMAIL and get_settings().SUPER_ADMIN_PASSWORD:
                seed_super_admin(db)
    yield


app = FastAPI(
    title="Sistema Integral de Gestión de Consorcios",
    version="1.0.0",
    lifespan=lifespan,
)

@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
    tags=["Salud"],
    status_code=status.HTTP_200_OK,
    summary="Chequeo de vida del servicio",
)
def health() -> dict[str, str]:
    """Público y sin tocar la base, a propósito.

    Un monitor externo lo pingea cada pocos minutos: en hostings que duermen los
    servicios por inactividad ese ping mantiene el demo despierto, y de paso
    avisa cuando el servicio se cae. Si consultara la base, un problema de la
    base haría fallar el chequeo de "el proceso está vivo", que es otra cosa.

    Acepta HEAD además de GET: los planes gratuitos de varios monitores de uptime
    solo mandan HEAD. Y FastAPI, a diferencia de Starlette pelado, NO agrega HEAD
    automáticamente a las rutas GET — declarado con `@app.get` responde 405 y el
    monitor lo reporta como caída.
    """
    return {"status": "ok"}


app.add_middleware(ImpersonateAuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_origin_regex=get_settings().CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "ok", "message": "Gestor de Consorcios API"}



@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "El pedido es inválido o le faltan campos requeridos."},
    )


app.include_router(auth.router)
app.include_router(me.router)
app.include_router(empleados.router)
app.include_router(peticiones.router)
app.include_router(presupuestos.router)
app.include_router(trabajos.router)
app.include_router(trabajos_recurrentes.router)
app.include_router(expensas.router)
app.include_router(comprobantes.router)
app.include_router(comunicados.router)
app.include_router(amenities.router)
app.include_router(reservas.router)
app.include_router(departamentos.router)
app.include_router(usuarios.router)
app.include_router(clases_prorrateo.router)
app.include_router(coeficientes.router)
app.include_router(proveedores.router)
app.include_router(configuracion.router)
app.include_router(consorcios.router)
app.include_router(gastos_habituales.router)
app.include_router(gastos.router)
app.include_router(conceptos_liquidacion.router)
app.include_router(haberes.router)
app.include_router(liquidaciones.router)
app.include_router(movimientos.router)
app.include_router(notificaciones.router)
app.include_router(periodos.router)
app.include_router(cajas.router)
app.include_router(transferencias_caja.router)
app.include_router(super_admin.router)
app.include_router(padron.router)
app.include_router(estado_financiero.router)
app.include_router(reportes.router)

# Candado 2: la ruta del demo no se registra fuera del modo demo. No es un 403
# —el endpoint literalmente no existe— así que un 404 no filtra que exista.
if get_settings().DEMO_MODE:
    from .routers import demo as demo_router
    app.include_router(demo_router.router)

_uploads_path = Path(get_settings().UPLOAD_DIR)
_uploads_path.mkdir(parents=True, exist_ok=True)
(_uploads_path / "comprobantes").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_path)), name="uploads")
