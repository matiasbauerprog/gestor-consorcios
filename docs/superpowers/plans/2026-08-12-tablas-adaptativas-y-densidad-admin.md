# Tablas adaptativas y densidad en administración — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que ninguna tabla de la app necesite scroll horizontal en ningún ancho, y que las pantallas que hoy muestran tarjetas en desktop aprovechen el espacio.

**Architecture:** Un único componente `TablaResponsive` administra un modelo de columnas con prioridad. Las columnas se reparten el ancho con `table-layout: fixed` + `<colgroup>`, y las de menor prioridad se ocultan por `@container` (no `@media`) a medida que el contenedor se angosta, reapareciendo en una fila de detalle expandible. El corte tarjetas↔tabla sigue en JS. Todo el trabajo es frontend.

**Tech Stack:** React 19, Vite 8, CSS plano con custom properties. Se agrega Vitest 3 + React Testing Library + jsdom, que hoy no existen en el proyecto.

**Spec:** `docs/superpowers/specs/2026-08-12-tablas-adaptativas-y-densidad-admin-design.md`

## Global Constraints

- **Mobile-first.** CSS base para ≥320px; mejoras con `@media (min-width: …)`, nunca `max-width`. Breakpoints del proyecto: 600px (tablet) y 960px (desktop). Ver `.claude/rules/frontend.md`.
- **Cero colores hardcodeados.** Todo color va por `var(--color-…)`. Está prohibido escribir hex/rgb dentro de componentes.
- **HTML semántico.** Nada de `<div onClick>`; todo control es `<button>`. Un solo `<main>` por pantalla.
- **Targets táctiles ≥44px de alto** en mobile.
- **Sin overflow horizontal.** `document.documentElement.scrollWidth === clientWidth` en toda pantalla tocada.
- **Anchos verificados:** 375px, 768px, 1024px, 1440px. El de 375px es innegociable — es el que revisa el usuario.
- **Backend intocable.** `pytest -v` debe seguir verde sin que nadie lo mire.
- **El lint NO parte de cero.** Baseline medido en `master` el 2026-08-12: **87 problemas (69 errores, 18 warnings)** — 45 `react-hooks/set-state-in-effect`, 21 `react-hooks/exhaustive-deps`, 1 `react-refresh/only-export-components`. Son preexistentes y **no se arreglan en este plan**. El criterio en cada tarea es **no agregar problemas nuevos**: si `npm run lint` sube de 87, hay que mirarlo; si se mantiene o baja, está bien. Nunca interpretar el conteo distinto de cero como una falla de la tarea.
- **Escalones de `@container`** (idénticos en todo el plan, container name `tabla`): prioridad 3 se oculta bajo 1000px, prioridad 2 bajo 760px. Prioridad 1 nunca se oculta.
- **Anchos de columna: `auto`, longitudes (`ch`, `rem`) o porcentajes. Nunca `fr`** — es una unidad de grid y en un `<col>` el navegador la descarta sin avisar. Montos, fechas y columnas de acciones siempre en `ch`/`rem` para que no puedan quedar recortadas.
- **Commits en español**, tiempo presente, prefijo `feat:` / `fix:` / `refactor:` / `test:` / `chore:`.

---

## File Structure

**Se crean:**

| Archivo | Responsabilidad |
|---|---|
| `frontend/vitest.config.js` | Config de Vitest: entorno jsdom, archivo de setup |
| `frontend/src/test/setup.js` | Stub de `matchMedia` (jsdom no lo implementa) + matchers de jest-dom |
| `frontend/src/components/TablaResponsive.jsx` | El motor: modelo de columnas, colgroup, fila de detalle, chevron |
| `frontend/src/components/TablaResponsive.test.jsx` | Tests del motor |
| `frontend/src/components/MenuAcciones.jsx` | Menú `⋯` con teclado y click afuera |
| `frontend/src/components/MenuAcciones.test.jsx` | Tests del menú |
| `frontend/src/utils/tiempoRelativo.js` | `formatearTiempoRelativo(fecha, ahora)` |
| `frontend/src/utils/tiempoRelativo.test.js` | Tests del helper |

**Se borra:** `frontend/src/components/ListaResponsive.jsx` (reemplazado por `TablaResponsive`).

**Se modifican:** `frontend/src/index.css`, `frontend/package.json`, `frontend/src/components/Campanita.jsx` y 14 pantallas en `frontend/src/screens/`.

---

### Task 1: Infraestructura de tests

El frontend no tiene ningún sistema de tests. Esta tarea lo instala y lo prueba con un test trivial. Sin esto, ninguna tarea siguiente puede correr.

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/test/setup.js`
- Create: `frontend/src/utils/tiempoRelativo.js`
- Create: `frontend/src/utils/tiempoRelativo.test.js`

**Interfaces:**
- Consumes: nada.
- Produces: comando `npm test` (una sola corrida, sin watch) y `npm run test:watch`. `formatearTiempoRelativo(fecha: Date | string, ahora?: Date): string` exportado desde `src/utils/tiempoRelativo.js`.

- [ ] **Step 1: Instalar las dependencias**

```bash
cd frontend
npm install -D vitest@^3 jsdom@^26 @testing-library/react@^16 @testing-library/user-event@^14 @testing-library/jest-dom@^6
```

- [ ] **Step 2: Agregar los scripts a `frontend/package.json`**

En el bloque `"scripts"`, después de `"lint"`:

```json
    "test": "vitest run",
    "test:watch": "vitest",
```

- [ ] **Step 3: Crear `frontend/vitest.config.js`**

```js
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
  },
});
```

- [ ] **Step 4: Crear `frontend/src/test/setup.js`**

jsdom no implementa `window.matchMedia`, y `useEsTablet` (`src/hooks/useBreakpoint.js:24`) lo llama en todo render. Sin este stub, cualquier test que monte una tabla explota con `matchMedia is not a function`.

```js
import "@testing-library/jest-dom/vitest";
import { beforeEach, vi } from "vitest";

/** Ancho simulado del viewport. Los tests lo cambian con `setAnchoViewport`. */
let anchoActual = 1440;

export function setAnchoViewport(px) {
  anchoActual = px;
}

/** Resuelve `(min-width: Npx)` y `(max-width: Npx)` contra `anchoActual`.
 *  Alcanza para `useMediaQuery`, que es el único consumidor en la app. */
function evaluar(query) {
  const min = query.match(/min-width:\s*(\d+)px/);
  if (min) return anchoActual >= Number(min[1]);
  const max = query.match(/max-width:\s*(\d+)px/);
  if (max) return anchoActual <= Number(max[1]);
  return false;
}

beforeEach(() => {
  anchoActual = 1440;
});

vi.stubGlobal("matchMedia", (query) => ({
  matches: evaluar(query),
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
}));
```

- [ ] **Step 5: Escribir el test que falla del helper de tiempo relativo**

Crear `frontend/src/utils/tiempoRelativo.test.js`:

```js
import { describe, it, expect } from "vitest";
import { formatearTiempoRelativo } from "./tiempoRelativo";

const AHORA = new Date("2026-08-12T15:00:00Z");

describe("formatearTiempoRelativo", () => {
  it("dice 'recién' para menos de un minuto", () => {
    expect(formatearTiempoRelativo("2026-08-12T14:59:30Z", AHORA)).toBe("recién");
  });

  it("cuenta minutos", () => {
    expect(formatearTiempoRelativo("2026-08-12T14:48:00Z", AHORA)).toBe("hace 12 min");
  });

  it("usa singular en la hora exacta", () => {
    expect(formatearTiempoRelativo("2026-08-12T14:00:00Z", AHORA)).toBe("hace 1 h");
  });

  it("cuenta horas", () => {
    expect(formatearTiempoRelativo("2026-08-12T12:00:00Z", AHORA)).toBe("hace 3 h");
  });

  it("dice 'ayer' entre 24 y 48 horas", () => {
    expect(formatearTiempoRelativo("2026-08-11T15:00:00Z", AHORA)).toBe("ayer");
  });

  it("cuenta días hasta la semana", () => {
    expect(formatearTiempoRelativo("2026-08-08T15:00:00Z", AHORA)).toBe("hace 4 días");
  });

  it("pasa a fecha corta después de una semana", () => {
    expect(formatearTiempoRelativo("2026-07-30T15:00:00Z", AHORA)).toBe("30/07/2026");
  });

  it("no rompe con una fecha inválida", () => {
    expect(formatearTiempoRelativo("no es una fecha", AHORA)).toBe("—");
  });
});
```

- [ ] **Step 6: Correr el test y verificar que falla**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./tiempoRelativo"`.

- [ ] **Step 7: Escribir la implementación mínima**

Crear `frontend/src/utils/tiempoRelativo.js`:

```js
const MINUTO = 60_000;
const HORA = 60 * MINUTO;
const DIA = 24 * HORA;

/**
 * Antigüedad de `fecha` en castellano coloquial: "recién", "hace 12 min",
 * "hace 3 h", "ayer", "hace 4 días", y de una semana en adelante la fecha corta.
 * `ahora` es inyectable para que los tests no dependan del reloj.
 */
export function formatearTiempoRelativo(fecha, ahora = new Date()) {
  const d = fecha instanceof Date ? fecha : new Date(fecha);
  if (Number.isNaN(d.getTime())) return "—";

  const delta = ahora.getTime() - d.getTime();
  if (delta < MINUTO) return "recién";
  if (delta < HORA) return `hace ${Math.floor(delta / MINUTO)} min`;
  if (delta < DIA) return `hace ${Math.floor(delta / HORA)} h`;
  if (delta < 2 * DIA) return "ayer";
  if (delta < 7 * DIA) return `hace ${Math.floor(delta / DIA)} días`;

  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}
```

- [ ] **Step 8: Correr los tests y verificar que pasan**

Run: `cd frontend && npm test`
Expected: PASS — 8 tests.

- [ ] **Step 9: Verificar que el build sigue funcionando**

Run: `cd frontend && npm run build && npm run lint`
Expected: el build termina sin errores (Vitest no debe haber roto la config de Vite). El lint termina en `✖ 87 problems` o menos — baseline preexistente de master, no una falla de esta tarea.

- [ ] **Step 10: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.js frontend/src/test/setup.js frontend/src/utils/tiempoRelativo.js frontend/src/utils/tiempoRelativo.test.js
git commit -m "test: instalar vitest y agregar helper de tiempo relativo"
```

---

### Task 2: `TablaResponsive` — modelo de columnas y anchos

Renombra `ListaResponsive` y le agrega el `<colgroup>`. Todavía no oculta nada: esta tarea solo cambia cómo se reparte el ancho.

**Files:**
- Create: `frontend/src/components/TablaResponsive.jsx`
- Create: `frontend/src/components/TablaResponsive.test.jsx`
- Delete: `frontend/src/components/ListaResponsive.jsx`
- Modify: `frontend/src/screens/Expensas.jsx` (import), `Comprobantes.jsx` (import), `Gastos.jsx` (import), `Reservas.jsx` (import)
- Modify: `frontend/src/index.css:2797-2813`

**Interfaces:**
- Consumes: `useEsTablet` de `../hooks/useBreakpoint`.
- Produces: `<TablaResponsive columnas filas claveFila renderTarjeta vacio />` (export default). Cada columna: `{ clave: string, titulo: string, celda: (fila) => ReactNode, prioridad?: 1|2|3 (default 1), ancho?: string (default "auto"), className?: string }`. Las tareas 3 y 7-11 dependen de estos nombres exactos.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `frontend/src/components/TablaResponsive.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TablaResponsive from "./TablaResponsive";
import { setAnchoViewport } from "../test/setup";

const FILAS = [
  { id: 1, fecha: "12/08", concepto: "Limpieza", monto: "$84.500" },
  { id: 2, fecha: "03/08", concepto: "Bomba", monto: "$12.000" },
];

const COLUMNAS = [
  { clave: "fecha", titulo: "Fecha", celda: (f) => f.fecha, ancho: "10ch" },
  { clave: "concepto", titulo: "Concepto", celda: (f) => f.concepto, prioridad: 3 },
  { clave: "monto", titulo: "Monto", celda: (f) => f.monto, ancho: "12ch" },
];

function montar(props = {}) {
  return render(
    <TablaResponsive
      columnas={COLUMNAS}
      filas={FILAS}
      claveFila={(f) => f.id}
      renderTarjeta={(f) => <p>{f.concepto}</p>}
      {...props}
    />,
  );
}

describe("TablaResponsive — anchos y modelo de columnas", () => {
  it("renderiza un <col> por columna con el ancho declarado", () => {
    const { container } = montar();
    const cols = container.querySelectorAll("colgroup col");
    expect(cols).toHaveLength(3);
    expect(cols[0]).toHaveStyle({ width: "10ch" });
    expect(cols[2]).toHaveStyle({ width: "12ch" });
  });

  it("usa auto como ancho por defecto", () => {
    const { container } = montar();
    const cols = container.querySelectorAll("colgroup col");
    expect(cols[1]).toHaveStyle({ width: "auto" });
  });

  it("marca cada celda y cada encabezado con su prioridad", () => {
    const { container } = montar();
    expect(container.querySelector('th[data-prio="3"]')).toHaveTextContent("Concepto");
    expect(container.querySelectorAll('td[data-prio="3"]')).toHaveLength(2);
  });

  it("asume prioridad 1 cuando la columna no la declara", () => {
    const { container } = montar();
    expect(container.querySelector('th[data-prio="1"]')).toHaveTextContent("Fecha");
  });

  it("muestra tarjetas por debajo de 600px", () => {
    setAnchoViewport(375);
    const { container } = montar();
    expect(container.querySelector("table")).toBeNull();
    expect(screen.getByText("Limpieza")).toBeInTheDocument();
  });

  it("muestra el mensaje de vacío cuando no hay filas", () => {
    montar({ filas: [], vacio: "No hay gastos." });
    expect(screen.getByText("No hay gastos.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd frontend && npm test -- TablaResponsive`
Expected: FAIL — `Failed to resolve import "./TablaResponsive"`.

- [ ] **Step 3: Crear `frontend/src/components/TablaResponsive.jsx`**

```jsx
import { useEsTablet } from "../hooks/useBreakpoint";

/**
 * Una misma colección en dos densidades: tabla de ≥600px para arriba, tarjetas
 * por debajo. Renderiza UN solo árbol — nunca los dos ocultando uno por CSS,
 * que duplicaría el contenido para los lectores de pantalla.
 *
 * En modo tabla las columnas NO miden su contenido: se reparten el ancho
 * disponible según el `ancho` declarado (`table-layout: fixed` + colgroup).
 *
 * Unidades válidas en `ancho`: `auto`, longitudes (`ch`, `rem`, `px`) y
 * porcentajes. NO uses `fr` — es una unidad de grid, y en un <col> el
 * navegador la descarta en silencio dejando la columna sin ancho declarado.
 * `auto` es el equivalente correcto acá: bajo `table-layout: fixed`, las
 * columnas en `auto` se reparten en partes iguales lo que sobra después de
 * las de ancho fijo, que es exactamente el reparto proporcional buscado.
 *
 * El `data-prio` de cada celda es lo que el CSS usa para esconderla cuando el
 * contenedor se angosta; ver el bloque `@container` en index.css.
 */
export default function TablaResponsive({
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
    <div className="tabla-datos-scroll">
      <table className="tabla-datos">
        <colgroup>
          {columnas.map((c) => (
            <col key={c.clave} style={{ width: c.ancho ?? "auto" }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c.clave} className={c.className} data-prio={c.prioridad ?? 1}>
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={claveFila(fila)} className="fila-datos">
              {columnas.map((c) => (
                <td key={c.clave} className={c.className} data-prio={c.prioridad ?? 1}>
                  {c.celda(fila)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd frontend && npm test -- TablaResponsive`
Expected: PASS — 6 tests.

- [ ] **Step 5: Migrar los cuatro consumidores y borrar el componente viejo**

En `Expensas.jsx`, `Comprobantes.jsx`, `Gastos.jsx` y `Reservas.jsx`, reemplazar la línea de import:

```jsx
import ListaResponsive from "../components/ListaResponsive";
```

por:

```jsx
import TablaResponsive from "../components/TablaResponsive";
```

y en cada archivo reemplazar el uso `<ListaResponsive` por `<TablaResponsive` (y su cierre si lo hubiera). Después:

```bash
rm frontend/src/components/ListaResponsive.jsx
```

Verificar que no queda ninguna referencia:

Run: `cd frontend && grep -rn "ListaResponsive" src/`
Expected: sin resultados.

- [ ] **Step 6: Reemplazar el bloque de CSS de la tabla**

En `frontend/src/index.css`, reemplazar íntegro el bloque que hoy va de la línea 2797 a la 2813 (desde `.tabla-datos-scroll {` hasta el cierre de `.tabla-datos {`) por:

```css
.tabla-datos-scroll {
  /* La tabla mide ESTE contenedor, no el viewport: con el sidebar de 230px
     (línea 2055) el viewport miente por un margen fijo en admin y por nada en
     la vista depto. Un corte por @media necesitaría dos calibraciones para la
     misma tabla; con @container hay una sola y siempre correcta. */
  container-type: inline-size;
  container-name: tabla;
  margin-bottom: 1rem;
}

.tabla-datos {
  width: 100%;
  /* Antes acá vivía `min-width: max-content`, que le prohibía a la tabla
     comprimirse y forzaba scroll horizontal apenas la pantalla se angostaba.
     Con `fixed` las columnas se reparten el ancho según el <colgroup> en vez
     de exigir el de su contenido más largo. Efecto lateral buscado: el
     `white-space: nowrap` de los <th> deja de empujar el ancho de la tabla,
     porque en layout fijo el contenido ya no participa del cálculo. */
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.8125rem;
}
```

Y agregar a la regla existente `.tabla-datos tbody td` (línea ~2835) las tres propiedades del recorte:

```css
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

- [ ] **Step 7: Verificar en el browser**

Levantar `cd frontend && npm run dev` y abrir `/gastos` y `/cobranzas`. A 1440px, 1024px y 768px, confirmar que la tabla ya no dispara barra de scroll horizontal y que las columnas se achican en proporción. **Se espera que a 768px el texto se vea muy recortado** — eso lo resuelve la tarea 4; acá solo se verifica que no hay desborde.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/TablaResponsive.jsx frontend/src/components/TablaResponsive.test.jsx frontend/src/index.css frontend/src/screens/Expensas.jsx frontend/src/screens/Comprobantes.jsx frontend/src/screens/Gastos.jsx frontend/src/screens/Reservas.jsx
git rm frontend/src/components/ListaResponsive.jsx
git commit -m "refactor: TablaResponsive reparte el ancho por colgroup en vez de exigir max-content"
```

---

### Task 3: Fila de detalle y chevron

**Files:**
- Modify: `frontend/src/components/TablaResponsive.jsx`
- Modify: `frontend/src/components/TablaResponsive.test.jsx`

**Interfaces:**
- Consumes: el modelo de columnas de la Task 2.
- Produces: por cada fila de datos, una `<tr class="fila-detalle">` hermana con `id={`detalle-${clave}`}`, y una primera celda `.col-chevron` con un `<button>` que lleva `aria-expanded` y `aria-controls`. Los pares etiqueta/valor del detalle van en `<div class="detalle-par" data-prio="N">`. La Task 4 depende de estos nombres de clase exactos.

- [ ] **Step 1: Agregar los tests que fallan**

Primero, en la línea de imports de `@testing-library/react` que ya existe arriba del archivo, agregar el import de `userEvent`:

```jsx
import userEvent from "@testing-library/user-event";
```

**No repetir el `import { describe, it, expect } from "vitest"` que ya está en la primera línea** — un segundo import de los mismos nombres desde el mismo módulo es un `SyntaxError` y no compila ni un test.

Después, agregar al final de `frontend/src/components/TablaResponsive.test.jsx` (el bloque reusa `montar`, `COLUMNAS` y `screen`, que ya están en scope):

```jsx
describe("TablaResponsive — fila de detalle", () => {
  it("renderiza una fila de detalle por fila de datos", () => {
    const { container } = montar();
    expect(container.querySelectorAll("tr.fila-detalle")).toHaveLength(2);
  });

  it("mete en el detalle solo las columnas de prioridad 2 y 3", () => {
    const { container } = montar();
    const pares = container.querySelectorAll("tr.fila-detalle .detalle-par");
    // 2 filas × 1 columna de prioridad 3 (Concepto). Fecha y Monto son prio 1.
    expect(pares).toHaveLength(2);
    expect(pares[0]).toHaveAttribute("data-prio", "3");
    expect(pares[0]).toHaveTextContent("Concepto");
    expect(pares[0]).toHaveTextContent("Limpieza");
  });

  it("arranca con el detalle colapsado", () => {
    const { container } = montar();
    expect(container.querySelector("tr.fila-detalle")).toHaveAttribute("hidden");
    expect(screen.getAllByRole("button", { name: /ver más datos/i })[0])
      .toHaveAttribute("aria-expanded", "false");
  });

  it("el chevron abre y cierra su fila", async () => {
    const user = userEvent.setup();
    const { container } = montar();
    const chevron = screen.getAllByRole("button", { name: /ver más datos/i })[0];

    await user.click(chevron);
    expect(chevron).toHaveAttribute("aria-expanded", "true");
    expect(container.querySelector("tr.fila-detalle")).not.toHaveAttribute("hidden");

    await user.click(chevron);
    expect(chevron).toHaveAttribute("aria-expanded", "false");
    expect(container.querySelector("tr.fila-detalle")).toHaveAttribute("hidden");
  });

  it("cada chevron apunta a su propia fila de detalle", () => {
    const { container } = montar();
    const chevrones = screen.getAllByRole("button", { name: /ver más datos/i });
    const detalles = container.querySelectorAll("tr.fila-detalle");
    expect(chevrones[0].getAttribute("aria-controls")).toBe(detalles[0].id);
    expect(chevrones[1].getAttribute("aria-controls")).toBe(detalles[1].id);
    expect(detalles[0].id).not.toBe(detalles[1].id);
  });

  it("no renderiza chevron ni detalle si todas las columnas son prioridad 1", () => {
    const soloPrio1 = COLUMNAS.map((c) => ({ ...c, prioridad: 1 }));
    const { container } = montar({ columnas: soloPrio1 });
    expect(container.querySelectorAll("tr.fila-detalle")).toHaveLength(0);
    expect(container.querySelector(".col-chevron")).toBeNull();
  });
});
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd frontend && npm test -- TablaResponsive`
Expected: FAIL — los 6 de la Task 2 pasan, los 6 nuevos fallan (`Unable to find role "button"`, `toHaveLength(0)` recibido).

- [ ] **Step 3: Implementar en `TablaResponsive.jsx`**

Agregar el import de `useState` arriba:

```jsx
import { useState } from "react";
import { useEsTablet } from "../hooks/useBreakpoint";
```

Dentro del componente, antes del `if (filas.length === 0)`:

```jsx
  const [expandidas, setExpandidas] = useState(() => new Set());

  /** Solo hay algo que esconder si alguna columna no es prioridad 1. */
  const columnasOcultables = columnas.filter((c) => (c.prioridad ?? 1) > 1);
  const hayDetalle = columnasOcultables.length > 0;

  function alternar(clave) {
    setExpandidas((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(clave)) siguiente.delete(clave);
      else siguiente.add(clave);
      return siguiente;
    });
  }
```

Reemplazar el `<colgroup>` para contemplar la columna del chevron:

```jsx
        <colgroup>
          {hayDetalle && <col className="col-chevron" style={{ width: "2.75rem" }} />}
          {columnas.map((c) => (
            <col key={c.clave} style={{ width: c.ancho ?? "auto" }} />
          ))}
        </colgroup>
```

Agregar la celda vacía de encabezado del chevron como primer `<th>`:

```jsx
          <tr>
            {hayDetalle && <th className="col-chevron"><span className="sr-only">Detalle</span></th>}
            {columnas.map((c) => (
```

Y reemplazar el `<tbody>` entero por:

```jsx
        <tbody>
          {filas.map((fila) => {
            const clave = claveFila(fila);
            const abierta = expandidas.has(clave);
            const idDetalle = `detalle-${clave}`;
            return [
              <tr key={clave} className="fila-datos">
                {hayDetalle && (
                  <td className="col-chevron">
                    <button
                      type="button"
                      className="chevron-detalle"
                      aria-expanded={abierta}
                      aria-controls={idDetalle}
                      aria-label={abierta ? "Ocultar más datos" : "Ver más datos"}
                      onClick={() => alternar(clave)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                           stroke="currentColor" strokeWidth="2.5"
                           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="m9 18 6-6-6-6" />
                      </svg>
                    </button>
                  </td>
                )}
                {columnas.map((c) => (
                  <td key={c.clave} className={c.className} data-prio={c.prioridad ?? 1}>
                    {c.celda(fila)}
                  </td>
                ))}
              </tr>,
              hayDetalle && (
                <tr key={`${clave}-detalle`} id={idDetalle} className="fila-detalle" hidden={!abierta}>
                  <td colSpan={columnas.length + 1}>
                    {columnasOcultables.map((c) => (
                      <div key={c.clave} className="detalle-par" data-prio={c.prioridad}>
                        <span className="detalle-etiqueta">{c.titulo}</span>
                        <span className="detalle-valor">{c.celda(fila)}</span>
                      </div>
                    ))}
                  </td>
                </tr>
              ),
            ];
          })}
        </tbody>
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd frontend && npm test`
Expected: PASS — 20 tests (8 del helper + 12 de la tabla).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TablaResponsive.jsx frontend/src/components/TablaResponsive.test.jsx
git commit -m "feat: fila de detalle expandible en TablaResponsive"
```

---

### Task 4: CSS de escalones con `@container`

Acá se conecta el `data-prio` del DOM con el ancho real. Es la tarea que hace visible todo lo anterior.

**Files:**
- Modify: `frontend/src/index.css` (agregar al final del bloque `.tabla-datos`, después de la regla `.col-acciones`)

**Interfaces:**
- Consumes: `.tabla-datos-scroll` con `container-name: tabla` (Task 2); `tr.fila-datos`, `tr.fila-detalle`, `.detalle-par[data-prio]`, `.col-chevron`, `.chevron-detalle` (Task 3).
- Produces: nada que consuman tareas posteriores.

- [ ] **Step 1: Agregar el bloque de escalones a `frontend/src/index.css`**

Después de la regla `.tabla-datos .col-acciones` (~línea 2847):

```css
/* ---------- Escalones de la tabla adaptativa ---------- */

/* La fila de detalle nace escondida: solo la muestra el @container que
   corresponde. Sin esta regla base, todos los pares saldrían siempre. */
.fila-detalle > td {
  padding: 0 0.75rem 0.7rem;
  background: var(--color-bg);
}

.detalle-par {
  display: none;
  gap: 0.5rem;
  align-items: baseline;
  padding: 0.15rem 0;
}

.detalle-etiqueta {
  font-size: 0.625rem;
  font-weight: 800;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.detalle-valor {
  font-size: 0.8125rem;
  color: var(--color-text);
  min-width: 0;
}

.col-chevron {
  text-align: center;
  padding: 0 !important;
}

.chevron-detalle {
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.chevron-detalle:hover:not(:disabled) {
  color: var(--color-text);
  background: transparent;
}

.chevron-detalle svg {
  transition: transform 0.15s ease;
}

.chevron-detalle[aria-expanded="true"] svg {
  transform: rotate(90deg);
}

/* Prioridad 3: se va primero, bajo 1000px de contenedor.
   El selector de ocultamiento baja por > thead/tbody > tr para NO alcanzar los
   .detalle-par, que viven adentro de la misma tabla y llevan el mismo
   data-prio. Sin ese acotamiento las dos reglas empatan en especificidad y el
   resultado queda a merced del orden. */
@container tabla (max-width: 999.98px) {
  .tabla-datos > thead > tr > [data-prio="3"],
  .tabla-datos > tbody > tr.fila-datos > [data-prio="3"] { display: none; }
  .fila-detalle .detalle-par[data-prio="3"] { display: flex; }
}

/* Prioridad 2: se va bajo 760px de contenedor. */
@container tabla (max-width: 759.98px) {
  .tabla-datos > thead > tr > [data-prio="2"],
  .tabla-datos > tbody > tr.fila-datos > [data-prio="2"] { display: none; }
  .fila-detalle .detalle-par[data-prio="2"] { display: flex; }
}

/* Con todo a la vista no queda nada que expandir: se va el chevron, y también
   la fila de detalle por si el usuario la había abierto antes de agrandar. */
@container tabla (min-width: 1000px) {
  .tabla-datos > thead > tr > .col-chevron,
  .tabla-datos > tbody > tr > .col-chevron { display: none; }
  .fila-detalle { display: none; }
}
```

- [ ] **Step 2: Agregar `.sr-only` si no existe**

Run: `cd frontend && grep -n "sr-only" src/index.css`

Si no aparece, agregarlo cerca del inicio del archivo (después del bloque `* { box-sizing }`):

```css
/* Texto solo para lectores de pantalla. */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

- [ ] **Step 3: Verificar en el browser**

`cd frontend && npm run dev`, abrir `/gastos` (la tabla con más columnas del sistema) y confirmar en este orden:

1. **1440px** — todas las columnas visibles, sin chevron, sin barra de scroll horizontal.
2. **Achicar despacio hasta ~1150px** — en algún punto desaparece la columna de menor prioridad y aparece el chevron. La transición no debe parpadear.
3. **Abrir un chevron** — se despliega la fila de detalle con los campos escondidos, cada uno con su etiqueta.
4. **Agrandar de vuelta a 1440px con el detalle abierto** — la fila de detalle desaparece sola.
5. **768px** — dos escalones aplicados, todo legible, cero scroll horizontal.
6. **375px** — tarjetas, idénticas a antes de este plan.
7. En consola: `document.documentElement.scrollWidth === document.documentElement.clientWidth` → `true` en los cuatro anchos.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: escalones por @container que esconden columnas segun prioridad"
```

---

### Task 5: Fix global del `<thead>` desalineado

Es un cambio de tres líneas borradas que alcanza a las 15 pantallas con `<table>` a mano. Va solo, para que si algo se rompe se sepa exactamente qué lo rompió.

**Files:**
- Modify: `frontend/src/index.css:270-282` (selector global `table`), y la regla `th` inmediatamente siguiente

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: Borrar las tres declaraciones del selector global `table`**

En `frontend/src/index.css`, dentro del bloque `table { … }` que arranca en la línea 270, borrar el comentario y las tres declaraciones (líneas 278-281):

```css
  /* Mobile: la tabla scrollea horizontal dentro de su caja, sin desbordar la pantalla */
  display: block;
  overflow-x: auto;
  overflow-y: hidden;
```

`display: block` convierte la tabla en bloque, y con eso `thead` y `tbody` dejan de compartir el contexto de layout de tabla: al scrollear se desalinean. Es el "header roto" del reporte. Sin scroll horizontal ya no hay nada que compensar.

- [ ] **Step 2: Hacer el encabezado pegajoso**

En la regla `th` que sigue (línea ~284), agregar:

```css
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--color-surface);
```

El fondo opaco es obligatorio: sin él, las filas se ven pasar por debajo del texto del encabezado.

- [ ] **Step 3: Correr los tests y el build**

Run: `cd frontend && npm test && npm run build`
Expected: PASS y build limpio.

- [ ] **Step 4: Verificar las 15 pantallas afectadas**

`cd frontend && npm run dev`. Recorrer con sesión de administración, a **1440px y 768px**, y en cada una scrollear vertical hasta el fondo comprobando que el encabezado queda fijo y alineado con sus columnas:

`/cobranzas?tab=cierres`, `/peticiones`, `/cuentas-corrientes`, `/tesoreria?tab=cajas`, `/tesoreria?tab=transferencias`, `/tesoreria?tab=estado`, `/departamentos/1/cuenta`, `/mi-cuenta`, `/padron`, `/liquidaciones`, `/configuracion` (matriz de coeficientes), `/reportes/morosos`, `/reportes/gastos`, `/reportes/estado-financiero`, `/reportes/proveedores`.

(Rutas verificadas contra `frontend/src/App.jsx:122-163`. Ojo: el reporte de gastos por período vive en `/reportes/gastos`, no en `/reportes/gastos-periodo`.)

**Atención especial a la matriz de coeficientes en `/configuracion`:** es la única que legítimamente necesita scroll horizontal (`.tabla-scroll`, `index.css:1380`) y no se convierte a `TablaResponsive`. Confirmar que su wrapper propio sigue dándole la barra y que nada se desborda del viewport.

Si alguna pantalla queda con scroll horizontal propio tras el cambio, envolverla en `<div className="tabla-scroll">` — no reponer la regla global.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "fix: thead deja de desalinearse al scrollear y queda pegado arriba"
```

---

### Task 6: `MenuAcciones`

**Files:**
- Create: `frontend/src/components/MenuAcciones.jsx`
- Create: `frontend/src/components/MenuAcciones.test.jsx`

**Interfaces:**
- Consumes: nada.
- Produces: `<MenuAcciones acciones={[{ label, onSelect, peligro? }]} etiqueta? />` (export default). `etiqueta` es el `aria-label` del trigger, default `"Acciones"`. Las tareas 8 a 11 lo consumen con esa firma exacta.

El estilo ya está escrito y completo en `index.css:1087-1152` (`.menu-kebab`, `.menu-kebab-trigger`, `.menu-kebab-lista`, `.menu-kebab-item`, `.menu-kebab-item.peligro`); ningún JSX lo consumía. Esta tarea **no escribe CSS**.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `frontend/src/components/MenuAcciones.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MenuAcciones from "./MenuAcciones";

function montar(overrides = {}) {
  const onEditar = vi.fn();
  const onEliminar = vi.fn();
  render(
    <div>
      <button type="button">afuera</button>
      <MenuAcciones
        acciones={[
          { label: "Editar", onSelect: onEditar },
          { label: "Eliminar", onSelect: onEliminar, peligro: true },
        ]}
        {...overrides}
      />
    </div>,
  );
  return { onEditar, onEliminar };
}

describe("MenuAcciones", () => {
  it("arranca cerrado", () => {
    montar();
    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.getByRole("button", { name: "Acciones" }))
      .toHaveAttribute("aria-expanded", "false");
  });

  it("abre al clickear el trigger", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Editar" })).toBeInTheDocument();
  });

  it("ejecuta la acción y cierra", async () => {
    const user = userEvent.setup();
    const { onEditar } = montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    expect(onEditar).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("marca las acciones destructivas", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toHaveClass("peligro");
  });

  it("cierra con Escape y devuelve el foco al trigger", async () => {
    const user = userEvent.setup();
    montar();
    const trigger = screen.getByRole("button", { name: "Acciones" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("cierra al clickear afuera", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.click(screen.getByRole("button", { name: "afuera" }));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("acepta una etiqueta propia para el trigger", () => {
    montar({ etiqueta: "Acciones de la caja Efectivo" });
    expect(screen.getByRole("button", { name: "Acciones de la caja Efectivo" }))
      .toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd frontend && npm test -- MenuAcciones`
Expected: FAIL — `Failed to resolve import "./MenuAcciones"`.

- [ ] **Step 3: Crear `frontend/src/components/MenuAcciones.jsx`**

```jsx
import { useEffect, useRef, useState } from "react";

/**
 * Menú "⋯" para la columna de acciones de una tabla. En una fila, tres botones
 * visibles se comen 200-250px de ancho — una columna de datos entera — y dejan
 * Eliminar a un click de Editar.
 *
 * El estilo ya vive en index.css como `.menu-kebab*`.
 */
export default function MenuAcciones({ acciones, etiqueta = "Acciones" }) {
  const [abierto, setAbierto] = useState(false);
  const contenedorRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;

    function alClickearAfuera(e) {
      if (!contenedorRef.current?.contains(e.target)) setAbierto(false);
    }
    function alApretarEscape(e) {
      if (e.key !== "Escape") return;
      setAbierto(false);
      // Sin esto el foco queda huérfano en el body y el teclado pierde el hilo.
      triggerRef.current?.focus();
    }

    document.addEventListener("mousedown", alClickearAfuera);
    document.addEventListener("keydown", alApretarEscape);
    return () => {
      document.removeEventListener("mousedown", alClickearAfuera);
      document.removeEventListener("keydown", alApretarEscape);
    };
  }, [abierto]);

  function ejecutar(accion) {
    setAbierto(false);
    accion.onSelect();
  }

  return (
    <div className="menu-kebab" ref={contenedorRef}>
      <button
        type="button"
        ref={triggerRef}
        className="menu-kebab-trigger"
        aria-label={etiqueta}
        aria-haspopup="menu"
        aria-expanded={abierto}
        onClick={() => setAbierto((prev) => !prev)}
      >
        ⋯
      </button>

      {abierto && (
        <ul className="menu-kebab-lista" role="menu">
          {acciones.map((a) => (
            <li key={a.label} role="none">
              <button
                type="button"
                role="menuitem"
                className={`menu-kebab-item${a.peligro ? " peligro" : ""}`}
                onClick={() => ejecutar(a)}
              >
                {a.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd frontend && npm test -- MenuAcciones`
Expected: PASS — 7 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MenuAcciones.jsx frontend/src/components/MenuAcciones.test.jsx
git commit -m "feat: componente MenuAcciones que consume el estilo kebab existente"
```

---

### Task 7: Prioridades en las cuatro pantallas que ya usan el componente

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx:125-195`
- Modify: `frontend/src/screens/Comprobantes.jsx:183-225`
- Modify: `frontend/src/screens/Gastos.jsx:160-205`
- Modify: `frontend/src/screens/Reservas.jsx` (bloque `columnas`)

**Interfaces:**
- Consumes: `TablaResponsive` (Tasks 2-3).
- Produces: nada.

Criterio: **prioridad 1** es lo que identifica la fila (fecha, período, código) más el número que la persona vino a ver (monto, estado). **Prioridad 3** es lo que solo importa una vez que ya encontraste la fila.

**Decisión del usuario tomada durante la ejecución (2026-08-13): estas tres pantallas también pasan a `MenuAcciones`.** Expensas, Comprobantes y Gastos tienen dos o tres botones sueltos por fila. Quedarían como la única parte de la app con ese patrón mientras el resto usa el menú `⋯`, y esos botones se comen unos 140px de cada fila. La columna de acciones de las tres pasa a un único `MenuAcciones` y su `ancho` baja de `9rem` a `4rem` — el ancho liberado es lo que deja entrar una columna más de datos antes de que empiecen a esconderse.

En mobile **no** se usa el menú: las tarjetas conservan sus botones sueltos, que es lo que corresponde a un target táctil.

- [ ] **Step 1: Expensas**

En el array `columnas` de `Expensas.jsx:125`, agregar a cada objeto:

| clave | prioridad | ancho |
|---|---|---|
| `periodo` | 1 | `10ch` |
| `depto` | 1 | `auto` |
| `venc1` | 3 | `auto` |
| `venc2` | 2 | `auto` |
| `estado` | 1 | `12ch` |
| `pendiente` | 1 | `14ch` |
| `acciones` | 1 | `9rem` |

`venc1` se va antes que `venc2` a propósito: si la expensa ya está vencida, el importe que importa es el del segundo vencimiento.

La columna `pendiente` tiene `<br>` y un `<span className="meta">`; para que el `white-space: nowrap` de la Task 2 no la aplaste, agregarle `col-monto` (ya lo tiene) y verificar en el browser que las dos líneas se siguen viendo.

- [ ] **Step 2: Comprobantes**

> Corregido durante la ejecución (2026-08-13): la columna se llama `archivo`, no `comprobante`. Y sube de prioridad 3 a **2**, con `fecha` bajando a 3: en la pantalla donde se aprueban pagos, la miniatura del comprobante ES el insumo de la decisión — esconderla obliga a desplegar la fila, mirarla, colapsarla y recién ahí abrir el menú. La fecha exacta de pago es un dato que se consulta después de encontrar la fila.

En `Comprobantes.jsx:183`:

| clave | prioridad | ancho |
|---|---|---|
| `fecha` | 3 | `12ch` |
| `depto` | 1 | `auto` |
| `monto` | 1 | `14ch` |
| `estado` | 1 | `12ch` |
| `archivo` | 2 | `8rem` |
| acciones (`titulo: ""`) | 1 | `9rem` |

- [ ] **Step 3: Gastos**

En el array `columnas` de `Gastos.jsx`:

| clave | prioridad | ancho |
|---|---|---|
| fecha | 1 | `12ch` |
| concepto | 1 | `auto` |
| rubro | 2 | `auto` |
| proveedor | 3 | `auto` |
| clase / departamento | 3 | `auto` |
| monto | 1 | `14ch` |
| pagado | 2 | `10ch` |
| acciones | 1 | `9rem` |

- [ ] **Step 4: Reservas**

En el array `columnas` de `Reservas.jsx`: `amenity` y `fecha` prioridad 1, `horario` prioridad 1, `estado` prioridad 1. Reservas tiene pocas columnas y vive en una grilla de dos columnas desde 960px (`.reservas-grid`, `index.css:2869-2880`), así que su contenedor es angosto: dejar todo en prioridad 1 y darle anchos `auto` salvo `fecha` (`12ch`).

- [ ] **Step 5: Correr los tests**

Run: `cd frontend && npm test && npm run lint`
Expected: tests PASS. El lint termina en `✖ 87 problems` o menos — ese es el baseline preexistente de master, no una falla de esta tarea. Si sube de 87, revisar qué se agregó.

- [ ] **Step 6: Verificar en el browser**

A **1440, 1024, 768 y 375px**, en `/cobranzas?tab=expensas`, `/cobranzas?tab=comprobantes`, `/gastos` y `/reservas`:

1. Cero scroll horizontal.
2. Ningún dato inalcanzable: lo que desaparece de la tabla aparece al abrir el chevron.
3. Montos y fechas nunca cortados con `…` (por eso van en `ch` y no en `auto`).
4. En Expensas, la columna Pendiente sigue mostrando el interés en su segunda línea.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/screens/Expensas.jsx frontend/src/screens/Comprobantes.jsx frontend/src/screens/Gastos.jsx frontend/src/screens/Reservas.jsx
git commit -m "feat: prioridades de columna en expensas, comprobantes, gastos y reservas"
```

---

### Task 8: Migrar Periodos y Peticiones

Estas dos no tienen densidad de tarjeta: muestran `<table>` en todos los anchos. Migrarlas incluye **escribir su `renderTarjeta` de cero**. Peticiones es la que el usuario reportó como ilegible en celular.

**Files:**
- Modify: `frontend/src/screens/Periodos.jsx:29-72`
- Modify: `frontend/src/screens/Peticiones.jsx:118-149`

**Interfaces:**
- Consumes: `TablaResponsive` (Tasks 2-3), `Tarjeta` de `../components/Tarjeta`.
- Produces: nada.

- [ ] **Step 1: Periodos — reemplazar la tabla**

Agregar los imports:

```jsx
import TablaResponsive from "../components/TablaResponsive";
import Tarjeta from "../components/Tarjeta";
```

Reemplazar todo el bloque `{periodos.length === 0 ? (…) : (<table>…</table>)}` (líneas 31-72) por:

```jsx
      <TablaResponsive
        columnas={[
          { clave: "periodo", titulo: "Período", celda: (p) => p.periodo, ancho: "10ch" },
          { clave: "cerrado", titulo: "Cerrado el", prioridad: 2, ancho: "auto",
            celda: (p) => formatFechaHora(p.fecha_cierre) },
          { clave: "boletas", titulo: "Boletas", prioridad: 3, ancho: "9ch",
            className: "col-monto", celda: (p) => p.cantidad_expensas },
          { clave: "total", titulo: "Total expensado", className: "col-monto", ancho: "15ch",
            celda: (p) => formatMoney(p.total_expensado) },
          { clave: "intereses", titulo: "Intereses", prioridad: 3, className: "col-monto",
            ancho: "13ch", celda: (p) => formatMoney(p.total_intereses) },
          { clave: "acciones", titulo: "", className: "col-acciones", ancho: "11rem",
            celda: (p) => (
              <>
                <Link to={`/expensas?periodo=${p.periodo}`}>Ver expensas</Link>{" "}
                <button
                  type="button"
                  onClick={() => setModalEnvio({
                    periodo: p.periodo,
                    cantidadExpensas: p.cantidad_expensas,
                    periodoCerrado: true,
                  })}
                >
                  ✉ Enviar PDFs
                </button>
              </>
            ) },
        ]}
        filas={periodos}
        claveFila={(p) => p.periodo}
        vacio="Todavía no hay períodos cerrados."
        renderTarjeta={(p) => (
          <Tarjeta>
            <h3>{p.periodo}</h3>
            <p className="meta">Cerrado el {formatFechaHora(p.fecha_cierre)}</p>
            <p className="meta">
              {p.cantidad_expensas} boletas · {formatMoney(p.total_expensado)}
            </p>
            <p className="meta">Intereses: {formatMoney(p.total_intereses)}</p>
            <div className="tarjeta-acciones">
              <Link to={`/expensas?periodo=${p.periodo}`}>Ver expensas</Link>
              <button
                type="button"
                onClick={() => setModalEnvio({
                  periodo: p.periodo,
                  cantidadExpensas: p.cantidad_expensas,
                  periodoCerrado: true,
                })}
              >
                ✉ Enviar PDFs
              </button>
            </div>
          </Tarjeta>
        )}
      />
```

Se va el `<div style={{ display: "flex", … }}>` inline de la línea 55: el estilo de la columna de acciones ya lo da `.col-acciones`.

- [ ] **Step 2: Peticiones — reemplazar la tabla**

Agregar los imports de `TablaResponsive` y `Tarjeta`. Reemplazar el bloque `<table className="tabla-listado">…</table>` (líneas 118-149) por:

```jsx
      <TablaResponsive
        columnas={[
          { clave: "id", titulo: "#", ancho: "6ch", celda: (p) => p.id },
          { clave: "depto", titulo: "Depto", prioridad: 2, ancho: "9ch",
            celda: (p) => p.departamento_id },
          { clave: "titulo", titulo: "Título", ancho: "auto", celda: (p) => p.titulo },
          { clave: "estado", titulo: "Estado", ancho: "13ch",
            celda: (p) => ETIQUETAS_ESTADO[p.estado] || p.estado },
          { clave: "fecha", titulo: "Fecha", prioridad: 3, ancho: "12ch",
            celda: (p) => formatFecha(p.fecha_creacion) },
          { clave: "acciones", titulo: "", className: "col-acciones", ancho: "7rem",
            celda: (p) => (
              <button type="button" onClick={() => setModal(p)}>Ver</button>
            ) },
        ]}
        filas={visibles}
        claveFila={(p) => p.id}
        vacio="Sin peticiones."
        renderTarjeta={(p) => (
          <Tarjeta>
            <h3>#{p.id} · {p.titulo}</h3>
            <p className="meta">
              Depto {p.departamento_id} · {formatFecha(p.fecha_creacion)}
            </p>
            <p className="meta">{ETIQUETAS_ESTADO[p.estado] || p.estado}</p>
            <div className="tarjeta-acciones">
              <button type="button" onClick={() => setModal(p)}>Ver detalle</button>
            </div>
          </Tarjeta>
        )}
      />
```

**El `<tr onClick>` de la línea 129 desaparece.** Una fila entera clickeable no es alcanzable por teclado y viola la regla del proyecto contra controles que no son `<button>`. Lo reemplaza el botón "Ver" de la columna de acciones.

- [ ] **Step 3: Correr tests y lint**

Run: `cd frontend && npm test && npm run lint`
Expected: tests PASS. El lint termina en `✖ 87 problems` o menos — baseline preexistente, no una falla de esta tarea.

- [ ] **Step 4: Verificar en el browser**

`/cobranzas?tab=cierres` y `/peticiones` a **375, 768, 1024 y 1440px**.

En **375px**, Peticiones tiene que mostrar tarjetas y entrar entera — es el bug que reportó el usuario. Confirmar `document.documentElement.scrollWidth === clientWidth`.

Con teclado: llegar a "Ver detalle" con Tab y abrirlo con Enter.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Periodos.jsx frontend/src/screens/Peticiones.jsx
git commit -m "feat: periodos y peticiones usan TablaResponsive y ganan tarjeta en mobile"
```

---

### Task 9: Migrar las tablas de Tesorería y Cuentas Corrientes

**Files:**
- Modify: `frontend/src/screens/Cajas.jsx:47-88` (dos tablas: cajas y movimientos)
- Modify: `frontend/src/screens/Transferencias.jsx:34-49`
- Modify: `frontend/src/screens/EstadoFinanciero.jsx:80-100`
- Modify: `frontend/src/screens/CuentasCorrientes.jsx:83-120`

**Interfaces:**
- Consumes: `TablaResponsive`, `Tarjeta`, `MenuAcciones` (Task 6).
- Produces: nada.

- [ ] **Step 1: Cajas — tabla principal**

**Este paso es la plantilla de las tareas 9, 10 y 11: va completo. Los pasos siguientes dan la especificación de columnas y siguen exactamente esta forma.**

Agregar los imports:

```jsx
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
```

(`Tarjeta` ya está importado en `Cajas.jsx` — lo usa el detalle de movimientos.)

Reemplazar la primera `<table>` (líneas 47-70) por:

```jsx
      <TablaResponsive
        columnas={[
          { clave: "nombre", titulo: "Nombre", ancho: "auto",
            celda: (c) => (
              <button type="button" className="boton-link" onClick={() => abrirDetalle(c)}>
                {c.nombre}
              </button>
            ) },
          { clave: "tipo", titulo: "Tipo", prioridad: 2, ancho: "12ch",
            celda: (c) => c.tipo },
          { clave: "descripcion", titulo: "Descripción", prioridad: 3, ancho: "auto",
            celda: (c) => c.descripcion || "—" },
          { clave: "saldo", titulo: "Saldo", ancho: "14ch", className: "col-monto",
            celda: (c) => fmtMoney(c.saldo_actual) },
          { clave: "activa", titulo: "Activa", prioridad: 3, ancho: "8ch",
            celda: (c) => (c.activa ? "Sí" : "No") },
          { clave: "acciones", titulo: "", ancho: "4rem", className: "col-acciones",
            celda: (c) => (
              <MenuAcciones
                etiqueta={`Acciones de ${c.nombre}`}
                acciones={[
                  { label: "Editar", onSelect: () => setModalCaja(c) },
                  { label: "Ajuste", onSelect: () => setModalAjuste(c) },
                  { label: "Borrar", onSelect: () => borrar(c), peligro: true },
                ]}
              />
            ) },
        ]}
        filas={cajas}
        claveFila={(c) => c.id}
        vacio="Todavía no hay cajas."
        renderTarjeta={(c) => (
          <Tarjeta>
            <h3>{c.nombre}</h3>
            <p className="meta">{c.tipo} · {fmtMoney(c.saldo_actual)}</p>
            {c.descripcion && <p className="meta">{c.descripcion}</p>}
            <p className="meta">{c.activa ? "Activa" : "Inactiva"}</p>
            <div className="tarjeta-acciones">
              <button type="button" onClick={() => abrirDetalle(c)}>Movimientos</button>
              <button type="button" onClick={() => setModalCaja(c)}>Editar</button>
              <button type="button" onClick={() => setModalAjuste(c)}>Ajuste</button>
              <button type="button" className="boton-borrar" onClick={() => borrar(c)}>
                Borrar
              </button>
            </div>
          </Tarjeta>
        )}
      />
```

Dos detalles: el `style={{textDecoration: "underline"}}` inline de la línea 55 se va y lo reemplaza `className="boton-link"`, que ya existe (`index.css:170`). Y en mobile **no** se usa el menú `⋯`: las tarjetas llevan los botones sueltos, que es lo que corresponde a un target táctil.

- [ ] **Step 2: Cajas — tabla de movimientos**

Reemplazar la segunda `<table>` (líneas 75-88) por `TablaResponsive`:

| clave | título | prioridad | ancho |
|---|---|---|---|
| `fecha` | Fecha | 1 | `12ch` |
| `tipo` | Tipo | 2 | `12ch` |
| `monto` | Monto | 1 | `14ch`, `col-monto` |
| `descripcion` | Descripción | 3 | `auto` |

`claveFila={(m) => m.id}`, `vacio="Sin movimientos."`.

- [ ] **Step 3: Transferencias**

Reemplazar la `<table>` (líneas 34-47):

| clave | título | prioridad | ancho |
|---|---|---|---|
| `fecha` | Fecha | 1 | `12ch` |
| `origen` | Origen | 1 | `auto` |
| `destino` | Destino | 1 | `auto` |
| `monto` | Monto | 1 | `14ch`, `col-monto` |
| `descripcion` | Descripción | 3 | `auto` |

`vacio="Todavía no hay transferencias registradas."`

- [ ] **Step 4: EstadoFinanciero**

Reemplazar la `<table>` de últimos movimientos (líneas 80-100):

| clave | título | prioridad | ancho |
|---|---|---|---|
| `fecha` | Fecha | 1 | `12ch` |
| `caja` | Caja | 2 | `auto` |
| `tipo` | Tipo | 3 | `12ch` |
| `monto` | Monto | 1 | `14ch`, `col-monto` |
| `descripcion` | Descripción | 3 | `auto` |

Esta tabla vive dentro de una `<Tarjeta>`, así que su contenedor es más angosto que el `.app-content`. Es justamente el caso que justifica `@container`: va a esconder columnas antes que las demás, y está bien.

- [ ] **Step 5: CuentasCorrientes**

Reemplazar la `<table className="tabla-padron">` (líneas 83-120):

| clave | título | prioridad | ancho |
|---|---|---|---|
| `unidad` | Unidad | 1 | `12ch` — el `<Link>` a `/departamentos/:id/cuenta` |
| `ubicacion` | Ubicación | 3 | `auto` |
| `saldo` | Saldo | 1 | `15ch`, `className: "col-monto"` |
| `estado` | Estado | 1 | `14ch` |

Los `style` inline de las líneas 100 y 103-105 se van: el alineado a la derecha lo da `col-monto`. **El color del saldo (`cfg.color`) y el punto del badge son colores calculados en JS** (`ESTILOS_ESTADO`); revisar ese objeto y si tiene hex hardcodeados, moverlos a `var(--color-…)` (`--color-danger`, `--color-warning`, `--color-success`) siguiendo la regla del proyecto.

`renderTarjeta`: `<Tarjeta>` con el código de unidad como `<h3>` enlazado, la ubicación, el saldo y el badge de estado.

- [ ] **Step 6: Correr tests y lint**

Run: `cd frontend && npm test && npm run lint`
Expected: tests PASS. El lint termina en `✖ 87 problems` o menos — baseline preexistente, no una falla de esta tarea.

- [ ] **Step 7: Verificar en el browser**

`/tesoreria?tab=estado`, `/tesoreria?tab=cajas` (abriendo el detalle de una caja), `/tesoreria?tab=transferencias` y `/cuentas-corrientes`, a **375, 768, 1024 y 1440px**.

El usuario reportó que Tesorería y Cuentas Corrientes obligaban a scrollear en mobile: a 375px las cuatro tienen que ser tarjetas, sin scroll horizontal.

Probar el menú `⋯` de Cajas con teclado: Tab hasta el trigger, Enter para abrir, Escape para cerrar, y confirmar que el foco vuelve al trigger.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/screens/Cajas.jsx frontend/src/screens/Transferencias.jsx frontend/src/screens/EstadoFinanciero.jsx frontend/src/screens/CuentasCorrientes.jsx
git commit -m "feat: tesoreria y cuentas corrientes usan TablaResponsive"
```

---

### Task 10: Gastos recurrentes y Amenities pasan a tabla

Las dos que el usuario señaló por nombre: "en desktop se ve como tarjeta y queda todo muy comprimido" y "en desktop se muestra como tarjetas, no tiene sentido".

**Files:**
- Modify: `frontend/src/screens/GastosHabituales.jsx:137-155`
- Modify: `frontend/src/screens/Amenities.jsx:51-73`

**Interfaces:**
- Consumes: `TablaResponsive`, `MenuAcciones`, `Tarjeta`.
- Produces: nada.

- [ ] **Step 1: GastosHabituales**

Reemplazar el `<ul className="lista-config">` (línea 137) por `TablaResponsive`. La tarjeta actual (líneas 140-152) se convierte casi tal cual en el `renderTarjeta`.

| clave | título | prioridad | ancho | celda |
|---|---|---|---|---|
| `nombre` | Nombre | 1 | `auto` | `h.nombre` |
| `monto` | Monto | 1 | `14ch`, `col-monto` | `$${h.monto.toLocaleString("es-AR")}` |
| `rubro` | Rubro | 2 | `auto` | `labelRubro(h.rubro)` |
| `clase` | Clase | 3 | `auto` | `clasePorId(h.clase_prorrateo_id)` |
| `proveedor` | Proveedor | 3 | `auto` | `proveedorPorId(h.proveedor_id)` |
| `caja` | Caja | 3 | `auto` | `cajaPorId(h.caja_id)` |
| `estado` | Estado | 2 | `11ch` | `h.activa ? "Activa" : "Inactiva"` |
| `acciones` | `""` | 1 | `4rem`, `col-acciones` | `MenuAcciones` con Editar / Activar-Desactivar / Eliminar (peligro) |

`claveFila={(h) => h.id}`, `vacio="No hay gastos recurrentes para mostrar."`

- [ ] **Step 2: Amenities**

Reemplazar el `<ul className="grid-fichas">` (línea 51) por `TablaResponsive`. El `<dl className="amenity-policies">` (líneas 58-64) ya es una tabla de dos columnas disfrazada de tarjeta: cada `<div><dt>/<dd></div>` se vuelve una columna.

| clave | título | prioridad | ancho | celda |
|---|---|---|---|---|
| `nombre` | Nombre | 1 | `auto` | `a.nombre` + `<small>(inactivo)</small>` si no está activo |
| `precio` | Precio | 1 | `13ch`, `col-monto` | `fmtPrecio(a.precio_reserva)` |
| `duracion` | Duración máx | 2 | `13ch` | `${fmt(a.duracion_maxima_horas)} h` |
| `anticipacion` | Anticipación máx | 3 | `15ch` | `${fmt(a.anticipacion_maxima_dias)} días` |
| `maxActivas` | Máx activas | 3 | `13ch` | `fmt(a.max_reservas_activas_por_depto)` |
| `cancelacion` | Cancelación | 3 | `15ch` | `${fmt(a.horas_minimas_cancelacion)} h antes` |
| `acciones` | `""` | 1 | `4rem`, `col-acciones` | `MenuAcciones` con Editar y, si `a.activo`, "Dar de baja" (peligro) |

El `renderTarjeta` es la ficha actual completa (`<h3>`, descripción, el `<dl>` y los botones), sin cambios. `.grid-fichas` sobrevive como estilo de las tarjetas en mobile — **no borrarlo** de `index.css:2885-2899`.

`claveFila={(a) => a.id}`, `vacio="Sin amenities."`

El `className={`tarjeta${a.activo ? "" : " inactivo"}`}` de la línea 55 se traslada a la `<Tarjeta className={a.activo ? "" : "inactivo"}>` del `renderTarjeta`.

- [ ] **Step 3: Correr tests y lint**

Run: `cd frontend && npm test && npm run lint`
Expected: tests PASS. El lint termina en `✖ 87 problems` o menos — baseline preexistente, no una falla de esta tarea.

- [ ] **Step 4: Verificar en el browser**

`/gastos/habituales` y `/amenities` a **375, 768, 1024 y 1440px**. A 1440px las dos tienen que ser tabla y llenar el ancho útil. A 375px, tarjetas idénticas a las de antes.

Probar "Dar de baja" en Amenities: usa `window.confirm` (`Amenities.jsx:21`). Confirmar que el diálogo aparece con el menú `⋯` ya cerrado y que cancelarlo no deja la fila en un estado raro.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/GastosHabituales.jsx frontend/src/screens/Amenities.jsx
git commit -m "feat: gastos recurrentes y amenities pasan a tabla en tablet y desktop"
```

---

### Task 11: Clases de prorrateo y Proveedores pasan a tabla

**Files:**
- Modify: `frontend/src/screens/ClasesProrrateo.jsx:58-79`
- Modify: `frontend/src/screens/Proveedores.jsx:66-85`

**Interfaces:**
- Consumes: `TablaResponsive`, `MenuAcciones`, `Tarjeta`.
- Produces: nada.

- [ ] **Step 1: ClasesProrrateo**

Reemplazar el `<ul className="lista-config">` (línea 58):

| clave | título | prioridad | ancho | celda |
|---|---|---|---|---|
| `codigo` | Código | 1 | `12ch` | `c.codigo` |
| `nombre` | Nombre | 1 | `auto` | `c.nombre` |
| `descripcion` | Descripción | 3 | `30%` | `c.descripcion \|\| "—"` |
| `estado` | Estado | 2 | `11ch` | `c.activa ? "Activa" : "Inactiva"` |
| `acciones` | `""` | 1 | `4rem`, `col-acciones` | `MenuAcciones`: Editar / `c.activa ? "Desactivar" : "Activar"` (`toggleActiva(c)`) / Eliminar (`borrar(c)`, peligro) |

`claveFila={(c) => c.id}`, `vacio="No hay clases cargadas."`

El `{clases.length === 0 && <p>No hay clases cargadas.</p>}` de la línea 56 se borra: ahora lo cubre `vacio`.

- [ ] **Step 2: Proveedores**

Reemplazar el `<ul className="lista-config">` (línea 66):

| clave | título | prioridad | ancho | celda |
|---|---|---|---|---|
| `razon` | Razón social | 1 | `auto` | `p.razon_social` |
| `fantasia` | Nombre fantasía | 3 | `auto` | `p.nombre_fantasia \|\| "—"` |
| `cuit` | CUIT | 1 | `15ch` | `p.cuit` |
| `direccion` | Dirección | 3 | `auto` | `p.direccion \|\| "—"` |
| `estado` | Estado | 2 | `11ch` | `p.activo ? "Activo" : "Inactivo"` |
| `acciones` | `""` | 1 | `4rem`, `col-acciones` | `MenuAcciones`: Editar / `p.activo ? "Desactivar" : "Activar"` (`toggleActivo(p)`) |

Proveedores **no** tiene acción de eliminar; no inventarla.

`claveFila={(p) => p.id}`, `vacio="No hay proveedores con esos filtros."`. Borrar el `{proveedores.length === 0 && <p>…</p>}` de la línea 64.

- [ ] **Step 3: Correr tests y lint**

Run: `cd frontend && npm test && npm run lint`
Expected: tests PASS. El lint termina en `✖ 87 problems` o menos — baseline preexistente, no una falla de esta tarea.

- [ ] **Step 4: Verificar en el browser**

`/clases-prorrateo` y `/proveedores` a **375, 768, 1024 y 1440px**. Confirmar que el mensaje de lista vacía sigue apareciendo (filtrar por algo que no exista en Proveedores).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/ClasesProrrateo.jsx frontend/src/screens/Proveedores.jsx
git commit -m "feat: clases de prorrateo y proveedores pasan a tabla"
```

---

### Task 12: Barra de período de Gastos

Dos bugs chicos y visibles: el mes cortado y el verde que desentona.

**Files:**
- Modify: `frontend/src/index.css:1175-1190`
- Modify: `frontend/src/screens/Gastos.jsx:240-250`

**Interfaces:**
- Consumes: nada.
- Produces: clases `.estado-punto--abierto` y `.estado-punto--cerrado`.

- [ ] **Step 1: Arreglar el ancho del input de mes**

En `frontend/src/index.css`, la regla `.barra-periodo-selector input[type="month"]` (línea 1175). Reemplazar la línea 1179:

```css
  width: 9.5rem;
```

por:

```css
  /* Chrome renderiza "agosto de 2026" y no entraba en los 9.5rem fijos que
     había acá: el mes salía cortado. El piso evita que el campo cambie de
     tamaño entre meses de nombre corto y largo. */
  width: auto;
  min-width: 9.5rem;
```

- [ ] **Step 2: Aliviar las flechas**

En la regla `.periodo-nav` (línea 1183), cambiar la línea 1188:

```css
  font-size: 1rem;
```

por:

```css
  font-size: 0.875rem;
```

**No tocar** `min-width: 44px` / `min-height: 44px` (líneas 1195-1199): eso es el área táctil accesible, no peso visual.

- [ ] **Step 3: Agregar las clases del punto de estado**

Al final del bloque de la barra de período en `index.css`:

```css
/* El verde y el gris de estos puntos estaban escritos a mano en Gastos.jsx
   (#16a34a / #6b7280): colores sueltos, fuera de la paleta, que desentonaban
   con todo lo que tenían al lado. */
.estado-punto--abierto { background: var(--color-success); }
.estado-punto--cerrado { background: var(--color-text-muted); }
```

- [ ] **Step 4: Sacar los estilos inline de `Gastos.jsx`**

Reemplazar el bloque de las líneas 240-250 por:

```jsx
          {cerrados.has(periodo) ? (
            <span className="estado-badge" title="Este período ya fue cerrado">
              <span className="estado-punto estado-punto--cerrado" aria-hidden="true" />
              Cerrado
            </span>
          ) : (
            <span className="estado-badge" title="Los gastos de este período aún se pueden modificar">
              <span className="estado-punto estado-punto--abierto" aria-hidden="true" />
              Abierto
            </span>
          )}
```

- [ ] **Step 5: Verificar que no quedan hex sueltos en esa pantalla**

Run: `cd frontend && grep -n "#[0-9a-fA-F]\{6\}" src/screens/Gastos.jsx`
Expected: sin resultados.

- [ ] **Step 6: Verificar en el browser**

`/gastos` a **375, 768 y 1440px**:

1. Navegar con `‹` `›` hasta agosto y hasta septiembre. **"agosto de 2026" y "septiembre de 2026" tienen que verse enteros**, y el campo no debe saltar de ancho entre uno y otro.
2. El punto verde de "Abierto" ya no compite con las flechas.
3. Las flechas siguen siendo clickeables con el dedo a 375px (área de 44px intacta).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/index.css frontend/src/screens/Gastos.jsx
git commit -m "fix: el filtro de periodo ya no corta el mes y el punto de estado usa la paleta"
```

---

### Task 13: Campanita

**Files:**
- Modify: `frontend/src/components/Campanita.jsx`
- Modify: `frontend/src/index.css` (bloque `.campanita*`)

**Interfaces:**
- Consumes: `formatearTiempoRelativo` de `../utils/tiempoRelativo` (Task 1).
- Produces: nada.

Dirección elegida por el usuario: **punto discreto** (el patrón de Linear y Notion). Sin número.

- [ ] **Step 1: Reemplazar el emoji por un SVG**

En `Campanita.jsx`, reemplazar el bloque del botón (líneas 61-70) por:

```jsx
      <button
        type="button"
        onClick={toggle}
        className={`campanita-boton${abierto ? " abierto" : ""}`}
        aria-label={count > 0 ? "Notificaciones sin leer" : "Notificaciones"}
        aria-expanded={abierto}
      >
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="1.8"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {count > 0 && <span className="campanita-badge" aria-hidden="true" />}
      </button>
```

Un emoji es una fuente del sistema operativo: se dibuja distinto en Windows, Mac y Android, tiene color propio que ignora la paleta y no admite ajuste de trazo. El SVG con `stroke="currentColor"` toma el color del CSS.

`obtenerNoLeidasCount` se sigue llamando igual y `count` se sigue guardando: lo único que cambia es que la UI ahora lee `count > 0` en vez de mostrar el número. **No tocar `api/notificaciones.js` ni el backend.**

- [ ] **Step 2: Convertir el `<li onClick>` en `<button>`**

Reemplazar el bloque de la lista (líneas 89-102) por:

```jsx
            <ul className="campanita-lista">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => handleClickNotif(n)}
                    className={`campanita-item${n.leida ? "" : " campanita-item-no-leida"}`}
                  >
                    <span className="campanita-item-mensaje">{n.mensaje}</span>
                    <span className="campanita-item-fecha">
                      {formatearTiempoRelativo(n.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
```

El `<li onClick>` de la línea 92 no era alcanzable por teclado y viola la regla del proyecto contra controles que no son `<button>`. Los `<p>` pasan a `<span>` porque ahora viven dentro de un botón, y un `<p>` adentro de un `<button>` es HTML inválido.

Agregar el import arriba:

```jsx
import { formatearTiempoRelativo } from "../utils/tiempoRelativo";
```

- [ ] **Step 3: Ajustar el CSS de la campanita**

En el bloque `.campanita*` de `index.css`, reemplazar el badge numérico por el punto y afinar el panel:

```css
.campanita-badge {
  position: absolute;
  top: 7px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-pill);
  background: var(--color-danger);
  /* El borde del color de la superficie separa el punto del ícono: sin él,
     el punto se funde con el trazo de la campana. */
  border: 2px solid var(--color-surface);
}

.campanita-boton.abierto {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.campanita-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.2rem;
  width: 100%;
  text-align: left;
  padding: 0.6rem 0.85rem;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
}

.campanita-item-no-leida {
  background: var(--color-primary-soft);
}

.campanita-item-mensaje {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.35;
}

.campanita-item-fecha {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--color-text-muted);
}
```

Borrar las reglas viejas de `.campanita-badge` (las del contador numérico) y las de `.campanita-item-mensaje` / `-fecha` que asumían `<p>`.

- [ ] **Step 4: El panel sube como sheet en mobile**

Hoy `.campanita-panel` (`index.css:562-575`) es un dropdown absoluto en todos los anchos: `min-width: 20rem` acotado por `max-width: 90vw`. A 375px eso deja un panel flotante y apretado contra el borde, cuando el resto de la app ya resuelve esto subiendo una sheet desde abajo.

Reescribir la regla mobile-first: base = sheet, y de 600px para arriba vuelve a ser dropdown.

```css
/* Base (mobile): sheet a lo ancho, anclada abajo. Mismo patrón y misma
   animación que SheetCuenta, que es lo que el usuario ya conoce. */
.campanita-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  top: auto;
  z-index: 100;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-bottom: none;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  max-height: 70vh;
  overflow-y: auto;
  box-shadow: var(--shadow-md);
  animation: sheetIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@media (min-width: 600px) {
  .campanita-panel {
    position: absolute;
    top: 100%;
    left: auto;
    right: 0;
    bottom: auto;
    min-width: 20rem;
    max-width: 90vw;
    max-height: 25rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
    animation: none;
  }
}
```

El `@keyframes sheetIn` ya existe en `index.css:74` — no redefinirlo.

- [ ] **Step 5: Correr tests, lint y build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: tests PASS, build sin errores. El lint termina en `✖ 87 problems` o menos — baseline preexistente.

- [ ] **Step 6: Verificar en el browser**

Con sesión que tenga notificaciones sin leer, a **375, 768 y 1440px**:

1. El ícono es de trazo, toma el color de la paleta y no es un emoji.
2. Con no leídas aparece el punto rojo; sin no leídas, no aparece nada.
3. El panel muestra "hace X min" / "ayer" en vez del timestamp largo.
4. Con Tab se llega a cada notificación y con Enter se abre su link.
5. A **375px el panel sube desde abajo como sheet**, a lo ancho de la pantalla; a 768px y 1440px sigue siendo dropdown anclado a la derecha del botón.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Campanita.jsx frontend/src/index.css
git commit -m "feat: campanita con icono propio y punto discreto en vez de emoji"
```

---

## Verificación final

Después de la última tarea, antes de dar el trabajo por cerrado:

- [ ] `cd frontend && npm test` — todos verdes.
- [ ] `cd frontend && npm run build` — sin errores.
- [ ] `cd frontend && npm run lint` — **87 problemas o menos**. Ese es el baseline de master medido antes de arrancar; el plan no arregla deuda de lint preexistente, solo se compromete a no sumarla.
- [ ] `pytest -v` desde la raíz — verde. El backend no se tocó; esto confirma que sigue siendo cierto.
- [ ] `cd frontend && grep -rn "#[0-9a-fA-F]\{3,6\}" src/screens/ src/components/` — revisar cada resultado. Los hex que queden tienen que estar justificados o migrados a `var(--color-…)`.
- [ ] Recorrido completo a **375px** de las 14 pantallas tocadas, confirmando `document.documentElement.scrollWidth === document.documentElement.clientWidth` en cada una. Es el ancho que revisa el usuario.
- [ ] Recorrido a **768px** — el rango que motivó todo el trabajo. Ninguna tabla debe pedir scroll horizontal.
