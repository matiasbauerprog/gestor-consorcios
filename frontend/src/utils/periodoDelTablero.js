/**
 * Qué período muestra la recaudación del tablero de inicio.
 *
 * El mes en curso recién empieza y todavía no tiene expensas emitidas hasta
 * que se cierra. Mostrar ese mes da una recaudación de $0 con "0% cobrado",
 * que se lee como "el sistema no tiene datos" cuando en realidad el mes recién
 * arrancó. Le pasa a cualquier administrador que entre los primeros días, no
 * sólo a quien mira la demo.
 *
 * Por eso: si el mes en curso ya tiene expensas emitidas se muestra ése; si no,
 * el último período cerrado, diciendo cuál es. Un consorcio recién creado, sin
 * nada cerrado todavía, se queda en el mes en curso — ahí el cero es la verdad.
 */
export function periodoDelTablero(periodoActual, cantidadExpensasDelActual, periodosCerrados) {
  if (cantidadExpensasDelActual > 0) {
    return { periodo: periodoActual, esMesEnCurso: true };
  }

  const cerrados = Array.isArray(periodosCerrados) ? periodosCerrados : [];
  if (cerrados.length === 0) {
    return { periodo: periodoActual, esMesEnCurso: true };
  }

  const ultimo = [...cerrados].sort().at(-1);
  return { periodo: ultimo, esMesEnCurso: false };
}
