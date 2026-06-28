import { apiFetch } from "./client";

export function listarReservas({ estado } = {}) {
  const qs = estado ? `?estado=${estado}` : "";
  return apiFetch(`/reservas${qs}`);
}

export function obtenerReserva(id) {
  return apiFetch(`/reservas/${id}`);
}

export function crearReserva(amenityId, { inicio, fin }) {
  return apiFetch(`/amenities/${amenityId}/reservas`, {
    method: "POST",
    body: { inicio, fin },
  });
}

export function cancelarReserva(id) {
  return apiFetch(`/reservas/${id}`, { method: "DELETE" });
}
