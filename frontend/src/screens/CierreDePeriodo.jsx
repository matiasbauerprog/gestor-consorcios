import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  estadoPeriodo,
  previewPeriodo,
  cerrarPeriodo,
} from "../api/periodos";
import Tarjeta from "../components/Tarjeta";
import ModalEnvioPdfs from "../components/ModalEnvioPdfs";

function periodoActual() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function CierreDePeriodo() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const periodoInicial = searchParams.get("periodo") || periodoActual();
  const [periodo, setPeriodo] = useState(periodoInicial);
  const [estado, setEstado] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [modalEnvio, setModalEnvio] = useState(null);

  useEffect(() => {
    setPreview(null);
    setError(null);
    (async () => {
      const r = await estadoPeriodo(periodo);
      if (r.status === 200) setEstado(r.data);
      else if (r.status !== 401) setError("No se pudo cargar el estado del período.");
    })();
  }, [periodo]);

  async function handleGenerarPreview() {
    setCargando(true);
    const r = await previewPeriodo(periodo);
    setCargando(false);
    if (r.status === 200) setPreview(r.data);
    else setError(r.data?.detail || "No se pudo generar el preview.");
  }

  async function handleConfirmar() {
    if (!preview) return;
    setConfirmando(true);
    const r = await cerrarPeriodo(periodo, {
      fecha_primer_vencimiento: preview.fecha_primer_vencimiento,
      fecha_segundo_vencimiento: preview.fecha_segundo_vencimiento,
    });
    setConfirmando(false);
    if (r.status === 201) {
      // Cierre OK → ofrecer envío de PDFs por email. Al cerrar el modal navegamos a /periodos.
      setModalEnvio({
        periodo,
        cantidadExpensas: preview.expensas.length,
        periodoCerrado: true,
      });
    } else {
      setError(r.data?.detail || "No se pudo cerrar el período.");
    }
  }

  return (
    <section>
      <h2>Cierre de período</h2>
      <label>
        Período:{" "}
        <input
          type="month"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </label>

      {error && <p role="alert" className="error-banner">{error}</p>}

      {!preview && estado && (
        <Tarjeta>
          <h3>Estado de {periodo}</h3>
          {estado.cerrado && <p><strong>⚠ Este período ya fue cerrado.</strong></p>}
          <ul className="lista-validaciones">
            {estado.validaciones.map((v, i) => (
              <li key={i} className={`val-${v.tipo}`}>
                {v.tipo === "bloqueante" ? "✗" : "⚠"} {v.mensaje}
              </li>
            ))}
            {estado.validaciones.length === 0 && <li>✓ Sin observaciones.</li>}
          </ul>
          <button
            type="button"
            onClick={handleGenerarPreview}
            disabled={!estado.puede_cerrar || cargando}
          >
            {cargando ? "Generando…" : "Generar preview"}
          </button>
        </Tarjeta>
      )}

      {modalEnvio && (
        <ModalEnvioPdfs
          periodo={modalEnvio.periodo}
          periodoCerrado={modalEnvio.periodoCerrado}
          cantidadExpensas={modalEnvio.cantidadExpensas}
          onClose={() => {
            setModalEnvio(null);
            navigate("/periodos");
          }}
        />
      )}

      {preview && !modalEnvio && (
        <Tarjeta>
          <h3>Vista previa de cierre — {periodo}</h3>
          <div>
            Total a expensar: <strong>{formatMoney(preview.total_expensado)}</strong>
            {" · "}Boletas: {preview.expensas.length}
            {" · "}Intereses: {formatMoney(preview.total_intereses)}
          </div>
          <ul>
            {preview.expensas.map((e) => (
              <li key={e.departamento_id}>
                Depto {e.departamento_id}: {formatMoney(e.monto_primer_vencimiento)}
                {e.saldo_anterior > 0 && ` + ${formatMoney(e.saldo_anterior)} saldo ant.`}
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => setPreview(null)}>← Volver</button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm("¿Confirmar cierre? Esta acción es irreversible.")) {
                handleConfirmar();
              }
            }}
            disabled={!preview.puede_cerrar || confirmando}
          >
            {confirmando ? "Cerrando…" : "Confirmar cierre del mes"}
          </button>
        </Tarjeta>
      )}
    </section>
  );
}
