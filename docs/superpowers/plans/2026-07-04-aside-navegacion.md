# Rediseño del aside — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el sidebar plano de 25 módulos en un acordeón reagrupado de 6 grupos colapsables, con auto-expansión por ruta y agregar un placeholder navegable para el futuro módulo Reglamento.

**Architecture:** Cambio 100% frontend, sobre `Sidebar.jsx` + `index.css`. Se preserva `Sidebar({ rol, abierto, onCerrar })` como contrato con `AppLayout`. La agrupación pasa a 6 grupos; cada uno se maneja con `useState` para saber cuál está abierto, sincronizado con `useLocation()` de react-router. Sin backend, sin cambios de rutas de API, sin tests de pytest.

**Tech Stack:** React 18 + Vite, react-router-dom v6, CSS con variables ya definidas en `frontend/src/index.css` (tokens `--color-*`, `--radius-sm`). Sin librerías nuevas.

**Verificación:** el proyecto no tiene tests de frontend. Cada task cierra con una verificación manual en el browser (dev server `npm run dev` desde `frontend/`, ya corriendo o iniciable) y luego commit. Roles a testear: `administracion`, `representante`, `departamento`.

**Referencia:** `docs/superpowers/specs/2026-07-04-aside-navegacion-design.md`.

---

## File Structure

**Modificar:**
- `frontend/src/components/Sidebar.jsx` — nueva agrupación + estado de acordeón + toggle.
- `frontend/src/index.css` — estilos del botón de grupo, chevron, animación y estado activo.
- `frontend/src/App.jsx` — nueva ruta `/reglamento`.

**Crear:**
- `frontend/src/screens/Reglamento.jsx` — pantalla placeholder "En construcción".

**No tocar:** backend, otros componentes, rutas de API, tests de pytest, documentación de reglas.

---

## Task 1: Placeholder de Reglamento (pantalla + ruta)

Este task deja navegable `/reglamento` con una pantalla mínima. Se hace primero para que en la Task 2 el link a Reglamento ya tenga destino real.

**Files:**
- Create: `frontend/src/screens/Reglamento.jsx`
- Modify: `frontend/src/App.jsx` (imports + `<Route>` dentro del layout autenticado)

- [ ] **Step 1: Crear el componente `Reglamento.jsx`**

Contenido completo (usa `Tarjeta` como el resto de las screens):

```jsx
import Tarjeta from "../components/Tarjeta";

export default function Reglamento() {
  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Reglamento</h2>
      </header>
      <Tarjeta>
        <p>
          Próximamente vas a poder consultar el reglamento del consorcio desde
          acá. El módulo todavía está en construcción.
        </p>
      </Tarjeta>
    </section>
  );
}
```

- [ ] **Step 2: Agregar el import en `App.jsx`**

En `frontend/src/App.jsx`, agregar el import junto a los demás screens (después de la línea de `import Reservas from "./screens/Reservas";`):

```jsx
import Reglamento from "./screens/Reglamento";
```

- [ ] **Step 3: Agregar la ruta en `App.jsx`**

Dentro del `<Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>`, después de `<Route path="reservas" element={<Reservas />} />` y antes de `<Route path="*" element={<NotFound />} />`, agregar:

```jsx
<Route path="reglamento" element={<Reglamento />} />
```

- [ ] **Step 4: Verificar manualmente**

- Si el dev server no está corriendo: desde `frontend/` correr `npm run dev`.
- En el browser, loguearse (cualquier rol) e ir a `http://localhost:5173/reglamento`.
- Esperado: aparece el título "Reglamento" y la tarjeta con el texto "En construcción".
- Verificar que ninguna ruta existente rompió: entrar a `/comunicados`, `/expensas`, `/reservas` — se cargan bien.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/screens/Reglamento.jsx frontend/src/App.jsx
git commit -m "feat(frontend): placeholder de Reglamento en /reglamento"
```

---

## Task 2: Nueva agrupación de `SECCIONES` en `Sidebar.jsx`

Reemplaza la constante `SECCIONES` por los 6 grupos definidos en el spec. Todavía **no** se cambia el comportamiento (siguen renderizándose todos abiertos), solo la agrupación y el orden. Esto reduce el diff cognitivo del próximo task.

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx` (constante `SECCIONES`, líneas 5-176)

- [ ] **Step 1: Reescribir la constante `SECCIONES`**

Reemplazar todo el bloque `const SECCIONES = [ ... ];` (líneas 5-176 del archivo actual) por:

```jsx
const SECCIONES = [
  {
    titulo: "Comunicaciones",
    modulos: [
      {
        ruta: "/comunicados",
        nombre: "Comunicados",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reglamento",
        nombre: "Reglamento",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
    ],
  },
  {
    titulo: "Finanzas",
    modulos: [
      {
        ruta: "/mi-cuenta",
        nombre: "Mi cuenta",
        rolesPermitidos: ["departamento"],
      },
      {
        ruta: "/expensas",
        nombre: "Expensas",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/comprobantes",
        nombre: "Comprobantes",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/periodos",
        nombre: "Historial de cierres",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/gastos",
        nombre: "Gastos",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/estado-financiero",
        nombre: "Estado financiero",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/cajas",
        nombre: "Cajas",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/transferencias",
        nombre: "Transferencias",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
  {
    titulo: "Operación",
    modulos: [
      {
        ruta: "/peticiones",
        nombre: "Peticiones",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/trabajos",
        nombre: "Trabajos",
        rolesPermitidos: ["administracion", "representante"],
      },
      {
        ruta: "/trabajos-recurrentes",
        nombre: "Trabajos recurrentes",
        rolesPermitidos: ["administracion", "representante"],
      },
      {
        ruta: "/reservas",
        nombre: "Reservas",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/amenities",
        nombre: "Amenities",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
  {
    titulo: "Reportes",
    modulos: [
      {
        ruta: "/reportes/morosos",
        nombre: "Lista de morosos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reportes/estado-financiero",
        nombre: "Estado financiero",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reportes/gastos",
        nombre: "Detalle de gastos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reportes/proveedores",
        nombre: "Lista de proveedores",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
    ],
  },
  {
    titulo: "Personal",
    modulos: [
      {
        ruta: "/liquidaciones",
        nombre: "Liquidaciones",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/haberes",
        nombre: "Haberes",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/conceptos-liquidacion",
        nombre: "Conceptos de liquidación",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
  {
    titulo: "Configuración",
    modulos: [
      {
        ruta: "/configuracion",
        nombre: "Datos del consorcio",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/clases-prorrateo",
        nombre: "Clases de prorrateo",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/proveedores",
        nombre: "Proveedores",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/departamentos",
        nombre: "Departamentos",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/empleados",
        nombre: "Empleados",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
];
```

**No** modificar todavía el JSX del componente ni la lógica de `seccionesVisibles`. La lógica de filtro por rol y por `reportes_visibles_a_depto` sigue funcionando igual.

- [ ] **Step 2: Verificar manualmente los 3 roles**

Recargar el browser (Vite hot-reloads):

- **Admin:** ver en el sidebar 6 títulos en este orden: Comunicaciones, Finanzas, Operación, Reportes, Personal, Configuración. Bajo Comunicaciones deben aparecer "Comunicados" y "Reglamento". Bajo Finanzas los 8 módulos (incluyendo Mi cuenta oculto porque solo depto). Clickear cada link y verificar que abre la pantalla correcta.
- **Departamento:** loguearse como usuario de rol depto. Esperado: Comunicaciones (Comunicados + Reglamento), Finanzas (Mi cuenta, Expensas, Comprobantes), Operación (Peticiones, Reservas). Reportes solo si `reportes_visibles_a_depto` está en `true` en `/configuracion`.
- **Representante:** loguearse como rol representante. Esperado: Comunicaciones (los dos), Operación (Peticiones, Trabajos, Trabajos recurrentes), Reportes.

- [ ] **Step 3: Verificar mobile (drawer)**

En DevTools → device toolbar → iPhone SE (375px):
- Abrir hamburguesa, ver los 6 grupos.
- Clickear un link → el drawer se cierra y navega.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "refactor(frontend): reagrupar sidebar en 6 grupos"
```

---

## Task 3: Estado del acordeón (toggle + auto-expansión por ruta)

Convierte el `<h3>` del título de grupo en un `<button>`, agrega estado `grupoAbierto`, sincroniza con la ruta activa usando `useLocation`, y renderiza los módulos solo cuando el grupo está abierto (acordeón estricto: uno por vez). Sin estilos aún (esos van en Task 4).

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Agregar imports en `Sidebar.jsx`**

En la línea 1 (imports actuales), agregar `useLocation` al import de `react-router-dom`:

```jsx
import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { obtenerConfiguracion } from "../api/configuracion";
```

- [ ] **Step 2: Agregar helper `grupoDeRuta` fuera del componente**

Debajo de la constante `SECCIONES` (y antes de `export default function Sidebar`), agregar:

```jsx
function grupoDeRuta(pathname) {
  for (const seccion of SECCIONES) {
    if (seccion.modulos.some((m) => pathname.startsWith(m.ruta))) {
      return seccion.titulo;
    }
  }
  return null;
}
```

Se usa `startsWith` para tolerar rutas con parámetros o hijos (por ejemplo `/reportes/morosos` matchea el módulo `/reportes/morosos`, y una futura `/gastos/habituales` matchearía Gastos).

- [ ] **Step 3: Agregar estado del grupo abierto y sincronización con la ruta**

Dentro del componente `Sidebar`, después del `useState` de `reportesVisiblesDepto` (línea 181) y antes del `useEffect` que lee configuración, agregar:

```jsx
  const location = useLocation();
  const [grupoAbierto, setGrupoAbierto] = useState(() =>
    grupoDeRuta(location.pathname)
  );

  useEffect(() => {
    const grupo = grupoDeRuta(location.pathname);
    if (grupo) setGrupoAbierto(grupo);
  }, [location.pathname]);

  function toggleGrupo(titulo) {
    setGrupoAbierto((actual) => (actual === titulo ? null : titulo));
  }
```

Nota: la ruta activa siempre expande su grupo (aunque el usuario lo haya cerrado a mano) — el `useEffect` reabre el grupo cuando cambia el `pathname`. Esto respeta el requisito del spec "auto-expansión por ruta".

- [ ] **Step 4: Reemplazar `<h3>` por `<button>` y renderizar módulos condicionalmente**

Reemplazar el bloque de renderizado dentro de `<nav>` (líneas 220-239 del archivo actual):

```jsx
        {seccionesVisibles.map((s) => {
          const abierto = grupoAbierto === s.titulo;
          const grupoActivo = grupoDeRuta(location.pathname) === s.titulo;
          return (
            <div key={s.titulo} className="sidebar-section">
              <button
                type="button"
                className={
                  grupoActivo
                    ? "sidebar-section-titulo activo"
                    : "sidebar-section-titulo"
                }
                aria-expanded={abierto}
                onClick={() => toggleGrupo(s.titulo)}
              >
                <span>{s.titulo}</span>
                <span className="sidebar-chevron" aria-hidden="true">▸</span>
              </button>
              {abierto && (
                <ul>
                  {s.modulos.map((m) => (
                    <li key={m.ruta}>
                      <NavLink
                        to={m.ruta}
                        onClick={onCerrar}
                        className={({ isActive }) =>
                          isActive ? "sidebar-link activo" : "sidebar-link"
                        }
                      >
                        {m.nombre}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
```

- [ ] **Step 5: Verificar manualmente el comportamiento**

Recargar (Vite hot-reload):

- **Admin en `/comunicados`:** solo el grupo Comunicaciones está abierto. Los 5 títulos restantes están cerrados (sin módulos visibles debajo).
- Clickear "Finanzas" → se abre Finanzas y se cierra Comunicaciones. Clickear "Finanzas" de nuevo → se cierra (queda todo cerrado).
- Navegar de `/comunicados` a `/gastos` clickeando primero el link (dentro del grupo Finanzas cuando lo abrás): al cargar `/gastos`, Finanzas queda abierto.
- Cerrar Finanzas a mano estando en `/gastos` → todos los grupos cerrados; el título "Finanzas" NO se pinta con clase `activo` aún (los estilos van en Task 4, pero el atributo debería estar).
- Navegar por URL directa (barra de dirección) a `/proveedores`: al cargar, Configuración se auto-expande.
- Verificar los 3 roles: cada uno ve solo sus grupos y el acordeón funciona.

- [ ] **Step 6: Verificar mobile**

En iPhone SE:
- Abrir hamburguesa → 6 grupos, solo el activo abierto.
- Toggle de un grupo funciona con touch.
- Clickear un link → drawer cierra y navega.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "feat(frontend): acordeon del sidebar con auto-expansion por ruta"
```

---

## Task 4: Estilos del acordeón (botón, chevron, hover, activo)

Ajusta `index.css` para que el título de grupo se vea y se sienta como un botón limpio, con chevron que rota, hover delicado (patrón ya validado), estado activo pintado en `--color-primary`, y target táctil ≥44px.

**Files:**
- Modify: `frontend/src/index.css` (bloque `.sidebar-section-titulo` en la línea 534 y agregado de reglas nuevas)

- [ ] **Step 1: Reemplazar el bloque `.sidebar-section-titulo`**

Localizar el bloque actual (líneas 534-542 aprox.):

```css
.sidebar-section-titulo {
  margin: 0;
  padding: 0.5em 1em 0.35em;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
}
```

Reemplazarlo por:

```css
.sidebar-section-titulo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  width: calc(100% - 1rem);
  margin: 0 0.5rem;
  padding: 0.75em 0.75em;
  min-height: 44px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
  cursor: pointer;
  text-align: left;
}

.sidebar-section-titulo:hover {
  background: color-mix(in srgb, var(--color-primary-soft) 55%, transparent);
  color: var(--color-primary);
}

.sidebar-section-titulo.activo {
  color: var(--color-primary);
}

.sidebar-chevron {
  font-size: 0.7rem;
  color: var(--color-text-muted);
  transition: transform 150ms ease;
  transform: rotate(0deg);
}

.sidebar-section-titulo[aria-expanded="true"] .sidebar-chevron {
  transform: rotate(90deg);
  color: var(--color-primary);
}

.sidebar-section-titulo.activo .sidebar-chevron {
  color: var(--color-primary);
}
```

- [ ] **Step 2: Ajustar el override desktop del título**

Localizar el bloque desktop (líneas 1073-1075 aprox.):

```css
  .sidebar-section-titulo {
    padding: 0.5em 1.25em 0.4em;
  }
```

Reemplazarlo por:

```css
  .sidebar-section-titulo {
    width: calc(100% - 1.5rem);
    margin: 0 0.75rem;
    padding: 0.75em 0.9em;
  }
```

- [ ] **Step 3: Verificar visualmente en desktop**

Recargar. En ≥960px:
- El título del grupo se ve como un botón sutil: hover con tinte delicado, sin borde marcado.
- El chevron `▸` está a la derecha, apunta a la derecha cuando el grupo está cerrado y rota 90° hacia abajo cuando está abierto (transición suave).
- El grupo activo (ej. Comunicaciones si estás en `/comunicados`) tiene su título pintado en el color primario aunque esté cerrado (probar: clickear el título para cerrarlo y confirmar que sigue con el color).
- Los links dentro conservan el highlight `--color-primary-soft` del NavLink activo.

- [ ] **Step 4: Verificar visualmente en mobile (375px)**

En iPhone SE:
- Abrir drawer, ver los 6 botones-título con hit area cómoda (44px mínimo).
- Toggle con tap responde bien.
- La rotación del chevron es visible.
- Nada desborda 375px de ancho.

- [ ] **Step 5: Verificar los 3 roles una vez más**

- Admin: 6 grupos, acordeón fluye.
- Depto: 3-4 grupos según flag, misma experiencia.
- Representante: sus grupos permitidos.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css
git commit -m "style(frontend): estilos del acordeon del sidebar (chevron y hover)"
```

---

## Self-review checklist (para quien ejecute)

Después de cerrar Task 4, mirar el resultado con ojo fresco:

- [ ] La ruta `/reglamento` funciona y aparece en el sidebar para los 3 roles.
- [ ] El sidebar muestra exactamente 6 grupos (menos para roles con menos módulos).
- [ ] Un grupo abierto por vez.
- [ ] Auto-expansión al cambiar de ruta.
- [ ] Título del grupo activo pintado, aunque esté colapsado.
- [ ] Cero cambios en el backend, en las rutas de API, ni en pytest.
- [ ] `.claude/rules/business-rules.md` sigue siendo cierto (permisos idénticos).
- [ ] Nada rompió: recorrer 3-4 pantallas de distintos grupos y confirmar que se cargan.
