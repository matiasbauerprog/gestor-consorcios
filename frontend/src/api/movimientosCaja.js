import { apiFetch } from "./client";

export function listarMovimientos(cajaId, { limit = 100, offset = 0 } = {}) {
  return apiFetch(`/cajas/${cajaId}/movimientos?limit=${limit}&offset=${offset}`);
}

export function crearAjuste(cajaId, payload) {
  return apiFetch(`/cajas/${cajaId}/movimientos`, { method: "POST", body: payload });
}
