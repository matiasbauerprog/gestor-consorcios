/** `YYYY-MM` exacto, de punta a punta: un período es la cadena entera. */
const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;
/** `YYYY-MM-DD` al principio de la cadena, con hora opcional detrás. */
const FECHA = /^(\d{4})-(\d{2})-(\d{2})(.*)$/;

/**
 * Cuántos meses enteros pasaron entre la generación del dataset y hoy.
 *
 * Nunca devuelve negativo: si el reloj de quien visita está atrasado respecto
 * de la generación, la demo se muestra tal como se generó en vez de viajar al
 * pasado — un dataset con fechas hacia adelante se vería peor que uno viejo.
 */
export function mesesDeDesfase(generadoISO, hoy) {
  const [anio, mes] = generadoISO.split("-").map(Number);
  const meses = (hoy.getFullYear() - anio) * 12 + (hoy.getMonth() + 1 - mes);
  return Math.max(0, meses);
}

/** Último día del mes (1-12) de un año dado. */
function ultimoDia(anio, mes) {
  return new Date(anio, mes, 0).getDate();
}

/** Suma `meses` a un par año/mes y devuelve el par resultante. */
function sumarMeses(anio, mes, meses) {
  const total = anio * 12 + (mes - 1) + meses;
  return [Math.floor(total / 12), (total % 12) + 1];
}

const dosDigitos = (n) => String(n).padStart(2, "0");

/**
 * Corre `valor` hacia adelante `meses` meses, conservando su formato.
 *
 * El desplazamiento es en MESES ENTEROS, no en días: los períodos son claves
 * de mes (`2026-07`) y sumarles una cantidad fija de días los rompería.
 * Cuando el día no existe en el mes destino (un 31 que cae en febrero) se
 * recorta al último día, que es la convención de cualquier calendario.
 *
 * Lo que no parece una fecha vuelve intacto: el dataset tiene códigos de
 * unidad, descripciones y montos, y este módulo no puede distinguirlos por
 * contexto — sólo por forma. Por eso los patrones están anclados: una
 * descripción como "Expensa 2026-07" no es una fecha y no se toca.
 */
export function correrFecha(valor, meses) {
  if (typeof valor !== "string" || meses === 0) return valor;

  if (PERIODO.test(valor)) {
    const [anio, mes] = valor.split("-").map(Number);
    const [anioDestino, mesDestino] = sumarMeses(anio, mes, meses);
    return `${anioDestino}-${dosDigitos(mesDestino)}`;
  }

  const m = FECHA.exec(valor);
  if (!m) return valor;
  const [, anioStr, mesStr, diaStr, resto] = m;
  const [anioDestino, mesDestino] = sumarMeses(Number(anioStr), Number(mesStr), meses);
  const dia = Math.min(Number(diaStr), ultimoDia(anioDestino, mesDestino));
  return `${anioDestino}-${dosDigitos(mesDestino)}-${dosDigitos(dia)}${resto}`;
}

/**
 * Copia del dataset con todas sus fechas corridas al día de la visita.
 *
 * Recorre en profundidad y aplica `correrFecha` a cada cadena. Los importes,
 * los identificadores y los textos quedan intactos porque no matchean el
 * formato de fecha.
 *
 * Los intereses y recargos NO se recalculan: viajan tal cual, como decidió el
 * spec (§3.3). En pantalla es indistinguible, porque lo que se muestra es un
 * importe y no una cuenta.
 */
export function correrDataset(dataset, hoy) {
  const meses = mesesDeDesfase(dataset._generado, hoy);
  if (meses === 0) return structuredClone(dataset);

  const correr = (valor) => {
    if (typeof valor === "string") return correrFecha(valor, meses);
    if (Array.isArray(valor)) return valor.map(correr);
    if (valor && typeof valor === "object") {
      return Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, correr(v)]));
    }
    return valor;
  };

  return correr(dataset);
}
