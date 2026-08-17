# Demo en el navegador, parte 2: los dos circuitos vivos — Plan B2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que en la demo se pueda presentar un pago y aprobarlo viendo bajar la deuda, y cargar un gasto y cerrar el mes viéndolo repartido en las expensas — todo sin backend.

**Architecture:** El sustituto del navegador pasa de sólo leer a también escribir. Se portan al navegador las dos piezas de cálculo más chicas y estables del backend —el reparto por coeficiente y la imputación de pagos por antigüedad—, y se verifican contra los saldos que calculó el backend real al generar el dataset.

**Tech Stack:** React 18 · Vite · vitest. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-08-16-demo-sin-backend-design.md` (§2.1, §5)

**Depende de:** Plan B1 (`docs/superpowers/plans/2026-08-17-demo-navegador-lectura.md`), ya ejecutado. El sustituto, el estado y el desplazamiento de fechas existen y funcionan.

**Alcance de ESTE plan:** los dos circuitos y el cálculo que los sostiene. El cambiador de rol (§2.4), las secciones marcadas (§2.2), el aviso superior con su botón de reinicio (§8), los arreglos de interfaz del tablero en cero (§3.2.4) y el despliegue (§7) son el Plan B3.

## Global Constraints

- **No se toca ninguna pantalla.** El trabajo es en `frontend/src/demo/`. Si una pantalla necesitara cambios, es señal de que el sustituto no respeta el contrato.
- **No se toca el backend** ni el generador.
- **Sin dependencias nuevas.**
- **Las respuestas mantienen la forma del contrato:** `{ok, status, data}` con los códigos que las pantallas ya saben interpretar (`201` al crear, `409` en conflicto de estado, `400` en validación).
- **Los importes se redondean a dos decimales en cada paso**, como hace el backend: comparar contra sus resultados exige el mismo redondeo.
- Comando de tests: `npm test` desde `frontend/` (hoy 133 pasando).

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `frontend/src/demo/cuenta.js` | Imputación de pagos por antigüedad y saldo de una unidad. Puro. |
| `frontend/src/demo/prorrateo.js` | Reparto de los gastos de un período entre las unidades. Puro. |
| `frontend/src/demo/escrituras.js` | Qué hace cada `POST`/`PATCH`/`DELETE` sobre el estado. |
| `frontend/src/demo/estado.js` | Modificado: pasa a permitir escritura. |
| `frontend/src/demo/servidor.js` | Modificado: deriva las escrituras en vez de responder 501. |

---

### Task 1: Imputación de pagos por antigüedad

Es la pieza que hace que aprobar un pago se sienta real: el crédito disponible cubre primero las expensas más viejas, y de ahí salen el saldo de la unidad y su estado en la lista de morosos.

El backend la resuelve en `backend/cuenta_corriente.py`. Lo que se porta es el núcleo: sumar débitos y créditos para el saldo, y repartir el crédito acumulado sobre las expensas ordenadas por vencimiento.

**Files:**
- Create: `frontend/src/demo/cuenta.js`
- Test: `frontend/src/demo/cuenta.test.js`

**Interfaces:**
- Produces: `saldoDeMovimientos(movimientos) -> number`
- Produces: `imputar(expensas, movimientos) -> {saldo, porExpensa: Map<id, {pagado, pendiente, estado}>}`

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/cuenta.test.js
import { describe, it, expect } from "vitest";
import { imputar, saldoDeMovimientos } from "./cuenta";

// Los tipos y su signo son los del backend (`backend/models.py`):
// suman lo que el departamento debe, restan lo que pagó.
const EXPENSA = (id, venc, monto) => ({
  id,
  fecha_primer_vencimiento: venc,
  monto_primer_vencimiento: monto,
});

describe("saldoDeMovimientos", () => {
  it("suma los débitos y resta los créditos", () => {
    const saldo = saldoDeMovimientos([
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 400 },
      { tipo: "nota_debito", monto: 50 },
      { tipo: "nota_credito", monto: 25 },
    ]);
    expect(saldo).toBe(625);
  });

  it("un recargo y un interés suman como débito", () => {
    expect(saldoDeMovimientos([
      { tipo: "recargo", monto: 100 },
      { tipo: "interes_punitorio", monto: 50 },
    ])).toBe(150);
  });

  it("sin movimientos el saldo es cero", () => {
    expect(saldoDeMovimientos([])).toBe(0);
  });

  it("redondea a dos decimales", () => {
    expect(saldoDeMovimientos([
      { tipo: "expensa_emitida", monto: 0.1 },
      { tipo: "expensa_emitida", monto: 0.2 },
    ])).toBe(0.3);
  });
});

describe("imputar", () => {
  const EXPENSAS = [
    EXPENSA(1, "2026-06-10", 1000),
    EXPENSA(2, "2026-07-10", 1000),
  ];

  it("cubre primero la expensa más vieja", () => {
    const r = imputar(EXPENSAS, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 1200 },
    ]);
    expect(r.porExpensa.get(1).pendiente).toBe(0);
    expect(r.porExpensa.get(1).estado).toBe("pagada");
    expect(r.porExpensa.get(2).pendiente).toBe(800);
    expect(r.porExpensa.get(2).estado).toBe("parcial");
  });

  it("sin pagos, todo queda pendiente", () => {
    const r = imputar(EXPENSAS, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
    ]);
    expect(r.saldo).toBe(2000);
    expect(r.porExpensa.get(1).pendiente).toBe(1000);
    expect(r.porExpensa.get(1).estado).toBe("pendiente");
  });

  it("un pago de más deja saldo a favor y todo pagado", () => {
    const r = imputar(EXPENSAS, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 2500 },
    ]);
    expect(r.saldo).toBe(-500);
    expect(r.porExpensa.get(2).pendiente).toBe(0);
  });

  it("imputa por vencimiento, no por el orden en que llegan", () => {
    const desordenadas = [EXPENSA(2, "2026-07-10", 1000), EXPENSA(1, "2026-06-10", 1000)];
    const r = imputar(desordenadas, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 1000 },
    ]);
    expect(r.porExpensa.get(1).pendiente).toBe(0);
    expect(r.porExpensa.get(2).pendiente).toBe(1000);
  });

  it("el recargo asentado contra una expensa sube lo que hay que cubrir", () => {
    const r = imputar([EXPENSA(1, "2026-06-10", 1000)], [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "recargo", monto: 100, expensa_id: 1 },
      { tipo: "pago_recibido", monto: 1000 },
    ]);
    expect(r.porExpensa.get(1).pendiente).toBe(100);
    expect(r.porExpensa.get(1).estado).toBe("parcial");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/cuenta.test.js`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/cuenta.js

/**
 * Tipos de movimiento que aumentan lo que el departamento debe. El resto
 * (pagos y notas de crédito) lo disminuye. Son los mismos de
 * `backend/models.py`: si allá se agrega uno, acá hay que agregarlo también.
 */
const DEBITOS = new Set([
  "expensa_emitida",
  "nota_debito",
  "interes_punitorio",
  "recargo",
]);

const dos = (n) => Math.round(n * 100) / 100;

/** Saldo de una unidad: lo que debe menos lo que pagó. */
export function saldoDeMovimientos(movimientos) {
  const total = movimientos.reduce(
    (acc, m) => acc + (DEBITOS.has(m.tipo) ? m.monto : -m.monto),
    0,
  );
  const redondeado = dos(total);
  // Un residuo de centésimos por acumulación no es una deuda.
  return Math.abs(redondeado) < 0.005 ? 0 : redondeado;
}

/**
 * Reparte el crédito disponible sobre las expensas, de la más vieja a la más
 * nueva, y devuelve el saldo y el estado de cada una.
 *
 * El estado no se guarda en ningún lado: se deduce de los movimientos cada
 * vez. Por eso no puede desincronizarse — es la misma decisión que tomó el
 * backend en `cuenta_corriente.py`.
 *
 * El techo de cada expensa es su primer vencimiento más los recargos que se
 * asentaron contra ella, no el importe original.
 */
export function imputar(expensas, movimientos) {
  const recargos = new Map();
  for (const m of movimientos) {
    if (m.tipo === "recargo" && m.expensa_id != null) {
      recargos.set(m.expensa_id, dos((recargos.get(m.expensa_id) ?? 0) + m.monto));
    }
  }

  const ordenadas = [...expensas].sort(
    (a, b) =>
      a.fecha_primer_vencimiento.localeCompare(b.fecha_primer_vencimiento) || a.id - b.id,
  );

  let credito = movimientos.reduce(
    (acc, m) => acc + (DEBITOS.has(m.tipo) ? 0 : m.monto),
    0,
  );

  const porExpensa = new Map();
  for (const e of ordenadas) {
    const techo = dos(e.monto_primer_vencimiento + (recargos.get(e.id) ?? 0));
    const cubierto = Math.min(credito, techo);
    credito = dos(credito - cubierto);
    const pendiente = dos(techo - cubierto);
    porExpensa.set(e.id, {
      pagado: dos(cubierto),
      pendiente,
      estado: pendiente <= 0.005 ? "pagada" : cubierto > 0.005 ? "parcial" : "pendiente",
    });
  }

  return { saldo: saldoDeMovimientos(movimientos), porExpensa };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/cuenta.test.js`
Expected: PASS (9 tests)

- [ ] **Step 5: Verificación cruzada contra el backend real**

Esta es la prueba que hace confiable tener dos implementaciones de la misma regla: el dataset lo generó el backend, así que su saldo es el resultado correcto. Si la versión del navegador llega al mismo número sobre los mismos movimientos, las dos coinciden.

```javascript
// frontend/src/demo/cuenta.test.js — al final
import DATASET from "./dataset.json";

describe("coincide con lo que calculó el backend", () => {
  const cuentas = Object.entries(DATASET)
    .filter(([path]) => path.endsWith("/cuenta"))
    .map(([path, cuenta]) => [path, cuenta]);

  it("hay cuentas para verificar", () => {
    expect(cuentas.length).toBeGreaterThan(0);
  });

  it.each(cuentas)("%s: el saldo coincide", (_path, cuenta) => {
    expect(saldoDeMovimientos(cuenta.movimientos)).toBeCloseTo(cuenta.saldo_total, 2);
  });
});
```

Run: `cd frontend && npx vitest run src/demo/cuenta.test.js`
Expected: PASS — los 18 saldos coinciden con los del backend.

**Si alguno no coincide, no ajustes el redondeo hasta que dé:** buscá la diferencia real. Un tipo de movimiento que el navegador clasifica distinto que el backend es exactamente lo que esta prueba existe para encontrar.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/demo/cuenta.js frontend/src/demo/cuenta.test.js
git commit -m "feat(demo): imputacion de pagos por antiguedad, verificada contra el backend"
```

---

### Task 2: Reparto de los gastos entre las unidades

La otra mitad del cálculo: convertir los gastos de un período en el importe que le toca a cada unidad. Es lo que hace que cargar un gasto y cerrar el mes se vea en las expensas.

La regla del backend (`backend/cierre.py`) es corta: un gasto asignado a un departamento va entero a esa unidad; un gasto con clase de prorrateo se reparte según el coeficiente de cada unidad en esa clase.

**Files:**
- Create: `frontend/src/demo/prorrateo.js`
- Test: `frontend/src/demo/prorrateo.test.js`

**Interfaces:**
- Produces: `repartir(gastos, coeficientesPorDepto) -> Map<departamento_id, {total, lineas}>`

`coeficientesPorDepto` es `Map<departamento_id, Array<{clase_prorrateo_id, porcentaje}>>`.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/prorrateo.test.js
import { describe, it, expect } from "vitest";
import { repartir } from "./prorrateo";

const COEFS = new Map([
  [1, [{ clase_prorrateo_id: 10, porcentaje: 60 }]],
  [2, [{ clase_prorrateo_id: 10, porcentaje: 40 }]],
]);

describe("repartir", () => {
  it("reparte un gasto de clase según el coeficiente de cada unidad", () => {
    const r = repartir(
      [{ id: 1, concepto: "Ascensores", rubro: "abonos_y_servicios", monto: 1000, clase_prorrateo_id: 10, departamento_id: null }],
      COEFS,
    );
    expect(r.get(1).total).toBe(600);
    expect(r.get(2).total).toBe(400);
  });

  it("un gasto asignado a una unidad va entero a esa unidad", () => {
    const r = repartir(
      [{ id: 2, concepto: "Reparación privada", rubro: "trabajos_reparaciones_unidades", monto: 500, clase_prorrateo_id: null, departamento_id: 2 }],
      COEFS,
    );
    expect(r.get(2).total).toBe(500);
    expect(r.get(1)?.total ?? 0).toBe(0);
  });

  it("acumula varios gastos sobre la misma unidad", () => {
    const r = repartir(
      [
        { id: 1, concepto: "A", rubro: "x", monto: 1000, clase_prorrateo_id: 10, departamento_id: null },
        { id: 2, concepto: "B", rubro: "y", monto: 500, clase_prorrateo_id: 10, departamento_id: null },
      ],
      COEFS,
    );
    expect(r.get(1).total).toBe(900); // 600 + 300
  });

  it("deja una línea de detalle por gasto, con su concepto", () => {
    const r = repartir(
      [{ id: 1, concepto: "Ascensores", rubro: "abonos_y_servicios", monto: 1000, clase_prorrateo_id: 10, departamento_id: null }],
      COEFS,
    );
    expect(r.get(1).lineas).toHaveLength(1);
    expect(r.get(1).lineas[0].concepto).toBe("Ascensores");
    expect(r.get(1).lineas[0].monto).toBe(600);
  });

  it("ignora un gasto sin clase ni departamento en vez de repartirlo mal", () => {
    const r = repartir(
      [{ id: 3, concepto: "Huérfano", rubro: "x", monto: 999, clase_prorrateo_id: null, departamento_id: null }],
      COEFS,
    );
    expect(r.get(1)?.total ?? 0).toBe(0);
    expect(r.get(2)?.total ?? 0).toBe(0);
  });

  it("redondea cada línea a dos decimales, como el backend", () => {
    const r = repartir(
      [{ id: 1, concepto: "A", rubro: "x", monto: 100, clase_prorrateo_id: 10, departamento_id: null }],
      new Map([[1, [{ clase_prorrateo_id: 10, porcentaje: 33.3333 }]]]),
    );
    expect(r.get(1).total).toBe(33.33);
  });

  it("sin gastos no reparte nada", () => {
    expect(repartir([], COEFS).size).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/prorrateo.test.js`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/prorrateo.js

const dos = (n) => Math.round(n * 100) / 100;

/**
 * Convierte los gastos de un período en lo que le toca a cada unidad.
 *
 * Dos casos, los mismos que el backend (`backend/cierre.py`):
 * - gasto asignado a un departamento → va entero a esa unidad;
 * - gasto con clase de prorrateo → se reparte según el coeficiente de cada
 *   unidad en esa clase.
 *
 * Un gasto sin clase ni departamento se ignora: el backend lo marca como
 * huérfano en las validaciones del cierre y tampoco lo reparte. Repartirlo
 * "por las dudas" inventaría plata que nadie asignó.
 */
export function repartir(gastos, coeficientesPorDepto) {
  const porDepto = new Map();

  const agregar = (deptoId, linea) => {
    if (!porDepto.has(deptoId)) porDepto.set(deptoId, { total: 0, lineas: [] });
    const entrada = porDepto.get(deptoId);
    entrada.lineas.push(linea);
    entrada.total = dos(entrada.total + linea.monto);
  };

  for (const gasto of gastos) {
    if (gasto.departamento_id != null) {
      agregar(gasto.departamento_id, {
        rubro: gasto.rubro,
        concepto: gasto.concepto,
        clase_prorrateo_id: null,
        departamento_origen_id: gasto.departamento_id,
        monto: dos(gasto.monto),
      });
      continue;
    }
    if (gasto.clase_prorrateo_id == null) continue;

    for (const [deptoId, coefs] of coeficientesPorDepto.entries()) {
      const coef = coefs.find((c) => c.clase_prorrateo_id === gasto.clase_prorrateo_id);
      if (!coef) continue;
      const monto = dos((gasto.monto * coef.porcentaje) / 100);
      if (monto <= 0) continue;
      agregar(deptoId, {
        rubro: gasto.rubro,
        concepto: gasto.concepto,
        clase_prorrateo_id: gasto.clase_prorrateo_id,
        departamento_origen_id: null,
        monto,
      });
    }
  }

  return porDepto;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/prorrateo.test.js`
Expected: PASS (7 tests)

- [ ] **Step 5: Verificación cruzada contra el dataset**

```javascript
// frontend/src/demo/prorrateo.test.js — al final
import DATASET from "./dataset.json";

describe("coincide con lo que calculó el backend", () => {
  it("reparte el último período cerrado como lo hizo el backend", () => {
    const periodo = DATASET["/periodos"][0].periodo;
    const gastos = DATASET["/gastos"].filter((g) => g.periodo === periodo);
    const coefs = new Map(
      DATASET["/departamentos"].map((d) => [
        d.id,
        DATASET[`/departamentos/${d.id}/coeficientes`] ?? [],
      ]),
    );

    const repartido = repartir(gastos, coefs);
    const expensas = DATASET["/expensas"].filter((e) => e.periodo === periodo);

    expect(expensas.length).toBeGreaterThan(0);
    for (const expensa of expensas) {
      const mio = repartido.get(expensa.departamento_id);
      expect(mio, `sin reparto para el depto ${expensa.departamento_id}`).toBeDefined();
      // El importe de la expensa incluye además el saldo anterior; lo que
      // tiene que coincidir es la parte que sale de los gastos del período.
      const delPeriodo = expensa.monto_primer_vencimiento - (expensa.saldo_anterior ?? 0);
      expect(mio.total).toBeCloseTo(delPeriodo, 0);
    }
  });
});
```

**Si no coincide**, la diferencia dice dónde está el desajuste: puede ser que el importe de la expensa incluya intereses además del saldo anterior. Ajustá la comparación a lo que el dataset realmente trae —mirando un caso concreto— antes de tocar `repartir`. Documentá en el reporte qué compone el importe.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/demo/prorrateo.js frontend/src/demo/prorrateo.test.js
git commit -m "feat(demo): reparto de gastos por coeficiente, verificado contra el dataset"
```

---

### Task 3: El estado pasa a aceptar escrituras

Hasta acá el estado sólo lee. Las escrituras necesitan poder agregar a una lista y reemplazar un valor, sin perder la garantía de que reiniciar vuelve al arranque.

**Files:**
- Modify: `frontend/src/demo/estado.js`
- Test: `frontend/src/demo/estado.test.js`

**Interfaces:**
- Produces: `estado.agregar(path, item)` — agrega al principio de la lista de ese path.
- Produces: `estado.reemplazar(path, valor)`.
- Produces: `estado.siguienteId(path)` — id nuevo, mayor que todos los de esa lista.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/estado.test.js — agregar
describe("escrituras", () => {
  const DATOS = {
    _generado: "2026-08-17",
    "/comunicados": [{ id: 3, titulo: "Viejo" }],
  };

  it("agrega al principio, que es donde la pantalla espera lo nuevo", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    estado.agregar("/comunicados", { id: 4, titulo: "Nuevo" });
    expect(estado.leer("/comunicados")[0].titulo).toBe("Nuevo");
    expect(estado.leer("/comunicados")).toHaveLength(2);
  });

  it("reemplaza el valor de una ruta", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    estado.reemplazar("/comunicados", []);
    expect(estado.leer("/comunicados")).toEqual([]);
  });

  it("el siguiente id es mayor que todos los existentes", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    expect(estado.siguienteId("/comunicados")).toBe(4);
  });

  it("el siguiente id de una lista vacía arranca en 1", () => {
    const estado = crearEstado({ _generado: "2026-08-17", "/x": [] }, new Date(2026, 7, 20));
    expect(estado.siguienteId("/x")).toBe(1);
  });

  it("reiniciar deshace las escrituras", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    estado.agregar("/comunicados", { id: 4, titulo: "Nuevo" });
    estado.reiniciar();
    expect(estado.leer("/comunicados")).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/estado.test.js`
Expected: FAIL — `estado.agregar is not a function`.

- [ ] **Step 3: Write minimal implementation**

En `frontend/src/demo/estado.js`, agregar al objeto devuelto:

```javascript
    agregar(path, item) {
      const lista = actual[path];
      if (!Array.isArray(lista)) {
        actual[path] = [item];
        return;
      }
      // Al principio: las pantallas listan lo más nuevo arriba, y así lo que
      // el visitante acaba de crear aparece donde lo va a buscar.
      lista.unshift(item);
    },
    reemplazar(path, valor) {
      actual[path] = valor;
    },
    siguienteId(path) {
      const lista = actual[path];
      if (!Array.isArray(lista) || lista.length === 0) return 1;
      return Math.max(...lista.map((x) => x.id ?? 0)) + 1;
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/estado.test.js`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/estado.js frontend/src/demo/estado.test.js
git commit -m "feat(demo): el estado del navegador acepta escrituras"
```

---

### Task 4: Las escrituras simples del recorrido

Publicar un comunicado, crear una petición y reservar un amenity. Son "agregar a una lista" y dan textura al recorrido sin cálculo de por medio.

**Files:**
- Create: `frontend/src/demo/escrituras.js`
- Modify: `frontend/src/demo/servidor.js`
- Test: `frontend/src/demo/escrituras.test.js`

**Interfaces:**
- Produces: `escribir(estado, method, ruta, body, sesion) -> {ok, status, data} | null` — `null` significa "esta escritura no la manejo yo", para que el servidor siga buscando.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/escrituras.test.js
import { describe, it, expect, beforeEach } from "vitest";
import { crearEstado } from "./estado";
import { escribir } from "./escrituras";

const DATOS = {
  _generado: "2026-08-17",
  "/comunicados": [{ id: 1, titulo: "Viejo", cuerpo: "..." }],
  "/peticiones": [{ id: 1, titulo: "Vieja", estado: "abierta" }],
  "/amenities": [{ id: 5, nombre: "SUM", precio_reserva: 25000 }],
  "/reservas": [],
};

let estado;
beforeEach(() => {
  estado = crearEstado(DATOS, new Date(2026, 7, 20));
});

describe("publicar un comunicado", () => {
  it("lo agrega y devuelve 201", () => {
    const r = escribir(estado, "POST", "/comunicados", { titulo: "Corte de agua", cuerpo: "Mañana" }, {});
    expect(r.status).toBe(201);
    expect(estado.leer("/comunicados")[0].titulo).toBe("Corte de agua");
  });

  it("le pone fecha de publicación", () => {
    const r = escribir(estado, "POST", "/comunicados", { titulo: "X", cuerpo: "Y" }, {});
    expect(r.data.fecha_publicacion).toBeTruthy();
  });

  it("sin título devuelve 400", () => {
    const r = escribir(estado, "POST", "/comunicados", { cuerpo: "sin titulo" }, {});
    expect(r.status).toBe(400);
  });
});

describe("crear una petición", () => {
  it("la agrega como abierta, a nombre del departamento de la sesión", () => {
    const r = escribir(
      estado, "POST", "/peticiones",
      { titulo: "Pérdida de agua", descripcion: "En el baño" },
      { departamento_id: 7 },
    );
    expect(r.status).toBe(201);
    expect(r.data.estado).toBe("abierta");
    expect(r.data.departamento_id).toBe(7);
  });
});

describe("reservar un amenity", () => {
  it("crea la reserva confirmada", () => {
    const r = escribir(
      estado, "POST", "/amenities/5/reservas",
      { inicio: "2026-09-10T14:00:00", fin: "2026-09-10T17:00:00" },
      { departamento_id: 3 },
    );
    expect(r.status).toBe(201);
    expect(r.data.estado).toBe("confirmada");
    expect(estado.leer("/reservas")).toHaveLength(1);
  });

  it("con fin anterior al inicio devuelve 400, como el backend", () => {
    const r = escribir(
      estado, "POST", "/amenities/5/reservas",
      { inicio: "2026-09-10T17:00:00", fin: "2026-09-10T14:00:00" },
      { departamento_id: 3 },
    );
    expect(r.status).toBe(400);
  });

  it("sobre un amenity que no existe devuelve 404", () => {
    const r = escribir(
      estado, "POST", "/amenities/999/reservas",
      { inicio: "2026-09-10T14:00:00", fin: "2026-09-10T17:00:00" },
      { departamento_id: 3 },
    );
    expect(r.status).toBe(404);
  });
});

describe("lo que no maneja", () => {
  it("devuelve null para que el servidor siga buscando", () => {
    expect(escribir(estado, "POST", "/algo-que-no-conoce", {}, {})).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/escrituras.test.js`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/escrituras.js

const ahora = () => new Date().toISOString().slice(0, 19);

const creado = (data) => ({ ok: true, status: 201, data });
const invalido = (detail) => ({ ok: false, status: 400, data: { detail } });
const noEncontrado = (detail) => ({ ok: false, status: 404, data: { detail } });

/**
 * Ejecuta una escritura sobre el estado.
 *
 * Devuelve `null` cuando la ruta no le corresponde, para que el servidor
 * siga buscando quién la atiende — así este módulo crece sin tocar el
 * enrutador.
 */
export function escribir(estado, method, ruta, body, sesion) {
  if (method === "POST" && ruta === "/comunicados") {
    if (!body?.titulo) return invalido("El comunicado necesita un título.");
    const comunicado = {
      id: estado.siguienteId("/comunicados"),
      titulo: body.titulo,
      cuerpo: body.cuerpo ?? "",
      fecha_publicacion: ahora(),
      autor_id: 1,
    };
    estado.agregar("/comunicados", comunicado);
    return creado(comunicado);
  }

  if (method === "POST" && ruta === "/peticiones") {
    if (!body?.titulo) return invalido("La petición necesita un título.");
    const peticion = {
      id: estado.siguienteId("/peticiones"),
      departamento_id: sesion?.departamento_id ?? null,
      titulo: body.titulo,
      descripcion: body.descripcion ?? "",
      estado: "abierta",
      fecha_creacion: ahora(),
    };
    estado.agregar("/peticiones", peticion);
    return creado(peticion);
  }

  const reserva = /^\/amenities\/(\d+)\/reservas$/.exec(ruta);
  if (method === "POST" && reserva) {
    const amenityId = Number(reserva[1]);
    const amenity = (estado.leer("/amenities") ?? []).find((a) => a.id === amenityId);
    if (!amenity) return noEncontrado("El amenity no existe.");
    if (!body?.inicio || !body?.fin) return invalido("Faltan las fechas de la reserva.");
    if (body.fin <= body.inicio) return invalido("El fin tiene que ser posterior al inicio.");
    const nueva = {
      id: estado.siguienteId("/reservas"),
      amenity_id: amenityId,
      usuario_id: sesion?.departamento_id ?? null,
      inicio: body.inicio,
      fin: body.fin,
      estado: "confirmada",
      movimiento_cuenta_id: null,
    };
    estado.agregar("/reservas", nueva);
    return creado(nueva);
  }

  return null;
}
```

En `servidor.js`, antes del rechazo de escrituras:

```javascript
  if (method !== "GET") {
    const escritura = escribir(estado, method, ruta, body, sesion);
    if (escritura) return escritura;
    return noImplementado(method, ruta, "esta escritura todavía no está en la demo");
  }
```

(y agregar `import { escribir } from "./escrituras";`)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/escrituras.js frontend/src/demo/escrituras.test.js frontend/src/demo/servidor.js
git commit -m "feat(demo): comunicados, peticiones y reservas se pueden crear"
```

---

### Task 5: Circuito 1 — presentar un pago y aprobarlo

El propietario presenta el comprobante con su foto; administración lo aprueba; el pago entra a la cuenta corriente, se imputa a la deuda más vieja, baja el saldo y la unidad sale de la lista de morosos.

**Files:**
- Modify: `frontend/src/demo/escrituras.js`
- Test: `frontend/src/demo/escrituras.test.js`

**Interfaces:**
- Consumes: `imputar`, `saldoDeMovimientos` (Task 1).

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/escrituras.test.js — agregar
describe("circuito 1: presentar y aprobar un pago", () => {
  const CON_DEUDA = {
    _generado: "2026-08-17",
    "/departamentos": [{ id: 7, codigo: "UF-03C" }],
    "/comprobantes": [],
    "/expensas": [
      {
        id: 90,
        departamento_id: 7,
        periodo: "2026-07",
        fecha_primer_vencimiento: "2026-08-10",
        monto_primer_vencimiento: 1000,
        monto_pendiente: 1000,
        estado_calculado: "vencida",
      },
    ],
    "/departamentos/7/cuenta": {
      saldo_total: 1000,
      movimientos: [{ id: 1, tipo: "expensa_emitida", monto: 1000, fecha: "2026-08-01", descripcion: "Expensa 2026-07" }],
    },
    "/reportes/morosos": [{ departamento_id: 7, departamento_codigo: "UF-03C", saldo: 1000 }],
  };

  let e;
  beforeEach(() => {
    e = crearEstado(CON_DEUDA, new Date(2026, 7, 20));
  });

  it("presentar deja el comprobante pendiente de aprobación", () => {
    const r = escribir(e, "POST", "/comprobantes", { monto: 1000, fecha_pago: "2026-08-18" }, { departamento_id: 7 });
    expect(r.status).toBe(201);
    expect(r.data.estado).toBe("pendiente_verificacion");
    expect(e.leer("/comprobantes")).toHaveLength(1);
  });

  it("aprobarlo agrega el pago a la cuenta corriente", () => {
    const p = escribir(e, "POST", "/comprobantes", { monto: 1000, fecha_pago: "2026-08-18" }, { departamento_id: 7 });
    const r = escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});

    expect(r.status).toBe(200);
    const cuenta = e.leer("/departamentos/7/cuenta");
    expect(cuenta.movimientos.some((m) => m.tipo === "pago_recibido")).toBe(true);
    expect(cuenta.saldo_total).toBe(0);
  });

  it("aprobarlo saca a la unidad de la lista de morosos", () => {
    const p = escribir(e, "POST", "/comprobantes", { monto: 1000, fecha_pago: "2026-08-18" }, { departamento_id: 7 });
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    expect(e.leer("/reportes/morosos")).toHaveLength(0);
  });

  it("aprobarlo marca la expensa como pagada", () => {
    const p = escribir(e, "POST", "/comprobantes", { monto: 1000, fecha_pago: "2026-08-18" }, { departamento_id: 7 });
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    const expensa = e.leer("/expensas")[0];
    expect(expensa.estado_calculado).toBe("pagada");
    expect(expensa.monto_pendiente).toBe(0);
  });

  it("un pago parcial deja la expensa parcial y la unidad en la lista", () => {
    const p = escribir(e, "POST", "/comprobantes", { monto: 400, fecha_pago: "2026-08-18" }, { departamento_id: 7 });
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    expect(e.leer("/expensas")[0].estado_calculado).toBe("parcial");
    expect(e.leer("/reportes/morosos")).toHaveLength(1);
  });

  it("aprobar dos veces el mismo comprobante devuelve 409, como el backend", () => {
    const p = escribir(e, "POST", "/comprobantes", { monto: 1000, fecha_pago: "2026-08-18" }, { departamento_id: 7 });
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    const segunda = escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    expect(segunda.status).toBe(409);
  });

  it("presentar sin sesión de departamento devuelve 403", () => {
    const r = escribir(e, "POST", "/comprobantes", { monto: 100, fecha_pago: "2026-08-18" }, { departamento_id: null });
    expect(r.status).toBe(403);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/escrituras.test.js`
Expected: FAIL — devuelve `null` para esas rutas.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/escrituras.js — agregar arriba
import { imputar, saldoDeMovimientos } from "./cuenta";

const prohibido = (detail) => ({ ok: false, status: 403, data: { detail } });
const conflicto = (detail) => ({ ok: false, status: 409, data: { detail } });
const ok = (data) => ({ ok: true, status: 200, data });
```

```javascript
// dentro de `escribir`, antes del return null

  if (method === "POST" && ruta === "/comprobantes") {
    if (!sesion?.departamento_id) return prohibido("Sólo un departamento presenta pagos.");
    if (!body?.monto || body.monto <= 0) return invalido("El monto tiene que ser mayor a cero.");
    const comprobante = {
      id: estado.siguienteId("/comprobantes"),
      departamento_id: sesion.departamento_id,
      departamento_codigo: codigoDe(estado, sesion.departamento_id),
      fecha_pago: body.fecha_pago ?? ahora().slice(0, 10),
      monto: body.monto,
      // La imagen que el visitante eligió se lee en el navegador y viaja como
      // dato embebido: no hay servidor donde subirla.
      archivo_path: body.archivo_url ?? null,
      estado: "pendiente_verificacion",
    };
    estado.agregar("/comprobantes", comprobante);
    return creado(comprobante);
  }

  const aprobacion = /^\/comprobantes\/(\d+)$/.exec(ruta);
  if (method === "PATCH" && aprobacion) {
    const comprobante = (estado.leer("/comprobantes") ?? []).find(
      (c) => c.id === Number(aprobacion[1]),
    );
    if (!comprobante) return noEncontrado("El comprobante no existe.");
    if (comprobante.estado !== "pendiente_verificacion") {
      return conflicto("El comprobante ya fue resuelto.");
    }
    comprobante.estado = body?.estado ?? "aprobado";
    if (comprobante.estado === "aprobado") {
      registrarPago(estado, comprobante);
    }
    return ok(comprobante);
  }
```

```javascript
// al final del archivo

function codigoDe(estado, deptoId) {
  return (estado.leer("/departamentos") ?? []).find((d) => d.id === deptoId)?.codigo ?? null;
}

/**
 * Asienta el pago en la cuenta corriente y recalcula todo lo que depende de
 * ella: el saldo, el estado de cada expensa y la lista de morosos.
 *
 * El backend hace lo mismo: no guarda el estado de una expensa, lo deduce de
 * los movimientos. Acá se recalcula en el momento por la misma razón — así no
 * hay dos verdades que puedan separarse.
 */
function registrarPago(estado, comprobante) {
  const rutaCuenta = `/departamentos/${comprobante.departamento_id}/cuenta`;
  const cuenta = estado.leer(rutaCuenta);
  if (!cuenta) return;

  cuenta.movimientos.unshift({
    id: Math.max(0, ...cuenta.movimientos.map((m) => m.id ?? 0)) + 1,
    tipo: "pago_recibido",
    monto: comprobante.monto,
    fecha: comprobante.fecha_pago,
    descripcion: `Pago ${comprobante.departamento_codigo ?? ""} - ${comprobante.fecha_pago}`,
    expensa_id: null,
  });

  const misExpensas = (estado.leer("/expensas") ?? []).filter(
    (e) => e.departamento_id === comprobante.departamento_id,
  );
  const { saldo, porExpensa } = imputar(misExpensas, cuenta.movimientos);

  cuenta.saldo_total = saldo;
  for (const expensa of misExpensas) {
    const estadoExpensa = porExpensa.get(expensa.id);
    if (!estadoExpensa) continue;
    expensa.monto_pendiente = estadoExpensa.pendiente;
    expensa.estado_calculado = estadoExpensa.estado;
  }

  const morosos = estado.leer("/reportes/morosos") ?? [];
  estado.reemplazar(
    "/reportes/morosos",
    saldo > 0.005
      ? morosos.map((m) =>
          m.departamento_id === comprobante.departamento_id ? { ...m, saldo } : m,
        )
      : morosos.filter((m) => m.departamento_id !== comprobante.departamento_id),
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/escrituras.js frontend/src/demo/escrituras.test.js
git commit -m "feat(demo): circuito de cobranza vivo — presentar y aprobar un pago"
```

---

### Task 6: Circuito 2 — cargar un gasto y cerrar el mes

Administración carga un gasto en el período abierto, va a cerrar el mes, ve las validaciones, confirma, y el gasto aparece repartido en las expensas de las dieciocho unidades.

**Files:**
- Modify: `frontend/src/demo/escrituras.js`
- Test: `frontend/src/demo/escrituras.test.js`

**Interfaces:**
- Consumes: `repartir` (Task 2).

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/escrituras.test.js — agregar
describe("circuito 2: cargar un gasto y cerrar el mes", () => {
  const ABIERTO = {
    _generado: "2026-08-17",
    "/departamentos": [{ id: 1, codigo: "UF-01A" }, { id: 2, codigo: "UF-01B" }],
    "/departamentos/1/coeficientes": [{ clase_prorrateo_id: 10, porcentaje: 50 }],
    "/departamentos/2/coeficientes": [{ clase_prorrateo_id: 10, porcentaje: 50 }],
    "/departamentos/1/cuenta": { saldo_total: 0, movimientos: [] },
    "/departamentos/2/cuenta": { saldo_total: 0, movimientos: [] },
    "/clases-prorrateo": [{ id: 10, codigo: "A", nombre: "Expensas ordinarias", activa: true }],
    "/gastos": [],
    "/expensas": [],
    "/periodos": [{ periodo: "2026-07", total_expensado: 0, cantidad_expensas: 2 }],
    "/periodos/2026-08/estado": { periodo: "2026-08", cerrado: false, validaciones: [], puede_cerrar: true },
  };

  let e;
  beforeEach(() => {
    e = crearEstado(ABIERTO, new Date(2026, 7, 20));
  });

  it("cargar un gasto lo agrega al período", () => {
    const r = escribir(e, "POST", "/gastos", {
      periodo: "2026-08", rubro: "abonos_y_servicios", concepto: "Ascensores",
      monto: 1000, clase_prorrateo_id: 10,
    }, {});
    expect(r.status).toBe(201);
    expect(e.leer("/gastos")).toHaveLength(1);
  });

  it("sin monto devuelve 400", () => {
    const r = escribir(e, "POST", "/gastos", { periodo: "2026-08", concepto: "X" }, {});
    expect(r.status).toBe(400);
  });

  it("el preview reparte el gasto entre las unidades", () => {
    escribir(e, "POST", "/gastos", {
      periodo: "2026-08", rubro: "abonos_y_servicios", concepto: "Ascensores",
      monto: 1000, clase_prorrateo_id: 10,
    }, {});
    const r = escribir(e, "POST", "/periodos/2026-08/preview", {}, {});
    expect(r.status).toBe(200);
    expect(r.data.expensas).toHaveLength(2);
    expect(r.data.expensas[0].monto_primer_vencimiento).toBe(500);
    expect(r.data.total_expensado).toBe(1000);
  });

  it("cerrar emite una expensa por unidad", () => {
    escribir(e, "POST", "/gastos", {
      periodo: "2026-08", rubro: "abonos_y_servicios", concepto: "Ascensores",
      monto: 1000, clase_prorrateo_id: 10,
    }, {});
    const r = escribir(e, "POST", "/periodos/2026-08/cerrar", {
      fecha_primer_vencimiento: "2026-09-10", fecha_segundo_vencimiento: "2026-09-20",
    }, {});

    expect(r.status).toBe(201);
    const emitidas = e.leer("/expensas").filter((x) => x.periodo === "2026-08");
    expect(emitidas).toHaveLength(2);
    expect(emitidas[0].monto_primer_vencimiento).toBe(500);
  });

  it("cerrar deja el movimiento en la cuenta de cada unidad", () => {
    escribir(e, "POST", "/gastos", {
      periodo: "2026-08", rubro: "x", concepto: "Y", monto: 1000, clase_prorrateo_id: 10,
    }, {});
    escribir(e, "POST", "/periodos/2026-08/cerrar", {
      fecha_primer_vencimiento: "2026-09-10", fecha_segundo_vencimiento: "2026-09-20",
    }, {});
    const cuenta = e.leer("/departamentos/1/cuenta");
    expect(cuenta.movimientos.some((m) => m.tipo === "expensa_emitida")).toBe(true);
    expect(cuenta.saldo_total).toBe(500);
  });

  it("cerrar dos veces el mismo período devuelve 409", () => {
    escribir(e, "POST", "/gastos", {
      periodo: "2026-08", rubro: "x", concepto: "Y", monto: 1000, clase_prorrateo_id: 10,
    }, {});
    const cerrar = () => escribir(e, "POST", "/periodos/2026-08/cerrar", {
      fecha_primer_vencimiento: "2026-09-10", fecha_segundo_vencimiento: "2026-09-20",
    }, {});
    cerrar();
    expect(cerrar().status).toBe(409);
  });

  it("cerrar un período sin gastos avisa en las validaciones", () => {
    const r = escribir(e, "POST", "/periodos/2026-08/preview", {}, {});
    expect(r.data.validaciones.some((v) => /no tiene gastos/i.test(v.mensaje))).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/escrituras.test.js`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/escrituras.js — agregar el import
import { repartir } from "./prorrateo";
```

```javascript
// dentro de `escribir`, antes del return null

  if (method === "POST" && ruta === "/gastos") {
    if (!body?.monto || body.monto <= 0) return invalido("El gasto necesita un monto.");
    if (!body?.periodo) return invalido("El gasto necesita un período.");
    const gasto = {
      id: estado.siguienteId("/gastos"),
      periodo: body.periodo,
      rubro: body.rubro ?? "otros",
      clase_prorrateo_id: body.clase_prorrateo_id ?? null,
      departamento_id: body.departamento_id ?? null,
      proveedor_id: body.proveedor_id ?? null,
      concepto: body.concepto ?? "",
      monto: body.monto,
      forma_pago: body.forma_pago ?? "transferencia",
      fecha_pago: body.fecha_pago ?? null,
      pagado: false,
      cuota_actual: null,
      cuota_total: null,
    };
    estado.agregar("/gastos", gasto);
    return creado(gasto);
  }

  const preview = /^\/periodos\/([\d-]+)\/preview$/.exec(ruta);
  if (method === "POST" && preview) {
    return armarPreview(estado, preview[1]);
  }

  const cierre = /^\/periodos\/([\d-]+)\/cerrar$/.exec(ruta);
  if (method === "POST" && cierre) {
    return cerrarPeriodo(estado, cierre[1], body);
  }
```

```javascript
// al final del archivo

function coeficientesPorDepto(estado) {
  const mapa = new Map();
  for (const depto of estado.leer("/departamentos") ?? []) {
    mapa.set(depto.id, estado.leer(`/departamentos/${depto.id}/coeficientes`) ?? []);
  }
  return mapa;
}

/**
 * Lo que el administrador ve antes de confirmar el cierre: cuánto se va a
 * expensar, a cuántas unidades, y qué conviene mirar antes.
 *
 * Las validaciones son las simples —las que salen de mirar el estado— porque
 * son parte del momento en que el sistema muestra criterio. Las elaboradas
 * las trae el dataset y no se recalculan (spec §5.2).
 */
function armarPreview(estado, periodo) {
  const gastos = (estado.leer("/gastos") ?? []).filter((g) => g.periodo === periodo);
  const repartido = repartir(gastos, coeficientesPorDepto(estado));

  const validaciones = [];
  if (gastos.length === 0) {
    validaciones.push({
      tipo: "warning",
      codigo: "sin_gastos",
      mensaje: `El período ${periodo} no tiene gastos cargados. Las expensas serán $0.`,
    });
  }
  for (const clase of estado.leer("/clases-prorrateo") ?? []) {
    const tiene = gastos.some((g) => g.clase_prorrateo_id === clase.id);
    if (!tiene) {
      validaciones.push({
        tipo: "warning",
        codigo: "clases_sin_gastos",
        mensaje: `La clase '${clase.nombre}' está activa pero no tiene gastos en el período (no se prorratea).`,
      });
    }
  }

  const expensas = [...repartido.entries()].map(([departamento_id, r]) => ({
    departamento_id,
    monto_primer_vencimiento: r.total,
    saldo_anterior: estado.leer(`/departamentos/${departamento_id}/cuenta`)?.saldo_total ?? 0,
    detalle: r.lineas,
  }));

  return ok({
    periodo,
    expensas,
    total_expensado: dos(expensas.reduce((a, e) => a + e.monto_primer_vencimiento, 0)),
    total_intereses: 0,
    validaciones,
    puede_cerrar: true,
  });
}

/** Emite las expensas del período y las asienta en cada cuenta corriente. */
function cerrarPeriodo(estado, periodo, body) {
  const yaCerrado = (estado.leer("/periodos") ?? []).some((p) => p.periodo === periodo);
  if (yaCerrado) return conflicto(`El período ${periodo} ya fue cerrado.`);

  const previa = armarPreview(estado, periodo);
  const f1 = body?.fecha_primer_vencimiento ?? null;
  const f2 = body?.fecha_segundo_vencimiento ?? null;

  for (const linea of previa.data.expensas) {
    const expensa = {
      id: estado.siguienteId("/expensas"),
      departamento_id: linea.departamento_id,
      periodo,
      monto_primer_vencimiento: linea.monto_primer_vencimiento,
      fecha_primer_vencimiento: f1,
      monto_segundo_vencimiento: dos(linea.monto_primer_vencimiento * 1.07),
      fecha_segundo_vencimiento: f2,
      saldo_anterior: linea.saldo_anterior,
      estado_calculado: "pendiente",
      monto_pendiente: linea.monto_primer_vencimiento,
      monto_exigible: linea.monto_primer_vencimiento,
      interes_acumulado: 0,
      detalle: linea.detalle,
    };
    estado.agregar("/expensas", expensa);

    const cuenta = estado.leer(`/departamentos/${linea.departamento_id}/cuenta`);
    if (cuenta) {
      cuenta.movimientos.unshift({
        id: Math.max(0, ...cuenta.movimientos.map((m) => m.id ?? 0)) + 1,
        tipo: "expensa_emitida",
        monto: linea.monto_primer_vencimiento,
        fecha: f1,
        descripcion: `Expensa ${periodo}`,
        expensa_id: expensa.id,
      });
      cuenta.saldo_total = saldoDeMovimientos(cuenta.movimientos);
    }
  }

  const cerrado = {
    periodo,
    fecha_cierre: ahora(),
    cerrado_por_usuario_id: 1,
    total_expensado: previa.data.total_expensado,
    total_intereses: 0,
    cantidad_expensas: previa.data.expensas.length,
  };
  estado.agregar("/periodos", cerrado);
  return { ok: true, status: 201, data: cerrado };
}
```

Agregar arriba del archivo el helper de redondeo:

```javascript
const dos = (n) => Math.round(n * 100) / 100;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/escrituras.js frontend/src/demo/escrituras.test.js
git commit -m "feat(demo): circuito de gastos vivo — cargar y cerrar el mes"
```

---

### Task 7: Los dos circuitos, de punta a punta

Las tareas anteriores probaron cada pieza. Esta prueba el recorrido completo sobre el dataset real, que es lo que va a hacer el visitante.

**Files:**
- Create: `frontend/src/demo/circuitos.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/circuitos.test.js
import { describe, it, expect, beforeEach } from "vitest";
import DATASET from "./dataset.json";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

let estado;
beforeEach(() => {
  estado = crearEstado(DATASET, new Date());
});

/** Entra con un perfil y devuelve su sesión, como hace la aplicación. */
function entrar(rol) {
  const r = responder(estado, "POST", "/auth/demo-login", { rol });
  return { departamento_id: r.data.user.departamento_id };
}

describe("circuito 1: la plata que entra", () => {
  it("el moroso paga, administración aprueba, y la deuda baja", () => {
    const moroso = entrar("propietario_moroso");
    const antes = responder(estado, "GET", "/movimientos/mi-cuenta", null, moroso).data.saldo_total;
    expect(antes).toBeGreaterThan(0);

    const presentado = responder(
      estado, "POST", "/comprobantes",
      { monto: antes, fecha_pago: "2026-08-18" }, moroso,
    );
    expect(presentado.status).toBe(201);
    expect(presentado.data.estado).toBe("pendiente_verificacion");

    const aprobado = responder(
      estado, "PATCH", `/comprobantes/${presentado.data.id}`,
      { estado: "aprobado" }, { departamento_id: null },
    );
    expect(aprobado.status).toBe(200);

    const despues = responder(estado, "GET", "/movimientos/mi-cuenta", null, moroso).data.saldo_total;
    expect(despues).toBeLessThan(antes);
    expect(despues).toBe(0);
  });

  it("y la unidad desaparece de la lista de morosos", () => {
    const moroso = entrar("propietario_moroso");
    const saldo = responder(estado, "GET", "/movimientos/mi-cuenta", null, moroso).data.saldo_total;
    const p = responder(estado, "POST", "/comprobantes", { monto: saldo, fecha_pago: "2026-08-18" }, moroso);
    responder(estado, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});

    const morosos = responder(estado, "GET", "/reportes/morosos").data;
    expect(morosos.some((m) => m.departamento_id === moroso.departamento_id)).toBe(false);
  });
});

describe("circuito 2: la plata que sale", () => {
  it("cargar un gasto y cerrar el mes emite una expensa por unidad", () => {
    const mesAbierto = mesSiguienteAlUltimoCerrado(estado);
    const unidades = responder(estado, "GET", "/departamentos").data.length;

    const clase = responder(estado, "GET", "/clases-prorrateo").data[0];
    const gasto = responder(estado, "POST", "/gastos", {
      periodo: mesAbierto,
      rubro: "abonos_y_servicios",
      concepto: "Service de bombas",
      monto: 480000,
      clase_prorrateo_id: clase.id,
    });
    expect(gasto.status).toBe(201);

    const preview = responder(estado, "POST", `/periodos/${mesAbierto}/preview`, {});
    expect(preview.status).toBe(200);
    expect(preview.data.expensas.length).toBe(unidades);

    const cierre = responder(estado, "POST", `/periodos/${mesAbierto}/cerrar`, {
      fecha_primer_vencimiento: "2026-09-10",
      fecha_segundo_vencimiento: "2026-09-20",
    });
    expect(cierre.status).toBe(201);
    expect(cierre.data.cantidad_expensas).toBe(unidades);

    const emitidas = responder(estado, "GET", `/expensas?periodo=${mesAbierto}`).data;
    expect(emitidas).toHaveLength(unidades);
    // El gasto se repartió: la suma de las expensas cubre el gasto cargado.
    const total = emitidas.reduce((a, e) => a + e.monto_primer_vencimiento, 0);
    expect(total).toBeCloseTo(480000, 0);
  });
});

/** El mes siguiente al último período cerrado del dataset. */
function mesSiguienteAlUltimoCerrado(estado) {
  const periodos = responder(estado, "GET", "/periodos").data.map((p) => p.periodo).sort();
  const [anio, mes] = periodos[periodos.length - 1].split("-").map(Number);
  const total = anio * 12 + (mes - 1) + 1;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/circuitos.test.js`
Expected: FAIL si algo del encadenado no funciona sobre datos reales. **Anotá qué falla**: puede ser que el dataset real tenga algo que los datos de prueba no.

- [ ] **Step 3: Cerrar lo que aparezca**

Los datos reales tienen casos que los de prueba no: unidades con saldo a favor, expensas con recargo asentado, un período con gastos de varias clases. Arreglá lo que falle **en el módulo que corresponda**, no en el test.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: todo verde, incluidos los 133 tests previos.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/circuitos.test.js
git commit -m "test(demo): los dos circuitos funcionan sobre el dataset real"
```

---

## Verificación manual antes de dar el plan por terminado

Con el backend **apagado**:

```bash
cd frontend && VITE_DEMO_MODE=true npm run dev
```

**Circuito 1:**
1. Entrar como Propietario moroso → Mi cuenta → anotar el saldo.
2. Presentar pago con una foto cualquiera del disco.
3. Verificar que aparece en Comprobantes como pendiente.
4. Salir, entrar como Administración → Cobranzas → Comprobantes → aprobarlo.
5. Volver a entrar como el propietario: el saldo tiene que haber bajado.
6. Lista de morosos: la unidad tiene que haber salido o bajado su saldo.

**Circuito 2:**
1. Entrar como Administración → Gastos → mes en curso → cargar un gasto.
2. Cierre de período → ver las validaciones → generar el preview.
3. Confirmar el cierre.
4. Cobranzas: tienen que aparecer las dieciocho expensas nuevas, con el gasto repartido.

**Lo que hay que mirar con desconfianza:** que los importes de la pantalla coincidan con lo que uno esperaría a mano. Cargá un gasto de $180.000 en un edificio de 18 unidades con coeficientes iguales y comprobá que a cada una le tocan $10.000.
