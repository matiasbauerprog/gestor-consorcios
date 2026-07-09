import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarCuentas } from "../api/movimientos";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
  });
}

function estadoDeCuenta(cuenta) {
  if (cuenta.en_mora) return "en_mora";
  if (cuenta.saldo_total < -0.005) return "a_favor";
  return "al_dia";
}

const ESTILOS_ESTADO = {
  en_mora: { color: "#b3261e", label: "En mora" },
  a_favor: { color: "#16a34a", label: "A favor" },
  al_dia: { color: "#6b7280", label: "Al día" },
};

export default function CuentasCorrientes() {
  const [cuentas, setCuentas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [busqueda, setBusqueda] = useState("");

  async function cargar() {
    setCargando(true);
    const r = await listarCuentas();
    if (r.status === 200) {
      setCuentas(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar las cuentas.");
    }
    setCargando(false);
  }

  useEffect(() => { cargar(); }, []);

  if (cargando) return <main className="pantalla"><p>Cargando…</p></main>;

  const q = busqueda.trim().toLowerCase();
  const filtradas = cuentas.filter((c) => {
    if (!q) return true;
    if (c.codigo.toLowerCase().includes(q)) return true;
    if ((c.ubicacion || "").toLowerCase().includes(q)) return true;
    return false;
  });

  const morosos = cuentas.filter((c) => c.en_mora);
  const deudaMorosos = morosos.reduce((s, c) => s + c.saldo_total, 0);

  return (
    <main className="pantalla">
      <header className="padron-cabecera">
        <div>
          <h2 style={{ marginBottom: "0.15rem" }}>Cuentas corrientes</h2>
          <p className="padron-contador">
            {cuentas.length} departamentos · {morosos.length} en mora ·
            deuda vencida {formatMoney(deudaMorosos)}
          </p>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="padron-filtros">
        <input
          type="search"
          placeholder="Buscar unidad o ubicación…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      </div>

      {filtradas.length === 0 ? (
        <p>Sin resultados.</p>
      ) : (
        <table className="tabla-padron">
          <thead>
            <tr>
              <th className="col-unidad">Unidad</th>
              <th>Ubicación</th>
              <th style={{ textAlign: "right" }}>Saldo</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {filtradas.map((c) => {
              const est = estadoDeCuenta(c);
              const cfg = ESTILOS_ESTADO[est];
              return (
                <tr key={c.departamento_id}>
                  <td className="col-unidad">
                    <Link to={`/departamentos/${c.departamento_id}/cuenta`}>
                      {c.codigo}
                    </Link>
                  </td>
                  <td>{c.ubicacion || "—"}</td>
                  <td style={{ textAlign: "right", color: cfg.color, fontWeight: 600 }}>
                    {formatMoney(c.saldo_total)}
                  </td>
                  <td>
                    <span className="estado-badge">
                      <span
                        className="estado-punto"
                        style={{ background: cfg.color }}
                        aria-hidden="true"
                      />
                      {cfg.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}
