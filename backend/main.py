import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import (
    amenities,
    auth,
    clases_prorrateo,
    comprobantes,
    comunicados,
    departamentos,
    expensas,
    peticiones,
    proveedores,
    reservas,
    trabajos,
    usuarios,
)
from .seed import seed_if_empty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if get_settings().SEED_ENABLED:
        with SessionLocal() as db:
            seed_if_empty(db)
    yield


app = FastAPI(
    title="Sistema Integral de Gestión de Consorcios",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
app.include_router(peticiones.router)
app.include_router(trabajos.router)
app.include_router(expensas.router)
app.include_router(comprobantes.router)
app.include_router(comunicados.router)
app.include_router(amenities.router)
app.include_router(reservas.router)
app.include_router(departamentos.router)
app.include_router(usuarios.router)
app.include_router(clases_prorrateo.router)
app.include_router(proveedores.router)

_uploads_path = Path(get_settings().UPLOAD_DIR)
_uploads_path.mkdir(parents=True, exist_ok=True)
(_uploads_path / "comprobantes").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_path)), name="uploads")
