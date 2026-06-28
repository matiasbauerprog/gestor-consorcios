import { apiFetch } from "./client";

export function listarRecurrentes() {
  return apiFetch("/trabajos-recurrentes");
}

export function crearRecurrente(payload) {
  return apiFetch("/trabajos-recurrentes", { method: "POST", body: payload });
}

export function actualizarRecurrente(id, payload) {
  return apiFetch(`/trabajos-recurrentes/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export function eliminarRecurrente(id) {
  return apiFetch(`/trabajos-recurrentes/${id}`, { method: "DELETE" });
}

export function materializarRecurrente(id) {
  return apiFetch(`/trabajos-recurrentes/${id}/materializar`, {
    method: "POST",
    body: {},
  });
}
