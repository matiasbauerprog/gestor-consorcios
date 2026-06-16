import { apiFetch } from "./client";

export function listarProveedores({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/proveedores${qs}`);
}

export function crearProveedor(payload) {
  return apiFetch("/proveedores", { method: "POST", body: payload });
}

export function obtenerProveedor(id) {
  return apiFetch(`/proveedores/${id}`);
}

export function actualizarProveedor(id, payload) {
  return apiFetch(`/proveedores/${id}`, { method: "PATCH", body: payload });
}

export function eliminarProveedor(id) {
  return apiFetch(`/proveedores/${id}`, { method: "DELETE" });
}
