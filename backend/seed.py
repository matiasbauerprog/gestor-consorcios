import logging
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    ClaseProrrateo,
    CoeficienteDepartamento,
    ConfiguracionConsorcio,
    Departamento,
    EstadoPeticion,
    Peticion,
    Proveedor,
    Rol,
    Usuario,
)
from .security import hash_password

logger = logging.getLogger(__name__)


def _resolve_default_password() -> tuple[str, bool]:
    cfg = get_settings().SEED_DEFAULT_PASSWORD
    if cfg:
        return cfg, False
    return secrets.token_urlsafe(12), True


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Usuario).limit(1)) is not None:
        return

    password, generated = _resolve_default_password()

    depto_a = Departamento(codigo="UF-1A", descripcion="Piso 1, Unidad A")
    depto_b = Departamento(codigo="UF-2B", descripcion="Piso 2, Unidad B")
    db.add_all([depto_a, depto_b])
    db.flush()

    admin = Usuario(
        email="admin@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.administracion,
        departamento_id=None,
    )
    user_a = Usuario(
        email="depto-a@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.departamento,
        departamento_id=depto_a.id,
    )
    user_b = Usuario(
        email="depto-b@consorcio.local",
        password_hash=hash_password(password),
        rol=Rol.departamento,
        departamento_id=depto_b.id,
    )
    db.add_all([admin, user_a, user_b])
    db.flush()

    # ----- Fase 1: clases de prorrateo -----
    clase_a = ClaseProrrateo(codigo="A", nombre="Expensas ordinarias", activa=True)
    clase_b = ClaseProrrateo(codigo="B", nombre="Expensas extraordinarias", activa=True)
    clase_c = ClaseProrrateo(codigo="C", nombre="Servicios diferenciados", activa=True)
    clase_d = ClaseProrrateo(codigo="D", nombre="Obras de frente", activa=True)
    db.add_all([clase_a, clase_b, clase_c, clase_d])
    db.flush()

    # ----- Fase 1: coeficientes para cada depto (clase A, 50% c/u) -----
    db.add_all([
        CoeficienteDepartamento(
            departamento_id=depto_a.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
        CoeficienteDepartamento(
            departamento_id=depto_b.id, clase_prorrateo_id=clase_a.id, porcentaje=50.0
        ),
    ])

    # ----- Fase 1: proveedores de ejemplo -----
    db.add_all([
        Proveedor(razon_social="Limpieza S.A.", nombre_fantasia="Limpieza", cuit="30-11111111-1"),
        Proveedor(razon_social="Ascensores SRL", nombre_fantasia="Ascensores", cuit="30-22222222-2"),
        Proveedor(razon_social="Seguros del Hogar", nombre_fantasia="SeguHogar", cuit="30-33333333-3"),
        Proveedor(razon_social="Banco Río", nombre_fantasia="Banco", cuit="30-44444444-4"),
        Proveedor(razon_social="Admin Consorcios", nombre_fantasia="Admin", cuit="30-55555555-5"),
    ])

    # ----- Fase 1: configuración singleton -----
    db.add(ConfiguracionConsorcio(
        id=1,
        consorcio_nombre="PENDIENTE",
        consorcio_domicilio="PENDIENTE",
        consorcio_cuit="00-00000000-0",
        consorcio_convenio_suterh=None,
        admin_nombre="PENDIENTE",
        admin_domicilio="PENDIENTE",
        admin_email="pendiente@local",
        admin_telefono="PENDIENTE",
        admin_cuit="00-00000000-0",
        admin_rpa="PENDIENTE",
        admin_situacion_fiscal="PENDIENTE",
        banco_titular="PENDIENTE",
        banco_nombre="PENDIENTE",
        banco_sucursal=None,
        banco_numero_cuenta="PENDIENTE",
        banco_cbu="0000000000000000000000",
        banco_alias=None,
    ))

    db.add_all(
        [
            Peticion(
                departamento_id=depto_a.id,
                titulo="Filtración en cocina",
                descripcion="Hay una filtración del piso de arriba en la cocina.",
                estado=EstadoPeticion.abierta,
            ),
            Peticion(
                departamento_id=depto_b.id,
                titulo="Luz quemada en pasillo",
                descripcion="La lámpara del pasillo del 2do piso está quemada.",
                estado=EstadoPeticion.abierta,
            ),
        ]
    )
    db.commit()

    logger.warning(
        "Seed completado. Usuarios: admin id=%s, depto-a id=%s, depto-b id=%s",
        admin.id,
        user_a.id,
        user_b.id,
    )
    if generated:
        logger.warning(
            "SEED_DEFAULT_PASSWORD no definida — generada al vuelo: %s "
            "(guardala ahora; no se persiste).",
            password,
        )
