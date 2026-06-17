import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-32-bytes-minimum")
os.environ.setdefault("SEED_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend import blacklist as _blacklist  # noqa: E402
from backend import database as db_module  # noqa: E402
from backend.auth import create_access_token  # noqa: E402
from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.security import hash_password  # noqa: E402

# Bcrypt es costoso (~100ms). Hasheamos una sola vez al cargar conftest
# y reusamos el mismo hash en todos los usuarios sembrados.
TEST_PASSWORD = "test-pass-1234"
_PASSWORD_HASH = hash_password(TEST_PASSWORD)
from datetime import date, datetime  # noqa: E402

from backend.models import (  # noqa: E402
    Amenity,
    CategoriaEmpleado,
    ClaseProrrateo,
    Comunicado,
    ConceptoLiquidacion,
    ConfiguracionConsorcio,
    Departamento,
    Empleado,
    EstadoExpensa,
    EstadoPeticion,
    EstadoReserva,
    Expensa,
    FormaPago,
    Gasto,
    GastoHabitual,
    Haber,
    LiquidacionDetalle,
    LiquidacionEmpleado,
    LiquidacionHaber,
    Peticion,
    Proveedor,
    Reserva,
    Rol,
    Rubro,
    TipoConcepto,
    TipoHaber,
    Usuario,
)


@pytest.fixture(autouse=True)
def _clear_blacklist() -> Iterator[None]:
    # La blacklist es un módulo singleton in-memory; aislar entre tests.
    _blacklist.clear()
    yield
    _blacklist.clear()


@pytest.fixture()
def db_session() -> Iterator:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session = TestingSession()
    try:
        _seed(session)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    # Reset override after test
    app.dependency_overrides.pop(get_db, None)


def _seed(db) -> None:
    depto_a = Departamento(id=1, codigo="UF-1A", descripcion="Depto A")
    depto_b = Departamento(id=2, codigo="UF-2B", descripcion="Depto B")
    db.add_all([depto_a, depto_b])
    db.flush()

    admin = Usuario(
        id=1,
        email="admin@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.administracion,
        departamento_id=None,
    )
    user_a = Usuario(
        id=2,
        email="a@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.departamento,
        departamento_id=depto_a.id,
    )
    user_b = Usuario(
        id=3,
        email="b@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.departamento,
        departamento_id=depto_b.id,
    )
    repre = Usuario(
        id=4,
        email="repre@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.representante,
        departamento_id=None,
    )
    db.add_all([admin, user_a, user_b, repre])
    db.flush()

    db.add_all(
        [
            Peticion(
                id=10,
                departamento_id=depto_a.id,
                titulo="Filtración A",
                descripcion="Cocina depto A",
                estado=EstadoPeticion.abierta,
            ),
            Peticion(
                id=11,
                departamento_id=depto_b.id,
                titulo="Luz pasillo B",
                descripcion="Pasillo depto B",
                estado=EstadoPeticion.abierta,
            ),
            Expensa(
                id=100,
                departamento_id=depto_a.id,
                periodo="2026-05",
                monto=85000.00,
                estado=EstadoExpensa.pendiente,
                fecha_vencimiento=date(2026, 6, 10),
            ),
            Expensa(
                id=101,
                departamento_id=depto_b.id,
                periodo="2026-05",
                monto=92000.00,
                estado=EstadoExpensa.pendiente,
                fecha_vencimiento=date(2026, 6, 10),
            ),
            Comunicado(
                id=200,
                titulo="Bienvenida",
                cuerpo="Comunicado inicial del consorcio.",
                autor_id=admin.id,
            ),
            Amenity(id=300, nombre="SUM", descripcion="Salón de usos múltiples"),
            Amenity(id=301, nombre="Laundry", descripcion="Lavandería compartida"),
            # Reserva confirmada existente en SUM: 2026-07-15 14:00–17:00.
            Reserva(
                id=400,
                amenity_id=300,
                usuario_id=user_a.id,
                inicio=datetime(2026, 7, 15, 14, 0),
                fin=datetime(2026, 7, 15, 17, 0),
                estado=EstadoReserva.confirmada,
            ),
            # Fase 1: clase de prorrateo de ejemplo (id=500)
            ClaseProrrateo(
                id=500,
                codigo="A",
                nombre="Expensas ordinarias",
                descripcion="Prorrateo principal",
                activa=True,
            ),
            # Fase 1: proveedor de ejemplo (id=600)
            Proveedor(
                id=600,
                razon_social="Proveedor Test SA",
                nombre_fantasia="Test",
                cuit="30-12345678-9",
                direccion="Calle Falsa 123",
                activo=True,
            ),
            # Fase 1: configuración del consorcio (singleton id=1)
            ConfiguracionConsorcio(
                id=1,
                consorcio_nombre="Consorcio Test",
                consorcio_domicilio="Av. Test 100",
                consorcio_cuit="30-99999999-9",
                consorcio_convenio_suterh=None,
                admin_nombre="Admin Test",
                admin_domicilio="Oficinas 200",
                admin_email="admin@test.local",
                admin_telefono="11-1111-1111",
                admin_cuit="20-11111111-1",
                admin_rpa="0001",
                admin_situacion_fiscal="Monotributo",
                banco_titular="Consorcio Test",
                banco_nombre="Banco Test",
                banco_sucursal="001",
                banco_numero_cuenta="000-1234567/8",
                banco_cbu="0000000000000000000000",
                banco_alias=None,
            ),
            # Fase 2: plantilla habitual de ejemplo (id=700)
            GastoHabitual(
                id=700,
                nombre="Plantilla Test",
                rubro=Rubro.abonos_y_servicios,
                clase_prorrateo_id=500,  # clase A sembrada en Fase 1
                proveedor_id=600,  # proveedor sembrado en Fase 1
                concepto="Servicio mensual de prueba",
                monto=10000.0,
                forma_pago=FormaPago.transferencia,
                activa=True,
            ),
            # Fase 2: gasto puntual de ejemplo (id=800), prorrateable por clase A
            Gasto(
                id=800,
                periodo="2026-06",
                rubro=Rubro.servicios_publicos,
                clase_prorrateo_id=500,
                departamento_id=None,
                proveedor_id=600,
                concepto="Luz pasillos",
                monto=15000.0,
                forma_pago=FormaPago.transferencia,
                fecha_pago=date(2026, 6, 10),
                numero_factura=None,
                fecha_factura=None,
                cuota_actual=None,
                cuota_total=None,
                gasto_habitual_id=None,
            ),
            # Fase 3: empleado de ejemplo (id=900)
            Empleado(
                id=900,
                nombre_completo="Test Empleado",
                cuil="20-30000000-3",
                categoria=CategoriaEmpleado.encargado_permanente_sin_vivienda,
                fecha_ingreso=date(2020, 1, 1),
                fecha_egreso=None,
                sueldo_basico=1000000.0,
                proveedor_id=600,  # proveedor sembrado en Fase 1
                activo=True,
            ),
            # Fase 3: liquidación histórica para empleado 900 (fuerza soft-delete en tests)
            LiquidacionEmpleado(
                id=970,
                empleado_id=900,
                periodo="2025-01",
                sueldo_bruto=1000000.0,
            ),
            # Fase 3: dos haberes mínimos
            Haber(
                id=940,
                nombre="Básico Test",
                tipo=TipoHaber.porcentaje_sobre_basico,
                valor_default=100.0,
                orden=1,
                activo=True,
            ),
            Haber(
                id=941,
                nombre="Antigüedad Test",
                tipo=TipoHaber.porcentaje_sobre_basico,
                valor_default=1.0,
                orden=2,
                activo=True,
            ),
            # Fase 3: dos conceptos mínimos
            ConceptoLiquidacion(
                id=950,
                nombre="Jubilación Test",
                tipo=TipoConcepto.descuento,
                porcentaje=11.0,
                proveedor_id=600,
                orden=1,
                activo=True,
            ),
            ConceptoLiquidacion(
                id=951,
                nombre="AFIP Test",
                tipo=TipoConcepto.contribucion,
                porcentaje=16.0,
                proveedor_id=600,
                orden=10,
                activo=True,
            ),
        ]
    )
    db.commit()


@pytest.fixture(autouse=True)
def _temp_upload_dir(tmp_path, monkeypatch) -> Iterator[None]:
    """Apunta `Settings.UPLOAD_DIR` a tmp_path para que los tests no escriban
    en el filesystem real del repo."""
    from backend.config import get_settings as _gs

    upload_root = tmp_path / "uploads"
    (upload_root / "comprobantes").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_gs(), "UPLOAD_DIR", str(upload_root))
    yield


@pytest.fixture()
def client(db_session) -> Iterator[TestClient]:
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def headers_admin() -> dict[str, str]:
    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_depto_a() -> dict[str, str]:
    token = create_access_token(user_id=2, rol=Rol.departamento, departamento_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_depto_b() -> dict[str, str]:
    token = create_access_token(user_id=3, rol=Rol.departamento, departamento_id=2)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_representante() -> dict[str, str]:
    token = create_access_token(user_id=4, rol=Rol.representante, departamento_id=None)
    return {"Authorization": f"Bearer {token}"}
