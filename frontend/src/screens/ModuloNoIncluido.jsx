import { MODULOS, MODULO_GENERICO } from "./modulosNoIncluidos";

/**
 * Pantalla que reemplaza a las secciones que la demo deja fuera del recorrido.
 *
 * En vez de un error o una pantalla en blanco, el visitante lee qué resuelve
 * el módulo que acaba de abrir. El catálogo de textos vive en
 * `modulosNoIncluidos.js`.
 */
export default function ModuloNoIncluido({ modulo }) {
  const info = MODULOS[modulo] ?? MODULO_GENERICO;

  return (
    <main className="pantalla modulo-no-incluido">
      <h2>{info.titulo}</h2>
      <p className="modulo-no-incluido-resumen">{info.resumen}</p>
      {info.detalle.map((parrafo) => (
        <p key={parrafo}>{parrafo}</p>
      ))}
      <p className="modulo-no-incluido-nota">
        Esta sección forma parte del <strong>sistema completo</strong>. La demo se
        concentra en el circuito de expensas y cobranzas para que se pueda recorrer
        en pocos minutos.
      </p>
    </main>
  );
}
