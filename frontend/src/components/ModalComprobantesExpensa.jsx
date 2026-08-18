import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  listarComprobantes,
  actualizarComprobante,
} from "../api/comprobantes";
import { rutaAdjuntoComprobante } from "../api/archivos";
import ArchivoAdjunto from "./ArchivoAdjunto";
import BadgeEstado from "./BadgeEstado";
import Modal from "./Modal";
import Tarjeta from "./Tarjeta";
import { formatFecha } from "../utils/fechas";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

export default function ModalComprobantesExpensa({ expensa, onClose }) {
  const { user } = useAuth();
  const esAdmin = user?.rol === "administracion";
  const [comprobantes, setComprobantes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [accionandoId, setAccionandoId] = useState(null);
  const [errorAccion, setErrorAccion] = useState(null);

  async function cargar() {
    setCargando(true);
    setErrorCarga(null);
    const r = await listarComprobantes();
    if (r.status === 200) {
      // Filtrar localmente por expensa_id si está disponible en el comprobante
      const filtrados = r.data.filter((c) => c.expensa_id === expensa.id);
      setComprobantes(filtrados);
    } else if (r.status !== 401) {
      setErrorCarga("No se pudieron cargar los comprobantes.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargar();
  }, [expensa.id]);

  async function handleDecision(id, estadoNuevo) {
    setAccionandoId(id);
    setErrorAccion(null);
    const r = await actualizarComprobante(id, { estado: estadoNuevo });
    setAccionandoId(null);

    if (r.status === 200) {
      setComprobantes((prev) => prev.map((c) => (c.id === id ? r.data : c)));
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

  return (
    <Modal
      titulo={`Comprobantes — Expensa ${expensa.periodo}`}
      onClose={onClose}
    >
      {errorAccion && <p role="alert" className="error-banner">{errorAccion}</p>}
      {cargando && <p>Cargando…</p>}
      {!cargando && errorCarga && (
        <p role="alert" className="error-banner">{errorCarga}</p>
      )}
      {!cargando && !errorCarga && comprobantes.length === 0 && (
        <p>No hay comprobantes para esta expensa.</p>
      )}
      {!cargando && !errorCarga && comprobantes.length > 0 && (
        <ul className="lista-comprobantes">
          {comprobantes.map((c) => (
            <li key={c.id}>
              <Tarjeta>
                <h3>
                  {formatMoney(c.monto)}
                </h3>
                <p className="meta">Pagado {formatFecha(c.fecha_pago)}</p>
                <p><BadgeEstado estado={c.estado} /></p>
                {c.archivo_path && (
                  <ArchivoAdjunto
                    ruta={rutaAdjuntoComprobante(c)}
                    alt="Comprobante"
                    className="comprobante-img"
                  />
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
      )}
    </Modal>
  );
}
