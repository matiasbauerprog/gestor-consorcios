import { useState } from "react";
import Modal from "./Modal";
import { enviarPdfsDePeriodo } from "../api/pdf";

export default function ModalEnvioPdfs({ periodo, periodoCerrado, cantidadExpensas, onClose, onCompletado }) {
  // Si está cerrado, no necesita confirmar. Si no, el checkbox debe estar tildado para habilitar.
  const [confirmado, setConfirmado] = useState(periodoCerrado);
  const [enviando, setEnviando] = useState(false);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState(null);

  async function handleEnviar() {
    setEnviando(true);
    setError(null);
    const r = await enviarPdfsDePeriodo(periodo, !periodoCerrado);
    setEnviando(false);
    if (r.status === 200) {
      setResumen(r.data);
      onCompletado?.(r.data);
    } else if (r.status === 409) {
      setError("El período no está cerrado y no se confirmó el envío. Tildá la confirmación.");
    } else {
      setError(r.data?.detail || "Error al enviar.");
    }
  }

  return (
    <Modal titulo={`Enviar boletas PDF — ${periodo}`} onClose={onClose}>
      {!resumen && (
        <>
          {!periodoCerrado && (
            <div
              style={{
                background: "var(--color-warning-bg)",
                border: "1px solid var(--color-warning)",
                padding: "1em",
                marginBottom: "1em",
                borderRadius: "4px",
              }}
            >
              <strong>⚠ Este período NO está cerrado.</strong>
              <p>
                Las boletas pueden cambiar si después aprobás comprobantes, agregás gastos
                o cerrás el período. Una vez enviadas no podés "desenviarlas".
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={confirmado}
                  onChange={(e) => setConfirmado(e.target.checked)}
                />
                {" "}Sí, entiendo y quiero enviar igual.
              </label>
            </div>
          )}

          <p>
            Vas a enviar <strong>{cantidadExpensas}</strong> boletas por email a los
            departamentos del período <strong>{periodo}</strong>.
          </p>

          {error && <p role="alert" className="error-banner">{error}</p>}

          <div style={{ display: "flex", gap: "0.5em", marginTop: "1em" }}>
            <button type="button" onClick={onClose} disabled={enviando}>Cancelar</button>
            <button
              type="button"
              onClick={handleEnviar}
              disabled={!confirmado || enviando}
            >
              {enviando ? "Enviando…" : "Confirmar envío"}
            </button>
          </div>
        </>
      )}

      {resumen && (
        <>
          <h3>Resumen del envío</h3>
          <p>✅ <strong>{resumen.enviados}</strong> enviados.</p>
          <p>❌ <strong>{resumen.fallaron}</strong> fallaron.</p>
          {resumen.errores.length > 0 && (
            <table style={{ marginTop: "1em", width: "100%" }}>
              <thead>
                <tr><th>Depto</th><th>Email</th><th>Motivo</th></tr>
              </thead>
              <tbody>
                {resumen.errores.map((e, i) => (
                  <tr key={i}>
                    <td>{e.depto_id}</td>
                    <td>{e.email || "—"}</td>
                    <td>{e.motivo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button type="button" onClick={onClose} style={{ marginTop: "1em" }}>Cerrar</button>
        </>
      )}
    </Modal>
  );
}
