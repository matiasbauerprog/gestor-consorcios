import { useEffect, useState } from "react";
import { obtenerGastosDelPeriodo, abrirPdfGastosPeriodo } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";
import { formatFecha } from "../utils/fechas";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

const NOMBRES_RUBRO = {
  sueldos_y_cargas_sociales: "Sueldos y cargas sociales",
  servicios_publicos: "Servicios públicos",
  abonos_y_servicios: "Abonos y servicios",
  mantenimiento_partes_comunes: "Mantenimiento partes comunes",
  trabajos_reparaciones_unidades: "Trabajos / reparaciones en unidades",
  gastos_bancarios: "Gastos bancarios",
  gastos_administracion: "Gastos administración",
  seguros: "Seguros",
  gastos_generales: "Gastos generales",
};

export default function ReporteGastosPeriodo() {
  const { token } = useAuth();
  const [periodo, setPeriodo] = useState(new Date().toISOString().slice(0, 7));
  const [rubro, setRubro] = useState("");
  const [rep, setRep] = useState(null);
  const [error, setError] = useState(null);

  async function cargar() {
    const r = await obtenerGastosDelPeriodo(periodo, { rubro: rubro || undefined });
    if (r.status === 200) {
      setRep(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudo cargar el reporte.");
    }
  }

  useEffect(() => { cargar(); }, [periodo, rubro]);

  if (error) return <p role="alert" className="error-banner">{error}</p>;
  if (!rep) return <p>Cargando…</p>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Detalle de gastos del período</h2>
        <button type="button" onClick={() => abrirPdfGastosPeriodo(periodo, { rubro: rubro || undefined })}>
          📄 Descargar PDF
        </button>
      </header>

      <div className="filtros" style={{ display: "flex", gap: "1em", marginBottom: "1em", flexWrap: "wrap" }}>
        <label>
          Período:{" "}
          <input type="month" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
        </label>
        <label>
          Rubro:{" "}
          <select value={rubro} onChange={(e) => setRubro(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(NOMBRES_RUBRO).map(([val, lbl]) => (
              <option key={val} value={val}>{lbl}</option>
            ))}
          </select>
        </label>
      </div>

      {Object.entries(rep.por_rubro).map(([rubroKey, items]) => (
        <Tarjeta key={rubroKey}>
          <h3>{NOMBRES_RUBRO[rubroKey] || rubroKey} — {fmtMoney(rep.subtotales_por_rubro[rubroKey])}</h3>
          <table>
            <thead><tr><th>Fecha</th><th>Concepto</th><th>Proveedor</th><th>Caja</th><th>Forma pago</th><th>Importe</th></tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i}>
                  <td>{formatFecha(it.fecha)}</td><td>{it.concepto}</td><td>{it.proveedor}</td>
                  <td>{it.caja}</td><td>{it.forma_pago}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(it.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tarjeta>
      ))}

      {rep.particulares.length > 0 && (
        <Tarjeta>
          <h3>Gastos particulares (a deptos)</h3>
          <table>
            <thead><tr><th>Fecha</th><th>Concepto</th><th>Proveedor</th><th>Caja</th><th>Forma pago</th><th>Importe</th></tr></thead>
            <tbody>
              {rep.particulares.map((it, i) => (
                <tr key={i}>
                  <td>{formatFecha(it.fecha)}</td><td>{it.concepto}</td><td>{it.proveedor}</td>
                  <td>{it.caja}</td><td>{it.forma_pago}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(it.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tarjeta>
      )}

      {rep.total_general === 0 && (
        <Tarjeta><p>Sin gastos en el período {periodo}.</p></Tarjeta>
      )}

      <Tarjeta>
        <h2>TOTAL GENERAL: {fmtMoney(rep.total_general)}</h2>
      </Tarjeta>
    </section>
  );
}
