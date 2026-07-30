# Reestructura de la navegación (sidebar) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la navegación de 8 secciones planas por un árbol de 4 macro-categorías + Inicio, arreglando Inicio ausente, resaltado de acordeón, secciones de 1 item y el filtro de Personal por string.

**Architecture:** `navegacion.js` pasa de `SECCIONES` (2 niveles) a `CATEGORIAS` (árbol de 3 niveles fijos: categoría → sub-grupo → item). Un `filtrarArbol()` de profundidad fija aplica permisos y dos reglas de colapso. `Sidebar.jsx` distingue nodos por forma (item suelto / categoría-acordeón / sub-grupo-label). El rol departamento conserva su rama plana. Super_admin y la TabBar no se tocan.

**Tech Stack:** React 19 + react-router-dom 6 + Vite 8. Sin runner de tests JS: la verificación es `npm run build`, `npm run lint` y checks manuales en browser.

## Global Constraints

- **Sin hex/rgb hardcodeado en componentes.** Colores siempre vía `var(--color-*)` (regla `frontend.md`).
- **Mobile-first.** Mejoras con `@media (min-width: ...)`, nunca `max-width`. Breakpoints: 600px (tablet), 960px (desktop). Sidebar visible solo ≥960px.
- **Targets táctiles ≥44px** de alto. Unidades relativas (`rem`/`em`/`%`); `px` solo para bordes/sombras.
- **Sin overflow horizontal**; usable a 375px.
- **HTML semántico**, sin sopa de divs. Labels no interactivos NO son `<button>`.
- **El árbol tiene exactamente 3 niveles.** No introducir recursión genérica ni un 4º nivel.
- **`useNavegacionVisible` debe devolver la misma forma** `{ secciones, seccionesMas, tabsVisibles, cargando }` — `AppLayout.jsx` no se toca.
- **Fuera de alcance:** TabBar, `moduloDeRuta`/`MODULO_POR_RUTA` (theming), `SidebarSuperAdmin.jsx`, hub Mi cuenta.
- Trabajo en la rama `reestructura-navegacion` (ya creada).
- Comandos desde `frontend/`: `npm run build`, `npm run lint`, `npm run dev`.

---

### Task 1: Modelo de datos `CATEGORIAS` + helpers en `navegacion.js`

**Files:**
- Modify: `frontend/src/navegacion.js` (reemplaza `SECCIONES`, `grupoDeRuta`, `filtrarSecciones`; conserva `ORDEN_DEPTO`, `moduloDeRuta`, `MODULO_POR_RUTA`, `TABS_POR_ROL`)

**Interfaces:**
- Consumes: nada (primer task).
- Produces:
  - `export const CATEGORIAS` — array de nodos. Nodo item: `{ ruta, nombre, modulo?, rolesPermitidos, rutasRelacionadas?, suelto? }`. Nodo grupo: `{ id, titulo, hijos: Nodo[] }`.
  - `export function filtrarArbol({ rol, modulosHabilitados, usaPersonalPropio, reportesVisiblesDepto }): Nodo[]` — árbol filtrado y colapsado.
  - `export function categoriaDeRuta(pathname): string | null` — devuelve el `titulo` de la categoría de nivel 1 que contiene la ruta (o null).
  - `export function aplanarParaDepto(arbol): Nodo[]` — items ordenados por `ORDEN_DEPTO` seguidos de sub-grupos con >1 item.
  - Se conservan sin cambios: `ORDEN_DEPTO`, `moduloDeRuta`, `MODULO_POR_RUTA`, `TABS_POR_ROL`.

- [ ] **Step 1: Escribir `CATEGORIAS`**

Reemplazar la constante `SECCIONES` (líneas 3-183) por `CATEGORIAS`. Copiar el árbol completo desde la sección "Modelo de datos" del spec (`docs/superpowers/specs/2026-07-30-reestructura-navegacion-design.md`). Verbatim, incluyendo `suelto`, `id`, `rutasRelacionadas`, `modulo` y `rolesPermitidos` de cada nodo.

- [ ] **Step 2: Escribir `filtrarArbol`**

Reemplazar `filtrarSecciones` (líneas 198-227). Profundidad fija, sin recursión genérica:

```js
export function filtrarArbol({
  rol,
  modulosHabilitados,
  usaPersonalPropio,
  reportesVisiblesDepto,
}) {
  const hojaVisible = (hoja) => {
    if (!hoja.rolesPermitidos.includes(rol)) return false;
    if (
      rol === "departamento" &&
      hoja.ruta.startsWith("/reportes/") &&
      !reportesVisiblesDepto
    ) {
      return false;
    }
    if (
      hoja.modulo &&
      modulosHabilitados !== null &&
      !modulosHabilitados.includes(hoja.modulo)
    ) {
      return false;
    }
    return true;
  };

  const resultado = [];
  for (const nodo of CATEGORIAS) {
    // Nivel 1 item suelto (Inicio)
    if (nodo.ruta) {
      if (hojaVisible(nodo)) resultado.push(nodo);
      continue;
    }
    // Personal por id (feature flag)
    if (nodo.id === "personal" && !usaPersonalPropio) continue;

    // Filtrar hijos (items y sub-grupos)
    const hijos = [];
    for (const hijo of nodo.hijos) {
      if (hijo.ruta) {
        if (hojaVisible(hijo)) hijos.push(hijo);
      } else {
        // sub-grupo: filtrar sus items
        const items = hijo.hijos.filter(hojaVisible);
        if (items.length === 0) continue;
        // Regla 1: sub-grupo de 1 → item suelto
        if (items.length === 1) hijos.push(items[0]);
        else hijos.push({ ...hijo, hijos: items });
      }
    }
    if (hijos.length === 0) continue;

    // Regla 2: categoría con un único sub-grupo y ningún item directo → promover
    const soloSubgrupos = hijos.every((h) => !h.ruta);
    if (hijos.length === 1 && soloSubgrupos) {
      resultado.push(hijos[0]); // el sub-grupo pasa a ser categoría nivel 1
    } else {
      resultado.push({ ...nodo, hijos });
    }
  }
  return resultado;
}
```

- [ ] **Step 3: Escribir `categoriaDeRuta`**

Reemplazar `grupoDeRuta` (líneas 185-196):

```js
export function categoriaDeRuta(pathname) {
  const matchea = (hoja) => {
    const rutas = [hoja.ruta, ...(hoja.rutasRelacionadas ?? [])];
    return rutas.some(
      (r) => pathname === r || pathname.startsWith(r + "/")
    );
  };
  for (const nodo of CATEGORIAS) {
    if (nodo.ruta) {
      if (matchea(nodo)) return nodo.titulo ?? nodo.nombre;
      continue;
    }
    for (const hijo of nodo.hijos) {
      if (hijo.ruta) {
        if (matchea(hijo)) return nodo.titulo;
      } else if (hijo.hijos.some(matchea)) {
        return nodo.titulo;
      }
    }
  }
  return null;
}
```

- [ ] **Step 4: Escribir `aplanarParaDepto`**

Agregar tras `categoriaDeRuta`. Recibe el árbol YA filtrado por `filtrarArbol` (rol departamento). Junta todos los items sueltos ordenados por `ORDEN_DEPTO`, y luego los sub-grupos que sobrevivieron con más de un item:

```js
export function aplanarParaDepto(arbol) {
  const items = [];
  const subgrupos = [];
  const recorrer = (nodos) => {
    for (const n of nodos) {
      if (n.ruta) items.push(n);
      else if (n.hijos) {
        const soloItems = n.hijos.filter((h) => h.ruta);
        if (soloItems.length > 1) subgrupos.push({ ...n, hijos: soloItems });
        else recorrer(n.hijos);
      }
    }
  };
  recorrer(arbol);
  items.sort((a, b) => {
    const ia = ORDEN_DEPTO.indexOf(a.ruta);
    const ib = ORDEN_DEPTO.indexOf(b.ruta);
    const na = ia === -1 ? ORDEN_DEPTO.length : ia;
    const nb = ib === -1 ? ORDEN_DEPTO.length : ib;
    return na - nb;
  });
  return { items, subgrupos };
}
```

Nota: devuelve `{ items, subgrupos }` (no un array plano) para que `Sidebar.jsx` pueda rotular el cluster Reportes. Ajustar el bloque Interfaces mentalmente: el productor real es `{ items: Nodo[], subgrupos: Nodo[] }`.

- [ ] **Step 5: Verificar build y lint**

Run (desde `frontend/`): `npm run build && npm run lint`
Expected: build OK; lint sin errores. (Habrá imports rotos en `Sidebar.jsx`/`useNavegacionVisible.js` que aún referencian `SECCIONES`/`grupoDeRuta`/`filtrarSecciones` — se arreglan en Tasks 2-3. Si el build falla SOLO por esos imports, es esperado; continuar. Si falla por sintaxis dentro de `navegacion.js`, corregir antes de seguir.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/navegacion.js
git commit -m "feat(nav): arbol CATEGORIAS + filtrarArbol/categoriaDeRuta/aplanarParaDepto"
```

---

### Task 2: Adaptar `useNavegacionVisible.js` al árbol

**Files:**
- Modify: `frontend/src/hooks/useNavegacionVisible.js`

**Interfaces:**
- Consumes: `filtrarArbol`, `TABS_POR_ROL` de `navegacion.js`.
- Produces: hook `useNavegacionVisible(rol)` que devuelve `{ secciones, seccionesMas, tabsVisibles, cargando }` — **misma forma que hoy**. `secciones` ahora es el árbol filtrado (`filtrarArbol(...)`). `seccionesMas` es el árbol sin las rutas ya presentes en la TabBar, aplanado a un nivel para el sheet.

- [ ] **Step 1: Reemplazar la llamada de filtrado**

Cambiar `import { filtrarSecciones, TABS_POR_ROL }` por `import { filtrarArbol, TABS_POR_ROL }`. Reemplazar la llamada:

```js
const secciones = filtrarArbol({
  rol,
  modulosHabilitados,
  usaPersonalPropio,
  reportesVisiblesDepto,
});
```

- [ ] **Step 2: Recalcular `seccionesMas` sobre el árbol**

`seccionesMas` alimenta el sheet "Más" mobile, que quiere una lista de categorías con items (un solo nivel de anidamiento). Aplanar sub-grupos y sacar rutas que ya están en la TabBar:

```js
const rutasEnTabs = new Set((TABS_POR_ROL[rol] ?? []).map((t) => t.ruta));

// Aplana una categoria del arbol a { titulo, modulos: [{ruta, nombre}] }
// disolviendo sub-grupos y quitando rutas presentes en la tabbar.
function aplanarCategoria(nodo) {
  const titulo = nodo.titulo ?? nodo.nombre;
  const modulos = [];
  const juntar = (hijos) => {
    for (const h of hijos) {
      if (h.ruta) {
        if (!rutasEnTabs.has(h.ruta)) modulos.push({ ruta: h.ruta, nombre: h.nombre });
      } else if (h.hijos) {
        juntar(h.hijos);
      }
    }
  };
  if (nodo.ruta) {
    // item suelto (Inicio): se ignora en "Más" si esta en tabs
    if (!rutasEnTabs.has(nodo.ruta)) modulos.push({ ruta: nodo.ruta, nombre: nodo.nombre });
  } else {
    juntar(nodo.hijos);
  }
  return { titulo, modulos };
}

const seccionesMas = secciones
  .map(aplanarCategoria)
  .filter((s) => s.modulos.length > 0);
```

- [ ] **Step 3: Recalcular `rutasVisibles` y `tabsVisibles`**

`rutasVisibles` debe juntar TODAS las rutas de hojas del árbol (a cualquier profundidad):

```js
const rutasVisibles = new Set();
const juntarRutas = (nodos) => {
  for (const n of nodos) {
    if (n.ruta) rutasVisibles.add(n.ruta);
    else if (n.hijos) juntarRutas(n.hijos);
  }
};
juntarRutas(secciones);

const tabsVisibles = (TABS_POR_ROL[rol] ?? []).filter(
  (t) => t.ruta === "/" || rutasVisibles.has(t.ruta)
);
```

- [ ] **Step 4: Verificar build y lint**

Run (desde `frontend/`): `npm run build && npm run lint`
Expected: build puede seguir fallando por `Sidebar.jsx` (Task 3). El hook en sí no debe tener errores de sintaxis/lint. Si el único error de build es `grupoDeRuta`/`ORDEN_DEPTO` importado en `Sidebar.jsx`, continuar.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useNavegacionVisible.js
git commit -m "feat(nav): useNavegacionVisible sobre el arbol de categorias"
```

---

### Task 3: Render de `Sidebar.jsx` (item suelto / categoría / sub-grupo)

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`

**Interfaces:**
- Consumes: `categoriaDeRuta`, `aplanarParaDepto` de `navegacion.js`; prop `secciones` (árbol filtrado) de `AppLayout`.
- Produces: sidebar de desktop renderizado. Sin exports nuevos.

- [ ] **Step 1: Actualizar imports y estado del acordeón**

Cambiar `import { grupoDeRuta, ORDEN_DEPTO }` por `import { categoriaDeRuta, aplanarParaDepto }`. Reemplazar los usos de `grupoDeRuta(...)` por `categoriaDeRuta(...)` en el `useState` inicial y en el `useEffect` (líneas 7-14).

- [ ] **Step 2: Rama departamento con cluster Reportes**

Reemplazar el bloque `rol === "departamento"` (líneas 35-59). Usar `aplanarParaDepto` sobre `seccionesVisibles`:

```jsx
{rol === "departamento" ? (
  (() => {
    const { items, subgrupos } = aplanarParaDepto(seccionesVisibles);
    return (
      <ul>
        {items.map((m) => (
          <li key={m.ruta}>
            <NavLink to={m.ruta} onClick={onCerrar}
              className={({ isActive }) => isActive ? "sidebar-link activo" : "sidebar-link"}>
              {m.nombre}
            </NavLink>
          </li>
        ))}
        {subgrupos.map((sg) => (
          <li key={sg.id}>
            <p className="sidebar-subgrupo">{sg.titulo}</p>
            <ul>
              {sg.hijos.map((m) => (
                <li key={m.ruta}>
                  <NavLink to={m.ruta} onClick={onCerrar}
                    className={({ isActive }) => isActive ? "sidebar-link en-subgrupo activo" : "sidebar-link en-subgrupo"}>
                    {m.nombre}
                  </NavLink>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    );
  })()
) : (
```

- [ ] **Step 3: Rama no-departamento (item suelto / categoría / sub-grupo)**

Reemplazar el bloque `seccionesVisibles.map((s) => {...})` (líneas 61-116) por un map que distingue por forma del nodo:

```jsx
  seccionesVisibles.map((nodo) => {
    // 1. Item suelto (Inicio)
    if (nodo.ruta) {
      return (
        <ul key={nodo.ruta} className="sidebar-section">
          <li>
            <NavLink to={nodo.ruta} end={nodo.ruta === "/"} onClick={onCerrar}
              className={({ isActive }) => isActive ? "sidebar-link activo" : "sidebar-link"}>
              {nodo.nombre}
            </NavLink>
          </li>
        </ul>
      );
    }
    // 2. Categoria acordeon
    const expandido = grupoAbierto === nodo.titulo;
    const categoriaActiva = categoriaDeRuta(location.pathname) === nodo.titulo;
    return (
      <div key={nodo.id} className="sidebar-section">
        <button type="button"
          className={categoriaActiva ? "sidebar-section-titulo activo" : "sidebar-section-titulo"}
          aria-expanded={expandido}
          onClick={() => toggleGrupo(nodo.titulo)}>
          <span>{nodo.titulo}</span>
          <span className="sidebar-chevron" aria-hidden="true">▸</span>
        </button>
        {expandido && (
          <ul>
            {nodo.hijos.map((hijo) =>
              hijo.ruta ? (
                // 3a. Item directo
                <li key={hijo.ruta}>
                  <NavLink to={hijo.ruta} onClick={onCerrar}
                    className={({ isActive }) => isActive ? "sidebar-link activo" : "sidebar-link"}>
                    {hijo.nombre}
                  </NavLink>
                </li>
              ) : (
                // 3b. Sub-grupo: label no-clickable + items
                <li key={hijo.id}>
                  <p className="sidebar-subgrupo">{hijo.titulo}</p>
                  <ul>
                    {hijo.hijos.map((m) => (
                      <li key={m.ruta}>
                        <NavLink to={m.ruta} onClick={onCerrar}
                          className={({ isActive }) => isActive ? "sidebar-link en-subgrupo activo" : "sidebar-link en-subgrupo"}>
                          {m.nombre}
                        </NavLink>
                      </li>
                    ))}
                  </ul>
                </li>
              )
            )}
          </ul>
        )}
      </div>
    );
  })
```

Nota: `toggleGrupo` recibe `nodo.titulo` (no cambia su firma). El item suelto Inicio no togglea.

- [ ] **Step 4: Verificar build y lint**

Run (desde `frontend/`): `npm run build && npm run lint`
Expected: build OK (ya no hay imports rotos), lint sin errores.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "feat(nav): render de sidebar con item suelto, categorias y sub-grupos"
```

---

### Task 4: Adaptar el sheet "Más" en `TabBar.jsx`

**Files:**
- Modify: `frontend/src/components/TabBar.jsx:64-83` (bloque del `Modal` "Más")

**Interfaces:**
- Consumes: prop `seccionesMas` — ahora `[{ titulo, modulos: [{ruta, nombre}] }]` (forma que produce `useNavegacionVisible` Task 2).
- Produces: sheet "Más" renderizado. Sin cambios en la TabBar principal ni en `ICONOS`.

- [ ] **Step 1: Ajustar el map del sheet**

El sheet ya itera `seccionesMas.map((s) => ...)` usando `s.titulo` y `s.modulos`. La forma nueva de `seccionesMas` (Task 2) mantiene exactamente `{ titulo, modulos: [{ruta, nombre}] }`, así que el JSX de las líneas 67-80 **no requiere cambios estructurales**. Verificar que `s.titulo` y `m.nombre`/`m.ruta` siguen siendo los campos correctos. Si es así, este task es solo verificación.

- [ ] **Step 2: Verificar build, lint y comportamiento**

Run (desde `frontend/`): `npm run build && npm run lint`
Expected: OK.

- [ ] **Step 3: Commit (si hubo cambios)**

```bash
git add frontend/src/components/TabBar.jsx
git commit -m "chore(nav): sheet Mas compatible con seccionesMas aplanado"
```

Si el Step 1 no cambió nada, saltear el commit (dejar constancia en el review).

---

### Task 5: CSS del sub-grupo en `index.css`

**Files:**
- Modify: `frontend/src/index.css` (agregar tras `.sidebar-link.activo`, línea ~776; y verificar bloque `@media (min-width: 960px)` ~1918+)

**Interfaces:**
- Consumes: variables `--color-text-muted`, `--color-border` (ya definidas en `:root`).
- Produces: clases `.sidebar-subgrupo` y `.sidebar-link.en-subgrupo`.

- [ ] **Step 1: Agregar `.sidebar-subgrupo` y `.en-subgrupo`**

Insertar tras la regla `.sidebar-link.activo` (línea 776):

```css
.sidebar-subgrupo {
  margin: 0.5rem 0.5rem 0.15rem;
  padding: 0 0.75em;
  font-size: 0.5625rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.sidebar-subgrupo::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--color-border);
}

.sidebar-link.en-subgrupo {
  padding-left: 1.5em;
}
```

- [ ] **Step 2: Verificar que el `<p>` no herede estilos de párrafo indebidos**

Buscar en `index.css` reglas globales de `p` (`grep -n "^p\b\|^p," frontend/src/index.css`). Si un `p` global aplica `margin`/`line-height` que rompa el label, la regla `.sidebar-subgrupo` ya fija `margin`; confirmar visualmente en Step 4.

- [ ] **Step 3: Verificar build**

Run (desde `frontend/`): `npm run build`
Expected: OK (CSS no rompe build; es import estático).

- [ ] **Step 4: Verificación visual en dev**

Run (desde `frontend/`): `npm run dev`, abrir con un usuario administración, expandir Gestión. Confirmar: "── MANTENIMIENTO ──" y "── ESPACIOS ──" se ven como rótulos con línea al costado, más chicos que el título de categoría; los items debajo indentados; sin overflow horizontal a 375px.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "style(nav): estilos de sub-grupo en el sidebar"
```

---

### Task 6: Verificación integral por rol

**Files:** ninguno (solo verificación manual).

- [ ] **Step 1: `npm run build && npm run lint`** sin errores ni warnings nuevos.

- [ ] **Step 2: Checks en browser (`npm run dev`)** — por cada rol:

  **Administración (desktop ≥960px):**
  - [ ] Inicio aparece arriba de todo y navega a `/`.
  - [ ] 4 categorías: Finanzas, Gestión, Personal, Configuración; una abierta a la vez.
  - [ ] Entrar a `/comprobantes`, `/expensas`, `/cierre-de-periodo`, `/departamentos/1/cuenta` → resalta **Finanzas**.
  - [ ] Gestión abierta: "Comunicados" es un item (no rótulo "Comunicación"); "── MANTENIMIENTO ──" y "── ESPACIOS ──" son rótulos.
  - [ ] Con `usa_personal_propio = false` en el consorcio, Personal desaparece.

  **Representante:**
  - [ ] Ve Inicio, Gestión y **REPORTES en nivel 1** (no dentro de Finanzas).
  - [ ] Gestión muestra Comunicados (item) + Mantenimiento.

  **Departamento:**
  - [ ] Lista plana: Mi cuenta, Comunicados, Peticiones, Reservas.
  - [ ] Con reportes habilitados: cluster "REPORTES" con los 4 reportes debajo; sin ellos, no aparece el cluster.

  **Super_admin:**
  - [ ] Sidebar sin cambios (3 items).

  **Mobile (375px, todos los roles con TabBar):**
  - [ ] TabBar intacta; botón "Más" abre el sheet con las categorías y sus items; sin overflow horizontal.

- [ ] **Step 3: Commit final (si algún check reveló un fix)**

```bash
git add -A
git commit -m "fix(nav): ajustes de verificacion por rol"
```

---

## Notas de decisión (del spec)

- **Orden de Personal:** Empleados → Haberes → Liquidaciones → Conceptos (propuesta), distinto del `SECCIONES` actual. Confirmado con el usuario al revisar el spec.
- **`rutasRelacionadas` de Cobranzas** incluye `/departamentos` para que `/departamentos/:id/cuenta` resalte Finanzas.
- **Tres vocabularios de "módulo"** (gating / resaltado nav / theming) son concerns distintos; este plan solo toca gating y resaltado.
