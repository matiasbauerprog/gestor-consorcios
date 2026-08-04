# Densidad en desktop, pendiente fehaciente y recurrentes automáticos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el monto pendiente de una expensa vencida incluya recargo e intereses, que los gastos recurrentes se carguen solos sin descuadrar la caja, y que las listas largas usen el ancho disponible en tablet y desktop.

**Architecture:** Tres fases independientes. La Fase 1 cambia el cálculo de la cuenta corriente para que el pendiente dependa de la fecha de consulta. La Fase 2 separa "el gasto existe" de "el gasto se pagó" con un flag `pagado` en el modelo `Gasto`, y materializa las plantillas recurrentes de forma perezosa e idempotente al listar. La Fase 3 introduce un componente `ListaResponsive` que renderiza tabla en `>=600px` y delega en tarjetas por debajo, y lo aplica a las pantallas afectadas.

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy 2.0 + SQLite (backend, tests con pytest). React 19 + Vite + react-router-dom 6 (frontend, sin test runner).

**Spec:** `docs/superpowers/specs/2026-08-04-densidad-desktop-y-pendiente-fehaciente-design.md`

## Global Constraints

- Backend: endpoints sólo en `backend/routers/`, modelos en `backend/models.py`, schemas en `backend/schemas.py`. SQLAlchemy 2.0 con `Mapped[...]` y `mapped_column`.
- Backend: dependencias `db: Session = Depends(get_db)` y `_user: CurrentUser = Depends(require_roles(Rol.administracion))` más `cid: int = Depends(get_consorcio_activo)` en todo endpoint de gastos.
- Backend: el proyecto convierte `RequestValidationError` a HTTP 400 (`backend/main.py`), así que las validaciones de schema se assertean con **400, no 422**.
- Tests backend: `pytest -v` desde la raíz. En Windows con venv: `./.venv/Scripts/python.exe -m pytest -v`.
- Frontend: HTML semántico, nada de sopa de divs. Colores **siempre** vía `var(--color-...)`, nunca hex hardcodeado en componentes.
- Frontend: mobile-first. Breakpoints del proyecto: base (≥320px), `@media (min-width: 600px)` tablet, `@media (min-width: 960px)` desktop. Nunca `max-width`.
- Frontend: targets táctiles ≥44px de alto. Usable a 375px de ancho.
- Frontend: no hay test runner. La verificación de cada tarea de la Fase 3 es `npm run lint` + `npm run build` en verde, más inspección visual a 375 / 768 / 1280px.
- Commits: mensaje en español, imperativo, con prefijo `feat:` / `fix:` / `refactor:`.

## Dos desvíos respecto del spec, ya decididos

Ambos simplifican sin cambiar el comportamiento buscado. Están explicados en la tarea donde aparecen.

1. **`fecha_pago` NO pasa a nullable** (Task 5). SQLite no soporta `ALTER COLUMN`, así que volverla nullable exigiría recrear la tabla `gastos` copiando datos, con FKs vivas apuntándole desde `movimientos_caja`. En su lugar `pagado` es la única fuente de verdad y el gasto sin pagar conserva `fecha_pago = día 1 del período` — que es exactamente lo que ya hace `cargar_habituales` hoy (`backend/routers/gastos.py:456`). La UI muestra "—" mientras `pagado` sea falso.
2. **`cierre.py` no comparte una función de intereses: consume el campo ya calculado** (Task 3). El spec proponía extraer la lógica a un helper común. Resulta más simple y más seguro que `calcular_estado_cuenta` calcule el interés una sola vez y que el cierre lea `calc.interes_acumulado`. Elimina la duplicación de raíz en vez de compartirla.

---

# FASE 1 — Pendiente fehaciente

Backend puro. Al terminar la fase, el pendiente de una expensa vencida incluye recargo e intereses, y el cierre sigue sin componer interés sobre interés.

---

### Task 1: Helpers de monto exigible e interés devengado

Dos funciones puras, sin DB, en el módulo de cuenta corriente. Son la base de todo lo demás.

**Files:**
- Modify: `backend/cuenta_corriente.py` (agregar al final, antes de `calcular_estado_cuenta`)
- Test: `tests/test_cuenta_corriente.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `monto_exigible_de(expensa: Expensa, hoy: date) -> float`
  - `interes_devengado(saldo_base: float, fecha_segundo_vencimiento: date, fecha_corte: date, tasa_mensual_pct: float, ultima_capitalizacion: date | None) -> float`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_cuenta_corriente.py`:

```python
from backend.cuenta_corriente import interes_devengado, monto_exigible_de


def _expensa_simple():
    return Expensa(
        consorcio_id=1, id=99, departamento_id=1, periodo="2026-05",
        monto_primer_vencimiento=1000.0,
        fecha_primer_vencimiento=date(2026, 6, 10),
        monto_segundo_vencimiento=1070.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        saldo_anterior=0.0,
    )


def test_exigible_antes_del_primer_vencimiento():
    assert monto_exigible_de(_expensa_simple(), date(2026, 6, 5)) == 1000.0


def test_exigible_el_dia_del_primer_vencimiento_todavia_es_el_primero():
    assert monto_exigible_de(_expensa_simple(), date(2026, 6, 10)) == 1000.0


def test_exigible_pasado_el_primer_vencimiento_es_el_segundo():
    assert monto_exigible_de(_expensa_simple(), date(2026, 6, 11)) == 1070.0


def test_exigible_pasado_el_segundo_vencimiento_sigue_siendo_el_segundo():
    # El interés se suma aparte, no infla el exigible.
    assert monto_exigible_de(_expensa_simple(), date(2026, 7, 30)) == 1070.0


def test_interes_cero_antes_del_segundo_vencimiento():
    assert interes_devengado(
        saldo_base=1070.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 6, 15),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=None,
    ) == 0.0


def test_interes_cero_si_no_hay_saldo():
    assert interes_devengado(
        saldo_base=0.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=None,
    ) == 0.0


def test_interes_proporcional_a_los_dias_de_mora():
    # tasa diaria = 3 / 100 / 30 = 0.001 ; 30 días ; 1000 * 0.001 * 30 = 30.0
    assert interes_devengado(
        saldo_base=1000.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=None,
    ) == 30.0


def test_interes_arranca_desde_la_ultima_capitalizacion():
    # Ya se capitalizó hasta el 10/07: sólo se cobran los 10 días siguientes.
    assert interes_devengado(
        saldo_base=1000.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=date(2026, 7, 10),
    ) == 10.0


def test_interes_cero_si_ya_se_capitalizo_todo():
    assert interes_devengado(
        saldo_base=1000.0,
        fecha_segundo_vencimiento=date(2026, 6, 20),
        fecha_corte=date(2026, 7, 20),
        tasa_mensual_pct=3.0,
        ultima_capitalizacion=date(2026, 7, 20),
    ) == 0.0
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_cuenta_corriente.py -v -k "exigible or interes"`
Expected: FAIL con `ImportError: cannot import name 'interes_devengado'`

- [ ] **Step 3: Implementar los helpers**

En `backend/cuenta_corriente.py`, después de las dataclasses y antes de `calcular_estado_cuenta`:

```python
def monto_exigible_de(expensa: Expensa, hoy: date) -> float:
    """Monto que hay que pagar hoy por esta expensa, sin contar intereses.

    Pasado el primer vencimiento pasa a regir el segundo (que incluye el
    recargo). El día exacto del vencimiento todavía rige el primero.
    """
    if hoy <= expensa.fecha_primer_vencimiento:
        return expensa.monto_primer_vencimiento
    return expensa.monto_segundo_vencimiento


def interes_devengado(
    saldo_base: float,
    fecha_segundo_vencimiento: date,
    fecha_corte: date,
    tasa_mensual_pct: float,
    ultima_capitalizacion: date | None,
) -> float:
    """Interés punitorio sobre `saldo_base` por el tramo de mora todavía NO
    capitalizado.

    El cierre de período capitaliza intereses como movimientos de cuenta. Si
    contáramos la mora desde el segundo vencimiento sin mirar esos movimientos,
    cada cierre volvería a cobrar lo que el anterior ya cobró.
    """
    if saldo_base <= 0.005:
        return 0.0
    if fecha_segundo_vencimiento >= fecha_corte:
        return 0.0
    desde = fecha_segundo_vencimiento
    if ultima_capitalizacion is not None and ultima_capitalizacion > desde:
        desde = ultima_capitalizacion
    dias_mora = (fecha_corte - desde).days
    if dias_mora <= 0:
        return 0.0
    tasa_diaria = tasa_mensual_pct / 100 / 30
    return round(saldo_base * tasa_diaria * dias_mora, 2)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_cuenta_corriente.py -v -k "exigible or interes"`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/cuenta_corriente.py tests/test_cuenta_corriente.py
git commit -m "feat: helpers de monto exigible e interes devengado por fecha"
```

---

### Task 2: `calcular_estado_cuenta` usa el exigible y suma intereses

**Files:**
- Modify: `backend/cuenta_corriente.py:22-28` (dataclass) y `:38-114` (función)
- Test: `tests/test_cuenta_corriente.py`

**Interfaces:**
- Consumes: `monto_exigible_de`, `interes_devengado` (Task 1).
- Produces: `EstadoExpensaCalculado` con los campos `expensa_id`, `monto_total`, `monto_exigible`, `interes_acumulado`, `monto_pagado`, `monto_pendiente`, `estado`. `monto_pendiente == monto_exigible + interes_acumulado - monto_pagado`, con piso en 0.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_cuenta_corriente.py`:

```python
def test_pago_del_primer_vencimiento_tarde_no_cancela_la_expensa(db_empty, depto):
    """El bug crítico: pagar $1000 después del 1er venc dejaba la expensa
    `pagada` y se perdía el recargo de $70."""
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    _mov_pago(db_empty, depto.id, 1000.0, date(2026, 6, 15))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 15))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1070.0
    assert calc.interes_acumulado == 0.0
    assert calc.monto_pendiente == 70.0
    assert calc.estado == EstadoExpensa.parcial


def test_expensa_impaga_pasado_el_segundo_vencimiento_acumula_interes(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.commit()

    # 10 días de mora, tasa default 3% mensual -> 1070 * 0.001 * 10 = 10.70
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1070.0
    assert calc.interes_acumulado == 10.70
    assert calc.monto_pendiente == 1080.70
    assert calc.estado == EstadoExpensa.vencida


def test_interes_no_se_recobra_si_ya_fue_capitalizado(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.add(MovimientoCuenta(
        consorcio_id=1, departamento_id=depto.id, fecha=date(2026, 6, 25),
        tipo=TipoMovimiento.interes_punitorio, descripcion="Intereses",
        monto=5.35,
    ))
    db_empty.commit()

    # Capitalizado hasta el 25/06 -> sólo se devengan los 5 días siguientes.
    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 30))

    assert estado.por_expensa[1].interes_acumulado == 5.35


def test_antes_del_vencimiento_el_exigible_sigue_siendo_el_primero(db_empty, depto):
    e = Expensa(consorcio_id=1, id=1, departamento_id=depto.id, periodo="2026-05",
                monto_primer_vencimiento=1000.0,
                fecha_primer_vencimiento=date(2026, 6, 10),
                monto_segundo_vencimiento=1070.0,
                fecha_segundo_vencimiento=date(2026, 6, 20),
                saldo_anterior=0.0)
    db_empty.add(e)
    _mov_expensa(db_empty, depto.id, e.id, 1000.0, date(2026, 5, 10))
    db_empty.commit()

    estado = calcular_estado_cuenta(db_empty, depto.id, hoy=date(2026, 6, 5))

    calc = estado.por_expensa[1]
    assert calc.monto_exigible == 1000.0
    assert calc.monto_pendiente == 1000.0
    assert calc.estado == EstadoExpensa.pendiente
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_cuenta_corriente.py -v -k "tarde or acumula_interes or capitalizado or exigible_sigue"`
Expected: FAIL con `AttributeError: 'EstadoExpensaCalculado' object has no attribute 'monto_exigible'`

- [ ] **Step 3: Implementar**

En `backend/cuenta_corriente.py`, extender el dataclass (líneas 22-28):

```python
@dataclass
class EstadoExpensaCalculado:
    expensa_id: int
    monto_total: float
    monto_exigible: float
    interes_acumulado: float
    monto_pagado: float
    monto_pendiente: float
    estado: EstadoExpensa
```

Agregar `Consorcio` y `Departamento` al import de `.models` (línea 12-19).

Reemplazar el cuerpo de `calcular_estado_cuenta` desde la línea 59 (`pendientes: dict...`) hasta el `return` final:

```python
    # El techo de cada expensa es lo exigible HOY, no el primer vencimiento:
    # pasado el 1er venc rige el 2do, que incluye el recargo.
    exigibles: dict[int, float] = {e.id: monto_exigible_de(e, hoy) for e in expensas}
    pendientes: dict[int, float] = dict(exigibles)
    pagado_por_expensa: dict[int, float] = {e.id: 0.0 for e in expensas}

    saldo_total = 0.0
    credito_disponible = 0.0

    for m in movimientos:
        if m.tipo in TIPOS_DEBITO:
            saldo_total += m.monto
        else:
            saldo_total -= m.monto
            credito_disponible += m.monto

    saldo_total = round(saldo_total, 2)
    credito_disponible = round(credito_disponible, 2)
    if abs(saldo_total) < 0.005:
        saldo_total = 0.0
    if abs(credito_disponible) < 0.005:
        credito_disponible = 0.0

    # FIFO: el crédito acumulado se aplica a las expensas más viejas.
    for e in expensas:
        if credito_disponible <= 0.005:
            break
        cubierto = min(credito_disponible, pendientes[e.id])
        cubierto = round(cubierto, 2)
        pagado_por_expensa[e.id] = round(pagado_por_expensa[e.id] + cubierto, 2)
        pendientes[e.id] = round(pendientes[e.id] - cubierto, 2)
        credito_disponible = round(credito_disponible - cubierto, 2)

    # Tasa punitoria del consorcio del depto, y hasta dónde ya se capitalizó.
    depto = db.get(Departamento, departamento_id)
    consorcio = db.get(Consorcio, depto.consorcio_id) if depto is not None else None
    tasa_mensual_pct = consorcio.tasa_interes_mensual_pct if consorcio is not None else 0.0

    ultima_capitalizacion = db.scalar(
        select(func.max(MovimientoCuenta.fecha)).where(
            MovimientoCuenta.departamento_id == departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.interes_punitorio,
        )
    )

    por_expensa: dict[int, EstadoExpensaCalculado] = {}
    for e in expensas:
        pagado = round(pagado_por_expensa[e.id], 2)
        saldo = round(pendientes[e.id], 2)
        interes = interes_devengado(
            saldo_base=saldo,
            fecha_segundo_vencimiento=e.fecha_segundo_vencimiento,
            fecha_corte=hoy,
            tasa_mensual_pct=tasa_mensual_pct,
            ultima_capitalizacion=ultima_capitalizacion,
        )
        pendiente = round(saldo + interes, 2)
        if pendiente <= 0.005:
            estado = EstadoExpensa.pagada
            pendiente = 0.0
        elif pagado > 0:
            estado = EstadoExpensa.parcial
        elif e.fecha_primer_vencimiento < hoy:
            estado = EstadoExpensa.vencida
        else:
            estado = EstadoExpensa.pendiente
        por_expensa[e.id] = EstadoExpensaCalculado(
            expensa_id=e.id,
            monto_total=exigibles[e.id],
            monto_exigible=exigibles[e.id],
            interes_acumulado=interes,
            monto_pagado=pagado,
            monto_pendiente=pendiente,
            estado=estado,
        )

    return EstadoCuenta(
        departamento_id=departamento_id,
        saldo_total=saldo_total,
        por_expensa=por_expensa,
    )
```

Agregar `func` al import de `sqlalchemy` (línea 9): `from sqlalchemy import func, select`.

- [ ] **Step 4: Correr toda la suite de cuenta corriente**

Run: `pytest tests/test_cuenta_corriente.py -v`
Expected: PASS. Los tests viejos consultan con `hoy` anterior al primer vencimiento, así que su exigible sigue siendo el primero y no cambian de resultado.

- [ ] **Step 5: Commit**

```bash
git add backend/cuenta_corriente.py tests/test_cuenta_corriente.py
git commit -m "fix: el pendiente de una expensa vencida incluye recargo e intereses"
```

---

### Task 3: El cierre deja de recalcular intereses

`calcular_intereses_al_cierre` duplica hoy la lógica de mora y, peor, usa `monto_pendiente` como base — que ahora ya trae interés adentro. Sin este cambio el cierre compone interés sobre interés.

**Files:**
- Modify: `backend/cierre.py:95-150`
- Test: `tests/test_cierre.py`

**Interfaces:**
- Consumes: `EstadoExpensaCalculado.interes_acumulado` (Task 2).
- Produces: `calcular_intereses_al_cierre(db, consorcio_id, depto_id, fecha_corte) -> tuple[float, str]` — misma firma que hoy.

**Tres tests existentes cambian de valor esperado, y es correcto que cambien.**
Hoy el interés se calcula sobre `monto_primer_vencimiento` ($1000 en los tests).
A partir de Task 2 se calcula sobre el exigible, que pasado el segundo
vencimiento es `monto_segundo_vencimiento` ($1070, con recargo). Es la conducta
buscada: el punitorio corre sobre lo que el depto realmente debe. Los tres son:

| Test | Línea | Esperado hoy | Esperado nuevo |
|---|---|---|---|
| `test_intereses_un_mes_de_mora_calcula_correcto` | `tests/test_cierre.py:226` | `10.0` | `10.70` |
| `test_intereses_no_recobra_lo_ya_cobrado` | `tests/test_cierre.py:256` | `10.0` | `10.70` |
| `test_intereses_usa_tasa_del_consorcio_correcto` | `tests/test_cierre.py:259` | recalcular | base × tasa × días con base = 2° venc |

En los tres: `1070 × 0.001 × 10 = 10.70`. Actualizarlos como parte del Step 3,
agregando en cada uno un comentario que aclare que la base es el segundo
vencimiento.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_cierre.py`. Usa los fixtures `db` y `proveedor` y el patrón
de `Expensa` + `MovimientoCuenta` que ya emplea `test_intereses_un_mes_de_mora_calcula_correcto`
(`tests/test_cierre.py:208-227`):

```python
def test_cierre_cobra_exactamente_el_interes_que_informa_la_cuenta(db, proveedor):
    """Regresión: si el cierre calcula el punitorio sobre un pendiente que ya
    incluye intereses devengados, cada corrida cobra interés del interés. El
    cierre y la cuenta corriente tienen que coincidir siempre."""
    from backend.cuenta_corriente import calcular_estado_cuenta

    expensa = Expensa(consorcio_id=1,
        departamento_id=1, periodo="2026-04",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento=date(2026, 5, 10),
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento=date(2026, 5, 20),
        saldo_anterior=0.0,
    )
    db.add(expensa); db.flush()
    db.add(MovimientoCuenta(consorcio_id=1,
        departamento_id=1, fecha=date(2026, 5, 1),
        tipo=TipoMovimiento.expensa_emitida, descripcion="Expensa 2026-04",
        monto=1000, expensa_id=expensa.id,
    ))
    db.commit()

    monto, _ = calcular_intereses_al_cierre(db, 1, 1, date(2026, 5, 30))
    calc = calcular_estado_cuenta(db, 1, hoy=date(2026, 5, 30)).por_expensa
    interes_informado = round(sum(c.interes_acumulado for c in calc.values()), 2)

    assert monto == interes_informado
    assert monto > 0
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_cierre.py::test_cierre_cobra_exactamente_el_interes_que_informa_la_cuenta -v`
Expected: FAIL — el cierre da `10.0` (calcula sobre `monto_pendiente`, base 1000) y la cuenta corriente informa `10.70` (base 1070).

- [ ] **Step 3: Implementar**

Reemplazar el cuerpo de `calcular_intereses_al_cierre` en `backend/cierre.py` (desde la línea 109, `config = db.get(...)`, hasta el `return` de la línea 150):

```python
    estado = calcular_estado_cuenta(db, depto_id, hoy=fecha_corte)

    intereses_por_expensa: list[tuple[str, float]] = []
    for expensa in db.scalars(
        select(Expensa).where(Expensa.departamento_id == depto_id)
    ).all():
        calc = estado.por_expensa.get(expensa.id)
        if calc is None or calc.interes_acumulado <= 0.001:
            continue
        intereses_por_expensa.append((expensa.periodo, calc.interes_acumulado))

    total = round(sum(m for _, m in intereses_por_expensa), 2)
    if total <= 0:
        return 0.0, ""

    partes = ", ".join(
        f"${m:.2f} por {p}" for p, m in intereses_por_expensa
    )
    descripcion = (
        f"Intereses al {fecha_corte.isoformat()} sobre "
        f"{len(intereses_por_expensa)} expensa(s) vencida(s): {partes}"
    )
    return total, descripcion
```

Actualizar el docstring de la función para reflejar que ahora delega el cálculo en `calcular_estado_cuenta` en vez de recalcularlo.

El parámetro `consorcio_id` queda sin usar dentro del cuerpo. **Mantenerlo** en la firma: hay llamadores que lo pasan posicionalmente y cambiar la firma es ruido fuera de alcance. Agregar `# noqa: ARG001` si el linter se queja.

Quitar los imports que queden huérfanos en `cierre.py` (`Consorcio` sigue usándose en `_calcular_fechas_default`; revisar `func` y `MovimientoCuenta` antes de borrar nada — `MovimientoCuenta` se usa en otras partes del módulo).

- [ ] **Step 4: Correr los tests de cierre y cuenta corriente**

Run: `pytest tests/test_cierre.py tests/test_cuenta_corriente.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/cierre.py tests/test_cierre.py
git commit -m "fix: el cierre consume el interes ya calculado y no lo compone"
```

---

### Task 4: Exponer el desglose en la API de expensas

**Files:**
- Modify: `backend/schemas.py:200-213`
- Modify: `backend/routers/expensas.py:44-45` (y los otros tres sitios que arman `ExpensaOut`)
- Test: `tests/test_expensas.py`

**Interfaces:**
- Consumes: `EstadoExpensaCalculado` (Task 2).
- Produces: `ExpensaOut` con `monto_exigible: float` e `interes_acumulado: float` además de los campos actuales.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_expensas.py`. `client` y `headers_admin` son fixtures de
`tests/conftest.py:457` y `:493`, disponibles en todos los archivos de test:

```python
def test_expensa_out_expone_exigible_e_interes(client, headers_admin):
    r = client.get("/expensas", headers=headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body, "el seed debe dejar al menos una expensa"
    assert "monto_exigible" in body[0]
    assert "interes_acumulado" in body[0]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_expensas.py::test_expensa_out_expone_exigible_e_interes -v`
Expected: FAIL con `KeyError` / assert de `"monto_exigible" in body[0]`

- [ ] **Step 3: Implementar**

En `backend/schemas.py`, dentro de `ExpensaOut`, después de `estado_calculado`:

```python
    monto_exigible: float
    interes_acumulado: float
```

En `backend/routers/expensas.py`, en cada lugar donde se construye el `ExpensaOut` a partir de `calc` (líneas 44-45 y los usos de `calcular_estado_cuenta` en `:92`, `:169`, `:198`, `:231`), agregar:

```python
        monto_exigible=calc.monto_exigible,
        interes_acumulado=calc.interes_acumulado,
```

Buscar todos los sitios con: `grep -n "monto_pendiente=calc" backend/routers/expensas.py`

- [ ] **Step 4: Correr la suite completa del backend**

Run: `pytest -v`
Expected: PASS. Es el primer punto de la Fase 1 donde corre todo junto; si algo se rompió en Tasks 2-3, aparece acá.

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py backend/routers/expensas.py tests/test_expensas.py
git commit -m "feat: ExpensaOut expone monto exigible e interes acumulado"
```

---

### Task 5: Mostrar el desglose en la UI de expensas

Cierra la Fase 1 con el usuario viendo el número correcto. La tabla de desktop llega en la Fase 3; esto arregla la tarjeta que ya existe.

**Files:**
- Modify: `frontend/src/components/TarjetaExpensa.jsx:50-57`

**Interfaces:**
- Consumes: `expensa.monto_exigible`, `expensa.interes_acumulado` (Task 4).
- Produces: nada que consuman otras tareas.

- [ ] **Step 1: Reemplazar el bloque de estado y pendiente**

En `frontend/src/components/TarjetaExpensa.jsx`, reemplazar el `<p>` de las líneas 50-57 por:

```jsx
      <p style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", flexWrap: "wrap" }}>
        <BadgeEstado estado={expensa.estado_calculado} />
        {expensa.monto_pendiente >= 0.5 && (
          <strong>Pendiente {formatearMonto(expensa.monto_pendiente)}</strong>
        )}
      </p>
      {expensa.monto_pendiente >= 0.5 && expensa.interes_acumulado > 0 && (
        <p className="meta">
          Incluye {formatearMonto(expensa.interes_acumulado)} de intereses por mora.
        </p>
      )}
```

El pendiente pasa de `.meta` (gris, secundario) a `<strong>`: es el dato que el usuario vino a buscar.

- [ ] **Step 2: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 3: Verificación manual**

Levantar backend (`uvicorn backend.main:app --reload`) y frontend (`npm run dev`). Entrar como administración a Cobranzas → Expensas. Una expensa pasada de vencimiento debe mostrar el monto con recargo, no el del primer vencimiento.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TarjetaExpensa.jsx
git commit -m "feat: la tarjeta de expensa destaca el pendiente y desglosa intereses"
```

---

# FASE 2 — Recurrentes automáticos

Al terminar la fase, el botón "Cargar recurrentes" no existe, las plantillas se materializan solas al abrir Gastos, y ningún gasto toca la caja hasta que se confirma el pago.

---

### Task 6: Columna `pagado` en el modelo Gasto

**Files:**
- Modify: `backend/models.py:593-628` (clase `Gasto`)
- Modify: `backend/main.py` (nueva función de migración + llamarla en `lifespan`)
- Modify: `backend/schemas.py:610-628` (`GastoOut`)
- Test: `tests/test_gastos.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Gasto.pagado: bool` (default `True`) y `GastoOut.pagado: bool`.

**Nota de diseño:** `fecha_pago` sigue siendo `NOT NULL` — ver "Dos desvíos respecto del spec" arriba. Un gasto con `pagado=False` conserva `fecha_pago = día 1 del período` como valor provisional; `pagado` es la única fuente de verdad.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_gastos.py`:

Los ids son los del seed de `tests/conftest.py`: caja `900`, clase de prorrateo
`500`, proveedor `600`, plantilla recurrente activa `700`. No hacen falta
fixtures nuevos en ninguna tarea de esta fase.

```python
GASTO_VALIDO = {
    "periodo": "2026-07",
    "rubro": "servicios_publicos",
    "clase_prorrateo_id": 500,
    "proveedor_id": 600,
    "concepto": "Luz pasillos julio",
    "monto": 15000.0,
    "forma_pago": "transferencia",
    "caja_id": 900,
    "fecha_pago": "2026-07-10",
}


def test_gasto_creado_a_mano_nace_pagado(client, headers_admin):
    r = client.post("/gastos", json=GASTO_VALIDO, headers=headers_admin)
    assert r.status_code == 201
    assert r.json()["pagado"] is True
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_gastos.py::test_gasto_creado_a_mano_nace_pagado -v`
Expected: FAIL con `KeyError: 'pagado'`

- [ ] **Step 3: Implementar**

En `backend/models.py`, dentro de la clase `Gasto`, después de `fecha_pago` (línea 625):

```python
    # Un gasto puede existir (devengado, prorrateable) sin estar pagado todavía.
    # Sólo al pagarse genera su MovimientoCaja. Default True: los gastos que ya
    # existían fueron todos creados junto con su movimiento.
    pagado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

Verificar que `Boolean` esté importado desde `sqlalchemy` al tope de `models.py`; si no, agregarlo.

En `backend/main.py`, junto a las otras migraciones:

```python
def _migrar_gasto_pagado() -> None:
    """ALTER TABLE idempotente: agrega `pagado` a gastos. Los gastos existentes
    quedan en 1 — todos generaron su MovimientoCaja al crearse."""
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(gastos)"))}
        if cols and "pagado" not in cols:
            conn.execute(text(
                "ALTER TABLE gastos ADD COLUMN pagado BOOLEAN NOT NULL DEFAULT 1"
            ))
```

Y llamarla en `lifespan`, después de `_migrar_administracion_modulos()`:

```python
        _migrar_gasto_pagado()
```

En `backend/schemas.py`, dentro de `GastoOut`, después de `fecha_pago`:

```python
    pagado: bool
```

- [ ] **Step 4: Correr los tests de gastos**

Run: `pytest tests/test_gastos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/main.py backend/schemas.py tests/test_gastos.py
git commit -m "feat: columna pagado en gastos con migracion idempotente"
```

---

### Task 7: Materializar recurrentes sin tocar la caja

**Files:**
- Modify: `backend/routers/gastos.py:440-499` (`cargar_habituales`)
- Test: `tests/test_gastos.py`

**Interfaces:**
- Consumes: `Gasto.pagado` (Task 6).
- Produces: `_materializar_habituales(db: Session, cid: int, periodo: str) -> list[Gasto]` — helper de módulo, idempotente, **no** hace `commit`. Lo consumen Task 8 (GET) y el endpoint POST.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_gastos.py`:

La plantilla recurrente `id=700` viene activa en el seed de `tests/conftest.py:345-357`,
así que no hace falta crear nada.

```python
def test_habituales_se_materializan_sin_pagar_ni_mover_caja(
    client, headers_admin, db_session
):
    from backend.models import MovimientoCaja

    r = client.post(
        "/gastos/cargar-habituales", json={"periodo": "2026-08"}, headers=headers_admin
    )
    assert r.status_code == 201
    creados = r.json()
    assert creados, "la plantilla 700 del seed debe materializarse"
    assert all(g["pagado"] is False for g in creados)

    ids = [g["id"] for g in creados]
    movs = db_session.query(MovimientoCaja).filter(MovimientoCaja.gasto_id.in_(ids)).all()
    assert movs == [], "un gasto sin pagar no debe generar movimiento de caja"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_gastos.py::test_habituales_se_materializan_sin_pagar_ni_mover_caja -v`
Expected: FAIL — hoy los gastos nacen `pagado=True` y con `MovimientoCaja`

- [ ] **Step 3: Implementar**

En `backend/routers/gastos.py`, agregar el helper junto a `_crear_movimiento_para_gasto` (después de la línea 144):

```python
def _materializar_habituales(db: Session, cid: int, periodo: str) -> list[Gasto]:
    """Crea los gastos que faltan para las plantillas activas del período.

    Idempotente: una plantilla que ya generó su gasto en ese período se saltea.
    Los gastos nacen SIN pagar y SIN MovimientoCaja — la plantilla dice cuánto
    se espera gastar, no cuánto se gastó. El egreso de caja lo produce
    POST /gastos/{id}/pagar cuando llega la factura real.

    No hace commit: el llamador decide la transacción.
    """
    anio, mes = map(int, periodo.split("-"))
    fecha_provisoria = date(anio, mes, 1)

    plantillas_activas = db.scalars(
        select(GastoHabitual).where(
            GastoHabitual.consorcio_id == cid,
            GastoHabitual.activa == True,  # noqa: E712
        )
    ).all()

    ids_ya_generadas = set(
        db.scalars(
            select(Gasto.gasto_habitual_id).where(
                Gasto.consorcio_id == cid,
                Gasto.periodo == periodo,
                Gasto.gasto_habitual_id.is_not(None),
            )
        ).all()
    )

    nuevos: list[Gasto] = []
    for plantilla in plantillas_activas:
        if plantilla.id in ids_ya_generadas:
            continue
        gasto = Gasto(
            consorcio_id=cid,
            periodo=periodo,
            rubro=plantilla.rubro,
            clase_prorrateo_id=plantilla.clase_prorrateo_id,
            departamento_id=None,
            proveedor_id=plantilla.proveedor_id,
            concepto=plantilla.concepto,
            monto=plantilla.monto,
            forma_pago=plantilla.forma_pago,
            caja_id=plantilla.caja_id,
            fecha_pago=fecha_provisoria,
            pagado=False,
            gasto_habitual_id=plantilla.id,
        )
        db.add(gasto)
        db.flush()
        nuevos.append(gasto)
    return nuevos
```

Reemplazar el cuerpo de `cargar_habituales` (desde la línea 455 hasta el `return`) por:

```python
    _bloquear_si_periodo_cerrado(db, cid, payload.periodo)
    nuevos = _materializar_habituales(db, cid, payload.periodo)
    db.commit()
    for g in nuevos:
        db.refresh(g)
    return nuevos
```

- [ ] **Step 4: Correr los tests de gastos**

Run: `pytest tests/test_gastos.py -v`
Expected: PASS. Si algún test viejo asumía que los habituales generaban movimiento de caja, actualizarlo: ese comportamiento es justamente el bug que estamos corrigiendo.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/gastos.py tests/test_gastos.py
git commit -m "feat: los recurrentes se materializan sin pagar ni mover caja"
```

---

### Task 8: `GET /gastos` materializa solo

**Files:**
- Modify: `backend/routers/gastos.py:147-180` (`listar_gastos`)
- Test: `tests/test_gastos.py`

**Interfaces:**
- Consumes: `_materializar_habituales` (Task 7), `periodo_cerrado_en` (ya existe en `backend/cierre.py:153`).
- Produces: nada nuevo — cambia el comportamiento de `GET /gastos`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
def test_listar_gastos_materializa_los_recurrentes_del_mes(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    r = client.get(f"/gastos?periodo={periodo}", headers=headers_admin)
    assert r.status_code == 200
    assert any(g["gasto_habitual_id"] == 700 for g in r.json())


def test_listar_gastos_no_materializa_en_periodo_futuro(client, headers_admin):
    r = client.get("/gastos?periodo=2030-01", headers=headers_admin)
    assert r.status_code == 200
    assert r.json() == []


def test_listar_gastos_es_idempotente(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    primera = client.get(f"/gastos?periodo={periodo}", headers=headers_admin).json()
    segunda = client.get(f"/gastos?periodo={periodo}", headers=headers_admin).json()
    assert len(primera) == len(segunda)
```

`date` tiene que estar importado al tope de `tests/test_gastos.py`
(`from datetime import date`); agregarlo si no está.

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_gastos.py -v -k "materializa or idempotente"`
Expected: FAIL — el primero devuelve lista vacía porque nadie materializó nada

- [ ] **Step 3: Implementar**

En `backend/routers/gastos.py`, agregar el helper de guarda junto a los otros privados:

```python
def _corresponde_materializar(db: Session, cid: int, periodo: str | None) -> bool:
    """Sólo se materializan recurrentes en un período consultable y vivo.

    - Período cerrado: ya liquidó sus expensas; agregarle gastos las dejaría
      inconsistentes.
    - Período futuro: navegar con las flechas hasta 2030 devengaría de golpe
      los recurrentes de todos los meses intermedios.
    """
    if periodo is None:
        return False
    if periodo > date.today().strftime("%Y-%m"):
        return False
    return not periodo_cerrado_en(db, cid, periodo)
```

Importar `periodo_cerrado_en` desde `..cierre` al tope del router.

En `listar_gastos`, antes de armar el `stmt` (línea 167):

```python
    # Efecto de escritura deliberado en un GET: materializa las plantillas
    # recurrentes que falten. La alternativa es un scheduler, que el proyecto
    # no tiene. La operación es idempotente, así que repetir el GET no duplica.
    if _corresponde_materializar(db, cid, periodo):
        if _materializar_habituales(db, cid, periodo):
            db.commit()
```

Cambiar el `order_by` de la línea 167 para que los gastos sin pagar queden arriba (son los que piden acción) y no al fondo:

```python
    stmt = (
        select(Gasto)
        .where(Gasto.consorcio_id == cid)
        .order_by(Gasto.pagado.asc(), Gasto.fecha_pago.desc(), Gasto.id.desc())
    )
```

Actualizar el `summary` del endpoint a `"Listar gastos del consorcio (materializa recurrentes pendientes)"`.

- [ ] **Step 4: Correr los tests de gastos**

Run: `pytest tests/test_gastos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/gastos.py tests/test_gastos.py
git commit -m "feat: listar gastos materializa los recurrentes del periodo"
```

---

### Task 9: Confirmar el pago de un gasto

**Files:**
- Modify: `backend/schemas.py` (nuevo `GastoPagar`)
- Modify: `backend/routers/gastos.py` (nuevo endpoint + guarda en PATCH)
- Test: `tests/test_gastos.py`

**Interfaces:**
- Consumes: `Gasto.pagado` (Task 6), `_crear_movimiento_para_gasto`, `_validar_caja_activa`, `_bloquear_si_periodo_cerrado` (ya existen).
- Produces: `POST /gastos/{gasto_id}/pagar` con body `{monto: float, fecha_pago: date, caja_id: int}` → `200` con `GastoOut`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
def _un_gasto_sin_pagar(client, headers_admin, periodo):
    """Materializa los recurrentes del período y devuelve uno sin pagar."""
    gastos = client.get(f"/gastos?periodo={periodo}", headers=headers_admin).json()
    return next(g for g in gastos if g["pagado"] is False)


def test_pagar_gasto_crea_movimiento_de_caja(client, headers_admin, db_session):
    from backend.models import MovimientoCaja

    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)

    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": 63400.0, "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["pagado"] is True
    assert r.json()["monto"] == 63400.0

    movs = (
        db_session.query(MovimientoCaja)
        .filter(MovimientoCaja.gasto_id == sin_pagar["id"])
        .all()
    )
    assert len(movs) == 1
    assert movs[0].monto == 63400.0


def test_pagar_dos_veces_devuelve_409(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)
    body = {"monto": 100.0, "fecha_pago": f"{periodo}-15", "caja_id": 900}

    assert client.post(
        f"/gastos/{sin_pagar['id']}/pagar", json=body, headers=headers_admin
    ).status_code == 200
    assert client.post(
        f"/gastos/{sin_pagar['id']}/pagar", json=body, headers=headers_admin
    ).status_code == 409


def test_pagar_gasto_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/gastos/999999/pagar",
        json={"monto": 100.0, "fecha_pago": "2026-08-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_pagar_gasto_con_monto_cero_devuelve_400(client, headers_admin):
    periodo = date.today().strftime("%Y-%m")
    sin_pagar = _un_gasto_sin_pagar(client, headers_admin, periodo)
    r = client.post(
        f"/gastos/{sin_pagar['id']}/pagar",
        json={"monto": 0, "fecha_pago": f"{periodo}-15", "caja_id": 900},
        headers=headers_admin,
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_gastos.py -v -k "pagar"`
Expected: FAIL con 404/405 — el endpoint no existe

- [ ] **Step 3: Implementar**

En `backend/schemas.py`, junto a los otros schemas de gastos:

```python
class GastoPagar(BaseModel):
    """Confirma el pago real de un gasto devengado. El monto puede diferir del
    de la plantilla: la factura manda."""
    monto: float = Field(..., gt=0)
    fecha_pago: date
    caja_id: int = Field(..., gt=0)
```

En `backend/routers/gastos.py`, después del endpoint PATCH:

```python
@router.post(
    "/{gasto_id}/pagar",
    response_model=GastoOut,
    status_code=status.HTTP_200_OK,
    summary="Confirmar el pago de un gasto devengado",
)
def pagar_gasto(
    gasto_id: int,
    payload: GastoPagar,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_roles(Rol.administracion)),
    cid: int = Depends(get_consorcio_activo),
) -> Gasto:
    gasto = db.get(Gasto, gasto_id)
    if gasto is None or gasto.consorcio_id != cid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto solicitado no existe.",
        )
    if gasto.pagado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El gasto ya figura como pagado.",
        )
    _bloquear_si_periodo_cerrado(db, cid, gasto.periodo)
    _validar_caja_activa(db, cid, payload.caja_id)

    gasto.monto = payload.monto
    gasto.fecha_pago = payload.fecha_pago
    gasto.caja_id = payload.caja_id
    gasto.pagado = True
    db.flush()
    _crear_movimiento_para_gasto(db, gasto)

    db.commit()
    db.refresh(gasto)
    return gasto
```

Importar `GastoPagar` en el bloque de imports de schemas del router.

**Guarda en el PATCH.** En `actualizar_gasto`, reemplazar las líneas 344-345:

```python
    _borrar_movimiento_de_gasto(db, gasto.id)
    _crear_movimiento_para_gasto(db, gasto)
```

por:

```python
    # Un gasto sin pagar no tiene movimiento de caja que rehacer. Recrearlo acá
    # le adelantaría el egreso a un gasto que todavía no se pagó.
    if gasto.pagado:
        _borrar_movimiento_de_gasto(db, gasto.id)
        _crear_movimiento_para_gasto(db, gasto)
```

- [ ] **Step 4: Correr la suite completa del backend**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py backend/routers/gastos.py tests/test_gastos.py
git commit -m "feat: endpoint para confirmar el pago de un gasto devengado"
```

---

### Task 10: Aviso en el cierre por gastos sin pagar

**Files:**
- Modify: `backend/cierre.py:207-232` (bloque de validaciones)
- Test: `tests/test_cierre.py`

**Interfaces:**
- Consumes: `Gasto.pagado` (Task 6).
- Produces: `Validacion(tipo="warning", codigo="gastos_sin_pagar", ...)` en el preview.

- [ ] **Step 1: Escribir el test que falla**

Usa el helper `_gasto` y los fixtures `db`, `proveedor` y `clase_50_50` que ya
existen en `tests/test_cierre.py:82-107`. La clase de prorrateo es necesaria para
no disparar además la validación bloqueante de gastos huérfanos.

```python
def test_preview_avisa_si_hay_gastos_sin_pagar(db, proveedor, clase_50_50):
    g = _gasto("2026-05", 1000, proveedor.id, clase_id=clase_50_50.id)
    g.pagado = False
    db.add(g)
    db.commit()

    preview = calcular_preview_cierre(db, 1, "2026-05")

    codigos = {v.codigo for v in preview.validaciones}
    assert "gastos_sin_pagar" in codigos
    aviso = next(v for v in preview.validaciones if v.codigo == "gastos_sin_pagar")
    assert aviso.tipo == "warning"
    # No debe impedir el cierre: es informativo.
    assert preview.puede_cerrar
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_cierre.py::test_preview_avisa_si_hay_gastos_sin_pagar -v`
Expected: FAIL — `gastos_sin_pagar` no está entre los códigos

- [ ] **Step 3: Implementar**

En `backend/cierre.py`, después del bloque de gastos huérfanos (línea 224) y antes del `if not gastos_periodo:`:

```python
    sin_pagar = [g for g in gastos_periodo if not g.pagado]
    if sin_pagar:
        validaciones.append(Validacion(
            "warning",
            "gastos_sin_pagar",
            f"Hay {len(sin_pagar)} gasto(s) del período todavía sin confirmar "
            f"el pago. Se prorratean igual, con el monto cargado.",
        ))
```

- [ ] **Step 4: Correr los tests de cierre**

Run: `pytest tests/test_cierre.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/cierre.py tests/test_cierre.py
git commit -m "feat: el preview de cierre avisa si quedan gastos sin pagar"
```

---

### Task 11: Sacar el botón "Cargar recurrentes" y agregar el de pagar

Cierra la Fase 2. La tabla llega en la Fase 3; acá la pantalla de gastos sigue en tarjetas.

**Files:**
- Modify: `frontend/src/api/gastos.js`
- Modify: `frontend/src/screens/Gastos.jsx:130-139` (handler), `:207-224` (botones), `:262-296` (tarjetas)
- Create: `frontend/src/components/ModalPagarGasto.jsx`

**Interfaces:**
- Consumes: `POST /gastos/{id}/pagar` (Task 9), `gasto.pagado` (Task 6).
- Produces: `pagarGasto(id, payload)` en `api/gastos.js`; componente `ModalPagarGasto` con props `{ gasto, cajas, onClose, onPagado }`.

- [ ] **Step 1: Agregar el cliente de API**

En `frontend/src/api/gastos.js`, reemplazar `cargarGastosHabituales` por:

```js
export function pagarGasto(id, payload) {
  return apiFetch(`/gastos/${id}/pagar`, { method: "POST", body: payload });
}
```

- [ ] **Step 2: Crear el modal de pago**

`frontend/src/components/ModalPagarGasto.jsx`:

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { pagarGasto } from "../api/gastos";

export default function ModalPagarGasto({ gasto, cajas, onClose, onPagado }) {
  const [monto, setMonto] = useState(String(gasto.monto));
  const [fechaPago, setFechaPago] = useState(
    () => new Date().toISOString().slice(0, 10),
  );
  const [cajaId, setCajaId] = useState(String(gasto.caja_id ?? ""));
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    const r = await pagarGasto(gasto.id, {
      monto: Number(monto),
      fecha_pago: fechaPago,
      caja_id: Number(cajaId),
    });
    setEnviando(false);

    if (r.status === 200) {
      onPagado(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 404) {
      setError("El gasto ya no existe.");
      return;
    }
    if (r.status === 409) {
      setError(r.data?.detail || "El gasto ya figura como pagado.");
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <Modal titulo="Confirmar pago" onClose={onClose}>
      <form onSubmit={onSubmit} noValidate>
        <p className="meta">{gasto.concepto}</p>
        <label>
          Monto real de la factura
          <input
            type="number"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            min="0.01"
            step="0.01"
            required
            autoFocus
          />
        </label>
        <label>
          Fecha de pago
          <input
            type="date"
            value={fechaPago}
            onChange={(e) => setFechaPago(e.target.value)}
            required
          />
        </label>
        <label>
          Caja
          <select
            value={cajaId}
            onChange={(e) => setCajaId(e.target.value)}
            required
          >
            <option value="">— Seleccioná una caja —</option>
            {cajas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
        </label>

        {error && <p role="alert" className="error-banner">{error}</p>}

        <div className="modal-acciones">
          <button
            type="button"
            className="boton-secundario"
            onClick={onClose}
            disabled={enviando}
          >
            Cancelar
          </button>
          <button type="submit" disabled={enviando || !cajaId}>
            {enviando ? "Confirmando…" : "Confirmar pago"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 3: Actualizar la pantalla de Gastos**

En `frontend/src/screens/Gastos.jsx`:

1. Cambiar el import de `../api/gastos`: sacar `cargarGastosHabituales`, no agregar `pagarGasto` (lo usa el modal).
2. Agregar `import ModalPagarGasto from "../components/ModalPagarGasto";`
3. Borrar la función `handleCargarHabituales` completa (líneas 130-139).
4. Borrar el `<button type="button" onClick={handleCargarHabituales}>Cargar recurrentes</button>` (líneas 210-212).
5. Agregar estado: `const [modalPagar, setModalPagar] = useState(null);`
6. En la tarjeta de cada gasto, reemplazar la línea del monto (`:267-269`) por:

```jsx
              <p className="meta">
                ${g.monto.toLocaleString("es-AR")} · {g.periodo} ·{" "}
                {g.pagado ? `pagó ${formatFecha(g.fecha_pago)}` : "sin pagar"}
              </p>
```

7. En `.tarjeta-acciones`, dentro del `else` del período cerrado, antes del botón Editar:

```jsx
                    {!g.pagado && (
                      <button type="button" onClick={() => setModalPagar(g)}>
                        Confirmar pago
                      </button>
                    )}
```

8. Antes del cierre del `<section>`, junto al otro modal:

```jsx
      {modalPagar && (
        <ModalPagarGasto
          gasto={modalPagar}
          cajas={cajas}
          onClose={() => setModalPagar(null)}
          onPagado={() => { setModalPagar(null); recargar(); }}
        />
      )}
```

- [ ] **Step 4: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores. Si el lint marca `cargarGastosHabituales` sin usar, es que quedó un import huérfano.

- [ ] **Step 5: Verificación manual**

Con backend y frontend levantados: entrar a Gastos con al menos una plantilla recurrente activa. Los recurrentes del mes deben aparecer solos, marcados "sin pagar", sin botón "Cargar recurrentes" a la vista. Confirmar el pago de uno y verificar en Tesorería que el saldo de la caja recién baja después de confirmar.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/gastos.js frontend/src/screens/Gastos.jsx frontend/src/components/ModalPagarGasto.jsx
git commit -m "feat: gastos recurrentes automaticos con confirmacion de pago"
```

---

# FASE 3 — Densidad en tablet y desktop

Frontend puro. No hay test runner: cada tarea verifica con `npm run lint && npm run build` más inspección visual a 375 / 768 / 1280px.

---

### Task 12: El primitivo `ListaResponsive`

**Files:**
- Create: `frontend/src/hooks/useBreakpoint.js`
- Create: `frontend/src/components/ListaResponsive.jsx`
- Modify: `frontend/src/index.css` (bloque nuevo al final)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `useMediaQuery(query: string) -> boolean` y `useEsTablet() -> boolean` (≥600px), desde `hooks/useBreakpoint.js`.
  - `<ListaResponsive columnas={...} filas={...} claveFila={fn} renderTarjeta={fn} vacio={string} />` donde `columnas` es `Array<{ clave: string, titulo: string, celda: (fila) => ReactNode, className?: string }>`, `claveFila` es `(fila) => string | number`, y `renderTarjeta` es `(fila) => ReactNode`.

- [ ] **Step 1: Crear el hook**

`frontend/src/hooks/useBreakpoint.js`:

```js
import { useEffect, useState } from "react";

/** Suscribe a una media query y devuelve si matchea. SSR-safe por defecto. */
export function useMediaQuery(query) {
  const [matchea, setMatchea] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = (e) => setMatchea(e.matches);
    setMatchea(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matchea;
}

/** Breakpoint tablet del proyecto (ver .claude/rules/frontend.md). */
export function useEsTablet() {
  return useMediaQuery("(min-width: 600px)");
}
```

- [ ] **Step 2: Crear el componente**

`frontend/src/components/ListaResponsive.jsx`:

```jsx
import { useEsTablet } from "../hooks/useBreakpoint";

/**
 * Una misma colección en dos densidades: tabla de ≥600px para arriba, tarjetas
 * por debajo. Renderiza UN solo árbol — nunca los dos ocultando uno por CSS,
 * que duplicaría el contenido para los lectores de pantalla.
 */
export default function ListaResponsive({
  columnas,
  filas,
  claveFila,
  renderTarjeta,
  vacio = "No hay nada para mostrar.",
}) {
  const esTablet = useEsTablet();

  if (filas.length === 0) {
    return <p className="lista-vacia">{vacio}</p>;
  }

  if (!esTablet) {
    return (
      <ul className="lista-cards">
        {filas.map((fila) => (
          <li key={claveFila(fila)}>{renderTarjeta(fila)}</li>
        ))}
      </ul>
    );
  }

  return (
    <div className="tabla-scroll">
      <table className="tabla-datos">
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c.clave} className={c.className}>{c.titulo}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={claveFila(fila)}>
              {columnas.map((c) => (
                <td key={c.clave} className={c.className}>{c.celda(fila)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Agregar el CSS**

Al final de `frontend/src/index.css`:

```css
/* ---------- ListaResponsive: tabla de ≥600px para arriba ---------- */

.tabla-scroll {
  overflow-x: auto;
  margin-bottom: 1rem;
}

.tabla-datos {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.tabla-datos thead th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  font-size: 0.625rem;
  font-weight: 800;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.tabla-datos tbody tr {
  border-bottom: 1px solid var(--color-border);
}

.tabla-datos tbody tr:hover {
  background: var(--color-bg);
}

.tabla-datos tbody td {
  padding: 0.6rem 0.75rem;
  vertical-align: middle;
}

/* Los importes se leen mejor alineados a la derecha y tabulados. */
.tabla-datos .col-monto {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.tabla-datos .col-acciones {
  text-align: right;
  white-space: nowrap;
}

.lista-vacia {
  color: var(--color-text-muted);
  margin: 1rem 0;
}
```

- [ ] **Step 4: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useBreakpoint.js frontend/src/components/ListaResponsive.jsx frontend/src/index.css
git commit -m "feat: primitivo ListaResponsive con tabla en tablet y tarjeta en mobile"
```

---

### Task 13: Barra de filtros horizontal en tablet

**Files:**
- Modify: `frontend/src/index.css:1740-1761` y el bloque `@media (min-width: 600px)` que arranca en `:1935`

**Interfaces:**
- Consumes: nada.
- Produces: la clase `.filtros-barra` con comportamiento de fila en ≥600px. La usan las Tasks 14, 15 y 16.

- [ ] **Step 1: Agregar el comportamiento de tablet**

Dentro del bloque `@media (min-width: 600px)` de `frontend/src/index.css` (el que arranca en la línea 1935), agregar:

```css
  /* Los filtros dejan de ser una columna que come alto y pasan a una barra.
     Los controles nunca se estiran: ocupan su contenido. */
  .filtros,
  .filtros-barra,
  .filtros-gastos {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 1rem;
  }

  .filtros label,
  .filtros-barra label,
  .filtros-gastos label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.6875rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .filtros-gastos select,
  .filtros-gastos input {
    width: auto;
    align-self: flex-start;
  }
```

- [ ] **Step 2: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 3: Verificación manual**

Abrir Gastos y Comprobantes a 768px y 1280px: los filtros deben verse en una fila, con cada control a su ancho natural. A 375px deben seguir apilados.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: los filtros pasan a barra horizontal desde tablet"
```

---

### Task 14: Expensas en tabla

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx:112-213`

**Interfaces:**
- Consumes: `ListaResponsive` (Task 12), `.filtros-barra` (Task 13), `monto_exigible` / `interes_acumulado` (Task 4).
- Produces: nada.

- [ ] **Step 1: Mover los filtros fuera del header**

En `frontend/src/screens/Expensas.jsx`, reemplazar el `<header className="seccion-header">` completo (líneas 114-144) por:

```jsx
      <header className="seccion-header">
        <h2>Expensas</h2>
      </header>

      {esAdmin && (
        <div className="filtros-barra">
          <SelectorDepartamento
            valor={departamentoSeleccionado}
            onChange={setDepartamentoSeleccionado}
          />
          <label>
            Período
            <input
              type="month"
              value={filtroPeriodo}
              onChange={(e) => setFiltroPeriodo(e.target.value)}
            />
          </label>
          {filtroPeriodo && (
            <button type="button" onClick={() => setFiltroPeriodo("")}>
              Limpiar
            </button>
          )}
          {departamentoSeleccionado !== null && (
            <button type="button" onClick={() => setModalCrearAbierto(true)}>
              + Nueva expensa
            </button>
          )}
        </div>
      )}
```

El "+ Nueva expensa" deja de renderizarse deshabilitado: aparece sólo cuando hay departamento elegido, que es cuando sirve.

- [ ] **Step 2: Reemplazar la lista por ListaResponsive**

Agregar los imports:

```jsx
import ListaResponsive from "../components/ListaResponsive";
import BadgeEstado from "../components/BadgeEstado";
import { formatFecha } from "../utils/fechas";
import { abrirPdfExpensa } from "../api/pdf";
```

Antes del `return`, definir el formateador y las columnas:

```jsx
  function formatearMonto(v) {
    return Number(v).toLocaleString("es-AR", {
      style: "currency",
      currency: "ARS",
      maximumFractionDigits: 0,
    });
  }

  async function handleAbrirPdf(expensa) {
    try {
      await abrirPdfExpensa(expensa.id);
    } catch (err) {
      setErrorAccion(`No se pudo abrir el PDF: ${err.message}`);
    }
  }

  const columnas = [
    { clave: "periodo", titulo: "Período", celda: (e) => e.periodo },
    ...(esAdmin
      ? [{
          clave: "depto",
          titulo: "Departamento",
          celda: (e) => {
            const d = deptoById[e.departamento_id];
            return d ? `${d.codigo} — ${d.descripcion}` : `#${e.departamento_id}`;
          },
        }]
      : []),
    {
      clave: "venc1",
      titulo: "1° venc",
      celda: (e) => `${formatFecha(e.fecha_primer_vencimiento)} · ${formatearMonto(e.monto_primer_vencimiento)}`,
    },
    {
      clave: "venc2",
      titulo: "2° venc",
      celda: (e) => `${formatFecha(e.fecha_segundo_vencimiento)} · ${formatearMonto(e.monto_segundo_vencimiento)}`,
    },
    {
      clave: "estado",
      titulo: "Estado",
      celda: (e) => <BadgeEstado estado={e.estado_calculado} />,
    },
    {
      clave: "pendiente",
      titulo: "Pendiente",
      className: "col-monto",
      celda: (e) =>
        e.monto_pendiente >= 0.5 ? (
          <>
            <strong>{formatearMonto(e.monto_pendiente)}</strong>
            {e.interes_acumulado > 0 && (
              <>
                <br />
                <span className="meta">
                  +{formatearMonto(e.interes_acumulado)} int.
                </span>
              </>
            )}
          </>
        ) : (
          "—"
        ),
    },
    {
      clave: "acciones",
      titulo: "",
      className: "col-acciones",
      celda: (e) => (
        <>
          <button type="button" onClick={() => setModalComprobantes(e)}>
            Comprobantes
          </button>
          <button type="button" onClick={() => handleAbrirPdf(e)}>
            PDF
          </button>
          {esAdmin && (
            <button
              type="button"
              className="boton-peligro"
              onClick={() => setModalEliminar(e)}
            >
              Eliminar
            </button>
          )}
        </>
      ),
    },
  ];
```

Reemplazar el `<ul className="lista-expensas">` completo (líneas 192-205) por:

```jsx
      {!cargando && (
        <ListaResponsive
          columnas={columnas}
          filas={expensasFiltradas}
          claveFila={(e) => e.id}
          vacio="No hay expensas para mostrar."
          renderTarjeta={(e) => (
            <TarjetaExpensa
              expensa={e}
              esAdmin={esAdmin}
              depto={deptoById[e.departamento_id]}
              token={token}
              onEliminar={setModalEliminar}
              onVerComprobantes={setModalComprobantes}
            />
          )}
        />
      )}
```

El guard `!cargando` importa: sin él, mientras carga se verían a la vez
"Cargando…" y "No hay expensas para mostrar", porque `filas` todavía está vacío.

Borrar el `{!cargando && !errorCarga && expensas.length === 0 && (<p>No hay expensas para mostrar.</p>)}` de las líneas 157-159: ahora lo cubre la prop `vacio`.

- [ ] **Step 3: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 4: Verificación manual**

A 375px: tarjetas, idénticas a antes. A 768px y 1280px: tabla, con el pendiente alineado a la derecha. Verificar que el botón "+ Nueva expensa" aparece sólo con departamento elegido.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Expensas.jsx
git commit -m "feat: expensas en tabla desde tablet y filtros en barra"
```

---

### Task 15: Comprobantes en tabla

**Files:**
- Modify: `frontend/src/screens/Comprobantes.jsx:180-255`
- Modify: `frontend/src/index.css` (miniatura)

**Interfaces:**
- Consumes: `ListaResponsive` (Task 12), `.filtros-barra` (Task 13).
- Produces: nada.

- [ ] **Step 1: Agregar la clase de miniatura**

Al final de `frontend/src/index.css`:

```css
/* La imagen inline de 240px hace la lista interminable; en tabla va miniatura. */
.comprobante-thumb {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  cursor: zoom-in;
}
```

- [ ] **Step 2: Reemplazar la lista**

En `frontend/src/screens/Comprobantes.jsx`, agregar `import ListaResponsive from "../components/ListaResponsive";` y cambiar `<div className="filtros">` por `<div className="filtros-barra">`.

Antes del `return`, definir las columnas:

```jsx
  const columnas = [
    { clave: "fecha", titulo: "Fecha", celda: (c) => formatFecha(c.fecha_pago) },
    ...(esAdmin
      ? [{
          clave: "depto",
          titulo: "Departamento",
          celda: (c) => c.departamento_codigo || (c.departamento_id ? `#${c.departamento_id}` : "—"),
        }]
      : []),
    {
      clave: "monto",
      titulo: "Monto",
      className: "col-monto",
      celda: (c) => `$${c.monto.toLocaleString("es-AR")}`,
    },
    {
      clave: "estado",
      titulo: "Estado",
      celda: (c) => <BadgeEstado estado={c.estado} />,
    },
    {
      clave: "archivo",
      titulo: "Comprobante",
      celda: (c) =>
        c.archivo_path ? (
          <a href={`${API_BASE}${c.archivo_path}`} target="_blank" rel="noopener noreferrer">
            <img
              src={`${API_BASE}${c.archivo_path}`}
              alt={`Comprobante del ${formatFecha(c.fecha_pago)}`}
              className="comprobante-thumb"
            />
          </a>
        ) : (
          "—"
        ),
    },
    {
      clave: "acciones",
      titulo: "",
      className: "col-acciones",
      celda: (c) => (
        <>
          {esAdmin && c.estado === "pendiente_verificacion" && (
            <>
              <button
                type="button"
                onClick={() => handleAprobarClick(c)}
                disabled={accionandoId === c.id || cargandoCajas}
              >
                {accionandoId === c.id ? "…" : "Aprobar"}
              </button>
              <button
                type="button"
                className="boton-borrar"
                onClick={() => handleDecision(c.id, "rechazado")}
                disabled={accionandoId === c.id}
              >
                {accionandoId === c.id ? "…" : "Rechazar"}
              </button>
            </>
          )}
          <button type="button" className="boton-peligro" onClick={() => setModalEliminar(c)}>
            Eliminar
          </button>
        </>
      ),
    },
  ];
```

Reemplazar el `<ul className="lista-comprobantes">` completo (líneas 207-255) por
el bloque siguiente. El guard `!cargando` evita que se vean a la vez "Cargando…"
y el mensaje de lista vacía:

```jsx
      {!cargando && (
      <ListaResponsive
        columnas={columnas}
        filas={comprobantes}
        claveFila={(c) => c.id}
        vacio="No hay comprobantes con esos filtros."
        renderTarjeta={(c) => (
          <Tarjeta>
            <h3>${c.monto.toLocaleString("es-AR")}</h3>
            <p className="meta">Pagado {formatFecha(c.fecha_pago)}</p>
            {c.departamento_id && (
              <p className="meta">
                Departamento: {c.departamento_codigo || `#${c.departamento_id}`}
              </p>
            )}
            <p><BadgeEstado estado={c.estado} /></p>
            {c.archivo_path && (
              <a href={`${API_BASE}${c.archivo_path}`} target="_blank" rel="noopener noreferrer">
                <img
                  src={`${API_BASE}${c.archivo_path}`}
                  alt="Comprobante"
                  className="comprobante-img"
                />
              </a>
            )}
            <div className="tarjeta-acciones">
              {esAdmin && c.estado === "pendiente_verificacion" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAprobarClick(c)}
                    disabled={accionandoId === c.id || cargandoCajas}
                  >
                    {accionandoId === c.id ? "…" : "Aprobar"}
                  </button>
                  <button
                    type="button"
                    className="boton-borrar"
                    onClick={() => handleDecision(c.id, "rechazado")}
                    disabled={accionandoId === c.id}
                  >
                    {accionandoId === c.id ? "…" : "Rechazar"}
                  </button>
                </>
              )}
              <button type="button" className="boton-peligro" onClick={() => setModalEliminar(c)}>
                Eliminar
              </button>
            </div>
          </Tarjeta>
        )}
      />
      )}
```

Borrar el `{!cargando && !errorCarga && comprobantes.length === 0 && ...}` de las líneas 203-205.

- [ ] **Step 3: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 4: Verificación manual**

A 375px: tarjetas con la imagen grande, como antes. A 1280px: tabla con miniaturas de 44px que abren el archivo completo al hacer click.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Comprobantes.jsx frontend/src/index.css
git commit -m "feat: comprobantes en tabla desde tablet con miniatura"
```

---

### Task 16: Gastos en tabla

**Files:**
- Modify: `frontend/src/screens/Gastos.jsx:227-296`

**Interfaces:**
- Consumes: `ListaResponsive` (Task 12), `gasto.pagado` y `ModalPagarGasto` (Task 11).
- Produces: nada.

- [ ] **Step 1: Reemplazar la lista**

En `frontend/src/screens/Gastos.jsx`, agregar `import ListaResponsive from "../components/ListaResponsive";`.

Antes del `return`, definir las columnas:

```jsx
  const columnas = [
    { clave: "concepto", titulo: "Concepto", celda: (g) => g.concepto },
    { clave: "rubro", titulo: "Rubro", celda: (g) => labelRubro(g.rubro) },
    { clave: "proveedor", titulo: "Proveedor", celda: (g) => proveedorPorId(g.proveedor_id) },
    {
      clave: "destino",
      titulo: "Clase / Depto",
      celda: (g) =>
        g.clase_prorrateo_id !== null
          ? `Clase ${clasePorId(g.clase_prorrateo_id)}`
          : `Depto ${deptoPorId(g.departamento_id)}`,
    },
    { clave: "caja", titulo: "Caja", celda: (g) => cajaPorId(g.caja_id) },
    {
      clave: "monto",
      titulo: "Monto",
      className: "col-monto",
      celda: (g) => `$${g.monto.toLocaleString("es-AR")}`,
    },
    {
      clave: "pago",
      titulo: "Pago",
      celda: (g) =>
        g.pagado ? (
          formatFecha(g.fecha_pago)
        ) : cerrados.has(g.periodo) ? (
          <span className="meta">Sin pagar</span>
        ) : (
          <button type="button" onClick={() => setModalPagar(g)}>
            Confirmar
          </button>
        ),
    },
    {
      clave: "acciones",
      titulo: "",
      className: "col-acciones",
      celda: (g) =>
        cerrados.has(g.periodo) ? (
          <span title="Período cerrado — no editable">🔒</span>
        ) : (
          <>
            <button type="button" onClick={() => setModal({ tipo: "editar", gasto: g })}>
              Editar
            </button>
            <button type="button" className="boton-borrar" onClick={() => handleBorrar(g)}>
              Eliminar
            </button>
          </>
        ),
    },
  ];
```

Reemplazar el `<ul className="lista-gastos">` completo (líneas 262-296) por el
bloque siguiente. El guard `!cargando` evita que se vean a la vez "Cargando…" y
el mensaje de lista vacía:

```jsx
      {!cargando && (
      <ListaResponsive
        columnas={columnas}
        filas={gastos}
        claveFila={(g) => g.id}
        vacio="No hay gastos con esos filtros."
        renderTarjeta={(g) => (
          <Tarjeta>
            <h3>{labelRubro(g.rubro)} · {g.concepto}</h3>
            <p className="meta">
              ${g.monto.toLocaleString("es-AR")} · {g.periodo} ·{" "}
              {g.pagado ? `pagó ${formatFecha(g.fecha_pago)}` : "sin pagar"}
            </p>
            <p className="meta">Proveedor: {proveedorPorId(g.proveedor_id)}</p>
            <p className="meta">
              {g.clase_prorrateo_id !== null
                ? <>Clase {clasePorId(g.clase_prorrateo_id)}</>
                : <>Particular a {deptoPorId(g.departamento_id)}</>}
              {g.cuota_actual && <> · Cuota {g.cuota_actual}/{g.cuota_total}</>}
              {g.gasto_habitual_id && <> · Recurrente</>}
            </p>
            <p className="meta">Caja: {cajaPorId(g.caja_id)}</p>
            <div className="tarjeta-acciones">
              {cerrados.has(g.periodo) ? (
                <span title="Período cerrado — no editable">🔒</span>
              ) : (
                <>
                  {!g.pagado && (
                    <button type="button" onClick={() => setModalPagar(g)}>
                      Confirmar pago
                    </button>
                  )}
                  <button type="button" onClick={() => setModal({ tipo: "editar", gasto: g })}>
                    Editar
                  </button>
                  <button type="button" className="boton-borrar" onClick={() => handleBorrar(g)}>
                    Eliminar
                  </button>
                </>
              )}
            </div>
          </Tarjeta>
        )}
      />
      )}
```

Borrar el `{!cargando && gastos.length === 0 && <p>No hay gastos con esos filtros.</p>}` de la línea 260.

- [ ] **Step 2: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 3: Verificación manual**

A 1280px: tabla con la columna Pago mostrando "Confirmar" en los recurrentes sin pagar y la fecha en los pagados. A 375px: tarjetas.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/screens/Gastos.jsx
git commit -m "feat: gastos en tabla desde tablet con columna de pago"
```

---

### Task 17: Reservas a dos columnas en desktop

**Files:**
- Modify: `frontend/src/screens/Reservas.jsx:149-309`
- Modify: `frontend/src/index.css` (bloque nuevo al final)

**Interfaces:**
- Consumes: `ListaResponsive` (Task 12).
- Produces: nada.

- [ ] **Step 1: Agregar el CSS del grid**

Al final de `frontend/src/index.css`:

```css
/* ---------- Reservas: dos columnas en desktop ---------- */

.reservas-grid {
  display: grid;
  gap: 1.5rem;
}

@media (min-width: 960px) {
  .reservas-grid {
    /* Izquierda: reservar (ancho fijo, es un formulario).
       Derecha: consultar (elástica, son listas). */
    grid-template-columns: minmax(280px, 380px) 1fr;
    align-items: start;
  }
}
```

- [ ] **Step 2: Envolver el contenido en el grid**

En `frontend/src/screens/Reservas.jsx`, después del `<section className="filtros">` del selector de amenity y los mensajes de info/error, envolver el resto en el grid. La estructura pasa a ser:

```jsx
      <div className="reservas-grid">
        <div className="reservas-col-form">
          {/* banner-politicas + form-reserva, tal como están hoy */}
        </div>
        <div className="reservas-col-listas">
          {/* próximas reservas + mis reservas */}
        </div>
      </div>
```

Mover el `<section className={...banner-politicas...}>` (líneas 172-207) y el `<form className="form-reserva">` (líneas 209-254) dentro de `.reservas-col-form`, sin cambiarles nada.

- [ ] **Step 3: Pasar las listas a ListaResponsive**

Agregar `import ListaResponsive from "../components/ListaResponsive";`.

Reemplazar la sección "Próximas reservas" (líneas 256-272) por:

```jsx
          <section>
            <h3>Próximas reservas (todos los deptos)</h3>
            <ListaResponsive
              columnas={[
                { clave: "inicio", titulo: "Desde", celda: (r) => fmtFecha(r.inicio) },
                { clave: "fin", titulo: "Hasta", celda: (r) => fmtFecha(r.fin) },
                { clave: "usuario", titulo: "Depto", celda: (r) => `#${r.usuario_id}` },
              ]}
              filas={proximasDelAmenity}
              claveFila={(r) => r.id}
              vacio="Sin próximas reservas."
              renderTarjeta={(r) => (
                <article className="tarjeta">
                  <h4>{fmtFecha(r.inicio)} → {fmtFecha(r.fin)}</h4>
                  <p>Depto del usuario #{r.usuario_id}</p>
                </article>
              )}
            />
          </section>
```

Reemplazar la sección "Mis reservas" (líneas 274-307) por:

```jsx
          {esDepto && (
            <section>
              <h3>Mis reservas</h3>
              <ListaResponsive
                columnas={[
                  { clave: "inicio", titulo: "Desde", celda: (r) => fmtFecha(r.inicio) },
                  { clave: "fin", titulo: "Hasta", celda: (r) => fmtFecha(r.fin) },
                  {
                    clave: "estado",
                    titulo: "Estado",
                    celda: (r) => `${r.estado}${r.movimiento_cuenta_id ? " — con cargo" : ""}`,
                  },
                  {
                    clave: "acciones",
                    titulo: "",
                    className: "col-acciones",
                    celda: (r) =>
                      r.estado === "confirmada" && new Date(r.inicio) > ahora ? (
                        <button type="button" onClick={() => handleCancelar(r)}>
                          Cancelar
                        </button>
                      ) : null,
                  },
                ]}
                filas={misReservas}
                claveFila={(r) => r.id}
                vacio="No tenés reservas."
                renderTarjeta={(r) => (
                  <article className={`tarjeta${r.estado === "confirmada" ? "" : " cancelada"}`}>
                    <h4>{fmtFecha(r.inicio)} → {fmtFecha(r.fin)}</h4>
                    <p>
                      Estado: {r.estado}
                      {r.movimiento_cuenta_id ? " — con cargo" : ""}
                    </p>
                    {r.estado === "confirmada" && new Date(r.inicio) > ahora && (
                      <button type="button" onClick={() => handleCancelar(r)}>
                        Cancelar
                      </button>
                    )}
                  </article>
                )}
              />
            </section>
          )}
```

- [ ] **Step 4: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 5: Verificación manual**

A 1280px: formulario a la izquierda, listas a la derecha, sin bandas vacías a lo ancho. A 375px y 768px: todo apilado en el orden actual.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/Reservas.jsx frontend/src/index.css
git commit -m "feat: reservas a dos columnas en desktop con listas en tabla"
```

---

### Task 18: Amenities en grid

Se mantiene el formato tarjeta: cada amenity es una ficha de configuración con cinco políticas, no una fila comparable.

**Files:**
- Modify: `frontend/src/index.css` (bloque nuevo al final)
- Modify: `frontend/src/screens/Amenities.jsx:51`

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: Agregar el CSS**

Al final de `frontend/src/index.css`:

```css
/* ---------- Amenities: fichas en grid desde tablet ---------- */

.grid-fichas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr;
}

@media (min-width: 600px) {
  .grid-fichas {
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  }
}
```

- [ ] **Step 2: Cambiar la clase de la lista**

En `frontend/src/screens/Amenities.jsx`, línea 51, cambiar `<ul className="lista-cards">` por `<ul className="grid-fichas">`.

El `<li className="vacio">` del caso sin amenities queda dentro del grid ocupando una celda, que es correcto.

- [ ] **Step 3: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 4: Verificación manual**

A 1280px: las fichas se acomodan en varias columnas. A 375px: una sola columna.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css frontend/src/screens/Amenities.jsx
git commit -m "feat: amenities en grid de fichas desde tablet"
```

---

### Task 19: Tabs de Cobranzas sin título duplicado ni aspecto de botón

**Files:**
- Modify: `frontend/src/index.css:2338-2380`
- Modify: `frontend/src/screens/Expensas.jsx` y `frontend/src/screens/Comprobantes.jsx` (prop nueva)
- Modify: `frontend/src/screens/Cobranzas.jsx:39-41`

**Interfaces:**
- Consumes: nada.
- Produces: prop `embebida` (bool, default `false`) en `Expensas` y `Comprobantes`; cuando es `true` no renderizan su `<header className="seccion-header">`.

- [ ] **Step 1: Rehacer el CSS de las tabs**

En `frontend/src/index.css`, reemplazar el bloque `.tabs-panel` / `.tab-panel` (líneas 2340-2380) por:

```css
.tabs-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  margin: 0 0 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.tab-panel {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  /* Área táctil por padding, no por min-height: el bloque queda liviano
     pero el target sigue arriba de 44px. */
  padding: 0.75em 0.15em;
  margin-bottom: -1px;
  font-family: inherit;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text-muted);
  cursor: pointer;
}

.tab-panel:hover:not(:disabled) {
  background: transparent;
  color: var(--color-text);
}

.tab-panel:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.tab-panel.activo {
  background: transparent;
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 700;
}
```

`.tab-panel` ya figura en las dos listas de exclusión de estilo de botón (`index.css:175` y `:199`), así que no hereda el tratamiento de CTA. No hace falta tocar esas listas.

- [ ] **Step 2: Agregar la prop `embebida`**

En `frontend/src/screens/Expensas.jsx`, cambiar la firma:

```jsx
export default function Expensas({ embebida = false }) {
```

y envolver el header:

```jsx
      {!embebida && (
        <header className="seccion-header">
          <h2>Expensas</h2>
        </header>
      )}
```

Hacer lo mismo en `frontend/src/screens/Comprobantes.jsx` (`export default function Comprobantes({ embebida = false })` y envolver su `<header className="seccion-header">` de la línea 182).

- [ ] **Step 3: Pasar la prop desde Cobranzas**

En `frontend/src/screens/Cobranzas.jsx`, líneas 39-41:

```jsx
      {tabActivo === "expensas" && <Expensas embebida />}
      {tabActivo === "comprobantes" && <Comprobantes embebida />}
      {tabActivo === "cierres" && <Periodos />}
```

- [ ] **Step 4: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 5: Verificación manual**

En Cobranzas: un solo "Cobranzas" arriba, tabs subrayadas sin caja, sin segundo título debajo. A 375px las tres tabs deben entrar sin verse como bloque pesado. Verificar que Expensas y Comprobantes siguen mostrando su título cuando se entra por su ruta directa (si existe en el router).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/src/screens/Cobranzas.jsx frontend/src/screens/Expensas.jsx frontend/src/screens/Comprobantes.jsx
git commit -m "feat: tabs subrayadas en cobranzas sin titulo duplicado"
```

---

### Task 20: Contraste del nombre del consorcio en el header

**Files:**
- Modify: `frontend/src/index.css:2392-2411`

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: Corregir los colores**

El botón hereda colores pensados para fondo claro pero vive sobre `.app-header`, cuyo fondo es `var(--color-modulo)` (`index.css:422-423`). Reemplazar la regla `.selector-consorcio-boton` (líneas 2392-2404) por:

```css
/* Vive dentro de .app-header, cuyo fondo es var(--color-modulo) — un color
   saturado. Hereda el mismo tratamiento blanco que .hamburguesa y
   .avatar-boton; con var(--color-text) el nombre quedaba negro e ilegible. */
.selector-consorcio-boton {
  background: transparent;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.35);
  padding: 0.4em 0.7em;
  min-height: 44px;
  font-size: 0.8125rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 200px;
}

.selector-consorcio-boton:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.6);
}
```

El `#fff` y los `rgba` blancos son intencionales y quedan fuera de la paleta de variables, igual que en `.hamburguesa` (`:477`) y `.app-modulo-label` (`:452`): son un contraste sobre el color de módulo, que ya es la variable.

**Importante:** la lista desplegable (`.selector-consorcio-lista`, `:2413`) NO cambia — está sobre `var(--color-bg)`, fondo claro, y sus ítems ya usan `var(--color-text)` correctamente.

- [ ] **Step 2: Verificar lint y build**

Run: `cd frontend && npm run lint && npm run build`
Expected: sin errores

- [ ] **Step 3: Verificación manual**

Hace falta un usuario con **dos o más consorcios**: con uno solo el selector no se renderiza (`SelectorConsorcio.jsx:21`). A ≥960px el nombre del edificio debe leerse blanco sobre el color del módulo. Navegar entre módulos para verificar el contraste en los seis colores de la paleta, y abrir el desplegable para confirmar que la lista sigue legible.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "fix: el nombre del consorcio se lee sobre el color del header"
```

---

## Verificación final

Después de la Task 20:

- [ ] `pytest -v` desde la raíz, en verde.
- [ ] `cd frontend && npm run lint && npm run build`, en verde.
- [ ] Recorrer Expensas, Comprobantes, Gastos, Reservas y Amenities a 375px, 768px y 1280px.
- [ ] Con un usuario multi-consorcio: nombre legible en el header, en los seis colores de módulo.
- [ ] Flujo completo de recurrentes: abrir Gastos del mes → aparecen sin pagar → confirmar uno con monto distinto al de la plantilla → verificar en Tesorería que el saldo de la caja bajó por el monto real.
- [ ] Flujo de expensa vencida: una expensa pasada del primer vencimiento muestra el monto con recargo, y pagar el monto viejo la deja `parcial`, no `pagada`.
