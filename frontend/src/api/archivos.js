import { API_BASE, apiFetch as apiFetchReal } from "./client";

/**
 * Resuelve la URL con la que se puede mostrar o descargar un adjunto.
 *
 * Hace falta este paso extra porque `<img src>` y `<a href>` no mandan el
 * header de autorización: el permiso se verifica en esta llamada, y lo que
 * vuelve es una URL firmada de vida corta que ya sirve sin token.
 *
 * @param {string} ruta - ruta del endpoint que devuelve la URL firmada, o una
 *   ruta estática de la demo (`/demo-comprobantes/...`), que se usa directo.
 * @param {object} [opciones]
 * @param {Function} [opciones.apiFetch] - inyectable para los tests.
 * @returns {Promise<string|null>} la URL, o null si no se pudo obtener.
 */
export async function urlDeArchivo(ruta, { apiFetch = apiFetchReal } = {}) {
  if (!ruta) return null;

  // La demo no tiene servidor: sus comprobantes son archivos que sirve el
  // hosting estático. Pedirles una firma no tendría a quién preguntarle.
  if (ruta.startsWith("/demo-comprobantes/")) return ruta;

  const res = await apiFetch(ruta);
  if (!res?.ok || !res.data?.url) return null;
  return `${API_BASE}${res.data.url}`;
}

/**
 * Ruta desde la que se obtiene el adjunto de un comprobante.
 *
 * En la demo el `archivo_path` ya es la ruta estática del archivo; contra el
 * backend real es la clave de almacenamiento, que no se puede abrir sola y
 * hay que cambiar por una URL firmada.
 *
 * @param {{id: number, archivo_path: string|null}} comprobante
 * @returns {string|null}
 */
export function rutaAdjuntoComprobante(comprobante) {
  if (!comprobante?.archivo_path) return null;
  if (comprobante.archivo_path.startsWith("/demo-comprobantes/")) {
    return comprobante.archivo_path;
  }
  return `/comprobantes/${comprobante.id}/archivo`;
}
