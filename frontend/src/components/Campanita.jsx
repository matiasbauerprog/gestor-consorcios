import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listarNotificaciones,
  obtenerNoLeidasCount,
  marcarLeida,
  marcarTodasLeidas,
} from "../api/notificaciones";
import { formatearTiempoRelativo } from "../utils/tiempoRelativo";

const POLL_INTERVAL_MS = 60_000;

export default function Campanita() {
  const navigate = useNavigate();
  const [count, setCount] = useState(0);
  const [otrosConsorcios, setOtrosConsorcios] = useState(0);
  const [items, setItems] = useState([]);
  const [abierto, setAbierto] = useState(false);

  async function refrescarCount() {
    const r = await obtenerNoLeidasCount();
    if (r.status === 200) {
      setCount(r.data.count);
      setOtrosConsorcios(r.data.otros_consorcios ?? 0);
    }
  }

  async function refrescarLista() {
    const r = await listarNotificaciones({ limit: 10 });
    if (r.status === 200) setItems(r.data);
  }

  useEffect(() => {
    refrescarCount();
    refrescarLista();
    const id = setInterval(refrescarCount, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  async function handleClickNotif(n) {
    if (!n.leida) {
      await marcarLeida(n.id);
      refrescarCount();
      refrescarLista();
    }
    setAbierto(false);
    if (n.link) navigate(n.link);
  }

  async function handleMarcarTodas() {
    await marcarTodasLeidas();
    refrescarCount();
    refrescarLista();
  }

  function toggle() {
    setAbierto((prev) => {
      const nuevo = !prev;
      if (nuevo) refrescarLista();
      return nuevo;
    });
  }

  return (
    <div className="campanita">
      <button
        type="button"
        onClick={toggle}
        className={`campanita-boton${abierto ? " abierto" : ""}`}
        aria-label={count > 0 ? "Notificaciones sin leer" : "Notificaciones"}
        aria-expanded={abierto}
      >
        <svg
          width="19"
          height="19"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {/* Punto discreto (patrón Linear/Notion), elegido por el usuario
            sobre un badge numérico. count sigue viniendo del backend y
            guardándose en estado: la UI solo lee count > 0. No reintroducir
            el número acá. */}
        {count > 0 && <span className="campanita-badge" aria-hidden="true" />}
      </button>

      {abierto && (
        <section className="campanita-panel">
          <header className="campanita-panel-header">
            <strong>Notificaciones</strong>
            <div className="campanita-acciones">
              <button
                type="button"
                onClick={() => { setAbierto(false); navigate("/notificaciones/preferencias"); }}
                className="campanita-engranaje"
                aria-label="Configurar avisos"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </button>
              {count > 0 && (
                <button
                  type="button"
                  onClick={handleMarcarTodas}
                  className="campanita-marcar-todas"
                >
                  Marcar todas
                </button>
              )}
            </div>
          </header>
          {items.length === 0 ? (
            <p className="campanita-vacio">Sin notificaciones.</p>
          ) : (
            <ul className="campanita-lista">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => handleClickNotif(n)}
                    className={`campanita-item${n.leida ? "" : " campanita-item-no-leida"}`}
                  >
                    {/* Punto por-item del mockup aprobado: el gutter se
                        reserva siempre (leída o no) para que marcar como
                        leída solo apague el color del punto, sin correr
                        el texto. Ver comentario de CSS junto a
                        .campanita-item-punto. */}
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
          <footer className="campanita-panel-pie">
            <button
              type="button"
              className="campanita-ver-todas"
              onClick={() => { setAbierto(false); navigate("/notificaciones"); }}
            >
              Ver todas
            </button>
            {/* Sólo la administración puede tener más de un consorcio; para
                depto y representante el backend devuelve siempre 0, así que
                esta línea no aparece sin necesidad de chequear el rol acá. */}
            {otrosConsorcios > 0 && (
              <span className="campanita-otros-consorcios">
                {otrosConsorcios} sin leer en otros consorcios
              </span>
            )}
          </footer>
        </section>
      )}
    </div>
  );
}
