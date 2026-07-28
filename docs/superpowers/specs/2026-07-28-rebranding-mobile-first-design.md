# Rebranding visual mobile-first

Fecha: 2026-07-28
Estado: aprobado, pendiente de plan de implementación

## Contexto

La app tiene hoy el design system "Aire" + paleta Command (`frontend/src/index.css`, ~2075 líneas,
~130 clases consumidas por 41 pantallas y 24 componentes). La navegación es un sidebar que en
mobile se abre como drawer desde un botón hamburguesa, y los modales son un `<Modal>` centrado.

En `rediseño mobile first/COMAND Consorcios Móvil.dc.html` hay un mockup mobile-first que propone
otra identidad: paleta crema, tipografías Montserrat + Plus Jakarta Sans, header coloreado según
el módulo activo, tab bar inferior, bottom sheets y una pantalla "Inicio" de administración que
hoy no existe.

## Alcance

**Adentro:** cambio de tokens (paleta, tipografías, radios), lenguaje visual del mockup aplicado a
las clases existentes, shell nuevo (header con color por módulo, tab bar en mobile, bottom sheets)
y la pantalla Inicio de admin.

**Afuera:** reescribir el contenido y la estructura interna de las pantallas existentes. Conservan
su markup y su lógica; se reskinean vía las clases compartidas. Tampoco hay cambios de backend.

## Decisiones tomadas

1. **Reskin + shell nuevo**, no reescritura de pantallas.
2. **Tab bar solo en mobile (<960px); desktop conserva el sidebar** reskineado. Lo que no entra en
   la tab bar vive en una tab "Más" que abre una sheet.
3. **La pantalla Inicio se construye**, con datos de endpoints existentes únicamente.
4. **"Próximos vencimientos" se limita a lo derivable.** Sin cambios de modelo.
5. **La densidad depende del breakpoint:** en mobile manda el mockup; desde 600px manda la
   preferencia previa del usuario (ghost, ancho a contenido). Al subir de breakpoint el contenido
   se reorganiza en columnas — nunca se estira el mismo contenedor a todo el ancho.
6. **Marca COMMAND** en el header, usando el PNG del mockup aplanado a blanco.

## Diseño

### 1. Tokens — `frontend/src/index.css` y `frontend/index.html`

Se reemplazan los valores manteniendo **los mismos nombres de variable**, para que las clases
existentes se reskineen sin tocarlas.

| Variable | Antes | Ahora |
|---|---|---|
| `--color-bg` | `#faf9f6` | `#F4F0E6` |
| `--color-surface` | `#ffffff` | `#ffffff` |
| `--color-text` | `#1c1917` | `#121212` |
| `--color-text-muted` | `#78716c` | `#757168` |
| `--color-border` | `#eceae4` | `#E3DED2` |
| `--color-border-strong` | `#e5e2da` | `#D6D0C4` |
| `--color-primary` | `#3460a8` | `#2C6473` |
| `--color-primary-soft` | `#e9eff8` | `#E7F0F3` |
| `--color-success` / `-bg` | `#24734c` / `#e7f4ec` | `#2D8F5E` / `#E3EFE7` |
| `--color-danger` / `-bg` | `#c0443c` / `#f9e9e8` | `#C0443C` / `#F7E0DE` |
| `--color-warning` / `-bg` | `#8a6d1a` / `#fdf3d7` | `#8A6D1C` / `#F7EFD4` |

Agregados:

- **Colores por módulo:** `--color-mod-inicio: #1B3A4B`, `--color-mod-cobranzas: #305D4A`,
  `--color-mod-gastos: #C0443C`, `--color-mod-finanzas: #8A6D1C`, `--color-mod-expensas: #2C6473`,
  `--color-mod-operacion: #5B36B8`. Las pantallas que el mockup no dibuja (Padrón, Configuración,
  Reportes, Personal, Consorcios, super-admin) usan `--color-mod-inicio` como color por defecto:
  el `:root` define `--color-modulo: var(--color-mod-inicio)` y cada `[data-modulo="..."]` lo
  pisa. Así una ruta nueva nunca queda sin color.
- **Radios:** `--radius-sm: 12px` (botones, inputs), `--radius: 16px` (cards),
  `--radius-lg: 20px` (hero), `--radius-pill: 999px`.
- **Tipografías:** `--font-display: "Montserrat"` (títulos y cifras, peso 800) y
  `--font-sans: "Plus Jakarta Sans"`. En `index.html` se cambia el `<link>` de Google Fonts de
  Inter a `Montserrat:wght@600;700;800;900` + `Plus+Jakarta+Sans:wght@400;500;600;700;800`.

**Regla de no-hardcodeo.** `.claude/rules/frontend.md` prohíbe hex en componentes. El color de
módulo se resuelve por atributo, no por estilo inline:

```css
[data-modulo="cobranzas"] { --color-modulo: var(--color-mod-cobranzas); }
```

El JSX solo escribe `data-modulo={modulo}`; el CSS hace el resto.

### 2. Lenguaje visual

Se aplica a las clases que ya existen (`.tarjeta`, `.badge`, `.lista-*`, `.seccion-header`, `.tabs`):

- Regla de sección: `border-top: 2px solid var(--color-text)` con micro-label encima
  (10px, peso 800, `letter-spacing: 0.2em`, uppercase, color muted).
- Filas hairline separadas por `1px solid var(--color-border)`, sin fondo propio.
- Cards blancas con borde `--color-border` y radio `--radius`.
- Badges pill con punto de color del mismo tono que el texto.
- `font-variant-numeric: tabular-nums` en todo lo monetario.

**Botones (responsive).** Base mobile con el tratamiento del mockup: `width: 100%` o `flex: 1`,
`min-height: 44px`, uppercase, peso 800, `letter-spacing: 0.08em`, sombra de color en primarios.
En `@media (min-width: 600px)`: `width: fit-content`, 36px de alto, ghost para secundarios, sin
uppercase ni sombra.

### 3. Bottom sheets

`Modal.jsx` es un componente único compartido por 16 archivos, así que el cambio es **solo CSS**:

- `.modal-backdrop`: `align-items: flex-end`.
- `.modal`: `border-radius: 24px 24px 0 0`, `max-height: 88%`, `animation: sheetIn 0.3s
  cubic-bezier(0.16,1,0.3,1)`, grab handle vía `::before`.
- Desde `600px`: vuelve a modal centrado con `max-width`, como hoy.

No se toca el JSX de ninguno de los 16 archivos.

### 4. `navegacion.js` — fuente única de rutas

Se extrae el array `SECCIONES` de `Sidebar.jsx` a `frontend/src/navegacion.js`, junto con la
lógica de filtrado (roles permitidos, `modulos_habilitados`, flag `usa_personal_propio`, y
`reportes_visibles_a_depto`). Lo consumen `Sidebar.jsx`, `TabBar.jsx` y la sheet "Más", para que
no haya dos listas de rutas que mantener en sincronía.

### 5. Header

En `AppLayout.jsx`: fondo `var(--color-modulo)` con `transition: background 0.35s ease`, derivado
del `pathname` actual. Contiene el logo COMMAND en blanco
(`filter: brightness(0) invert(1)`, copiado a `frontend/public/logo-comand.png`), el label del
módulo activo, y un avatar circular con la inicial del usuario que abre una sheet de cuenta
(usuario y rol, cambiar contraseña, cerrar sesión). La hamburguesa se elimina en mobile.

Distribución de los componentes que ya viven en el header: en mobile, `Campanita` queda en la
barra junto al avatar, y `SelectorConsorcio` se mueve adentro de la sheet de cuenta — no entra en
una barra de 375px junto al logo y el label de módulo. Desde 960px ambos vuelven a la barra, como
hoy.

### 6. `TabBar.jsx`

Componente nuevo, `position: fixed; bottom: 0`, visible solo `<960px`. `padding-bottom:
calc(10px + env(safe-area-inset-bottom))`. Cada tab tiene ≥48px de alto, ícono SVG y label de 9px.
El tab activo toma el color de su módulo; los inactivos van en `#9B968A`.

| Rol | Tabs |
|---|---|
| `administracion` | Inicio · Cobranzas · Gastos · Finanzas · Operación · Más |
| `departamento` | Mi cuenta · Peticiones · Reservas · Comunicados · Más |
| `representante` | Comunicados · Peticiones · Trabajos · Más |
| `super_admin` | sin tab bar — conserva su drawer actual |

Admin no necesita tab de Expensas: `/expensas` ya redirige a `/cobranzas?tab=expensas`.

La tab "Más" abre una sheet con las secciones restantes (Reportes, Personal, Configuración,
Padrón, Consorcios), filtradas por `navegacion.js`.

Como la tab bar es `fixed`, `.app-content` necesita `padding-bottom` suficiente en mobile para que
el último elemento no quede tapado. Y `.cta-sticky`, que hoy se ancla al pie, pasa a anclarse
**por encima** de la tab bar (`bottom: calc(altura-tabbar + safe-area)`), no debajo ni tapándola.
Ambas medidas salen de una variable `--altura-tabbar` para que no queden números sueltos.

### 7. `screens/Inicio.jsx`

Ruta `/`, con reruteo por rol: admin → `Inicio`, departamento → `/mi-cuenta`,
representante → `/comunicados`. Reemplaza el `<Navigate to="/comunicados">` actual de `App.jsx`.

Todos los bloques salen de endpoints existentes:

| Bloque | Fuente |
|---|---|
| Saludo con fecha larga y consorcio | `AuthContext` + consorcio activo |
| Hero recaudación: liquidado, cobrado con %, pendiente, gastos | `Σ monto_primer_vencimiento` y `Σ monto_pendiente` de `GET /expensas?periodo=`; `total_general` de `GET /reportes/gastos/{periodo}` |
| Acciones rápidas | links a `/cobranzas` y `/gastos` |
| Requiere tu atención | `GET /reportes/morosos` filtrando por `primer_vencimiento_impago` > 60 días; `GET /peticiones` con estado `abierta`; `GET /periodos/{p}/estado` para el cierre pendiente |
| Actividad reciente (6 ítems) | merge por fecha desc de `ultimos_movimientos` (`GET /estado-financiero`), `GET /peticiones` y `GET /reservas` (con `GET /amenities` para resolver el nombre, porque `ReservaOut` solo trae `amenity_id`) |
| Próximos vencimientos | `fecha_primer_vencimiento` y `fecha_segundo_vencimiento` de `ExpensaOut`; más "sin cargar este mes" = `GET /gastos-habituales` activas menos los `GET /gastos?periodo=` que ya tienen `gasto_habitual_id` |

Cada ítem enlaza a su pantalla. **Un bloque sin datos se oculta entero**, no muestra ceros.

**Excluido deliberadamente:** el ítem "Trabajo X vence el viernes" del mockup — `Trabajo` no tiene
campo de fecha de vencimiento en `models.py`. Y los vencimientos de sueldos y de gastos habituales
van sin fecha, porque `GastoHabitual` no tiene día del mes y las liquidaciones no tienen
vencimiento.

## Verificación

El proyecto no tiene tests de frontend (`package.json` solo define `dev`, `build`, `lint`,
`preview`). La verificación es:

1. `npm run build` sin errores.
2. `npm run lint` sin errores nuevos.
3. Revisión manual a 375px de: Inicio, Cobranzas, Gastos, Tesorería y Mi cuenta.
4. Chequeo de contraste en badges y tablas, que es donde el cambio de tokens puede degradar
   legibilidad sin avisar.

## Riesgos

- **El cambio de tokens toca las 41 pantallas a la vez.** Algo puntual puede quedar con bajo
  contraste o con un color que ya no pega. Se mitiga con el paso 4 de verificación.
- **La tab bar `fixed` puede tapar contenido** en pantallas con CTA al pie. Resuelto en la sección
  6 vía `--altura-tabbar`, pero es lo primero a revisar en el paso 3 de verificación.
- **`navegacion.js` es un refactor de `Sidebar.jsx`**, que hoy funciona. Hay que preservar el
  filtrado por módulos habilitados y el flag de personal propio tal cual están.

## Orden de implementación

1. Tokens (`index.css` `:root` + `index.html`).
2. Lenguaje visual sobre las clases existentes, con botones responsive.
3. Bottom sheets (CSS de `.modal`).
4. `navegacion.js` extraído de `Sidebar.jsx`.
5. Header con color por módulo, logo y sheet de cuenta.
6. `TabBar.jsx` + sheet "Más".
7. `Inicio.jsx` + reruteo de `/`.
8. Verificación.
