import { useState } from "react";
import Modal from "./Modal";
import { actualizarPeticion, eliminarPeticion } from "../api/peticiones";
import { crearTrabajo } from "../api/trabajos";
import { useAuth } from "../auth/AuthContext";
import { formatFecha, formatFechaHora } from "../utils/fechas";

const ETIQUETAS_ESTADO = {
  abierta: "Abierta",
  convertida_en_trabajo: "Convertida en trabajo",
  rechazada: "Rechazada",
  cancelada: "Cancelada",
};

export default function ModalDetallePeticion({
  peticion,
  onClose,
  onActualizado,
}) {
  const { user } = useAuth();
  const esAdmin =
    user?.rol === "administracion" || user?.rol === "representante";
  const esMia =
    user?.rol === "departamento" &&
    user.departamento_id === peticion.departamento_id;
  const puedeBorrar = esAdmin || (esMia && peticion.estado === "abierta");
  const [error, setError] = useState("");
  // `null` = no está rechazando. Un string = el motivo que viene escribiendo.
  // Rechazar es en dos pasos justamente para que haya un lugar donde explicar
  // el "no" antes de confirmarlo.
  const [motivoRechazo, setMotivoRechazo] = useState(null);
  const [rechazando, setRechazando] = useState(false);

  async function handleConvertirTrabajo() {
    setError("");
    const r = await crearTrabajo({
      peticion_id: peticion.id,
      descripcion: peticion.titulo,
    });
    if (r.status === 201) onActualizado();
    else setError(r.data?.detail || "Error al convertir la petición.");
  }

  async function handleRechazar() {
    setError("");
    setRechazando(true);
    const r = await actualizarPeticion(peticion.id, {
      estado: "rechazada",
      motivo_rechazo: motivoRechazo?.trim() || null,
    });
    setRechazando(false);
    if (r.status === 200) onActualizado();
    else setError(r.data?.detail || "Error al rechazar la petición.");
  }

  async function handleEliminar() {
    setError("");
    if (!window.confirm("¿Eliminar esta petición?")) return;
    const r = await eliminarPeticion(peticion.id);
    if (r.status === 204) onActualizado();
    else setError(r.data?.detail || "Error al eliminar la petición.");
  }

  return (
    <Modal titulo={`Petición #${peticion.id}`} onClose={onClose}>
      <p>
        <strong>Depto:</strong> {peticion.departamento_id}
      </p>
      <p>
        <strong>Título:</strong> {peticion.titulo}
      </p>
      <p>
        <strong>Descripción:</strong> {peticion.descripcion}
      </p>
      <p>
        <strong>Estado:</strong>{" "}
        {ETIQUETAS_ESTADO[peticion.estado] || peticion.estado}
      </p>
      {peticion.estado === "rechazada" && peticion.motivo_rechazo && (
        <p>
          <strong>Motivo del rechazo:</strong> {peticion.motivo_rechazo}
        </p>
      )}
      <p>
        <strong>Fecha:</strong>{" "}
        {formatFechaHora(peticion.fecha_creacion)}
      </p>

      {motivoRechazo !== null && (
        <label>
          Motivo del rechazo (opcional, lo ve el departamento)
          <textarea
            value={motivoRechazo}
            onChange={(e) => setMotivoRechazo(e.target.value)}
            rows={3}
            maxLength={1000}
            autoFocus
          />
        </label>
      )}

      {error && <p className="error">{error}</p>}

      <div className="acciones-modal">
        {esAdmin && peticion.estado === "abierta" && (
          motivoRechazo === null ? (
            <>
              <button type="button" onClick={handleConvertirTrabajo}>
                Convertir en trabajo
              </button>
              <button type="button" onClick={() => setMotivoRechazo("")}>
                Rechazar
              </button>
            </>
          ) : (
            <>
              <button type="button" onClick={handleRechazar} disabled={rechazando}>
                {rechazando ? "Rechazando…" : "Confirmar rechazo"}
              </button>
              <button
                type="button"
                onClick={() => setMotivoRechazo(null)}
                disabled={rechazando}
              >
                Volver
              </button>
            </>
          )
        )}
        {puedeBorrar && (
          <button type="button" onClick={handleEliminar}>
            Eliminar
          </button>
        )}
        <button type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </Modal>
  );
}
