import { apiFetch } from "./client";

export function listarConceptos({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/conceptos-liquidacion${qs}`);
}

export function crearConcepto(payload) {
  return apiFetch("/conceptos-liquidacion", { method: "POST", body: payload });
}

export function obtenerConcepto(id) {
  return apiFetch(`/conceptos-liquidacion/${id}`);
}

export function actualizarConcepto(id, payload) {
  return apiFetch(`/conceptos-liquidacion/${id}`, { method: "PATCH", body: payload });
}

export function eliminarConcepto(id) {
  return apiFetch(`/conceptos-liquidacion/${id}`, { method: "DELETE" });
}
