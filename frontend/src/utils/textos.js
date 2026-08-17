/**
 * Pone en mayúscula la primera letra y deja el resto como está.
 *
 * En castellano los meses, los días y las preposiciones van en minúscula:
 * "lunes, 17 de agosto de 2026". El `text-transform: capitalize` del CSS
 * capitaliza *cada* palabra y deja "Lunes, 17 De Agosto De 2026", que es
 * incorrecto — y lo mismo le hace a un consorcio llamado "Edificio del Sol".
 * Sólo la primera letra es lo que hace falta cuando el texto abre una línea.
 */
export function mayusculaInicial(texto) {
  if (!texto) return texto;
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/**
 * Concuerda un sustantivo con su cantidad: "1 petición", "3 peticiones".
 *
 * El tablero mostraba "1 peticiones sin responder". Es la primera pantalla
 * que ve un administrador y la que más se mira en una demostración.
 *
 * `plural` es opcional: por defecto agrega "s", que sirve para la mayoría
 * ("gasto"/"gastos"), pero no para las palabras que terminan en consonante
 * ("petición"/"peticiones") ni para las invariables.
 */
export function pluralizar(cantidad, singular, plural) {
  const palabra = cantidad === 1 ? singular : (plural ?? `${singular}s`);
  return `${cantidad} ${palabra}`;
}
