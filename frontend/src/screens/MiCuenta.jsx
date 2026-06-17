import { useEffect, useState } from "react";
import { listarMisMovimientos } from "../api/movimientos";
import { presentarComprobante } from "../api/comprobantes";
import Modal from "../components/Modal";
import Tarjeta from "../components/Tarjeta";

const TIPO_LABEL = {
  expensa_emitida: "Expensa emitida",
  pago_recibido: "Pago",
  interes_punitorio: "Interés",
  nota_debito: "Nota de débito",
  nota_credito: "Nota de crédito",
};

const TIPO_SIGNO = {
  expensa_emitida: "+",
  pago_recibido: "-",
  interes_punitorio: "+",
  nota_debito: "+",
  nota_credito: "-",
};

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
  });
}

export default function MiCuenta() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);

  async function cargar() {
    setError(null);
    const res = await listarMisMovimientos();
    if (!res.ok) {
      setError(res.data?.detail || "Error cargando la cuenta corriente.");
      return;
    }
    setData(res.data);
  }

  useEffect(() => {
    cargar();
  }, []);

  if (error) {
    return (
      <main className="pantalla">
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="pantalla">
        <p>Cargando cuenta corriente…</p>
      </main>
    );
  }

  const saldo = data.saldo_total;
  const saldoColor =
    saldo > 0
      ? "var(--color-danger)"
      : saldo < 0
        ? "var(--color-success, #1f8a3a)"
        : "var(--color-text)";
  const saldoTexto =
    saldo > 0
      ? "Saldo pendiente."
      : saldo < 0
        ? "Tenés saldo a favor."
        : "Estás al día.";

  return (
    <main className="pantalla">
      <header className="pantalla-encabezado">
        <h1>Mi cuenta</h1>
        <button type="button" onClick={() => setShowModal(true)}>
          + Presentar pago
        </button>
      </header>

      <Tarjeta>
        <p style={{ fontSize: "1.4rem", margin: 0, color: saldoColor }}>
          <strong>Saldo: {formatMoney(saldo)}</strong>
        </p>
        <p style={{ margin: "0.4rem 0 0", color: "var(--color-text-muted, #666)" }}>
          {saldoTexto}
        </p>
      </Tarjeta>

      <section>
        <h2>Movimientos</h2>
        {data.movimientos.length === 0 ? (
          <p>No hay movimientos.</p>
        ) : (
          <table className="tabla-movimientos">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Descripción</th>
                <th>Monto</th>
              </tr>
            </thead>
            <tbody>
              {data.movimientos.map((m) => (
                <tr key={m.id}>
                  <td>{m.fecha}</td>
                  <td>{TIPO_LABEL[m.tipo] || m.tipo}</td>
                  <td>{m.descripcion}</td>
                  <td>
                    {TIPO_SIGNO[m.tipo] || ""}
                    {formatMoney(m.monto)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {showModal && (
        <ModalPresentarPago
          onClose={() => setShowModal(false)}
          onDone={() => {
            setShowModal(false);
            cargar();
          }}
        />
      )}
    </main>
  );
}

function ModalPresentarPago({ onClose, onDone }) {
  const [fechaPago, setFechaPago] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [monto, setMonto] = useState("");
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
    <Modal titulo="Presentar pago" onClose={onClose}>
      <form onSubmit={submit}>
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
        <label>
          Comprobante (opcional)
          <input
            type="file"
            accept="image/*,application/pdf"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
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
