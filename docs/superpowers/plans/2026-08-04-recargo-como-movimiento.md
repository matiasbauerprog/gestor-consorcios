# El recargo por mora como movimiento de cuenta — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el recargo del segundo vencimiento exista en la cuenta corriente, para que el saldo del departamento y el pendiente de sus expensas no puedan divergir.

**Architecture:** Tres pasos. Primero se corrige que `calcular_estado_cuenta` ignore los movimientos posteriores a la fecha consultada — condición necesaria para evaluar de forma estable si una expensa estaba impaga en su vencimiento. Después se agrega un tipo de movimiento `recargo` y un módulo que lo devenga de forma idempotente. Por último se cablea ese devengamiento en las lecturas de la cuenta.

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy 2.0 + SQLite, tests con pytest.

**Origen:** defecto encontrado el 2026-08-04 ejecutando la Task 2 del plan
`2026-08-04-densidad-desktop-y-pendiente-fehaciente.md`. Este plan se ejecuta
**después de la Task 3 y antes de la Task 4** de aquel.

## El problema

El `MovimientoCuenta` de tipo `expensa_emitida` usa **siempre**
`monto_primer_vencimiento` (`backend/routers/periodos.py:186` y
`backend/routers/expensas.py:161`). El recargo del segundo vencimiento no se
convierte en movimiento en ningún momento — ni al cerrar el período. Sólo el
interés punitorio posterior al segundo vencimiento se capitaliza.

Con el fix del plan anterior, el pendiente por expensa incluye el recargo pero
`saldo_total` (que sale de los movimientos) no. Consecuencias reales:

- El saldo de la cuenta y la suma de pendientes difieren de forma permanente
  mientras la expensa esté impaga.
- El reporte de morosos subestima la deuda.
- Si el departamento paga el monto correcto con recargo ($1070 sobre una expensa
  de $1000), el saldo queda en **−$70**: el sistema le muestra un crédito a favor
  que se aplica a la expensa siguiente. En la práctica le devuelve el recargo.

## Las dos reglas de negocio

Decididas por el dueño del producto el 2026-08-04:

1. **Cuándo se gana el recargo:** el día del primer vencimiento. Si a esa fecha la
   expensa tenía saldo, corresponde, y no se revierte aunque el departamento pague
   después. Se evalúa mirando sólo los movimientos con fecha hasta ese día, así el
   resultado es estable y nunca cambia retroactivamente.
2. **Cuándo se emite el movimiento:** de forma perezosa, la primera vez que se lee
   la cuenta corriente después del vencimiento. Idempotente, sin scheduler — el
   mismo patrón que el plan anterior usa para los gastos recurrentes.

## Global Constraints

- Endpoints sólo en `backend/routers/`, modelos en `backend/models.py`, schemas en
  `backend/schemas.py`. SQLAlchemy 2.0 con `Mapped[...]` y `mapped_column`.
- El proyecto convierte `RequestValidationError` a HTTP 400, no 422.
- Tests: `pytest -v` desde la raíz. En este worktree el venv vive en el repo padre:
  `../../.venv/Scripts/python.exe -m pytest -v`.
- Comentarios y docstrings en español, siguiendo el estilo del archivo que se toca.
- La plata se redondea a 2 decimales y se compara contra epsilons de 0.005.
- Commits en español, imperativo, con prefijo `feat:` / `fix:`, y estos dos
  trailers separados del asunto por una línea en blanco:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` y
  `Claude-Session: https://claude.ai/code/session_01AAEuofDrCCy8fFx7ThMobz`.

---

### Task 1: `calcular_estado_cuenta` ignora los movimientos futuros

Hoy la función suma **todos** los movimientos del departamento sin mirar la fecha,
aunque reciba un `hoy`. Consultar el estado a una fecha pasada devuelve un
resultado contaminado con pagos posteriores. Es un bug latente por sí solo, y es
la base de la regla "estaba impaga al primer vencimiento" de la Task 2.

**Files:**
- Modify: `backend/cuenta_corriente.py` (las dos queries dentro de
  `calcular_estado_cuenta`: la de movimientos y la de `ultima_capitalizacion`)
- Test: `tests/test_cuenta_corriente.py`

**Interfaces:**
- Consumes: nada.
- Produces: `calcular_estado_cuenta(db, departamento_id, hoy)` pasa a considerar
  únicamente movimientos con `fecha <= hoy`. Misma firma, mismo tipo de retorno.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_cuenta_corriente.py`. El archivo ya tiene el fixture `depto`
y los helpers `_mov_expensa(db, depto_id, expensa_id, monto, fecha)` y
`_mov_pago(db, depto_id, monto, fecha)`.

```python
def test_un_pago_posterior_a_hoy_no_cancela_la_expensa(db_empty, depto):
    """La foto de la cuenta a una fecha no puede incluir pagos del futuro."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 25))
    db_empty.commit()

    # Al 5 de junio ese pago todavía no ocurrió.
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))
    assert estado.saldo_total == 1000.0
    assert estado.por_expensa[1].monto_pagado == 0.0
    assert estado.por_expensa[1].estado == EstadoExpensa.pendiente

    # Al 30 de junio sí.
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))
    assert estado.por_expensa[1].monto_pagado == 1000.0


def test_una_capitalizacion_posterior_a_hoy_no_recorta_el_interes(db_empty, depto):
    """El interés al 30/06 no puede descontarse por un cierre del 10/07."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=depto.id, fecha=date(2026, 7, 10),
        tipo=TipoMovimiento.interes_punitorio, descripcion="Intereses", monto=99.0,
    ))
    db_empty.commit()

    # 10 días de mora al 30/06: 1070 * 0.001 * 10 = 10.70
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))
    assert estado.por_expensa[1].interes_acumulado == 10.70
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `../../.venv/Scripts/python.exe -m pytest tests/test_cuenta_corriente.py -v -k "posterior"`
Expected: FAIL — el pago del 25/06 y la capitalización del 10/07 se cuentan igual.

- [ ] **Step 3: Implementar**

En `backend/cuenta_corriente.py`, dentro de `calcular_estado_cuenta`, agregar el
filtro de fecha a la query de movimientos:

```python
    movimientos = list(
        db.scalars(
            select(MovimientoCuenta)
            .where(
                MovimientoCuenta.departamento_id == departamento_id,
                # La foto es a `hoy`: un pago de mañana no cancela nada hoy.
                MovimientoCuenta.fecha <= hoy,
            )
            .order_by(MovimientoCuenta.fecha.asc(), MovimientoCuenta.id.asc())
        ).all()
    )
```

Y el mismo filtro a la query de `ultima_capitalizacion`:

```python
    ultima_capitalizacion = db.scalar(
        select(func.max(MovimientoCuenta.fecha)).where(
            MovimientoCuenta.departamento_id == departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.interes_punitorio,
            MovimientoCuenta.fecha <= hoy,
        )
    )
```

- [ ] **Step 4: Correr la suite de cuenta corriente y expensas**

Run: `../../.venv/Scripts/python.exe -m pytest tests/test_cuenta_corriente.py tests/test_expensas.py -v`
Expected: PASS. Ningún test existente depende de contar movimientos futuros; si
alguno falla, revisar si el caso realmente los necesitaba antes de tocar nada.

- [ ] **Step 5: Commit**

```bash
git add backend/cuenta_corriente.py tests/test_cuenta_corriente.py
git commit -m "fix: la cuenta corriente a una fecha ignora los movimientos posteriores"
```

---

### Task 2: Devengamiento del recargo por mora

**Files:**
- Modify: `backend/models.py` (enum `TipoMovimiento` y `TIPOS_DEBITO`, líneas 61-78)
- Create: `backend/recargos.py`
- Test: `tests/test_recargos.py`

**Interfaces:**
- Consumes: `calcular_estado_cuenta` con el filtro de fecha (Task 1).
- Produces:
  - `TipoMovimiento.recargo`, miembro de `TIPOS_DEBITO`.
  - `devengar_recargos(db: Session, departamento_id: int, hoy: date | None = None) -> list[MovimientoCuenta]` en `backend/recargos.py`. Idempotente. **No hace commit.**

**Nota de migración:** no hace falta ninguna. El `Enum` de SQLAlchemy 2.0 usa
`create_constraint=False` por defecto, así que la columna es un VARCHAR sin CHECK
y acepta el valor nuevo sin tocar el esquema.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_recargos.py`:

```python
"""Tests del devengamiento del recargo por mora. Sin HTTP, contra DB en memoria."""
from datetime import date

import pytest

from backend.models import (
    Administracion,
    Consorcio,
    Departamento,
    Expensa,
    MovimientoCuenta,
    TipoMovimiento,
)
from backend.recargos import devengar_recargos


@pytest.fixture
def depto(db_empty):
    db_empty.add(Administracion(
        id=1, razon_social="Admin recargos", cuit="30-11-1",
        email_contacto="a@a.com",
    ))
    db_empty.flush()
    db_empty.add(Consorcio(
        id=1, administracion_id=1, nombre="Recargos test",
        consorcio_domicilio="d", consorcio_cuit="c",
        admin_nombre="n", admin_domicilio="d", admin_email="e@e.com",
        admin_telefono="t", admin_cuit="c", admin_rpa="0",
        admin_situacion_fiscal="M", banco_titular="t", banco_nombre="n",
        banco_numero_cuenta="0", banco_cbu="0" * 22,
    ))
    db_empty.flush()
    d = Departamento(consorcio_id=1, id=1, codigo="1A", descripcion="1° A")
    db_empty.add(d)
    db_empty.commit()
    return d


def _expensa(db, expensa_id, venc1, venc2, monto1=1000.0, monto2=1070.0):
    e = Expensa(consorcio_id=1, id=expensa_id, departamento_id=1,
                periodo="2026-05", monto_primer_vencimiento=monto1,
                fecha_primer_vencimiento=venc1,
                monto_segundo_vencimiento=monto2,
                fecha_segundo_vencimiento=venc2, saldo_anterior=0.0)
    db.add(e)
    db.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=date(2026, 5, 1),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa",
        monto=monto1, expensa_id=expensa_id,
    ))
    db.commit()
    return e


def _pago(db, monto, fecha):
    db.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=1, fecha=fecha,
        tipo=TipoMovimiento.pago_recibido, descripcion="Pago", monto=monto,
    ))
    db.commit()


def test_expensa_impaga_al_vencimiento_devenga_recargo(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))

    nuevos = devengar_recargos(db_empty, 1, hoy=date(2026, 6, 15))
    db_empty.commit()

    assert len(nuevos) == 1
    assert nuevos[0].monto == 70.0
    assert nuevos[0].tipo == TipoMovimiento.recargo
    assert nuevos[0].expensa_id == 1
    # Se fecha el día del vencimiento, que es cuando se ganó.
    assert nuevos[0].fecha == date(2026, 6, 10)


def test_expensa_pagada_antes_del_vencimiento_no_devenga(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _pago(db_empty, 1000.0, date(2026, 6, 5))

    assert devengar_recargos(db_empty, 1, hoy=date(2026, 6, 15)) == []


def test_pagar_despues_del_vencimiento_no_borra_el_recargo(db_empty, depto):
    """El recargo se ganó el 10/06; pagar el 12/06 no lo revierte."""
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    _pago(db_empty, 1000.0, date(2026, 6, 12))

    nuevos = devengar_recargos(db_empty, 1, hoy=date(2026, 6, 15))
    assert len(nuevos) == 1
    assert nuevos[0].monto == 70.0


def test_no_devenga_antes_del_vencimiento(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))

    assert devengar_recargos(db_empty, 1, hoy=date(2026, 6, 10)) == []


def test_es_idempotente(db_empty, depto):
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))

    primera = devengar_recargos(db_empty, 1, hoy=date(2026, 6, 15))
    db_empty.commit()
    segunda = devengar_recargos(db_empty, 1, hoy=date(2026, 6, 20))
    db_empty.commit()

    assert len(primera) == 1
    assert segunda == []


def test_sin_recargo_configurado_no_emite_movimiento(db_empty, depto):
    """monto_segundo == monto_primer: el consorcio no cobra recargo."""
    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20),
             monto1=1000.0, monto2=1000.0)

    assert devengar_recargos(db_empty, 1, hoy=date(2026, 6, 15)) == []


def test_el_saldo_vuelve_a_coincidir_con_el_pendiente(db_empty, depto):
    """Es el punto de todo esto: saldo_total y la suma de pendientes empatan."""
    from backend.cuenta_corriente import calcular_estado_cuenta

    _expensa(db_empty, 1, date(2026, 6, 10), date(2026, 6, 20))
    devengar_recargos(db_empty, 1, hoy=date(2026, 6, 15))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, 1, hoy=date(2026, 6, 15))
    suma_pendientes = round(
        sum(c.monto_pendiente for c in estado.por_expensa.values()), 2
    )
    assert estado.saldo_total == 1070.0
    assert suma_pendientes == 1070.0
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `../../.venv/Scripts/python.exe -m pytest tests/test_recargos.py -v`
Expected: FAIL con `ModuleNotFoundError: backend.recargos`.

- [ ] **Step 3: Implementar**

En `backend/models.py`, agregar el miembro al enum y al frozenset:

```python
class TipoMovimiento(str, enum.Enum):
    expensa_emitida = "expensa_emitida"
    pago_recibido = "pago_recibido"
    interes_punitorio = "interes_punitorio"
    recargo = "recargo"
    nota_debito = "nota_debito"
    nota_credito = "nota_credito"


TIPOS_DEBITO = frozenset({
    TipoMovimiento.expensa_emitida,
    TipoMovimiento.interes_punitorio,
    TipoMovimiento.recargo,
    TipoMovimiento.nota_debito,
})
```

`TIPOS_CREDITO` no cambia.

Crear `backend/recargos.py`:

```python
"""Devengamiento del recargo por mora — el salto del primer al segundo vencimiento.

El movimiento `expensa_emitida` se emite siempre por `monto_primer_vencimiento`,
así que sin este módulo el recargo no existiría en la cuenta corriente: el saldo
quedaría por debajo del pendiente real y un pago con recargo dejaría un crédito
a favor fantasma.

El recargo se gana el día del primer vencimiento. Si a esa fecha la expensa tenía
saldo, corresponde, y no se revierte aunque el departamento pague después — por
eso la evaluación mira la foto de esa fecha y no la de hoy: el resultado es
estable y no cambia retroactivamente.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .cuenta_corriente import calcular_estado_cuenta
from .models import Expensa, MovimientoCuenta, TipoMovimiento


def devengar_recargos(
    db: Session, departamento_id: int, hoy: date | None = None
) -> list[MovimientoCuenta]:
    """Emite el recargo de las expensas del depto que vencieron impagas.

    Idempotente: una expensa que ya tiene su movimiento de recargo se saltea.
    No hace commit — el llamador decide la transacción.
    """
    hoy = hoy or date.today()

    expensas = list(
        db.scalars(
            select(Expensa)
            .where(
                Expensa.departamento_id == departamento_id,
                Expensa.fecha_primer_vencimiento < hoy,
            )
            .order_by(Expensa.fecha_primer_vencimiento.asc(), Expensa.id.asc())
        ).all()
    )
    if not expensas:
        return []

    ya_recargadas = set(
        db.scalars(
            select(MovimientoCuenta.expensa_id).where(
                MovimientoCuenta.departamento_id == departamento_id,
                MovimientoCuenta.tipo == TipoMovimiento.recargo,
            )
        ).all()
    )

    nuevos: list[MovimientoCuenta] = []
    for e in expensas:
        if e.id in ya_recargadas:
            continue
        recargo = round(e.monto_segundo_vencimiento - e.monto_primer_vencimiento, 2)
        if recargo <= 0.005:
            continue
        # La foto al día del vencimiento: calcular_estado_cuenta ignora los
        # movimientos posteriores, así que un pago tardío no borra el recargo.
        foto = calcular_estado_cuenta(
            db, departamento_id, hoy=e.fecha_primer_vencimiento
        )
        calc = foto.por_expensa.get(e.id)
        if calc is None or calc.monto_pendiente <= 0.005:
            continue
        mov = MovimientoCuenta(
            consorcio_id=e.consorcio_id,
            departamento_id=departamento_id,
            fecha=e.fecha_primer_vencimiento,
            tipo=TipoMovimiento.recargo,
            descripcion=f"Recargo por mora — expensa {e.periodo}",
            monto=recargo,
            expensa_id=e.id,
        )
        db.add(mov)
        nuevos.append(mov)

    if nuevos:
        db.flush()
    return nuevos
```

**Por qué el recargo no descuadra el FIFO:** el movimiento es un débito, y el
FIFO sólo consume créditos (`TIPOS_CREDITO`). El recargo ya está adentro del
`monto_exigible` de la expensa, así que sumarlo como movimiento afecta
`saldo_total` y nada más. No hay doble conteo.

- [ ] **Step 4: Correr los tests**

Run: `../../.venv/Scripts/python.exe -m pytest tests/test_recargos.py tests/test_cuenta_corriente.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/recargos.py tests/test_recargos.py
git commit -m "feat: el recargo por mora se emite como movimiento de cuenta"
```

---

### Task 3: Cablear el devengamiento en las lecturas de la cuenta

**Files:**
- Modify: `backend/routers/movimientos.py` (función `_cuenta` y el listado de
  saldos por departamento)
- Modify: `backend/reportes.py` (alrededor de la línea 106, reporte de morosos)
- Modify: `backend/cierre.py` (alrededor de la línea 370, saldo por depto)
- Test: `tests/test_movimientos.py`

**Interfaces:**
- Consumes: `devengar_recargos` (Task 2).
- Produces: nada nuevo — cambia el comportamiento de las lecturas.

**Dónde NO va:** el devengamiento nunca entra adentro de `calcular_estado_cuenta`.
Esa función es pura y está documentada como tal; muchos caminos de sólo lectura
la llaman. La escritura va en la capa de router y de reportes.

- [ ] **Step 1: Escribir el test que falla**

Antes de escribirlo, mirar la forma real de `EstadoCuentaOut` en
`backend/schemas.py` y los helpers de auth de `tests/test_movimientos.py`.
**No inventar campos** — si el schema no expone las expensas con su pendiente,
comparar `saldo_total` contra la suma de `monto_pendiente` que devuelve
`GET /expensas?departamento_id=1`.

El test debe montar un departamento con una expensa vencida e impaga y afirmar
que, al leer la cuenta corriente por HTTP, `saldo_total` coincide con la suma de
los pendientes de sus expensas.

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `../../.venv/Scripts/python.exe -m pytest tests/test_movimientos.py -v -k recargo`
Expected: FAIL — el saldo no incluye el recargo.

- [ ] **Step 3: Implementar**

En `backend/routers/movimientos.py`, importar `from ..recargos import devengar_recargos`
y al principio de `_cuenta`, antes de `calcular_estado_cuenta`:

```python
    # Devengamiento perezoso: leer la cuenta materializa los recargos vencidos.
    # Idempotente, así que repetir la lectura no duplica nada.
    if devengar_recargos(db, departamento_id):
        db.commit()
```

En el listado de saldos por departamento del mismo router (el bucle que llama a
`calcular_estado_cuenta(db, d.id).saldo_total`, alrededor de la línea 97):
devengar para cada depto dentro del bucle acumulando novedades, y hacer **un
solo** `db.commit()` al final si hubo alguna.

En `backend/reportes.py`, alrededor de la línea 106, el mismo patrón antes de
`calcular_estado_cuenta(db, d.id)`.

En `backend/cierre.py`, alrededor de la línea 370, ídem antes de
`calcular_estado_cuenta(db, d.id, hoy=fecha_corte)`, pasando `hoy=fecha_corte`
a `devengar_recargos` para que el preview no devengue recargos futuros.

- [ ] **Step 4: Verificar que el camino unitario no devenga**

`tests/test_cuenta_corriente.py::test_un_pago_cubre_dos_expensas_fifo` no pasa por
los routers, así que no devenga recargos y su `saldo_total` sigue siendo `500.0`.
Correrlo y confirmarlo. Si falla, el devengamiento se coló adentro de
`calcular_estado_cuenta` — eso es un error de cableado, no un assert a actualizar.

- [ ] **Step 5: Correr la suite completa**

Run: `../../.venv/Scripts/python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/routers/movimientos.py backend/reportes.py backend/cierre.py tests/
git commit -m "feat: leer la cuenta corriente devenga los recargos vencidos"
```

---

## Verificación final

- [ ] `pytest -v` en verde.
- [ ] Para un departamento con una expensa vencida e impaga, el saldo de la cuenta
      corriente coincide con la suma de los pendientes de sus expensas.
- [ ] Pagar el monto con recargo deja el saldo en 0, no en negativo.
- [ ] El movimiento de recargo aparece en el listado de la cuenta corriente con su
      descripción, fechado el día del primer vencimiento.
