import { useEffect, useId, useRef, useState } from "react";
import { useEsTablet } from "../hooks/useBreakpoint";

/** Prioridad 2 se cae bajo 720px de contenedor; prioridad 3, bajo 1000px.
 *  Prioridad 1 nunca se cae. Antes de la primera medición (`ancho === null`)
 *  se consideran todas visibles: un primer paint de más es preferible a uno
 *  de menos que salte apenas el ResizeObserver reporta el ancho real.
 *
 *  Por qué 720 y no 760 (el número original): el contenedor que mide el
 *  ResizeObserver no es el viewport — es el viewport menos el sidebar
 *  (230px, solo desde 960px para arriba: `.app-sidebar` en index.css) menos
 *  el padding horizontal de `.app-content`, que cambia de valor en dos
 *  breakpoints propios (`index.css`, reglas `.app-content`):
 *
 *    <600px   (sin sidebar): padding 1rem   por lado → 32px totales
 *    600–959px (sin sidebar): padding 1.5rem por lado → 48px totales
 *    ≥960px    (CON sidebar): padding 1.5rem por lado → 48px totales
 *
 *  Contenedor = viewport − sidebar (si aplica) − padding horizontal total.
 *  Para los cuatro anchos de viewport que este componente declara verificar:
 *
 *    375px  (mobile, <600px):  esTablet=false → renderiza cards, no tabla.
 *                               Contenedor teórico: 375 − 32 = 343px.
 *    768px  (tablet, 600–959): sin sidebar. 768 − 48 = 720px.
 *    1024px (desktop, ≥960):   1024 − 230 − 48 = 746px.
 *    1440px (desktop, ≥960):   1440 − 230 − 48 = 1162px (asumiendo
 *                               `.app-content:has(.pantalla-ancha)`, tope
 *                               1600px, que no se activa acá; sin esa clase
 *                               el tope es 960px y el contenedor da
 *                               960 − 48 = 912px en su lugar — igual arriba
 *                               de 720 y por debajo de 1000).
 *
 *  760 chocaba de lleno contra el caso de 768px: 720px de contenedor real
 *  quedaba 40px por DEBAJO del umbral, así que la tablet portrait — el
 *  ancho que motivó todo este trabajo — caía al escalón mínimo (solo
 *  prioridad 1) en vez del intermedio. 720 le da a la tablet su escalón
 *  intermedio, pero EXACTO en el filo (720 >= 720, `>=` es inclusive) —
 *  CERO margen, no "margen real": cualquier cambio futuro a
 *  `--ancho-sidebar`, al padding de `.app-content`, o un gutter de
 *  scrollbar overlay que le robe aunque sea 1px al contenedor tira a la
 *  tablet de vuelta al escalón mínimo. Por eso este número no se "ajusta"
 *  la próxima vez — se vuelve a DERIVAR desde cero, corriendo de nuevo la
 *  cuenta completa de arriba para los cuatro anchos de viewport, porque no
 *  hay colchón que absorba un cambio chico. */
function prioridadVisible(prioridad, ancho) {
  if (prioridad <= 1) return true;
  if (ancho === null) return true;
  if (prioridad === 2) return ancho >= 720;
  return ancho >= 1000;
}

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
 * El `data-prio` de cada celda queda para debugging/estilo, pero quién decide
 * si la columna se dibuja es este componente, no el CSS: una celda en
 * `display: none` no ocupa lugar en la grilla, así que con `table-layout:
 * fixed` el `<colgroup>` (que asigna ancho por posición) se desalinea apenas
 * se esconde una columna que no es la última. La tabla mide su propio
 * contenedor con `ResizeObserver` y solo dibuja las columnas que entran —
 * las que no entran nunca llegan a generar una celda, así que no hay nada
 * que desalinear. Ver el detalle en el spec (sección "El mecanismo de
 * ocultamiento").
 */
export default function TablaResponsive({
  columnas,
  filas,
  claveFila,
  renderTarjeta,
  vacio = "No hay nada para mostrar.",
}) {
  const esTablet = useEsTablet();
  // Namespacea los ids de fila de detalle por instancia montada: dos
  // <TablaResponsive> en la misma página (p. ej. Cajas.jsx: cajas y
  // movimientos) pueden compartir dominio de `claveFila` (ambas numéricas),
  // y sin este prefijo `detalle-${clave}` colisionaría en el DOM entre
  // instancias, dejando `aria-controls` ambiguo. `useId` es estable entre
  // renders y único por componente montado.
  const idInstancia = useId();
  const [expandidas, setExpandidas] = useState(() => new Set());
  const wrapperRef = useRef(null);
  /** `null` = todavía no midió: se tratan todas las columnas como visibles. */
  const [anchoContenedor, setAnchoContenedor] = useState(null);

  const hayFilas = filas.length > 0;
  const mostrarTabla = esTablet && hayFilas;

  // El ref solo se attachea en la rama de tabla, así que el observer se
  // (re)conecta cada vez que `mostrarTabla` pasa a true — incluyendo la
  // primera vez que el layout deja de ser tarjetas.
  useEffect(() => {
    if (!mostrarTabla) return undefined;
    const el = wrapperRef.current;
    if (!el) return undefined;

    const observer = new ResizeObserver((entries) => {
      const [entry] = entries;
      if (entry) setAnchoContenedor(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [mostrarTabla]);

  function alternar(clave) {
    setExpandidas((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(clave)) siguiente.delete(clave);
      else siguiente.add(clave);
      return siguiente;
    });
  }

  if (!hayFilas) {
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

  const columnasVisibles = columnas.filter((c) =>
    prioridadVisible(c.prioridad ?? 1, anchoContenedor),
  );
  const columnasOcultas = columnas.filter(
    (c) => !prioridadVisible(c.prioridad ?? 1, anchoContenedor),
  );
  const hayDetalle = columnasOcultas.length > 0;
  const colSpanDetalle = columnasVisibles.length + 1;

  return (
    <div className="tabla-datos-scroll" ref={wrapperRef}>
      <table className="tabla-datos">
        <colgroup>
          {hayDetalle && <col className="col-chevron" style={{ width: "2.75rem" }} />}
          {columnasVisibles.map((c) => (
            <col key={c.clave} style={{ width: c.ancho ?? "auto" }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {hayDetalle && <th className="col-chevron"><span className="sr-only">Detalle</span></th>}
            {columnasVisibles.map((c) => (
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
            const idDetalle = `detalle${idInstancia}-${clave}`;
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
                {columnasVisibles.map((c) => (
                  <td key={c.clave} className={c.className} data-prio={c.prioridad ?? 1}>
                    {c.celda(fila)}
                  </td>
                ))}
              </tr>,
              hayDetalle && (
                <tr key={`${clave}-detalle`} id={idDetalle} className="fila-detalle" hidden={!abierta}>
                  <td colSpan={colSpanDetalle}>
                    {columnasOcultas.map((c) => (
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
