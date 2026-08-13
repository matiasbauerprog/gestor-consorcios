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
  const [items, setItems] = useState([]);
  const [abierto, setAbierto] = useState(false);

  async function refrescarCount() {
    const r = await obtenerNoLeidasCount();
    if (r.status === 200) setCount(r.data.count);
  }

  async function refrescarLista() {
    const r = await listarNotificaciones(10);
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
            {count > 0 && (
              <button
                type="button"
                onClick={handleMarcarTodas}
                className="campanita-marcar-todas"
              >
                Marcar todas
              </button>
            )}
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
        </section>
      )}
    </div>
  );
}
