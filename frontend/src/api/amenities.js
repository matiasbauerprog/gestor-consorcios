import { apiFetch } from "./client";

export function listarAmenities({ incluirInactivos = false } = {}) {
  const qs = incluirInactivos ? "?incluir_inactivos=true" : "";
  return apiFetch(`/amenities${qs}`);
}

export function crearAmenity(payload) {
  return apiFetch("/amenities", { method: "POST", body: payload });
}

export function actualizarAmenity(id, payload) {
  return apiFetch(`/amenities/${id}`, { method: "PATCH", body: payload });
}

export function darDeBajaAmenity(id) {
  return apiFetch(`/amenities/${id}`, { method: "DELETE" });
}
