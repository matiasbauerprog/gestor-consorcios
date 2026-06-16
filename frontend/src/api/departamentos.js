import { apiFetch } from "./client";

export function listarDepartamentos() {
  return apiFetch("/departamentos");
}

export function crearDepartamento(payload) {
  return apiFetch("/departamentos", { method: "POST", body: payload });
}

export function actualizarDepartamento(id, payload) {
  return apiFetch(`/departamentos/${id}`, { method: "PATCH", body: payload });
}

export function listarCoeficientesDepartamento(id) {
  return apiFetch(`/departamentos/${id}/coeficientes`);
}

export function reemplazarCoeficientesDepartamento(id, coeficientes) {
  return apiFetch(`/departamentos/${id}/coeficientes`, {
    method: "PUT",
    body: { coeficientes },
  });
}
