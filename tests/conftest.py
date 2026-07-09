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
from datetime import date, datetime, timedelta  # noqa: E402

from backend.models import (  # noqa: E402
    Amenity,
    Caja,
    CategoriaEmpleado,
    ClaseProrrateo,
    Comunicado,
    ConceptoLiquidacion,
    Departamento,
    Empleado,
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
    MovimientoCuenta,
    Peticion,
    Proveedor,
    Reserva,
    Rol,
    Rubro,
    TipoCaja,
    TipoConcepto,
    TipoHaber,
    TipoMovimiento,
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


@pytest.fixture()
def db_empty() -> Iterator:
    """Isolated in-memory DB session WITHOUT seed. Used by unit tests
    that need to control all data themselves (e.g. cuenta_corriente FIFO tests)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed(db) -> None:
    # Bridge multitenant: crear administracion+consorcio Demo antes de departamentos.
    # Task 23 va a reestructurar esto; por ahora suficiente para deblockear tests.
    from backend.models import Administracion, Consorcio

    admin_tenant = Administracion(
        id=1,
        razon_social="Administración Test",
        cuit="30-11111111-1",
        email_contacto="admin@test.local",
    )
    db.add(admin_tenant)
    db.flush()

    consorcio = Consorcio(
        id=1,
        administracion_id=1,
        nombre="Consorcio Test",
        consorcio_domicilio="Av. Test 100",
        consorcio_cuit="30-99999999-9",
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
    )
    db.add(consorcio)
    db.flush()

    depto_a = Departamento(id=1, consorcio_id=1, codigo="UF-1A", descripcion="Depto A")
    depto_b = Departamento(id=2, consorcio_id=1, codigo="UF-2B", descripcion="Depto B")
    db.add_all([depto_a, depto_b])
    db.flush()

    # Fase 5: caja default para tests (id=900)
    caja_seed = Caja(
        id=900,
        consorcio_id=1,
        nombre="Banco Test",
        tipo=TipoCaja.banco,
        saldo_inicial=0.0,
        activa=True,
    )
    db.add(caja_seed)
    db.flush()
    consorcio.caja_default_pagos_id = 900
    db.flush()

    admin = Usuario(
        id=1,
        email="admin@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.administracion,
        administracion_id=1,
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
        consorcio_id=1,
        departamento_id=None,
    )
    db.add_all([admin, user_a, user_b, repre])
    db.flush()

    db.add_all(
        [
            Peticion(
                id=10,
                consorcio_id=1,
                departamento_id=depto_a.id,
                titulo="Filtración A",
                descripcion="Cocina depto A",
                estado=EstadoPeticion.abierta,
            ),
            Peticion(
                id=11,
                consorcio_id=1,
                departamento_id=depto_b.id,
                titulo="Luz pasillo B",
                descripcion="Pasillo depto B",
                estado=EstadoPeticion.abierta,
            ),
            Expensa(
                id=100,
                consorcio_id=1,
                departamento_id=depto_a.id,
                periodo="2026-05",
                monto_primer_vencimiento=85000.00,
                fecha_primer_vencimiento=date(2026, 7, 10),
                monto_segundo_vencimiento=round(85000.00 * 1.07, 2),
                fecha_segundo_vencimiento=date(2026, 7, 10) + timedelta(days=10),
                saldo_anterior=0.0,
            ),
            Expensa(
                id=101,
                consorcio_id=1,
                departamento_id=depto_b.id,
                periodo="2026-05",
                monto_primer_vencimiento=92000.00,
                fecha_primer_vencimiento=date(2026, 7, 10),
                monto_segundo_vencimiento=round(92000.00 * 1.07, 2),
                fecha_segundo_vencimiento=date(2026, 7, 10) + timedelta(days=10),
                saldo_anterior=0.0,
            ),
            MovimientoCuenta(
                id=1100,
                consorcio_id=1,
                departamento_id=depto_a.id,
                fecha=date(2026, 5, 1),
                tipo=TipoMovimiento.expensa_emitida,
                descripcion="Expensa 2026-05",
                monto=85000.00,
                expensa_id=100,
            ),
            MovimientoCuenta(
                id=1101,
                consorcio_id=1,
                departamento_id=depto_b.id,
                fecha=date(2026, 5, 1),
                tipo=TipoMovimiento.expensa_emitida,
                descripcion="Expensa 2026-05",
                monto=92000.00,
                expensa_id=101,
            ),
            Comunicado(
                id=200,
                consorcio_id=1,
                titulo="Bienvenida",
                cuerpo="Comunicado inicial del consorcio.",
                autor_id=admin.id,
            ),
            Amenity(
                id=300, consorcio_id=1, nombre="SUM", descripcion="Salón de usos múltiples",
                activo=True,
            ),
            Amenity(
                id=301, consorcio_id=1, nombre="Laundry", descripcion="Lavandería compartida",
                activo=True,
            ),
            # Reserva confirmada existente en SUM: 2026-07-15 14:00–17:00.
            Reserva(
                id=400,
                consorcio_id=1,
                amenity_id=300,
                usuario_id=user_a.id,
                inicio=datetime(2026, 7, 15, 14, 0),
                fin=datetime(2026, 7, 15, 17, 0),
                estado=EstadoReserva.confirmada,
            ),
            # Fase 1: clase de prorrateo de ejemplo (id=500)
            ClaseProrrateo(
                id=500,
                consorcio_id=1,
                codigo="A",
                nombre="Expensas ordinarias",
                descripcion="Prorrateo principal",
                activa=True,
            ),
            # Fase 1: proveedor de ejemplo (id=600)
            Proveedor(
                id=600,
                consorcio_id=1,
                razon_social="Proveedor Test SA",
                nombre_fantasia="Test",
                cuit="30-12345678-9",
                direccion="Calle Falsa 123",
                activo=True,
            ),
            # Fase 2: plantilla habitual de ejemplo (id=700)
            GastoHabitual(
                id=700,
                consorcio_id=1,
                nombre="Plantilla Test",
                rubro=Rubro.abonos_y_servicios,
                clase_prorrateo_id=500,  # clase A sembrada en Fase 1
                proveedor_id=600,  # proveedor sembrado en Fase 1
                concepto="Servicio mensual de prueba",
                monto=10000.0,
                forma_pago=FormaPago.transferencia,
                caja_id=900,  # Fase 5: caja default
                activa=True,
            ),
            # Fase 2: gasto puntual de ejemplo (id=800), prorrateable por clase A
            Gasto(
                id=800,
                consorcio_id=1,
                periodo="2026-06",
                rubro=Rubro.servicios_publicos,
                clase_prorrateo_id=500,
                departamento_id=None,
                proveedor_id=600,
                concepto="Luz pasillos",
                monto=15000.0,
                forma_pago=FormaPago.transferencia,
                caja_id=900,  # Fase 5: caja default
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
                consorcio_id=1,
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
                consorcio_id=1,
                empleado_id=900,
                periodo="2025-01",
                sueldo_bruto=1000000.0,
                caja_id=900,  # Fase 5: caja default
            ),
            # Fase 3: dos haberes mínimos
            Haber(
                id=940,
                consorcio_id=1,
                nombre="Básico Test",
                tipo=TipoHaber.porcentaje_sobre_basico,
                valor_default=100.0,
                orden=1,
                activo=True,
            ),
            Haber(
                id=941,
                consorcio_id=1,
                nombre="Antigüedad Test",
                tipo=TipoHaber.porcentaje_sobre_basico,
                valor_default=1.0,
                orden=2,
                activo=True,
            ),
            # Fase 3: dos conceptos mínimos
            ConceptoLiquidacion(
                id=950,
                consorcio_id=1,
                nombre="Jubilación Test",
                tipo=TipoConcepto.descuento,
                porcentaje=11.0,
                proveedor_id=600,
                orden=1,
                activo=True,
            ),
            ConceptoLiquidacion(
                id=951,
                consorcio_id=1,
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
def client(db_session, monkeypatch) -> Iterator[TestClient]:
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Monkeypatch SessionLocal para que middleware (ej. ImpersonateAudit) escriba
    # en la misma DB que la fixture. Envolvemos la session en un proxy que
    # ignora close() para no romper la fixture al terminar el request.
    from backend import database as _db_module

    class _NoCloseSession:
        def __init__(self, s):
            self._s = s

        def __getattr__(self, name):
            return getattr(self._s, name)

        def close(self):
            pass

    def _factory():
        return _NoCloseSession(db_session)

    monkeypatch.setattr(_db_module, "SessionLocal", _factory)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def headers_admin() -> dict[str, str]:
    token = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    return {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}


@pytest.fixture()
def headers_depto_a() -> dict[str, str]:
    token = create_access_token(user_id=2, rol=Rol.departamento, departamento_id=1)
    return {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}


@pytest.fixture()
def headers_depto_b() -> dict[str, str]:
    token = create_access_token(user_id=3, rol=Rol.departamento, departamento_id=2)
    return {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}


@pytest.fixture()
def headers_representante() -> dict[str, str]:
    token = create_access_token(user_id=4, rol=Rol.representante, departamento_id=None)
    return {"Authorization": f"Bearer {token}", "X-Consorcio-Id": "1"}


@pytest.fixture()
def headers_super_admin(db_session) -> dict[str, str]:
    from backend.models import Rol as _Rol, Usuario as _Usuario
    sa = _Usuario(
        id=5, email="sa@test.local",
        password_hash=_PASSWORD_HASH,
        rol=_Rol.super_admin,
    )
    db_session.add(sa)
    db_session.commit()
    token = create_access_token(user_id=5, rol=_Rol.super_admin, departamento_id=None)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def db(db_session) -> Iterator:
    """Alias for db_session (short name for unit tests)."""
    yield db_session


@pytest.fixture()
def dos_consorcios(db_session):
    """Provisiona un segundo consorcio (id=2) con su admin y depto para tests de
    aislamiento multitenant. Se apoya en el seed de consorcio 1 ya existente.

    Devuelve un dict con headers para operar contra cada consorcio y para simular
    intentos de spoofing (admin de c1 con X-Consorcio-Id=2)."""
    from backend.models import Administracion, Caja, Consorcio, Departamento

    admin2 = Administracion(
        id=2,
        razon_social="Administración 2",
        cuit="30-22222222-2",
        email_contacto="admin2@test.local",
    )
    db_session.add(admin2)
    db_session.flush()

    consorcio2 = Consorcio(
        id=2,
        administracion_id=2,
        nombre="Consorcio Aislado",
        consorcio_domicilio="Av. Aislada 200",
        consorcio_cuit="30-88888888-8",
        admin_nombre="Admin 2",
        admin_domicilio="Oficinas 300",
        admin_email="admin2@test.local",
        admin_telefono="11-2222-2222",
        admin_cuit="20-22222222-2",
        admin_rpa="0002",
        admin_situacion_fiscal="Monotributo",
        banco_titular="Consorcio Aislado",
        banco_nombre="Banco Aislado",
        banco_sucursal="002",
        banco_numero_cuenta="000-9999999/9",
        banco_cbu="1111111111111111111111",
    )
    db_session.add(consorcio2)
    db_session.flush()

    depto_c2 = Departamento(
        id=3, consorcio_id=2, codigo="UF-1A", descripcion="Depto C2-1"
    )
    db_session.add(depto_c2)
    db_session.flush()

    caja_c2 = Caja(
        id=901, consorcio_id=2, nombre="Banco C2",
        tipo=TipoCaja.banco, saldo_inicial=0.0, activa=True,
    )
    db_session.add(caja_c2)
    db_session.flush()
    consorcio2.caja_default_pagos_id = 901

    admin_c2 = Usuario(
        id=6,
        email="admin_c2@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.administracion,
        administracion_id=2,
    )
    depto_c2_user = Usuario(
        id=7,
        email="depto_c2@test.local",
        password_hash=_PASSWORD_HASH,
        rol=Rol.departamento,
        departamento_id=3,
    )
    db_session.add_all([admin_c2, depto_c2_user])
    db_session.commit()

    token_admin_c1 = create_access_token(user_id=1, rol=Rol.administracion, departamento_id=None)
    token_admin_c2 = create_access_token(user_id=6, rol=Rol.administracion, departamento_id=None)
    token_depto_c1_a = create_access_token(user_id=2, rol=Rol.departamento, departamento_id=1)
    token_depto_c2 = create_access_token(user_id=7, rol=Rol.departamento, departamento_id=3)

    return {
        "consorcio_1_id": 1,
        "consorcio_2_id": 2,
        "depto_c1_id": 1,
        "depto_c2_id": 3,
        "headers_admin_c1": {"Authorization": f"Bearer {token_admin_c1}", "X-Consorcio-Id": "1"},
        "headers_admin_c2": {"Authorization": f"Bearer {token_admin_c2}", "X-Consorcio-Id": "2"},
        "headers_depto_c1": {"Authorization": f"Bearer {token_depto_c1_a}", "X-Consorcio-Id": "1"},
        "headers_depto_c2": {"Authorization": f"Bearer {token_depto_c2}", "X-Consorcio-Id": "2"},
        # Spoof: admin de c1 intenta operar contra c2.
        "headers_admin_c1_spoof_c2": {"Authorization": f"Bearer {token_admin_c1}", "X-Consorcio-Id": "2"},
        # Spoof: admin de c2 intenta operar contra c1.
        "headers_admin_c2_spoof_c1": {"Authorization": f"Bearer {token_admin_c2}", "X-Consorcio-Id": "1"},
    }
