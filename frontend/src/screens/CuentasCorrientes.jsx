import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarCuentas } from "../api/movimientos";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import { ANCHO_MONTO_DECIMAL } from "../utils/anchosColumnas";

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

// `clase` alimenta los modificadores `.estado-punto--*` / `.saldo-cuenta--*`
// de index.css — el color siempre sale de un token `var(--color-...)`, nunca
// de un hex hardcodeado acá.
const ESTILOS_ESTADO = {
  en_mora: { clase: "en-mora", label: "En mora" },
  a_favor: { clase: "a-favor", label: "A favor" },
  al_dia: { clase: "al-dia", label: "Al día" },
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

      <TablaResponsive
        columnas={[
          { clave: "unidad", titulo: "Unidad", prioridad: 1, ancho: "12ch",
            celda: (c) => (
              <Link to={`/departamentos/${c.departamento_id}/cuenta`}>{c.codigo}</Link>
            ) },
          { clave: "ubicacion", titulo: "Ubicación", prioridad: 3, ancho: "auto",
            celda: (c) => c.ubicacion || "—" },
          // `formatMoney` acá deja 2 decimales (sin `maximumFractionDigits`)
          // — ANCHO_MONTO_DECIMAL, no ANCHO_MONTO.
          { clave: "saldo", titulo: "Saldo", prioridad: 1, ancho: ANCHO_MONTO_DECIMAL, className: "col-monto",
            celda: (c) => {
              const cfg = ESTILOS_ESTADO[estadoDeCuenta(c)];
              return (
                <span className={`saldo-cuenta saldo-cuenta--${cfg.clase}`}>
                  {formatMoney(c.saldo_total)}
                </span>
              );
            } },
          { clave: "estado", titulo: "Estado", prioridad: 1, ancho: "14ch",
            celda: (c) => {
              const cfg = ESTILOS_ESTADO[estadoDeCuenta(c)];
              return (
                <span className="estado-badge">
                  <span
                    className={`estado-punto estado-punto--${cfg.clase}`}
                    aria-hidden="true"
                  />
                  {cfg.label}
                </span>
              );
            } },
        ]}
        filas={filtradas}
        claveFila={(c) => c.departamento_id}
        vacio="Sin resultados."
        renderTarjeta={(c) => {
          const cfg = ESTILOS_ESTADO[estadoDeCuenta(c)];
          return (
            <Tarjeta>
              <h3>
                <Link to={`/departamentos/${c.departamento_id}/cuenta`}>{c.codigo}</Link>
              </h3>
              <p className="meta">{c.ubicacion || "—"}</p>
              <p className={`meta saldo-cuenta saldo-cuenta--${cfg.clase}`}>
                {formatMoney(c.saldo_total)}
              </p>
              <span className="estado-badge">
                <span
                  className={`estado-punto estado-punto--${cfg.clase}`}
                  aria-hidden="true"
                />
                {cfg.label}
              </span>
            </Tarjeta>
          );
        }}
      />
    </main>
  );
}
