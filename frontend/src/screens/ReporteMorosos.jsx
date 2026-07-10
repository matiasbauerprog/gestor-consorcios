import { useEffect, useState } from "react";
import { listarMorosos, abrirPdfMorosos } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

export default function ReporteMorosos() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [soloDeudores, setSoloDeudores] = useState(true);
  const [cargando, setCargando] = useState(true);

  async function cargar() {
    setCargando(true);
    const r = await listarMorosos({ soloDeudores });
    if (r.status === 200) setItems(r.data);
    setCargando(false);
  }

  useEffect(() => {
    cargar();
  }, [soloDeudores]);

  const total = items.reduce((acc, it) => acc + it.saldo, 0);

  return (
    <main>
      <section>
        <header className="cabecera-pantalla">
          <h2>Lista de morosos</h2>
          <button
            type="button"
            onClick={() => abrirPdfMorosos({ soloDeudores })}
          >
            📄 Descargar PDF
          </button>
        </header>

        <label style={{ display: "block", marginBottom: "1em" }}>
          <input
            type="checkbox"
            checked={soloDeudores}
            onChange={(e) => setSoloDeudores(e.target.checked)}
          />
          {" "}Solo deudores (excluir saldos a favor y al día)
        </label>

        {cargando && <p>Cargando…</p>}
        {!cargando && items.length === 0 && (
          <Tarjeta>
            <p>✓ Sin morosos al día de la fecha.</p>
          </Tarjeta>
        )}
        {!cargando && items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Depto</th>
                <th>Saldo</th>
                <th>Períodos vencidos</th>
                <th>Primer venc. impago</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.departamento_id}>
                  <td>{it.departamento_codigo}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(it.saldo)}</td>
                  <td style={{ textAlign: "center" }}>
                    {it.periodos_vencidos_impagos}
                  </td>
                  <td>{it.primer_vencimiento_impago || "—"}</td>
                </tr>
              ))}
              <tr
                style={{
                  fontWeight: "bold",
                  borderTop: "2px solid var(--color-border-strong)",
                }}
              >
                <td>TOTAL</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(total)}</td>
                <td colSpan="2"></td>
              </tr>
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
