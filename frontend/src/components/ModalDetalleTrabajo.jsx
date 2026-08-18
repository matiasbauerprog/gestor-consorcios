import { useEffect, useState } from "react";
import Modal from "./Modal";
import ArchivoAdjunto from "./ArchivoAdjunto";
import { completarTrabajo, cancelarTrabajo } from "../api/trabajos";
import {
  listarPresupuestos,
  aprobarPresupuesto,
  rechazarPresupuesto,
  eliminarPresupuesto,
} from "../api/presupuestos";
import { listarProveedores } from "../api/proveedores";
import ModalNuevoPresupuesto from "./ModalNuevoPresupuesto";
import { formatFecha } from "../utils/fechas";

const ETIQUETAS_ESTADO_TRABAJO = {
  en_curso: "En curso",
  finalizado: "Finalizado",
  cancelado: "Cancelado",
};

const ETIQUETAS_ESTADO_PPTO = {
  presentado: "Presentado",
  aprobado: "Aprobado",
  rechazado: "Rechazado",
};

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

export default function ModalDetalleTrabajo({
  trabajo,
  onClose,
  onActualizado,
}) {
  const [presupuestos, setPresupuestos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [creandoPpto, setCreandoPpto] = useState(false);
  const [error, setError] = useState("");

  async function cargar() {
    setError("");
    const [rp, rpr] = await Promise.all([
      listarPresupuestos(trabajo.id),
      listarProveedores(),
    ]);
    if (rp.status === 200) setPresupuestos(rp.data);
    else setError(rp.data?.detail || "No se pudieron cargar los presupuestos.");
    if (rpr.status === 200) setProveedores(rpr.data);
  }

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trabajo.id]);

  const proveedorNombre = (id) =>
    proveedores.find((p) => p.id === id)?.razon_social || `#${id}`;

  async function handleAprobar(p) {
    if (
      presupuestos.some((x) => x.estado === "aprobado" && x.id !== p.id) &&
      !window.confirm("Ya hay un presupuesto aprobado. ¿Reemplazarlo?")
    ) {
      return;
    }
    const r = await aprobarPresupuesto(trabajo.id, p.id);
    if (r.status === 200) cargar();
    else setError(r.data?.detail || "Error al aprobar el presupuesto.");
  }

  async function handleRechazar(p) {
    const r = await rechazarPresupuesto(trabajo.id, p.id);
    if (r.status === 200) cargar();
    else setError(r.data?.detail || "Error al rechazar el presupuesto.");
  }

  async function handleEliminar(p) {
    if (!window.confirm("¿Eliminar este presupuesto?")) return;
    const r = await eliminarPresupuesto(trabajo.id, p.id);
    if (r.status === 204) cargar();
    else setError(r.data?.detail || "Error al eliminar.");
  }

  async function handleCompletar() {
    const r = await completarTrabajo(trabajo.id);
    if (r.status === 200) {
      const params = new URLSearchParams({
        proveedor_id: r.data.proveedor_id,
        monto: r.data.monto,
        concepto: r.data.concepto_sugerido,
        trabajo_id: r.data.trabajo_id,
      });
      window.location.href = `/gastos?${params}`;
    } else {
      setError(r.data?.detail || "Error al completar el trabajo.");
    }
  }

  async function handleCancelar() {
    if (!window.confirm("¿Cancelar este trabajo sin generar gasto?")) return;
    const r = await cancelarTrabajo(trabajo.id);
    if (r.status === 204) onActualizado();
    else setError(r.data?.detail || "Error al cancelar.");
  }

  const aprobado = presupuestos.find((p) => p.estado === "aprobado");

  return (
    <Modal titulo={`Trabajo #${trabajo.id}`} onClose={onClose} ancho>
      <p>
        <strong>Descripción:</strong> {trabajo.descripcion}
      </p>
      <p>
        <strong>Estado:</strong>{" "}
        {ETIQUETAS_ESTADO_TRABAJO[trabajo.estado] || trabajo.estado}
      </p>
      <p>
        <strong>Petición:</strong> {trabajo.peticion_id || "—"}
      </p>

      {error && <p className="error">{error}</p>}

      <h3>Presupuestos</h3>
      {trabajo.estado === "en_curso" && (
        <button type="button" onClick={() => setCreandoPpto(true)}>
          + Sumar presupuesto
        </button>
      )}

      <table className="tabla-listado">
        <thead>
          <tr>
            <th>Proveedor</th>
            <th>Monto</th>
            <th>Fecha</th>
            <th>Archivo</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {presupuestos.length === 0 ? (
            <tr>
              <td colSpan={6} className="vacio">
                Sin presupuestos.
              </td>
            </tr>
          ) : (
            presupuestos.map((p) => (
              <tr
                key={p.id}
                style={
                  p.estado === "aprobado" ? { background: "var(--color-success-bg)" } : {}
                }
              >
                <td>{proveedorNombre(p.proveedor_id)}</td>
                <td>{fmtMoney(p.monto)}</td>
                <td>{formatFecha(p.fecha_presentacion)}</td>
                <td>
                  {p.archivo_path ? (
                    <ArchivoAdjunto
                      ruta={`/trabajos/${trabajo.id}/presupuestos/${p.id}/archivo`}
                    >
                      Ver
                    </ArchivoAdjunto>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{ETIQUETAS_ESTADO_PPTO[p.estado] || p.estado}</td>
                <td>
                  {p.estado === "presentado" &&
                    trabajo.estado === "en_curso" && (
                      <>
                        <button type="button" onClick={() => handleAprobar(p)}>
                          Aprobar
                        </button>{" "}
                        <button type="button" onClick={() => handleRechazar(p)}>
                          Rechazar
                        </button>{" "}
                        <button type="button" onClick={() => handleEliminar(p)}>
                          Borrar
                        </button>
                      </>
                    )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <h3>Acciones del trabajo</h3>
      <div className="acciones-modal">
        {trabajo.estado === "en_curso" && aprobado && (
          <button type="button" onClick={handleCompletar}>
            💰 Sumar gasto a la caja
          </button>
        )}
        {trabajo.estado === "en_curso" && (
          <button type="button" onClick={handleCancelar}>
            Cancelar trabajo
          </button>
        )}
        {trabajo.estado === "finalizado" && (
          <p>✓ Trabajo finalizado. Gasto: #{trabajo.gasto_id || "—"}</p>
        )}
        {trabajo.estado === "cancelado" && <p>✕ Trabajo cancelado.</p>}
      </div>

      {creandoPpto && (
        <ModalNuevoPresupuesto
          trabajoId={trabajo.id}
          proveedores={proveedores}
          onClose={() => setCreandoPpto(false)}
          onCreado={() => {
            setCreandoPpto(false);
            cargar();
          }}
        />
      )}
    </Modal>
  );
}
