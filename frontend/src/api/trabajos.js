import { apiFetch } from "./client";

export function listarTrabajos() {
  return apiFetch("/trabajos");
}

export function obtenerTrabajo(id) {
  return apiFetch(`/trabajos/${id}`);
}

export function crearTrabajo(payload) {
  return apiFetch("/trabajos", { method: "POST", body: payload });
}

export function actualizarTrabajo(id, payload) {
  return apiFetch(`/trabajos/${id}`, { method: "PATCH", body: payload });
}

export function completarTrabajo(id) {
  return apiFetch(`/trabajos/${id}/completar`, { method: "POST", body: {} });
}

export function cancelarTrabajo(id) {
  return apiFetch(`/trabajos/${id}/cancelar`, { method: "POST", body: {} });
}
