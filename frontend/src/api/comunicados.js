import { apiFetch } from "./client";

export function listarComunicados() {
  return apiFetch("/comunicados");
}

export function crearComunicado({ titulo, cuerpo }) {
  return apiFetch("/comunicados", {
    method: "POST",
    body: { titulo, cuerpo },
  });
}

export function borrarComunicado(id) {
  return apiFetch(`/comunicados/${id}`, {
    method: "DELETE",
  });
}
