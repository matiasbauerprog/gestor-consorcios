import { apiFetch } from "./client";

export function listarNotificaciones({ limit = 50, offset = 0, soloNoLeidas = false, q = "" } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (soloNoLeidas) params.set("solo_no_leidas", "true");
  if (q) params.set("q", q);
  return apiFetch(`/notificaciones?${params.toString()}`);
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

export function listarPreferencias() {
  return apiFetch("/notificaciones/preferencias");
}

export function guardarPreferencias(items) {
  return apiFetch("/notificaciones/preferencias", { method: "PUT", body: items });
}
