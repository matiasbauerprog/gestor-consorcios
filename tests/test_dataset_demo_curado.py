# tests/test_dataset_demo_curado.py
"""Verificaciones sobre la base demo ya generada.

Se saltean si `demo.db` no existe: no generan la base (tarda ~70 s), sólo la
auditan. Correr primero el comando de regeneración de la cabecera del plan.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from backend.caja_saldo import MovimientoSnapshot, calcular_saldo
from backend.models import TIPOS_CREDITO, TIPOS_DEBITO

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
    # Patrones alineados con el mapa concepto -> proveedor real de
    # backend/seed_demo.py (_PROVEEDOR_POR_CONCEPTO): seguros -> "Seguros La
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


def test_la_lista_de_morosos_es_razonable(con):
    # C1 de la revisión final: el cargo en cuenta corriente de una reserva de
    # amenity (nota_debito) que nadie pagaba nunca quedaba con el saldo
    # EXACTO del precio del SUM o el Laundry, y /reportes/morosos lo imputaba
    # por antigüedad igual que a un moroso real (mismos
    # periodos_vencidos_impagos, mismo primer_vencimiento_impago). Sobre 18
    # unidades, eso inflaba la mora a 13/18 (72%) con 6 pagadores puntuales
    # adentro. Replica el signo de TIPOS_DEBITO/TIPOS_CREDITO (la misma
    # fuente que usa backend/cuenta_corriente.py) para no duplicar el cálculo
    # de saldo con lógica propia que pueda divergir.
    tipos_debito = {t.value for t in TIPOS_DEBITO}
    tipos_credito = {t.value for t in TIPOS_CREDITO}

    saldo_por_depto: dict[int, float] = {}
    for depto_id, tipo, monto in con.execute(
        "select departamento_id, tipo, monto from movimientos_cuenta"
    ):
        if tipo in tipos_debito:
            signo = 1
        elif tipo in tipos_credito:
            signo = -1
        else:
            continue
        saldo_por_depto[depto_id] = saldo_por_depto.get(depto_id, 0.0) + signo * monto

    morosos = {d: round(s, 2) for d, s in saldo_por_depto.items() if s > 0.01}

    (n_deptos,) = con.execute("select count(*) from departamentos").fetchone()
    assert len(morosos) <= n_deptos // 2, (
        f"{len(morosos)} de {n_deptos} unidades en mora — parece inflado"
    )

    precios_amenity = {
        round(p, 2) for (p,) in con.execute("select precio_reserva from amenities").fetchall()
    }
    for depto_id, saldo in morosos.items():
        assert saldo not in precios_amenity, (
            f"depto {depto_id} figura en mora por ${saldo}, el precio exacto de un amenity"
        )


def test_abono_ascensores_no_lo_factura_la_empresa_de_limpieza(con):
    # I1 de la revisión final: RUBROS_COMUNES tiene tres conceptos bajo
    # "abonos_y_servicios" (limpieza, ascensores, fumigación) y el mapa viejo
    # sólo distinguía por rubro, así que los tres facturaban a la empresa de
    # limpieza y "Ascensores Vertirod SA" no facturaba nada nunca.
    (razon,) = con.execute("""
        select p.razon_social from gastos g
        join proveedores p on p.id = g.proveedor_id
        where g.concepto = 'Abono ascensores' limit 1
    """).fetchone()
    assert "Ascensores" in razon

    (n,) = con.execute("""
        select count(*) from gastos g join proveedores p on p.id = g.proveedor_id
        where p.razon_social = 'Ascensores Vertirod SA'
    """).fetchone()
    assert n >= 1, "Ascensores Vertirod SA no facturó ningún gasto"


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


_DATASET_JSON = Path("frontend/src/demo/dataset.json")


@pytest.mark.skipif(not _DATASET_JSON.exists(), reason="falta el dataset exportado (--exportar)")
def test_los_comprobantes_exportados_apuntan_a_archivos_que_existen():
    # C2 de la revisión final: el volcado estático conservaba
    # "archivo_path": "/uploads/comprobantes/<hash>.png", que en la demo sin
    # backend no carga nada. Tiene que apuntar a un archivo estático real,
    # servido por el propio frontend.
    datos = json.loads(_DATASET_JSON.read_text(encoding="utf-8"))
    comprobantes = datos["/comprobantes"]
    assert comprobantes, "el export no trajo comprobantes"

    con_archivo = [c for c in comprobantes if c.get("archivo_path")]
    assert con_archivo, "ningún comprobante exportado tiene archivo_path"

    for c in con_archivo:
        ruta = c["archivo_path"]
        assert not ruta.startswith("/uploads/"), f"{ruta} todavía apunta al backend"
        archivo = Path("frontend/public") / ruta.lstrip("/")
        assert archivo.exists(), f"falta {archivo}"
        assert archivo.stat().st_size > 2_000, f"{archivo} parece un PNG de 1px"

    # No 82 copias del mismo contenido: sólo las 3 imágenes de origen.
    nombres = {Path(c["archivo_path"]).name for c in con_archivo}
    assert len(nombres) <= 3


def test_los_datos_de_administracion_no_son_del_smoke_test(con):
    # I2 de la revisión final: /configuracion heredaba "Administración
    # Semilla SRL" / "contacto@semilla-admin.local" del fixture de
    # backend/seed_e2e.py (otro script), visibles en la pantalla que
    # consultan los departamentos para saber a quién pagarle.
    admin_nombre, admin_email = con.execute(
        "select admin_nombre, admin_email from consorcios limit 1"
    ).fetchone()
    assert "Semilla" not in admin_nombre
    assert "semilla-admin" not in admin_email


def test_hay_mas_de_una_caja(con):
    # La pestaña Transferencias no tiene sentido con una sola caja, y un
    # consorcio real maneja al menos banco y efectivo. Con una caja sola, la
    # sección se ve a medio hacer.
    cajas = con.execute("select nombre from cajas").fetchall()
    assert len(cajas) >= 2, f"sólo hay {len(cajas)} caja(s): {cajas}"


def test_hay_transferencias_entre_cajas(con):
    # Sin esto la pestaña Transferencias aparece vacía en la demo.
    total = con.execute("select count(*) from transferencias_caja").fetchone()[0]
    assert total >= 2, f"hay {total} transferencias"


def test_hay_trabajos_recurrentes_programados(con):
    # Es uno de los diferenciales frente a la planilla: las tareas que se
    # repiten solas. Vacío, el argumento no se ve.
    total = con.execute("select count(*) from trabajos_recurrentes").fetchone()[0]
    assert total >= 2, f"hay {total} trabajos recurrentes"


def test_cada_trabajo_dice_de_que_se_trata(con):
    # Los tres trabajos compartían la descripción "Trabajo generado a partir
    # del reclamo del depto.". En la lista de trabajos se leían tres filas
    # idénticas: delata un dato inventado justo en la pantalla que muestra
    # cómo se resuelve un reclamo.
    descripciones = [d for (d,) in con.execute("select descripcion from trabajos")]
    assert len(descripciones) >= 2
    assert len(set(descripciones)) == len(descripciones), descripciones
    for d in descripciones:
        assert "generado a partir del reclamo" not in d, d


def test_cada_peticion_cuenta_un_problema_distinto(con):
    titulos = [t for (t,) in con.execute("select titulo from peticiones")]
    assert len(set(titulos)) == len(titulos), titulos


def test_ningun_presupuesto_es_anterior_al_reclamo_que_lo_originó(con):
    # Los presupuestos SÍ quedan fechados el día de la generación, y está
    # bien: la petición que los origina también, porque `fecha_creacion` de
    # peticiones la pone la base (`server_default=func.now()`) y la API no
    # acepta pasarla. Escalonar los reclamos en el semestre exigiría agregar
    # un campo de fecha al backend sólo para maquillar la demo. Lo que sí
    # tiene que cumplirse es el orden: primero el reclamo, después el
    # presupuesto.
    # `fecha_creacion` la escribe la base con su reloj, que es UTC; en cambio
    # `fecha_presentacion` es una fecha comercial que pone el router con el
    # reloj local. Compararlas crudas es comparar un instante contra una fecha
    # de calendario: al este de Greenwich la petición queda fechada al día
    # siguiente durante las últimas horas del día, y este test se ponía rojo
    # sólo por la hora a la que se hubiera generado el demo. `localtime` lleva
    # el instante al mismo huso en el que se eligió la fecha comercial.
    filas = con.execute("""
        select date(p.fecha_creacion, 'localtime'), pr.fecha_presentacion
        from presupuestos pr
        join trabajos t on t.id = pr.trabajo_id
        join peticiones p on p.id = t.peticion_id
    """).fetchall()
    assert filas
    for fecha_peticion, fecha_presupuesto in filas:
        assert str(fecha_presupuesto) >= str(fecha_peticion), (fecha_peticion, fecha_presupuesto)


def test_el_presupuesto_aprobado_es_de_un_proveedor_del_rubro(con):
    # Un presupuesto de ascensores firmado por la empresa de limpieza es el
    # mismo defecto que ya se arregló en los gastos.
    filas = con.execute("""
        select t.descripcion, p.razon_social
        from presupuestos pr
        join trabajos t on t.id = pr.trabajo_id
        join proveedores p on p.id = pr.proveedor_id
        where pr.estado = 'aprobado'
    """).fetchall()
    assert filas
    for descripcion, razon in filas:
        d = descripcion.lower()
        if "ascensor" in d:
            assert "ascensor" in razon.lower(), (descripcion, razon)
        if "agua" in d or "filtra" in d or "humedad" in d or "pérdida" in d:
            assert "plomer" in razon.lower(), (descripcion, razon)


def test_los_trabajos_muestran_el_ciclo_completo(con):
    # Con un trabajo cancelado y uno solo en curso, la pantalla no cuenta el
    # circuito: hace falta ver también uno terminado, que es el desenlace que
    # justifica el módulo.
    estados = {e for (e,) in con.execute("select estado from trabajos")}
    assert {"en_curso", "finalizado", "cancelado"} <= estados, estados


def test_las_reservas_caen_en_horario_de_uso_real(con):
    # El generador tomaba la hora en que se lo corría y le sumaba unas horas,
    # así que regenerar el demo de madrugada dejaba el SUM alquilado de 3 a 6
    # AM. Ningún consorcio hace eso, y es lo primero que ve un interesado que
    # entra a la demo. La hora tiene que salir de una decisión, no del reloj
    # de quien apretó el botón.
    filas = con.execute("select inicio, fin from reservas").fetchall()
    assert filas
    for inicio, fin in filas:
        hora_inicio = int(str(inicio)[11:13])
        assert 8 <= hora_inicio <= 21, (inicio, "arranca fuera de horario de uso")
        assert str(fin)[:10] == str(inicio)[:10], (inicio, fin, "cruza la medianoche")
