import { useEsTablet } from "../hooks/useBreakpoint";

/**
 * Una misma colección en dos densidades: tabla de ≥600px para arriba, tarjetas
 * por debajo. Renderiza UN solo árbol — nunca los dos ocultando uno por CSS,
 * que duplicaría el contenido para los lectores de pantalla.
 */
export default function ListaResponsive({
  columnas,
  filas,
  claveFila,
  renderTarjeta,
  vacio = "No hay nada para mostrar.",
}) {
  const esTablet = useEsTablet();

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
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c.clave} className={c.className}>{c.titulo}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={claveFila(fila)}>
              {columnas.map((c) => (
                <td key={c.clave} className={c.className}>{c.celda(fila)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
