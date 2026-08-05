import { useState } from "react";
import Modal from "./Modal";
import { pagarGasto } from "../api/gastos";

export default function ModalPagarGasto({ gasto, cajas, onClose, onPagado }) {
  const [monto, setMonto] = useState(String(gasto.monto));
  const [fechaPago, setFechaPago] = useState(
    () => new Date().toISOString().slice(0, 10),
  );
  const [cajaId, setCajaId] = useState(String(gasto.caja_id ?? ""));
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    const r = await pagarGasto(gasto.id, {
      monto: Number(monto),
      fecha_pago: fechaPago,
      caja_id: Number(cajaId),
    });
    setEnviando(false);

    if (r.status === 200) {
      onPagado(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 404) {
      setError("El gasto ya no existe.");
      return;
    }
    if (r.status === 409) {
      setError(r.data?.detail || "El gasto ya figura como pagado.");
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <Modal titulo="Confirmar pago" onClose={onClose}>
      <form onSubmit={onSubmit} noValidate>
        <p className="meta">{gasto.concepto}</p>
        <label>
          Monto real de la factura
          <input
            type="number"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            min="0.01"
            step="0.01"
            required
            autoFocus
          />
        </label>
        <label>
          Fecha de pago
          <input
            type="date"
            value={fechaPago}
            onChange={(e) => setFechaPago(e.target.value)}
            required
          />
        </label>
        <label>
          Caja
          <select
            value={cajaId}
            onChange={(e) => setCajaId(e.target.value)}
            required
          >
            <option value="">— Seleccioná una caja —</option>
            {cajas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
        </label>

        {error && <p role="alert" className="error-banner">{error}</p>}

        <div className="modal-acciones">
          <button
            type="button"
            className="boton-secundario"
            onClick={onClose}
            disabled={enviando}
          >
            Cancelar
          </button>
          <button type="submit" disabled={enviando || !cajaId}>
            {enviando ? "Confirmando…" : "Confirmar pago"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
