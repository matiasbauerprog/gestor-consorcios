import { useEffect, useState } from "react";
import { obtenerEstadoFinanciero, abrirPdfEstadoFinanciero } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

export default function ReporteEstadoFinanciero() {
  const { token } = useAuth();
  const [rep, setRep] = useState(null);
  const [error, setError] = useState(null);
  const [fechaCorte, setFechaCorte] = useState(
    new Date().toISOString().slice(0, 10)
  );

  async function cargar() {
    const r = await obtenerEstadoFinanciero(fechaCorte);
    if (r.status === 200) {
      setRep(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudo cargar el reporte.");
    }
  }

  useEffect(() => {
    cargar();
  }, [fechaCorte]);

  if (error) return <p role="alert" className="error-banner">{error}</p>;
  if (!rep) return <p>Cargando…</p>;

  return (
    <main>
      <section>
        <header className="cabecera-pantalla">
          <h2>Estado financiero</h2>
          <button
            type="button"
            onClick={() => abrirPdfEstadoFinanciero(fechaCorte)}
          >
            📄 Descargar PDF
          </button>
        </header>

        <label style={{ display: "block", marginBottom: "1em" }}>
          Fecha de corte:{" "}
          <input
            type="date"
            value={fechaCorte}
            onChange={(e) => setFechaCorte(e.target.value)}
          />
        </label>

        <Tarjeta>
          <h3>ACTIVO</h3>
          <table>
            <tbody>
              {rep.cajas.map((c) => (
                <tr key={c.caja_id}>
                  <td>{c.nombre}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(c.saldo)}</td>
                </tr>
              ))}
              <tr>
                <td>Deudores (saldos a cobrar)</td>
                <td style={{ textAlign: "right" }}>
                  {fmtMoney(rep.deudores_total)}
                </td>
              </tr>
              <tr
                style={{
                  fontWeight: "bold",
                  borderTop: "2px solid var(--color-border-strong)",
                }}
              >
                <td>TOTAL ACTIVO</td>
                <td style={{ textAlign: "right" }}>
                  {fmtMoney(rep.activo_total)}
                </td>
              </tr>
            </tbody>
          </table>
        </Tarjeta>

        <Tarjeta>
          <h3>PASIVO</h3>
          {rep.pasivos.length === 0 ? (
            <p>Sin pasivos registrados.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Proveedor</th>
                  <th>Concepto</th>
                  <th>Importe</th>
                </tr>
              </thead>
              <tbody>
                {rep.pasivos.map((p) => (
                  <tr key={p.gasto_id}>
                    <td>{p.proveedor}</td>
                    <td>{p.concepto}</td>
                    <td style={{ textAlign: "right" }}>
                      {fmtMoney(p.monto)}
                    </td>
                  </tr>
                ))}
                <tr
                  style={{
                    fontWeight: "bold",
                    borderTop: "2px solid var(--color-border-strong)",
                  }}
                >
                  <td colSpan="2">TOTAL PASIVO</td>
                  <td style={{ textAlign: "right" }}>
                    {fmtMoney(rep.pasivo_total)}
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </Tarjeta>

        <Tarjeta>
          <h2>PATRIMONIO NETO: {fmtMoney(rep.patrimonio_neto)}</h2>
        </Tarjeta>
      </section>
    </main>
  );
}
