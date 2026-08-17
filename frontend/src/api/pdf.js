import { apiFetch, abrirPdf } from "./client";

/** Dónde quedan los PDF exportados dentro del sitio publicado. */
const CARPETA_PDFS_DEMO = "/demo-pdfs";

/**
 * Abre el PDF de una expensa en una nueva pestaña.
 *
 * Contra el servidor real lo genera el backend al vuelo. En la demo no hay
 * servidor: el generador exportó los PDF del último período cerrado como
 * archivos estáticos, y el dataset trae el mapa de qué archivo le toca a cada
 * expensa.
 *
 * Sólo el último período tiene PDF exportado — son 18 archivos, uno por
 * unidad. Pedir el de una expensa más vieja falla con un mensaje entendible
 * en vez de abrir una pestaña en blanco.
 */
export async function abrirPdfExpensa(expensaId) {
  // Se compara contra la variable de entorno y no contra una constante
  // importada: así el empaquetador puede descartar esta rama en el build de
  // producción y no emitir el dataset de la demo.
  if (import.meta.env.VITE_DEMO_MODE === "true") {
    const { default: DATASET } = await import("../demo/dataset.json");
    const nombre = DATASET._pdfs?.[String(expensaId)];
    if (!nombre) {
      throw new Error(
        "En la demo sólo está el PDF de las expensas del último período cerrado.",
      );
    }
    window.open(`${CARPETA_PDFS_DEMO}/${nombre}`, "_blank");
    return;
  }
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
