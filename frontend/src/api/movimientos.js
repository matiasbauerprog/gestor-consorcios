import { apiFetch } from "./client";

export function listarMisMovimientos({ desde, hasta } = {}) {
  const params = new URLSearchParams();
  if (desde) params.set("desde", desde);
  if (hasta) params.set("hasta", hasta);
  const qs = params.toString();
  return apiFetch(`/movimientos/mi-cuenta${qs ? `?${qs}` : ""}`);
}

export function listarMovimientosDepto(departamentoId, { desde, hasta } = {}) {
  const params = new URLSearchParams();
  if (desde) params.set("desde", desde);
  if (hasta) params.set("hasta", hasta);
  const qs = params.toString();
  return apiFetch(`/departamentos/${departamentoId}/cuenta${qs ? `?${qs}` : ""}`);
}

export function crearNota({ departamentoId, tipo, monto, descripcion, fecha }) {
  return apiFetch("/movimientos/nota", {
    method: "POST",
    body: {
      departamento_id: departamentoId,
      tipo,
      monto,
      descripcion,
      fecha,
    },
  });
}
