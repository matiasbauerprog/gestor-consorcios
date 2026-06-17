import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  listarComprobantes,
  actualizarComprobante,
  eliminarComprobante,
} from "../api/comprobantes";
import { API_BASE } from "../api/client";
import BadgeEstado from "../components/BadgeEstado";
import Modal from "../components/Modal";
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
  const [modalEliminar, setModalEliminar] = useState(null);
  const [eliminando, setEliminando] = useState(false);

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

  async function handleEliminar() {
    if (!modalEliminar) return;
    setEliminando(true);
    setErrorAccion(null);
    const r = await eliminarComprobante(modalEliminar.id);
    setEliminando(false);
    if (r.status === 204) {
      setComprobantes((prev) => prev.filter((c) => c.id !== modalEliminar.id));
      setModalEliminar(null);
      return;
    }
    if (r.status === 403) {
      setErrorAccion("No tenés permisos para eliminar este comprobante.");
      setModalEliminar(null);
      return;
    }
    if (r.status === 404) {
      setComprobantes((prev) => prev.filter((c) => c.id !== modalEliminar.id));
      setModalEliminar(null);
      return;
    }
    if (r.status !== 401) {
      setErrorAccion("No se pudo eliminar el comprobante.");
      setModalEliminar(null);
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
        <p>
          No hay comprobantes con esos filtros.
          {!esAdmin && (
            <>{" "}Para presentar un pago, andá a <Link to="/mi-cuenta">Mi cuenta</Link>.</>
          )}
        </p>
      )}

      <ul className="lista-comprobantes">
        {comprobantes.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>
                ${c.monto.toLocaleString("es-AR")}
              </h3>
              <p className="meta">Pagado {c.fecha_pago}</p>
              {c.departamento_id && (
                <p className="meta">Departamento: {c.departamento_id}</p>
              )}
              <p><BadgeEstado estado={c.estado} /></p>
              {c.archivo_path && (
                <a href={`${API_BASE}${c.archivo_path}`} target="_blank" rel="noopener noreferrer">
                  <img src={`${API_BASE}${c.archivo_path}`} alt="Comprobante" className="comprobante-img" />
                </a>
              )}
              <div className="tarjeta-acciones">
                {esAdmin && c.estado === "pendiente_verificacion" && (
                  <>
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
                  </>
                )}
                <button
                  type="button"
                  className="boton-peligro"
                  onClick={() => setModalEliminar(c)}
                >
                  Eliminar
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modalEliminar && (
        <Modal titulo="Eliminar comprobante" onClose={() => setModalEliminar(null)}>
          <p>¿Eliminar el comprobante del {modalEliminar.fecha_pago}?</p>
          <p className="meta">
            Esta acción lo oculta de la vista. Si ya estaba aprobado, el pago
            sigue contabilizado en la cuenta corriente.
          </p>
          <div className="modal-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={() => setModalEliminar(null)}
              disabled={eliminando}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="boton-peligro"
              onClick={handleEliminar}
              disabled={eliminando}
            >
              {eliminando ? "Eliminando…" : "Eliminar"}
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
