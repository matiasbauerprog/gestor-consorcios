import { apiFetch, abrirPdf } from "./client";

export function obtenerResumenTesoreria({ ultimos = 20 } = {}) {
  return apiFetch(`/tesoreria?ultimos=${ultimos}`);
}

export function abrirPdfMovimientos({ desde, hasta }) {
  const qs = new URLSearchParams({ desde, hasta }).toString();
  return abrirPdf(`/tesoreria/movimientos-pdf?${qs}`);
}
