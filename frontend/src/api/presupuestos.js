import { apiFetch } from "./client";

export function listarPresupuestos(trabajoId) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos`);
}

// Crear con archivo opcional. payload es FormData ya armada por el componente.
export function crearPresupuesto(trabajoId, formData) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos`, {
    method: "POST",
    body: formData,
  });
}

export function actualizarPresupuesto(trabajoId, presupuestoId, payload) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos/${presupuestoId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function eliminarPresupuesto(trabajoId, presupuestoId) {
  return apiFetch(`/trabajos/${trabajoId}/presupuestos/${presupuestoId}`, {
    method: "DELETE",
  });
}

export function aprobarPresupuesto(trabajoId, presupuestoId) {
  return apiFetch(
    `/trabajos/${trabajoId}/presupuestos/${presupuestoId}/aprobar`,
    { method: "POST", body: {} },
  );
}

export function rechazarPresupuesto(trabajoId, presupuestoId) {
  return apiFetch(
    `/trabajos/${trabajoId}/presupuestos/${presupuestoId}/rechazar`,
    { method: "POST", body: {} },
  );
}
