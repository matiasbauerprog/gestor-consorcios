import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { listarComunicados } from "../api/comunicados";
import Tarjeta from "../components/Tarjeta";

function formatearFecha(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function cuerpoLargo(cuerpo) {
  if (cuerpo.length > 280) return true;
  if (cuerpo.split("\n").length > 3) return true;
  return false;
}

export default function Comunicados() {
  const { user } = useAuth();
  const [comunicados, setComunicados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [expandidos, setExpandidos] = useState(() => new Set());

  function toggleExpandir(id) {
    setExpandidos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  useEffect(() => {
    let cancelado = false;

    async function cargar() {
      const r = await listarComunicados();
      if (cancelado) return;

      if (r.status === 200) {
        setComunicados(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        // 401 lo maneja apiFetch (logout automático). El resto es error genérico.
        setErrorCarga("No se pudieron cargar los comunicados.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <section>
      <header className="seccion-header">
        <h2>Comunicados</h2>
        {user.rol === "administracion" && (
          <button type="button">+ Nuevo comunicado</button>
        )}
      </header>

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {!cargando && !errorCarga && comunicados.length === 0 && (
        <p>No hay comunicados publicados.</p>
      )}

      <ul className="lista-comunicados">
        {comunicados.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>{c.titulo}</h3>
              <p className="meta">
                {formatearFecha(c.fecha_publicacion)} · Administración
              </p>
              <p className={expandidos.has(c.id) ? "" : "cuerpo-truncado"}>
                {c.cuerpo}
              </p>
              {cuerpoLargo(c.cuerpo) && (
                <div className="tarjeta-acciones">
                  <button
                    type="button"
                    className="boton-link"
                    onClick={() => toggleExpandir(c.id)}
                  >
                    {expandidos.has(c.id) ? "Ver menos" : "Ver más"}
                  </button>
                </div>
              )}
            </Tarjeta>
          </li>
        ))}
      </ul>
    </section>
  );
}
