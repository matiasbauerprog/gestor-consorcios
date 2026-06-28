import { useState } from "react";
import Modal from "./Modal";
import { crearPresupuesto } from "../api/presupuestos";

export default function ModalNuevoPresupuesto({
  trabajoId,
  proveedores,
  onClose,
  onCreado,
}) {
  const [proveedorId, setProveedorId] = useState(proveedores[0]?.id || "");
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [observaciones, setObservaciones] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setGuardando(true);
    const fd = new FormData();
    fd.append("proveedor_id", proveedorId);
    fd.append("monto", monto);
    fd.append("fecha_presentacion", fecha);
    if (observaciones) fd.append("observaciones", observaciones);
    if (archivo) fd.append("archivo", archivo);
    const r = await crearPresupuesto(trabajoId, fd);
    setGuardando(false);
    if (r.status === 201) onCreado();
    else setError(r.data?.detail || "Error al crear el presupuesto.");
  }

  return (
    <Modal titulo="Nuevo presupuesto" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>
          Proveedor{" "}
          <select
            value={proveedorId}
            onChange={(e) => setProveedorId(e.target.value)}
            required
          >
            {proveedores.map((p) => (
              <option key={p.id} value={p.id}>
                {p.razon_social}
              </option>
            ))}
          </select>
        </label>
        <label>
          Monto{" "}
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            required
          />
        </label>
        <label>
          Fecha de presentación{" "}
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </label>
        <label>
          Observaciones{" "}
          <textarea
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
            maxLength={1000}
            rows={3}
          />
        </label>
        <label>
          Archivo (PDF/JPG/PNG/WebP, opcional, máx 5 MB){" "}
          <input
            type="file"
            accept=".pdf,image/jpeg,image/png,image/webp"
            onChange={(e) => setArchivo(e.target.files[0] || null)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="acciones">
          <button type="submit" disabled={guardando}>
            {guardando ? "Guardando…" : "Crear"}
          </button>
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
        </div>
      </form>
    </Modal>
  );
}
