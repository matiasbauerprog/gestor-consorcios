import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { listarComprobantes } from "../api/comprobantes";
import BadgeEstado from "../components/BadgeEstado";
import SelectorDepartamento from "../components/SelectorDepartamento";
import Tarjeta from "../components/Tarjeta";

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "pendiente_verificacion", label: "Pendientes" },
  { value: "aprobado", label: "Aprobados" },
  { value: "rechazado", label: "Rechazados" },
];

export default function Comprobantes() {
  const { user } = useAuth();
  const esAdmin = user.rol === "administracion";

  const [comprobantes, setComprobantes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroDepto, setFiltroDepto] = useState(null);

  useEffect(() => {
    let cancelado = false;
    setCargando(true);

    async function cargar() {
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      if (esAdmin && filtroDepto != null) params.departamento_id = filtroDepto;

      const r = await listarComprobantes(params);
      if (cancelado) return;

      if (r.status === 200) {
        setComprobantes(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        setErrorCarga("No se pudieron cargar los comprobantes.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, [filtroEstado, filtroDepto, esAdmin]);

  return (
    <section>
      <header className="seccion-header">
        <h2>Comprobantes</h2>
      </header>

      <div className="filtros">
        <label>
          Estado
          <select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
            {ESTADOS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        {esAdmin && (
          <SelectorDepartamento valor={filtroDepto} onChange={setFiltroDepto} permitirVacio />
        )}
      </div>

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {!cargando && !errorCarga && comprobantes.length === 0 && (
        <p>No hay comprobantes con esos filtros.</p>
      )}

      <ul className="lista-comprobantes">
        {comprobantes.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>
                {c.expensa?.periodo ?? "—"} · ${c.monto.toLocaleString("es-AR")}
              </h3>
              <p className="meta">Pagado {c.fecha_pago}</p>
              {c.expensa && (
                <p className="meta">Departamento: {c.expensa.departamento_id}</p>
              )}
              <p><BadgeEstado estado={c.estado} /></p>
              {c.archivo_url && (
                <p>
                  <a href={c.archivo_url} target="_blank" rel="noopener noreferrer">
                    Ver archivo
                  </a>
                </p>
              )}
            </Tarjeta>
          </li>
        ))}
      </ul>
    </section>
  );
}
