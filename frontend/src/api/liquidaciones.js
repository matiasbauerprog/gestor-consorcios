import { apiFetch } from "./client";

export function listarLiquidaciones({ periodo, empleado_id } = {}) {
  const qs = new URLSearchParams();
  if (periodo) qs.set("periodo", periodo);
  if (empleado_id) qs.set("empleado_id", empleado_id);
  const s = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/liquidaciones${s}`);
}

export function crearLiquidacion(payload) {
  return apiFetch("/liquidaciones", { method: "POST", body: payload });
}

export function obtenerLiquidacion(id) {
  return apiFetch(`/liquidaciones/${id}`);
}

export function actualizarLiquidacion(id, payload) {
  return apiFetch(`/liquidaciones/${id}`, { method: "PATCH", body: payload });
}

export function eliminarLiquidacion(id) {
  return apiFetch(`/liquidaciones/${id}`, { method: "DELETE" });
}
