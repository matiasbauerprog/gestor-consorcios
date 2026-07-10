import { apiFetch, abrirPdf } from "./client";

export function obtenerEstadoFinanciero({ ultimos = 20 } = {}) {
  return apiFetch(`/estado-financiero?ultimos=${ultimos}`);
}

export function abrirPdfMovimientos({ desde, hasta }) {
  const qs = new URLSearchParams({ desde, hasta }).toString();
  return abrirPdf(`/estado-financiero/movimientos-pdf?${qs}`);
}
