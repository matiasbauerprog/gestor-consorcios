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
 *  peor caso con signo y 7 dígitos: "-$ 1.234.567" (12 caracteres):
 *  (12×8.2×1.2 + 24) / 7.15 ≈ 19.9 → 20ch.
 *  Margen final: 20ch deja ≈119px vs. 98.4px crudos → ~21%.
 *  Se usa el mismo ancho exista o no un caso negativo real en cada
 *  pantalla puntual — un solo número conservador para las ocho pantallas
 *  que lo consumen, en vez de auditar el signo columna por columna. */
export const ANCHO_MONTO = "20ch";

/** Monto con centavos (CuentasCorrientes: `Number.toLocaleString` sin
 *  `maximumFractionDigits`, que en es-AR deja 2 decimales), peor caso con
 *  signo y 7 dígitos: "-$ 1.234.567,89" (15 caracteres):
 *  (15×8.2×1.2 + 24) / 7.15 ≈ 24.0 → 24ch.
 *  Margen final: 24ch deja ≈147.6px vs. 123px crudos → ~20%.
 *  El signo no es hipotético acá: el estado "a favor" de una cuenta
 *  corriente es justamente `saldo_total < 0`. */
export const ANCHO_MONTO_DECIMAL = "24ch";
