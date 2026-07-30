# Limpieza de theming + label del sheet depto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remapear el theming por módulo a una historia coherente sobre los 6 colores existentes, quitar el campo `modulo` muerto de `TABS_POR_ROL`, y rotular el cluster del sheet "Más" del depto como "Reportes" en vez de "Finanzas".

**Architecture:** Dos cambios independientes en dos archivos: (1) reescribir `MODULO_POR_RUTA` y limpiar `TABS_POR_ROL` en `navegacion.js`; (2) computar `seccionesMas` desde `aplanarParaDepto` para el rol departamento en `useNavegacionVisible.js`. Sin cambios de CSS ni de otros componentes.

**Tech Stack:** React 19 + react-router-dom 6 + Vite 8. Sin runner de tests JS: verificación por `npm run build` + `npx eslint` + revisión manual en browser.

## Global Constraints

- **Paleta intacta:** no agregar ni cambiar colores en `index.css`. Solo se reasignan rutas a las 6 claves existentes: `inicio`, `cobranzas`, `gastos`, `finanzas`, `expensas`, `operacion`.
- **Configuración queda navy sin mapear:** las rutas de Configuración (`/configuracion`, `/clases-prorrateo`, `/proveedores`, `/padron`, `/administracion/consorcios`) NO se agregan a `MODULO_POR_RUTA`; el default de `moduloDeRuta` ya devuelve `inicio` (navy).
- **`moduloDeRuta` no cambia su lógica** (`if pathname === "/" return "inicio"` + búsqueda por prefijo + default `inicio`).
- **`useNavegacionVisible` mantiene su forma de retorno** `{ secciones, seccionesMas, tabsVisibles, cargando }` — `AppLayout.jsx` no se toca.
- Los demás roles (no departamento) siguen usando `aplanarCategoria` para `seccionesMas` sin cambios.
- No JS test runner: verificación = `npm run build` pasa + `npx eslint` sin errores nuevos (2 `set-state-in-effect` pre-existentes son aceptables).
- Rama `limpieza-theming` (ya creada). Comandos desde `frontend/`.

---

### Task 1: Remapear `MODULO_POR_RUTA` + quitar `modulo` muerto de `TABS_POR_ROL`

**Files:**
- Modify: `frontend/src/navegacion.js` (constante `MODULO_POR_RUTA` ~líneas 178-198; `TABS_POR_ROL` ~líneas 208-227)

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `MODULO_POR_RUTA` reescrito; `moduloDeRuta(pathname)` sin cambios de firma (sigue devolviendo una de las 6 claves o `"inicio"`); `TABS_POR_ROL` sin el campo `modulo` (entradas quedan `{ ruta, nombre, icono }`).

- [ ] **Step 1: Confirmar que el campo `modulo` de las tabs está muerto**

Run (desde `frontend/`): `grep -rn "\.modulo\b" src --include=*.jsx --include=*.js | grep -v "modulosHabilitados\|moduloDeRuta\|modulos_habilitados\|\.modulos\b"`
Expected: ningún resultado que lea `.modulo` (singular) de una tab. (Ya verificado: solo se usa `s.modulos` plural en el sheet.) Si aparece algún consumidor real de `t.modulo`, NO quitar el campo — en su lugar alinear sus valores con el mapeo de abajo y reportarlo como concern.

- [ ] **Step 2: Reescribir `MODULO_POR_RUTA`**

Reemplazar la constante completa (líneas 178-198) por:

```js
// Prefijo de ruta → clave de data-modulo (una de las 6 de index.css). Se evalúa
// en orden; el primero que matchea gana. Configuración queda fuera a propósito:
// cae al default "inicio" (navy), su zona de setup neutral.
const MODULO_POR_RUTA = [
  ["/cobranzas", "cobranzas"],
  ["/cuentas-corrientes", "cobranzas"],
  ["/comprobantes", "cobranzas"],
  ["/gastos", "gastos"],
  ["/liquidaciones", "gastos"],
  ["/haberes", "gastos"],
  ["/empleados", "gastos"],
  ["/conceptos-liquidacion", "gastos"],
  ["/tesoreria", "finanzas"],
  ["/estado-financiero", "finanzas"],
  ["/cajas", "finanzas"],
  ["/transferencias", "finanzas"],
  ["/reportes", "finanzas"],
  ["/expensas", "expensas"],
  ["/mi-cuenta", "expensas"],
  ["/departamentos", "expensas"],
  ["/cierre-de-periodo", "expensas"],
  ["/periodos", "expensas"],
  ["/peticiones", "operacion"],
  ["/trabajos", "operacion"],
  ["/trabajos-recurrentes", "operacion"],
  ["/amenities", "operacion"],
  ["/reservas", "operacion"],
  ["/comunicados", "operacion"],
];
```

No tocar `moduloDeRuta` (la función que sigue debajo).

- [ ] **Step 3: Quitar el campo `modulo` de `TABS_POR_ROL`**

En cada una de las 12 entradas de `TABS_POR_ROL` (los 3 roles), eliminar el par `modulo: "..."`, dejando `{ ruta, nombre, icono }`. Resultado:

```js
export const TABS_POR_ROL = {
  administracion: [
    { ruta: "/", nombre: "Inicio", icono: "casa" },
    { ruta: "/cobranzas", nombre: "Cobranzas", icono: "moneda" },
    { ruta: "/gastos", nombre: "Gastos", icono: "documento" },
    { ruta: "/tesoreria", nombre: "Finanzas", icono: "billetera" },
    { ruta: "/peticiones", nombre: "Operación", icono: "llave" },
  ],
  departamento: [
    { ruta: "/mi-cuenta", nombre: "Mi cuenta", icono: "casa" },
    { ruta: "/peticiones", nombre: "Peticiones", icono: "chat" },
    { ruta: "/reservas", nombre: "Reservas", icono: "calendario" },
    { ruta: "/comunicados", nombre: "Comunicados", icono: "campana" },
  ],
  representante: [
    { ruta: "/comunicados", nombre: "Comunicados", icono: "campana" },
    { ruta: "/peticiones", nombre: "Peticiones", icono: "chat" },
    { ruta: "/trabajos", nombre: "Trabajos", icono: "llave" },
  ],
};
```

- [ ] **Step 4: Verificar build y lint**

Run (desde `frontend/`): `npm run build && npx eslint src/navegacion.js`
Expected: build OK; eslint de `navegacion.js` sin errores (este archivo no tiene los `set-state-in-effect`).

- [ ] **Step 5: Verificación puntual de mapeo (node ESM)**

Run un chequeo rápido importando `moduloDeRuta` y confirmando: `/comunicados`→`operacion`, `/liquidaciones`→`gastos`, `/haberes`→`gastos`, `/reportes/morosos`→`finanzas`, `/reservas`→`operacion`, `/amenities`→`operacion`, `/trabajos-recurrentes`→`operacion`, `/gastos/habituales`→`gastos`, `/departamentos/5/cuenta`→`expensas`, `/configuracion`→`inicio`, `/padron`→`inicio`, `/`→`inicio`.
Expected: todos coinciden. (Si no podés correr node, dejar constancia y verificar en browser en Task 3.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/navegacion.js
git commit -m "fix(nav): remapear theming por modulo (6 colores coherentes) + quitar modulo muerto de TABS_POR_ROL"
```

---

### Task 2: `seccionesMas` del depto desde `aplanarParaDepto`

**Files:**
- Modify: `frontend/src/hooks/useNavegacionVisible.js` (cálculo de `seccionesMas`, ~líneas 43-72)

**Interfaces:**
- Consumes: `aplanarParaDepto(secciones)` de `navegacion.js` → `{ items, subgrupos }` donde `subgrupos` es `[{ id, titulo, hijos: [{ruta, nombre, ...}] }]` con `titulo` real (p.ej. "Reportes"); `rutasEnTabs` (Set ya calculado en el hook).
- Produces: `seccionesMas` con la MISMA forma `[{ titulo, modulos: [{ruta, nombre}] }]`; para departamento el cluster se rotula "Reportes".

- [ ] **Step 1: Importar `aplanarParaDepto`**

En el import de `../navegacion` (línea 5), agregar `aplanarParaDepto` a lo que ya se importa (`filtrarArbol, TABS_POR_ROL`).

- [ ] **Step 2: Bifurcar el cálculo de `seccionesMas` por rol**

Localizar el bloque actual que arma `seccionesMas` (usa `aplanarCategoria`, ~líneas 43-68) y el `const seccionesMas = secciones.map(aplanarCategoria).filter(...)` (~líneas 70-72). Dejar `aplanarCategoria` y `rutasEnTabs` como están; cambiar SOLO la asignación final de `seccionesMas` para bifurcar por rol:

```js
const noEnTabs = (m) => !rutasEnTabs.has(m.ruta);

let seccionesMas;
if (rol === "departamento") {
  // El depto navega en lista plana; el sheet "Más" debe rotular el cluster con su
  // nombre real ("Reportes"), no con el título de la categoría de admin ("Finanzas").
  // Los items planos del depto (mi-cuenta, peticiones, reservas, comunicados) están
  // siempre en la tab bar, así que solo los sub-grupos generan sección en "Más".
  const { subgrupos } = aplanarParaDepto(secciones);
  seccionesMas = subgrupos
    .map((sg) => ({
      titulo: sg.titulo,
      modulos: sg.hijos.filter(noEnTabs).map((m) => ({ ruta: m.ruta, nombre: m.nombre })),
    }))
    .filter((s) => s.modulos.length > 0);
} else {
  seccionesMas = secciones.map(aplanarCategoria).filter((s) => s.modulos.length > 0);
}
```

Nota: si el bloque existente usa una firma distinta de `aplanarCategoria`/`rutasEnTabs`, adaptarse a lo que ya hay — el único cambio de comportamiento requerido es que para `rol === "departamento"` el `seccionesMas` salga de `aplanarParaDepto` con los títulos de sub-grupo.

- [ ] **Step 3: Verificar build y lint**

Run (desde `frontend/`): `npm run build && npx eslint src/hooks/useNavegacionVisible.js`
Expected: build OK; eslint sin errores NUEVOS (el `set-state-in-effect` de la línea 16 es pre-existente y aceptable).

- [ ] **Step 4: Verificación de comportamiento (node ESM o razonada)**

Confirmar (importando el módulo o razonando contra el árbol): para `rol: "departamento"` con `reportesVisiblesDepto: true`, `seccionesMas` = `[{ titulo: "Reportes", modulos: [4 reportes] }]` (ninguno de los 4 reportes está en la tab bar del depto). Con `reportesVisiblesDepto: false`, `seccionesMas` = `[]`. Para admin/representante, `seccionesMas` sin cambios respecto de antes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useNavegacionVisible.js
git commit -m "fix(nav): sheet Mas del depto rotula el cluster como Reportes"
```

---

### Task 3: Verificación integral en browser

**Files:** ninguno (verificación manual).

- [ ] **Step 1: `npm run build`** sin errores; `npx eslint src/navegacion.js src/hooks/useNavegacionVisible.js` sin errores nuevos.

- [ ] **Step 2: Checks en browser (`npm run dev`)**

  **Admin — el acento del header (`--color-modulo`) cambia acorde a la ruta:**
  - [ ] `/comunicados` → violeta; `/liquidaciones`, `/haberes`, `/empleados`, `/conceptos-liquidacion` → rojo.
  - [ ] `/reportes/morosos` → oro; `/tesoreria` → oro.
  - [ ] `/reservas`, `/amenities`, `/trabajos-recurrentes` → violeta.
  - [ ] `/cobranzas`, `/cuentas-corrientes` → verde; `/gastos` y `/gastos/habituales` → rojo.
  - [ ] `/configuracion`, `/clases-prorrateo`, `/proveedores`, `/padron` → navy (como Inicio).

  **Depto:**
  - [ ] Abrir el sheet "Más" → el cluster de reportes se rotula **"Reportes"** (no "Finanzas").
  - [ ] Con reportes deshabilitados, el sheet no muestra esa sección.

- [ ] **Step 3: Commit final (si algún check reveló un fix)**

```bash
git add -A
git commit -m "fix(nav): ajustes de verificacion de theming"
```

---

## Notas de decisión (del spec)

- Paleta de 6 colores intacta; Configuración → navy vía default (sin mapear).
- Personal → rojo (gastos), Comunicados → violeta (operacion), Configuración → navy: confirmado con el usuario.
- Campo `modulo` de `TABS_POR_ROL` confirmado muerto → se elimina.
