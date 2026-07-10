import { apiFetch, abrirPdf } from "./client";

/**
 * Abre el PDF de una expensa en una nueva pestaña.
 * El token y el X-Consorcio-Id los inyecta el helper del client.
 */
export function abrirPdfExpensa(expensaId) {
  return abrirPdf(`/expensas/${expensaId}/pdf`);
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
