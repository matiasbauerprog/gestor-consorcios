import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarMisMovimientos } from "../api/movimientos";
import { listarExpensas } from "../api/expensas";
import { listarComprobantes, presentarComprobante } from "../api/comprobantes";
import { abrirPdfExpensa } from "../api/pdf";
import { rutaAdjuntoComprobante } from "../api/archivos";
import ArchivoAdjunto from "../components/ArchivoAdjunto";
import Modal from "../components/Modal";
import TabsPanel from "../components/TabsPanel";
import Tarjeta from "../components/Tarjeta";
import TarjetaExpensa from "../components/TarjetaExpensa";
import BadgeEstado from "../components/BadgeEstado";
import { formatFecha } from "../utils/fechas";

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

const TABS = [
  { valor: "resumen", label: "Resumen" },
  { valor: "expensas", label: "Expensas" },
  { valor: "comprobantes", label: "Comprobantes" },
  { valor: "movimientos", label: "Movimientos" },
];

const TABS_VALIDOS = new Set(TABS.map((t) => t.valor));

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
  });
}

function sumarDias(yyyymmdd, n) {
  const d = new Date(yyyymmdd);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function MiCuenta() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tabActivo = TABS_VALIDOS.has(tabParam) ? tabParam : "resumen";

  const [data, setData] = useState(null);
  const [expensas, setExpensas] = useState([]);
  const [comprobantes, setComprobantes] = useState([]);
  const [error, setError] = useState(null);
  const [modalPagoAbierto, setModalPagoAbierto] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  function cambiarTab(valor) {
    const params = new URLSearchParams(searchParams);
    if (valor === "resumen") params.delete("tab");
    else params.set("tab", valor);
    setSearchParams(params, { replace: true });
  }

  async function cargar() {
    setError(null);
    const res = await listarMisMovimientos();
    if (!res.ok) {
      setError(res.data?.detail || "Error cargando la cuenta corriente.");
      return;
    }
    setData(res.data);
  }

  async function cargarExpensas() {
    const res = await listarExpensas();
    if (res.ok) {
      setExpensas(res.data);
    }
  }

  async function cargarComprobantes() {
    const res = await listarComprobantes();
    if (res.ok) {
      setComprobantes(res.data);
    }
  }

  useEffect(() => {
    cargar();
    cargarExpensas();
    cargarComprobantes();
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
        ? "var(--color-success)"
        : "var(--color-text)";
  const saldoTexto =
    saldo > 0
      ? "Saldo pendiente."
      : saldo < 0
        ? "Tenés saldo a favor."
        : "Estás al día.";

  const montoInicialPago = saldo > 0 ? saldo : "";

  return (
    <main className="pantalla">
      <header className="cabecera-pantalla">
        <h2>Mi cuenta</h2>
        <button type="button" onClick={() => setModalPagoAbierto(true)}>
          + Presentar pago
        </button>
      </header>

      {successMsg && (
        <p role="status" className="banner-exito">
          ✓ {successMsg}
        </p>
      )}

      <TabsPanel
        items={TABS}
        activo={tabActivo}
        onCambio={cambiarTab}
        ariaLabel="Secciones de mi cuenta"
      />

      {tabActivo === "resumen" && (
        <SeccionResumen
          saldo={saldo}
          saldoColor={saldoColor}
          saldoTexto={saldoTexto}
          expensas={expensas}
          token={token}
        />
      )}

      {tabActivo === "expensas" && (
        <SeccionExpensas expensas={expensas} token={token} />
      )}

      {tabActivo === "comprobantes" && (
        <SeccionComprobantes comprobantes={comprobantes} />
      )}

      {tabActivo === "movimientos" && (
        <SeccionMovimientos movimientos={data.movimientos} />
      )}

      {modalPagoAbierto && (
        <ModalPresentarPago
          montoInicial={montoInicialPago}
          onClose={() => setModalPagoAbierto(false)}
          onDone={() => {
            setModalPagoAbierto(false);
            setSuccessMsg(
              "Comprobante enviado. Va a quedar pendiente hasta que administración lo apruebe.",
            );
            cargar();
            cargarExpensas();
            cargarComprobantes();
          }}
        />
      )}
    </main>
  );
}

function SeccionResumen({ saldo, saldoColor, saldoTexto, expensas, token }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const proximaExpensa = expensas
    .filter((e) => e.fecha_primer_vencimiento >= hoy)
    .sort((a, b) =>
      a.fecha_primer_vencimiento.localeCompare(b.fecha_primer_vencimiento),
    )[0];

  async function handleAbrirPdf() {
    if (!proximaExpensa) return;
    try {
      await abrirPdfExpensa(proximaExpensa.id);
    } catch (e) {
      alert(`No se pudo abrir el PDF: ${e.message}`);
    }
  }

  return (
    <>
      <Tarjeta>
        <p style={{ fontSize: "1.4rem", margin: 0, color: saldoColor }}>
          <strong>Saldo: {formatMoney(saldo)}</strong>
        </p>
        <p style={{ margin: "0.4rem 0 0", color: "var(--color-text-muted)" }}>
          {saldoTexto}
        </p>
      </Tarjeta>

      {proximaExpensa && (
        <Tarjeta>
          <h3>Próximo vencimiento</h3>
          <p>
            Si pagás hasta el {formatFecha(proximaExpensa.fecha_primer_vencimiento)}:{" "}
            <strong>{formatMoney(proximaExpensa.monto_primer_vencimiento)}</strong>
          </p>
          <p>
            Del {formatFecha(sumarDias(proximaExpensa.fecha_primer_vencimiento, 1))} al{" "}
            {formatFecha(proximaExpensa.fecha_segundo_vencimiento)}:{" "}
            <strong>{formatMoney(proximaExpensa.monto_segundo_vencimiento)}</strong>{" "}
            (+recargo)
          </p>
          <p className="meta">
            Después del {formatFecha(proximaExpensa.fecha_segundo_vencimiento)}: se acumulan
            intereses mensuales.
          </p>
          <div className="tarjeta-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={handleAbrirPdf}
            >
              📄 Ver PDF
            </button>
          </div>
        </Tarjeta>
      )}
    </>
  );
}

function SeccionExpensas({ expensas, token }) {
  if (expensas.length === 0) {
    return <p>No hay expensas.</p>;
  }
  return (
    <ul className="lista-expensas">
      {expensas.map((e) => (
        <li key={e.id}>
          <TarjetaExpensa
            expensa={e}
            esAdmin={false}
            depto={null}
            token={token}
            mostrarBotonComprobantes={false}
          />
        </li>
      ))}
    </ul>
  );
}

function SeccionComprobantes({ comprobantes }) {
  if (comprobantes.length === 0) {
    return <p>No hay comprobantes.</p>;
  }
  return (
    <ul className="lista-comprobantes">
      {comprobantes.map((c) => (
        <li key={c.id}>
          <Tarjeta>
            <h3>{formatMoney(c.monto)}</h3>
            <p className="meta">Pagado {formatFecha(c.fecha_pago)}</p>
            <p><BadgeEstado estado={c.estado} /></p>
            {/* Es la pantalla donde el departamento se entera de que le
                rechazaron el pago: el motivo tiene que estar acá, no sólo del
                lado de administración. */}
            {c.estado === "rechazado" && c.motivo_rechazo && (
              <p className="meta">Motivo: {c.motivo_rechazo}</p>
            )}
            {c.archivo_path && (
              <ArchivoAdjunto
                ruta={rutaAdjuntoComprobante(c)}
                alt="Comprobante"
                className="comprobante-img"
              />
            )}
          </Tarjeta>
        </li>
      ))}
    </ul>
  );
}

function SeccionMovimientos({ movimientos }) {
  if (movimientos.length === 0) {
    return <p>No hay movimientos.</p>;
  }
  return (
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
        {movimientos.map((m) => (
          <tr key={m.id}>
            <td>{formatFecha(m.fecha)}</td>
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
  );
}

function ModalPresentarPago({ montoInicial, onClose, onDone }) {
  const [fechaPago, setFechaPago] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [monto, setMonto] = useState(
    montoInicial ? String(montoInicial) : "",
  );
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
      <form onSubmit={submit} noValidate>
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
          Comprobante (imagen JPG/PNG/WebP o PDF)
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            required
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem" }}>
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
