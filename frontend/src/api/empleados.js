import { apiFetch } from "./client";

export function listarEmpleados({ activo } = {}) {
  const qs = activo === undefined ? "" : `?activo=${activo}`;
  return apiFetch(`/empleados${qs}`);
}

export function crearEmpleado(payload) {
  return apiFetch("/empleados", { method: "POST", body: payload });
}

export function obtenerEmpleado(id) {
  return apiFetch(`/empleados/${id}`);
}

export function actualizarEmpleado(id, payload) {
  return apiFetch(`/empleados/${id}`, { method: "PATCH", body: payload });
}

export function eliminarEmpleado(id) {
  return apiFetch(`/empleados/${id}`, { method: "DELETE" });
}
