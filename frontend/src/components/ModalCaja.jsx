import { useState } from "react";
import Modal from "./Modal";
import { crearCaja, actualizarCaja } from "../api/cajas";

export default function ModalCaja({ caja, onClose, onGuardada }) {
  const esEditar = caja !== null;
  const [nombre, setNombre] = useState(caja?.nombre || "");
  const [tipo, setTipo] = useState(caja?.tipo || "banco");
  const [descripcion, setDescripcion] = useState(caja?.descripcion || "");
  const [saldoInicial, setSaldoInicial] = useState(caja?.saldo_inicial || 0);
  const [activa, setActiva] = useState(caja?.activa ?? true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = esEditar
      ? { nombre, descripcion, activa }
      : { nombre, tipo, descripcion, saldo_inicial: Number(saldoInicial), activa };
    const r = esEditar
      ? await actualizarCaja(caja.id, payload)
      : await crearCaja(payload);
    setGuardando(false);
    if (r.status === 200 || r.status === 201) onGuardada();
    else setError(r.data?.detail || "Error al guardar.");
  }

  return (
    <Modal titulo={esEditar ? "Editar caja" : "Nueva caja"} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label>Nombre <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} required /></label>
        {!esEditar && (
          <>
            <label>Tipo
              <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
                <option value="banco">Banco</option>
                <option value="efectivo">Efectivo</option>
                <option value="fondo_reparacion">Fondo de reparación</option>
                <option value="otro">Otro</option>
              </select>
            </label>
            <label>Saldo inicial <input type="number" step="0.01" value={saldoInicial} onChange={(e) => setSaldoInicial(e.target.value)} /></label>
          </>
        )}
        <label>Descripción <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></label>
        <label><input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Activa</label>
        {error && <p role="alert" className="error-banner">{error}</p>}
        <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
      </form>
    </Modal>
  );
}
