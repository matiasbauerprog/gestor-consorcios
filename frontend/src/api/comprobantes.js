import { apiFetch } from "./client";

export function listarComprobantes({ estado, departamento_id } = {}) {
  const params = new URLSearchParams();
  if (estado) params.set("estado", estado);
  if (departamento_id != null) params.set("departamento_id", departamento_id);
  const qs = params.toString();
  return apiFetch(`/comprobantes${qs ? `?${qs}` : ""}`);
}

export function presentarComprobante({ fecha_pago, monto, archivo }) {
  const fd = new FormData();
  fd.append("fecha_pago", fecha_pago);
  fd.append("monto", String(monto));
  if (archivo) fd.append("archivo", archivo);
  return apiFetch("/comprobantes", {
    method: "POST",
    body: fd,
  });
}

export function actualizarComprobante(id, payload) {
  return apiFetch(`/comprobantes/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export function eliminarComprobante(id) {
  return apiFetch(`/comprobantes/${id}`, { method: "DELETE" });
}
