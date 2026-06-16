import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarComprobantes, actualizarComprobante } from "../api/comprobantes";
import { API_BASE } from "../api/client";
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
  const [searchParams] = useSearchParams();
  const deptoInicial = searchParams.get("departamento_id");

  const [comprobantes, setComprobantes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroDepto, setFiltroDepto] = useState(
    deptoInicial ? Number(deptoInicial) : null,
  );
  const [accionandoId, setAccionandoId] = useState(null);
  const [errorAccion, setErrorAccion] = useState(null);

  async function handleDecision(id, estadoNuevo) {
    setAccionandoId(id);
    const r = await actualizarComprobante(id, { estado: estadoNuevo });
    setAccionandoId(null);

    if (r.status === 200) {
      setComprobantes((prev) => prev.map((c) => (c.id === id ? r.data : c)));
      setErrorAccion(null);
      return;
    }
    if (r.status === 404) {
      setComprobantes((prev) => prev.filter((c) => c.id !== id));
      setErrorAccion("El comprobante no existe.");
      return;
    }
    if (r.status === 409) {
      setErrorAccion("El comprobante ya fue verificado.");
      return;
    }
    if (r.status === 403) {
      setErrorAccion("No tenés permisos para esta operación.");
      return;
    }
    if (r.status !== 401) {
      setErrorAccion("Ocurrió un error. Intentá de nuevo.");
    }
  }

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
      {errorAccion && <p role="alert" className="error-banner">{errorAccion}</p>}
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
              {c.archivo_path && (
                <a href={`${API_BASE}${c.archivo_path}`} target="_blank" rel="noopener noreferrer">
                  <img src={`${API_BASE}${c.archivo_path}`} alt="Comprobante" className="comprobante-img" />
                </a>
              )}
              {esAdmin && c.estado === "pendiente_verificacion" && (
                <div className="tarjeta-acciones">
                  <button
                    type="button"
                    onClick={() => handleDecision(c.id, "aprobado")}
                    disabled={accionandoId === c.id}
                  >
                    {accionandoId === c.id ? "…" : "Aprobar"}
                  </button>
                  <button
                    type="button"
                    className="boton-borrar"
                    onClick={() => handleDecision(c.id, "rechazado")}
                    disabled={accionandoId === c.id}
                  >
                    {accionandoId === c.id ? "…" : "Rechazar"}
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
