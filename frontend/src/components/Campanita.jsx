import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listarNotificaciones,
  obtenerNoLeidasCount,
  marcarLeida,
  marcarTodasLeidas,
} from "../api/notificaciones";

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
        className="campanita-boton"
        aria-label="Notificaciones"
        aria-expanded={abierto}
      >
        🔔
        {count > 0 && <span className="campanita-badge">{count}</span>}
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
                <li
                  key={n.id}
                  onClick={() => handleClickNotif(n)}
                  className={`campanita-item${n.leida ? "" : " campanita-item-no-leida"}`}
                >
                  <p className="campanita-item-mensaje">{n.mensaje}</p>
                  <p className="campanita-item-fecha">
                    {new Date(n.created_at).toLocaleString("es-AR")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
