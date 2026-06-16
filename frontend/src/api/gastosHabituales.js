import { apiFetch } from "./client";

export function listarGastosHabituales({ activa } = {}) {
  const qs = activa === undefined ? "" : `?activa=${activa}`;
  return apiFetch(`/gastos-habituales${qs}`);
}

export function crearGastoHabitual(payload) {
  return apiFetch("/gastos-habituales", { method: "POST", body: payload });
}

export function obtenerGastoHabitual(id) {
  return apiFetch(`/gastos-habituales/${id}`);
}

export function actualizarGastoHabitual(id, payload) {
  return apiFetch(`/gastos-habituales/${id}`, { method: "PATCH", body: payload });
}

export function eliminarGastoHabitual(id) {
  return apiFetch(`/gastos-habituales/${id}`, { method: "DELETE" });
}
