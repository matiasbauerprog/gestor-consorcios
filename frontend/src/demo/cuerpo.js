/** Lee un archivo del disco como URL embebida, para poder mostrarlo. */
function comoDataUrl(archivo) {
  return new Promise((resolve) => {
    const lector = new FileReader();
    lector.onload = () => resolve(lector.result);
    lector.onerror = () => resolve(null);
    lector.readAsDataURL(archivo);
  });
}

/** `"1500.5"` → `1500.5`; `"2026-08"` y `"Service"` quedan como texto. */
function comoNumeroSiCorresponde(valor) {
  if (valor === "" || valor == null) return valor;
  const n = Number(valor);
  return Number.isFinite(n) && String(n) === valor.trim() ? n : valor;
}

/**
 * Deja el cuerpo de un pedido en la forma que espera el sustituto.
 *
 * Las pantallas que adjuntan un archivo mandan `FormData`, no JSON — es lo que
 * el backend real necesita para recibir la imagen del comprobante. Sin esta
 * traducción el sustituto recibe un objeto sin campos y rechaza el pedido por
 * validación, que es exactamente lo que pasaba al presentar un pago desde la
 * pantalla aunque los tests con objetos planos pasaran.
 *
 * El archivo adjunto se convierte en una URL embebida: en la demo no hay
 * servidor donde subirlo, así que la imagen viaja con el dato y la pantalla
 * puede mostrarla igual.
 */
export async function normalizarCuerpo(body) {
  if (!(typeof FormData !== "undefined" && body instanceof FormData)) return body;

  const plano = {};
  for (const [clave, valor] of body.entries()) {
    if (typeof File !== "undefined" && valor instanceof File) {
      plano.archivo_url = await comoDataUrl(valor);
      continue;
    }
    plano[clave] = comoNumeroSiCorresponde(valor);
  }
  return plano;
}
