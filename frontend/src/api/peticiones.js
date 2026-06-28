import { apiFetch } from "./client";

export function listarPeticiones() {
  return apiFetch("/peticiones");
}

export function crearPeticion({ titulo, descripcion }) {
  return apiFetch("/peticiones", {
    method: "POST",
    body: { titulo, descripcion },
  });
}

export function actualizarPeticion(id, payload) {
  return apiFetch(`/peticiones/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export function eliminarPeticion(id) {
  return apiFetch(`/peticiones/${id}`, { method: "DELETE" });
}
