from datetime import date

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from backend.models import Administracion, Base, Consorcio, Departamento
from backend.seed_demo import _resetear_esquema, meses_demo, perfiles_deterministas


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
