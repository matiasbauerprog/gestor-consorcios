import { apiFetch } from "./client";

export function listarUsuarios() {
  return apiFetch("/usuarios");
}

export function crearUsuario(payload) {
  return apiFetch("/usuarios", { method: "POST", body: payload });
}

export function cambiarEstadoUsuario(id, activa) {
  return apiFetch(`/usuarios/${id}/estado`, {
    method: "PATCH",
    body: { activa },
  });
}

export function eliminarUsuario(id) {
  return apiFetch(`/usuarios/${id}`, { method: "DELETE" });
}
