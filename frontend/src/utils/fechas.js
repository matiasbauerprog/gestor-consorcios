// Formateo de fechas en formato argentino (DD/MM/YYYY).
//
// Aceptan strings ISO ("2026-07-10", "2026-07-10T15:30:00") o Date.
// Devuelven "" si el valor es nulo/inválido — evita que la UI muestre "NaN/NaN".

/** DD/MM/YYYY */
export function formatFecha(v) {
  const d = _parse(v);
  if (!d) return "";
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** DD/MM/YYYY HH:MM */
export function formatFechaHora(v) {
  const d = _parse(v);
  if (!d) return "";
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Formato compacto DD/MM/YY para tablas densas. */
export function formatFechaCorta(v) {
  const d = _parse(v);
  if (!d) return "";
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

/**
 * Fecha del proyecto → `Date`, o `null` si no se puede.
 *
 * Exportada porque comparar fechas necesita el mismo criterio que mostrarlas:
 * quien compare con `new Date(...)` a secas se come el corrimiento de un día
 * que documenta el comentario de abajo.
 */
export function parseFecha(v) {
  return _parse(v);
}

function _parse(v) {
  if (!v) return null;
  if (v instanceof Date) return isNaN(v) ? null : v;
  // Las fechas ISO tipo "2026-07-10" sin timezone se parsean como UTC y
  // pueden restar un día al mostrar en zona local. Fijamos la hora al mediodía
  // para evitar ese corrimiento.
  const s = typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? `${v}T12:00:00` : v;
  const d = new Date(s);
  return isNaN(d) ? null : d;
}
