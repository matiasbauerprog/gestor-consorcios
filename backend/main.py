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


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrar_usuario_activa()
    if get_settings().SEED_ENABLED:
        with SessionLocal() as db:
            seed_if_empty(db)
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
