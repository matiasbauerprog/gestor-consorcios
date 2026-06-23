import { apiFetch } from "./client";

export function obtenerEstadoFinanciero({ ultimos = 20 } = {}) {
  return apiFetch(`/estado-financiero?ultimos=${ultimos}`);
}
