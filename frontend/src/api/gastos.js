import { apiFetch } from "./client";

export function listarGastos(filtros = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) {
    if (v !== null && v !== undefined && v !== "") qs.set(k, v);
  }
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/gastos${suffix}`);
}

export function crearGasto(payload) {
  return apiFetch("/gastos", { method: "POST", body: payload });
}

export function crearPlanCuotas(payload) {
  return apiFetch("/gastos/plan-cuotas", { method: "POST", body: payload });
}

export function cargarGastosHabituales(periodo) {
  return apiFetch("/gastos/cargar-habituales", {
    method: "POST",
    body: { periodo },
  });
}

export function obtenerGasto(id) {
  return apiFetch(`/gastos/${id}`);
}

export function actualizarGasto(id, payload) {
  return apiFetch(`/gastos/${id}`, { method: "PATCH", body: payload });
}

export function eliminarGasto(id) {
  return apiFetch(`/gastos/${id}`, { method: "DELETE" });
}
