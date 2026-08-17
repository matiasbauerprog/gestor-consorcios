# Dataset demo curado y exportable — Plan A

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el generador del demo produzca un dataset creíble frente a un administrador de consorcios, y que ese dataset pueda exportarse a un archivo estático que consuma la demo sin backend.

**Architecture:** Se corrigen seis defectos del generador (`backend/seed_demo.py`), cada uno extrayendo la decisión a una función pura testeable, siguiendo el patrón que ya usan `meses_demo` y `perfiles_deterministas`. Después se agrega un exportador que recorre la base recién generada y vuelca un JSON con los datos en la forma exacta en que los devuelve cada endpoint.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 · pytest. Sin dependencias nuevas: la simulación del reloj usa `unittest.mock.patch` de la stdlib.

**Spec:** `docs/superpowers/specs/2026-08-16-demo-sin-backend-design.md` (§3)

## Global Constraints

- **No se toca el backend de producción.** Ni `backend/routers/`, ni `backend/models.py`, ni `openapi.yaml`. Todo el trabajo es en `backend/seed_demo.py`, un módulo nuevo de exportación y `tests/`.
- **Sin dependencias nuevas** en `requirements.txt`.
- **Los tests son sobre funciones puras.** Correr el generador completo tarda 67-69 s; ningún test de este plan debe invocarlo.
- **Determinismo:** el generador usa un `RNG` sembrado (`backend/seed_e2e.py`). Cualquier función nueva que use azar debe recibir el `RNG` como parámetro, nunca crear uno propio.
- Comando de tests: `pytest tests/test_seed_demo.py -v` desde la raíz del repo.
- Comando para regenerar el dataset completo (sólo verificación manual al final):
  `DEMO_SEED_PASSWORD=demo1234 SUPER_ADMIN_EMAIL=sa@demo.local SUPER_ADMIN_PASSWORD=demo12345678 DATABASE_URL=sqlite:///./demo.db SEED_ENABLED=false python -m backend.seed_demo --reset`

---

### Task 1: Proveedor coherente con el rubro del gasto

Hoy `backend/seed_demo.py` asigna `"proveedor_id": RNG.choice(proveedores)` a cada gasto, así que en pantalla se lee "Honorarios administración → Limpieza Total SRL", "Seguro integral consorcio → ElectroSur SRL" y "Comisiones bancarias → Ascensores Vertirod SA". Un administrador lo nota de inmediato y deja de creer en el resto de los números.

**Files:**
- Modify: `backend/seed_demo.py` (lista de proveedores ~línea 271; gastos ~líneas 377 y 390)
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Produces: `proveedor_para_rubro(rubro: str, proveedores: dict[str, int], rng) -> int` — devuelve el id del proveedor que corresponde al rubro. `proveedores` mapea razón social → id.
- Produces: `PROVEEDORES_DEMO: list[tuple[str, str]]` — lista de (razón social, rubro que atiende).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo.py
from backend.seed_demo import PROVEEDORES_DEMO, proveedor_para_rubro


def test_cada_rubro_comun_tiene_un_proveedor_plausible():
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
    proveedores = {razon: i + 1 for i, (razon, _) in enumerate(PROVEEDORES_DEMO)}
    elegido = proveedor_para_rubro("rubro_que_no_existe", proveedores, None)
    assert elegido in proveedores.values()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -k proveedor -v`
Expected: FAIL con `ImportError: cannot import name 'PROVEEDORES_DEMO'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/seed_demo.py — cerca de las constantes de arriba (junto a PISOS_DEMO)

# Proveedor por rubro: en pantalla, un gasto de seguros facturado por una
# empresa de ascensores destruye la credibilidad del dataset entero. El
# segundo elemento es el rubro que atiende cada proveedor.
PROVEEDORES_DEMO: list[tuple[str, str]] = [
    ("Limpieza Total SRL", "abonos_y_servicios"),
    ("Ascensores Vertirod SA", "abonos_y_servicios"),
    ("ElectroSur SRL", "mantenimiento_partes_comunes"),
    ("Plomería Paz", "mantenimiento_partes_comunes"),
    ("Seguros La Continental", "seguros"),
    ("Estudio Rossi & Asociados", "gastos_administracion"),
    ("Servicios Metropolitanos SA", "servicios_publicos"),
    ("Banco Ciudad", "gastos_bancarios"),
]

_PROVEEDOR_POR_RUBRO = {
    "gastos_administracion": "Estudio Rossi & Asociados",
    "seguros": "Seguros La Continental",
    "servicios_publicos": "Servicios Metropolitanos SA",
    "gastos_bancarios": "Banco Ciudad",
    "abonos_y_servicios": "Limpieza Total SRL",
    "mantenimiento_partes_comunes": "Plomería Paz",
    "trabajos_reparaciones_unidades": "Plomería Paz",
    "sueldos_y_cargas_sociales": "Estudio Rossi & Asociados",
}


def proveedor_para_rubro(rubro: str, proveedores: dict[str, int], rng) -> int:
    """Id del proveedor que corresponde a `rubro`.

    `proveedores` mapea razón social → id (los ids los devuelve la API al
    crearlos). Un rubro sin mapa cae en el primero de la lista en vez de
    elegir al azar: un default estable es preferible a uno que cambia entre
    corridas y hace irreproducible el dataset.
    """
    razon = _PROVEEDOR_POR_RUBRO.get(rubro)
    if razon is None or razon not in proveedores:
        return next(iter(proveedores.values()))
    return proveedores[razon]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_demo.py -k proveedor -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Conectar el generador a la función nueva**

En `backend/seed_demo.py`, reemplazar el bloque que crea los proveedores (hoy itera sobre una lista de 5 razones sociales y acumula en la lista `proveedores`) por uno que construya el diccionario:

```python
    proveedores = {}
    for razon, _rubro in PROVEEDORES_DEMO:
        r = api.req("POST", "/proveedores", token=admin_token, cid=cid,
                    json={"razon_social": razon,
                          "cuit": f"30-{RNG.randint(10_000_000, 99_999_999)}-{RNG.randint(0, 9)}"},
                    expect=201)
        proveedores[razon] = r.json()["id"]
```

Y en los tres lugares que hoy dicen `"proveedor_id": RNG.choice(proveedores)`, poner `"proveedor_id": proveedor_para_rubro(rubro, proveedores, RNG)`. En el gasto particular a un departamento el rubro es la constante `"trabajos_reparaciones_unidades"`.

**Ojo:** el plan de cuotas de la obra de frente usa `proveedores[0]` (índice de lista). Cambiarlo a `proveedor_para_rubro("mantenimiento_partes_comunes", proveedores, RNG)`.

**Ojo 2:** `crear_catalogo_personal(api, admin_token, cid, proveedor_id)` recibe un id suelto; pasarle `proveedor_para_rubro("sueldos_y_cargas_sociales", proveedores, RNG)`.

**Ojo 3:** la sección de presupuestos hace `RNG.sample(proveedores, k=...)` sobre la lista. Con un dict hay que cambiarlo a `RNG.sample(sorted(proveedores.values()), k=...)`.

- [ ] **Step 6: Verificar que el generador sigue corriendo entero**

Run: el comando de regeneración de "Global Constraints"
Expected: termina sin error e imprime el resumen con 18 deptos y 6 períodos.

- [ ] **Step 7: Commit**

```bash
git add backend/seed_demo.py tests/test_seed_demo.py
git commit -m "fix(seed): asignar el proveedor segun el rubro del gasto"
```

---

### Task 2: Dejar comprobantes pendientes de aprobación

Hoy el generador aprueba cada comprobante inmediatamente después de crearlo, así que los 50 que devuelve la API están todos en `aprobado`. El circuito que más vende —el propietario presenta el pago, administración lo aprueba y la deuda baja— **no tiene nada esperando** cuando el visitante entra.

**Files:**
- Modify: `backend/seed_demo.py` (bucle de pagos, ~líneas 430-441)
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces: `deja_pendiente(indice_pago: int, total_pagos: int, es_ultimo_periodo: bool) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo.py
from backend.seed_demo import deja_pendiente


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -k pendiente -v`
Expected: FAIL con `ImportError: cannot import name 'deja_pendiente'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/seed_demo.py

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_demo.py -k pendiente -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Conectar el generador**

En el bucle de pagos de `poblar_demo`, cambiar el `for depto_id in pagan_este_mes:` para que lleve índice y decida si aprueba:

```python
        es_ultimo = periodo == meses[-1]
        for idx, depto_id in enumerate(pagan_este_mes):
            ...  # creación del comprobante, sin cambios
            if not deja_pendiente(idx, len(pagan_este_mes), es_ultimo):
                api.req("PATCH", f"/comprobantes/{r.json()['id']}", token=admin_token,
                        cid=cid, json={"estado": "aprobado"}, expect=200)
            comprobantes += 1
```

- [ ] **Step 6: Verificar sobre la base regenerada**

Run: el comando de regeneración, y después:

```bash
python -c "
import sqlite3
c = sqlite3.connect('demo.db')
print(c.execute(\"select estado, count(*) from comprobantes group by estado\").fetchall())
"
```
Expected: aparece `pendiente_verificacion` con 3 (o el cupo que corresponda), además de los `aprobado`.

- [ ] **Step 7: Commit**

```bash
git add backend/seed_demo.py tests/test_seed_demo.py
git commit -m "fix(seed): dejar 3 comprobantes esperando aprobacion en el ultimo periodo"
```

---

### Task 3: Saldo inicial de caja para que la tesorería no arranque en rojo

El estado financiero muestra hoy la caja "Banco principal" en **−$13.263.900**. Un consorcio real no puede tener la caja negativa, y es la primera pantalla que mira un administrador. El déficit es acumulativo: los gastos se registran como egresos y sólo paga el 70-85% de las unidades.

**Files:**
- Modify: `backend/seed_demo.py` (creación del consorcio / caja default)
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Produces: `saldo_inicial_caja(gasto_mensual_estimado: float, meses: int) -> float`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo.py
from backend.seed_demo import saldo_inicial_caja


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -k saldo_inicial -v`
Expected: FAIL con `ImportError: cannot import name 'saldo_inicial_caja'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/seed_demo.py

#: Porción de las expensas que el dataset deja impaga (15% moroso + la mitad
#: del 15% irregular, según los perfiles de `perfiles_deterministas`).
_MOROSIDAD_ESTIMADA = 0.25


def saldo_inicial_caja(gasto_mensual_estimado: float, meses: int) -> float:
    """Fondo de arranque de la caja para que la tesorería no quede negativa.

    El dataset gasta todos los meses y cobra sólo lo que los perfiles de pago
    dejan cobrar, así que sin un fondo inicial la caja termina el semestre en
    rojo profundo — que es imposible en un consorcio real y desmiente al resto
    de los números en la primera pantalla que mira un administrador.

    Se cubre el déficit acumulado más un mes de colchón, redondeado a la
    centena de miles para que se lea como un fondo de reserva y no como el
    resultado de una cuenta.
    """
    deficit = gasto_mensual_estimado * _MOROSIDAD_ESTIMADA * meses
    colchon = gasto_mensual_estimado * 0.5
    return float(round((deficit + colchon) / 100_000) * 100_000)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_demo.py -k saldo_inicial -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Conectar el generador**

`POST /consorcios` crea la caja "Banco principal" con `saldo_inicial = 0`, y `CajaActualizar` **no permite** editar ese campo después (verificado en `backend/schemas.py:936`). La vía correcta es el ajuste manual: `POST /cajas/{caja_id}/movimientos` con el schema `AjusteCrear` (`fecha`, `monto` firmado, `descripcion` de 5 a 500 caracteres), que `caja_saldo.calcular_saldo` suma como tipo `ajuste`.

El endpoint se titula "no usar para ingreso/egreso, se generan auto" — y esto no es ninguno de los dos: un fondo de reserva de arranque es exactamente un ajuste.

Después de crear el consorcio y **antes** del primer período:

```python
    caja_id = _caja_default(api, admin_token, cid)
    api.req("POST", f"/cajas/{caja_id}/movimientos", token=admin_token, cid=cid, json={
        "fecha": _dia_del_periodo(meses[0], 1).isoformat(),
        "monto": saldo_inicial_caja(10_000_000, len(meses)),
        "descripcion": "Fondo de reserva inicial del consorcio",
    }, expect=201)
```

- [ ] **Step 6: Verificar sobre la base regenerada**

Run: el comando de regeneración, y después consultar el estado financiero:

```bash
python -c "
import sqlite3
c = sqlite3.connect('demo.db')
print(c.execute('select nombre, saldo_actual from cajas').fetchall())
"
```
Expected: `saldo_actual` positivo.

- [ ] **Step 7: Commit**

```bash
git add backend/seed_demo.py tests/test_seed_demo.py
git commit -m "fix(seed): fondo de reserva inicial para que la caja no quede negativa"
```

---

### Task 4: Imágenes de comprobante que se vean

Los comprobantes se suben con `_PNG_1PX`: una imagen de un píxel. En la pantalla de comprobantes se renderiza como una miniatura rota, y es una de las pantallas del circuito 1.

**Files:**
- Create: `backend/assets_demo/comprobante_1.png`, `comprobante_2.png`, `comprobante_3.png`
- Modify: `backend/seed_demo.py`
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Produces: `imagen_comprobante(indice: int) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo.py
from backend.seed_demo import imagen_comprobante


def test_imagen_comprobante_devuelve_un_png_de_verdad():
    datos = imagen_comprobante(0)
    assert datos.startswith(b"\x89PNG\r\n\x1a\n")
    # Un PNG de 1px pesa ~70 bytes; cualquier captura real pesa mucho más.
    assert len(datos) > 2_000


def test_imagen_comprobante_rota_entre_las_disponibles():
    assert imagen_comprobante(0) != imagen_comprobante(1)


def test_imagen_comprobante_no_se_pasa_de_indice():
    # Con más pagos que imágenes, tiene que seguir devolviendo alguna.
    assert imagen_comprobante(99).startswith(b"\x89PNG\r\n\x1a\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -k imagen_comprobante -v`
Expected: FAIL con `ImportError: cannot import name 'imagen_comprobante'`

- [ ] **Step 3: Crear las imágenes**

Tres capturas genéricas de comprobante de transferencia, sin datos de ninguna persona real: fondo claro, un título "Comprobante de transferencia", importe, CBU parcial enmascarado y fecha. Se pueden generar con cualquier editor o con Pillow si ya estuviera disponible; **no descargar imágenes de internet** ni usar capturas de un banco real (son marcas registradas).

Guardarlas en `backend/assets_demo/` con esos tres nombres, a 600×800 aproximadamente.

- [ ] **Step 4: Write minimal implementation**

```python
# backend/seed_demo.py
from pathlib import Path

_DIR_ASSETS = Path(__file__).parent / "assets_demo"


def imagen_comprobante(indice: int) -> bytes:
    """Bytes de una captura de transferencia para adjuntar a un comprobante.

    Rota entre las disponibles para que la lista no muestre tres veces la
    misma imagen. `_PNG_1PX` servía mientras nadie miraba los comprobantes;
    en la demo son parte del circuito que se muestra.
    """
    archivos = sorted(_DIR_ASSETS.glob("comprobante_*.png"))
    return archivos[indice % len(archivos)].read_bytes()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_seed_demo.py -k imagen_comprobante -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Conectar el generador**

En el `POST /comprobantes`, cambiar
`files={"archivo": ("pago.png", _PNG_1PX_DEMO, "image/png")}`
por
`files={"archivo": ("pago.png", imagen_comprobante(comprobantes), "image/png")}`
(`comprobantes` es el contador que ya lleva el bucle).

- [ ] **Step 7: Commit**

```bash
git add backend/seed_demo.py backend/assets_demo tests/test_seed_demo.py
git commit -m "fix(seed): comprobantes con capturas de transferencia visibles"
```

---

### Task 5: Que el "propietario al día" esté efectivamente al día

UF-01A es el destino del botón "Propietario al día" del selector de la demo y los perfiles lo pinnean como pagador puntual. Sin embargo tiene **$242.357 de saldo, un recargo por mora de $38.260 y $6.209 de intereses punitorios** (verificado sobre `demo.db`). El selector promete una cosa y la pantalla muestra otra, en rojo.

La causa: los puntuales pagan `monto_primer_vencimiento` con fecha `min(f1 - randint(0,5), date.today())`. Para el último período el primer vencimiento cae después de hoy, así que el pago queda registrado tarde y el recargo ya se aplicó.

**Files:**
- Modify: `backend/seed_demo.py` (cálculo de `fecha_pago` en el bucle de pagos)
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Produces: `fecha_pago_puntual(primer_vencimiento: date, hoy: date, rng) -> date`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo.py
from datetime import date
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -k fecha_pago -v`
Expected: FAIL con `ImportError: cannot import name 'fecha_pago_puntual'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/seed_demo.py
from datetime import date, timedelta


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_demo.py -k fecha_pago -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Conectar el generador**

Reemplazar `fecha_pago = min(f1 - timedelta(days=RNG.randint(0, 5)), date.today())` por
`fecha_pago = fecha_pago_puntual(f1, date.today(), RNG)`.

- [ ] **Step 6: Verificar sobre la base regenerada**

Run: el comando de regeneración, y después:

```bash
python -c "
import sqlite3
c = sqlite3.connect('demo.db')
q = '''select m.tipo, m.monto from movimientos_cuenta m
       join departamentos d on d.id = m.departamento_id
       where d.codigo = 'UF-01A' and m.tipo in ('recargo','interes_punitorio')'''
print(c.execute(q).fetchall())
"
```
Expected: lista vacía — el propietario "al día" no tiene ni recargos ni intereses.

- [ ] **Step 7: Commit**

```bash
git add backend/seed_demo.py tests/test_seed_demo.py
git commit -m "fix(seed): el propietario al dia paga antes del vencimiento"
```

---

### Task 6: Fechar cada emisión de expensa en su período

Los seis movimientos `expensa_emitida` de cada unidad llevan **la misma fecha**: el día en que corrió el generador. En la pestaña de movimientos del propietario se leen seis expensas emitidas el mismo día, lo que delata que los datos son fabricados.

La causa está en el backend (`routers/periodos.py:145` hace `hoy = date.today()` y fecha con eso los movimientos de emisión en la línea 183) y **no puede corregirse pasando un parámetro**. La solución que respeta "sin cambios en el backend" es que el generador simule el paso del tiempo al cerrar cada período.

**Files:**
- Modify: `backend/seed_demo.py` (el `POST /periodos/{periodo}/cerrar`)
- Test: `tests/test_seed_demo.py`

**Interfaces:**
- Produces: `dia_de_cierre(periodo: str) -> date` — el día en que se considera cerrado ese período.
- Produces: `reloj_en(fecha: date)` — context manager que hace que el módulo de períodos vea `fecha` como hoy.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo.py
from datetime import date
from backend.seed_demo import dia_de_cierre, reloj_en


def test_el_cierre_cae_a_principios_del_mes_siguiente():
    # Las expensas de julio se emiten en agosto, no en julio.
    assert dia_de_cierre("2026-07") == date(2026, 8, 1)


def test_el_cierre_de_diciembre_cruza_el_anio():
    assert dia_de_cierre("2026-12") == date(2027, 1, 1)


def test_reloj_en_hace_que_el_modulo_de_periodos_vea_otra_fecha():
    from backend.routers import periodos
    with reloj_en(date(2026, 3, 1)):
        assert periodos.date.today() == date(2026, 3, 1)
    # Y lo restaura al salir.
    assert periodos.date.today() == date.today()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo.py -k "dia_de_cierre or reloj_en" -v`
Expected: FAIL con `ImportError: cannot import name 'dia_de_cierre'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/seed_demo.py
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch


def dia_de_cierre(periodo: str) -> date:
    """Día en que se cierra `periodo` ("YYYY-MM"): el 1 del mes siguiente.

    Una administración liquida el mes vencido a principios del siguiente, así
    que la expensa de julio se emite en agosto.
    """
    anio, mes = (int(x) for x in periodo.split("-"))
    return date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)


@contextmanager
def reloj_en(fecha: date):
    """Hace que el módulo de períodos vea `fecha` como el día de hoy.

    `routers/periodos.py` fecha los movimientos de emisión con `date.today()`
    (línea 145). Como el generador cierra seis períodos en un minuto, sin esto
    los seis quedan fechados el mismo día y el libro de la cuenta corriente se
    lee como fabricado.

    Se parchea el símbolo `date` importado por ese módulo —no `datetime.date`
    global— para no alterar el resto del sistema durante el cierre.
    """
    class _FechaFija(date):
        @classmethod
        def today(cls):
            return fecha

    from backend.routers import periodos
    with patch.object(periodos, "date", _FechaFija):
        yield
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_demo.py -k "dia_de_cierre or reloj_en" -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Conectar el generador**

Envolver la llamada de cierre en el context manager:

```python
        with reloj_en(dia_de_cierre(periodo)):
            api.req("POST", f"/periodos/{periodo}/cerrar", token=admin_token, cid=cid, json={
                "fecha_primer_vencimiento": f1.isoformat(),
                "fecha_segundo_vencimiento": f2.isoformat(),
            }, expect=201)
```

**Importante:** sólo el cierre. Los pagos y los gastos se registran con sus propias fechas explícitas y no dependen del reloj.

- [ ] **Step 6: Verificar sobre la base regenerada**

Run: el comando de regeneración, y después:

```bash
python -c "
import sqlite3
c = sqlite3.connect('demo.db')
q = '''select m.descripcion, m.fecha from movimientos_cuenta m
       join departamentos d on d.id = m.departamento_id
       where d.codigo = 'UF-01A' and m.tipo = 'expensa_emitida' order by m.fecha'''
for fila in c.execute(q): print(fila)
"
```
Expected: seis fechas **distintas**, cada una el día 1 del mes siguiente a su período.

- [ ] **Step 7: Commit**

```bash
git add backend/seed_demo.py tests/test_seed_demo.py
git commit -m "fix(seed): fechar cada emision de expensa en su propio periodo"
```

---

### Task 7: Exportar el dataset a un archivo estático

Con el dataset ya curado, hace falta volcarlo a un JSON con los datos **en la forma exacta en que los devuelve cada endpoint**, para que la demo del navegador (Plan B) lo use como estado inicial.

La clave del diseño: el exportador **no arma los datos a mano**, los pide a la propia API con el `TestClient` que ya usa el generador. Así la forma no puede divergir del contrato.

**Files:**
- Create: `backend/export_demo.py`
- Create: `tests/test_export_demo.py`
- Modify: `backend/seed_demo.py` (llamarlo al final, detrás de un flag)

**Interfaces:**
- Consumes: la base ya poblada por `poblar_demo`.
- Produces: `exportar(api, admin_token, tokens_depto: dict[int, str], cid: int) -> dict` — el diccionario que se serializa.
- Produces: `RUTAS_EXPORTADAS: list[tuple[str, str]]` — pares (rol, path) que se piden a la API.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_demo.py
from backend.export_demo import RUTAS_EXPORTADAS, exportar


class _ApiFalsa:
    """Registra qué se pidió y devuelve un cuerpo reconocible por path."""

    def __init__(self):
        self.pedidos = []

    def req(self, metodo, path, **kwargs):
        self.pedidos.append((metodo, path))

        class _R:
            status_code = 200

            @staticmethod
            def json():
                return [{"path_pedido": path}]

        return _R()


def test_exporta_todas_las_rutas_declaradas():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    paths_pedidos = [p for _, p in api.pedidos]
    for _rol, path in RUTAS_EXPORTADAS:
        assert path in paths_pedidos


def test_el_export_indexa_por_path():
    api = _ApiFalsa()
    datos = exportar(api, "tok-admin", {1: "tok-depto"}, cid=1)
    assert "/departamentos" in datos
    assert datos["/departamentos"] == [{"path_pedido": "/departamentos"}]


def test_incluye_las_rutas_del_recorrido_de_venta():
    # Si alguien saca una de estas del export, la demo del navegador queda
    # sin datos en una pantalla del recorrido.
    paths = {p for _rol, p in RUTAS_EXPORTADAS}
    for imprescindible in [
        "/departamentos", "/expensas", "/gastos", "/comprobantes",
        "/comunicados", "/amenities", "/reservas", "/peticiones",
        "/proveedores", "/periodos", "/reportes/morosos",
    ]:
        assert imprescindible in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_demo.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.export_demo'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/export_demo.py
"""Vuelca el dataset demo a un JSON con la forma que devuelve cada endpoint.

No arma los datos a mano: los pide a la propia API con el mismo TestClient
in-process que usa el generador. Por eso la forma del export no puede
divergir del contrato — si un endpoint cambia su respuesta, el export cambia
con él en la siguiente corrida.
"""
import json
from pathlib import Path

#: (rol, path). El rol decide con qué token se pide: "admin" o "depto".
RUTAS_EXPORTADAS: list[tuple[str, str]] = [
    ("admin", "/departamentos"),
    ("admin", "/expensas"),
    ("admin", "/gastos"),
    ("admin", "/comprobantes"),
    ("admin", "/comunicados"),
    ("admin", "/amenities"),
    ("admin", "/reservas"),
    ("admin", "/peticiones"),
    ("admin", "/trabajos"),
    ("admin", "/proveedores"),
    ("admin", "/periodos"),
    ("admin", "/clases-prorrateo"),
    ("admin", "/cajas"),
    ("admin", "/estado-financiero"),
    ("admin", "/reportes/morosos"),
    ("admin", "/configuracion"),
]


def exportar(api, admin_token: str, tokens_depto: dict[int, str], cid: int) -> dict:
    """Pide cada ruta declarada y devuelve {path: cuerpo}."""
    datos: dict = {}
    for rol, path in RUTAS_EXPORTADAS:
        token = admin_token if rol == "admin" else next(iter(tokens_depto.values()))
        r = api.req("GET", path, token=token, cid=cid)
        datos[path] = r.json()
    return datos


def escribir(datos: dict, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_demo.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Conectar al generador detrás de un flag**

Al final de `backend/seed_demo.py`, cuando se invoca con `--exportar`, escribir el archivo en `frontend/src/demo/dataset.json`:

```python
    if "--exportar" in sys.argv:
        from .export_demo import escribir, exportar
        destino = Path(__file__).parent.parent / "frontend" / "src" / "demo" / "dataset.json"
        datos = exportar(api, admin_token, tokens_depto, cid)
        escribir(datos, destino)
        print(f"dataset exportado a {destino}")
```

**Dejar `datos` en una variable, no pasarlo en línea:** la Task 8 agrega el mapa de PDF a ese mismo diccionario antes de escribirlo definitivamente.

- [ ] **Step 6: Verificar la corrida real**

Run: el comando de regeneración con `--exportar` agregado al final.
Expected: el archivo existe y tiene las 16 claves.

```bash
python -c "
import json
d = json.load(open('frontend/src/demo/dataset.json', encoding='utf-8'))
print(len(d), 'rutas'); print(sorted(d)[:5])
print('expensas:', len(d['/expensas']))
"
```

- [ ] **Step 7: Commit**

```bash
git add backend/export_demo.py tests/test_export_demo.py backend/seed_demo.py
git commit -m "feat(seed): exportar el dataset demo a un archivo estatico"
```

---

### Task 8: Exportar los PDF de boleta del último período

La demo del navegador no puede generar PDF: los arma el backend. La especificación (§3.4) resuelve incluir los PDF **reales** del último período cerrado, uno por unidad, como archivos estáticos. Cuando el propietario toca "ver PDF" se abre el suyo, con su unidad y sus importes.

Se sirven sueltos, **fuera del paquete de la aplicación**: dieciocho boletas pesan más que todo el frontend junto, y así se descarga sólo la que se abre.

**Files:**
- Modify: `backend/export_demo.py`
- Test: `tests/test_export_demo.py`

**Interfaces:**
- Consumes: `exportar` y `escribir` de la Task 7.
- Produces: `exportar_pdfs(api, admin_token, cid, expensas: list[dict], destino: Path) -> dict[int, str]` — devuelve `{expensa_id: nombre_de_archivo}` para que la demo sepa qué archivo abrir.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_demo.py
from pathlib import Path
from backend.export_demo import exportar_pdfs


class _ApiPdf:
    """Devuelve bytes de PDF para cualquier path que termine en /pdf."""

    def req(self, metodo, path, **kwargs):
        class _R:
            status_code = 200
            content = b"%PDF-1.4 contenido de prueba"

        return _R()


def test_exporta_un_pdf_por_expensa(tmp_path):
    expensas = [{"id": 7, "departamento_id": 1}, {"id": 8, "departamento_id": 2}]
    mapa = exportar_pdfs(_ApiPdf(), "tok", 1, expensas, tmp_path)
    assert set(mapa) == {7, 8}
    for expensa_id, nombre in mapa.items():
        assert (tmp_path / nombre).exists()
        assert (tmp_path / nombre).read_bytes().startswith(b"%PDF")


def test_el_nombre_del_pdf_no_expone_datos_del_vecino(tmp_path):
    # El nombre viaja en una URL pública: sólo el id de la expensa.
    expensas = [{"id": 7, "departamento_id": 1}]
    mapa = exportar_pdfs(_ApiPdf(), "tok", 1, expensas, tmp_path)
    assert mapa[7] == "expensa-7.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_demo.py -k pdf -v`
Expected: FAIL con `ImportError: cannot import name 'exportar_pdfs'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/export_demo.py
from pathlib import Path


def exportar_pdfs(api, admin_token: str, cid: int, expensas: list[dict],
                  destino: Path) -> dict[int, str]:
    """Baja el PDF de cada expensa y lo escribe en `destino`.

    Devuelve {expensa_id: nombre de archivo} para que la demo sepa qué abrir.
    El nombre lleva sólo el id de la expensa: viaja en una URL pública y no
    tiene por qué exponer la unidad ni el propietario.
    """
    destino.mkdir(parents=True, exist_ok=True)
    mapa: dict[int, str] = {}
    for expensa in expensas:
        expensa_id = expensa["id"]
        r = api.req("GET", f"/expensas/{expensa_id}/pdf", token=admin_token, cid=cid)
        nombre = f"expensa-{expensa_id}.pdf"
        (destino / nombre).write_bytes(r.content)
        mapa[expensa_id] = nombre
    return mapa
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_demo.py -k pdf -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Conectar al flag de exportación**

En el bloque `--exportar` de `backend/seed_demo.py`, después de escribir el dataset:

```python
        ultimo = meses[-1]
        expensas_ultimas = [e for e in datos["/expensas"] if e["periodo"] == ultimo]
        mapa = exportar_pdfs(
            api, admin_token, cid, expensas_ultimas,
            Path(__file__).parent.parent / "frontend" / "public" / "demo-pdfs",
        )
        datos["_pdfs"] = mapa
        escribir(datos, destino)   # re-escribir con el mapa incluido
        print(f"{len(mapa)} PDFs exportados")
```

`frontend/public/` es el directorio de archivos estáticos de Vite: lo que va ahí se copia tal cual al sitio publicado, sin entrar al paquete de JavaScript. Es exactamente lo que pide §3.4.

- [ ] **Step 6: Verificar la corrida real**

Run: el comando de regeneración con `--exportar`.

```bash
ls frontend/public/demo-pdfs | head -3
python -c "
import json
d = json.load(open('frontend/src/demo/dataset.json', encoding='utf-8'))
print(len(d['_pdfs']), 'pdfs mapeados')
"
```
Expected: 18 archivos y 18 entradas en el mapa.

- [ ] **Step 7: Commit**

```bash
git add backend/export_demo.py tests/test_export_demo.py backend/seed_demo.py
git commit -m "feat(seed): exportar los PDF de boleta del ultimo periodo"
```

---

### Task 9: Verificación final del dataset completo

Las tareas anteriores arreglaron cada defecto por separado. Esta comprueba, sobre una corrida real y completa, que los seis quedaron arreglados a la vez y que no se pisaron entre sí.

**Files:**
- Create: `tests/test_dataset_demo_curado.py`

**Interfaces:**
- Consumes: `demo.db` generada por la corrida completa.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset_demo_curado.py
"""Verificaciones sobre la base demo ya generada.

Se saltean si `demo.db` no existe: no generan la base (tarda ~70 s), sólo la
auditan. Correr primero el comando de regeneración de la cabecera del plan.
"""
import sqlite3
from pathlib import Path

import pytest

DB = Path("demo.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="falta demo.db generada")


@pytest.fixture
def con():
    c = sqlite3.connect(DB)
    yield c
    c.close()


def test_la_caja_no_esta_en_rojo(con):
    (saldo,) = con.execute("select saldo_actual from cajas limit 1").fetchone()
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


def test_las_expensas_no_se_emitieron_todas_el_mismo_dia(con):
    fechas = con.execute("""
        select distinct m.fecha from movimientos_cuenta m
        join departamentos d on d.id = m.departamento_id
        where d.codigo = 'UF-01A' and m.tipo = 'expensa_emitida'
    """).fetchall()
    assert len(fechas) >= 5


def test_cada_gasto_tiene_un_proveedor_plausible(con):
    incoherentes = con.execute("""
        select g.concepto, p.razon_social
        from gastos g join proveedores p on p.id = g.proveedor_id
        where (g.rubro = 'seguros' and p.razon_social not like '%Seguros%')
           or (g.rubro = 'gastos_bancarios' and p.razon_social not like '%Banco%')
           or (g.rubro = 'gastos_administracion' and p.razon_social not like '%Estudio%')
    """).fetchall()
    assert incoherentes == []


def test_los_comprobantes_tienen_imagenes_de_verdad(con):
    rutas = con.execute(
        "select archivo_path from comprobantes where archivo_path is not null limit 5"
    ).fetchall()
    assert rutas, "ningún comprobante tiene archivo"
    for (ruta,) in rutas:
        archivo = Path("." + ruta) if ruta.startswith("/") else Path(ruta)
        assert archivo.exists(), f"falta {archivo}"
        assert archivo.stat().st_size > 2_000, f"{archivo} parece un PNG de 1px"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dataset_demo_curado.py -v`
Expected: los tests fallan (o se saltean si aún no regeneraste la base con todos los arreglos aplicados).

- [ ] **Step 3: Regenerar la base con todos los arreglos**

Run: el comando de regeneración con `--exportar`.
Expected: termina sin error en ~70 s.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dataset_demo_curado.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Correr la suite entera para descartar regresiones**

Run: `pytest -q`
Expected: los 765 tests previos siguen pasando, más los nuevos. **Nota conocida:** `tests/test_amenities.py` tiene la fecha `2026-08-11` escrita a mano y falla por el paso del tiempo — es previo a este plan y ajeno a él (documentado en `docs/superpowers/2026-08-13-verificacion-visual-pendiente.md`).

- [ ] **Step 6: Commit**

```bash
git add tests/test_dataset_demo_curado.py
git commit -m "test(seed): auditoria del dataset demo generado"
```

---

## Verificación manual antes de dar el plan por terminado

Levantar la aplicación contra la base recién generada y mirar con los ojos:

```bash
# terminal 1
uvicorn backend.main:app --port 8000
# terminal 2
cd frontend && npm run dev
```

1. **Gastos**, mes anterior: cada gasto tiene un proveedor que tiene sentido con su concepto.
2. **Cobranzas → Comprobantes**: hay comprobantes en `pendiente_verificacion`, con una imagen que se ve.
3. **Tesorería → Estado financiero**: el total general es positivo.
4. Entrar como **Propietario al día** → Mi cuenta → Movimientos: las expensas emitidas tienen fechas distintas y no hay recargos ni intereses.
5. Entrar como **Propietario moroso**: sí tiene recargos e intereses (el contraste es lo que vende).
