import { useState } from "react";
import { presentarComprobante } from "../api/comprobantes";
import Modal from "./Modal";

export default function ModalPresentarPago({ expensa, onClose, onDone }) {
  const [fechaPago, setFechaPago] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [monto, setMonto] = useState(expensa.monto_primer_vencimiento);
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const res = await presentarComprobante({
      fecha_pago: fechaPago,
      monto: parseFloat(monto),
      archivo,
    });
    setSubmitting(false);
    if (!res.ok) {
      setError(res.data?.detail || "No se pudo registrar el comprobante.");
      return;
    }
    onDone();
  }

  return (
    <Modal titulo={`Presentar pago — Expensa ${expensa.periodo}`} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <p style={{ margin: "0 0 1rem", color: "var(--color-text-muted, #666)" }}>
          Vence el <strong>{expensa.fecha_primer_vencimiento}</strong>
        </p>
        <label>
          Fecha del pago
          <input
            type="date"
            value={fechaPago}
            onChange={(e) => setFechaPago(e.target.value)}
            required
          />
        </label>
        <label>
          Monto
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            required
          />
        </label>
        <p style={{ color: "var(--color-text-muted, #666)", fontSize: "0.85rem", margin: "0.5rem 0 1rem", padding: "0.5rem 0.75rem", borderLeft: "3px solid var(--color-primary, #0d6efd)", background: "rgba(13, 110, 253, 0.05)" }}>
          💡 Tu pago se aplica primero a las deudas más antiguas. Si tenés saldo a favor o pendiente, podés ver el detalle en tu cuenta corriente.
        </p>
        <label>
          Comprobante (imagen JPG/PNG/WebP o PDF)
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            required
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <p style={{ color: "var(--color-text-muted, #666)", fontSize: "0.9rem" }}>
          Tu pago será visible cuando administración lo apruebe.
        </p>
        <div className="modal-acciones">
          <button type="button" onClick={onClose} disabled={submitting}>
            Cancelar
          </button>
          <button type="submit" disabled={submitting}>
            {submitting ? "Enviando…" : "Presentar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
