import { useState } from "react";
import Modal from "./Modal";
import { crearAmenity, actualizarAmenity } from "../api/amenities";

export default function ModalAmenity({ item, onClose, onGuardado }) {
  const esEditar = item !== null;
  const [nombre, setNombre] = useState(item?.nombre || "");
  const [descripcion, setDescripcion] = useState(item?.descripcion || "");
  const [precio, setPrecio] = useState(item?.precio_reserva ?? "");
  const [duracion, setDuracion] = useState(item?.duracion_maxima_horas ?? "");
  const [anticipacion, setAnticipacion] = useState(item?.anticipacion_maxima_dias ?? "");
  const [maxActivas, setMaxActivas] = useState(item?.max_reservas_activas_por_depto ?? "");
  const [horasCancelacion, setHorasCancelacion] = useState(item?.horas_minimas_cancelacion ?? "");
  const [activa, setActiva] = useState(item?.activo ?? true);
  const [error, setError] = useState("");

  function num(v) {
    if (v === "" || v === null || v === undefined) return null;
    return Number(v);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const payload = {
      nombre,
      descripcion: descripcion || null,
      precio_reserva: num(precio),
      duracion_maxima_horas: num(duracion),
      anticipacion_maxima_dias: num(anticipacion),
      max_reservas_activas_por_depto: num(maxActivas),
      horas_minimas_cancelacion: num(horasCancelacion),
    };
    if (esEditar) payload.activo = activa;
    const r = esEditar
      ? await actualizarAmenity(item.id, payload)
      : await crearAmenity(payload);
    if (r.status === 200 || r.status === 201) onGuardado();
    else setError(r.data?.detail || "Error al guardar.");
  }

  return (
    <Modal titulo={esEditar ? "Editar amenity" : "Nuevo amenity"} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} required maxLength={100} />
        </label>
        <label>
          Descripción
          <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={500} rows={2} />
        </label>
        <label>
          Precio por reserva (vacío = gratuito)
          <input type="number" min="0" step="0.01" value={precio} onChange={(e) => setPrecio(e.target.value)} />
        </label>
        <label>
          Duración máx (horas, vacío = sin límite)
          <input type="number" min="1" value={duracion} onChange={(e) => setDuracion(e.target.value)} />
        </label>
        <label>
          Anticipación máx (días, vacío = sin límite)
          <input type="number" min="1" value={anticipacion} onChange={(e) => setAnticipacion(e.target.value)} />
        </label>
        <label>
          Máx reservas activas por depto (vacío = sin límite)
          <input type="number" min="1" value={maxActivas} onChange={(e) => setMaxActivas(e.target.value)} />
        </label>
        <label>
          Horas mínimas para cancelación gratuita (vacío = siempre gratuita)
          <input type="number" min="0" value={horasCancelacion} onChange={(e) => setHorasCancelacion(e.target.value)} />
        </label>
        {esEditar && (
          <label className="label-checkbox">
            <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} />
            Activa
          </label>
        )}
        {error && <p className="error">{error}</p>}
        <div className="acciones">
          <button type="submit">Guardar</button>
          <button type="button" onClick={onClose}>Cancelar</button>
        </div>
      </form>
    </Modal>
  );
}
