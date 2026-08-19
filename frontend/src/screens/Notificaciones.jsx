import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listarNotificaciones,
  marcarLeida,
  marcarTodasLeidas,
} from "../api/notificaciones";
import { formatearTiempoRelativo } from "../utils/tiempoRelativo";

const POR_PAGINA = 30;

export default function Notificaciones() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [soloNoLeidas, setSoloNoLeidas] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [offset, setOffset] = useState(0);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(false);
  // Número de secuencia del pedido vigente: si "Cargar más" queda en vuelo
  // y mientras tanto el buscador dispara uno nuevo (que reemplaza en vez de
  // acumular), la respuesta vieja llega después y no debe tocar el estado
  // — se mezclaría la página anterior con la búsqueda nueva.
  const pedidoActual = useRef(0);

  const cargar = useCallback(
    async (nuevoOffset, reemplazar) => {
      const idPedido = ++pedidoActual.current;
      setCargando(true);
      const r = await listarNotificaciones({
        limit: POR_PAGINA,
        offset: nuevoOffset,
        soloNoLeidas,
        q: busqueda,
      });
      if (idPedido !== pedidoActual.current) return; // respuesta descartada, ya no es la vigente
      setCargando(false);
      if (r.status !== 200) return;
      setItems((prev) => (reemplazar ? r.data : [...prev, ...r.data]));
      setOffset(nuevoOffset + r.data.length);
      // Una página completa significa que puede haber más; una parcial, que
      // llegamos al final. Evita un pedido extra sólo para descubrirlo.
      setHayMas(r.data.length === POR_PAGINA);
    },
    [soloNoLeidas, busqueda],
  );

  useEffect(() => {
    const id = setTimeout(() => cargar(0, true), 250);
    return () => clearTimeout(id);
  }, [cargar]);

  async function handleClick(n) {
    if (!n.leida) await marcarLeida(n.id);
    if (n.link) navigate(n.link);
    else cargar(0, true);
  }

  async function handleMarcarTodas() {
    await marcarTodasLeidas();
    cargar(0, true);
  }

  return (
    <section className="pantalla-notificaciones">
      <header className="pantalla-notificaciones-header">
        <h1>Notificaciones</h1>
        <button type="button" onClick={handleMarcarTodas} className="campanita-marcar-todas">
          Marcar todas
        </button>
      </header>

      <div className="pantalla-notificaciones-filtros">
        <input
          type="search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar en las notificaciones"
          aria-label="Buscar en las notificaciones"
        />
        <label className="label-checkbox">
          <input
            type="checkbox"
            checked={soloNoLeidas}
            onChange={(e) => setSoloNoLeidas(e.target.checked)}
          />
          Solo no leídas
        </label>
      </div>

      {items.length === 0 && !cargando ? (
        <p className="pantalla-notificaciones-vacio">
          {busqueda || soloNoLeidas
            ? "No hay notificaciones que coincidan."
            : "Todavía no tenés notificaciones."}
        </p>
      ) : (
        <ul className="pantalla-notificaciones-lista">
          {items.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => handleClick(n)}
                className={`campanita-item${n.leida ? "" : " campanita-item-no-leida"}`}
              >
                <span className="campanita-item-punto" aria-hidden="true" />
                <span className="campanita-item-texto">
                  <span className="campanita-item-mensaje">{n.mensaje}</span>
                  <span className="campanita-item-fecha">
                    {formatearTiempoRelativo(n.created_at)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {hayMas && (
        <button
          type="button"
          onClick={() => cargar(offset, false)}
          disabled={cargando}
          className="pantalla-notificaciones-cargar-mas"
        >
          {cargando ? "Cargando…" : "Cargar más"}
        </button>
      )}
    </section>
  );
}
