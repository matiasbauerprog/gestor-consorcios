import { apiFetch } from "./client";

export function listarCajas() {
  return apiFetch("/cajas");
}

export function crearCaja(payload) {
  return apiFetch("/cajas", { method: "POST", body: payload });
}

export function actualizarCaja(id, payload) {
  return apiFetch(`/cajas/${id}`, { method: "PATCH", body: payload });
}

export function eliminarCaja(id) {
  return apiFetch(`/cajas/${id}`, { method: "DELETE" });
}
