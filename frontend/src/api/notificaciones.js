import { apiFetch } from "./client";

export function listarNotificaciones(limit = 50) {
  return apiFetch(`/notificaciones?limit=${limit}`);
}

export function obtenerNoLeidasCount() {
  return apiFetch("/notificaciones/no-leidas-count");
}

export function marcarLeida(id) {
  return apiFetch(`/notificaciones/${id}/marcar-leida`, {
    method: "POST",
    body: {},
  });
}

export function marcarTodasLeidas() {
  return apiFetch("/notificaciones/marcar-todas-leidas", {
    method: "POST",
    body: {},
  });
}
