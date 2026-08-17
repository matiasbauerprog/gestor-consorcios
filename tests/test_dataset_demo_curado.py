# tests/test_dataset_demo_curado.py
"""Verificaciones sobre la base demo ya generada.

Se saltean si `demo.db` no existe: no generan la base (tarda ~70 s), sólo la
auditan. Correr primero el comando de regeneración de la cabecera del plan.
"""
import sqlite3
from pathlib import Path

import pytest

from backend.caja_saldo import MovimientoSnapshot, calcular_saldo

DB = Path("demo.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="falta demo.db generada")


@pytest.fixture
def con():
    c = sqlite3.connect(DB)
    yield c
    c.close()


def test_la_caja_no_esta_en_rojo(con):
    # No existe una columna `saldo_actual` en `cajas`: el saldo se calcula en
    # tiempo real a partir del saldo inicial y los movimientos, con la misma
    # función pura que usa el backend (backend/caja_saldo.py).
    #
    # El modelo soporta varias cajas por consorcio (el seed base del proyecto
    # llega a crear tres). Filtramos `movimientos_caja` por el `caja_id` de la
    # caja elegida para no mezclar el saldo inicial de una con los
    # movimientos de todas — hoy el dataset demo tiene una sola caja, pero el
    # filtro deja el test correcto igual si el día de mañana agrega otra.
    caja_id, ini = con.execute("select id, saldo_inicial from cajas limit 1").fetchone()
    movs = [
        MovimientoSnapshot(tipo=t, monto=m)
        for t, m in con.execute(
            "select tipo, monto from movimientos_caja where caja_id = ?", (caja_id,)
        )
    ]
    saldo = calcular_saldo(ini, movs)
    assert saldo > 0


def test_hay_comprobantes_esperando_aprobacion(con):
    (n,) = con.execute(
        "select count(*) from comprobantes where estado = 'pendiente_verificacion'"
    ).fetchone()
    assert n >= 1


def test_el_propietario_al_dia_no_tiene_mora(con):
    filas = con.execute("""
        select m.tipo from movimientos_cuenta m
        join departamentos d on d.id = m.departamento_id
        where d.codigo = 'UF-01A' and m.tipo in ('recargo', 'interes_punitorio')
    """).fetchall()
    assert filas == []


def test_el_propietario_moroso_si_tiene_mora(con):
    # Contracara del test anterior: el dataset necesita el contraste entre una
    # unidad al día y otra en mora. Un test que sólo mire a UF-01A pasaría
    # igual si el generador dejara de aplicar recargos a todo el mundo.
    filas = con.execute("""
        select m.tipo from movimientos_cuenta m
        join departamentos d on d.id = m.departamento_id
        where d.codigo = 'UF-03C' and m.tipo in ('recargo', 'interes_punitorio')
    """).fetchall()
    assert filas != []


def test_las_expensas_no_se_emitieron_todas_el_mismo_dia(con):
    fechas = con.execute("""
        select distinct m.fecha from movimientos_cuenta m
        join departamentos d on d.id = m.departamento_id
        where d.codigo = 'UF-01A' and m.tipo = 'expensa_emitida'
    """).fetchall()
    assert len(fechas) >= 5


def test_cada_gasto_tiene_un_proveedor_plausible(con):
    # Patrones alineados con el mapa rubro -> proveedor real de
    # backend/seed_demo.py (_PROVEEDOR_POR_RUBRO): seguros -> "Seguros La
    # Continental", gastos_bancarios -> "Banco Ciudad", gastos_administracion
    # -> "Estudio Rossi & Asociados".
    rubros = ("seguros", "gastos_bancarios", "gastos_administracion")

    incoherentes = con.execute("""
        select g.concepto, p.razon_social
        from gastos g join proveedores p on p.id = g.proveedor_id
        where (g.rubro = 'seguros' and p.razon_social not like '%Seguros%')
           or (g.rubro = 'gastos_bancarios' and p.razon_social not like '%Banco%')
           or (g.rubro = 'gastos_administracion' and p.razon_social not like '%Estudio%')
    """).fetchall()
    assert incoherentes == []

    # `incoherentes == []` también sería cierto si el join no encontrara
    # ningún gasto de estos rubros (rubro renombrado, join roto, etc.): una
    # ausencia sin contraparte de presencia no prueba nada. Exigimos que cada
    # uno de los tres rubros haya tenido al menos un gasto evaluado.
    for rubro in rubros:
        (n,) = con.execute(
            "select count(*) from gastos g join proveedores p on p.id = g.proveedor_id "
            "where g.rubro = ?",
            (rubro,),
        ).fetchone()
        assert n >= 1, f"no se evaluó ningún gasto del rubro {rubro!r}"


def test_la_obra_de_frente_suma_el_costo_total_una_sola_vez(con):
    # crear_plan_cuotas replica el mismo `monto` en cada una de las
    # `cuota_total` cuotas (no divide el total entre cuotas). Si alguien
    # vuelve a mandarle el costo total en vez del importe por cuota, la obra
    # termina sumando 6 veces más de lo real. El total de las seis cuotas
    # tiene que dar exactamente el costo de la obra.
    total, n = con.execute("""
        select sum(monto), count(*) from gastos
        where concepto = 'Reparación integral del frente del edificio'
    """).fetchone()
    assert n == 6
    assert total == pytest.approx(7_200_000.0)


def test_los_comprobantes_tienen_imagenes_de_verdad(con):
    # archivo_path se guarda relativo a UPLOAD_DIR (p. ej.
    # "comprobantes/abc123.png"), no relativo a la raíz del repo ni como URL
    # absoluta — ver backend/storage.py:guardar_imagen_comprobante. No usamos
    # `get_settings().UPLOAD_DIR` acá porque el fixture autouse
    # `_temp_upload_dir` de tests/conftest.py lo redirige a un tmp_path en
    # TODOS los tests de la suite (para no escribir en el filesystem real);
    # demo.db, en cambio, apunta a los archivos reales servidos en
    # producción, así que resolvemos contra el default real de
    # `backend/config.py::Settings.UPLOAD_DIR`.
    upload_dir = Path("backend/uploads")
    rutas = con.execute(
        "select archivo_path from comprobantes where archivo_path is not null limit 5"
    ).fetchall()
    assert rutas, "ningún comprobante tiene archivo"
    for (ruta,) in rutas:
        archivo = upload_dir / ruta
        assert archivo.exists(), f"falta {archivo}"
        assert archivo.stat().st_size > 2_000, f"{archivo} parece un PNG de 1px"
