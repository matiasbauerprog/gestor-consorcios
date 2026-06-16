import { apiFetch } from "./client";

export function listarClasesProrrateo({ activa } = {}) {
  const qs = activa === undefined ? "" : `?activa=${activa}`;
  return apiFetch(`/clases-prorrateo${qs}`);
}

export function crearClaseProrrateo(payload) {
  return apiFetch("/clases-prorrateo", { method: "POST", body: payload });
}

export function obtenerClaseProrrateo(id) {
  return apiFetch(`/clases-prorrateo/${id}`);
}

export function actualizarClaseProrrateo(id, payload) {
  return apiFetch(`/clases-prorrateo/${id}`, { method: "PATCH", body: payload });
}

export function eliminarClaseProrrateo(id) {
  return apiFetch(`/clases-prorrateo/${id}`, { method: "DELETE" });
}
