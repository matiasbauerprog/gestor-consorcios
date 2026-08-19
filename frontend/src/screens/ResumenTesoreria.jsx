import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { abrirPdfMovimientos, obtenerResumenTesoreria } from "../api/tesoreria";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import ModalNuevaTransferencia from "../components/ModalNuevaTransferencia";
import { formatFechaCorta } from "../utils/fechas";
import { ANCHO_FECHA_CORTA, ANCHO_MONTO } from "../utils/anchosColumnas";

function primerDiaDelMes(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

function hoy() {
  return new Date().toISOString().slice(0, 10);
}

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function ResumenTesoreria() {
  const [data, setData] = useState(null);
  const [modalTransfer, setModalTransfer] = useState(false);
  const [modalPdf, setModalPdf] = useState(false);

  async function cargar() {
    const r = await obtenerResumenTesoreria();
    if (r.status === 200) setData(r.data);
  }

  useEffect(() => { cargar(); }, []);

  if (!data) return <p>Cargando…</p>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Resumen</h2>
        <div className="cabecera-acciones">
          <button type="button" onClick={() => setModalPdf(true)}>
            📄 Descargar movimientos
          </button>
          <button type="button" onClick={() => setModalTransfer(true)}>
            🔄 Transferir entre cajas
          </button>
        </div>
      </header>

      <Tarjeta>
        <h3>Total general</h3>
        <p style={{ fontSize: "1.5em" }}><strong>{fmtMoney(data.total)}</strong></p>
      </Tarjeta>

      <div className="grid-cajas">
        {data.cajas.map((c) => (
          <Link key={c.id} to={`/cajas`} style={{ textDecoration: "none" }}>
            <Tarjeta>
              <h3>{c.nombre}</h3>
              <p className="meta">{c.tipo}</p>
              <p style={{ fontSize: "1.3em" }}><strong>{fmtMoney(c.saldo_actual)}</strong></p>
            </Tarjeta>
          </Link>
        ))}
      </div>

      <Tarjeta>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h3 style={{ margin: 0 }}>Últimos 20 movimientos</h3>
          <button
            type="button"
            className="accion-discreta"
            onClick={() => setModalPdf(true)}
          >
            ver todos por período (PDF)
          </button>
        </div>
        <TablaResponsive
          columnas={[
            // Fecha corta: esta tabla vive dentro de la <Tarjeta> "Últimos
            // 20 movimientos", un contenedor más angosto que .app-content
            // (ver nota de la tarea sobre @container) — cada ch cuenta.
            { clave: "fecha", titulo: "Fecha", prioridad: 1, ancho: ANCHO_FECHA_CORTA,
              celda: (m) => formatFechaCorta(m.fecha) },
            { clave: "caja", titulo: "Caja", prioridad: 2, ancho: "auto",
              celda: (m) => data.cajas.find((c) => c.id === m.caja_id)?.nombre || m.caja_id },
            { clave: "tipo", titulo: "Tipo", prioridad: 3, ancho: "12ch",
              celda: (m) => m.tipo },
            { clave: "monto", titulo: "Monto", prioridad: 1, ancho: ANCHO_MONTO, className: "col-monto",
              celda: (m) => fmtMoney(m.monto) },
            { clave: "descripcion", titulo: "Descripción", prioridad: 3, ancho: "auto",
              celda: (m) => m.descripcion },
          ]}
          filas={data.ultimos_movimientos}
          claveFila={(m) => m.id}
          vacio="Sin movimientos."
          renderTarjeta={(m) => {
            // Sin <Tarjeta>: esta tabla ya vive dentro de la <Tarjeta> de
            // "Últimos 20 movimientos" — anidar otra por fila apilaría cajas
            // dentro de cajas. `.lista-cards` separa cada fila con su gap.
            const caja = data.cajas.find((c) => c.id === m.caja_id);
            return (
              <div>
                <p className="meta"><strong>{fmtMoney(m.monto)}</strong> · {formatFechaCorta(m.fecha)}</p>
                <p className="meta">{caja?.nombre || m.caja_id} · {m.tipo}</p>
                {m.descripcion && <p className="meta">{m.descripcion}</p>}
              </div>
            );
          }}
        />
      </Tarjeta>

      {modalTransfer && (
        <ModalNuevaTransferencia
          cajas={data.cajas}
          onClose={() => setModalTransfer(false)}
          onCreada={() => { setModalTransfer(false); cargar(); }}
        />
      )}

      {modalPdf && (
        <ModalDescargarMovimientos onCerrar={() => setModalPdf(false)} />
      )}
    </section>
  );
}

function ModalDescargarMovimientos({ onCerrar }) {
  const [desde, setDesde] = useState(primerDiaDelMes());
  const [hasta, setHasta] = useState(hoy());
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState(null);

  async function descargar(e) {
    e.preventDefault();
    if (desde > hasta) {
      setErr("La fecha 'desde' no puede ser posterior a 'hasta'.");
      return;
    }
    setErr(null);
    setEnviando(true);
    try {
      await abrirPdfMovimientos({ desde, hasta });
      onCerrar();
    } catch (e) {
      setErr("No se pudo generar el PDF.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Descargar movimientos de caja</h3>
        <p className="meta">
          Genera un PDF con todos los movimientos del rango, agrupados por
          caja y con totales.
        </p>
        <form onSubmit={descargar}>
          <label>
            Desde
            <input type="date" required value={desde}
                   onChange={(e) => setDesde(e.target.value)} />
          </label>
          <label>
            Hasta
            <input type="date" required value={hasta}
                   onChange={(e) => setHasta(e.target.value)} />
          </label>
          {err && <p className="error">{err}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={enviando}>
              {enviando ? "Generando…" : "Descargar PDF"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
