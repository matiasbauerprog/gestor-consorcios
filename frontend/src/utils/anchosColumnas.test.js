import { describe, it, expect } from "vitest";
import {
  PX_POR_CH,
  ANCHO_FECHA,
  ANCHO_FECHA_CORTA,
  ANCHO_MONTO,
  ANCHO_MONTO_DECIMAL,
  ANCHO_PERIODO,
  ANCHO_FECHA_MONTO,
  ANCHO_CUIT,
} from "./anchosColumnas";

/** Los `ch` declarados en un <col> se resuelven contra la fuente COMPUTADA de
 *  ese <col>: Plus Jakarta Sans a 13px en peso 700, donde el glyph "0" mide
 *  9.52px — no los 7.15px del mismo glyph en peso normal. Medido en el
 *  browser sobre `.tabla-datos` (una columna declarada en 34ch renderizaba
 *  324px = 34 × 9.53). Dividir por el valor de peso normal infla cada columna
 *  un 33%, que es el bug que estos tests fijan. */
const PX_POR_CH_MEDIDO = 9.52;

/** Ancho por carácter del CONTENIDO (peso 700 a 13px) y padding horizontal de
 *  la celda: los dos números de la fórmula documentada en anchosColumnas.js. */
const PX_POR_CARACTER = 8.2;
const PADDING_CELDA = 24;
const COLCHON = 1.2;

/** La fórmula del archivo: para un string de L caracteres, cuántos `ch` hacen
 *  falta para que entre con su colchón y su padding. */
function chNecesarios(largo) {
  return (largo * PX_POR_CARACTER * COLCHON + PADDING_CELDA) / PX_POR_CH_MEDIDO;
}

const ch = (valor) => Number(String(valor).replace("ch", ""));
const px = (valor) => ch(valor) * PX_POR_CH_MEDIDO;

describe("anchosColumnas — el factor de conversión", () => {
  it("usa el ancho del glyph en el peso REAL de la celda, no en peso normal", () => {
    expect(PX_POR_CH).toBeCloseTo(PX_POR_CH_MEDIDO, 2);
  });
});

describe("anchosColumnas — cada medida alcanza para su contenido", () => {
  // [constante, largo del peor caso declarado en su docblock, nombre]
  const CASOS = [
    [ANCHO_FECHA, 10, "fecha DD/MM/YYYY"],
    [ANCHO_FECHA_CORTA, 8, "fecha corta DD/MM/YY"],
    [ANCHO_MONTO, 14, "monto -$ 123.456.789"],
    [ANCHO_MONTO_DECIMAL, 17, "monto con centavos"],
    [ANCHO_PERIODO, 7, "período YYYY-MM"],
    [ANCHO_FECHA_MONTO, 22, "fecha · monto (caso típico)"],
    [ANCHO_CUIT, 13, "CUIT XX-XXXXXXXX-X"],
  ];

  it.each(CASOS)("%s entra sin truncar", (valor, largo) => {
    const disponible = px(valor) - PADDING_CELDA;
    const contenidoCrudo = largo * PX_POR_CARACTER;
    expect(disponible).toBeGreaterThanOrEqual(contenidoCrudo);
  });

  // El bug que motivó este archivo de tests: dividir por el `ch` de peso
  // normal no hace que las columnas trunquen — las hace un 33% MÁS anchas de
  // lo necesario. Sobra tanto en cada una que la suma se come el contenedor
  // entero y la única columna en `auto` se queda sin nada.
  it.each(CASOS)("%s no se pasa más de un 35% de lo que necesita", (valor, largo) => {
    const necesarios = chNecesarios(largo);
    expect(ch(valor)).toBeLessThanOrEqual(Math.ceil(necesarios * 1.35));
  });
});

describe("anchosColumnas — presupuesto de la fila de Expensas", () => {
  /** Columnas fijas de `/cobranzas` (Expensas) en el escalón donde se muestran
   *  TODAS, incluidas las dos de vencimiento (prioridad 3, contenedor ≥1000):
   *  período, 1° venc, 2° venc, estado, pendiente. `departamento` va en `auto`
   *  y se queda con lo que sobre — es la que absorbe cualquier exceso. */
  const ANCHO_ESTADO = "12ch"; // declarado en Expensas.jsx

  /** Contenedor real de un viewport de 1280px: 1280 − 230 (sidebar) − 48
   *  (padding de .app-content). Es el más chico donde el escalón de ≥1000
   *  se activa, así que es el peor caso del presupuesto. */
  const CONTENEDOR_1280 = 1002;

  /** Departamento muestra "UF-03F — Piso 3, Unidad F". Con menos de esto la
   *  columna que identifica la unidad deja de ser legible, que es exactamente
   *  el desenlace que este presupuesto existe para impedir. */
  const MINIMO_DEPARTAMENTO = 120;

  it("las columnas fijas dejan lugar para Departamento en un viewport de 1280px", () => {
    const fijas = [
      ANCHO_PERIODO,
      ANCHO_FECHA_MONTO,
      ANCHO_FECHA_MONTO,
      ANCHO_ESTADO,
      ANCHO_MONTO,
    ];
    const sumaFijas = fijas.reduce((total, valor) => total + px(valor), 0);
    const sobra = CONTENEDOR_1280 - sumaFijas;
    expect(sobra).toBeGreaterThanOrEqual(MINIMO_DEPARTAMENTO);
  });
});
