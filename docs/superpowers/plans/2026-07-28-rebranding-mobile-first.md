# Rebranding visual mobile-first — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Llevar el frontend al mockup de `rediseño mobile first/` — tokens nuevos, shell con header coloreado por módulo y tab bar en mobile, bottom sheets, y una pantalla Inicio de admin.

**Architecture:** El reskin se hace cambiando los valores de las variables CSS en `:root` **sin renombrarlas**, para que las ~130 clases existentes se actualicen solas en las 41 pantallas. Encima de eso van tres piezas nuevas de shell (header con `data-modulo`, `TabBar`, sheet de cuenta) y una pantalla nueva. Los bottom sheets son CSS puro sobre el `Modal.jsx` compartido.

**Tech Stack:** React 19, react-router-dom 6, Vite 8. CSS plano con variables — sin preprocesador, sin librería de componentes, sin CSS-in-JS.

## Global Constraints

- **Nunca hardcodear hex/rgb en componentes JSX.** Regla de `.claude/rules/frontend.md`. Todo color se consume vía `var(--color-...)`. El color por módulo se resuelve con el atributo `data-modulo` y una regla CSS, no con `style={{background: ...}}`.
- **Mobile-first.** El CSS base apunta a ≥320px; las mejoras van en `@media (min-width: 600px)` y `@media (min-width: 960px)`. Nunca `max-width` para el caso base.
- **Densidad según breakpoint.** Base mobile: botones full-width, uppercase, peso 800, sombra en primarios. Desde 600px: `fit-content`, 36px, ghost, sin uppercase ni sombra.
- **Al subir de breakpoint el contenido se reorganiza, no se estira.** Nada de tomar un bloque mobile y darle `width: 100%` en desktop.
- **Targets táctiles ≥44px** de alto.
- **HTML semántico:** `<nav>`, `<main>`, `<header>`, `<section>`, `<button>`. Sin `<div onClick>`.
- **Sin cambios de backend.** Ningún endpoint, schema ni modelo se toca en este plan.
- **Verificación sin tests unitarios.** El proyecto no tiene framework de tests de frontend (`package.json` define solo `dev`, `build`, `lint`, `preview`). El ciclo de verificación de cada tarea es `npm run build` + `npm run lint` + revisión en browser a 375px. Esto es una desviación consciente del TDD por defecto: montar Vitest sería scope que el spec no aprobó. Ver "Nota sobre testing" al final.

---

## Estructura de archivos

| Archivo | Responsabilidad | Tarea |
|---|---|---|
| `frontend/index.html` | Carga de fuentes Google | 1 |
| `frontend/src/index.css` | Tokens + todas las clases compartidas | 1, 2, 3, 5, 6 |
| `frontend/public/logo-comand.png` | Logo de marca | 5 |
| `frontend/src/navegacion.js` | **Nuevo.** Fuente única de rutas, filtrado por rol, mapa ruta→módulo | 4 |
| `frontend/src/components/Sidebar.jsx` | Consume `navegacion.js` en vez de su array propio | 4 |
| `frontend/src/components/AppLayout.jsx` | Header con `data-modulo`, monta `TabBar` y `SheetCuenta` | 5, 6 |
| `frontend/src/components/SheetCuenta.jsx` | **Nuevo.** Sheet de usuario/consorcio/logout | 5 |
| `frontend/src/components/TabBar.jsx` | **Nuevo.** Tab bar mobile + sheet "Más" | 6 |
| `frontend/src/screens/Inicio.jsx` | **Nuevo.** Dashboard de admin | 7 |
| `frontend/src/App.jsx` | Reruteo de `/` por rol | 7 |

---

### Task 1: Tokens y tipografías

**Files:**
- Modify: `frontend/src/index.css:8-41` (bloque `:root`)
- Modify: `frontend/index.html:7-13` (link de Google Fonts)

**Interfaces:**
- Consumes: nada.
- Produces: las variables que todas las tareas siguientes consumen — `--color-bg`, `--color-surface`, `--color-text`, `--color-text-muted`, `--color-border`, `--color-border-strong`, `--color-primary`, `--color-primary-hover`, `--color-primary-soft`, `--color-danger`, `--color-danger-bg`, `--color-danger-hover`, `--color-success`, `--color-success-bg`, `--color-warning`, `--color-warning-bg`, `--color-mod-inicio`, `--color-mod-cobranzas`, `--color-mod-gastos`, `--color-mod-finanzas`, `--color-mod-expensas`, `--color-mod-operacion`, `--color-modulo`, `--color-tab-inactivo`, `--radius`, `--radius-sm`, `--radius-lg`, `--radius-pill`, `--shadow-md`, `--altura-tabbar`, `--font-sans`, `--font-display`.

- [ ] **Step 1: Reemplazar el bloque `:root` de `index.css`**

Sustituir las líneas 8 a 41 por:

```css
:root {
  /* Paleta — mockup mobile-first (2026-07) */
  --color-bg: #f4f0e6;
  --color-surface: #ffffff;
  --color-text: #121212;
  --color-text-muted: #757168;
  --color-border: #e3ded2;
  --color-border-strong: #d6d0c4;
  --color-primary: #2c6473;
  --color-primary-hover: #24525e;
  --color-primary-soft: #e7f0f3;
  --color-danger: #c0443c;
  --color-danger-bg: #f7e0de;
  --color-danger-hover: #a93b34;
  --color-success: #2d8f5e;
  --color-success-bg: #e3efe7;
  --color-warning: #8a6d1c;
  --color-warning-bg: #f7efd4;

  /* Color por módulo — lo aplica [data-modulo] más abajo */
  --color-mod-inicio: #1b3a4b;
  --color-mod-cobranzas: #305d4a;
  --color-mod-gastos: #c0443c;
  --color-mod-finanzas: #8a6d1c;
  --color-mod-expensas: #2c6473;
  --color-mod-operacion: #5b36b8;
  --color-modulo: var(--color-mod-inicio);
  --color-tab-inactivo: #9b968a;

  /* Geometría y elevación */
  --radius-sm: 12px;
  --radius: 16px;
  --radius-lg: 20px;
  --radius-pill: 999px;
  --shadow-md: 0 8px 24px rgba(18, 18, 18, 0.1);
  --altura-tabbar: 62px;

  /* Tipografía */
  --font-sans: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Montserrat", var(--font-sans);

  font-family: var(--font-sans);
  font-size: 16px;
  color: var(--color-text);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Cada ruta pinta su módulo; el default de :root cubre las rutas no mapeadas. */
[data-modulo="inicio"]     { --color-modulo: var(--color-mod-inicio); }
[data-modulo="cobranzas"]  { --color-modulo: var(--color-mod-cobranzas); }
[data-modulo="gastos"]     { --color-modulo: var(--color-mod-gastos); }
[data-modulo="finanzas"]   { --color-modulo: var(--color-mod-finanzas); }
[data-modulo="expensas"]   { --color-modulo: var(--color-mod-expensas); }
[data-modulo="operacion"]  { --color-modulo: var(--color-mod-operacion); }
```

- [ ] **Step 2: Aplicar la fuente display a los títulos**

Reemplazar la regla `h1, h2, h3` (actualmente en `index.css:52-57`) por:

```css
h1, h2, h3 {
  margin: 0 0 0.5em;
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--color-text);
}
```

- [ ] **Step 3: Cambiar las fuentes en `index.html`**

Reemplazar el `<link>` de Inter (línea 12-15) por:

```html
    <link
      href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
      rel="stylesheet"
    />
```

- [ ] **Step 4: Verificar build y lint**

```bash
cd frontend && npm run build && npm run lint
```
Esperado: build exitoso, lint sin errores nuevos.

- [ ] **Step 5: Verificar en browser**

```bash
cd frontend && npm run dev
```
Abrir con DevTools en iPhone SE (375px). Confirmar: fondo crema, títulos en Montserrat, texto en Plus Jakarta Sans, primarios en teal. **La app va a verse a medio camino en este punto — es lo esperado**, las clases se ajustan en la tarea 2.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/index.html
git commit -m "feat(ui): tokens y tipografias del rebranding mobile-first"
```

---

### Task 2: Lenguaje visual y botones responsive

**Files:**
- Modify: `frontend/src/index.css` — reglas `button` (71-92), `.tarjeta` (1145-1151), `.badge` (1377-1384), `.seccion-header` (625-631), `.boton-secundario` (1355-1364), `.cta-sticky` (1884-1897), y el `@media (min-width: 600px)` de la línea 1499.

**Interfaces:**
- Consumes: todas las variables de la Task 1.
- Produces: clases `.regla-seccion` y `.micro-label` (nuevas, las usa la Task 7); `.tarjeta`, `.badge` y `button` reskineados (los consumen todas las pantallas existentes sin cambios de JSX).

- [ ] **Step 1: Botones — base mobile**

Reemplazar la regla `button` (líneas 71-83) por:

```css
button {
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  width: 100%;
  min-height: 44px;
  padding: 0.6em 1.2em;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 10px rgb(from var(--color-primary) r g b / 0.25);
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
```

- [ ] **Step 2: Botones — aliviane desde 600px**

Agregar dentro del `@media (min-width: 600px)` que arranca en la línea 1499:

```css
  button {
    width: fit-content;
    min-height: 36px;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: none;
    letter-spacing: normal;
    box-shadow: none;
  }
```

- [ ] **Step 3: Tarjetas y badges**

Reemplazar la regla `.tarjeta` (1145-1151) conservando sus propiedades actuales pero con el radio nuevo, y `.badge` (1377-1384) por la pill con punto:

```css
.tarjeta {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.9rem;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: var(--radius-pill);
  border: none;
  font-size: 0.625rem;
  font-weight: 700;
  text-transform: none;
  letter-spacing: normal;
  width: auto;
  min-height: 0;
  box-shadow: none;
}

.badge::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: var(--radius-pill);
  background: currentColor;
  flex-shrink: 0;
}
```

- [ ] **Step 4: Regla de sección y micro-label**

Agregar después de `.seccion-header` (línea 631):

```css
.regla-seccion {
  border-top: 2px solid var(--color-text);
  padding-top: 0.75rem;
  margin-bottom: 1.4rem;
}

.micro-label {
  margin: 0 0 2px;
  font-size: 0.625rem;
  font-weight: 800;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

/* Todo lo monetario alinea por dígito */
.monto,
td.monto {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
```

- [ ] **Step 5: Reconciliar `.cta-sticky` con la futura tab bar**

Reemplazar el bloque `@media (max-width: 599px)` de las líneas 1889-1897 — nótese que el spec exige mobile-first, así que se invierte a `min-width`:

```css
.cta-sticky {
  position: sticky;
  bottom: calc(var(--altura-tabbar) + env(safe-area-inset-bottom));
  background: var(--color-surface);
  padding: 0.5rem 0;
  box-shadow: 0 -2px 8px rgba(18, 18, 18, 0.06);
}

@media (min-width: 960px) {
  .cta-sticky {
    position: static;
    bottom: auto;
    background: transparent;
    box-shadow: none;
  }
}
```

- [ ] **Step 6: Verificar build, lint y browser**

```bash
cd frontend && npm run build && npm run lint && npm run dev
```
A 375px recorrer Cobranzas, Gastos y Tesorería. Confirmar que los badges muestran el punto de color, que las tarjetas tienen el radio de 16px y que ningún botón desborda el viewport.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(ui): lenguaje visual del mockup y botones responsive"
```

---

### Task 3: Bottom sheets

**Files:**
- Modify: `frontend/src/index.css` — `.modal-backdrop` y `.modal` (el bloque que arranca donde hoy está `.modal-backdrop`).

**Interfaces:**
- Consumes: `--radius-lg`, `--color-bg`, `--color-border-strong`, `--shadow-md`.
- Produces: nada nuevo. `Modal.jsx` y sus 16 consumidores quedan intactos.

- [ ] **Step 1: Definir la animación**

Agregar cerca del tope de `index.css`, después del bloque `[data-modulo]`:

```css
@keyframes sheetIn {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}
```

- [ ] **Step 2: Anclar el modal abajo**

Reemplazar `.modal-backdrop` y `.modal` por:

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(14, 31, 41, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 1000;
  padding: 0;
}

.modal {
  background: var(--color-bg);
  border-radius: 24px 24px 0 0;
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 100%;
  max-height: 88%;
  display: flex;
  flex-direction: column;
  animation: sheetIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  padding-bottom: env(safe-area-inset-bottom);
}

/* Grab handle */
.modal::before {
  content: "";
  width: 40px;
  height: 4px;
  border-radius: var(--radius-pill);
  background: var(--color-border-strong);
  margin: 10px auto 4px;
  flex-shrink: 0;
}
```

- [ ] **Step 3: Volver a modal centrado desde 600px**

Agregar dentro del `@media (min-width: 600px)` de la línea ~1499:

```css
  .modal-backdrop {
    align-items: center;
    padding: 1.5rem;
  }

  .modal {
    border-radius: var(--radius);
    max-width: 560px;
    max-height: 90%;
    animation: none;
    padding-bottom: 0;
  }

  .modal::before {
    display: none;
  }
```

- [ ] **Step 4: Verificar**

```bash
cd frontend && npm run build && npm run lint && npm run dev
```
A 375px abrir un modal (por ejemplo el detalle de una petición en `/peticiones`) y confirmar que entra deslizándose desde abajo con el handle visible. Ensanchar a 700px y confirmar que vuelve a modal centrado. **Confirmar que Escape y el click en el backdrop siguen cerrando** — esa lógica vive en `Modal.jsx` y no se tocó.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(ui): modales como bottom sheets en mobile"
```

---

### Task 4: `navegacion.js` — fuente única de rutas

**Files:**
- Create: `frontend/src/navegacion.js`
- Create: `frontend/src/hooks/useNavegacionVisible.js`
- Modify: `frontend/src/components/Sidebar.jsx:7-202` (borrar `ORDEN_DEPTO`, `SECCIONES` y `grupoDeRuta`, importarlos) y `205-263` (reemplazar el estado propio por el hook)

**Interfaces:**
- Consumes: nada.
- Produces, desde `navegacion.js`:
  - `SECCIONES: Array<{titulo: string, modulos: Array<{ruta, nombre, rolesPermitidos, modulo?}>}>`
  - `ORDEN_DEPTO: string[]`
  - `grupoDeRuta(pathname: string): string | null`
  - `filtrarSecciones({rol, modulosHabilitados, usaPersonalPropio, reportesVisiblesDepto}): typeof SECCIONES`
  - `moduloDeRuta(pathname: string): string` — devuelve la clave de `data-modulo` (`"inicio" | "cobranzas" | "gastos" | "finanzas" | "expensas" | "operacion"`)
  - `TABS_POR_ROL: Record<string, Array<{ruta, nombre, modulo, icono}>>`
- Produces, desde `hooks/useNavegacionVisible.js`:
  - `useNavegacionVisible(rol): { secciones, seccionesMas, cargando }` — hace **un solo** par de fetches por consorcio activo y devuelve las secciones ya filtradas. Lo consumen `Sidebar.jsx`, `AppLayout.jsx` y `TabBar.jsx`.

**Por qué el hook:** hoy `Sidebar.jsx` guarda `modulosHabilitados`, `usaPersonalPropio` y `reportesVisiblesDepto` como estado privado y los carga en su propio `useEffect` (líneas 226-244). La tab bar y la sheet "Más" necesitan exactamente lo mismo. Sin el hook habría dos componentes disparando los mismos dos requests y dos copias del filtrado que pueden divergir.

- [ ] **Step 1: Crear `navegacion.js` con lo movido desde `Sidebar.jsx`**

Copiar **textualmente** los arrays `ORDEN_DEPTO` (línea 7) y `SECCIONES` (líneas 9-189) y la función `grupoDeRuta` (191-202) de `Sidebar.jsx` al archivo nuevo, agregándoles `export`. No modificar su contenido — es lógica que hoy funciona.

- [ ] **Step 2: Agregar el filtrado, extraído de `Sidebar.jsx:246-263`**

```js
export function filtrarSecciones({
  rol,
  modulosHabilitados,
  usaPersonalPropio,
  reportesVisiblesDepto,
}) {
  return SECCIONES.map((s) => ({
    ...s,
    modulos: s.modulos.filter((m) => {
      if (!m.rolesPermitidos.includes(rol)) return false;
      if (
        rol === "departamento" &&
        m.ruta.startsWith("/reportes/") &&
        !reportesVisiblesDepto
      ) {
        return false;
      }
      if (
        m.modulo &&
        modulosHabilitados !== null &&
        !modulosHabilitados.includes(m.modulo)
      ) {
        return false;
      }
      return true;
    }),
  }))
    .filter((s) => s.modulos.length > 0)
    .filter((s) => usaPersonalPropio || s.titulo !== "Personal");
}
```

- [ ] **Step 3: Agregar el mapa ruta → módulo**

```js
// Prefijo de ruta → clave de data-modulo. Se evalúa en orden; el primero que
// matchea gana, así que los prefijos más específicos van primero.
const MODULO_POR_RUTA = [
  ["/cobranzas", "cobranzas"],
  ["/cuentas-corrientes", "cobranzas"],
  ["/comprobantes", "cobranzas"],
  ["/gastos", "gastos"],
  ["/tesoreria", "finanzas"],
  ["/estado-financiero", "finanzas"],
  ["/cajas", "finanzas"],
  ["/transferencias", "finanzas"],
  ["/comunicados", "finanzas"],
  ["/expensas", "expensas"],
  ["/mi-cuenta", "expensas"],
  ["/departamentos", "expensas"],
  ["/cierre-de-periodo", "expensas"],
  ["/periodos", "expensas"],
  ["/liquidaciones", "expensas"],
  ["/peticiones", "operacion"],
  ["/trabajos", "operacion"],
  ["/amenities", "operacion"],
  ["/reservas", "cobranzas"],
];

export function moduloDeRuta(pathname) {
  if (pathname === "/") return "inicio";
  const hit = MODULO_POR_RUTA.find(
    ([prefijo]) => pathname === prefijo || pathname.startsWith(prefijo + "/")
  );
  return hit ? hit[1] : "inicio";
}
```

- [ ] **Step 4: Agregar `TABS_POR_ROL`**

Los `icono` son claves que `TabBar.jsx` resuelve a SVG en la Task 6.

```js
export const TABS_POR_ROL = {
  administracion: [
    { ruta: "/", nombre: "Inicio", modulo: "inicio", icono: "casa" },
    { ruta: "/cobranzas", nombre: "Cobranzas", modulo: "cobranzas", icono: "moneda" },
    { ruta: "/gastos", nombre: "Gastos", modulo: "gastos", icono: "documento" },
    { ruta: "/tesoreria", nombre: "Finanzas", modulo: "finanzas", icono: "billetera" },
    { ruta: "/peticiones", nombre: "Operación", modulo: "operacion", icono: "llave" },
  ],
  departamento: [
    { ruta: "/mi-cuenta", nombre: "Mi cuenta", modulo: "expensas", icono: "casa" },
    { ruta: "/peticiones", nombre: "Peticiones", modulo: "operacion", icono: "chat" },
    { ruta: "/reservas", nombre: "Reservas", modulo: "cobranzas", icono: "calendario" },
    { ruta: "/comunicados", nombre: "Comunicados", modulo: "finanzas", icono: "campana" },
  ],
  representante: [
    { ruta: "/comunicados", nombre: "Comunicados", modulo: "finanzas", icono: "campana" },
    { ruta: "/peticiones", nombre: "Peticiones", modulo: "operacion", icono: "chat" },
    { ruta: "/trabajos", nombre: "Trabajos", modulo: "operacion", icono: "llave" },
  ],
};
```

- [ ] **Step 5: Crear el hook compartido**

`frontend/src/hooks/useNavegacionVisible.js` — mueve acá el `useEffect` que hoy vive en `Sidebar.jsx:226-244`, tal cual, y expone también las secciones que van a la sheet "Más" (las que no son tab):

```js
import { useEffect, useState } from "react";
import { obtenerConfiguracion } from "../api/configuracion";
import { obtenerConsorcio } from "../api/consorcios";
import { useAuth } from "../auth/AuthContext";
import { filtrarSecciones, TABS_POR_ROL } from "../navegacion";

export function useNavegacionVisible(rol) {
  const { consorcioActivoId } = useAuth();
  const [reportesVisiblesDepto, setReportesVisiblesDepto] = useState(false);
  const [usaPersonalPropio, setUsaPersonalPropio] = useState(true);
  const [modulosHabilitados, setModulosHabilitados] = useState(null); // null = cargando → mostrar todo
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!consorcioActivoId) return;
    setModulosHabilitados(null);
    setCargando(true);
    (async () => {
      const r = await obtenerConfiguracion();
      if (r.status === 200) {
        setReportesVisiblesDepto(!!r.data?.reportes_visibles_a_depto);
      }
      const c = await obtenerConsorcio(consorcioActivoId);
      if (c.status === 200 && c.data?.usa_personal_propio !== undefined) {
        setUsaPersonalPropio(!!c.data.usa_personal_propio);
      }
      if (c.status === 200 && Array.isArray(c.data?.modulos_habilitados)) {
        setModulosHabilitados(c.data.modulos_habilitados);
      }
      setCargando(false);
    })();
  }, [rol, consorcioActivoId]);

  const secciones = filtrarSecciones({
    rol,
    modulosHabilitados,
    usaPersonalPropio,
    reportesVisiblesDepto,
  });

  const rutasEnTabs = new Set((TABS_POR_ROL[rol] ?? []).map((t) => t.ruta));
  const seccionesMas = secciones
    .map((s) => ({ ...s, modulos: s.modulos.filter((m) => !rutasEnTabs.has(m.ruta)) }))
    .filter((s) => s.modulos.length > 0);

  return { secciones, seccionesMas, cargando };
}
```

- [ ] **Step 6: Adelgazar `Sidebar.jsx`**

Borrar las líneas 7-202 (los dos arrays y `grupoDeRuta`) y los `useState`/`useEffect` de configuración (205-244), reemplazándolos por:

```jsx
import { grupoDeRuta, ORDEN_DEPTO } from "../navegacion";
import { useNavegacionVisible } from "../hooks/useNavegacionVisible";

// dentro del componente, en lugar del estado propio y del map/filter inline:
const { secciones: seccionesVisibles } = useNavegacionVisible(rol);
```

El `useState` de `grupoAbierto` y todo el render del drawer no cambian.

- [ ] **Step 7: Verificar que la navegación no se rompió**

```bash
cd frontend && npm run build && npm run lint && npm run dev
```
Este es un refactor sin cambio visible, así que la verificación es de **no regresión**. Con un usuario admin: confirmar que el sidebar lista los mismos grupos que antes, que el grupo de la ruta actual se abre solo, y que los links navegan. Repetir con un usuario departamento (debe ver la lista plana ordenada por `ORDEN_DEPTO`). En la pestaña Network confirmar que `/configuracion` y `/consorcios/{id}` se piden **una sola vez** por consorcio activo, no dos.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/navegacion.js frontend/src/hooks/useNavegacionVisible.js frontend/src/components/Sidebar.jsx
git commit -m "refactor(nav): extraer rutas y filtrado a navegacion.js"
```

---

### Task 5: Header con color por módulo, logo y sheet de cuenta

**Files:**
- Create: `frontend/public/logo-comand.png` (copiado de `rediseño mobile first/assets/logo-comand.png`)
- Create: `frontend/src/components/SheetCuenta.jsx`
- Modify: `frontend/src/components/AppLayout.jsx` (todo el `<header>`)
- Modify: `frontend/src/index.css` — `.app-header` y siguientes (262-330), y el `@media (min-width: 960px)` de la línea 1556

**Interfaces:**
- Consumes: `moduloDeRuta` de `navegacion.js` (Task 4); `--color-modulo` (Task 1); `.modal` como sheet (Task 3).
- Produces: `<SheetCuenta abierta={boolean} onCerrar={() => void} />`; clases `.app-header`, `.app-logo`, `.app-modulo-label`, `.avatar-boton`.
- Produces también `nombreDeUsuario(email: string): string` — helper exportado desde `SheetCuenta.jsx`, que la Task 7 reutiliza para el saludo.

- [ ] **Step 1: Copiar el logo**

```bash
cp "rediseño mobile first/assets/logo-comand.png" frontend/public/logo-comand.png
```

- [ ] **Step 2: Crear `SheetCuenta.jsx`**

`UsuarioOut` no tiene campo `nombre` — solo `email`, `rol` y `departamento_id`. El nombre visible se deriva del local-part del email.

```jsx
import Modal from "./Modal";
import { useAuth } from "../auth/AuthContext";
import { useNavigate } from "react-router-dom";
import SelectorConsorcio from "./SelectorConsorcio";

/** "marina.suarez@mail.com" → "Marina Suarez". El backend no guarda nombre. */
export function nombreDeUsuario(email) {
  if (!email) return "";
  return email
    .split("@")[0]
    .replace(/[._-]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

export default function SheetCuenta({ abierta, onCerrar }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!abierta) return null;

  return (
    <Modal titulo="Tu cuenta" onClose={onCerrar}>
      <section className="sheet-cuenta">
        <p className="sheet-cuenta-nombre">{nombreDeUsuario(user.email)}</p>
        <p className="sheet-cuenta-meta">
          {user.email} · {user.rol}
        </p>
        <SelectorConsorcio />
        <button
          type="button"
          className="boton-secundario"
          onClick={() => {
            onCerrar();
            navigate("/mi-usuario/cambiar-password");
          }}
        >
          Cambiar contraseña
        </button>
        <button type="button" onClick={logout}>
          Cerrar sesión
        </button>
      </section>
    </Modal>
  );
}
```

- [ ] **Step 3: Reescribir el header de `AppLayout.jsx`**

Reemplazar el `<header>` completo (líneas 30-53) por lo siguiente, y agregar el estado `sheetCuenta` y el import de `useLocation`, `moduloDeRuta` y `SheetCuenta`. El `<div className="app-shell">` pasa a llevar el `data-modulo`.

```jsx
const location = useLocation();
const [sheetCuenta, setSheetCuenta] = useState(false);
const modulo = moduloDeRuta(location.pathname);
const inicial = (user.email?.[0] ?? "?").toUpperCase();
```

```jsx
<header className="app-header">
  <div className="app-header-titulo">
    <img className="app-logo" src="/logo-comand.png" alt="COMMAND" />
    <span className="app-modulo-label">{moduloLabel}</span>
  </div>
  {!esSuperAdmin && <Campanita />}
  <button
    type="button"
    className="avatar-boton"
    aria-label="Tu cuenta"
    onClick={() => setSheetCuenta(true)}
  >
    <span aria-hidden="true">{inicial}</span>
  </button>
</header>
```

`moduloLabel` se resuelve en este orden: el nombre de la tab cuya ruta matchea, si no el grupo del sidebar, y si no el nombre del consorcio activo.

```jsx
import { grupoDeRuta, moduloDeRuta, TABS_POR_ROL } from "../navegacion";

function etiquetaModulo(pathname, rol, nombreConsorcio) {
  const tab = (TABS_POR_ROL[rol] ?? []).find(
    (t) => pathname === t.ruta || (t.ruta !== "/" && pathname.startsWith(t.ruta + "/"))
  );
  if (tab) return tab.nombre;
  return grupoDeRuta(pathname) ?? nombreConsorcio ?? "Consorcios";
}
```

```jsx
const { consorciosAccesibles, consorcioActivoId } = useAuth();
const nombreConsorcio = consorciosAccesibles.find((c) => c.id === consorcioActivoId)?.nombre;
const moduloLabel = etiquetaModulo(location.pathname, user.rol, nombreConsorcio);
```

Montar el sheet al final del `app-shell`:

```jsx
<SheetCuenta abierta={sheetCuenta} onCerrar={() => setSheetCuenta(false)} />
```

Quitar el botón `.hamburguesa` y el bloque `<nav className="app-user">`. El `SelectorConsorcio` ya no va en el header: vive dentro de `SheetCuenta`.

- [ ] **Step 4: Estilos del header**

Reemplazar `.app-header` y sus reglas asociadas (262-330):

```css
.app-header {
  background: var(--color-modulo);
  transition: background 0.35s ease;
  border-bottom: none;
  padding: 14px 18px 12px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.app-header-titulo {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.app-logo {
  height: 20px;
  width: auto;
  filter: brightness(0) invert(1);
}

.app-modulo-label {
  font-size: 0.5625rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.75);
  border-left: 2px solid rgba(255, 255, 255, 0.3);
  padding-left: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* El círculo se ve de 32px (mockup) pero el área cliqueable es de 44px
   (Global Constraint de targets táctiles). El padding transparente es lo
   que sostiene las dos cosas a la vez — no reducir a 32px el botón. */
.avatar-boton {
  width: 44px;
  height: 44px;
  min-height: 44px;
  flex-shrink: 0;
  padding: 6px;
  background: transparent;
  border: none;
  box-shadow: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-boton span {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.25);
  color: #fff;
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 0.75rem;
  letter-spacing: normal;
  display: flex;
  align-items: center;
  justify-content: center;
}
```

Y dentro del `@media (min-width: 960px)` de la línea 1556, borrar las reglas que escondían `.app-header h1` y agrupaban a la derecha (1568-1581), reemplazándolas por lo que corresponda al header nuevo. **La regla que oculta `.hamburguesa`, `.drawer-backdrop` y `.sidebar-cabecera` (1583-1587) se conserva**, porque el drawer sigue existiendo para super_admin.

- [ ] **Step 5: Verificar**

```bash
cd frontend && npm run build && npm run lint && npm run dev
```
A 375px: el header cambia de color al navegar entre `/cobranzas` (verde), `/gastos` (rojo) y `/tesoreria` (dorado), con la transición de 0.35s. El logo se ve blanco. El avatar abre la sheet, y desde ahí se puede cambiar de consorcio y cerrar sesión.

- [ ] **Step 6: Commit**

```bash
git add frontend/public/logo-comand.png frontend/src/components/SheetCuenta.jsx frontend/src/components/AppLayout.jsx frontend/src/index.css
git commit -m "feat(ui): header con color por modulo, logo COMMAND y sheet de cuenta"
```

---

### Task 6: TabBar y sheet "Más"

**Files:**
- Create: `frontend/src/components/TabBar.jsx`
- Modify: `frontend/src/components/AppLayout.jsx` (montar `TabBar`)
- Modify: `frontend/src/index.css` (clases `.tabbar*`, y `.app-content` en 616-621)

**Interfaces:**
- Consumes: `TABS_POR_ROL`, `filtrarSecciones` de `navegacion.js`; `--altura-tabbar`, `--color-modulo`, `--color-tab-inactivo`.
- Produces: `<TabBar rol={string} />`.

- [ ] **Step 1: Crear `TabBar.jsx`**

Los SVG van inline (el proyecto ya tiene `public/icons.svg` pero estos son específicos de la tab bar). `super_admin` no renderiza tab bar.

```jsx
import { useState } from "react";
import { NavLink } from "react-router-dom";
import Modal from "./Modal";
import { TABS_POR_ROL, filtrarSecciones } from "../navegacion";

const ICONOS = {
  casa: "m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
  moneda: "M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 6v2m0 8v2",
  documento: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6M16 13H8M16 17H8",
  billetera: "M21 12V7H5a2 2 0 0 1 0-4h14v4 M3 5v14a2 2 0 0 0 2 2h16v-5 M18 12a2 2 0 0 0 0 4h4v-4Z",
  llave: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z",
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  calendario: "M16 2v4M8 2v4M3 10h18",
  campana: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9 M10.3 21a1.94 1.94 0 0 0 3.4 0",
  mas: "M5 12h.01M12 12h.01M19 12h.01",
};

function Icono({ nombre }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONOS[nombre].split(" M").map((d, i) => (
        <path key={i} d={i === 0 ? d : `M${d}`} />
      ))}
    </svg>
  );
}

export default function TabBar({ rol, seccionesMas }) {
  const [sheetMas, setSheetMas] = useState(false);
  const tabs = TABS_POR_ROL[rol];

  if (!tabs) return null; // super_admin conserva su drawer

  return (
    <>
      <nav className="tabbar" aria-label="Módulos">
        {tabs.map((t) => (
          <NavLink
            key={t.ruta}
            to={t.ruta}
            end={t.ruta === "/"}
            data-modulo={t.modulo}
            className={({ isActive }) =>
              isActive ? "tabbar-item activo" : "tabbar-item"
            }
          >
            <Icono nombre={t.icono} />
            <span>{t.nombre}</span>
          </NavLink>
        ))}
        <button type="button" className="tabbar-item" onClick={() => setSheetMas(true)}>
          <Icono nombre="mas" />
          <span>Más</span>
        </button>
      </nav>

      {sheetMas && (
        <Modal titulo="Más" onClose={() => setSheetMas(false)}>
          <nav className="sheet-mas">
            {seccionesMas.map((s) => (
              <section key={s.titulo}>
                <p className="micro-label">{s.titulo}</p>
                <ul>
                  {s.modulos.map((m) => (
                    <li key={m.ruta}>
                      <NavLink to={m.ruta} onClick={() => setSheetMas(false)}>
                        {m.nombre}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </nav>
        </Modal>
      )}
    </>
  );
}
```

- [ ] **Step 2: Montar en `AppLayout.jsx`**

Dentro del `app-shell`, después del `</div>` que cierra el `app-body`. `seccionesMas` sale del hook de la Task 4 — no se recalcula acá:

```jsx
import { useNavegacionVisible } from "../hooks/useNavegacionVisible";
import TabBar from "./TabBar";

// dentro del componente:
const { seccionesMas } = useNavegacionVisible(user.rol);
```

```jsx
{!esSuperAdmin && <TabBar rol={user.rol} seccionesMas={seccionesMas} />}
```

- [ ] **Step 3: Estilos de la tab bar**

```css
.tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  display: flex;
  padding: 6px 8px calc(10px + env(safe-area-inset-bottom));
  z-index: 900;
}

.tabbar-item {
  flex: 1;
  min-height: 48px;
  width: auto;
  border: none;
  background: transparent;
  box-shadow: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-family: inherit;
  font-size: 0.5625rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: none;
  color: var(--color-tab-inactivo);
  text-decoration: none;
}

.tabbar-item.activo {
  color: var(--color-modulo);
}

@media (min-width: 960px) {
  .tabbar {
    display: none;
  }
}
```

Y ajustar `.app-content` (líneas 616-621) para que la tab bar no tape el final del contenido:

```css
.app-content {
  flex: 1;
  padding: 1rem 1rem calc(var(--altura-tabbar) + 1.5rem);
  width: 100%;
  margin: 0;
}
```

El `@media (min-width: 960px)` de la línea 1628 ya redefine `.app-content` con `padding: 2rem 1.5rem`, así que en desktop el espacio extra desaparece solo.

- [ ] **Step 4: Verificar**

```bash
cd frontend && npm run build && npm run lint && npm run dev
```
A 375px con admin: 6 tabs (5 + Más), el activo pintado del color de su módulo. Scrollear hasta el fondo de `/gastos` y confirmar que el último gasto no queda tapado. Abrir "Más" y confirmar que lista Reportes, Personal, Configuración y Padrón, **y ninguna ruta que ya sea tab**. Ensanchar a 1000px y confirmar que la tab bar desaparece y vuelve el sidebar. Repetir con depto (4 tabs + Más) y representante (3 + Más).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TabBar.jsx frontend/src/components/AppLayout.jsx frontend/src/index.css
git commit -m "feat(ui): tab bar inferior en mobile con sheet de mas"
```

---

### Task 7: Pantalla Inicio

**Files:**
- Create: `frontend/src/screens/Inicio.jsx`
- Modify: `frontend/src/App.jsx:97` (la ruta index)
- Modify: `frontend/src/index.css` (clases `.inicio-*`)

**Interfaces:**
- Consumes: `listarExpensas` (`api/expensas.js`), `obtenerGastosDelPeriodo` y `listarMorosos` (`api/reportes.js`), `listarPeticiones` (`api/peticiones.js`), `estadoPeriodo` (`api/periodos.js`), `obtenerEstadoFinanciero` (`api/estadoFinanciero.js`), `listarGastos` (`api/gastos.js`), `listarGastosHabituales` (`api/gastosHabituales.js`), `listarReservas` (`api/reservas.js`), `listarAmenities` (`api/amenities.js`), `nombreDeUsuario` (Task 5), `.regla-seccion` y `.micro-label` (Task 2).
- Produces: `<Inicio />` como componente default.

- [ ] **Step 1: Reroutear `/` por rol en `App.jsx`**

Reemplazar la línea 97 (`<Route index element={<Navigate to="/comunicados" replace />} />`) por `<Route index element={<InicioRoute />} />`, y agregar junto a los otros wrappers de ruta:

```jsx
function InicioRoute() {
  const { user } = useAuth();
  if (user.rol === "departamento") return <Navigate to="/mi-cuenta" replace />;
  if (user.rol === "representante") return <Navigate to="/comunicados" replace />;
  // super_admin no tiene consorcio activo: Inicio dispararía endpoints
  // admin-only contra 403. Va a su propia pantalla.
  if (user.rol === "super_admin") {
    return <Navigate to="/super-admin/administraciones" replace />;
  }
  return <Inicio />;
}
```

`Inicio` solo se renderiza para `administracion`. Cualquier rol futuro que no matchee cae también en `Inicio`, así que si se agrega uno hay que sumarlo acá.

- [ ] **Step 2: Crear `Inicio.jsx` — carga de datos**

Un solo `useEffect` que dispara todo en paralelo con `Promise.all`. El período vigente es el mes actual en formato `YYYY-MM`. Cada bloque se calcula del resultado; **si un bloque queda vacío, no se renderiza**.

```jsx
const periodo = new Date().toISOString().slice(0, 7);

const [expensas, gastosRep, morosos, peticiones, cierre, finanzas, gastos, habituales, reservas, amenities] =
  await Promise.all([
    listarExpensas({ periodo }),
    obtenerGastosDelPeriodo(periodo),
    listarMorosos({ soloDeudores: true }),
    listarPeticiones(),
    estadoPeriodo(periodo),
    obtenerEstadoFinanciero({ ultimos: 10 }),
    listarGastos({ periodo }),
    listarGastosHabituales(),
    listarReservas(),
    listarAmenities(),
  ]);
```

Cada respuesta se normaliza primero con el helper `datos()` del paso 4, que convierte un 403 o un 404 en el fallback vacío en lugar de romper la pantalla. Todos los cálculos de abajo trabajan sobre esas variables normalizadas, no sobre `respuesta.data` cruda.

Cálculos del hero, a partir de `ExpensaOut` (`monto_primer_vencimiento`, `monto_pendiente`) y del reporte de gastos (`total_general`):

```js
const liquidado = expensasData.reduce((a, e) => a + e.monto_primer_vencimiento, 0);
const pendiente = expensasData.reduce((a, e) => a + e.monto_pendiente, 0);
const cobrado = liquidado - pendiente;
const pctCobrado = liquidado > 0 ? Math.round((cobrado / liquidado) * 100) : 0;
```

"Requiere tu atención" — cada ítem solo entra si su condición se cumple:

```js
const hoy = new Date();
const morososViejos = morososData.filter((m) => {
  if (!m.primer_vencimiento_impago) return false;
  const dias = (hoy - new Date(m.primer_vencimiento_impago)) / 86400000;
  return dias > 60;
});

const peticionesAbiertas = peticionesData.filter((p) => p.estado === "abierta");
```

"Actividad reciente" — merge por fecha descendente, top 6. `ReservaOut` solo trae `amenity_id`, por eso se cruza con `amenities`:

```js
const amenitiesData = datos(amenities, []);
const reservasData = datos(reservas, []);
const nombreAmenity = new Map(amenitiesData.map((a) => [a.id, a.nombre]));

const actividad = [
  ...finanzasData.ultimos_movimientos.map((m) => ({
    fecha: m.fecha, titulo: m.descripcion, detalle: "Movimiento de caja", monto: m.monto,
  })),
  ...peticionesData.map((p) => ({
    fecha: p.fecha_creacion, titulo: p.titulo, detalle: "Petición", monto: null,
  })),
  ...reservasData.map((r) => ({
    fecha: r.inicio, titulo: nombreAmenity.get(r.amenity_id) ?? "Reserva", detalle: "Reserva", monto: null,
  })),
]
  .sort((a, b) => new Date(b.fecha) - new Date(a.fecha))
  .slice(0, 6);
```

"Próximos vencimientos" — fechas de las expensas, más los habituales activos que todavía no se materializaron este período (los materializados son los `Gasto` con `gasto_habitual_id` no nulo):

```js
const gastosData = datos(gastos, []);
const habitualesData = datos(habituales, []);

const yaCargados = new Set(
  gastosData.filter((g) => g.gasto_habitual_id != null).map((g) => g.gasto_habitual_id)
);
const habitualesSinCargar = habitualesData.filter((h) => h.activa && !yaCargados.has(h.id));

const primera = expensasData[0];
const vencimientos = primera
  ? [
      { fecha: primera.fecha_primer_vencimiento, titulo: "1er vto. expensas", detalle: `${expensasData.length} unidades` },
      { fecha: primera.fecha_segundo_vencimiento, titulo: "2do vto. expensas", detalle: "con recargo" },
    ]
  : [];
```

- [ ] **Step 3: Render**

Estructura semántica, usando `.regla-seccion` y `.micro-label` de la Task 2. `atencion` se arma como lista de objetos para no repetir markup por ítem.

```jsx
const money = (n) =>
  n.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });

const atencion = [
  morososViejos.length > 0 && {
    to: "/reportes/morosos",
    tono: "alerta",
    texto: `${morososViejos.length} departamentos con deuda +60 días`,
  },
  peticionesAbiertas.length > 0 && {
    to: "/peticiones",
    tono: "operacion",
    texto: `${peticionesAbiertas.length} peticiones sin responder`,
  },
  cierrePendiente && {
    to: "/cierre-de-periodo",
    tono: "warning",
    texto: `Cierre de período ${periodo} pendiente`,
  },
].filter(Boolean);
```

```jsx
<main className="inicio">
  <p className="inicio-fecha">{fechaLarga} · {nombreConsorcio}</p>
  <h1>Hola, {nombreDeUsuario(user.email)}</h1>

  <section className="inicio-hero">
    <header>
      <p className="micro-label">Recaudación · {periodo}</p>
      <span className="badge badge--ok">{pctCobrado}% cobrado</span>
    </header>
    <p className="inicio-hero-cifra monto">{money(cobrado)}</p>
    <dl className="inicio-hero-grid">
      <div><dt>Liquidado</dt><dd className="monto">{money(liquidado)}</dd></div>
      <div><dt>Pendiente</dt><dd className="monto">{money(pendiente)}</dd></div>
      <div><dt>Gastos</dt><dd className="monto negativo">−{money(totalGastos)}</dd></div>
    </dl>
  </section>

  <div className="inicio-acciones">
    <Link to="/cobranzas">Registrar pago</Link>
    <Link to="/gastos">Cargar gasto</Link>
  </div>

  {atencion.length > 0 && (
    <section className="regla-seccion">
      <p className="micro-label">Requiere tu atención</p>
      <ul className="inicio-lista">
        {atencion.map((a) => (
          <li key={a.to}>
            <Link to={a.to}>
              <span className={`punto punto--${a.tono}`} aria-hidden="true" />
              <span className="inicio-lista-texto">{a.texto}</span>
              <span className="inicio-chevron" aria-hidden="true">›</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )}

  {actividad.length > 0 && (
    <section className="regla-seccion">
      <p className="micro-label">Actividad reciente</p>
      <ul className="inicio-lista">
        {actividad.map((a, i) => (
          <li key={i}>
            <div className="inicio-lista-texto">
              <p>{a.titulo}</p>
              <p className="inicio-lista-detalle">{a.detalle}</p>
            </div>
            {a.monto != null && <span className="monto">{money(a.monto)}</span>}
          </li>
        ))}
      </ul>
    </section>
  )}

  {(vencimientos.length > 0 || habitualesSinCargar.length > 0) && (
    <section className="regla-seccion">
      <p className="micro-label">Próximos vencimientos</p>
      <ul className="inicio-lista">
        {vencimientos.map((v) => (
          <li key={v.titulo}>
            <span className="inicio-fecha-corta">{fechaCorta(v.fecha)}</span>
            <div className="inicio-lista-texto">
              <p>{v.titulo}</p>
              <p className="inicio-lista-detalle">{v.detalle}</p>
            </div>
          </li>
        ))}
      </ul>
      {habitualesSinCargar.length > 0 && (
        <>
          <p className="micro-label">Sin cargar este mes</p>
          <ul className="inicio-lista">
            {habitualesSinCargar.map((h) => (
              <li key={h.id}>
                <div className="inicio-lista-texto"><p>{h.nombre}</p></div>
                <span className="monto negativo">−{money(h.monto)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )}
</main>
```

`fechaCorta(iso)` devuelve `"05 ago"` vía `toLocaleDateString("es-AR", { day: "2-digit", month: "short" })`.

El hero lleva `background: var(--color-mod-inicio)`, `border-radius: var(--radius-lg)`, texto blanco, la cifra en `--font-display` a 2rem con `tabular-nums`, y la `<dl>` en `grid-template-columns: repeat(3, 1fr)` separada por `border-top: 1px solid rgba(255,255,255,0.12)`. Los `.punto` son círculos de 8px que toman su color de `--color-danger`, `--color-mod-operacion` y `--color-warning` según el modificador.

- [ ] **Step 4: Manejar errores y estado de carga**

Cada respuesta se normaliza antes de usarse: si su `status` no es 200, ese bloque se trata como vacío en lugar de romper la pantalla entera. Es un caso real — un admin cuyo consorcio no tiene el módulo `finanzas` habilitado recibe 403 en `/estado-financiero`, y la pantalla igual tiene que renderizar.

```jsx
/** Devuelve r.data si la respuesta fue OK; si no, el fallback. */
const datos = (r, fallback) => (r?.ok && r.data != null ? r.data : fallback);

const expensasData = datos(expensas, []);
const morososData = datos(morosos, []);
const peticionesData = datos(peticiones, []);
const finanzasData = datos(finanzas, { ultimos_movimientos: [] });
const totalGastos = datos(gastosRep, { total_general: 0 }).total_general;
const cierrePendiente = cierre?.ok ? !cierre.data.cerrado : false;
```

`apiFetch` (`api/client.js:34`) devuelve siempre `{ok, status, data}` y **no rechaza ante errores HTTP** — un 403 llega como `{ok: false, status: 403}`. Por eso `Promise.all` es seguro para permisos faltantes. Pero **sí rechaza si `fetch` falla por red**, así que el `Promise.all` va dentro de un `try/catch` que setea un mensaje de error y corta la carga:

```jsx
try {
  const [...] = await Promise.all([...]);
  // … cálculos
} catch {
  setError("No se pudieron cargar los datos. Revisá tu conexión.");
} finally {
  setCargando(false);
}
```

Mientras `cargando` es `true`, renderizar `<main className="inicio"><p>Cargando…</p></main>`. Si hay `error`, renderizarlo con la clase `.error-banner` que ya existe.

- [ ] **Step 5: Verificar**

```bash
cd frontend && npm run build && npm run lint && npm run dev
```
Loguearse como admin y confirmar: `/` muestra Inicio; las cifras del hero coinciden con lo que muestran `/cobranzas` y `/gastos` para el mismo período; cada ítem de "Requiere tu atención" navega a donde corresponde. Loguearse como depto y confirmar que `/` redirige a `/mi-cuenta`; como representante, a `/comunicados`. Revisar a 375px.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/screens/Inicio.jsx frontend/src/App.jsx frontend/src/index.css
git commit -m "feat(inicio): dashboard de admin con datos de endpoints existentes"
```

---

### Task 8: Pasada final de verificación

**Files:** los que haga falta corregir.

- [ ] **Step 1: Build y lint limpios**

```bash
cd frontend && npm run build && npm run lint
```

- [ ] **Step 2: Recorrido a 375px**

Con DevTools en iPhone SE, recorrer como admin: Inicio, Cobranzas, Gastos, Tesorería, Peticiones, Liquidaciones (tabla ancha), Padrón (tabla ancha). Como depto: Mi cuenta, Peticiones, Reservas, Comunicados. Buscar en cada una: overflow horizontal, botones que desbordan, contenido tapado por la tab bar, targets menores a 44px.

- [ ] **Step 3: Contraste**

Revisar con el inspector los badges (`.badge--neutro` sobre fondo crema es el candidato más probable a fallar), las celdas de tabla y el texto muted sobre `--color-bg`. Objetivo: 4.5:1 para texto normal. Corregir el token, no el componente.

- [ ] **Step 4: No-regresión de los modales**

Abrir un modal de cada tipo (detalle de petición, nuevo presupuesto, ajuste de caja, comprobantes de expensa) y confirmar que Escape cierra, el click en backdrop cierra, y los formularios largos scrollean dentro de la sheet sin que la página de atrás se mueva.

- [ ] **Step 5: Desktop**

A 1200px: sidebar visible, sin tab bar, modales centrados, botones ghost a contenido, y **contenido reorganizado en vez de estirado** — ningún bloque que en mobile ocupaba todo el ancho debe quedar estirado a 960px en desktop.

- [ ] **Step 6: Commit de correcciones**

```bash
git add -A frontend/
git commit -m "fix(ui): correcciones de la pasada de verificacion"
```

---

## Nota sobre testing

Este plan no incluye tests automatizados porque el proyecto no tiene framework de tests de frontend y el spec aprobado definió la verificación como build + lint + browser. Vale registrar que `navegacion.js` (Task 4) es la única pieza con lógica pura y ramificada — `filtrarSecciones` y `moduloDeRuta` — y sería la candidata natural si más adelante se decide sumar Vitest. Es una decisión aparte de este rebranding.

## Riesgos

- **El cambio de tokens toca las 41 pantallas de una.** Cubierto por la Task 8, pasos 2 y 3.
- **La Task 4 refactoriza `Sidebar.jsx`, que hoy funciona.** El paso 6 de esa tarea es explícitamente de no-regresión: preservar el filtrado por `modulos_habilitados`, el flag `usa_personal_propio` y el orden de `ORDEN_DEPTO`.
- **El header pierde el `SelectorConsorcio` visible en mobile.** Pasa a la sheet de cuenta. Si el usuario lo usa seguido, puede ser un roce a revisar después.
- **La regla global de `button` cambia el ancho a `100%` en mobile.** Puede afectar botones dentro de tablas o filas que hoy quedan inline. Es el primer lugar a mirar si algo se ve raro en la Task 2.
