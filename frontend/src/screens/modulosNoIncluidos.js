/**
 * Lo único que la demo deja fuera del recorrido.
 *
 * Al principio eran tres secciones — Tesorería, Personal y Configuración —
 * porque el dataset no traía sus datos. Ahora sí los trae, así que la demo
 * muestra la aplicación entera y acá queda sólo la consola comercial: la que
 * usa quien *vende* el sistema, no quien administra el consorcio. No tiene
 * sentido mostrarle al visitante por dónde se le suspende la cuenta.
 *
 * No está en el menú de ningún rol de la demo; esta pantalla existe para
 * quien llegue escribiendo la dirección a mano.
 *
 * Vive en su propio archivo y no junto al componente porque un módulo que
 * exporta componentes y constantes a la vez rompe la recarga rápida durante
 * el desarrollo.
 */
export const MODULOS = {
  "super-admin": {
    titulo: "Consola de la plataforma",
    resumen:
      "El panel de quien provee el sistema: qué administraciones lo usan, cuánto consumen y qué módulos tiene contratada cada una.",
    detalle: [
      "Desde acá se da de alta una administración nueva, se le habilitan módulos y se la suspende si deja de pagar.",
      "Incluye un registro de auditoría de las acciones sensibles y la posibilidad de entrar como un cliente para darle soporte.",
      "No forma parte de lo que ve un administrador de consorcios, y por eso queda fuera de la demostración.",
    ],
  },
};

export const MODULO_GENERICO = {
  titulo: "Sección no incluida en la demo",
  resumen: "Esta parte del sistema no forma parte del recorrido de la demostración.",
  detalle: [],
};
