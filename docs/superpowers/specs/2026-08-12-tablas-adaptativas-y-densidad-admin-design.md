# Tablas adaptativas y densidad en administración

Fecha: 2026-08-12

## Problema

Revisión de la app en uso. Todo lo que sigue es frontend; el backend no se toca.

1. **Las tablas no se adaptan.** En Cobranzas la tabla entra justo en un desktop
   grande y a partir de ahí solo hay scroll horizontal. Al scrollear, el header
   se despega del cuerpo. Es un problema del sistema de tablas, no de una
   pantalla: Gastos, Tesorería, Cuentas Corrientes y Comprobantes lo tienen
   igual, y solo se nota menos donde hay menos columnas.
2. **Peticiones en mobile** muestra tabla en vez de tarjetas y no entra por poco.
3. **Pantallas que siguen siendo tarjetas en desktop** cuando su contenido ya es
   tabular: Gastos recurrentes, Amenities, Clases de prorrateo y Proveedores.
4. **El filtro de período en Gastos** corta el texto ("agosto de 202…") y el
   indicador verde de estado desentona con las flechas de navegación.
5. **La campanita** es un emoji del sistema operativo.

Continúa el trabajo de [2026-08-04](2026-08-04-densidad-desktop-y-pendiente-fehaciente-design.md),
que introdujo `ListaResponsive` y convirtió cuatro pantallas a tabla en ≥600px.
Ese spec resolvió la densidad en desktop grande; este resuelve el rango
intermedio y termina de convertir las pantallas que quedaron en tarjetas.

## Fuera de alcance

- **Vista de inquilino/propietario en desktop.** Entra completa en el rediseño
  del hub "Mi cuenta" ([2026-07-04](2026-07-04-hub-mi-cuenta-design.md)), que
  sigue pendiente. Decidido con el usuario para no tocar dos veces las mismas
  pantallas ni meter un rediseño a medias adentro de otro.
- **Tablas de Reportes, Padrón, Liquidaciones y matriz de Coeficientes.** No
  fueron reportadas y varias no son listas homogéneas — la matriz de
  coeficientes es una grilla de edición, no una lista. Igual heredan gratis el
  arreglo global del `<thead>` (bloque 1.4).

---

## 1. Motor de tablas

### 1.1 Diagnóstico

Tres causas independientes, todas en `frontend/src/index.css`:

| Causa | Dónde | Efecto |
|---|---|---|
| `min-width: max-content` en `.tabla-datos` | `index.css:2810` | La tabla nunca se comprime: exige el ancho de su contenido más largo. Por debajo de eso, scroll horizontal obligado. |
| `white-space: nowrap` en `.tabla-datos thead th` | `index.css:2824` | Sube el piso de ese `max-content`: ningún título de columna puede envolver. |
| `display: block; overflow-x: auto` en el selector global `table` | `index.css:279-281` | Convierte la tabla en bloque y le da su propio scroll. `thead` y `tbody` dejan de compartir el mismo contexto de layout y se desalinean al scrollear — es el "header roto". |

El comentario en `index.css:2803-2809` explica que `min-width: max-content` se
puso para que el wrapper llegara a disparar su barra de scroll. Era el parche
correcto para el modelo viejo (tabla que no se achica → hay que poder
scrollearla). Este spec cambia el modelo, así que el parche se va con él.

### 1.2 `TablaResponsive`

`components/ListaResponsive.jsx` (53 líneas, 4 consumidores) evoluciona a
`components/TablaResponsive.jsx`. Se renombra porque la responsabilidad cambia:
antes elegía entre dos densidades, ahora administra un modelo de columnas.

Cada columna gana dos campos, ambos opcionales con default:

```js
{
  clave: "proveedor",
  titulo: "Proveedor",
  celda: (fila) => …,
  prioridad: 2,      // 1 = nunca se oculta (default) · 2 · 3 = se va primero
  ancho: "auto",     // auto o % para texto, ch para montos y fechas (default "auto")
  className: "col-monto",
}
```

**Nada de `fr`.** Es una unidad de grid: en un `<col>` el navegador la descarta
en silencio. Bajo `table-layout: fixed`, las columnas en `auto` se reparten en
partes iguales lo que sobra después de las de ancho fijo — que es exactamente el
reparto proporcional que se busca.

El componente renderiza un `<colgroup>` con los anchos declarados y
`table-layout: fixed` en la tabla. Ahí está la inversión: las columnas se
reparten el ancho disponible en proporción en vez de exigir el que su contenido
necesita. El texto que no entra se corta con `text-overflow: ellipsis` y el valor
completo queda en el `title` de la celda.

`ListaResponsive` no se mantiene como alias. Los cuatro consumidores actuales
(`Expensas`, `Comprobantes`, `Gastos`, `Reservas`) se migran en el mismo cambio;
dejar dos componentes que hacen casi lo mismo es exactamente cómo se llega a
tener tres sistemas de tablas.

### 1.3 Escalones y fila de detalle

El wrapper declara `container-type: inline-size`. Las columnas se ocultan por
`@container`, no por `@media`: la tabla mide el ancho que le tocó a ella, no el
del viewport. Con el sidebar de 230px (`index.css:2055`) el viewport miente por
un margen fijo en admin y por nada en la vista depto, así que un corte por
viewport necesitaría dos calibraciones distintas para la misma tabla.

| Ancho del contenedor | Se ve |
|---|---|
| ≥ 600px | Prioridad 1 |
| ≥ 720px | + prioridad 2 |
| ≥ 1000px | Todo |

**Corrección post-revisión (2026-08-13): el umbral de prioridad 2 bajó de 760
a 720.** El contenedor no es el viewport: es viewport menos sidebar (230px,
solo desde 960px) menos el padding horizontal de `.app-content`, que cambia
en dos breakpoints propios (`index.css`, reglas `.app-content`): 1rem por
lado bajo 600px (32px totales), 1.5rem por lado desde 600px (48px totales,
tanto en el rango 600–959px como en ≥960px). Un viewport de 768px — la
tablet portrait que motivó todo este trabajo — da un contenedor real de
768 − 48 = **720px**, 40px por debajo del umbral viejo de 760: la tablet
caía al escalón mínimo (solo prioridad 1) por un accidente de aritmética,
no por una decisión de diseño. 720 (con `>=` inclusive) le devuelve su
escalón intermedio. El detalle completo, incluyendo la cuenta para 375,
1024 y 1440px, vive en el docblock de `prioridadVisible` en
`TablaResponsive.jsx` — actualizar ahí primero si este número vuelve a
moverse.

**El corte tarjetas ↔ tabla es la excepción y sigue siendo por viewport.** Lo
resuelve `useEsTablet` (`hooks/useBreakpoint.js:24`, `min-width: 600px`) en JS,
no `@container`, porque tarjetas y tabla son dos árboles de DOM distintos:
renderizar los dos y ocultar uno por CSS duplicaría el contenido para los
lectores de pantalla. La razón está documentada en `ListaResponsive.jsx:5-6` y se
mantiene tal cual. Los escalones de la tabla de arriba aplican una vez que el
árbol de tabla ya se eligió.

**El mecanismo de ocultamiento (corregido durante la implementación,
2026-08-13).** El diseño original ocultaba las columnas con `display: none` bajo
`@container`, sin JavaScript: la misma condición leída en dos direcciones,
imposible de desfasar. **No funciona**, y la razón es estructural, no un detalle
de implementación.

Una celda en `display: none` no genera caja y por lo tanto no ocupa lugar en la
grilla de la tabla. Con `table-layout: fixed`, los anchos vienen del `<colgroup>`
**por posición**: si se oculta la 4ª columna, la 5ª cae en el slot 4 y hereda el
ancho de su vecina, la 6ª cae en el 5, y el último `<col>` queda declarando ancho
para una columna vacía. Los montos se renderizan con el ancho de otra columna y
sobra una franja muerta al costado. Y no ocurre solo en el escalón de 1000px:
pasa en cada escalón donde se oculte algo. Bajarle el ancho a 0 al `<col>` no lo
arregla — el defecto es posicional, no de ancho.

El reemplazo: **la tabla mide su contenedor con `ResizeObserver` y renderiza
únicamente las columnas que entran.** Lo que el usuario ve es idéntico. Lo que
cambia es que las columnas descartadas no se dibujan nunca, así que no hay
celdas ocultas, no hay corrimiento posicional, el `<colgroup>` siempre coincide
con las celdas presentes, y el `colSpan` de la fila de detalle siempre iguala la
cantidad real de columnas visibles.

El costo es el JavaScript de medición que el diseño original quería evitar. A
cambio desaparece una familia entera de errores de alineación que la versión CSS
no podía evitar sin apilar hacks (`visibility: collapse` en `<col>`, soporte
despareja entre motores; o `font-size: 0` para que una celda de ancho cero no
estire la fila).

**La fila de detalle** sigue igual: cada fila renderiza una segunda
`<tr class="fila-detalle">` con un `<td colSpan>` que lista como pares
etiqueta/valor exactamente las columnas que quedaron afuera en el ancho actual.

El chevron vive en una columna propia al inicio, y **no se renderiza** en los
anchos donde no quedó ninguna columna afuera — no se oculta por CSS, no existe.
Es un `<button>` con `aria-expanded` y `aria-controls` apuntando al `id` de su
fila de detalle.

Estado: un `Set` de ids expandidos en `useState` dentro del componente. Hoy no se
resetea al cambiar el conjunto de filas; una clave huérfana no es observable
(sin fila que la use, no se renderiza nada), así que queda como deuda anotada y
no como bug.

Sin costo de DOM duplicado: en la fila de detalle vive exactamente lo que no está
en la tabla, nunca las dos cosas a la vez. El diseño viejo sí duplicaba —
renderizaba toda columna de prioridad 2-3 arriba y abajo en todos los anchos, y
escondía una de las dos copias con `display: none`.

### 1.4 Fix global del `<thead>`

Se borra `display: block; overflow-x: auto; overflow-y: hidden` del selector
global `table` (`index.css:279-281`). Sin scroll horizontal ya no hace falta, y
es la causa directa del header desalineado.

Con la tabla de vuelta en su modo de layout nativo, `thead th` pasa a
`position: sticky; top: 0` con fondo opaco. En listas largas el encabezado queda
fijo al scrollear vertical.

Este cambio alcanza a las 15 pantallas que escriben `<table>` a mano, incluidas
las que están fuera de alcance. Es el único punto del spec con ese radio, y es
deliberado: la regla que se borra es un bug, no una decisión de diseño.

### 1.5 Menú de acciones

Las tablas de catálogo tienen tres acciones por fila (Editar / Desactivar /
Eliminar) que hoy son tres botones visibles. En una tabla se comen 200-250px de
ancho y dejan Eliminar a un click de Editar.

Se construye `components/MenuAcciones.jsx`: un `<button>` con `⋯` que despliega
una lista de acciones. **El estilo ya está escrito y completo** en
`index.css:1087-1152` (`.menu-kebab`, `-trigger`, `-lista`, `-item`,
`-item.peligro`, incluida la variante destructiva), pero ningún JSX lo consume.
Solo falta el componente.

Requisitos: cierre con `Escape` y con click afuera, foco devuelto al trigger al
cerrar, `aria-haspopup="menu"`, y las acciones destructivas con
`--color-danger`. En mobile no se usa: las tarjetas siguen con sus botones a la
vista, que es lo que corresponde a un target táctil.

### 1.6 Pantallas que migran

Ya usan el componente, solo declaran `prioridad` y `ancho`:

| Pantalla | Columnas |
|---|---|
| `Expensas.jsx:126` | Período, Departamento, 1° venc, 2° venc, Estado, Pendiente, acciones |
| `Comprobantes.jsx:183` | Fecha, Departamento, Monto, Estado, Comprobante, acciones |
| `Gastos.jsx:304` | Fecha, Concepto, Rubro, Proveedor, Clase, Monto, Pagado, acciones |
| `Reservas.jsx` | Amenity, Fecha, Horario, Estado |

Pasan de `<table>` a mano al componente:

| Pantalla | Hoy |
|---|---|
| `Periodos.jsx:37` | 6 columnas — la solapa "Historial de cierres" de Cobranzas |
| `Peticiones.jsx:121` | 5 columnas, **tabla también en mobile** → gana tarjetas |
| `CuentasCorrientes.jsx:87` | columnas dinámicas |
| `Cajas.jsx:50,76` | dos tablas (cajas y movimientos) |
| `Transferencias.jsx:36` | 5 columnas |
| `EstadoFinanciero.jsx:84` | 5 columnas |

Estas seis no tienen densidad de tarjeta hoy: muestran `<table>` en todos los
anchos. Migrarlas incluye **escribir su `renderTarjeta`**, que es trabajo nuevo,
no un movimiento de código. Es el motivo por el que Peticiones no entra entera en
375px: hoy no tiene tarjeta que mostrar.

Las prioridades concretas por columna se deciden en el plan de implementación,
pantalla por pantalla. El criterio: prioridad 1 es lo que identifica la fila
(fecha, código, nombre) más el número que la persona vino a ver (monto, estado);
prioridad 3 es lo que solo importa cuando ya encontraste la fila (descripción,
proveedor, clase).

---

## 2. Pantallas que pasan de tarjeta a tabla

Cuatro pantallas renderizan tarjetas en cualquier viewport. Las tres primeras
usan `.lista-config`, que apila una tarjeta a ancho completo por fila: seis
datos en la esquina izquierda y el resto vacío.

| Pantalla | Estado actual | Columnas de la tabla |
|---|---|---|
| `GastosHabituales.jsx:137` | tarjeta apilada, 6 datos verticales | Nombre, Monto, Rubro, Clase, Proveedor, Caja, Estado, ⋯ |
| `Amenities.jsx:51` | `.grid-fichas` con un `<dl>` de 5 políticas | Nombre, Precio, Duración máx, Anticipación máx, Máx activas, Cancelación, Estado, ⋯ |
| `ClasesProrrateo.jsx:58` | tarjeta apilada | Código, Nombre, Descripción, Estado, ⋯ |
| `Proveedores.jsx:66` | tarjeta apilada | Razón social, Nombre fantasía, CUIT, Dirección, Estado, ⋯ |

Las cuatro usan `TablaResponsive` con su `renderTarjeta`, así que en <600px
quedan exactamente como están hoy. `.lista-config` y `.grid-fichas` sobreviven
como estilo de las tarjetas en mobile.

Amenities es el caso más claro: su `<dl class="amenity-policies">`
(`Amenities.jsx:58-64`) ya es una tabla de dos columnas metida adentro de una
tarjeta. Comparar cinco políticas entre amenities hoy exige leer cinco tarjetas.

---

## 3. Barra de período en Gastos

### 3.1 Texto cortado

`index.css:1179` fija `width: 9.5rem` en el `input[type="month"]`. Chrome
renderiza "agosto de 2026" y no entra. Se reemplaza por
`width: auto; min-width: 9.5rem`: el campo mide lo que su contenido necesita y
el piso evita que cambie de tamaño entre meses de nombre corto y largo.

Esto también respeta la preferencia registrada de que los controles de filtro
midan según su contenido, no un ancho impuesto.

### 3.2 Contraste del indicador

`Gastos.jsx:242` y `:247` pintan el punto de estado con `#6b7280` y `#16a34a`
escritos inline. Son colores sueltos que no pertenecen a la paleta y violan la
regla de `.claude/rules/frontend.md` de consumir color siempre vía
`var(--color-...)`.

- Verde `#16a34a` → `var(--color-success)` (`#26784f`), más apagado y calibrado
  para convivir con los grises de la paleta.
- Gris `#6b7280` → `var(--color-text-muted)`.
- Los glifos `‹ ›` de `.periodo-nav` ya usan `--color-text-muted`
  (`index.css:1189`), pero el `font-size: 1rem` de `index.css:1188` los deja
  pesados al lado del indicador. Bajan a `0.875rem`. El hit area de 44px
  (`index.css:1195-1199`) no se toca: es accesibilidad táctil, no peso visual.

Los estilos inline se van; el estado queda expresado con una clase
(`estado-punto--abierto` / `--cerrado`).

---

## 4. Campanita

### 4.1 Diagnóstico

`components/Campanita.jsx:68` renderiza el emoji `🔔`. Un emoji es una fuente del
sistema operativo: se dibuja distinto en Windows, Mac y Android, tiene su propio
color amarillo/naranja fijo que ignora la paleta, y no se le puede ajustar el
trazo ni el tamaño óptico.

### 4.2 Diseño

Dirección elegida: **punto discreto**, el patrón de Linear y Notion.

- **Ícono:** SVG inline de campana en trazo, `stroke: currentColor`, 19px,
  `stroke-width: 1.8`. Toma el color de la paleta y se ve igual en todos lados.
- **Badge:** un punto de 8px en `var(--color-danger)` con borde del color de la
  superficie, arriba a la derecha. Sin número.

  `obtenerNoLeidasCount` (`api/notificaciones.js`) se sigue llamando igual: la
  UI ahora solo lee `count > 0`. No se toca el backend ni el endpoint. Que el
  contador exacto deje de mostrarse es decisión de UI, no de datos.
- **Botón:** 38px, radio `--radius-sm`, fondo transparente; `--color-primary-soft`
  cuando el panel está abierto.
- **Panel:** header con título y "Marcar todas" como link discreto. Cada ítem
  con un punto de no leída de 7px en `--color-primary`, mensaje en 0.78rem/600, y
  la fecha en tiempo relativo ("hace 12 min", "ayer") en vez del
  `toLocaleString("es-AR")` completo de `Campanita.jsx:98`. Las no leídas con un
  tinte suave de fondo, no un color fuerte.
- **`<li onClick>` (`Campanita.jsx:91-94`) pasa a `<button>`** dentro del `<li>`.
  Hoy no es alcanzable por teclado y la regla del proyecto prohíbe
  `<div onClick>` como control.
- **Mobile:** el panel deja de ser dropdown y sube como sheet, reusando el patrón
  de `SheetCuenta`.

El formateo relativo va a un helper propio en `utils/`, con tests: es lógica pura
de fechas, el tipo de código donde los off-by-one no se ven a simple vista.

---

## Riesgos

**`table-layout: fixed` corta contenido que hoy se ve entero.** Es el punto de
verificación real del spec. Mitigación: `title` con el valor completo en toda
celda con ellipsis, y anchos en `ch` (no en `auto`) para montos y fechas, que son
las columnas donde cortar sería inaceptable.

**Borrar la regla global de `table` toca 15 pantallas de una.** Incluidas las
que están fuera de alcance. Se verifican las 15 a 375px, 768px y 1440px antes de
dar el bloque por cerrado.

**~~`@container` no tiene fallback.~~** Obsoleto: el ocultamiento pasó a
`ResizeObserver` (ver 1.3). `ResizeObserver` es soporte universal desde 2020 y no
necesita fallback. `@container` sigue sin usarse para esto.

## Verificación

Cada bloque se valida en el browser antes de commitear, a **375px** (iPhone SE,
el ancho que el usuario revisa), **768px** (tablet — el rango que motivó el
spec), **1024px** y **1440px**.

Chequeos por ancho:

1. `document.documentElement.scrollWidth === clientWidth` en toda pantalla
   tocada — cero desborde horizontal.
2. El `<thead>` alineado con el `<tbody>` durante y después del scroll.
3. Ningún dato inalcanzable: lo que se oculta en la tabla aparece al expandir la
   fila.
4. El menú `⋯` navegable solo con teclado, y el foco de vuelta en el trigger al
   cerrar con `Escape`.
5. "agosto de 2026" entero en el filtro de período.

`pytest -v` sigue verde: no se toca backend.
