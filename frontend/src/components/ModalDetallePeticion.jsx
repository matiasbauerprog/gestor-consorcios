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
    const r = await actualizarPeticion(peticion.id, { estado: "rechazada" });
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
      <p>
        <strong>Fecha:</strong>{" "}
        {formatFechaHora(peticion.fecha_creacion)}
      </p>

      {error && <p className="error">{error}</p>}

      <div className="acciones-modal">
        {esAdmin && peticion.estado === "abierta" && (
          <>
            <button type="button" onClick={handleConvertirTrabajo}>
              Convertir en trabajo
            </button>
            <button type="button" onClick={handleRechazar}>
              Rechazar
            </button>
          </>
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
