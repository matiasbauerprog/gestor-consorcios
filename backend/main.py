import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .database import SessionLocal
from .errores import purgar_viejos, registrar as registrar_error
from .middleware.impersonate_audit import ImpersonateAuditMiddleware
from .routers import (
    amenities,
    archivos,
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
    tesoreria,
    trabajos,
    trabajos_recurrentes,
    transferencias_caja,
    usuarios,
)
from .seed import seed_if_empty
from .seed_super_admin import seed as seed_super_admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _iniciar_sentry() -> None:
    """Alertas por error, si están configuradas.

    El registro propio deja *encontrar* un error; esto es lo que hace que te
    *enteres* sin que nadie te avise. Es opcional a propósito: sin
    `SENTRY_DSN` el sistema funciona igual y no hay dependencia obligatoria.

    Va por variable de entorno y no por la interfaz porque tiene que arrancar
    antes de que algo pueda fallar: una configuración guardada en la base no
    está disponible si el problema es justamente la base.
    """
    dsn = get_settings().SENTRY_DSN
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0, send_default_pii=False)
        logger.info("Sentry activo")
    except ImportError:
        logger.warning(
            "SENTRY_DSN está cargado pero falta el paquete sentry-sdk. "
            "Instalalo o dejá SENTRY_DSN vacío."
        )
    except Exception:  # noqa: BLE001 — nunca puede impedir que el servicio arranque
        logger.exception("no se pudo iniciar Sentry; el sistema sigue igual")


_iniciar_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """El esquema NO se crea aca: lo aplica `alembic upgrade head` antes de que
    arranque el proceso web (ver Procfile). Asi el despliegue falla ruidosamente
    si una migracion no se puede aplicar, en vez de arrancar con un esquema
    incompleto y romper recien cuando alguien toca la columna que falta."""
    if get_settings().SEED_ENABLED:
        with SessionLocal() as db:
            seed_if_empty(db)
            if get_settings().SUPER_ADMIN_EMAIL and get_settings().SUPER_ADMIN_PASSWORD:
                seed_super_admin(db)

    # Los errores registrados se borran solos pasada la retención. Va acá y no
    # en una tarea programada porque no amerita una pieza más: los despliegues
    # son suficientemente frecuentes. Envuelto en try porque una falla de
    # limpieza no puede impedir que el servicio arranque.
    try:
        with SessionLocal() as db:
            borrados = purgar_viejos(db, get_settings().ERRORES_RETENCION_DIAS)
            if borrados:
                logger.info("purgados %d errores registrados vencidos", borrados)
    except Exception:  # noqa: BLE001
        logger.exception("no se pudieron purgar los errores viejos")

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


def _contexto_del_request(request: Request) -> dict:
    """Quién estaba haciendo qué, si se puede saber.

    No re-autentica ni levanta: un error puede pasar antes de resolver el
    usuario, y ahí igual hay que registrar lo que se tenga.
    """
    contexto = {"usuario_id": None, "rol": None, "consorcio_id": None}
    usuario = getattr(request.state, "user", None)
    if usuario is not None:
        contexto["usuario_id"] = getattr(usuario, "id", None)
        rol = getattr(usuario, "rol", None)
        contexto["rol"] = getattr(rol, "value", None) or (str(rol) if rol else None)
    crudo = request.headers.get("X-Consorcio-Id")
    if crudo and crudo.isdigit():
        contexto["consorcio_id"] = int(crudo)
    return contexto


@app.exception_handler(Exception)
async def error_inesperado_handler(request: Request, exc: Exception) -> JSONResponse:
    """Todo lo que no previmos.

    Le devuelve al usuario un código corto y nada más: la traza va al log y a
    la tabla, nunca al navegador. Ese código es lo que después se busca en el
    panel de super admin.

    La sesión de base es propia y no la del request: si el error fue una falla
    de base, la del request quedó en estado inválido.
    """
    codigo = "E-000000"
    try:
        with SessionLocal() as db:
            codigo = registrar_error(
                exc,
                ruta=request.url.path,
                metodo=request.method,
                db=db,
                **_contexto_del_request(request),
            )
    except Exception:  # noqa: BLE001 — ni siquiera abrir la sesión puede romper esto
        logger.exception("fallo el registro del error, la traza original sigue")

    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Ocurrió un error inesperado. Si necesitás reportarlo, pasá "
                f"este código: {codigo}"
            ),
            "codigo": codigo,
        },
    )


app.include_router(archivos.router)
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
app.include_router(tesoreria.router)
app.include_router(reportes.router)

# Candado 2: la ruta del demo no se registra fuera del modo demo. No es un 403
# —el endpoint literalmente no existe— así que un 404 no filtra que exista.
if get_settings().DEMO_MODE:
    from .routers import demo as demo_router
    app.include_router(demo_router.router)

