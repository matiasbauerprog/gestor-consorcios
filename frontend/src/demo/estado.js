import { correrDataset } from "./fechas";

/**
 * Estado en memoria de la demo, sembrado con el dataset ya corrido al día de
 * la visita.
 *
 * `reiniciar()` existe para el botón "reiniciar demo" del aviso superior: como
 * el estado vive en memoria y no se persiste (spec §2.3), volver al arranque
 * es recargar la copia original. Cada lectura y cada reinicio parten de un
 * clon, así que una pantalla que mute lo que recibió no puede contaminar el
 * dataset de origen ni las lecturas siguientes.
 */
export function crearEstado(dataset, hoy) {
  const inicial = correrDataset(dataset, hoy);
  let actual = structuredClone(inicial);

  return {
    leer(path) {
      return actual[path];
    },
    reiniciar() {
      actual = structuredClone(inicial);
    },
  };
}
