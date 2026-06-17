import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { crearNota, listarMovimientosDepto } from "../api/movimientos";
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

export default function DepartamentoCuenta() {
  const { id } = useParams();
  const departamentoId = parseInt(id, 10);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [showCredito, setShowCredito] = useState(false);
  const [showDebito, setShowDebito] = useState(false);

  async function cargar() {
    setError(null);
    const res = await listarMovimientosDepto(departamentoId);
    if (!res.ok) {
      setError(res.data?.detail || "Error cargando la cuenta corriente.");
      return;
    }
    setData(res.data);
  }

  useEffect(() => {
    cargar();
  }, [departamentoId]);

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

  return (
    <main className="pantalla">
      <header className="pantalla-encabezado">
        <h1>Cuenta corriente — Depto {departamentoId}</h1>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button type="button" onClick={() => setShowCredito(true)}>
            + Nota de crédito
          </button>
          <button type="button" onClick={() => setShowDebito(true)}>
            + Nota de débito
          </button>
        </div>
      </header>

      <Tarjeta>
        <p style={{ fontSize: "1.4rem", margin: 0, color: saldoColor }}>
          <strong>Saldo: {formatMoney(saldo)}</strong>
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

      {showCredito && (
        <ModalNota
          tipo="nota_credito"
          titulo="Nueva nota de crédito"
          departamentoId={departamentoId}
          onClose={() => setShowCredito(false)}
          onDone={() => {
            setShowCredito(false);
            cargar();
          }}
        />
      )}
      {showDebito && (
        <ModalNota
          tipo="nota_debito"
          titulo="Nueva nota de débito"
          departamentoId={departamentoId}
          onClose={() => setShowDebito(false)}
          onDone={() => {
            setShowDebito(false);
            cargar();
          }}
        />
      )}
    </main>
  );
}

function ModalNota({ tipo, titulo, departamentoId, onClose, onDone }) {
  const [monto, setMonto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const res = await crearNota({
      departamentoId,
      tipo,
      monto: parseFloat(monto),
      descripcion,
      fecha,
    });
    setSubmitting(false);
    if (!res.ok) {
      setError(res.data?.detail || "No se pudo crear la nota.");
      return;
    }
    onDone();
  }

  return (
    <Modal titulo={titulo} onClose={onClose}>
      <form onSubmit={submit}>
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
          Descripción
          <input
            type="text"
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            required
            maxLength={500}
          />
        </label>
        <label>
          Fecha
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <div className="modal-acciones">
          <button type="button" onClick={onClose} disabled={submitting}>
            Cancelar
          </button>
          <button type="submit" disabled={submitting}>
            {submitting ? "Guardando…" : "Crear"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
