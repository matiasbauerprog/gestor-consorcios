// Anchos fijos para columnas de fecha/monto de TablaResponsive.
//
// Se calculan UNA vez acá y las pantallas los importan, en vez de que cada
// `columnas.push({ ancho: "..." })` repita (o adivine de nuevo) la misma
// cuenta. El error que motivó este archivo: varias pantallas declaraban
// `ancho: "12ch"` para fechas y `"14ch"` o `"15ch"` para montos sin este
// cálculo, y el texto truncaba con ellipsis — inaceptable en una fecha o
// un importe, a diferencia de una etiqueta larga.
//
// Por qué no alcanza con "más o menos el largo del texto":
//
//   1. `table-layout: fixed` + `box-sizing: border-box` (global, `* {
//      box-sizing: border-box }`) hacen que `ancho` fije el BORDE EXTERIOR
//      de la columna: el padding horizontal de la celda sale de ese ancho
//      antes de dibujar una sola letra. `.tabla-datos tbody td` tiene
//      `padding: 0.6rem 0.75rem` → 0.75rem × 2 = 1.5rem = 24px de padding
//      horizontal por celda (root 16px).
//
//   2. Todo `<td>` de la app hereda `font-weight: 700` de la regla
//      genérica `td { font-weight: 700; ... }` (index.css, cerca de la
//      línea 315) — `.tabla-datos tbody td` no la pisa, así que el texto
//      de estas columnas es SIEMPRE negrita, no el peso normal que se ve
//      a simple vista en el editor.
//
//   3. La tabla usa `font-size: 0.8125rem` (13px). A ese tamaño y peso, en
//      Plus Jakarta Sans, un carácter mide en promedio ≈8.2px de ancho
//      (medido en el fix previo de la columna Estado de Peticiones,
//      commit 93802e9). Contar "N caracteres = Nch" subestima por partida
//      doble: ignora el padding Y el peso negrita.
//
//   4. La unidad `ch` de un `<col>` se resuelve contra la fuente COMPUTADA
//      de ese `<col>` — que hereda el mismo 13px/peso 700 de la celda. El
//      glyph "0" mide ahí ≈9.52px, NO los ≈7.15px que mide en peso normal.
//      Ver `PX_POR_CH` abajo: durante mucho tiempo esta cuenta dividió por
//      7.15 y todas las columnas salieron un 33% más anchas de lo previsto.
//
// Fórmula (igual a la de Peticiones, generalizada): para un string de L
// caracteres, contenido_px = L × 8.2, + 20% de colchón real (no rozar el
// límite), + 24px de padding, / PX_POR_CH = ancho en ch. Redondeado
// para arriba a un número prolijo, con el margen final (contenido
// disponible ÷ contenido crudo) documentado al lado de cada constante para
// que quede claro que no es un número tirado.

/** Ancho real de 1`ch` en las celdas de `.tabla-datos`: el glyph "0" de Plus
 *  Jakarta Sans a 13px en **peso 700**, que es el peso que TODO `<td>` de la
 *  app hereda (punto 2 de arriba). Medido en el browser sobre `/cobranzas`:
 *  una columna declarada en 34ch renderizaba 324px → 324/34 = 9.53.
 *
 *  Este número es la corrección del bug que motivó `anchosColumnas.test.js`:
 *  la versión anterior de este archivo calculaba el contenido en peso 700
 *  (8.2px por carácter, correcto) pero dividía por 7.15 — el "0" en peso
 *  NORMAL. Cada constante salía 9.52/7.15 ≈ 1.33× más ancha de lo que su
 *  propio comentario declaraba. No truncaba nada: sobraba tanto en cada
 *  columna que, en `/cobranzas` con las dos columnas de vencimiento visibles
 *  (contenedor ≥1000px), las columnas fijas sumaban los 1168px enteros del
 *  contenedor y `departamento` — la única en `auto`, y la que dice a QUÉ
 *  UNIDAD pertenece la expensa — se quedaba en 0px, con la página
 *  desbordando 182px a 1280 y 22px a 1440.
 *
 *  Si alguna vez cambia el `font-size` o el `font-weight` de
 *  `.tabla-datos tbody td`, este número se vuelve a MEDIR en el browser
 *  (`getComputedStyle` no lo da: hay que renderizar un `width: 10ch` dentro
 *  de la tabla y dividir por 10) y se re-derivan las siete constantes de
 *  abajo — no se ajusta a ojo. */
export const PX_POR_CH = 9.52;

/** Fecha completa `DD/MM/YYYY` (`formatFecha`, 10 caracteres, p. ej.
 *  "13/08/2026"): (10×8.2×1.2 + 24) / 9.52 ≈ 12.9 → 13ch.
 *  Margen final: 13ch deja (13×9.52 − 24) ≈ 99.8px disponibles vs. 82px de
 *  contenido crudo → ~22% de colchón real. */
export const ANCHO_FECHA = "13ch";

/** Fecha corta `DD/MM/YY` (`formatFechaCorta`, "para tablas densas" según
 *  utils/fechas.js — 8 caracteres, p. ej. "13/08/26"):
 *  (8×8.2×1.2 + 24) / 9.52 ≈ 10.8 → 11ch.
 *  Margen final: 11ch deja ≈80.7px vs. 65.6px crudos → ~23%.
 *  Usar donde varias columnas compiten en prioridad 1 y el año completo no
 *  agrega información real (movimientos recientes del mismo consorcio). */
export const ANCHO_FECHA_CORTA = "11ch";

/** Monto sin centavos (0 decimales — `formatearMonto`, `fmtMoney` locales),
 *  peor caso con signo y 9 DÍGITOS SIGNIFICATIVOS: "-$ 123.456.789" (14
 *  caracteres): (14×8.2×1.2 + 24) / 9.52 ≈ 17.0 → 17ch.
 *  Margen final: 17ch deja ≈137.8px vs. 114.8px crudos → ~20%.
 *
 *  El techo de 9 dígitos es una DECISIÓN sobre la magnitud de la moneda, no
 *  una medición de ningún dato real — nada en `backend/models.py` acota
 *  `Caja.saldo_actual` / `saldo_inicial` / `saldo_total` (son floats sin
 *  límite). La app es argentina, los montos son en pesos, y en una moneda
 *  con inflación una tesorería de consorcio o un gasto edilicio agregado
 *  llega a 8 dígitos de rutina y a 9 dentro de la vida útil del software.
 *  Un monto truncado es exactamente el modo de falla que todo este ejercicio
 *  de anchos existe para evitar, y es peor que una etiqueta cortada: "$
 *  12.345.6…" se lee como un número más chico, no como un error. Que este
 *  número se vea generoso es intencional — no "optimizarlo" de nuevo para
 *  abajo sin repetir esta cuenta con un techo de dígitos más alto.
 *
 *  Se usa el mismo ancho exista o no un caso negativo real en cada pantalla
 *  puntual — un solo número conservador para las siete pantallas que lo
 *  consumen, en vez de auditar el signo columna por columna. */
export const ANCHO_MONTO = "17ch";

/** Monto con centavos (CuentasCorrientes: `Number.toLocaleString` sin
 *  `maximumFractionDigits`, que en es-AR deja 2 decimales), mismo techo de
 *  9 dígitos significativos (ver `ANCHO_MONTO` — decisión de magnitud, no
 *  medición) con signo: "-$ 123.456.789,99" (17 caracteres):
 *  (17×8.2×1.2 + 24) / 9.52 ≈ 20.1 → 21ch.
 *  Margen final: 21ch deja ≈175.9px vs. 139.4px crudos → ~26%.
 *  El signo no es hipotético acá: el estado "a favor" de una cuenta
 *  corriente es justamente `saldo_total < 0`. */
export const ANCHO_MONTO_DECIMAL = "21ch";

/** Período `"YYYY-MM"` (p. ej. "2026-08", 7 caracteres) — string de formato
 *  fijo que NO pasa por `formatFecha`/`formatFechaCorta` (es una clave de
 *  mes, no una fecha formateada), pero aparece en más de una pantalla
 *  (Expensas, Periodos) con el mismo argumento que ya justificó
 *  `ANCHO_FECHA`: un solo ancho calculado una vez en vez de repetido (o
 *  subestimado) por pantalla.
 *  (7×8.2×1.2 + 24) / 9.52 ≈ 9.8 → 10ch.
 *  Margen final: 10ch deja ≈71.2px vs. 57.4px crudos → ~24%. */
export const ANCHO_PERIODO = "10ch";

/** Fecha + monto compuestos en una sola celda (`` `${formatFecha(...)} ·
 *  ${formatearMonto(...)}` ``, patrón usado por `Expensas.jsx` en las
 *  columnas `venc1`/`venc2` — "1° venc"/"2° venc" muestran fecha e importe
 *  del vencimiento juntos, no en columnas separadas). Estas dos columnas
 *  quedaron en `auto` cuando se migró la pantalla mientras que TODA otra
 *  fecha y TODO otro monto de esta rama recibió un ancho calculado — el
 *  mismo error que motivó este archivo, aplicado a un caso compuesto en vez
 *  de a una fecha o un monto sueltos.
 *
 *  A DIFERENCIA de todas las demás constantes de este archivo, esta usa el
 *  caso TÍPICO, no el peor caso conjunto — decisión deliberada, no un
 *  descuido, y específica a `venc1`/`venc2`: en `Expensas.jsx` esas dos
 *  columnas son contexto ("¿cuándo y cuánto vencía?"), no el número que el
 *  usuario vino a buscar en esa pantalla — ese es `pendiente` (el saldo
 *  pendiente actual), que tiene su propio `ANCHO_MONTO` sin recortar. Con
 *  dos columnas fecha+monto en la misma fila (`periodo`, `depto`, `venc1`,
 *  `venc2`, `estado`, `pendiente`, `acciones`), dimensionarlas al peor caso
 *  conjunto (signo + 9 dígitos en las dos a la vez, L=27) le come a `depto`
 *  — prioridad 1, la columna que identifica a QUÉ UNIDAD pertenece la
 *  expensa — el poco margen que le queda en un viewport de 1280px
 *  (contenedor 1002px), un desenlace peor que el truncado que este archivo
 *  entero existe para evitar.
 *
 *  Nota histórica: dos intentos previos atacaron ese hundimiento de `depto`
 *  bajando ESTE número (41ch → 34ch). No alcanzaron porque la causa no era
 *  el número sino el divisor de la fórmula: con 7.15 en vez de 9.52, 34ch
 *  rendía 324px en pantalla — el 33% de más que dejaba a `depto` en 0px.
 *  Corregido `PX_POR_CH`, el presupuesto de la fila cierra con holgura y lo
 *  cubre un test (`anchosColumnas.test.js`, "presupuesto de la fila de
 *  Expensas"). Si `depto` vuelve a apretarse, revisar primero ese test
 *  antes de tocar este número de nuevo.
 *
 *  L = 10 (`formatFecha`, `DD/MM/YYYY`) + 3 (` · `, espacio-punto medio-
 *  espacio) + 9 (`formatearMonto` caso típico, p. ej. "$ 145.300" — NO el
 *  peor caso con signo y 9 dígitos de `ANCHO_MONTO`) = 22 caracteres.
 *  (22×8.2×1.2 + 24) / 9.52 ≈ 25.3 → 26ch.
 *  Margen final: 26ch deja ≈223.5px vs. 216.48px crudos (sin el 20% de
 *  colchón que ya incluye la fórmula) → colchón real ~3.2%, chico a
 *  propósito por la misma razón que documentaba la versión anterior de
 *  este comentario: fecha y monto rara vez tocan sus propios peores casos
 *  a la vez en la misma fila, así que el margen de la fórmula ya alcanza.
 *  Un vencimiento con signo negativo o 8-9 dígitos truncará con ellipsis
 *  en estas dos columnas — aceptable, es contexto, no el monto que importa
 *  en esta pantalla. Si un futuro cambio necesita que `venc1`/`venc2`
 *  nunca trunquen, la solución correcta es separar fecha y monto en dos
 *  columnas (cada una con su propio `ANCHO_FECHA`/`ANCHO_MONTO` de peor
 *  caso), no volver a subir este número — eso es lo que vuelve a hundir a
 *  `depto`. */
export const ANCHO_FECHA_MONTO = "26ch";

/** CUIT/CUIL `"XX-XXXXXXXX-X"` (p. ej. "30-12345678-9", 13 caracteres) —
 *  igual que `ANCHO_PERIODO`, un string de formato FIJO (regex
 *  `^\d{2}-\d{8}-\d{1}$` en `backend/schemas.py`, columna `String(13)` en
 *  `backend/models.py`: `Proveedor.cuit`, `AdministracionGlobal.cuit`,
 *  `Consorcio.cuit`, `Administracion.cuit`), no un texto libre — el mismo
 *  argumento que ya justificó centralizar fecha/monto/período: nunca varía
 *  de largo, así que un solo ancho calculado acá evita que cada pantalla
 *  (Proveedores, y cualquier futura tabla de Empleados/CUIL o
 *  Administraciones) lo adivine de nuevo o lo subestime.
 *  (13×8.2×1.2 + 24) / 9.52 ≈ 16.0 → 16ch.
 *  Margen final: 16ch deja ≈128.3px vs. 106.6px crudos → ~20%. */
export const ANCHO_CUIT = "16ch";
