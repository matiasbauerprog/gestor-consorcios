import { apiFetch } from "./client";

export function listarComprobantes({ estado, departamento_id } = {}) {
  const params = new URLSearchParams();
  if (estado) params.set("estado", estado);
  if (departamento_id != null) params.set("departamento_id", departamento_id);
  const qs = params.toString();
  return apiFetch(`/comprobantes${qs ? `?${qs}` : ""}`);
}

export function actualizarComprobante(id, payload) {
  return apiFetch(`/comprobantes/${id}`, {
    method: "PATCH",
    body: payload,
  });
}
