# Limpieza del theming por módulo + label del sheet "Más" (depto)

## Problema

Dos cabos sueltos que quedaron fuera de alcance de la reestructura de navegación
(ver `2026-07-30-reestructura-navegacion-design.md`):

### 1. `moduloDeRuta` / `MODULO_POR_RUTA` — theming incoherente

`AppLayout` pinta un acento por área vía `data-modulo` (`--color-modulo`), tomado de
una paleta fija de **6 colores** definidos en `index.css`:

| Clave | Hex | Rol semántico (nuevo) |
|---|---|---|
| `inicio` | `#1b3a4b` (navy) | Home + setup neutral |
| `cobranzas` | `#305d4a` (verde) | Plata que entra |
| `gastos` | `#c0443c` (rojo) | Plata que sale |
| `finanzas` | `#8a6d1c` (oro) | Análisis |
| `expensas` | `#2c6473` (teal) | Autogestión del depto |
| `operacion` | `#5b36b8` (violeta) | Operación del edificio (Gestión) |

`MODULO_POR_RUTA` mapea prefijos de ruta → clave de color (primer match gana). Hoy
tiene asignaciones arbitrarias y rutas huérfanas que caen al default `inicio`:

- `/comunicados` → `finanzas` (arbitrario; comunicación no es finanzas).
- `/reservas` → `cobranzas` mientras `/amenities` → `operacion` (misma área "Espacios",
  dos colores distintos).
- `/liquidaciones` → `expensas`, pero `/haberes`, `/empleados`,
  `/conceptos-liquidacion` no están mapeadas → default `inicio` (Personal partido).
- `/trabajos-recurrentes` no matchea `/trabajos` (el prefijo requiere `/trabajos/`),
  cae a `inicio` en vez de `operacion`.
- `/reportes/*` sin mapear → `inicio`.

Además, cada entrada de `TABS_POR_ROL` tiene un campo `modulo` con los mismos valores
arbitrarios (`Comunicados`→`finanzas`, `Reservas`→`cobranzas`). **Ese campo no lo
consume ningún componente** (verificado: solo se usa `s.modulos` plural en el sheet;
la tab bar usa `ruta`/`nombre`/`icono`). Es un tercer vocabulario de "módulo" muerto.

### 2. Sheet "Más" (depto) — encabezado "Finanzas" que el depto nunca ve

El sheet "Más" mobile toma `seccionesMas`, que para todos los roles se computa
aplanando las macro-categorías (`aplanarCategoria`). Para departamento, los reportes
viven en la categoría "Finanzas" (con `/mi-cuenta` filtrado por estar en la tab bar),
así que el sheet muestra un encabezado **"Finanzas"** — vocabulario de administración
que el depto nunca ve en su navegación plana (donde el cluster se llama "Reportes").

## Alcance

**Incluye:** `MODULO_POR_RUTA` (reescritura), remoción del campo muerto `modulo` de
`TABS_POR_ROL`, y el cálculo de `seccionesMas` para el rol departamento en
`useNavegacionVisible.js`.

**No incluye:** agregar colores nuevos a la paleta (decisión tomada: mantener los 6),
la tab bar principal, ni el resto de la navegación (ya integrada).

## Decisión de diseño — mapeo de theming (6 colores, sin agregar)

Cada ruta tiene un hogar coherente con una historia legible detrás:

| Color (clave) | Rutas (prefijos) |
|---|---|
| **navy** (`inicio`) | `/` (especial), y **Configuración** por default sin mapear: `/configuracion`, `/clases-prorrateo`, `/proveedores`, `/padron`, `/administracion/consorcios` |
| **verde** (`cobranzas`) | `/cobranzas`, `/cuentas-corrientes`, `/comprobantes` |
| **rojo** (`gastos`) | `/gastos`, `/liquidaciones`, `/haberes`, `/empleados`, `/conceptos-liquidacion` |
| **oro** (`finanzas`) | `/tesoreria`, `/estado-financiero`, `/cajas`, `/transferencias`, `/reportes` |
| **teal** (`expensas`) | `/mi-cuenta`, `/expensas`, `/departamentos`, `/cierre-de-periodo`, `/periodos` |
| **violeta** (`operacion`) | `/peticiones`, `/trabajos`, `/trabajos-recurrentes`, `/amenities`, `/reservas`, `/comunicados` |

Decisiones subjetivas confirmadas con el usuario:
- **Personal → rojo (gastos):** "plata que sale" (genera gastos de sueldos).
- **Comunicados → violeta (operacion):** unifica todo Gestión bajo un acento.
- **Configuración → navy (inicio):** zona de setup neutral, junto a Home. Se logra
  dejándola **sin mapear** (el default de `moduloDeRuta` ya devuelve `inicio`), así que
  no requiere entradas nuevas.

### Nuevo `MODULO_POR_RUTA`

Orden: prefijos más específicos primero cuando podrían solaparse. `/reportes` cubre
`/reportes/*`. `/gastos` cubre `/gastos/habituales`. `/trabajos-recurrentes` necesita
entrada propia (no lo captura `/trabajos`). Configuración queda fuera de la lista
(default `inicio`).

```js
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

`moduloDeRuta` no cambia su lógica (`if (pathname === "/") return "inicio"` + búsqueda
por prefijo + default `inicio`).

### Remoción del campo muerto `modulo` en `TABS_POR_ROL`

Verificar una vez más que ningún componente lee `.modulo` de una tab (grep). Si se
confirma muerto, quitar el campo `modulo` de las 12 entradas de `TABS_POR_ROL`,
dejando `{ ruta, nombre, icono }`. Si resultara estar en uso, NO removerlo y alinear
sus valores con el mapeo de arriba en su lugar (reportar el hallazgo).

## Decisión de diseño — sheet "Más" del depto

Para el rol **departamento**, computar `seccionesMas` desde `aplanarParaDepto(secciones)`
en vez de `aplanarCategoria`, para que el cluster se rotule con su nombre real
("Reportes") y no con el título de la categoría de administración ("Finanzas").

`aplanarParaDepto(secciones)` devuelve `{ items, subgrupos }` (los `subgrupos` ya vienen
`{ id, titulo, hijos }` con `titulo` correcto, p.ej. "Reportes"). El sheet "Más" quiere
`[{ titulo, modulos: [{ruta, nombre}] }]` con las rutas que NO están en la tab bar.

Lógica para departamento:
```js
const { items, subgrupos } = aplanarParaDepto(secciones);
const noEnTabs = (m) => !rutasEnTabs.has(m.ruta);
const seccionesMas = subgrupos
  .map((sg) => ({
    titulo: sg.titulo,
    modulos: sg.hijos.filter(noEnTabs).map((m) => ({ ruta: m.ruta, nombre: m.nombre })),
  }))
  .filter((s) => s.modulos.length > 0);
```

Nota: los `items` planos del depto (mi-cuenta, peticiones, reservas, comunicados) están
siempre en la tab bar, así que no generan sección en "Más" (comportamiento actual: el
sheet solo muestra lo que no es tab). Un comentario en el código deja constancia. Los
demás roles siguen usando `aplanarCategoria` sin cambios.

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `frontend/src/navegacion.js` | Reescribir `MODULO_POR_RUTA`; quitar campo `modulo` de `TABS_POR_ROL` (si confirmado muerto) |
| `frontend/src/hooks/useNavegacionVisible.js` | `seccionesMas` desde `aplanarParaDepto` para rol departamento |

No cambian: `index.css` (la paleta de 6 se mantiene), `AppLayout.jsx`, `Sidebar.jsx`,
`TabBar.jsx`.

## Verificación

Sin runner de tests JS. Verificación:
- `npm run build` sin errores; `npx eslint` sin errores nuevos (los 2
  `set-state-in-effect` pre-existentes son aceptables).
- Confirmar por rol en browser (`npm run dev`):
  - Admin: navegar a `/comunicados` (violeta), `/liquidaciones` y `/haberes` (rojo),
    `/reportes/morosos` (oro), `/reservas` y `/amenities` (violeta),
    `/trabajos-recurrentes` (violeta), `/configuracion` (navy). El acento del header
    (`--color-modulo`) cambia acorde.
  - Depto: abrir el sheet "Más" → el cluster de reportes se rotula **"Reportes"**,
    no "Finanzas". Sin reportes habilitados, el sheet no muestra esa sección.
  - Verificar que no haya rutas que caigan a un color inesperado (revisar
    `/gastos/habituales` → rojo, `/departamentos/:id/cuenta` → teal).
