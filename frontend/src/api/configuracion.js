import { apiFetch } from "./client";

export function obtenerConfiguracion() {
  return apiFetch("/configuracion");
}

export function actualizarConfiguracion(payload) {
  return apiFetch("/configuracion", { method: "PUT", body: payload });
}
