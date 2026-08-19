from datetime import date

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from backend.models import Administracion, Base, Consorcio, Departamento
from backend.seed_demo import (
    COSTO_TOTAL_OBRA_DEMO,
    CUOTAS_OBRA_DEMO,
    _CUOTA_OBRA_ESTIMADA,
    _resetear_esquema,
    deja_pendiente,
    estimar_gasto_mensual_demo,
    importe_por_cuota,
    meses_demo,
    perfiles_deterministas,
    saldo_inicial_caja,
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


def test_cada_concepto_de_rubros_comunes_tiene_un_proveedor_plausible():
    # Los tres conceptos de "abonos_y_servicios" son el caso que motivó el
    # cambio de rubro a concepto: antes los tres facturaban a la empresa de
    # limpieza porque el mapa sólo distinguía por rubro.
    from backend.seed_demo import PROVEEDORES_DEMO, proveedor_para_gasto

    proveedores = {razon: i + 1 for i, razon in enumerate(PROVEEDORES_DEMO)}
    esperado = {
        ("gastos_administracion", "Honorarios administración"): "Estudio Rossi & Asociados",
        ("seguros", "Seguro integral consorcio"): "Seguros La Continental",
        ("servicios_publicos", "AySA agua común"): "Servicios Metropolitanos SA",
        ("servicios_publicos", "Edesur espacios comunes"): "Servicios Metropolitanos SA",
        ("gastos_bancarios", "Comisiones bancarias"): "Banco Ciudad",
        ("abonos_y_servicios", "Abono limpieza"): "Limpieza Total SRL",
        ("abonos_y_servicios", "Abono ascensores"): "Ascensores Vertirod SA",
        ("abonos_y_servicios", "Fumigación mensual"): "Limpieza Total SRL",
        ("mantenimiento_partes_comunes", "Mantenimiento bombas"): "ElectroSur SRL",
    }
    for (rubro, concepto), razon in esperado.items():
        assert proveedor_para_gasto(rubro, concepto, proveedores, None) == proveedores[razon]


def test_proveedores_de_ascensores_y_electricidad_facturan_algo():
    # El defecto original: dos proveedores del catálogo (Ascensores Vertirod
    # SA, ElectroSur SRL) nunca resultaban elegidos por ningún gasto.
    from backend.seed_demo import PROVEEDORES_DEMO, _PROVEEDOR_POR_CONCEPTO

    assert "Ascensores Vertirod SA" in _PROVEEDOR_POR_CONCEPTO.values()
    assert "ElectroSur SRL" in _PROVEEDOR_POR_CONCEPTO.values()
    assert "Ascensores Vertirod SA" in PROVEEDORES_DEMO
    assert "ElectroSur SRL" in PROVEEDORES_DEMO


def test_gastos_sin_concepto_propio_caen_en_el_comodin_del_rubro():
    # Reparaciones privadas, la obra de frente y el sueldo del encargado no
    # salen de RUBROS_COMUNES: su concepto no está en el mapa y tienen que
    # caer en el comodín "*<rubro>", no en el proveedor del primer rubro
    # cualquiera.
    from backend.seed_demo import PROVEEDORES_DEMO, proveedor_para_gasto

    proveedores = {razon: i + 1 for i, razon in enumerate(PROVEEDORES_DEMO)}
    assert proveedor_para_gasto(
        "trabajos_reparaciones_unidades", "Reparación privada UF-02B", proveedores, None
    ) == proveedores["Plomería Paz"]
    assert proveedor_para_gasto(
        "sueldos_y_cargas_sociales", "", proveedores, None
    ) == proveedores["Estudio Rossi & Asociados"]


def test_proveedor_para_gasto_sin_rubro_ni_concepto_conocidos_cae_en_uno_generico():
    from backend.seed_demo import PROVEEDORES_DEMO, proveedor_para_gasto

    proveedores = {razon: i + 1 for i, razon in enumerate(PROVEEDORES_DEMO)}
    elegido = proveedor_para_gasto("rubro_que_no_existe", "concepto_inexistente", proveedores, None)
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


def test_con_un_solo_pago_no_deja_nada_pendiente():
    # cupo = min(3, 1 // 2) = 0: con un único pagador, ese pago tiene que
    # quedar cobrado, no colgado esperando aprobación.
    assert deja_pendiente(0, 1, es_ultimo_periodo=True) is False


def test_con_cero_pagos_el_resultado_es_irrelevante_en_la_practica():
    # Caso degenerado documentado, no una garantía: con total_pagos=0 no hay
    # ningún índice válido para invocar la función (el generador nunca llama
    # a deja_pendiente si no hay pagos), así que el valor que devuelva no
    # importa. Lo que este test fija es el comportamiento actual —
    # cupo = min(3, 0 // 2) = 0 y 0 >= 0 - 0 da True para cualquier índice—
    # para que un cambio futuro que lo altere sea una decisión explícita y
    # no una regresión silenciosa.
    assert deja_pendiente(0, 0, es_ultimo_periodo=True) is True


def test_estimar_gasto_mensual_demo_excluye_las_filas_de_sueldos():
    # poblar_demo saltea las filas "sueldos_y_cargas_sociales" de
    # RUBROS_COMUNES (las genera la liquidación aparte), así que sus rangos
    # no deben sumar al estimado.
    con_sueldos = [
        ("sueldos_y_cargas_sociales", "Sueldo", 900_000, 1_300_000),
        ("seguros", "Seguro", 90_000, 140_000),
    ]
    sin_sueldos = [("seguros", "Seguro", 90_000, 140_000)]
    assert estimar_gasto_mensual_demo(con_sueldos) == estimar_gasto_mensual_demo(sin_sueldos)


def test_estimar_gasto_mensual_demo_reacciona_a_nuevas_filas():
    # La razón de ser de esta función: agregar un rubro a RUBROS_COMUNES tiene
    # que mover el estimado, así nadie tiene que acordarse de actualizar un
    # literal a mano en otro lado del archivo.
    base = [("seguros", "Seguro", 90_000, 140_000)]
    con_fila_nueva = base + [("gastos_bancarios", "Comisión extra", 10_000, 30_000)]
    assert estimar_gasto_mensual_demo(con_fila_nueva) == pytest.approx(
        estimar_gasto_mensual_demo(base) + 20_000
    )


def test_estimar_gasto_mensual_demo_con_rubros_comunes_reales_ronda_los_4_millones():
    # No es un valor fijo pinneado (RUBROS_COMUNES puede cambiar), sino una
    # banda amplia que confirma que la cuenta da un orden de magnitud
    # razonable para un consorcio de 18 UF, no un número descolgado de la
    # realidad del dataset.
    # Banda rehacible: comunes (~1.059.000) + reparaciones privadas (105.000)
    # + sueldo del encargado (~1.643.340) + cuota de la obra (1.200.000, no el
    # costo total) ronda los 4.007.340 — antes de corregir `_CUOTA_OBRA_ESTIMADA`
    # para que valga la cuota y no el total de la obra, esta cuenta rondaba los
    # 10.007.340 porque sumaba la obra entera.
    from backend.seed_e2e import RUBROS_COMUNES

    estimado = estimar_gasto_mensual_demo(RUBROS_COMUNES)
    assert 3_000_000 < estimado < 5_000_000


def test_el_importe_por_cuota_divide_el_total():
    # `crear_plan_cuotas` repite `monto` una vez por cuota sin dividirlo, así
    # que el generador tiene que mandarle ya dividido el total de la obra.
    assert importe_por_cuota(7_200_000.0, 6) == 1_200_000.0


def test_la_obra_del_demo_suma_su_costo_total_y_no_seis_veces_mas():
    assert importe_por_cuota(COSTO_TOTAL_OBRA_DEMO, CUOTAS_OBRA_DEMO) * CUOTAS_OBRA_DEMO == COSTO_TOTAL_OBRA_DEMO


def test_la_estimacion_de_gasto_usa_la_cuota_real_y_no_el_total():
    # _CUOTA_OBRA_ESTIMADA alimenta el fondo de reserva. Si sigue valiendo el
    # total, el fondo queda calculado sobre un gasto seis veces mayor al real.
    assert _CUOTA_OBRA_ESTIMADA == importe_por_cuota(COSTO_TOTAL_OBRA_DEMO, CUOTAS_OBRA_DEMO)


def test_saldo_inicial_cubre_el_deficit_de_los_meses_sembrados():
    # 10M por mes de gastos, 6 meses: el fondo tiene que aguantar la porción
    # que la morosidad deja sin cubrir y todavía quedar en positivo.
    assert saldo_inicial_caja(10_000_000, 6) > 0


def test_saldo_inicial_escala_con_la_cantidad_de_meses():
    assert saldo_inicial_caja(10_000_000, 12) > saldo_inicial_caja(10_000_000, 6)


def test_saldo_inicial_es_un_numero_redondo():
    # Un fondo de reserva con centavos se lee como un cálculo, no como un
    # saldo real de arranque.
    assert saldo_inicial_caja(10_000_000, 6) % 100_000 == 0


def test_seed_demo_no_expone_guard_de_reentrada():
    """El guard GENERANDO se elimino junto con el seed-on-boot.

    Existia para cortar la recursion lifespan -> generar -> TestClient ->
    lifespan. Sin seed-on-boot ese camino no existe y la constante quedaba
    escrita pero nunca leida.
    """
    from backend import seed_demo

    assert not hasattr(seed_demo, "GENERANDO")


# --- imagen_comprobante ----------------------------------------------------
# _PNG_1PX renderiza como miniatura rota en la pantalla de comprobantes, que
# es parte del circuito de demo. imagen_comprobante() rota entre capturas
# genéricas reales para que se vea un comprobante de verdad.


def test_imagen_comprobante_devuelve_un_png_de_verdad():
    from backend.seed_demo import imagen_comprobante

    datos = imagen_comprobante(0)
    assert datos.startswith(b"\x89PNG\r\n\x1a\n")
    # Un PNG de 1px pesa ~70 bytes; cualquier captura real pesa mucho más.
    assert len(datos) > 2_000


def test_imagen_comprobante_rota_entre_las_disponibles():
    from backend.seed_demo import imagen_comprobante

    assert imagen_comprobante(0) != imagen_comprobante(1)


def test_imagen_comprobante_no_se_pasa_de_indice():
    from backend.seed_demo import imagen_comprobante

    # Con más pagos que imágenes, tiene que seguir devolviendo alguna.
    assert imagen_comprobante(99).startswith(b"\x89PNG\r\n\x1a\n")


# --- fecha_pago_puntual -----------------------------------------------------
# La version anterior (`min(f1 - randint(0,5), date.today())`) podia dejar el
# pago en o despues del vencimiento cuando f1 era futuro respecto de hoy, asi
# que UF-01A -pinneado como pagador puntual- terminaba con recargo por mora e
# intereses punitorios en la demo.


import random

from backend.seed_demo import fecha_pago_puntual


def test_un_pagador_puntual_paga_antes_del_vencimiento():
    rng = random.Random(1)
    f1 = date(2026, 8, 10)
    for _ in range(20):
        pago = fecha_pago_puntual(f1, hoy=date(2026, 8, 16), rng=rng)
        assert pago < f1, "un pago puntual nunca puede caer en o después del vencimiento"


def test_el_pago_no_queda_en_el_futuro_respecto_de_hoy():
    rng = random.Random(1)
    # Vencimiento dentro de un mes: el pago tiene que ser creíble hoy, no
    # una fecha que todavía no ocurrió.
    pago = fecha_pago_puntual(date(2026, 9, 10), hoy=date(2026, 8, 16), rng=rng)
    assert pago <= date(2026, 8, 16)


def test_el_pago_cae_dentro_de_los_dias_previos_al_vencimiento():
    rng = random.Random(7)
    f1 = date(2026, 8, 10)
    pago = fecha_pago_puntual(f1, hoy=date(2026, 8, 16), rng=rng)
    assert (f1 - pago).days <= 6


# --- dia_de_cierre / reloj_en -----------------------------------------------
# El brief original sólo pedía parchear routers/periodos.py. La revisión de
# la tarea anterior rastreó el camino completo de POST /periodos/{p}/cerrar →
# GET /expensas → POST /comprobantes y encontró que cierre.py y recargos.py
# también leen date.today() sin que nadie se lo pase — y ambos corren DENTRO
# de ese camino (cierre.py incluso antes que periodos.py). Sin parchear los
# tres, el devengamiento de recargos e intereses queda atado a la fecha real
# de la corrida, no a la fecha histórica del período, y unidades puntuales
# terminan con recargo por un pago que todavía no se cargó.

from backend.seed_demo import dia_de_cierre, reloj_en


def test_el_cierre_cae_a_principios_del_mes_siguiente():
    # Las expensas de julio se emiten en agosto, no en julio.
    assert dia_de_cierre("2026-07") == date(2026, 8, 1)


def test_el_cierre_de_diciembre_cruza_el_anio():
    assert dia_de_cierre("2026-12") == date(2027, 1, 1)


def test_reloj_en_hace_que_periodos_cierre_y_recargos_vean_la_misma_fecha():
    """Los tres módulos que `POST /periodos/{p}/cerrar → GET /expensas` toca
    sin que nadie les pase `hoy` tienen que ver la fecha simulada."""
    from backend import cierre, recargos
    from backend.routers import periodos

    with reloj_en(date(2026, 3, 1)):
        assert periodos.date.today() == date(2026, 3, 1)
        assert cierre.date.today() == date(2026, 3, 1)
        assert recargos.date.today() == date(2026, 3, 1)

    # Y los restaura a todos al salir.
    assert periodos.date.today() == date.today()
    assert cierre.date.today() == date.today()
    assert recargos.date.today() == date.today()


def test_reloj_en_no_toca_el_date_de_seed_demo():
    # fecha_pago_puntual recibe el date.today() de este módulo (seed_demo),
    # no el de periodos/cierre/recargos: reloj_en no debe pisarlo, o el tope
    # "nunca una fecha futura" pasaría a compararse contra el día de cierre
    # simulado (anterior al vencimiento) en vez de la fecha real del proceso.
    from backend import seed_demo

    real_hoy = date.today()
    with reloj_en(date(2020, 1, 1)):
        assert seed_demo.date.today() == real_hoy


def test_reloj_en_revierte_los_tres_parches_aunque_el_bloque_explote():
    # poblar_demo cierra 6 períodos seguidos dentro de reloj_en. Si algo
    # revienta a mitad de uno (una API que devuelve un status inesperado,
    # por ejemplo) y el parche quedara pegado, contaminaría con la fecha
    # simulada TODO lo que corra después — incluidos los períodos
    # siguientes. La garantía la da `unittest.mock.patch` como context
    # manager (restaura en `__exit__` incluso si el `with` propaga una
    # excepción), pero es justo la clase de cosa que se verifica con un
    # test, no con confianza en la biblioteca estándar.
    from backend import cierre, recargos
    from backend.routers import periodos

    class _ExplotoAMitadDelBloque(Exception):
        pass

    with pytest.raises(_ExplotoAMitadDelBloque):
        with reloj_en(date(2020, 5, 5)):
            assert periodos.date.today() == date(2020, 5, 5)
            raise _ExplotoAMitadDelBloque("una API falla a mitad del período")

    assert periodos.date.today() == date.today()
    assert cierre.date.today() == date.today()
    assert recargos.date.today() == date.today()


def test_reloj_en_no_arrastra_la_fecha_simulada_entre_dos_entradas_seguidas():
    # El generador entra a este bloque una vez por período, 6 veces
    # seguidas. Si la restauración de una vuelta quedara pisada por la
    # siguiente, la segunda entrada heredaría la fecha simulada de la
    # primera en vez de partir de la fecha real.
    from backend.routers import periodos

    real_hoy = date.today()

    with reloj_en(date(2026, 1, 1)):
        assert periodos.date.today() == date(2026, 1, 1)
    assert periodos.date.today() == real_hoy

    with reloj_en(date(2026, 6, 1)):
        assert periodos.date.today() == date(2026, 6, 1)
    assert periodos.date.today() == real_hoy


def test_fecha_fija_no_admite_construccion_directa():
    # `_FechaFija` sólo debe responder `.today()`. Si algo bajo el patch
    # construye una fecha por afuera de `.today()` (`date(y, m, d)`,
    # aritmética que preserve la subclase vía `fromordinal`, etc.), la
    # instancia resultante llevaría un `.today()` fijo para siempre y
    # podría terminar grabada en `fecha_primer_vencimiento` /
    # `fecha_segundo_vencimiento` si algún día ese código corre bajo el
    # patch. Hoy nada lo dispara (`cierre._calcular_fechas_default` es la
    # única construcción directa del módulo, y sólo corre si las fechas
    # llegan en None — `poblar_demo` siempre las manda explícitas), pero
    # eso es un invariante del llamador, no algo que reloj_en deba confiar
    # que se mantenga: por eso el constructor falla ruidoso en vez de
    # dejar pasar el objeto en silencio.
    from backend.routers import periodos

    with reloj_en(date(2026, 3, 1)):
        with pytest.raises(TypeError):
            periodos.date(2026, 3, 10)


def test_resetear_esquema_tambien_borra_la_version_de_alembic(engine_demo):
    # `alembic_version` no pertenece a Base.metadata —la maneja Alembic—, así
    # que `drop_all` no la toca y sobrevivía al reset marcada en la cabeza. El
    # `alembic upgrade head` que viene después la leía, concluía que no había
    # nada que aplicar, y dejaba la base sin una sola tabla: el generador moría
    # con "no such table: usuarios". Sólo se notaba regenerando sobre una
    # demo.db ya existente; con el archivo borrado a mano andaba, y por eso
    # pasó desapercibido.
    from sqlalchemy import text

    _poblar_con_fks(engine_demo)
    with engine_demo.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('2f598eb91171')"))
    assert "alembic_version" in inspect(engine_demo).get_table_names()

    _resetear_esquema(engine_demo)

    assert inspect(engine_demo).get_table_names() == []
