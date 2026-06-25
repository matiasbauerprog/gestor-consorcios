import { apiFetch, API_BASE } from "./client";

/**
 * Abre el PDF de una expensa en una nueva pestaña.
 * Fetcha como blob para evitar pasar el token por query string.
 *
 * @param {number} expensaId
 * @param {string} token - JWT del usuario actual
 */
export async function abrirPdfExpensa(expensaId, token) {
  const res = await fetch(`${API_BASE}/expensas/${expensaId}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Error al cargar PDF: HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/**
 * Envía PDFs de todas las expensas del período por email (admin).
 * @param {string} periodo - "YYYY-MM"
 * @param {boolean} confirmarSinCerrar - true para forzar envío si período no cerrado
 */
export function enviarPdfsDePeriodo(periodo, confirmarSinCerrar = false) {
  return apiFetch(`/periodos/${periodo}/enviar-pdfs`, {
    method: "POST",
    body: { confirmar_sin_cerrar: confirmarSinCerrar },
  });
}
