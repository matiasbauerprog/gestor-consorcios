import { useState } from "react";
import Modal from "./Modal";
import { crearAjuste } from "../api/movimientosCaja";

export default function ModalAjusteCaja({ caja, onClose, onCreado }) {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [monto, setMonto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const r = await crearAjuste(caja.id, {
      fecha, monto: Number(monto), descripcion,
    });
    setGuardando(false);
    if (r.status === 201) onCreado();
    else setError(r.data?.detail || "Error al crear el ajuste.");
  }

  return (
    <Modal titulo={`Ajuste manual — ${caja.nombre}`} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <p>Cargá un ajuste positivo o negativo. Quedará registrado con su descripción.</p>
        <label>Fecha <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} required /></label>
        <label>Monto (+/-) <input type="number" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} required /></label>
        <label>Descripción (mín 5 chars) <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} minLength="5" required /></label>
        {error && <p role="alert" className="error-banner">{error}</p>}
        <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Confirmar ajuste"}</button>
      </form>
    </Modal>
  );
}
