const MINUTO = 60_000;
const HORA = 60 * MINUTO;
const DIA = 24 * HORA;

/**
 * Antigüedad de `fecha` en castellano coloquial: "recién", "hace 12 min",
 * "hace 3 h", "ayer", "hace 4 días", y de una semana en adelante la fecha corta.
 * `ahora` es inyectable para que los tests no dependan del reloj.
 */
export function formatearTiempoRelativo(fecha, ahora = new Date()) {
  const d = fecha instanceof Date ? fecha : new Date(fecha);
  if (Number.isNaN(d.getTime())) return "—";

  const delta = ahora.getTime() - d.getTime();
  if (delta < MINUTO) return "recién";
  if (delta < HORA) return `hace ${Math.floor(delta / MINUTO)} min`;
  if (delta < DIA) return `hace ${Math.floor(delta / HORA)} h`;
  if (delta < 2 * DIA) return "ayer";
  if (delta < 7 * DIA) return `hace ${Math.floor(delta / DIA)} días`;

  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}
