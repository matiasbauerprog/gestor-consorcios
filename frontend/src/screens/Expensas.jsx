import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarExpensas } from "../api/expensas";
import SelectorDepartamento from "../components/SelectorDepartamento";

export default function Expensas() {
  const { user } = useAuth();
  const [expensas, setExpensas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);
  const [departamentoSeleccionado, setDepartamentoSeleccionado] = useState(null);

  const esAdmin = user.rol === "administracion";

  useEffect(() => {
    if (esAdmin && departamentoSeleccionado === null) {
      setExpensas([]);
      return;
    }

    let cancelado = false;
    setCargando(true);

    async function cargar() {
      const params = esAdmin ? { departamento_id: departamentoSeleccionado } : {};
      const r = await listarExpensas(params);
      if (cancelado) return;
      if (r.status === 200) {
        setExpensas(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        setErrorCarga("No se pudieron cargar las expensas.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, [esAdmin, departamentoSeleccionado]);

  return (
    <section>
      <header className="seccion-header">
        <h2>Expensas</h2>
        {esAdmin && (
          <div className="seccion-acciones">
            <SelectorDepartamento
              valor={departamentoSeleccionado}
              onChange={setDepartamentoSeleccionado}
              permitirVacio={false}
            />
          </div>
        )}
      </header>

      {esAdmin && departamentoSeleccionado === null && (
        <p>Elegí un departamento para ver sus expensas.</p>
      )}

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {!cargando && !errorCarga && expensas.length === 0 &&
        (!esAdmin || departamentoSeleccionado !== null) && (
          <p>No hay expensas para mostrar.</p>
        )}

      <ul className="lista-expensas">
        {expensas.map((e) => (
          <li key={e.id}>
            <article className="tarjeta">
              <h3>{e.periodo} — ${e.monto.toLocaleString("es-AR")}</h3>
              <p className="meta">vence {e.fecha_vencimiento}</p>
              <p>Estado: {e.estado}</p>
            </article>
          </li>
        ))}
      </ul>

      <p>
        <Link to="/comprobantes">Ver todos los comprobantes →</Link>
      </p>
    </section>
  );
}
