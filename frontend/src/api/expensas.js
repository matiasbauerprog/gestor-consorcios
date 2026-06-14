import { apiFetch } from "./client";

export function listarExpensas({ departamento_id, estado, periodo } = {}) {
  const params = new URLSearchParams();
  if (departamento_id != null) params.set("departamento_id", departamento_id);
  if (estado) params.set("estado", estado);
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

export function presentarComprobante(expensa_id, { fecha_pago, monto, archivo }) {
  const fd = new FormData();
  fd.append("fecha_pago", fecha_pago);
  fd.append("monto", String(monto));
  if (archivo) fd.append("archivo", archivo);
  return apiFetch(`/expensas/${expensa_id}/comprobantes`, {
    method: "POST",
    body: fd,
  });
}
