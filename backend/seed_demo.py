"""Generador del dataset demo — 18 UF, 6 meses de operación real.

A diferencia de `backend/seed.py` (fixture de smoke-test que escribe directo a
la DB), este módulo puebla la app **a través de su propia API** con TestClient
in-process, reusando la maquinaria de `backend/seed_e2e.py`. Dos consecuencias:

1. El dataset es consistente por construcción: los saldos, los intereses y el
   FIFO de pagos los calcula el mismo código que corre en producción.
2. El generador funciona como test end-to-end de 6 meses de operación. Si
   termina sin error, el sistema aguanta un semestre.

Uso:
    DEMO_SEED_PASSWORD=... SUPER_ADMIN_EMAIL=... SUPER_ADMIN_PASSWORD=... \\
    DATABASE_URL=sqlite:///./demo.db SEED_ENABLED=false \\
        python -m backend.seed_demo [--reset]

`SEED_ENABLED=false` no es opcional: el lifespan de backend/main.py corre
`seed_if_empty`, que sobre una base vacía crea la "Administración Demo" y el
"Consorcio Demo" del smoke-test. Ese consorcio fantasma quedaría a la vista del
visitante junto al demo real.

Para regenerar SÓLO dataset.json a partir de una `demo.db` que ya existe y
está poblada (por ejemplo, después de un cambio en qué exporta
`export_demo.py`, sin tocar los datos) — sin re-sembrar los 6 meses de
`poblar_demo()`, que tarda ~2 minutos —, usar `--solo-exportar` en vez de
`--reset`/`--exportar`. No necesita SUPER_ADMIN_EMAIL/PASSWORD: no siembra
nada nuevo, sólo loguea contra usuarios que ya existen en la base:

    DEMO_SEED_PASSWORD=... DATABASE_URL=sqlite:///./demo.db \\
    SEED_ENABLED=false python -m backend.seed_demo --solo-exportar

Ver `exportar_desde_db()` para el detalle de qué asume sobre la base.
"""
import os
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from .seed_e2e import (
    RNG,
    Api,
    _caja_default,
    _consorcio_payload,
    _dia_del_periodo,
    _fechas_del_periodo,
    _padron_csv,
)
from .seed_e2e import RUBROS_COMUNES

_DIR_ASSETS = Path(__file__).parent / "assets_demo"

PISOS_DEMO = 3                      # 3 pisos × 6 unidades (A–F) = 18 UF
DOMINIO_DEMO = "demo.local"
EMAIL_ADMIN_DEMO = "admin@demo.local"
NOMBRE_CONSORCIO = "Edificio Libertador"

#: Domicilio del consorcio demo. Se muestra en pantalla junto al nombre, así
#: que tiene que sonar a edificio real y no al "Av. Siempreviva" que trae el
#: smoke-test. Numeración inventada sobre una avenida conocida: verosímil
#: para el ojo, y sin datos de nadie detrás.
DOMICILIO_CONSORCIO_DEMO = "Av. del Libertador 4382, CABA"

# Administración que gestiona el consorcio demo, mostrada en /configuracion
# a los departamentos (necesitan el email de contacto para pagar). Antes
# `_consorcio_payload` (heredado de seed_e2e.py, el smoke-test) dejaba
# "Administración Semilla SRL" / "contacto@semilla-admin.local": datos del
# fixture de otro script, visibles en la pantalla insignia de un demo de
# venta. Una sola razón social/email para todo lo que representa a "quién
# administra este consorcio" en el dataset (el alta en /super-admin y el
# contacto de /configuracion).
NOMBRE_ADMINISTRACION_DEMO = "Administración Demo SRL"
EMAIL_CONTACTO_ADMINISTRACION_DEMO = "contacto@demo.local"

# Deptos pinneados: son los destinos del selector de rol de /auth/demo-login.
CODIGO_PUNTUAL_FIJO = "UF-01A"
CODIGO_MOROSO_FIJO = "UF-03C"

# 12 comunicados con registro de administrador real (no "Comunicado de prueba
# N"): el demo es de venta y lo lee gente que evalúa comprar el sistema. Se
# reparten de a dos por período a lo largo de los 6 meses (ver poblar_demo).
COMUNICADOS_DEMO: list[tuple[str, str]] = [
    ("Corte programado de agua",
     "El martes de 9 a 14 h se corta el suministro por reparación del tanque "
     "de reserva. Les pedimos juntar agua la noche anterior."),
    ("Convocatoria a asamblea ordinaria",
     "Se convoca a asamblea ordinaria para tratar el presupuesto anual, la "
     "rendición de cuentas y la obra de frente. Quórum a las 19 h."),
    ("Nuevo reglamento del SUM",
     "A partir de este mes la reserva del SUM se hace desde el sistema. "
     "Cancelaciones con menos de 48 h de aviso no tienen reintegro."),
    ("Mantenimiento de ascensores",
     "El service mensual pasa a los primeros lunes. El ascensor B queda fuera "
     "de servicio de 8 a 12 h."),
    ("Recordatorio de vencimiento de expensas",
     "El primer vencimiento opera el día 10. Pasada esa fecha se aplica el "
     "recargo previsto por reglamento."),
    ("Obra de frente: inicio de los trabajos",
     "Comienza la reparación del frente del edificio. Se financia en 6 cuotas "
     "por expensas extraordinarias, prorrateadas por la clase B."),
    ("Fumigación general",
     "El jueves se fumigan palieres, sótano y espacios comunes. Les pedimos no "
     "dejar mascotas en zonas comunes ese día."),
    ("Cambio de horario del encargado",
     "Durante enero el encargado cumple horario de verano: de 7 a 15 h."),
    ("Uso de la parrilla y limpieza",
     "Se recuerda dejar la parrilla limpia después de cada uso. El costo de "
     "limpieza extra se carga a la unidad responsable."),
    ("Instalación de medidores individuales",
     "Se evalúa instalar medidores de agua por unidad. Se tratará en la "
     "próxima asamblea con tres presupuestos a la vista."),
    ("Reclamos por filtraciones",
     "Quien tenga filtraciones en el último piso debe cargar la petición por "
     "el sistema para que quede registrada con fecha."),
    ("Cierre de ejercicio",
     "Queda disponible la rendición del ejercicio en la sección Reportes, "
     "junto con el detalle de gastos por período."),
]


# Proveedor por CONCEPTO de gasto: en pantalla, un gasto de seguros
# facturado por una empresa de ascensores destruye la credibilidad del
# dataset entero. Fuente única: antes había dos mapas separados —una lista
# de proveedores con un "rubro que atiende" que nadie leía, y un segundo
# dict rubro → proveedor, 1:1— y ese 1:1 no alcanzaba: RUBROS_COMUNES tiene
# TRES conceptos distintos bajo "abonos_y_servicios" (limpieza, ascensores,
# fumigación), así que los tres terminaban facturados a la empresa de
# limpieza y "Ascensores Vertirod SA" no facturaba nada nunca.
#
# La clave es el CONCEPTO exacto cuando hace falta desambiguar dentro de un
# mismo rubro; el comodín "*<rubro>" cubre los gastos que no salen de
# RUBROS_COMUNES (reparaciones privadas, la obra de frente, el encargado) y
# cualquier concepto de RUBROS_COMUNES que no necesite su propio proveedor.
_PROVEEDOR_POR_CONCEPTO: dict[str, str] = {
    "Abono limpieza": "Limpieza Total SRL",
    "Abono ascensores": "Ascensores Vertirod SA",
    "Fumigación mensual": "Limpieza Total SRL",
    "Mantenimiento bombas": "ElectroSur SRL",
    "AySA agua común": "Servicios Metropolitanos SA",
    "Edesur espacios comunes": "Servicios Metropolitanos SA",
    "Honorarios administración": "Estudio Rossi & Asociados",
    "Comisiones bancarias": "Banco Ciudad",
    "Seguro integral consorcio": "Seguros La Continental",
    "*trabajos_reparaciones_unidades": "Plomería Paz",
    "*mantenimiento_partes_comunes": "Plomería Paz",
    "*sueldos_y_cargas_sociales": "Estudio Rossi & Asociados",
}

#: Catálogo de proveedores del demo: se crean todos estos, en este orden.
#: DERIVADO de `_PROVEEDOR_POR_CONCEPTO` —no una lista aparte— para que el
#: catálogo nunca pueda desincronizarse de a quién se le factura de verdad.
PROVEEDORES_DEMO: list[str] = list(dict.fromkeys(_PROVEEDOR_POR_CONCEPTO.values()))


def proveedor_para_gasto(rubro: str, concepto: str, proveedores: dict[str, int], rng) -> int:
    """Id del proveedor que corresponde a este gasto.

    Busca primero por CONCEPTO exacto —necesario para no repetir el bug que
    esta función vino a arreglar: dentro de un mismo rubro puede haber varios
    proveedores reales (limpieza, ascensores, fumigación son los tres
    "abonos_y_servicios")—. Si el concepto no tiene entrada propia (gastos
    que no salen de RUBROS_COMUNES), cae al comodín "*<rubro>". Sin comodín
    tampoco, usa el primero del catálogo en vez de elegir al azar: un
    default estable es preferible a uno que cambia entre corridas y hace
    irreproducible el dataset.

    `proveedores` mapea razón social → id (los ids los devuelve la API al
    crearlos).
    """
    razon = _PROVEEDOR_POR_CONCEPTO.get(concepto) or _PROVEEDOR_POR_CONCEPTO.get(f"*{rubro}")
    if razon is None or razon not in proveedores:
        return next(iter(proveedores.values()))
    return proveedores[razon]


# --- Estimación de gasto mensual, para dimensionar el fondo de reserva -----
# saldo_inicial_caja necesita un "gasto mensual típico" del dataset. Se deriva
# de los datos que el propio generador ya usa —no de un literal a dedo— para
# que un cambio en esos datos (ej. agregar una fila a RUBROS_COMUNES) se
# refleje acá solo, sin dejar un número suelto que nadie vuelve a comprobar.

#: 1 a 3 reparaciones privadas por período (poblar_demo: `RNG.randint(1, 3)`),
#: de $15.000 a $90.000 c/u (`RNG.uniform(15_000, 90_000)`). Punto medio de
#: cada rango: 2 reparaciones × $52.500 = $105.000/mes.
_REPARACIONES_PRIVADAS_ESTIMADO = (1 + 3) / 2 * (15_000 + 90_000) / 2

#: Costo mensual del encargado vía liquidación (crear_catalogo_personal), no
#: vía RUBROS_COMUNES: poblar_demo saltea sus dos filas
#: "sueldos_y_cargas_sociales" con `continue` porque ese rubro lo genera la
#: liquidación, no un /gastos suelto.
#:   bruto = 950.000 (básico 100%) + 190.000 (antigüedad 20%) + 95.000
#:           (presentismo) + 60.000 (plus limpieza) + 52.000 (horas extra,
#:           8h × $6.500) = 1.347.000
#:   costo total = bruto × (1 + 17% contribuciones patronales + 5% ART)
#:               = 1.347.000 × 1.22 ≈ 1.643.340
#: Los descuentos (jubilación, obra social, sindicato) no se suman aparte: ya
#: están dentro del bruto, sólo cambian a quién se le paga — ver
#: `_generar_gastos` en backend/routers/liquidaciones.py.
#: Si cambia el `sueldo_basico`, algún haber o algún porcentaje de
#: contribución/ART en `crear_catalogo_personal` (más abajo en este archivo),
#: hay que actualizar esta constante a mano — no se recalcula sola.
_SUELDO_ENCARGADO_ESTIMADO = (950_000 + 190_000 + 95_000 + 60_000 + 52_000) * 1.22

#: Costo total de la obra de frente del dataset demo, y en cuántas cuotas se
#: financia. Se declaran por separado porque `crear_plan_cuotas`
#: (backend/routers/gastos.py) espera el importe DE CADA CUOTA, no el total:
#: no divide `monto` entre `cuota_total`, sino que replica el mismo `monto`
#: recibido en cada una de las cuotas. Mandarle el total multiplica el gasto
#: real por la cantidad de cuotas — ver `importe_por_cuota`.
COSTO_TOTAL_OBRA_DEMO = 7_200_000.0
CUOTAS_OBRA_DEMO = 6


def importe_por_cuota(costo_total: float, cuotas: int) -> float:
    """Importe de cada cuota para `POST /gastos/plan-cuotas`.

    Ese endpoint NO divide: crea `cuota_total` gastos con el `monto` recibido
    entero cada uno (`backend/routers/gastos.py:555-581`). Mandarle el costo
    total de una obra multiplica el gasto por la cantidad de cuotas — el
    dataset llegó a tener una reparación de frente de $43.200.000 por esta
    causa, el 72% de los gastos del semestre.
    """
    return round(costo_total / cuotas, 2)


#: Cuota mensual de la obra extraordinaria (plan-cuotas en poblar_demo), para
#: sumar al estimado de `estimar_gasto_mensual_demo`. Es el importe de UNA
#: cuota, no el costo total de la obra: lo que golpea la caja cada mes es una
#: cuota (ver `importe_por_cuota`), no la obra entera.
#:   cuota = importe_por_cuota(COSTO_TOTAL_OBRA_DEMO, CUOTAS_OBRA_DEMO)
#:         = 7.200.000 / 6 = 1.200.000
#: Si cambian `COSTO_TOTAL_OBRA_DEMO` o `CUOTAS_OBRA_DEMO`, hay que actualizar
#: esta constante a mano — no se recalcula sola.
#: Acoplamiento implícito con `meses_demo`: esta constante asume que la
#: cantidad de cuotas de la obra (`CUOTAS_OBRA_DEMO=6`) coincide con la
#: cantidad de meses que siembra el dataset (`meses_demo(..., cantidad=6)` por
#: default). Mientras coincidan, la cuota golpea los 6 períodos del dataset
#: entero y la cuenta cierra. Si el día de mañana uno de esos dos "6" cambia
#: sin el otro (por ejemplo, más meses de dataset pero la misma obra de 6
#: cuotas), la obra deja de pagarse todos los períodos y esta constante pasa a
#: sobreestimar el gasto mensual real — sin que nada lo avise.
_CUOTA_OBRA_ESTIMADA = 1_200_000.0


def estimar_gasto_mensual_demo(rubros_comunes: list[tuple]) -> float:
    """Gasto mensual típico del dataset, para dimensionar `saldo_inicial_caja`.

    Suma el punto medio `(lo + hi) / 2` de cada fila de `rubros_comunes`
    —salvo las de rubro `sueldos_y_cargas_sociales`, que poblar_demo saltea y
    reemplaza por la liquidación del encargado— más las reparaciones privadas,
    el sueldo del encargado y la cuota de la obra extraordinaria.

    Recibe `rubros_comunes` por parámetro (en vez de importar `RUBROS_COMUNES`
    directo) para poder testearse con datos sintéticos, sin acoplarse al
    catálogo real ni a un import con efectos secundarios.
    """
    comunes = sum(
        (lo + hi) / 2
        for rubro, _concepto, lo, hi in rubros_comunes
        if rubro != "sueldos_y_cargas_sociales"
    )
    return (
        comunes
        + _REPARACIONES_PRIVADAS_ESTIMADO
        + _SUELDO_ENCARGADO_ESTIMADO
        + _CUOTA_OBRA_ESTIMADA
    )


#: Porción de las expensas que el dataset deja impaga: el 15% moroso nunca
#: entra a `pagan` (perfiles_deterministas + el loop de pagos en poblar_demo
#: arma `pagan` sólo desde puntuales + irregulares) y de los irregulares
#: (15%) paga en promedio la mitad de los períodos (`RNG.random() < 0.5`) →
#: 15% + 15% × 0.5 = 22.5%.
_MOROSIDAD_ESTIMADA = 0.225


def saldo_inicial_caja(gasto_mensual_estimado: float, meses: int) -> float:
    """Fondo de arranque de la caja para que la tesorería no quede negativa.

    El dataset gasta todos los meses y cobra sólo lo que los perfiles de pago
    dejan cobrar, así que sin un fondo inicial la caja termina el semestre en
    rojo profundo — que es imposible en un consorcio real y desmiente al resto
    de los números en la primera pantalla que mira un administrador.

    Se cubre el déficit acumulado más un mes ENTERO de colchón (margen para
    que un mes particularmente caro, o más moroso que el promedio, no tumbe la
    caja igual), redondeado a la centena de miles para que se lea como un
    fondo de reserva y no como el resultado de una cuenta.
    """
    deficit = gasto_mensual_estimado * _MOROSIDAD_ESTIMADA * meses
    colchon = gasto_mensual_estimado * 1.0
    return float(round((deficit + colchon) / 100_000) * 100_000)


def meses_demo(hoy: date, cantidad: int = 6) -> list[str]:
    """Los `cantidad` meses calendario completos anteriores al mes en curso.

    Corriendo el 2026-07-31 → ['2026-01' … '2026-06'].
    El mes en curso queda abierto a propósito: el visitante tiene un período
    vivo donde cargar gastos y probar el cierre él mismo, que es la acción más
    demostrativa del sistema.
    """
    meses: list[str] = []
    anio, mes = hoy.year, hoy.month
    for _ in range(cantidad):
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
        meses.append(f"{anio:04d}-{mes:02d}")
    return list(reversed(meses))


#: Cuántos comprobantes quedan esperando aprobación al abrir la demo.
COMPROBANTES_PENDIENTES = 3


def deja_pendiente(indice_pago: int, total_pagos: int, es_ultimo_periodo: bool) -> bool:
    """¿Este comprobante queda sin aprobar?

    Sólo en el último período cerrado, y sólo los últimos
    `COMPROBANTES_PENDIENTES`: son la bandeja de entrada que el visitante
    encuentra al abrir la demo. En períodos anteriores todo queda aprobado,
    porque un comprobante colgado en un mes viejo descuadraría la cobranza
    histórica que el resto del dataset da por cobrada.

    Se reserva al menos la mitad de los pagos como aprobados para que el
    período no quede sin ninguna cobranza si hubiera pocos pagadores.
    """
    if not es_ultimo_periodo:
        return False
    cupo = min(COMPROBANTES_PENDIENTES, total_pagos // 2)
    return indice_pago >= total_pagos - cupo


def fecha_pago_puntual(primer_vencimiento: date, hoy: date, rng) -> date:
    """Fecha en que un pagador puntual abona, siempre ANTES del vencimiento.

    La versión anterior hacía `min(f1 - randint(0,5), hoy)`, con dos fallas:
    `randint(0, 5)` incluye el 0 —o sea el pago cae el mismo día del
    vencimiento, cuando el recargo ya corrió— y el `min` contra hoy podía
    empujarlo *después* de f1 si el vencimiento era futuro. Por eso UF-01A,
    pinneado como puntual, terminaba con recargo por mora e intereses.

    Se paga entre 1 y 6 días antes del vencimiento, y si esa fecha todavía no
    ocurrió se usa el día anterior a hoy — nunca una fecha futura.
    """
    pago = primer_vencimiento - timedelta(days=rng.randint(1, 6))
    if pago > hoy:
        pago = min(hoy, primer_vencimiento - timedelta(days=1))
    return pago


def imagen_comprobante(indice: int) -> bytes:
    """Bytes de una captura de transferencia para adjuntar a un comprobante.

    Rota entre las disponibles para que la lista no muestre tres veces la
    misma imagen. La imagen de 1px de `seed_e2e._PNG_1PX` servía mientras
    nadie miraba los comprobantes; en la demo son parte del circuito que se
    muestra.
    """
    archivos = sorted(_DIR_ASSETS.glob("comprobante_*.png"))
    return archivos[indice % len(archivos)].read_bytes()


def dia_de_cierre(periodo: str) -> date:
    """Día en que se cierra `periodo` ("YYYY-MM"): el 1 del mes siguiente.

    Una administración liquida el mes vencido a principios del siguiente, así
    que la expensa de julio se emite en agosto. Cae siempre antes del primer
    vencimiento histórico (`_fechas_del_periodo` lo fija el día 10 de ese mismo
    mes siguiente), lo que importa para `reloj_en`: al cerrar y leer el propio
    período bajo esta fecha, su expensa recién creada todavía no venció y no
    puede devengar recargo dentro de su propio bloque.
    """
    anio, mes = (int(x) for x in periodo.split("-"))
    return date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)


@contextmanager
def reloj_en(fecha: date):
    """Hace que el cierre de un período (y todo lo que dispara) vea `fecha`
    como el día de hoy.

    No alcanza con parchear `routers/periodos.py`. El rastreo completo del
    camino que corre `POST /periodos/{periodo}/cerrar → GET /expensas → POST
    /comprobantes` (el bloque que `poblar_demo` ejecuta por período) encontró
    TRES módulos que llaman a `date.today()` sin que nadie se lo pase:

    - `backend/routers/periodos.py` (línea ~145): fecha los movimientos
      `expensa_emitida` e `interes_punitorio` que crea el cierre.
    - `backend/cierre.py` (línea ~341, `_completar_preview`): calcula
      `fecha_corte` con ella, y esa fecha decide DOS cosas antes de que
      `periodos.py` escriba nada — qué expensas atrasadas devengan recargo
      (dispara `recargos.devengar_recargos_y_marcar` con `hoy` explícito) y
      cuánto interés punitorio corresponde (`calcular_intereses_al_cierre`).
    - `backend/recargos.py` (línea ~36, `_devengar`): es el default cuando el
      llamador NO pasa `hoy`, y `routers/expensas.py:94` llama así en cada
      `GET /expensas` — el propio `poblar_demo` hace ese GET justo después de
      cerrar, antes de cargar los pagos.

    Sin parchear los tres, el generador cierra seis períodos históricos en
    minutos: `cierre.py` ve la fecha real de la corrida al calcular
    `fecha_corte`, encuentra expensas ya vencidas (según el calendario real)
    sin comprobante todavía cargado, y les devenga recargo e interés antes de
    que exista ningún pago — inclusive a las unidades que iban a pagar en
    término. Con los tres módulos viendo `fecha` (el día de cierre simulado
    de este período, siempre anterior a su propio primer vencimiento), el
    devengamiento sólo alcanza a las expensas de períodos *anteriores* que ya
    deberían estar vencidas a esa altura de la historia simulada — igual que
    haría una administración real.

    Se parchea el símbolo `date` que cada módulo importó —no `datetime.date`
    global, y no el `date` de `seed_demo.py`— para no alterar el resto del
    sistema durante el bloque. En particular, `fecha_pago_puntual` sigue
    viendo la fecha real del proceso: el `date.today()` que recibe en
    `poblar_demo` es el de este mismo módulo, no el de `periodos`/`cierre`/
    `recargos`, así que el reloj simulado no le cambia el significado.

    `_FechaFija` sólo responde `.today()`. No expone su constructor: hoy
    ningún código bajo el patch construye una fecha por afuera de
    `.today()` (`cierre._calcular_fechas_default` es la única excepción del
    módulo, y sólo corre si `fecha_primer_venc`/`fecha_segundo_venc` llegan
    en `None` — algo que `poblar_demo` nunca hace, siempre manda las dos
    explícitas), pero esa garantía es un invariante del LLAMADOR, no algo
    que este context manager pueda hacer cumplir por sí solo. Si algún día
    deja de cumplirse —un `poblar_demo` que omite una fecha, o un llamador
    nuevo de `reloj_en` que sí lo hace—, `date(y, m, d)` bajo el patch
    devolvería una instancia de `_FechaFija` (la aritmética de `date`
    preserva la subclase vía `type(self).fromordinal(...)`), y ese objeto
    —con un `.today()` fijo para siempre— podría terminar grabado en
    `fecha_primer_vencimiento` / `fecha_segundo_vencimiento`. Preferimos que
    ese escenario reviente ruidosamente acá a que se cuele en la base en
    silencio.
    """
    class _FechaFija(date):
        @classmethod
        def today(cls):
            return fecha

        def __new__(cls, *args, **kwargs):
            raise TypeError(
                "_FechaFija no admite construcción directa (sólo expone "
                ".today()). Si ves este error, algo dentro del bloque de "
                "reloj_en() construyó una fecha nueva por afuera de "
                "date.today() -- ese código necesita su propia fecha real, "
                "no la simulada."
            )

    from . import cierre, recargos
    from .routers import periodos

    with patch.object(periodos, "date", _FechaFija), \
         patch.object(cierre, "date", _FechaFija), \
         patch.object(recargos, "date", _FechaFija):
        yield


def perfiles_deterministas(
    deptos: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Reparte los deptos en (puntuales, irregulares, morosos) sin azar.

    `seed_e2e.py` mezcla con RNG.shuffle antes de asignar perfiles. Para el demo
    eso no sirve: el selector de rol apunta a emails fijos, así que qué depto es
    moroso tiene que estar pinneado y ser estable entre corridas.

    Mantiene la distribución 70/15/15 del original, que sobre 18 UF da 12/3/3.
    """
    por_codigo = {d["codigo"]: d for d in deptos}
    n = len(deptos)
    cupo_puntuales = int(n * 0.70)
    cupo_irregulares = int(n * 0.85) - cupo_puntuales

    fijo_puntual = por_codigo.get(CODIGO_PUNTUAL_FIJO)
    fijo_moroso = por_codigo.get(CODIGO_MOROSO_FIJO)
    pinneados = {d["codigo"] for d in (fijo_puntual, fijo_moroso) if d is not None}

    # Orden estable por código, con los pinneados fuera del reparto para no
    # asignarlos dos veces. Se reinsertan a mano en su grupo al final.
    resto = [
        d for d in sorted(deptos, key=lambda x: x["codigo"])
        if d["codigo"] not in pinneados
    ]

    # Un solo cursor sobre `resto` garantiza el invariante que piden los tests:
    # cada depto cae en exactamente un grupo, sin huecos ni repetidos.
    cursor = 0
    puntuales = [fijo_puntual] if fijo_puntual is not None else []
    faltan = max(cupo_puntuales - len(puntuales), 0)
    puntuales += resto[cursor:cursor + faltan]
    cursor += faltan

    irregulares = resto[cursor:cursor + cupo_irregulares]
    cursor += len(irregulares)

    # Los morosos se llevan el remanente: así nunca se pierde un depto por
    # redondeo de los cupos.
    morosos = ([fijo_moroso] if fijo_moroso is not None else []) + resto[cursor:]

    return puntuales, irregulares, morosos


#: Rango de la reposición mensual de la caja chica. Un consorcio real retira
#: una suma modesta para gastos menores (ferretería, fletes, propinas de
#: service) y la repone cuando se agota — nunca el mismo importe exacto ni el
#: mismo día, que es lo que delata a un dato inventado en cámara.
_REPOSICION_CAJA_CHICA = (120_000.0, 220_000.0)


def crear_caja_chica(api, admin_token, cid, caja_banco_id: int, meses: list[str]) -> int:
    """Segunda caja + una transferencia mensual desde el banco.

    Con una sola caja la pestaña Transferencias de Tesorería no tiene nada
    que mostrar y la sección se lee como una pantalla a medio hacer. Un
    consorcio real maneja al menos la cuenta bancaria y algo de efectivo, y
    el movimiento entre las dos es justamente lo que la pestaña explica.

    Devuelve el id de la caja creada.
    """
    r = api.req("POST", "/cajas", token=admin_token, cid=cid, json={
        "nombre": "Caja chica",
        "tipo": "efectivo",
        "descripcion": "Efectivo para gastos menores del edificio",
        "saldo_inicial": 0.0,
    }, expect=201)
    caja_chica_id = r.json()["id"]

    # Una reposición por mes, en la primera semana: ya entró la cobranza del
    # período anterior y hay con qué reponer. El importe y el día varían
    # porque el administrador repone lo que falta, no una cuota fija.
    minimo, maximo = _REPOSICION_CAJA_CHICA
    for periodo in meses:
        api.req("POST", "/transferencias-caja", token=admin_token, cid=cid, json={
            "caja_origen_id": caja_banco_id,
            "caja_destino_id": caja_chica_id,
            "monto": float(round(RNG.uniform(minimo, maximo), -3)),
            "fecha": _dia_del_periodo(periodo, RNG.randint(2, 8)).isoformat(),
            "descripcion": "Reposición de caja chica",
        }, expect=201)

    # Un cierre de ejercicio devuelve al banco el sobrante de efectivo: es lo
    # que hace ver que las cajas se mueven en los dos sentidos y no son un
    # tobogán de una sola dirección.
    api.req("POST", "/transferencias-caja", token=admin_token, cid=cid, json={
        "caja_origen_id": caja_chica_id,
        "caja_destino_id": caja_banco_id,
        "monto": 85_000.0,
        "fecha": _dia_del_periodo(meses[len(meses) // 2], 26).isoformat(),
        "descripcion": "Devolución de sobrante de caja chica al banco",
    }, expect=201)

    return caja_chica_id


#: Tareas que todo edificio repite sin que nadie las pida: por eso el sistema
#: las programa en vez de esperar a que alguien se acuerde.
#:
#: Cada una nombra la razón social que la atiende, no un rubro: estas tareas
#: no salen de RUBROS_COMUNES, así que `proveedor_para_gasto` no tendría
#: entrada para ellas y las mandaría todas al primer proveedor del catálogo —
#: los cuatro trabajos quedarían facturados por la empresa de limpieza, que
#: es exactamente el defecto que esa función vino a arreglar. Las razones
#: sociales tienen que existir en `PROVEEDORES_DEMO`; lo verifica el assert
#: de `crear_trabajos_recurrentes`.
#: Los seis reclamos del semestre, cada uno con lo que escribió el vecino, lo
#: que anotó la administración al convertirlo en trabajo, y quién lo atiende.
#:
#: Van juntos a propósito. Antes el título salía por sorteo de una lista y la
#: descripción del trabajo era una sola frase repetida ("Trabajo generado a
#: partir del reclamo del depto."): la pantalla de Trabajos mostraba tres
#: filas idénticas y la de Peticiones repetía títulos, justo donde el sistema
#: tiene que mostrar cómo se resuelve un reclamo. El proveedor viaja acá
#: mismo para que un presupuesto de ascensores no lo firme la empresa de
#: limpieza — el mismo criterio que `_PROVEEDOR_POR_CONCEPTO` aplica a los
#: gastos. Cada razón social tiene que existir en `PROVEEDORES_DEMO`.
PROBLEMAS_DEMO = [
    ("Pérdida de agua en el baño",
     "Gotea la conexión del inodoro desde el fin de semana y se está "
     "humedeciendo el piso. Solicito revisión a la brevedad.",
     "Reparación de pérdida en conexión de inodoro — UF con filtración",
     "Plomería Paz"),
    ("Humedad en la pared del dormitorio",
     "Apareció una mancha de humedad que va creciendo en la pared que da al "
     "pulmón de manzana.",
     "Revisión de humedad en pared medianera y sellado exterior",
     "Plomería Paz"),
    ("El portero eléctrico no tiene audio",
     "Se escucha el timbre pero no se oye a quien llama. Pasa desde el corte "
     "de luz del martes.",
     "Reparación del portero eléctrico: se escucha el timbre pero no el audio",
     "ElectroSur SRL"),
    ("Luz de pasillo quemada",
     "La luz del pasillo del tercer piso está quemada hace una semana y de "
     "noche no se ve nada.",
     "Cambio de luminaria del pasillo del 3er piso",
     "ElectroSur SRL"),
    ("Filtración en el balcón",
     "Cuando llueve entra agua por la junta del balcón y moja el interior.",
     "Sellado de junta de balcón por filtración de agua de lluvia",
     "Plomería Paz"),
    ("El ascensor hace ruido al frenar",
     "Hace un chirrido fuerte cada vez que frena, sobre todo bajando.",
     "Ascensor: ruido al frenar — revisión de guías y freno",
     "Ascensores Vertirod SA"),
]


TRABAJOS_RECURRENTES_DEMO = [
    ("Limpieza de tanques de agua", "Certificado obligatorio semestral.",
     "semestral", "Servicios Metropolitanos SA", 180_000.0),
    ("Service de matafuegos", "Recarga y control de todos los matafuegos del edificio.",
     "anual", "Seguros La Continental", 240_000.0),
    ("Mantenimiento de ascensores", "Visita mensual de control obligatoria.",
     "mensual", "Ascensores Vertirod SA", 320_000.0),
    ("Desinfección y desratización", "Certificado que exige el municipio.",
     "trimestral", "Limpieza Total SRL", 95_000.0),
]


def crear_trabajos_recurrentes(api, admin_token, cid, proveedores: dict) -> list[int]:
    """Las tareas programadas del edificio.

    Es uno de los diferenciales frente a llevar el consorcio en una planilla:
    la planilla no avisa que vencen los matafuegos. Vacía, la pantalla no
    cuenta ese argumento.
    """
    ids = []
    for nombre, descripcion, periodicidad, razon_social, monto in TRABAJOS_RECURRENTES_DEMO:
        assert razon_social in proveedores, (
            f"'{razon_social}' no está en PROVEEDORES_DEMO: el trabajo "
            f"recurrente '{nombre}' quedaría sin proveedor"
        )
        r = api.req("POST", "/trabajos-recurrentes", token=admin_token, cid=cid, json={
            "nombre": nombre,
            "descripcion": descripcion,
            "periodicidad": periodicidad,
            "proveedor_sugerido_id": proveedores[razon_social],
            "monto_estimado": monto,
        }, expect=201)
        ids.append(r.json()["id"])
    return ids


def crear_catalogo_personal(api, admin_token, cid, proveedor_id: int) -> dict:
    """Empleado + haberes + conceptos de liquidación del encargado.

    Sin esto el módulo Personal queda vacío en el demo, que es justo uno de
    los diferenciales frente a llevar el consorcio en una planilla.

    Los payloads siguen EmpleadoCrear (backend/schemas.py:666), HaberCrear
    (:701) y ConceptoLiquidacionCrear (:727). Ojo con los enums: `categoria`
    es CategoriaEmpleado, `tipo` de haber es TipoHaber y `tipo` de concepto es
    TipoConcepto (backend/models.py:125-140).
    """
    r = api.req("POST", "/empleados", token=admin_token, cid=cid, json={
        "nombre_completo": "Ramón Gutiérrez",
        "cuil": "20-14555666-3",
        "categoria": "encargado_permanente_con_vivienda",
        "fecha_ingreso": "2019-03-01",
        "sueldo_basico": 950_000.0,
        "proveedor_id": proveedor_id,
    }, expect=201)
    empleado_id = r.json()["id"]

    # Proveedores institucionales para descuentos y contribuciones. Se crean
    # acá — no se reusan los proveedores comerciales del consorcio (limpieza,
    # ascensores, etc.) porque no representan a quién se le paga de verdad
    # una retención o contribución — siguiendo el mismo patrón que
    # backend/seed.py (Fase 3: AFIP/ARCA/FATERYH/SUTERH como Proveedor).
    # "AFIP", "FATERYH" y "SUTERH" son nombres genérico-institucionales del
    # rubro (como "AFIP" en cualquier software de administración argentino);
    # para el proveedor de ART usamos una etiqueta obviamente ficticia
    # ("ART Demo SA") en vez del nombre de una aseguradora real — este
    # dataset se publica en un demo público y una razón social real con un
    # CUIT inventado se leería como un dato genuino.
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "AFIP", "cuit": "30-00000101-1",
    }, expect=201)
    proveedor_afip = r.json()["id"]
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "FATERYH", "cuit": "30-00000102-2",
    }, expect=201)
    proveedor_fateryh = r.json()["id"]
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "SUTERH", "cuit": "30-00000103-3",
    }, expect=201)
    proveedor_suterh = r.json()["id"]
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "ART Demo SA", "cuit": "30-00000104-4",
    }, expect=201)
    proveedor_art = r.json()["id"]

    # El sueldo básico NO entra solo por estar en el empleado: _calcular_y_guardar
    # (backend/routers/liquidaciones.py:289) arma el bruto sumando únicamente
    # los haberes de la liquidación. Por eso el catálogo necesita un haber
    # "Básico" porcentaje_sobre_basico al 100%, igual que backend/seed.py:338 —
    # sin él, el bruto se arma sólo con los adicionales y el sueldo real del
    # encargado casi desaparece del rubro.
    # "Horas extra" queda última a propósito: poblar_demo necesita saber cuál
    # de los ids requiere `cantidad` al armar la liquidación
    # (LiquidacionHaberItem, schemas.py:756).
    haberes = []
    for orden, (nombre, tipo, valor) in enumerate([
        ("Básico", "porcentaje_sobre_basico", 100.0),
        ("Antigüedad", "porcentaje_sobre_basico", 20.0),
        ("Presentismo", "monto_fijo", 95_000.0),
        ("Plus por limpieza", "monto_fijo", 60_000.0),
        ("Horas extra", "cantidad_x_valor", 6_500.0),
    ]):
        r = api.req("POST", "/haberes", token=admin_token, cid=cid, json={
            "nombre": nombre, "tipo": tipo,
            "valor_default": valor, "orden": orden,
        }, expect=201)
        haberes.append(r.json()["id"])

    # Todos los conceptos llevan `proveedor_id`, descuentos incluidos.
    # _generar_gastos (backend/routers/liquidaciones.py:252-276) sólo
    # materializa un Gasto por cada proveedor con detalle asociado — sin
    # proveedor_id el monto se calcula y queda en liquidacion.detalle, pero
    # nunca entra al prorrateo. Los descuentos NO son un pago que el empleado
    # hace por su cuenta: el empleador los retiene del bruto y los deposita
    # él mismo en AFIP, la obra social y el sindicato — por eso también
    # necesitan generar su propio Gasto, igual que backend/seed.py:349-355
    # (que le asigna proveedor_id a los 4 conceptos `descuento`, no sólo a
    # las contribuciones). Esto no duplica el descuento del neto:
    # `descuentos_total` en _generar_gastos se calcula por `concepto_tipo`,
    # sin importar si el concepto tiene proveedor — el Gasto por-proveedor es
    # un agrupado aparte sobre `liquidacion.detalle`.
    conceptos = []
    for orden, (nombre, tipo, porcentaje, prov) in enumerate([
        ("Jubilación", "descuento", 11.0, proveedor_afip),
        ("Ley 19.032", "descuento", 3.0, proveedor_afip),
        ("Obra social FATERYH", "descuento", 3.0, proveedor_fateryh),
        ("Sindicato SUTERH", "descuento", 2.0, proveedor_suterh),
        ("Contribuciones patronales", "contribucion", 17.0, proveedor_afip),
        ("ART", "contribucion", 5.0, proveedor_art),
    ]):
        payload = {"nombre": nombre, "tipo": tipo, "porcentaje": porcentaje, "orden": orden}
        if prov is not None:
            payload["proveedor_id"] = prov
        r = api.req("POST", "/conceptos-liquidacion", token=admin_token, cid=cid, json=payload,
                    expect=201)
        conceptos.append(r.json()["id"])

    return {"empleado_id": empleado_id, "haberes": haberes, "conceptos": conceptos}


def poblar_demo(api, admin_token, seed_password: str) -> dict:
    """Crea el consorcio demo y lo puebla con 6 meses de operación."""
    t0 = time.monotonic()
    meses = meses_demo(date.today())

    consorcio_payload = _consorcio_payload(NOMBRE_CONSORCIO, 33333)
    # `_consorcio_payload` es de seed_e2e.py (el smoke-test) y trae sus
    # propios datos de administración fijos ("Administración Semilla SRL" /
    # contacto@semilla-admin.local). El demo tiene los suyos — ver el
    # comentario junto a NOMBRE_ADMINISTRACION_DEMO más arriba.
    consorcio_payload["admin_nombre"] = NOMBRE_ADMINISTRACION_DEMO
    consorcio_payload["admin_email"] = EMAIL_CONTACTO_ADMINISTRACION_DEMO
    # El domicilio también viene del smoke-test, que usa "Av. Siempreviva" —
    # el chiste de Los Simpson. Sirve para un test; en una demo de venta, que
    # se muestra en pantalla junto al nombre del consorcio, delata que los
    # datos son de juguete. Va uno verosímil y acorde al nombre del edificio.
    consorcio_payload["consorcio_domicilio"] = DOMICILIO_CONSORCIO_DEMO
    r = api.req("POST", "/consorcios", token=admin_token,
                json=consorcio_payload, expect=201)
    cid = r.json()["id"]

    # Fondo de reserva inicial: sin esto la caja "Banco principal" termina el
    # semestre en rojo, porque el dataset gasta todos los meses y sólo cobra
    # lo que los perfiles de pago dejan cobrar (ver saldo_inicial_caja). Se
    # carga como ajuste manual, antes del primer período, con fecha del día 1
    # del primer mes sembrado.
    caja_id = _caja_default(api, admin_token, cid)
    api.req("POST", f"/cajas/{caja_id}/movimientos", token=admin_token, cid=cid, json={
        "fecha": _dia_del_periodo(meses[0], 1).isoformat(),
        "monto": saldo_inicial_caja(estimar_gasto_mensual_demo(RUBROS_COMUNES), len(meses)),
        "descripcion": "Fondo de reserva inicial del consorcio",
    }, expect=201)

    r = api.req("POST", "/clases-prorrateo", token=admin_token, cid=cid,
                json={"codigo": "A", "nombre": "Expensas ordinarias"}, expect=201)
    clase_a = r.json()["id"]
    r = api.req("POST", "/clases-prorrateo", token=admin_token, cid=cid,
                json={"codigo": "B", "nombre": "Expensas extraordinarias"}, expect=201)
    clase_b = r.json()["id"]

    proveedores = {}
    for razon in PROVEEDORES_DEMO:
        r = api.req("POST", "/proveedores", token=admin_token, cid=cid,
                    json={"razon_social": razon,
                          "cuit": f"30-{RNG.randint(10_000_000, 99_999_999)}-{RNG.randint(0, 9)}"},
                    expect=201)
        proveedores[razon] = r.json()["id"]

    amenities = {}
    precios_amenity: dict[int, float] = {}
    for nombre_a, precio in [("SUM", 25_000.0), ("Laundry", 3_000.0)]:
        r = api.req("POST", "/amenities", token=admin_token, cid=cid,
                    json={"nombre": nombre_a, "precio_reserva": precio}, expect=201)
        amenity_id = r.json()["id"]
        amenities[nombre_a] = amenity_id
        precios_amenity[amenity_id] = precio

    # Padrón: 3 pisos × 6 unidades = 18 UF, con sus usuarios.
    csv_bytes = _padron_csv(PISOS_DEMO, DOMINIO_DEMO)
    r = api.req("POST", "/padron/importar", token=admin_token, cid=cid,
                files={"file": ("padron.csv", csv_bytes, "text/csv")}, expect=200)
    resultados = r.json()["resultados"]
    passwords_iniciales = {x["email"]: x["password_generada"] for x in resultados}

    r = api.req("GET", "/departamentos", token=admin_token, cid=cid, expect=200)
    deptos = r.json()
    n = len(deptos)

    base = round(100.0 / n, 4)
    coefs = [{"departamento_id": d["id"], "clase_prorrateo_id": clase_a,
              "porcentaje": base} for d in deptos]
    coefs[-1]["porcentaje"] = round(100.0 - base * (n - 1), 4)

    # La clase B (obra en cuotas, más abajo) necesita coeficientes propios o
    # el cierre puede rechazar el prorrateo: se mandan las dos clases juntas
    # en una sola llamada a PUT /coeficientes.
    coefs_b = [{"departamento_id": d["id"], "clase_prorrateo_id": clase_b,
                "porcentaje": base} for d in deptos]
    coefs_b[-1]["porcentaje"] = round(100.0 - base * (n - 1), 4)
    api.req("PUT", "/coeficientes", token=admin_token, cid=cid,
            json={"coeficientes": coefs + coefs_b}, expect=200)

    # El encargado necesita un proveedor (le paga la administración): el que
    # atiende sueldos_y_cargas_sociales.
    personal = crear_catalogo_personal(
        api, admin_token, cid,
        proveedor_para_gasto("sueldos_y_cargas_sociales", "", proveedores, RNG),
    )

    # Tesorería con dos cajas y las tareas programadas del edificio: sin
    # esto, dos pantallas de la demo se ven vacías aunque funcionen.
    crear_caja_chica(api, admin_token, cid, caja_id, meses)
    crear_trabajos_recurrentes(api, admin_token, cid, proveedores)

    puntuales, irregulares, morosos = perfiles_deterministas(deptos)

    # UF-03C (el moroso "fijo") es, además de un moroso más, el destino del
    # botón "Propietario moroso" de /auth/demo-login — a diferencia de un
    # moroso real (que es realista que nunca haya iniciado sesión), a este
    # login público le pedimos entrar directo, así que necesita haber pasado
    # por el alta con password ya cambiada como cualquier usuario puntual o
    # irregular. Se agrega SÓLO a este loop de login: el loop de pagos más
    # abajo arma `pagan` desde `puntuales + irregulares`, no desde
    # `tokens_depto`, así que esto no le paga las expensas ni le saca la
    # deuda/interés que es la razón de ser de ese botón.
    deptos_por_codigo = {d["codigo"]: d for d in deptos}
    fijo_moroso = deptos_por_codigo.get(CODIGO_MOROSO_FIJO)
    deptos_con_login = puntuales + irregulares + (
        [fijo_moroso] if fijo_moroso is not None else []
    )

    email_de = {d["id"]: f"uf{d['codigo'][3:].lower()}@{DOMINIO_DEMO}" for d in deptos}
    tokens_depto = {}
    for depto in deptos_con_login:
        email = email_de[depto["id"]]
        token = api.login(email, passwords_iniciales[email])
        api.cambiar_password(token, passwords_iniciales[email], seed_password)
        tokens_depto[depto["id"]] = token

    comprobantes = 0
    liquidaciones = 0
    comunicados = 0
    cuotas_obra = 0
    for i, periodo in enumerate(meses):
        for titulo, cuerpo in COMUNICADOS_DEMO[i * 2: i * 2 + 2]:
            api.req("POST", "/comunicados", token=admin_token, cid=cid,
                    json={"titulo": titulo, "cuerpo": cuerpo}, expect=201)
            comunicados += 1

        # Obra extraordinaria financiada en 6 cuotas por la clase B. Es lo que
        # le da sentido a tener varias clases de prorrateo: sin esto todo va
        # por la clase A y el sistema parece más simple de lo que es. Se
        # carga una sola vez, en el primer período, antes de su cierre.
        if periodo == meses[0]:
            api.req("POST", "/gastos/plan-cuotas", token=admin_token, cid=cid, json={
                "periodo": periodo,
                "rubro": "mantenimiento_partes_comunes",
                "clase_prorrateo_id": clase_b,
                "proveedor_id": proveedor_para_gasto(
                    "mantenimiento_partes_comunes",
                    "Reparación integral del frente del edificio", proveedores, RNG),
                "concepto": "Reparación integral del frente del edificio",
                "monto": importe_por_cuota(COSTO_TOTAL_OBRA_DEMO, CUOTAS_OBRA_DEMO),
                "forma_pago": "transferencia",
                "caja_id": _caja_default(api, admin_token, cid),
                "fecha_pago": _dia_del_periodo(periodo, 5).isoformat(),
                "cuota_total": CUOTAS_OBRA_DEMO,
            }, expect=201)
            cuotas_obra = CUOTAS_OBRA_DEMO

        for rubro, concepto, lo, hi in RUBROS_COMUNES:
            if rubro == "sueldos_y_cargas_sociales":
                continue  # ahora los genera la liquidación, ver más abajo
            api.req("POST", "/gastos", token=admin_token, cid=cid, json={
                "periodo": periodo, "rubro": rubro,
                "clase_prorrateo_id": clase_a,
                "proveedor_id": proveedor_para_gasto(rubro, concepto, proveedores, RNG),
                "concepto": concepto,
                "monto": round(RNG.uniform(lo, hi), 2),
                "forma_pago": "transferencia",
                "caja_id": _caja_default(api, admin_token, cid),
                "fecha_pago": _dia_del_periodo(periodo, RNG.randint(3, 26)).isoformat(),
            }, expect=201)

        for _ in range(RNG.randint(1, 3)):
            depto = RNG.choice(deptos)
            concepto_reparacion = f"Reparación privada {depto['codigo']}"
            api.req("POST", "/gastos", token=admin_token, cid=cid, json={
                "periodo": periodo, "rubro": "trabajos_reparaciones_unidades",
                "departamento_id": depto["id"],
                "proveedor_id": proveedor_para_gasto(
                    "trabajos_reparaciones_unidades", concepto_reparacion, proveedores, RNG),
                "concepto": concepto_reparacion,
                "monto": round(RNG.uniform(15_000, 90_000), 2),
                "forma_pago": "transferencia",
                "caja_id": _caja_default(api, admin_token, cid),
                "fecha_pago": _dia_del_periodo(periodo, RNG.randint(5, 25)).isoformat(),
            }, expect=201)

        # Liquidación del encargado: genera gastos del rubro
        # sueldos_y_cargas_sociales que tienen que entrar al prorrateo de
        # este período, por eso se carga antes del cierre.
        haberes_payload = [{"haber_id": h} for h in personal["haberes"]]
        # El último haber del catálogo (Horas extra) es cantidad_x_valor: sin
        # `cantidad` el endpoint devuelve 400 "requiere `cantidad`"
        # (backend/routers/liquidaciones.py:148).
        haberes_payload[-1]["cantidad"] = 8.0
        api.req("POST", "/liquidaciones", token=admin_token, cid=cid, json={
            "empleado_id": personal["empleado_id"],
            "periodo": periodo,
            "caja_id": _caja_default(api, admin_token, cid),
            "haberes": haberes_payload,
        }, expect=201)
        liquidaciones += 1

        f1, f2 = _fechas_del_periodo(periodo)

        # Todo el bloque del período —cierre, lectura de expensas (que
        # devenga recargos de arrastre) y carga de pagos— corre bajo el
        # reloj simulado del día de cierre. Ver el docstring de `reloj_en`:
        # sin esto, `cierre.py` y `recargos.py` evalúan mora contra la fecha
        # real de la corrida en vez de la fecha histórica del período, y
        # unidades puntuales terminan con recargo por un pago que todavía no
        # se cargó.
        with reloj_en(dia_de_cierre(periodo)):
            api.req("POST", f"/periodos/{periodo}/cerrar", token=admin_token, cid=cid, json={
                "fecha_primer_vencimiento": f1.isoformat(),
                "fecha_segundo_vencimiento": f2.isoformat(),
            }, expect=201)

            r = api.req("GET", f"/expensas?periodo={periodo}", token=admin_token, cid=cid,
                        expect=200)
            expensas_por_depto = {e["departamento_id"]: e for e in r.json()}

            pagan = [d["id"] for d in puntuales]
            pagan += [d["id"] for d in irregulares if RNG.random() < 0.5]
            es_ultimo = periodo == meses[-1]

            # Filtrado ANTES del loop, no `continue` adentro: deja_pendiente()
            # decide sobre el índice y el total de comprobantes que van a
            # existir de verdad. Si el filtro viviera como un `continue` dentro
            # del for, un depto sin expensa o sin login corrido podría desalinear
            # `idx`/`len(...)` de los comprobantes efectivamente creados y, en el
            # peor caso, dejar el período entero sin ninguna cobranza aprobada
            # (la garantía que promete el docstring de deja_pendiente).
            pagan_con_datos = [
                depto_id for depto_id in pagan
                if depto_id in expensas_por_depto and depto_id in tokens_depto
            ]

            for idx, depto_id in enumerate(pagan_con_datos):
                exp = expensas_por_depto[depto_id]
                # `date.today()` acá es el de este módulo (seed_demo), no el
                # de periodos/cierre/recargos: reloj_en no lo toca a
                # propósito, así que sigue siendo la fecha real del proceso
                # — el tope que evita un comprobante fechado en el futuro
                # real. Ver el docstring de reloj_en.
                fecha_pago = fecha_pago_puntual(f1, date.today(), RNG)
                monto = exp["monto_primer_vencimiento"]
                if RNG.random() < 0.05:
                    monto = float(int(monto / 1000 + 1) * 1000)
                r = api.req("POST", "/comprobantes", token=tokens_depto[depto_id], cid=cid,
                            data={"fecha_pago": fecha_pago.isoformat(), "monto": monto},
                            files={"archivo": ("pago.png", imagen_comprobante(comprobantes), "image/png")},
                            expect=201)
                if not deja_pendiente(idx, len(pagan_con_datos), es_ultimo):
                    api.req("PATCH", f"/comprobantes/{r.json()['id']}", token=admin_token, cid=cid,
                            json={"estado": "aprobado"}, expect=200)
                comprobantes += 1
        print(f"[demo] {periodo}: cerrado · {len(pagan)} pagos")

    # --- Reservas de amenities (fechas futuras, relativas a "ahora") ---
    # Portado de seed_e2e.py:286-305 con la escala ajustada de 180 deptos a 18
    # (k=8 en vez de k=25). El POST deliberadamente NO lleva expect=201: hay
    # reservas random que chocan con la política del amenity y dan 409
    # legítimo, y eso no debe hacer explotar el generador.
    reservantes = RNG.sample(sorted(tokens_depto), k=min(8, len(tokens_depto)))
    reservas = 0
    reservas_canceladas = 0
    for depto_id in reservantes:
        amenity = RNG.choice(list(amenities.values()))
        # La hora sale de una decisión, no del reloj de quien corre esto. Antes
        # era `now() + 1..5 h`: regenerar el demo de madrugada dejaba el SUM
        # alquilado de 3 a 6 AM, que es lo primero que ve un interesado. El
        # tope de las 19 deja lugar a las 3 h de duración máxima de abajo sin
        # que la reserva cruce la medianoche.
        inicio = (datetime.now() + timedelta(days=RNG.randint(2, 40))).replace(
            hour=RNG.randint(10, 19), minute=0, second=0, microsecond=0
        )
        r = api.req("POST", f"/amenities/{amenity}/reservas", token=tokens_depto[depto_id],
                    cid=cid, json={
                        "inicio": inicio.isoformat(),
                        "fin": (inicio + timedelta(hours=RNG.randint(1, 3))).isoformat(),
                    })
        if r.status_code == 201:
            reservas += 1
            # La primera reserva exitosa se cancela siempre (determinista): el
            # 20% al azar puede no tocar a nadie en una corrida entera —pasó
            # de hecho en una corrida real, 0 de 8— y sin al menos una
            # cancelación la reversa del cargo en cuenta corriente, que es lo
            # que hace interesante al módulo, no queda demostrada. El resto
            # sigue al 20% probabilístico para sumar variedad.
            if reservas_canceladas == 0 or RNG.random() < 0.2:
                api.req("DELETE", f"/reservas/{r.json()['id']}",
                        token=tokens_depto[depto_id], cid=cid)
                reservas_canceladas += 1
            else:
                # El cargo en cuenta corriente de una reserva confirmada
                # (nota_debito) no lo cobra ningún cierre de período: sin
                # esto queda impago para siempre y, sobre el saldo exacto del
                # precio del amenity, /reportes/morosos lo confunde con un
                # moroso real (misma imputación por antigüedad — ver C1 en
                # la revisión final). Se paga y aprueba en el momento, como
                # haría cualquier consorcio que de verdad cobra el SUM.
                rc = api.req(
                    "POST", "/comprobantes", token=tokens_depto[depto_id], cid=cid,
                    data={"fecha_pago": date.today().isoformat(),
                          "monto": precios_amenity[amenity]},
                    files={"archivo": ("pago.png", imagen_comprobante(comprobantes), "image/png")},
                    expect=201,
                )
                api.req("PATCH", f"/comprobantes/{rc.json()['id']}", token=admin_token, cid=cid,
                        json={"estado": "aprobado"}, expect=200)
                comprobantes += 1
    print(f"[demo] reservas: {reservas} · canceladas: {reservas_canceladas}")

    # --- Peticiones → trabajos → presupuestos ---
    # Portado de seed_e2e.py:307-351 con la escala ajustada (k=6 en vez de
    # k=12). EstadoPeticion tiene 4 valores (abierta, convertida_en_trabajo,
    # rechazada, cancelada — backend/models.py), pero la lógica probabilística
    # de seed_e2e.py sólo alcanza dos: nunca llama a PATCH /peticiones/{id}
    # (único camino a rechazada) ni a POST /trabajos/{id}/cancelar (único
    # camino a cancelada, que cascadea desde el trabajo — ver
    # backend/routers/trabajos.py:190-201). Por eso acá los primeros 4 deptos
    # muestreados recorren los 4 estados de forma explícita y determinista;
    # los 2 restantes quedan con la lógica probabilística original para sumar
    # variedad dentro de "convertida_en_trabajo".
    peticionantes = RNG.sample(sorted(tokens_depto), k=min(6, len(PROBLEMAS_DEMO)))
    peticiones = 0
    trabajos_creados = 0
    for indice, depto_id in enumerate(peticionantes):
        titulo, relato, descripcion_trabajo, razon_proveedor = PROBLEMAS_DEMO[indice]
        r = api.req("POST", "/peticiones", token=tokens_depto[depto_id], cid=cid, json={
            "titulo": titulo,
            "descripcion": relato,
        }, expect=201)
        peticion_id = r.json()["id"]
        peticiones += 1

        if indice == 0:
            continue  # queda abierta, sin tocar

        if indice == 1:
            api.req("PATCH", f"/peticiones/{peticion_id}", token=admin_token, cid=cid,
                    json={"estado": "rechazada"}, expect=200)
            continue

        if indice == 2:
            r = api.req("POST", "/trabajos", token=admin_token, cid=cid, json={
                "peticion_id": peticion_id,
                "descripcion": descripcion_trabajo,
            }, expect=201)
            trabajo_id = r.json()["id"]
            trabajos_creados += 1
            api.req("POST", f"/trabajos/{trabajo_id}/cancelar", token=admin_token, cid=cid,
                    expect=204)
            continue

        # De acá en adelante todas se convierten en trabajo. Antes los
        # índices 4 y 5 dependían de un sorteo al 60% y podían no salir
        # ninguno: quedaban dos trabajos, uno de ellos cancelado, y la
        # pantalla no llegaba a mostrar el circuito. Ahora el módulo muestra
        # el ciclo entero — cancelado, en curso y completado.

        r = api.req("POST", "/trabajos", token=admin_token, cid=cid, json={
            "peticion_id": peticion_id,
            "descripcion": descripcion_trabajo,
        }, expect=201)
        trabajo_id = r.json()["id"]
        trabajos_creados += 1

        # Se piden presupuestos a varios y se aprueba el del proveedor que
        # atiende ese rubro. Antes se sorteaban los proveedores entre todos y
        # se aprobaba el último sorteado: quedaba la empresa de limpieza
        # presupuestando el ascensor, y encima ganándolo.
        assert razon_proveedor in proveedores, razon_proveedor
        competidores = [pid for razon, pid in proveedores.items()
                        if razon != razon_proveedor]
        del_rubro = None
        for prov in [proveedores[razon_proveedor]] + RNG.sample(competidores, k=RNG.randint(0, 2)):
            # El endpoint de presupuestos recibe multipart/form-data.
            r = api.req("POST", f"/trabajos/{trabajo_id}/presupuestos",
                        token=admin_token, cid=cid,
                        data={"proveedor_id": str(prov),
                              "monto": str(round(RNG.uniform(20_000, 150_000), 2))},
                        expect=201)
            if prov == proveedores[razon_proveedor]:
                del_rubro = r.json()
        if del_rubro is not None:
            api.req("POST",
                    f"/trabajos/{trabajo_id}/presupuestos/{del_rubro['id']}/aprobar",
                    token=admin_token, cid=cid, expect=200)

        # Uno de los trabajos llega hasta el final: sin un trabajo terminado
        # el módulo muestra sólo problemas abiertos, que es la mitad de la
        # historia que tiene para contar.
        #
        # `POST /completar` no completa nada pese al nombre: devuelve el
        # gasto ya pre-cargado con el proveedor y el monto del presupuesto
        # aprobado (ver su `summary` en routers/trabajos.py). Lo que cierra
        # el trabajo es dar de alta ese gasto con `trabajo_id`
        # (routers/gastos.py, "Integración Fase 11"), que además le avisa al
        # vecino que su reclamo se resolvió. Recorrer los dos pasos es
        # justamente el circuito que la pantalla tiene para mostrar.
        if indice == 4:
            r = api.req("POST", f"/trabajos/{trabajo_id}/completar",
                        token=admin_token, cid=cid, expect=200)
            borrador = r.json()
            # Al mes en curso, no al último cerrado: un período cerrado no
            # admite cambios (409). Y es lo que pasa de verdad — el trabajo
            # se terminó ahora y su gasto entra en el cierre que viene.
            hoy = date.today()
            api.req("POST", "/gastos", token=admin_token, cid=cid, json={
                "periodo": hoy.strftime("%Y-%m"),
                "rubro": "mantenimiento_partes_comunes",
                "clase_prorrateo_id": clase_a,
                "proveedor_id": borrador["proveedor_id"],
                "concepto": borrador["concepto_sugerido"],
                "monto": borrador["monto"],
                "forma_pago": "transferencia",
                "caja_id": _caja_default(api, admin_token, cid),
                "fecha_pago": hoy.isoformat(),
                "trabajo_id": trabajo_id,
            }, expect=201)
    print(f"[demo] peticiones: {peticiones} · trabajos: {trabajos_creados}")

    dt = time.monotonic() - t0
    return {
        "consorcio_id": cid,
        "clase_a": clase_a,
        "clase_b": clase_b,
        "deptos": n,
        "meses": meses,
        "comprobantes": comprobantes,
        "liquidaciones": liquidaciones,
        "comunicados": comunicados,
        "cuotas_obra": cuotas_obra,
        "reservas": reservas,
        "reservas_canceladas": reservas_canceladas,
        "peticiones": peticiones,
        "amenities": amenities,
        "proveedores": proveedores,
        "tokens_depto": tokens_depto,
        "morosos": [d["codigo"] for d in morosos],
        "segundos": round(dt, 1),
    }


def _resetear_esquema(engine) -> None:
    """Borra todas las tablas para regenerar el dataset desde cero.

    En SQLite no alcanza con `drop_all`: backend/database.py activa
    `PRAGMA foreign_keys=ON` en cada conexión, y el modelo tiene un ciclo de FK
    (cajas → consorcios → presupuestos → trabajos), así que al soltar la primera
    tabla referenciada por otra con filas cargadas SQLite tira
    `IntegrityError: FOREIGN KEY constraint failed`. El pragma es *por
    conexión*, por eso lo apagamos en la conexión donde corre el DROP en vez de
    tocar la configuración global del engine.
    """
    from sqlalchemy import text

    from .models import Base

    if engine.url.get_backend_name() != "sqlite":
        # drop_all no sirve aca: ordena las tablas topologicamente y el modelo
        # tiene un ciclo de FK (cajas -> consorcios -> presupuestos ->
        # trabajos), asi que no puede resolver el orden y falla al soltar una
        # tabla todavia referenciada. DROP SCHEMA ... CASCADE no depende del
        # orden: se lleva todo el esquema de una, constraints incluidas.
        #
        # Esto requiere que el rol de conexion sea DUEÑO del esquema `public`
        # — en el addon estandar de Postgres de Railway conecta como
        # `postgres`, superusuario de esa instancia dedicada, que bypasea
        # el chequeo de ownership, asi que hoy siempre se cumple. Si el demo
        # se mudara a otro Postgres administrado con roles acotados (RDS,
        # Cloud SQL con un usuario no-superusuario, etc.) esto puede fallar
        # en silencio cada 6 h sin fallback. La salida portable, si llega
        # ese caso, es dropear las tablas del metadata con CASCADE en vez
        # del esquema entero (`DROP TABLE ... CASCADE` por cada tabla, o el
        # equivalente vía `Base.metadata.tables`): esas tablas las crea este
        # mismo rol via create_all, asi que siempre las posee, sin depender
        # de ser dueño del esquema.
        with engine.begin() as conn:
            try:
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
            except Exception:
                # Fallback portable si el rol de conexión no es dueño del esquema `public`:
                # dropea cada tabla de los modelos con CASCADE para ignorar ciclos de FK.
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
                # Idem que en SQLite: sin esto el upgrade posterior es un no-op
                # y la base queda vacía. El camino de arriba no lo necesita
                # porque DROP SCHEMA se lleva todo.
                conn.execute(text('DROP TABLE IF EXISTS "alembic_version" CASCADE'))
        return

    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            Base.metadata.drop_all(bind=conn)
            # `alembic_version` no está en Base.metadata —la maneja Alembic—,
            # así que drop_all no la toca. Si sobrevive marcada en la cabeza,
            # el `alembic upgrade head` de acá abajo concluye que no hay nada
            # que aplicar y la base queda sin una sola tabla: el generador
            # muere después con "no such table: usuarios". Sólo se nota
            # regenerando sobre una demo.db que ya existía.
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
    finally:
        # Salir del `with` NO cierra la conexión física: la devuelve al
        # QueuePool con foreign_keys todavía en OFF. El listener de
        # backend/database.py:19 sólo corre al abrir conexiones *nuevas*, no en
        # los checkouts reciclados — así que cualquier próximo SessionLocal()
        # del proceso puede llevarse esa misma conexión reciclada (sin importar
        # el orden de entrega del pool) y operar sin integridad referencial, en
        # silencio y para siempre. Acá pasa de verdad: generar_dataset_demo()
        # sigue con TestClient(app), cuyo lifespan hace create_all sobre este
        # mismo engine — y esto sólo corre para SQLite, que es el motor de
        # desarrollo y de los tests; en producción el demo resetea sobre
        # Postgres desde un proceso de cron aparte, sin este camino.
        #
        # dispose() descarta el pool entero, así que la siguiente conexión es
        # física y nueva y el listener vuelve a poner foreign_keys=ON. Se
        # prefiere a un `PRAGMA foreign_keys=ON` de cierre porque va en
        # `finally`: si el drop falla a mitad de camino, la conexión vuelve al
        # pool igual de envenenada, y un pragma de reparación tendría que correr
        # sobre una conexión que quizás ya está en estado inválido.
        engine.dispose()


def _aplicar_migraciones() -> None:
    """Deja el esquema al día con `alembic upgrade head`.

    Se llama en proceso (no por subprocess) para que herede la DATABASE_URL ya
    resuelta por Settings: quien invoca este módulo pasa la URL por variable de
    entorno y un subprocess podría leer un .env distinto.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    raiz = Path(__file__).resolve().parents[1]
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "backend" / "migrations"))
    command.upgrade(cfg, "head")


def generar_dataset_demo(*, seed_password: str, sa_email: str, sa_password: str,
                         reset: bool = False, hacer_export: bool = False) -> dict:
    """Genera el dataset demo completo. Núcleo reusable.

    No lee sys.argv ni llama a sys.exit: lo invoca `main()` de este mismo
    módulo desde el proceso de cron (`python -m backend.seed_demo --reset`),
    aparte del servidor web. Ante un problema levanta la excepción para que el
    llamador decida — un exit abrupto acá no tiene servidor que proteger.

    `hacer_export` sigue el mismo patrón que `reset`: es un booleano explícito
    que decide el llamador (en `main()`, a partir de `--exportar` en
    sys.argv), no algo que esta función lea de sys.argv por su cuenta.
    """
    from fastapi.testclient import TestClient

    from .database import SessionLocal, engine
    from .main import app
    from .seed_super_admin import seed as seed_super_admin

    if reset:
        print("[demo] reset: borrando todas las tablas")
        _resetear_esquema(engine)
        print("[demo] aplicando migraciones")
        _aplicar_migraciones()

    t0 = time.monotonic()
    return _generar(seed_password, sa_email, sa_password, t0, TestClient,
                    app, SessionLocal, seed_super_admin, hacer_export)


def _generar(seed_password, sa_email, sa_password, t0, TestClient, app,
             SessionLocal, seed_super_admin, hacer_export: bool = False) -> dict:
    with TestClient(app) as client:  # lifespan: create_all + migraciones
        with SessionLocal() as db:
            seed_super_admin(db)

        api = Api(client)
        sa_token = api.login(sa_email, sa_password)

        r = api.req("POST", "/super-admin/administraciones", token=sa_token, json={
            "razon_social": NOMBRE_ADMINISTRACION_DEMO,
            "cuit": "30-70000000-3",
            "email_contacto": EMAIL_CONTACTO_ADMINISTRACION_DEMO,
            "admin_email": EMAIL_ADMIN_DEMO,
            "admin_password_inicial": seed_password + "-inicial",
        }, expect=201)
        print(f"[demo] administración creada id={r.json()['id']}")

        admin_token = api.login(EMAIL_ADMIN_DEMO, seed_password + "-inicial")
        api.cambiar_password(admin_token, seed_password + "-inicial", seed_password)

        m = poblar_demo(api, admin_token, seed_password)

        # Volcado a JSON estático para la demo del navegador sin backend (Plan
        # B). Corre acá adentro, todavía con el TestClient in-process
        # abierto: exportar() vuelve a pedirle cada ruta a la propia API, con
        # el mismo cliente que puebla el dataset, para que la forma del
        # export no pueda divergir del contrato.
        if hacer_export:
            from .config import get_settings
            from .export_demo import escribir, exportar, exportar_comprobantes, exportar_pdfs
            destino = Path(__file__).parent.parent / "frontend" / "src" / "demo" / "dataset.json"
            datos = exportar(api, admin_token, m["tokens_depto"], m["consorcio_id"])

            # Imágenes de comprobante reales, no la clave de almacenamiento que
            # devuelve la API (que en la demo sin backend no tiene a quién
            # pedirle la URL firmada). Reescribe `datos["/comprobantes"]`
            # in-place con el path estático.
            mapa_comprobantes = exportar_comprobantes(
                datos, Path(get_settings().UPLOAD_DIR), _DIR_ASSETS,
                Path(__file__).parent.parent / "frontend" / "public" / "demo-comprobantes",
            )
            print(f"[demo] {len(mapa_comprobantes)} comprobantes con imagen exportada")

            # PDFs reales de la boleta del último período cerrado, uno por
            # unidad, servidos sueltos fuera del paquete de la app: van a
            # frontend/public/ (estáticos de Vite, no entran al bundle de JS)
            # para que "ver PDF" en la demo abra el propio sin backend.
            ultimo = m["meses"][-1]
            expensas_ultimas = [
                e for e in datos["/expensas"] if e["periodo"] == ultimo
            ]
            mapa = exportar_pdfs(
                api, admin_token, m["consorcio_id"], expensas_ultimas,
                Path(__file__).parent.parent / "frontend" / "public" / "demo-pdfs",
            )
            datos["_pdfs"] = mapa
            escribir(datos, destino)
            print(f"[demo] dataset exportado a {destino}")
            print(f"[demo] {len(mapa)} PDFs exportados")

    m["segundos_total"] = round(time.monotonic() - t0, 1)
    print(f"\n[demo] listo en {m['segundos_total']} s · {m['deptos']} UF · "
          f"{len(m['meses'])} períodos · {m['comprobantes']} comprobantes")
    print(f"[demo] meses generados: {m['meses'][0]} … {m['meses'][-1]}")
    return m


def exportar_desde_db(seed_password: str) -> None:
    """Sólo-exportar: regenera dataset.json a partir de una `demo.db` ya
    poblada, SIN volver a correr `poblar_demo()` (que tarda ~2 minutos).

    Existe porque regenerar el dataset no tenía otro camino documentado que
    re-sembrar desde cero: `_generar()` siempre llama a `poblar_demo()`. Un
    cambio de contrato que sólo toca qué se exporta (agregar una ruta,
    cambiar cómo se arma una clave auxiliar) no necesita datos nuevos, sólo
    reflejar los que ya están.

    No pasa por `seed_super_admin` ni por la creación del consorcio: loguea
    directo contra los usuarios que YA existen en la base — el admin y los
    dos deptos pinneados del selector de demo-login (`CODIGO_PUNTUAL_FIJO` /
    `CODIGO_MOROSO_FIJO`), con la MISMA `seed_password` que se les puso al
    sembrar (el admin ya tiene la definitiva, no la de alta). Si `demo.db`
    no tiene lo que el export espera (por ejemplo, está vacía), revienta con
    el mismo `RuntimeError` de `_verificar` en vez de escribir un dataset a
    medias.

    Uso:
        DEMO_SEED_PASSWORD=... DATABASE_URL=sqlite:///./demo.db \\
        SEED_ENABLED=false python -m backend.seed_demo --solo-exportar
    """
    from fastapi.testclient import TestClient

    from .main import app

    with TestClient(app) as client:
        api = Api(client)
        admin_token = api.login(EMAIL_ADMIN_DEMO, seed_password)

        r = api.req("GET", "/me/consorcios", token=admin_token, expect=200)
        consorcios = r.json()
        if not consorcios:
            raise RuntimeError(
                "demo.db no tiene ningún consorcio: --solo-exportar necesita "
                "una base ya poblada por poblar_demo() (corré sin --reset "
                "primero, o con --reset una única vez)."
            )
        cid = consorcios[0]["id"]

        # Sólo los dos deptos que el export realmente usa (ver
        # _CODIGOS_DEPTOS_NOTIFICACIONES en export_demo.py): son los únicos
        # con login desde el selector de demo-login, así que son los únicos
        # cuya password conocemos acá.
        r = api.req("GET", "/departamentos", token=admin_token, cid=cid, expect=200)
        tokens_depto: dict[int, str] = {}
        for depto in r.json():
            if depto["codigo"] not in (CODIGO_PUNTUAL_FIJO, CODIGO_MOROSO_FIJO):
                continue
            email = f"uf{depto['codigo'][3:].lower()}@{DOMINIO_DEMO}"
            tokens_depto[depto["id"]] = api.login(email, seed_password)

        from .config import get_settings
        from .export_demo import escribir, exportar, exportar_comprobantes, exportar_pdfs

        destino = Path(__file__).parent.parent / "frontend" / "src" / "demo" / "dataset.json"
        datos = exportar(api, admin_token, tokens_depto, cid)

        mapa_comprobantes = exportar_comprobantes(
            datos, Path(get_settings().UPLOAD_DIR), _DIR_ASSETS,
            Path(__file__).parent.parent / "frontend" / "public" / "demo-comprobantes",
        )
        print(f"[demo] {len(mapa_comprobantes)} comprobantes con imagen exportada")

        # Período más reciente entre los ya cerrados: mismo criterio que
        # `m["meses"][-1]` en `_generar()`, pero leído de la base en vez de
        # recalculado — acá no corrió `meses_demo()`.
        ultimo = max(p["periodo"] for p in datos["/periodos"])
        expensas_ultimas = [e for e in datos["/expensas"] if e["periodo"] == ultimo]
        mapa = exportar_pdfs(
            api, admin_token, cid, expensas_ultimas,
            Path(__file__).parent.parent / "frontend" / "public" / "demo-pdfs",
        )
        datos["_pdfs"] = mapa
        escribir(datos, destino)
        print(f"[demo] dataset exportado a {destino}")
        print(f"[demo] {len(mapa)} PDFs exportados")


def main() -> None:
    """Entrypoint de CLI: valida el entorno y delega."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    seed_password = os.environ.get("DEMO_SEED_PASSWORD", "")
    if not seed_password:
        print("Falta DEMO_SEED_PASSWORD", file=sys.stderr)
        sys.exit(1)
    if len(seed_password) < 8:
        print("DEMO_SEED_PASSWORD debe tener al menos 8 caracteres", file=sys.stderr)
        sys.exit(1)

    if "--solo-exportar" in sys.argv:
        # No hace falta SUPER_ADMIN_EMAIL/PASSWORD acá: no se siembra nada,
        # sólo se loguea contra usuarios que ya existen en demo.db.
        exportar_desde_db(seed_password)
        return

    sa_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
    sa_password = os.environ.get("SUPER_ADMIN_PASSWORD", "")
    if not sa_email or not sa_password:
        print("Faltan SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD", file=sys.stderr)
        sys.exit(1)

    generar_dataset_demo(
        seed_password=seed_password,
        sa_email=sa_email,
        sa_password=sa_password,
        reset="--reset" in sys.argv,
        hacer_export="--exportar" in sys.argv,
    )


if __name__ == "__main__":
    main()
