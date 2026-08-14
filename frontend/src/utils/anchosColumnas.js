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
//      commit 93802e9) — más que el `ch` teórico (el ancho del glyph "0"
//      normal, ≈7.15px a este tamaño/peso). Contar "N caracteres = Nch"
//      subestima por partida doble: ignora el padding Y el peso negrita.
//
// Fórmula (igual a la de Peticiones, generalizada): para un string de L
// caracteres, contenido_px = L × 8.2, + 20% de colchón real (no rozar el
// límite), + 24px de padding, / 7.15px por ch = ancho en ch. Redondeado
// para arriba a un número prolijo, con el margen final (contenido
// disponible ÷ contenido crudo) documentado al lado de cada constante para
// que quede claro que no es un número tirado.

/** Fecha completa `DD/MM/YYYY` (`formatFecha`, 10 caracteres, p. ej.
 *  "13/08/2026"): (10×8.2×1.2 + 24) / 7.15 ≈ 17.1 → 17ch.
 *  Margen final: 17ch deja (17×7.15 − 24) ≈ 97.6px disponibles vs. 82px de
 *  contenido crudo → ~19% de colchón real. */
export const ANCHO_FECHA = "17ch";

/** Fecha corta `DD/MM/YY` (`formatFechaCorta`, "para tablas densas" según
 *  utils/fechas.js — 8 caracteres, p. ej. "13/08/26"):
 *  (8×8.2×1.2 + 24) / 7.15 ≈ 14.4 → 14ch.
 *  Margen final: 14ch deja ≈76.1px vs. 65.6px crudos → ~16%.
 *  Usar donde varias columnas compiten en prioridad 1 y el año completo no
 *  agrega información real (movimientos recientes del mismo consorcio). */
export const ANCHO_FECHA_CORTA = "14ch";

/** Monto sin centavos (0 decimales — `formatearMonto`, `fmtMoney` locales),
 *  peor caso con signo y 9 DÍGITOS SIGNIFICATIVOS: "-$ 123.456.789" (14
 *  caracteres): (14×8.2×1.2 + 24) / 7.15 ≈ 22.6 → 23ch.
 *  Margen final: 23ch deja ≈140.4px vs. 114.8px crudos → ~22%.
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
export const ANCHO_MONTO = "23ch";

/** Monto con centavos (CuentasCorrientes: `Number.toLocaleString` sin
 *  `maximumFractionDigits`, que en es-AR deja 2 decimales), mismo techo de
 *  9 dígitos significativos (ver `ANCHO_MONTO` — decisión de magnitud, no
 *  medición) con signo: "-$ 123.456.789,99" (17 caracteres):
 *  (17×8.2×1.2 + 24) / 7.15 ≈ 26.7 → 27ch.
 *  Margen final: 27ch deja ≈169.1px vs. 139.4px crudos → ~21%.
 *  El signo no es hipotético acá: el estado "a favor" de una cuenta
 *  corriente es justamente `saldo_total < 0`. */
export const ANCHO_MONTO_DECIMAL = "27ch";

/** Período `"YYYY-MM"` (p. ej. "2026-08", 7 caracteres) — string de formato
 *  fijo que NO pasa por `formatFecha`/`formatFechaCorta` (es una clave de
 *  mes, no una fecha formateada), pero aparece en más de una pantalla
 *  (Expensas, Periodos) con el mismo argumento que ya justificó
 *  `ANCHO_FECHA`: un solo ancho calculado una vez en vez de repetido (o
 *  subestimado) por pantalla.
 *  (7×8.2×1.2 + 24) / 7.15 ≈ 13.0 → 13ch.
 *  Margen final: 13ch deja ≈68.9px vs. 57.4px crudos → ~20%. */
export const ANCHO_PERIODO = "13ch";

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
 *  descuido, y specífica a `venc1`/`venc2`: en `Expensas.jsx` esas dos
 *  columnas son contexto ("¿cuándo y cuánto vencía?"), no el número que el
 *  usuario vino a buscar en esa pantalla — ese es `pendiente` (el saldo
 *  pendiente actual), que tiene su propio `ANCHO_MONTO` sin recortar. Con
 *  dos columnas fecha+monto en la misma fila (`periodo`, `depto`, `venc1`,
 *  `venc2`, `estado`, `pendiente`, `acciones`), dimensionar `venc1`/`venc2`
 *  al peor caso conjunto (signo + 9 dígitos en las dos a la vez, L=27,
 *  41ch) deja tan poco margen en el contenedor que `depto` — prioridad 1,
 *  la columna que identifica a QUÉ UNIDAD pertenece la expensa — se cae a
 *  ~8px utilizables en un viewport de 1280px (contenedor 1002px), un
 *  desenlace peor que el truncado que este archivo entero existe para
 *  evitar. Sacrificar el último dígito de una columna de contexto para
 *  garantizarlo en las dos a la vez es el trade-off equivocado — el que
 *  este archivo en general evita para fecha/monto es distinto: ahí SÍ
 *  importa el peor caso porque esas columnas suelen ser las únicas de su
 *  tipo en la fila, no dos columnas compitiendo por el mismo contenedor
 *  contra una columna de prioridad 1.
 *
 *  L = 10 (`formatFecha`, `DD/MM/YYYY`) + 3 (` · `, espacio-punto medio-
 *  espacio) + 9 (`formatearMonto` caso típico, p. ej. "$ 145.300" — NO el
 *  peor caso con signo y 9 dígitos de `ANCHO_MONTO`) = 22 caracteres.
 *  (22×8.2×1.2 + 24) / 7.15 ≈ 33.6 → 34ch.
 *  Margen final: 34ch deja ≈219.9px vs. 216.48px crudos (sin el 20% de
 *  colchón que ya incluye la fórmula) → colchón real ~1.6%, chico a
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
export const ANCHO_FECHA_MONTO = "34ch";

/** CUIT/CUIL `"XX-XXXXXXXX-X"` (p. ej. "30-12345678-9", 13 caracteres) —
 *  igual que `ANCHO_PERIODO`, un string de formato FIJO (regex
 *  `^\d{2}-\d{8}-\d{1}$` en `backend/schemas.py`, columna `String(13)` en
 *  `backend/models.py`: `Proveedor.cuit`, `AdministracionGlobal.cuit`,
 *  `Consorcio.cuit`, `Administracion.cuit`), no un texto libre — el mismo
 *  argumento que ya justificó centralizar fecha/monto/período: nunca varía
 *  de largo, así que un solo ancho calculado acá evita que cada pantalla
 *  (Proveedores, y cualquier futura tabla de Empleados/CUIL o
 *  Administraciones) lo adivine de nuevo o lo subestime.
 *  (13×8.2×1.2 + 24) / 7.15 ≈ 21.2 → 22ch.
 *  Margen final: 22ch deja ≈133.3px vs. 106.6px crudos → ~25%. */
export const ANCHO_CUIT = "22ch";
