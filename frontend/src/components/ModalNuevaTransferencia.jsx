import { useState } from "react";
import Modal from "./Modal";
import { crearTransferencia } from "../api/transferencias";

export default function ModalNuevaTransferencia({ cajas, onClose, onCreada }) {
  const [origen, setOrigen] = useState(cajas[0]?.id || "");
  const [destino, setDestino] = useState(cajas[1]?.id || "");
  const [monto, setMonto] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [descripcion, setDescripcion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const r = await crearTransferencia({
      caja_origen_id: Number(origen),
      caja_destino_id: Number(destino),
      monto: Number(monto),
      fecha,
      descripcion,
    });
    setGuardando(false);
    if (r.status === 201) onCreada();
    else setError(r.data?.detail || "No se pudo crear la transferencia.");
  }

  return (
    <Modal titulo="Transferir entre cajas" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>
          Origen
          <select value={origen} onChange={(e) => setOrigen(e.target.value)} required>
            {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label>
          Destino
          <select value={destino} onChange={(e) => setDestino(e.target.value)} required>
            {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label>
          Monto
          <input type="number" step="0.01" min="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} required />
        </label>
        <label>
          Fecha
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} required />
        </label>
        <label>
          Descripción
          <input type="text" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} required />
        </label>
        {error && <p role="alert" className="error-banner">{error}</p>}
        <button type="submit" disabled={guardando}>
          {guardando ? "Guardando…" : "Confirmar transferencia"}
        </button>
      </form>
    </Modal>
  );
}
