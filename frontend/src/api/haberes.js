import { apiFetch } from "./client";

export function listarHaberes({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/haberes${qs}`);
}

export function crearHaber(payload) {
  return apiFetch("/haberes", { method: "POST", body: payload });
}

export function obtenerHaber(id) {
  return apiFetch(`/haberes/${id}`);
}

export function actualizarHaber(id, payload) {
  return apiFetch(`/haberes/${id}`, { method: "PATCH", body: payload });
}

export function eliminarHaber(id) {
  return apiFetch(`/haberes/${id}`, { method: "DELETE" });
}
