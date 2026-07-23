import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if get_settings().DATABASE_URL.startswith("sqlite"):
        _migrar_usuario_activa()
        _migrar_pk_periodos_cerrados()
        _migrar_administracion_modulos()
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

app.add_middleware(ImpersonateAuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_origin_regex=get_settings().CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
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

_uploads_path = Path(get_settings().UPLOAD_DIR)
_uploads_path.mkdir(parents=True, exist_ok=True)
(_uploads_path / "comprobantes").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_path)), name="uploads")
