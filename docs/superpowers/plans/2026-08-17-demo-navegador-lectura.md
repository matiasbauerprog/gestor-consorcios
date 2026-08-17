# Demo en el navegador, parte 1: navegable en lectura — Plan B1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la demo se navegue entera sin backend — todas las pantallas del recorrido de venta cargando datos reales desde un archivo estático, con las fechas corridas al día de la visita.

**Architecture:** Un módulo en `frontend/src/demo/` recibe los pedidos que hoy salen a la red y los responde desde un estado en memoria sembrado con el dataset exportado. El enganche es un único punto: `apiFetch`, por donde ya pasan las 142 llamadas del frontend. Ninguna pantalla se modifica.

**Tech Stack:** React 18 · Vite · vitest. Sin dependencias nuevas. Del lado del generador: Python, `backend/export_demo.py`.

**Spec:** `docs/superpowers/specs/2026-08-16-demo-sin-backend-design.md` (§2, §3.3, §4)

**Alcance de ESTE plan:** sólo lectura. Las escrituras de los dos circuitos (§2.1), el prorrateo y la imputación portados (§5.1), el cambiador de rol (§2.4), las secciones marcadas (§2.2) y el despliegue (§7) son el Plan B2.

## Global Constraints

- **No se toca ninguna pantalla.** El trabajo es en `frontend/src/demo/` (nuevo), `frontend/src/api/client.js` (el enganche) y `backend/export_demo.py`. Si una pantalla necesitara cambios, es señal de que el sustituto no está respetando el contrato: arreglar el sustituto.
- **No se toca el backend de producción:** ni `backend/routers/`, ni `backend/models.py`, ni `openapi.yaml`.
- **Sin dependencias nuevas** ni en `requirements.txt` ni en `frontend/package.json`.
- **El sustituto devuelve la misma forma que `apiFetch`:** `{ok, status, data}`, con los códigos del contrato (`200`/`201`/`204`/`400`/`403`/`404`/`409`).
- **En el build de producción el sustituto no existe:** la inclusión es condicional por `import.meta.env.VITE_DEMO_MODE`.
- Comando de tests del frontend: `npm test` desde `frontend/` (hoy 59 pasando).
- Comando de tests del backend: `pytest tests/test_export_demo.py -v` (hoy 6 pasando).
- Comando para regenerar el dataset:
  `DEMO_SEED_PASSWORD=demo1234 SUPER_ADMIN_EMAIL=sa@demo.local SUPER_ADMIN_PASSWORD=demo12345678 DATABASE_URL=sqlite:///./demo.db SEED_ENABLED=false python -m backend.seed_demo --reset --exportar`

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `frontend/src/demo/dataset.json` | Ya existe. Estado inicial exportado del backend real. |
| `frontend/src/demo/fechas.js` | Desplazar fechas del dataset al día de la visita. Puro. |
| `frontend/src/demo/estado.js` | Cargar el dataset, aplicar el desplazamiento, exponer el estado. |
| `frontend/src/demo/rutas.js` | Tabla de rutas → función que produce la respuesta. |
| `frontend/src/demo/servidor.js` | Entrada única: `responder(method, path, body)`. |
| `frontend/src/api/client.js` | Modificado: deriva a `responder` si la bandera está encendida. |
| `backend/export_demo.py` | Modificado: exporta las rutas que faltan y la fecha de generación. |

---

### Task 1: Exportar las rutas que faltan y la fecha de generación

El dataset actual tiene 16 rutas, pero **le faltan las que el recorrido necesita**. La más grave: la cuenta corriente de los departamentos, que es la base de la pantalla "Mi cuenta" del propietario y del circuito de cobranza. También falta la fecha de generación, sin la cual no se puede calcular el desplazamiento (§3.3 del spec).

Rutas faltantes, verificadas contra los clientes de `frontend/src/api/`:

| Ruta | Quién la usa |
|---|---|
| `/me/consorcios` | `AuthContext` al iniciar sesión |
| `/movimientos/mi-cuenta` | Mi cuenta del propietario (saldo y movimientos) |
| `/departamentos/{id}/cuenta` | Cuenta corriente vista por el admin |
| `/movimientos/cuentas` | Pantalla Cuentas corrientes |
| `/gastos-habituales` | Inicio ("sin cargar este mes") |
| `/periodos/{periodo}/estado` | Cierre de período (las validaciones) |
| `/reportes/estado-financiero` | Reporte |
| `/reportes/gastos/{periodo}` | Reporte e Inicio |
| `/reportes/proveedores` | Reporte |
| `/notificaciones` y `/notificaciones/no-leidas-count` | La campanita |
| `/departamentos/{id}/coeficientes` | Padrón |

**Files:**
- Modify: `backend/export_demo.py`
- Test: `tests/test_export_demo.py`

**Interfaces:**
- Produces: `RUTAS_POR_DEPARTAMENTO: list[str]` — plantillas con `{id}` que se piden una vez por departamento.
- Produces: `RUTAS_POR_PERIODO: list[str]` — plantillas con `{periodo}`.
- Produces: en el JSON, la clave `_generado` con la fecha ISO de generación.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_demo.py
from backend.export_demo import (
    RUTAS_EXPORTADAS,
    RUTAS_POR_DEPARTAMENTO,
    RUTAS_POR_PERIODO,
    exportar,
)


def test_exporta_la_cuenta_corriente_de_cada_departamento():
    # Es la base de "Mi cuenta" del propietario: sin esto la pantalla más
    # importante del circuito de cobranza queda vacía en la demo.
    assert "/departamentos/{id}/cuenta" in RUTAS_POR_DEPARTAMENTO


def test_exporta_el_estado_de_cada_periodo():
    assert "/periodos/{periodo}/estado" in RUTAS_POR_PERIODO


def test_exporta_las_rutas_que_el_recorrido_necesita():
    paths = {p for _rol, p in RUTAS_EXPORTADAS}
    for imprescindible in [
        "/me/consorcios",
        "/movimientos/mi-cuenta",
        "/movimientos/cuentas",
        "/gastos-habituales",
        "/reportes/estado-financiero",
        "/reportes/proveedores",
        "/notificaciones",
        "/notificaciones/no-leidas-count",
    ]:
        assert imprescindible in paths


def test_el_export_deja_la_fecha_de_generacion():
    # Sin esto no se puede calcular cuánto correr las fechas al abrir la demo.
    class _Api:
        def req(self, metodo, path, **kwargs):
            class _R:
                status_code = 200

                @staticmethod
                def json():
                    return []

            return _R()

    datos = exportar(_Api(), "tok", {1: "tok-depto"}, cid=1)
    assert "_generado" in datos
    assert datos["_generado"].count("-") == 2  # ISO: YYYY-MM-DD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_demo.py -v`
Expected: FAIL con `ImportError: cannot import name 'RUTAS_POR_DEPARTAMENTO'`

- [ ] **Step 3: Write minimal implementation**

En `backend/export_demo.py`, agregar a `RUTAS_EXPORTADAS` las rutas sueltas nuevas, y las dos listas de plantillas:

```python
#: Rutas que se piden una vez por departamento. La clave en el JSON lleva el
#: id resuelto (`/departamentos/7/cuenta`), para que el sustituto del navegador
#: las encuentre por el mismo path que pide la pantalla.
RUTAS_POR_DEPARTAMENTO: list[str] = [
    "/departamentos/{id}/cuenta",
    "/departamentos/{id}/coeficientes",
]

#: Ídem por período cerrado.
RUTAS_POR_PERIODO: list[str] = [
    "/periodos/{periodo}/estado",
    "/reportes/gastos/{periodo}",
]
```

Y sumar a `RUTAS_EXPORTADAS`:

```python
    ("admin", "/me/consorcios"),
    ("depto", "/movimientos/mi-cuenta"),
    ("admin", "/movimientos/cuentas"),
    ("admin", "/gastos-habituales"),
    ("admin", "/reportes/estado-financiero"),
    ("admin", "/reportes/proveedores"),
    ("admin", "/notificaciones"),
    ("admin", "/notificaciones/no-leidas-count"),
```

**Ojo con `/movimientos/mi-cuenta`:** es la cuenta del departamento cuyo token se use. Exportarla con el token del departamento **pinneado como "propietario al día"** (`CODIGO_PUNTUAL_FIJO` en `backend/seed_demo.py`), que es el destino del botón del selector. La cuenta de las demás unidades ya viaja en `/departamentos/{id}/cuenta`.

En `exportar()`, después del bucle de rutas sueltas, agregar los dos bucles de plantillas y la fecha:

```python
    for depto in datos.get("/departamentos", []):
        for plantilla in RUTAS_POR_DEPARTAMENTO:
            path = plantilla.format(id=depto["id"])
            r = api.req("GET", path, token=admin_token, cid=cid)
            datos[path] = r.json()

    for periodo in datos.get("/periodos", []):
        for plantilla in RUTAS_POR_PERIODO:
            path = plantilla.format(periodo=periodo["periodo"])
            r = api.req("GET", path, token=admin_token, cid=cid)
            datos[path] = r.json()

    datos["_generado"] = date.today().isoformat()
```

(agregar `from datetime import date` arriba).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_demo.py -v`
Expected: PASS

- [ ] **Step 5: Regenerar el dataset y verificar**

Run: el comando de regeneración de "Global Constraints".

```bash
python -c "
import json
d = json.load(open('frontend/src/demo/dataset.json', encoding='utf-8'))
print('rutas:', len(d))
print('generado:', d['_generado'])
print('cuentas de depto:', sum(1 for k in d if k.endswith('/cuenta')))
mi = d['/movimientos/mi-cuenta']
print('mi-cuenta saldo:', mi['saldo_total'], 'movimientos:', len(mi['movimientos']))
"
```
Expected: 18 cuentas de departamento, `_generado` con la fecha de hoy, y `mi-cuenta` con saldo y movimientos.

- [ ] **Step 6: Commit**

```bash
git add backend/export_demo.py tests/test_export_demo.py frontend/src/demo/dataset.json
git commit -m "feat(demo): exportar cuentas corrientes, reportes y fecha de generacion"
```

---

### Task 2: Correr las fechas del dataset al día de la visita

El dataset se congela con fechas absolutas. Sin esto, en dos meses la demo muestra un edificio al que le faltan meses por cerrar, con reservas pasadas y el propietario "al día" leyéndose como atrasado (§3.3 del spec).

El desplazamiento es **en meses enteros**, no en días: los meses tienen distinta cantidad de días y los períodos son claves de mes.

**Files:**
- Create: `frontend/src/demo/fechas.js`
- Test: `frontend/src/demo/fechas.test.js`

**Interfaces:**
- Produces: `mesesDeDesfase(generadoISO: string, hoy: Date) -> number`
- Produces: `correrFecha(valor: string, meses: number) -> string` — acepta `"YYYY-MM"`, `"YYYY-MM-DD"` y fecha con hora; devuelve el mismo formato.
- Produces: `correrDataset(dataset: object, hoy: Date) -> object` — copia con todas las fechas corridas.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/fechas.test.js
import { describe, it, expect } from "vitest";
import { correrDataset, correrFecha, mesesDeDesfase } from "./fechas";

describe("mesesDeDesfase", () => {
  it("cuenta meses enteros entre la generación y hoy", () => {
    expect(mesesDeDesfase("2026-08-17", new Date(2026, 9, 5))).toBe(2);
  });

  it("cruza el año", () => {
    expect(mesesDeDesfase("2026-11-10", new Date(2027, 0, 3))).toBe(2);
  });

  it("es cero el mismo mes en que se generó", () => {
    expect(mesesDeDesfase("2026-08-17", new Date(2026, 7, 30))).toBe(0);
  });

  it("nunca va para atrás", () => {
    // Un reloj atrasado no debe mandar la demo al pasado.
    expect(mesesDeDesfase("2026-08-17", new Date(2026, 5, 1))).toBe(0);
  });
});

describe("correrFecha", () => {
  it("corre un período YYYY-MM", () => {
    expect(correrFecha("2026-07", 2)).toBe("2026-09");
  });

  it("corre una fecha simple", () => {
    expect(correrFecha("2026-08-10", 2)).toBe("2026-10-10");
  });

  it("conserva la hora", () => {
    expect(correrFecha("2026-09-20T03:00:00", 1)).toBe("2026-10-20T03:00:00");
  });

  it("recorta al último día cuando el mes destino es más corto", () => {
    // 31 de enero + 1 mes no es el 31 de febrero.
    expect(correrFecha("2026-01-31", 1)).toBe("2026-02-28");
  });

  it("deja intacto lo que no es una fecha", () => {
    expect(correrFecha("UF-03C", 2)).toBe("UF-03C");
    expect(correrFecha("", 2)).toBe("");
  });
});

describe("correrDataset", () => {
  const DATASET = {
    _generado: "2026-08-17",
    "/expensas": [
      { id: 1, periodo: "2026-07", fecha_primer_vencimiento: "2026-08-10", monto: 1000 },
    ],
    "/reservas": [{ id: 5, inicio: "2026-09-20T03:00:00" }],
  };

  it("corre las fechas de todas las rutas", () => {
    const corrido = correrDataset(DATASET, new Date(2026, 9, 5));
    expect(corrido["/expensas"][0].periodo).toBe("2026-09");
    expect(corrido["/expensas"][0].fecha_primer_vencimiento).toBe("2026-10-10");
    expect(corrido["/reservas"][0].inicio).toBe("2026-11-20T03:00:00");
  });

  it("no toca los importes ni los identificadores", () => {
    const corrido = correrDataset(DATASET, new Date(2026, 9, 5));
    expect(corrido["/expensas"][0].monto).toBe(1000);
    expect(corrido["/expensas"][0].id).toBe(1);
    expect(corrido["/reservas"][0].id).toBe(5);
  });

  it("no modifica el dataset original", () => {
    correrDataset(DATASET, new Date(2026, 9, 5));
    expect(DATASET["/expensas"][0].periodo).toBe("2026-07");
  });

  it("con desfase cero devuelve los mismos valores", () => {
    const corrido = correrDataset(DATASET, new Date(2026, 7, 30));
    expect(corrido["/expensas"][0].periodo).toBe("2026-07");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/fechas.test.js`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/fechas.js

/** `YYYY-MM` exacto. */
const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;
/** `YYYY-MM-DD`, con hora opcional detrás. */
const FECHA = /^(\d{4})-(\d{2})-(\d{2})(.*)$/;

/**
 * Cuántos meses enteros pasaron entre la generación del dataset y hoy.
 *
 * Nunca devuelve negativo: si el reloj de quien visita está atrasado respecto
 * de la generación, la demo se muestra tal como se generó en vez de viajar al
 * pasado — un dataset con fechas hacia atrás se vería peor que uno viejo.
 */
export function mesesDeDesfase(generadoISO, hoy) {
  const [anio, mes] = generadoISO.split("-").map(Number);
  const meses = (hoy.getFullYear() - anio) * 12 + (hoy.getMonth() + 1 - mes);
  return Math.max(0, meses);
}

/** Último día del mes (1-12) de un año dado. */
function ultimoDia(anio, mes) {
  return new Date(anio, mes, 0).getDate();
}

/**
 * Corre `valor` hacia adelante `meses` meses, conservando su formato.
 *
 * El desplazamiento es en MESES ENTEROS, no en días: los períodos son claves
 * de mes (`2026-07`) y sumarles una cantidad fija de días los rompería. Cuando
 * el día no existe en el mes destino (un 31 que cae en febrero) se recorta al
 * último día, que es la convención de cualquier calendario.
 *
 * Lo que no parece una fecha vuelve intacto: el dataset tiene códigos de
 * unidad, descripciones y montos, y este módulo no puede distinguirlos por
 * contexto — sólo por forma.
 */
export function correrFecha(valor, meses) {
  if (typeof valor !== "string" || meses === 0) return valor;

  if (PERIODO.test(valor)) {
    const [anio, mes] = valor.split("-").map(Number);
    const total = (anio * 12 + (mes - 1)) + meses;
    return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
  }

  const m = FECHA.exec(valor);
  if (!m) return valor;
  const [, anioStr, mesStr, diaStr, resto] = m;
  const total = (Number(anioStr) * 12 + (Number(mesStr) - 1)) + meses;
  const anioDestino = Math.floor(total / 12);
  const mesDestino = (total % 12) + 1;
  const dia = Math.min(Number(diaStr), ultimoDia(anioDestino, mesDestino));
  return `${anioDestino}-${String(mesDestino).padStart(2, "0")}-${String(dia).padStart(2, "0")}${resto}`;
}

/**
 * Copia del dataset con todas sus fechas corridas al día de la visita.
 *
 * Recorre en profundidad y aplica `correrFecha` a cada string. Los importes,
 * los identificadores y los textos quedan intactos porque no matchean el
 * formato de fecha.
 *
 * Los intereses y recargos NO se recalculan: viajan tal cual, como decidió el
 * spec (§3.3). En pantalla es indistinguible, porque lo que se muestra es un
 * importe y no una cuenta.
 */
export function correrDataset(dataset, hoy) {
  const meses = mesesDeDesfase(dataset._generado, hoy);
  if (meses === 0) return structuredClone(dataset);

  const correr = (valor) => {
    if (typeof valor === "string") return correrFecha(valor, meses);
    if (Array.isArray(valor)) return valor.map(correr);
    if (valor && typeof valor === "object") {
      return Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, correr(v)]));
    }
    return valor;
  };

  return correr(dataset);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/fechas.test.js`
Expected: PASS (13 tests)

- [ ] **Step 5: Verificar contra el dataset real**

El dataset es un módulo ESM del proyecto, así que la verificación va como test —no con `node` suelto—. Agregar al final de `frontend/src/demo/fechas.test.js`:

```javascript
// frontend/src/demo/fechas.test.js — al final
import DATASET_REAL from "./dataset.json";

describe("sobre el dataset real", () => {
  it("el último período queda siempre en el mes pasado, por lejos que se mire", () => {
    const hoy = new Date(2027, 2, 15); // marzo de 2027, siete meses después
    const corrido = correrDataset(DATASET_REAL, hoy);
    const periodos = [...new Set(corrido["/expensas"].map((e) => e.periodo))].sort();
    expect(periodos[periodos.length - 1]).toBe("2027-02");
  });

  it("conserva la cantidad de expensas y sus importes", () => {
    const corrido = correrDataset(DATASET_REAL, new Date(2027, 2, 15));
    expect(corrido["/expensas"]).toHaveLength(DATASET_REAL["/expensas"].length);
    expect(corrido["/expensas"][0].monto_primer_vencimiento).toBe(
      DATASET_REAL["/expensas"][0].monto_primer_vencimiento,
    );
  });
});
```

Run: `cd frontend && npx vitest run src/demo/fechas.test.js`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/demo/fechas.js frontend/src/demo/fechas.test.js
git commit -m "feat(demo): correr las fechas del dataset al dia de la visita"
```

---

### Task 3: El estado del navegador

Carga el dataset, le aplica el desplazamiento una sola vez al arrancar, y lo expone para que las rutas lo consulten.

**Files:**
- Create: `frontend/src/demo/estado.js`
- Test: `frontend/src/demo/estado.test.js`

**Interfaces:**
- Consumes: `correrDataset` de la Task 2.
- Produces: `crearEstado(dataset, hoy) -> {leer(path), reiniciar()}`

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/estado.test.js
import { describe, it, expect } from "vitest";
import { crearEstado } from "./estado";

const DATASET = {
  _generado: "2026-08-17",
  "/departamentos": [{ id: 1, codigo: "UF-01A" }],
  "/expensas": [{ id: 9, periodo: "2026-07" }],
};

describe("crearEstado", () => {
  it("lee una ruta del dataset", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    expect(estado.leer("/departamentos")).toEqual([{ id: 1, codigo: "UF-01A" }]);
  });

  it("devuelve undefined para una ruta que no está", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    expect(estado.leer("/no-existe")).toBeUndefined();
  });

  it("aplica el desplazamiento de fechas al cargar", () => {
    const estado = crearEstado(DATASET, new Date(2026, 9, 5));
    expect(estado.leer("/expensas")[0].periodo).toBe("2026-09");
  });

  it("no comparte referencias con el dataset original", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    estado.leer("/departamentos")[0].codigo = "MODIFICADO";
    expect(DATASET["/departamentos"][0].codigo).toBe("UF-01A");
  });

  it("reiniciar vuelve al estado del arranque", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    estado.leer("/departamentos")[0].codigo = "MODIFICADO";
    estado.reiniciar();
    expect(estado.leer("/departamentos")[0].codigo).toBe("UF-01A");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/estado.test.js`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/estado.js
import { correrDataset } from "./fechas";

/**
 * Estado en memoria de la demo, sembrado con el dataset ya corrido al día de
 * la visita.
 *
 * `reiniciar()` existe para el botón "reiniciar demo" del aviso superior: como
 * el estado vive en memoria y no se persiste (spec §2.3), volver al arranque
 * es recargar la copia original.
 */
export function crearEstado(dataset, hoy) {
  const inicial = correrDataset(dataset, hoy);
  let actual = structuredClone(inicial);

  return {
    leer(path) {
      return actual[path];
    },
    reiniciar() {
      actual = structuredClone(inicial);
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/estado.test.js`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/estado.js frontend/src/demo/estado.test.js
git commit -m "feat(demo): estado en memoria sembrado con el dataset corrido"
```

---

### Task 4: El enrutador y la entrada única

Traduce un pedido (método, path) en una respuesta con la forma de `apiFetch`. Acá viven los filtros por query string que las pantallas usan (período, departamento, estado) y las rutas con identificador en el medio.

**Files:**
- Create: `frontend/src/demo/rutas.js`
- Create: `frontend/src/demo/servidor.js`
- Test: `frontend/src/demo/servidor.test.js`

**Interfaces:**
- Consumes: `crearEstado` de la Task 3.
- Produces: `responder(estado, method, path, body) -> {ok, status, data}`

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/servidor.test.js
import { describe, it, expect, beforeEach } from "vitest";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

const DATASET = {
  _generado: "2026-08-17",
  "/departamentos": [
    { id: 1, codigo: "UF-01A" },
    { id: 2, codigo: "UF-01B" },
  ],
  "/expensas": [
    { id: 9, departamento_id: 1, periodo: "2026-07", estado_calculado: "pagada" },
    { id: 10, departamento_id: 2, periodo: "2026-07", estado_calculado: "vencida" },
    { id: 11, departamento_id: 1, periodo: "2026-06", estado_calculado: "pagada" },
  ],
  "/departamentos/1/cuenta": { saldo_total: 0, movimientos: [] },
};

let estado;
beforeEach(() => {
  estado = crearEstado(DATASET, new Date(2026, 7, 20));
});

describe("responder", () => {
  it("devuelve una lista con la forma de apiFetch", () => {
    const r = responder(estado, "GET", "/departamentos");
    expect(r.ok).toBe(true);
    expect(r.status).toBe(200);
    expect(r.data).toHaveLength(2);
  });

  it("resuelve una ruta con identificador en el medio", () => {
    const r = responder(estado, "GET", "/departamentos/1/cuenta");
    expect(r.status).toBe(200);
    expect(r.data.saldo_total).toBe(0);
  });

  it("filtra por período", () => {
    const r = responder(estado, "GET", "/expensas?periodo=2026-07");
    expect(r.data).toHaveLength(2);
  });

  it("filtra por departamento", () => {
    const r = responder(estado, "GET", "/expensas?departamento_id=1");
    expect(r.data).toHaveLength(2);
  });

  it("combina filtros", () => {
    const r = responder(estado, "GET", "/expensas?periodo=2026-07&departamento_id=1");
    expect(r.data).toHaveLength(1);
    expect(r.data[0].id).toBe(9);
  });

  it("ignora un filtro que la ruta no conoce, en vez de devolver vacío", () => {
    // Una pantalla puede mandar un parámetro que este sustituto no implementa;
    // devolver la lista completa es preferible a una pantalla vacía sin causa.
    const r = responder(estado, "GET", "/expensas?ordenar_por=monto");
    expect(r.data).toHaveLength(3);
  });

  it("devuelve 501 explicativo ante una ruta desconocida", () => {
    const r = responder(estado, "GET", "/rutaquenoexiste");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(501);
    expect(r.data.detail).toContain("/rutaquenoexiste");
  });

  it("devuelve 501 ante una escritura, que es el Plan B2", () => {
    const r = responder(estado, "POST", "/gastos", { monto: 1 });
    expect(r.status).toBe(501);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/servidor.test.js`
Expected: FAIL — el módulo no existe.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/rutas.js

/**
 * Filtros por query string que las pantallas usan sobre las listas.
 *
 * Cada entrada es `nombre del parámetro` → cómo comparar contra el elemento.
 * Un parámetro que no esté acá se ignora: devolver la lista completa es
 * preferible a devolver vacío, porque una pantalla vacía se lee como "no hay
 * datos" y manda a buscar el problema al lugar equivocado.
 */
const FILTROS = {
  periodo: (item, valor) => item.periodo === valor,
  departamento_id: (item, valor) => String(item.departamento_id) === valor,
  estado: (item, valor) => item.estado === valor || item.estado_calculado === valor,
  solo_deudores: () => true, // el dataset de morosos ya viene filtrado
};

export function aplicarFiltros(lista, params) {
  if (!Array.isArray(lista)) return lista;
  let resultado = lista;
  for (const [clave, valor] of params.entries()) {
    const filtro = FILTROS[clave];
    if (filtro) resultado = resultado.filter((item) => filtro(item, valor));
  }
  return resultado;
}
```

```javascript
// frontend/src/demo/servidor.js
import { aplicarFiltros } from "./rutas";

/**
 * Responde un pedido desde el estado en memoria, con la misma forma que
 * devuelve `apiFetch` contra el servidor real: `{ok, status, data}`.
 *
 * Las lecturas se resuelven por coincidencia exacta de path contra las claves
 * del dataset — que se exportaron con el mismo path que piden las pantallas,
 * incluidas las que llevan un identificador en el medio. Por eso no hace falta
 * un enrutador con patrones: el generador ya resolvió los ids.
 */
export function responder(estado, method, path, body) {
  const [ruta, qs] = path.split("?");
  const params = new URLSearchParams(qs ?? "");

  if (method !== "GET") {
    return noImplementado(method, ruta, "las escrituras llegan en el Plan B2");
  }

  const datos = estado.leer(ruta);
  if (datos === undefined) {
    return noImplementado(method, ruta, "no está en el dataset exportado");
  }

  return { ok: true, status: 200, data: aplicarFiltros(datos, params) };
}

function noImplementado(method, ruta, motivo) {
  if (import.meta.env?.DEV) {
    console.error(`[demo] sin implementar: ${method} ${ruta} — ${motivo}`);
  }
  return {
    ok: false,
    status: 501,
    data: { detail: `La demo no implementa ${method} ${ruta}: ${motivo}.` },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/servidor.test.js`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/rutas.js frontend/src/demo/servidor.js frontend/src/demo/servidor.test.js
git commit -m "feat(demo): enrutador y entrada unica del sustituto del servidor"
```

---

### Task 5: Enganchar el sustituto en el único punto por donde pasa todo

`apiFetch` es el punto por donde pasan las 142 llamadas del frontend. Con la bandera de demo encendida, deriva al sustituto en vez de salir a la red. Ninguna pantalla cambia.

**Files:**
- Modify: `frontend/src/api/client.js`
- Create: `frontend/src/demo/index.js`
- Test: `frontend/src/api/client.test.js`

**Interfaces:**
- Consumes: `responder` (Task 4), `crearEstado` (Task 3), el dataset.
- Produces: `responderDemo(method, path, body)` — envuelve el estado ya creado.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/api/client.test.js
import { describe, it, expect, vi, beforeEach } from "vitest";

describe("apiFetch en modo demo", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("no sale a la red: responde desde el dataset", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const { apiFetch } = await import("./client");
    const r = await apiFetch("/departamentos");
    expect(fetch).not.toHaveBeenCalled();
    expect(r.ok).toBe(true);
    expect(Array.isArray(r.data)).toBe(true);
    expect(r.data.length).toBeGreaterThan(0);
  });

  it("con la bandera apagada sale a la red como siempre", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    fetch.mockResolvedValue({ ok: true, status: 200, text: async () => "[]" });
    const { apiFetch } = await import("./client");
    await apiFetch("/departamentos");
    expect(fetch).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/client.test.js`
Expected: FAIL — sale a la red en los dos casos.

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/demo/index.js
import DATASET from "./dataset.json";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

const estado = crearEstado(DATASET, new Date());

export function responderDemo(method, path, body) {
  return responder(estado, method, path, body);
}

export function reiniciarDemo() {
  estado.reiniciar();
}
```

En `frontend/src/api/client.js`, al principio de `apiFetch`, antes de armar los headers:

```javascript
  // En modo demo no hay servidor: el sustituto responde desde un dataset
  // estático en memoria. La importación es dinámica para que ni el módulo ni
  // el dataset entren en el bundle que recibe un cliente real.
  if (import.meta.env.VITE_DEMO_MODE === "true") {
    const { responderDemo } = await import("../demo/index.js");
    return responderDemo(method, path, body);
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api/client.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Verificar que el sustituto NO entra al bundle de producción**

```bash
cd frontend && npm run build && grep -c "demo-comprobantes\|_generado" dist/assets/*.js || echo "0 — el dataset no está en el bundle de produccion"
```
Expected: `0`. Si aparece, la importación dinámica no está funcionando como separación y hay que revisarla antes de seguir.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.js frontend/src/api/client.test.js frontend/src/demo/index.js
git commit -m "feat(demo): apiFetch deriva al sustituto cuando la bandera esta encendida"
```

---

### Task 6: Entrar a la demo sin backend

La pantalla de entrada llama a `/auth/demo-login`, que hoy responde el servidor. Sin backend hay que resolverla en el sustituto: devolver un usuario y un token de mentira según el perfil elegido, con la forma que espera `AuthContext`.

**Files:**
- Modify: `frontend/src/demo/servidor.js`
- Modify: `frontend/src/demo/rutas.js`
- Test: `frontend/src/demo/servidor.test.js`

**Interfaces:**
- Produces: en `rutas.js`, `PERFILES_DEMO` — los tres perfiles del selector con su usuario.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/servidor.test.js — agregar
describe("entrada a la demo", () => {
  it("responde el login de cada perfil con la forma que espera la app", () => {
    for (const rol of ["administracion", "propietario_al_dia", "propietario_moroso"]) {
      const r = responder(estado, "POST", "/auth/demo-login", { rol });
      expect(r.status).toBe(200);
      expect(r.data.access_token).toBeTruthy();
      expect(r.data.user.rol).toMatch(/administracion|departamento/);
    }
  });

  it("el propietario al día y el moroso son departamentos distintos", () => {
    const alDia = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_al_dia" });
    const moroso = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_moroso" });
    expect(alDia.data.user.departamento_id).not.toBe(moroso.data.user.departamento_id);
  });

  it("un perfil desconocido devuelve 400", () => {
    const r = responder(estado, "POST", "/auth/demo-login", { rol: "intruso" });
    expect(r.status).toBe(400);
  });

  it("devuelve el consorcio del dataset en /me/consorcios", () => {
    const r = responder(estado, "GET", "/me/consorcios");
    expect(r.status).toBe(200);
  });
});
```

Agregar al `DATASET` del archivo de test:

```javascript
  "/me/consorcios": [{ id: 1, nombre: "Edificio Libertador" }],
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/servidor.test.js`
Expected: FAIL — el login devuelve 501.

- [ ] **Step 3: Write minimal implementation**

En `rutas.js`:

```javascript
/**
 * Los tres perfiles del selector de entrada. No hay autenticación real: el
 * token es un rótulo, y la identidad la resuelve este mapa. Los códigos de
 * unidad coinciden con los que el generador pinnea (`CODIGO_PUNTUAL_FIJO` y
 * `CODIGO_MOROSO_FIJO` en `backend/seed_demo.py`).
 */
export const PERFILES_DEMO = {
  administracion: { rol: "administracion", departamento_id: null, codigo: null },
  propietario_al_dia: { rol: "departamento", codigo: "UF-01A" },
  propietario_moroso: { rol: "departamento", codigo: "UF-03C" },
};
```

En `servidor.js`, agregar `PERFILES_DEMO` al import que ya trae `aplicarFiltros`:

```javascript
import { aplicarFiltros, PERFILES_DEMO } from "./rutas";
```

Y antes del rechazo de escrituras:

```javascript
  if (method === "POST" && ruta === "/auth/demo-login") {
    const perfil = PERFILES_DEMO[body?.rol];
    if (!perfil) {
      return { ok: false, status: 400, data: { detail: "Perfil de demo desconocido." } };
    }
    const deptos = estado.leer("/departamentos") ?? [];
    const depto = perfil.codigo ? deptos.find((d) => d.codigo === perfil.codigo) : null;
    return {
      ok: true,
      status: 200,
      data: {
        access_token: `demo-${body.rol}`,
        token_type: "bearer",
        expires_in: 3600,
        user: {
          id: depto ? depto.id : 1,
          email: depto ? `uf${depto.codigo}@demo.local` : "admin@demo.local",
          rol: perfil.rol,
          departamento_id: depto ? depto.id : null,
        },
      },
    };
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/servidor.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/servidor.js frontend/src/demo/rutas.js frontend/src/demo/servidor.test.js
git commit -m "feat(demo): entrada a la demo resuelta sin backend"
```

---

### Task 7: La cuenta del propietario responde según quién entró

`/movimientos/mi-cuenta` devuelve la cuenta del departamento que pide. En el dataset se exportó **una sola**: la del propietario al día. Cuando entra el moroso tiene que ver la suya, que viaja en `/departamentos/{id}/cuenta`.

**Files:**
- Modify: `frontend/src/demo/servidor.js`
- Test: `frontend/src/demo/servidor.test.js`

**Interfaces:**
- Produces: `responder` acepta un cuarto argumento `sesion` con el departamento activo.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/servidor.test.js — agregar
describe("mi cuenta según quién entró", () => {
  it("devuelve la cuenta del departamento de la sesión", () => {
    const r = responder(estado, "GET", "/movimientos/mi-cuenta", null, { departamento_id: 1 });
    expect(r.status).toBe(200);
    expect(r.data.saldo_total).toBe(0);
  });

  it("sin sesión de departamento devuelve 403, como el backend", () => {
    const r = responder(estado, "GET", "/movimientos/mi-cuenta", null, { departamento_id: null });
    expect(r.status).toBe(403);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/servidor.test.js`
Expected: FAIL — devuelve la cuenta exportada, sin mirar la sesión.

- [ ] **Step 3: Write minimal implementation**

En `servidor.js`, antes de la lectura genérica:

```javascript
  if (ruta === "/movimientos/mi-cuenta") {
    if (!sesion?.departamento_id) {
      return { ok: false, status: 403, data: { detail: "Sólo para departamentos." } };
    }
    const cuenta = estado.leer(`/departamentos/${sesion.departamento_id}/cuenta`);
    if (!cuenta) {
      return noImplementado(method, ruta, "falta la cuenta de ese departamento en el dataset");
    }
    return { ok: true, status: 200, data: cuenta };
  }
```

Y cambiar la firma a `responder(estado, method, path, body, sesion)`.

En `frontend/src/demo/index.js`, guardar la sesión que devolvió el login y pasarla:

```javascript
let sesion = { departamento_id: null };

export function responderDemo(method, path, body) {
  const r = responder(estado, method, path, body, sesion);
  if (method === "POST" && path === "/auth/demo-login" && r.ok) {
    sesion = { departamento_id: r.data.user.departamento_id };
  }
  return r;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/servidor.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/demo/servidor.js frontend/src/demo/index.js frontend/src/demo/servidor.test.js
git commit -m "feat(demo): mi-cuenta responde segun el departamento de la sesion"
```

---

### Task 8: Recorrer la demo entera y tapar los agujeros

Las tareas anteriores construyeron el mecanismo. Esta comprueba que **el recorrido completo carga**, y cubre lo que aparezca faltando.

**Files:**
- Create: `frontend/src/demo/recorrido.test.js`
- Modify: lo que haga falta según lo que falle.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/demo/recorrido.test.js
import { describe, it, expect, beforeEach } from "vitest";
import DATASET from "./dataset.json";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

/**
 * Cada ruta que las pantallas del recorrido de venta consultan al cargar.
 * Si una devuelve 501, la pantalla correspondiente muestra un cartel de error
 * en la demo publicada — por eso esta lista es la red de contención del plan.
 */
const RECORRIDO = [
  ["/me/consorcios", "AuthContext al entrar"],
  ["/departamentos", "varias"],
  ["/expensas", "Cobranzas"],
  ["/comprobantes", "Cobranzas"],
  ["/periodos", "Historial de cierres"],
  ["/gastos", "Gastos"],
  ["/gastos-habituales", "Inicio"],
  ["/comunicados", "Comunicados"],
  ["/peticiones", "Peticiones"],
  ["/reservas", "Reservas"],
  ["/amenities", "Reservas"],
  ["/trabajos", "Trabajos"],
  ["/proveedores", "Reporte de proveedores"],
  ["/clases-prorrateo", "formulario de gasto"],
  ["/cajas", "Tesorería"],
  ["/estado-financiero", "Inicio y Tesorería"],
  ["/configuracion", "Configuración"],
  ["/movimientos/cuentas", "Cuentas corrientes"],
  ["/reportes/morosos", "Inicio y reporte"],
  ["/reportes/estado-financiero", "Reporte"],
  ["/reportes/proveedores", "Reporte"],
  ["/notificaciones", "campanita"],
  ["/notificaciones/no-leidas-count", "campanita"],
];

let estado;
beforeEach(() => {
  estado = crearEstado(DATASET, new Date());
});

describe("el recorrido de venta carga entero", () => {
  it.each(RECORRIDO)("%s (%s) responde 200", (ruta) => {
    const r = responder(estado, "GET", ruta, null, { departamento_id: 1 });
    expect(r.status, `${ruta} devolvió ${r.status}: ${JSON.stringify(r.data)}`).toBe(200);
  });

  it("mi cuenta del propietario trae saldo y movimientos", () => {
    const login = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_al_dia" });
    const r = responder(estado, "GET", "/movimientos/mi-cuenta", null, {
      departamento_id: login.data.user.departamento_id,
    });
    expect(r.status).toBe(200);
    expect(r.data.movimientos.length).toBeGreaterThan(0);
  });

  it("el estado del último período responde, que es lo que mira Cierre", () => {
    const periodos = estado.leer("/periodos");
    const ultimo = periodos[0].periodo;
    const r = responder(estado, "GET", `/periodos/${ultimo}/estado`);
    expect(r.status).toBe(200);
  });

  it("cada expensa con PDF apunta a un archivo declarado en el mapa", () => {
    const pdfs = DATASET._pdfs ?? {};
    expect(Object.keys(pdfs).length).toBeGreaterThan(0);
    for (const nombre of Object.values(pdfs)) {
      expect(nombre).toMatch(/^expensa-\d+\.pdf$/);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/demo/recorrido.test.js`
Expected: FAIL en las rutas que el dataset no tenga. **Anotá cuáles**: son el trabajo real de esta tarea.

- [ ] **Step 3: Cubrir lo que falte**

Para cada ruta en rojo, decidir dónde corresponde el arreglo:

- **Falta en el dataset** → agregarla a `RUTAS_EXPORTADAS` (o a las plantillas) en `backend/export_demo.py` y regenerar. Es lo más probable y lo preferible: el dato viene del backend real.
- **Está pero con otro path** (por ejemplo con query string obligatoria) → normalizar en `servidor.js`.
- **Es derivable de otra** (por ejemplo un contador que sale de contar una lista) → resolverla en `servidor.js` sin tocar el export, y documentar por qué.

**No inventes datos.** Si una ruta no está en el dataset y no es derivable, la respuesta correcta es exportarla, no fabricar un cuerpo plausible.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/demo/recorrido.test.js`
Expected: PASS — las 23 rutas en 200.

- [ ] **Step 5: Correr toda la suite del frontend**

Run: `cd frontend && npm test`
Expected: los 59 tests previos siguen pasando, más los nuevos.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/demo backend/export_demo.py frontend/src/demo/dataset.json
git commit -m "test(demo): el recorrido de venta carga entero sin backend"
```

---

## Verificación manual antes de dar el plan por terminado

Levantar la demo **sin backend corriendo** y recorrerla con los ojos:

```bash
cd frontend && VITE_DEMO_MODE=true npm run dev
```

Con el backend **apagado**, entrar y verificar:

1. **Entrar como Administración** y recorrer Inicio, Cobranzas (las tres pestañas), Gastos, Tesorería y los cuatro reportes. Ninguna pantalla debe mostrar cartel de error ni quedarse cargando.
2. **La pestaña de red del navegador no debe mostrar ningún pedido a `localhost:8000`.** Si aparece uno, el enganche tiene un agujero.
3. **Entrar como Propietario al día** → Mi cuenta: saldo, expensas, comprobantes con sus imágenes, y movimientos.
4. **Entrar como Propietario moroso** → su cuenta tiene que ser distinta, con recargos e intereses.
5. **Abrir el PDF de una boleta** desde Mi cuenta.
6. **Adelantar el reloj del sistema dos meses** y recargar: los períodos tienen que haberse corrido, el último cierre debe seguir siendo el mes pasado y el vencimiento a pocos días.

El punto 6 es el que prueba que la demo no envejece, y es el único que no puede verificarse con tests automáticos.
