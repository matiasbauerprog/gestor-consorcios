import { apiFetch } from "./client";

export async function listarConsorcios() {
  return apiFetch("/consorcios");
}

export async function obtenerConsorcio(id) {
  return apiFetch(`/consorcios/${id}`);
}

export async function crearConsorcio(body) {
  return apiFetch("/consorcios", { method: "POST", body });
}

export async function actualizarConsorcio(id, body) {
  return apiFetch(`/consorcios/${id}`, { method: "PATCH", body });
}
