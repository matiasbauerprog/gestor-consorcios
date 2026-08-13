import { useState } from "react";
import { useEsTablet } from "../hooks/useBreakpoint";

/**
 * Una misma colección en dos densidades: tabla de ≥600px para arriba, tarjetas
 * por debajo. Renderiza UN solo árbol — nunca los dos ocultando uno por CSS,
 * que duplicaría el contenido para los lectores de pantalla.
 *
 * En modo tabla las columnas NO miden su contenido: se reparten el ancho
 * disponible según el `ancho` declarado (`table-layout: fixed` + colgroup).
 *
 * Unidades válidas en `ancho`: `auto`, longitudes (`ch`, `rem`, `px`) y
 * porcentajes. NO uses `fr` — es una unidad de grid, y en un <col> el
 * navegador la descarta en silencio dejando la columna sin ancho declarado.
 * `auto` es el equivalente correcto acá: bajo `table-layout: fixed`, las
 * columnas en `auto` se reparten en partes iguales lo que sobra después de
 * las de ancho fijo, que es exactamente el reparto proporcional buscado.
 *
 * El `data-prio` de cada celda es lo que el CSS usa para esconderla cuando el
 * contenedor se angosta; ver el bloque `@container` en index.css.
 */
export default function TablaResponsive({
  columnas,
  filas,
  claveFila,
  renderTarjeta,
  vacio = "No hay nada para mostrar.",
}) {
  const esTablet = useEsTablet();

  const [expandidas, setExpandidas] = useState(() => new Set());

  /** Solo hay algo que esconder si alguna columna no es prioridad 1. */
  const columnasOcultables = columnas.filter((c) => (c.prioridad ?? 1) > 1);
  const hayDetalle = columnasOcultables.length > 0;

  function alternar(clave) {
    setExpandidas((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(clave)) siguiente.delete(clave);
      else siguiente.add(clave);
      return siguiente;
    });
  }

  if (filas.length === 0) {
    return <p className="lista-vacia">{vacio}</p>;
  }

  if (!esTablet) {
    return (
      <ul className="lista-cards">
        {filas.map((fila) => (
          <li key={claveFila(fila)}>{renderTarjeta(fila)}</li>
        ))}
      </ul>
    );
  }

  return (
    <div className="tabla-datos-scroll">
      <table className="tabla-datos">
        <colgroup>
          {hayDetalle && <col className="col-chevron" style={{ width: "2.75rem" }} />}
          {columnas.map((c) => (
            <col key={c.clave} style={{ width: c.ancho ?? "auto" }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {hayDetalle && <th className="col-chevron"><span className="sr-only">Detalle</span></th>}
            {columnas.map((c) => (
              <th key={c.clave} className={c.className} data-prio={c.prioridad ?? 1}>
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => {
            const clave = claveFila(fila);
            const abierta = expandidas.has(clave);
            const idDetalle = `detalle-${clave}`;
            return [
              <tr key={clave} className="fila-datos">
                {hayDetalle && (
                  <td className="col-chevron">
                    <button
                      type="button"
                      className="chevron-detalle"
                      aria-expanded={abierta}
                      aria-controls={idDetalle}
                      aria-label={abierta ? "Ocultar más datos" : "Ver más datos"}
                      onClick={() => alternar(clave)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                           stroke="currentColor" strokeWidth="2.5"
                           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="m9 18 6-6-6-6" />
                      </svg>
                    </button>
                  </td>
                )}
                {columnas.map((c) => (
                  <td key={c.clave} className={c.className} data-prio={c.prioridad ?? 1}>
                    {c.celda(fila)}
                  </td>
                ))}
              </tr>,
              hayDetalle && (
                <tr key={`${clave}-detalle`} id={idDetalle} className="fila-detalle" hidden={!abierta}>
                  <td colSpan={columnas.length + 1}>
                    {columnasOcultables.map((c) => (
                      <div key={c.clave} className="detalle-par" data-prio={c.prioridad}>
                        <span className="detalle-etiqueta">{c.titulo}</span>
                        <span className="detalle-valor">{c.celda(fila)}</span>
                      </div>
                    ))}
                  </td>
                </tr>
              ),
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}
