# Reestructura de la navegación (sidebar)

## Problema

La navegación actual (`SECCIONES` en `frontend/src/navegacion.js`) tiene 8 secciones
de nivel 1 con inconsistencias que dificultan el uso, sobre todo para el rol
Administración, que vive en el sidebar todo el día:

- **No hay link a Inicio en el sidebar.** La ruta `/` (`InicioRoute`) existe pero
  no figura en `SECCIONES`, así que en desktop no hay forma de volver al inicio
  desde la navegación.
- **`grupoDeRuta` desconoce rutas reales.** `/comprobantes`, `/expensas`,
  `/cierre-de-periodo`, `/departamentos/:id/cuenta` no matchean ninguna sección,
  así que al entrar a esas pantallas el acordeón queda abierto en el grupo anterior.
- **Las secciones de 1 item muestran el título de la sección, no el nombre del
  módulo.** Por eso se ve "Comunicación" en vez de "Comunicados".
- **`filtrarSecciones` filtra Personal comparando el string `"Personal"`.** Renombrar
  la categoría rompe el feature flag `usa_personal_propio`.
- **Categorías dispersas:** Cobranzas, Gastos y Finanzas están en 3 secciones
  separadas cuando conceptualmente son finanzas; Comunicación es una sección con un
  único item; Reportes cuelga como sección independiente.

La base de la reestructura es `propuesta-sidebar.md`: 4 macro-categorías
(Finanzas, Gestión, Personal, Configuración) + Inicio suelto, nombradas desde la
perspectiva del administrador.

## Alcance

**Incluye:** el modelo de datos de navegación (`navegacion.js`), el render del
sidebar de desktop (`Sidebar.jsx`), el hook de filtrado (`useNavegacionVisible.js`),
y el sheet "Más" de mobile (`TabBar.jsx`), más el CSS asociado (`index.css`).

**No incluye (fuera de alcance explícito):**

- La **TabBar** (los 5 atajos fijos por rol) no se toca. Son accesos directos, no
  un índice de la jerarquía.
- El **theming de páginas** (`moduloDeRuta` + `MODULO_POR_RUTA`, que pinta
  `data-modulo`). Tiene mapeos raros (`/comunicados`→`finanzas`, `/reservas`→
  `cobranzas`, `/liquidaciones`→`expensas`) pero es un concern distinto de la
  navegación y se limpia aparte.
- El **rediseño del hub "Mi cuenta"** del rol departamento (acordado por separado).
  Ese trabajo toca el *contenido* de las pantallas; este toca la *navegación*.
- **`SidebarSuperAdmin.jsx`** (super_admin conserva su sidebar plana de 3 items).

### Tres vocabularios de "módulo" — legítimamente distintos

No hay que unificarlos; son concerns diferentes:

| Concern | Quién lo maneja | ¿Lo toca este trabajo? |
|---|---|---|
| **Gating** (mostrar/ocultar por consorcio) | campo `modulo` en la hoja + `modulosHabilitados` | Sí, se conserva |
| **Resaltado de nav** (qué categoría se abre) | `categoriaDeRuta` (antes `grupoDeRuta`) | Sí, se arregla |
| **Theming de página** (`data-modulo`, color) | `moduloDeRuta` + `MODULO_POR_RUTA` | No |

## Modelo de datos

`SECCIONES` (lista de 2 niveles) se reemplaza por `CATEGORIAS`, un árbol de
**exactamente 3 niveles** (categoría → sub-grupo → item), nunca más. Un nodo con
`ruta` es un item (hoja); un nodo con `hijos` es un grupo.

```js
export const CATEGORIAS = [
  { ruta: "/", nombre: "Inicio", suelto: true,
    rolesPermitidos: ["administracion", "representante"] },

  { id: "finanzas", titulo: "Finanzas", hijos: [
      { ruta: "/mi-cuenta", nombre: "Mi cuenta", modulo: "cobranzas",
        rolesPermitidos: ["departamento"] },
      { ruta: "/cobranzas", nombre: "Cobranzas", modulo: "cobranzas",
        rolesPermitidos: ["administracion"],
        rutasRelacionadas: ["/expensas", "/comprobantes", "/cierre-de-periodo", "/departamentos"] },
      { ruta: "/gastos", nombre: "Gastos", modulo: "gastos",
        rolesPermitidos: ["administracion"] },
      { ruta: "/tesoreria", nombre: "Tesorería", modulo: "finanzas",
        rolesPermitidos: ["administracion"] },
      { ruta: "/cuentas-corrientes", nombre: "Cuentas corrientes", modulo: "cobranzas",
        rolesPermitidos: ["administracion"] },
      { id: "reportes", titulo: "Reportes", hijos: [
          { ruta: "/reportes/morosos", nombre: "Lista de morosos", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/reportes/estado-financiero", nombre: "Estado financiero", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/reportes/gastos", nombre: "Detalle de gastos", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/reportes/proveedores", nombre: "Lista de proveedores", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
      ]},
  ]},

  { id: "gestion", titulo: "Gestión", hijos: [
      { id: "comunicacion", titulo: "Comunicación", hijos: [
          { ruta: "/comunicados", nombre: "Comunicados", modulo: "comunicacion",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
      ]},
      { id: "mantenimiento", titulo: "Mantenimiento", hijos: [
          { ruta: "/peticiones", nombre: "Peticiones", modulo: "operacion",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/trabajos", nombre: "Trabajos", modulo: "operacion",
            rolesPermitidos: ["administracion", "representante"] },
          { ruta: "/trabajos-recurrentes", nombre: "Trabajos recurrentes", modulo: "operacion",
            rolesPermitidos: ["administracion", "representante"] },
      ]},
      { id: "espacios", titulo: "Espacios", hijos: [
          { ruta: "/reservas", nombre: "Reservas", modulo: "espacios_comunes",
            rolesPermitidos: ["administracion", "departamento"] },
          { ruta: "/amenities", nombre: "Amenities", modulo: "espacios_comunes",
            rolesPermitidos: ["administracion"] },
      ]},
  ]},

  { id: "personal", titulo: "Personal", hijos: [
      { ruta: "/empleados", nombre: "Empleados", modulo: "personal", rolesPermitidos: ["administracion"] },
      { ruta: "/haberes", nombre: "Haberes", modulo: "personal", rolesPermitidos: ["administracion"] },
      { ruta: "/liquidaciones", nombre: "Liquidaciones", modulo: "personal", rolesPermitidos: ["administracion"] },
      { ruta: "/conceptos-liquidacion", nombre: "Conceptos de liquidación", modulo: "personal", rolesPermitidos: ["administracion"] },
  ]},

  { id: "configuracion", titulo: "Configuración", hijos: [
      { ruta: "/configuracion", nombre: "Datos del consorcio", rolesPermitidos: ["administracion"] },
      { ruta: "/administracion/consorcios", nombre: "Consorcios de la administración", rolesPermitidos: ["administracion"] },
      { ruta: "/clases-prorrateo", nombre: "Clases de prorrateo", rolesPermitidos: ["administracion"] },
      { ruta: "/proveedores", nombre: "Proveedores", rolesPermitidos: ["administracion"] },
      { ruta: "/padron", nombre: "Usuarios y coeficientes", rolesPermitidos: ["administracion"] },
  ]},
];
```

Notas de campo:
- `suelto: true` → item de nivel 1 sin acordeón (Inicio).
- `id` en categorías/sub-grupos → key estable y base del feature flag de Personal.
- `modulo` en hojas → gating por `modulosHabilitados` (igual que hoy).
- `rutasRelacionadas` → prefijos extra que resaltan la categoría sin ser links del
  menú (arregla `/comprobantes`, `/expensas`, etc.).
- `rolesPermitidos` en la categoría Inicio omite `departamento` (su primer destino
  es Mi cuenta, como hoy en `ORDEN_DEPTO`).

## Filtrado — `filtrarArbol()` (profundidad fija, no recursión)

Reemplaza a `filtrarSecciones`. El árbol tiene 3 niveles fijos, así que el
recorrido es explícito (no recursivo genérico, para no invitar a un 4º nivel con
comportamiento impredecible). Orden de pasos:

1. **Permisos por hoja.** Descarta hojas cuyo `rolesPermitidos` no incluye el rol;
   aplica `modulosHabilitados` (si no es `null`); aplica la excepción
   `reportes_visibles_a_depto` para hojas bajo `/reportes/` cuando el rol es
   departamento. Idéntico al comportamiento actual.
2. **Poda de vacíos.** Sub-grupo o categoría sin hijos tras el filtrado desaparece.
3. **Personal por `id`.** Si `!usaPersonalPropio`, se descarta la categoría
   `id === "personal"` (antes se comparaba el string `"Personal"`).
4. **Regla 1 — sub-grupo de 1.** Un sub-grupo que queda con un único item se
   reemplaza por ese item (se disuelve el label). Efecto: "Comunicación" nunca
   aparece como rótulo sobre un solo "Comunicados".
5. **Regla 2 — promoción.** Una categoría que queda con un único sub-grupo y ningún
   item directo se promueve: el sub-grupo pasa a ser la categoría de nivel 1.
   Efecto: representante ve "REPORTES" en nivel 1 (no "Finanzas ▸ Reportes", que no
   tiene sentido para un rol sin finanzas).

Las reglas 4 y 5 existen por dos casos concretos de hoy (Comunicación de 1 item; la
Finanzas-solo-Reportes de representante), no por hipótesis futuras.

## Resaltado de ruta — `categoriaDeRuta()`

Reemplaza a `grupoDeRuta`. Camina `CATEGORIAS` y devuelve el `titulo`/`id` de la
categoría de nivel 1 que contiene la ruta actual, matcheando tanto `ruta` de las
hojas como sus `rutasRelacionadas` (con igualdad exacta o prefijo `ruta + "/"`).
Arregla que `/comprobantes`, `/expensas`, `/cierre-de-periodo` y
`/departamentos/:id/cuenta` dejaran el acordeón abierto en el grupo equivocado.

## Vista por rol (resultado esperado)

**Administración** — las 4 categorías + Inicio. Ejemplo, Gestión abierta:

```
Inicio
FINANZAS ▾            (Cobranzas, Gastos, Tesorería, Cuentas corrientes, ── REPORTES ── + 4)
GESTIÓN ▾
   Comunicados                 (regla 1: Comunicación 1 item → item suelto)
   ── MANTENIMIENTO ──
   Peticiones · Trabajos · Trabajos recurrentes
   ── ESPACIOS ──
   Reservas · Amenities
PERSONAL ▸
CONFIGURACIÓN ▸
```

**Representante:**

```
Inicio
GESTIÓN ▸            (Comunicados [regla 1] + Mantenimiento)
REPORTES ▸           (regla 2: era Finanzas → Reportes)
```

**Departamento** — mantiene rama especial de lista plana (sin acordeones),
reordenada por `ORDEN_DEPTO`, con los reportes agrupados bajo un cluster "REPORTES"
(en vez de colgar sueltos al final). `aplanarParaDepto(arbol)` devuelve los items
ordenados seguidos de los sub-grupos que sobrevivieron con más de un item (en la
práctica, solo Reportes):

```
Mi cuenta · Comunicados · Peticiones · Reservas
── REPORTES ──
Morosos · Estado financiero · Detalle de gastos · Proveedores
```

**Super_admin** — sin cambios (`SidebarSuperAdmin.jsx` intacto).

## Render — `Sidebar.jsx`

Dos paths, como hoy:

- **Departamento:** rama plana usando `aplanarParaDepto`. Los items van como
  `NavLink`; el cluster Reportes se rotula con `.sidebar-subgrupo` y sus items debajo.
- **Resto de roles:** `.map` sobre las categorías filtradas, distinguiendo por forma
  del nodo:
  1. **Item suelto** (`nodo.suelto`) → `NavLink` directo, arriba de todo, sin acordeón.
  2. **Categoría** (`titulo` + `hijos`) → botón-acordeón de nivel 1, idéntico a hoy.
     Un solo grupo abierto a la vez (`grupoAbierto` se conserva). Chevron ▸/▾ y clase
     `.activo` los gobierna `categoriaDeRuta`.
  3. **Dentro de la categoría abierta**, se mapean los hijos: hijo item → `NavLink`;
     hijo sub-grupo → label no-clickable (`.sidebar-subgrupo`) seguido de sus items.
     **El sub-grupo no togglea nada** — es un divisor visual; sus items ya están a la
     vista. No se agrega estado nuevo.

Accesibilidad: el label de sub-grupo **no es un `<button>`** (no hace nada), es un
`<p>`/rótulo. Así no hay targets táctiles muertos y el lector de pantalla lo lee como
etiqueta, no como acción.

## CSS — `index.css`

Se reutilizan sin tocar `.sidebar-section`, `.sidebar-section-titulo`,
`.sidebar-chevron`, `.sidebar-link`. Única clase nueva:

```css
.sidebar-subgrupo {
  margin: 0.5rem 0.5rem 0.15rem;
  padding: 0 0.75em;
  font-size: 0.5625rem;              /* < categoría (0.625rem): jerarquía por tamaño */
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.sidebar-subgrupo::after {           /* línea "── ESPACIOS ──" */
  content: "";
  flex: 1;
  height: 1px;
  background: var(--color-border);
}
```

Los items bajo un sub-grupo llevan un modificador `.sidebar-link.en-subgrupo` con
`padding-left` extra, para leerse como colgados del rótulo. Sin hex hardcodeado
(colores por `var(--color-*)`), tamaños en `rem`, targets ≥44px intactos. Jerarquía
tipográfica de 3 pesos, sin íconos: categoría `0.625rem` + línea superior + chevron;
sub-grupo `0.5625rem` + línea al costado; item `0.8125rem` peso normal. En el bloque
`@media (min-width: 960px)` se verifica que `.sidebar-subgrupo` no rompa el padding
del sidebar fijo; no requiere reglas nuevas.

## Sheet "Más" (mobile) — `TabBar.jsx` + `useNavegacionVisible.js`

El sheet "Más" reusa `seccionesMas`. Con el árbol nuevo, cada categoría trae `hijos`
que pueden ser items o sub-grupos. Para el sheet se **aplana un nivel**: cada
categoría es una `<section>` con su `micro-label`, y los sub-grupos se disuelven en
la lista de items (el sheet mobile es una lista de escape, no el índice principal;
no necesita el 3er nivel).

`useNavegacionVisible` adapta el cálculo de `seccionesMas`, `rutasVisibles` y
`tabsVisibles` al árbol, pero **devuelve la misma forma que hoy** (`{ secciones,
seccionesMas, tabsVisibles, cargando }`) para no tocar `AppLayout.jsx`.

## Verificación

No hay runner de tests JS en el frontend (solo `lint` y `build`). Verificación:

- `npm run build` sin errores.
- `npm run lint` sin warnings nuevos.
- Revisión manual en browser por rol (administración, representante, departamento,
  super_admin) en desktop (≥960px) y mobile (375px, iPhone SE):
  - Inicio aparece y navega en admin/representante.
  - Al entrar a `/comprobantes`, `/expensas`, `/cierre-de-periodo` se resalta Finanzas.
  - "Comunicados" aparece como item, no como rótulo "Comunicación".
  - Representante ve "REPORTES" en nivel 1.
  - Departamento ve su lista plana con cluster Reportes.
  - Feature flag `usa_personal_propio = false` oculta Personal.
  - Sheet "Más" en mobile lista las categorías con sus items.
  - Super_admin sin cambios.
```
