import { apiFetch } from "./client";

export function listarPeriodos() {
  return apiFetch("/periodos");
}

export function estadoPeriodo(periodo) {
  return apiFetch(`/periodos/${periodo}/estado`);
}

export function previewPeriodo(periodo, { fecha_1, fecha_2 } = {}) {
  const qs = new URLSearchParams();
  if (fecha_1) qs.set("fecha_1", fecha_1);
  if (fecha_2) qs.set("fecha_2", fecha_2);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/periodos/${periodo}/preview${suffix}`);
}

export function cerrarPeriodo(periodo, body = {}) {
  return apiFetch(`/periodos/${periodo}/cerrar`, {
    method: "POST",
    body,
  });
}
