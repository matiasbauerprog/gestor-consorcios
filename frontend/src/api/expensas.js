import { apiFetch } from "./client";

export function listarExpensas({ departamento_id, periodo } = {}) {
  const params = new URLSearchParams();
  if (departamento_id != null) params.set("departamento_id", departamento_id);
  if (periodo) params.set("periodo", periodo);
  const qs = params.toString();
  return apiFetch(`/expensas${qs ? `?${qs}` : ""}`);
}

export function obtenerExpensa(id) {
  return apiFetch(`/expensas/${id}`);
}

export function crearExpensa(payload) {
  return apiFetch("/expensas", {
    method: "POST",
    body: payload,
  });
}

export function eliminarExpensa(id) {
  return apiFetch(`/expensas/${id}`, { method: "DELETE" });
}
