from datetime import date

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from backend.models import Administracion, Base, Consorcio, Departamento
from backend.seed_demo import (
    _resetear_esquema,
    deja_pendiente,
    meses_demo,
    perfiles_deterministas,
)


def test_meses_demo_devuelve_los_6_meses_completos_anteriores():
    # El mes en curso (julio) queda deliberadamente abierto: el visitante
    # tiene un periodo vivo para cargar gastos y probar el cierre el mismo.
    assert meses_demo(date(2026, 7, 31)) == [
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
    ]


def test_meses_demo_cruza_el_anio_correctamente():
    assert meses_demo(date(2026, 3, 15)) == [
        "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02",
    ]


def test_meses_demo_desde_enero():
    assert meses_demo(date(2026, 1, 1)) == [
        "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    ]


def test_meses_demo_respeta_la_cantidad():
    assert meses_demo(date(2026, 7, 31), cantidad=2) == ["2026-05", "2026-06"]


def _deptos(n):
    letras = "ABCDEF"
    return [
        {"id": i + 1, "codigo": f"UF-{i // 6 + 1:02d}{letras[i % 6]}"}
        for i in range(n)
    ]


def test_perfiles_pinnean_uf01a_puntual_y_uf03c_moroso():
    # El selector de rol apunta a uf01a@ y uf03c@, asi que su comportamiento
    # no puede salir de un shuffle: tiene que ser estable entre corridas.
    puntuales, irregulares, morosos = perfiles_deterministas(_deptos(18))
    assert "UF-01A" in {d["codigo"] for d in puntuales}
    assert "UF-03C" in {d["codigo"] for d in morosos}


def test_perfiles_reparten_18_deptos_como_12_3_3():
    puntuales, irregulares, morosos = perfiles_deterministas(_deptos(18))
    assert (len(puntuales), len(irregulares), len(morosos)) == (12, 3, 3)


def test_perfiles_no_pierden_ni_duplican_deptos():
    deptos = _deptos(18)
    puntuales, irregulares, morosos = perfiles_deterministas(deptos)
    ids = [d["id"] for d in puntuales + irregulares + morosos]
    assert sorted(ids) == sorted(d["id"] for d in deptos)


def test_perfiles_es_estable_entre_corridas():
    a = perfiles_deterministas(_deptos(18))
    b = perfiles_deterministas(_deptos(18))
    assert [[d["codigo"] for d in grupo] for grupo in a] == \
           [[d["codigo"] for d in grupo] for grupo in b]


# --- _resetear_esquema ----------------------------------------------------
# El reset es codigo nuevo, escrito para arreglar un bug real: drop_all pelado
# moria con "FOREIGN KEY constraint failed" sobre una base con datos, porque
# backend/database.py activa PRAGMA foreign_keys=ON en cada conexion y el
# modelo tiene un ciclo de FK. Se testea contra un engine SQLite temporal que
# replica ese listener.


@pytest.fixture
def engine_demo(tmp_path):
    """Engine SQLite de archivo que replica el listener de backend/database.py.

    De archivo y no :memory: a proposito: el bug que cubren estos tests es del
    reciclado del QueuePool, y con :memory: + StaticPool el pool se comporta
    distinto y el test no probaria nada.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'reset-demo.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # mismo listener que backend/database.py:19-24
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def _poblar_con_fks(engine):
    """Filas encadenadas por FK: sin ellas el drop_all nunca fallaria."""
    with Session(engine) as db:
        db.add(Administracion(id=1, razon_social="Administración Reset",
                              cuit="30-11111111-1", email_contacto="reset@demo.local"))
        db.flush()
        db.add(Consorcio(
            id=1, administracion_id=1, nombre="Consorcio Reset",
            consorcio_domicilio="Av. Reset 100", consorcio_cuit="30-99999999-9",
            admin_nombre="Admin Reset", admin_domicilio="Oficinas 200",
            admin_email="admin@demo.local", admin_telefono="11-1111-1111",
            admin_cuit="20-11111111-1", admin_rpa="0001",
            admin_situacion_fiscal="Monotributo", banco_titular="Consorcio Reset",
            banco_nombre="Banco Reset", banco_sucursal="001",
            banco_numero_cuenta="000-1234567/8",
            banco_cbu="0000000000000000000000",
        ))
        db.flush()
        db.add(Departamento(id=1, consorcio_id=1, codigo="UF-01A"))
        db.commit()


def _fk_de_una_conexion_nueva(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("PRAGMA foreign_keys")).scalar()


def test_resetear_esquema_borra_las_tablas_con_datos_cargados(engine_demo):
    # El caso que rompia: drop_all pelado tira IntegrityError en el DROP de la
    # primera tabla referenciada por otra que tiene filas.
    _poblar_con_fks(engine_demo)
    assert inspect(engine_demo).get_table_names()

    _resetear_esquema(engine_demo)

    assert inspect(engine_demo).get_table_names() == []


def test_resetear_esquema_no_deja_las_fks_apagadas_en_el_proceso(engine_demo):
    # Regresion: apagar el pragma y salir del `with` devuelve la conexion al
    # pool con foreign_keys=OFF, y el listener solo corre en conexiones fisicas
    # nuevas. Sin el dispose() el proceso seguia sin integridad referencial, en
    # silencio. Se mide sobre la conexion SIGUIENTE, no sobre la del drop.
    _poblar_con_fks(engine_demo)
    assert _fk_de_una_conexion_nueva(engine_demo) == 1

    _resetear_esquema(engine_demo)

    assert _fk_de_una_conexion_nueva(engine_demo) == 1


def test_crear_catalogo_personal_esta_exportado():
    # Contrato con la Task 6: el catalogo se crea antes del loop de meses.
    from backend.seed_demo import crear_catalogo_personal
    assert callable(crear_catalogo_personal)


def test_resetear_esquema_restaura_las_fks_aunque_el_drop_falle(engine_demo,
                                                               monkeypatch):
    # El dispose() va en `finally` justamente por esto: si el drop explota a
    # mitad de camino, la conexion vuelve al pool igual de envenenada.
    def _explota(*args, **kwargs):
        raise RuntimeError("drop roto a proposito")

    monkeypatch.setattr(Base.metadata, "drop_all", _explota)

    with pytest.raises(RuntimeError):
        _resetear_esquema(engine_demo)

    assert _fk_de_una_conexion_nueva(engine_demo) == 1


def test_comunicados_demo_tiene_contenido_variado():
    from backend.seed_demo import COMUNICADOS_DEMO
    assert len(COMUNICADOS_DEMO) >= 10
    # Titulo y cuerpo no vacios en todos.
    assert all(t.strip() and c.strip() for t, c in COMUNICADOS_DEMO)
    # Sin titulos repetidos: un demo con 12 avisos iguales se ve falso.
    assert len({t for t, _ in COMUNICADOS_DEMO}) == len(COMUNICADOS_DEMO)


class _ConexionPostgresFalsa:
    """Registra los statements que le llegan en vez de ejecutarlos.

    No hay Postgres real en este entorno (ver reporte de la Task 7), asi que
    no podemos verificar el DROP SCHEMA contra una base de verdad. Esto es
    lo mejor que se puede hacer sin levantar un Postgres en CI: capturar el
    SQL que _resetear_esquema emite realmente, en el orden en que lo emite,
    en vez de inspeccionar el codigo fuente como texto (fragil ante
    refactors que muevan la rama a otra funcion sin cambiar su
    comportamiento).
    """

    def __init__(self):
        self.statements: list[str] = []

    def execute(self, clause):
        self.statements.append(str(clause))


class _EnginePostgresFalso:
    """Engine minimo que finge ser Postgres para _resetear_esquema.

    Solo implementa lo que la rama no-sqlite de _resetear_esquema toca:
    `url.get_backend_name()` y `begin()` como context manager. No abre
    ninguna conexion real.
    """

    def __init__(self):
        self.url = type("Url", (), {"get_backend_name": lambda self: "postgresql"})()
        self.conexion = _ConexionPostgresFalsa()

    def begin(self):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield self.conexion

        return _ctx()


def test_resetear_esquema_en_postgres_hace_drop_schema_cascade_y_recrea():
    """En Postgres, drop_all choca con el mismo ciclo de FK que en SQLite.

    El modelo tiene un ciclo cajas -> consorcios -> presupuestos -> trabajos, y
    drop_all ordena las tablas topologicamente: con un ciclo no puede, avisa por
    SAWarning y falla al soltar una tabla todavia referenciada. En Postgres la
    salida limpia es DROP SCHEMA ... CASCADE, que no depende del orden.

    Test de comportamiento (que SQL se emite y en que orden), no de forma
    textual del codigo: sobrevive a un refactor que mueva esta rama a otra
    funcion, y ademas verifica el orden DROP -> CREATE, que la version
    anterior basada en inspect.getsource no cubria.
    """
    from backend.seed_demo import _resetear_esquema

    engine_falso = _EnginePostgresFalso()

    _resetear_esquema(engine_falso)

    statements = [s.upper() for s in engine_falso.conexion.statements]
    assert statements == ["DROP SCHEMA PUBLIC CASCADE", "CREATE SCHEMA PUBLIC"]


def test_cada_rubro_comun_tiene_un_proveedor_plausible():
    from backend.seed_demo import PROVEEDORES_DEMO, proveedor_para_rubro

    proveedores = {razon: i + 1 for i, (razon, _) in enumerate(PROVEEDORES_DEMO)}
    esperado = {
        "gastos_administracion": "Estudio Rossi & Asociados",
        "seguros": "Seguros La Continental",
        "servicios_publicos": "Servicios Metropolitanos SA",
        "gastos_bancarios": "Banco Ciudad",
        "abonos_y_servicios": "Limpieza Total SRL",
        "mantenimiento_partes_comunes": "Plomería Paz",
        "trabajos_reparaciones_unidades": "Plomería Paz",
    }
    for rubro, razon in esperado.items():
        assert proveedor_para_rubro(rubro, proveedores, None) == proveedores[razon]


def test_proveedor_para_rubro_desconocido_cae_en_uno_generico():
    from backend.seed_demo import PROVEEDORES_DEMO, proveedor_para_rubro

    proveedores = {razon: i + 1 for i, (razon, _) in enumerate(PROVEEDORES_DEMO)}
    elegido = proveedor_para_rubro("rubro_que_no_existe", proveedores, None)
    assert elegido in proveedores.values()


def test_no_deja_pendientes_en_periodos_viejos():
    # Un comprobante sin aprobar en un período ya cerrado descuadraría la
    # cobranza histórica que el resto del dataset da por cobrada.
    assert deja_pendiente(0, 12, es_ultimo_periodo=False) is False
    assert deja_pendiente(5, 12, es_ultimo_periodo=False) is False


def test_deja_los_tres_ultimos_del_ultimo_periodo_pendientes():
    assert deja_pendiente(9, 12, es_ultimo_periodo=True) is True
    assert deja_pendiente(10, 12, es_ultimo_periodo=True) is True
    assert deja_pendiente(11, 12, es_ultimo_periodo=True) is True


def test_los_demas_pagos_del_ultimo_periodo_se_aprueban():
    assert deja_pendiente(0, 12, es_ultimo_periodo=True) is False
    assert deja_pendiente(8, 12, es_ultimo_periodo=True) is False


def test_con_menos_de_tres_pagos_no_deja_todo_pendiente():
    # Con 2 pagos, dejar 3 pendientes dejaría el período sin ninguna cobranza.
    assert deja_pendiente(0, 2, es_ultimo_periodo=True) is False
    assert deja_pendiente(1, 2, es_ultimo_periodo=True) is True


def test_seed_demo_no_expone_guard_de_reentrada():
    """El guard GENERANDO se elimino junto con el seed-on-boot.

    Existia para cortar la recursion lifespan -> generar -> TestClient ->
    lifespan. Sin seed-on-boot ese camino no existe y la constante quedaba
    escrita pero nunca leida.
    """
    from backend import seed_demo

    assert not hasattr(seed_demo, "GENERANDO")
