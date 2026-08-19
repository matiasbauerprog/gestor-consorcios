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

export default function CuentasCorrientes({ embebida = false }) {
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

  // Embebida dentro de Cobranzas es una pestaña más (hermana de Expensas y
  // Comprobantes): no abre <main> propio ni repite el título, que ya lo pone
  // la cabecera de la sección.
  const Contenedor = embebida ? "section" : "main";
  const claseContenedor = embebida ? "pantalla pantalla-ancha" : "pantalla";

  if (cargando)
    return <Contenedor className={claseContenedor}><p>Cargando…</p></Contenedor>;

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
    <Contenedor className={claseContenedor}>
      <header className="padron-cabecera">
        <div>
          {!embebida && (
            <h2 style={{ marginBottom: "0.15rem" }}>Cuentas corrientes</h2>
          )}
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
          // `col-unidad` (además de fijar el ancho) trae `font-weight: 700`
          // en index.css — el código de unidad es el identificador de la
          // fila y va destacado, igual que en la tabla vieja.
          { clave: "unidad", titulo: "Unidad", prioridad: 1, ancho: "12ch", className: "col-unidad",
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
            <Tarjeta className="tarjeta-cuenta">
              <h3>
                <Link to={`/departamentos/${c.departamento_id}/cuenta`}>{c.codigo}</Link>
              </h3>
              <p className="meta">{c.ubicacion || "—"}</p>
              {/* Sin "meta": `.tarjeta .meta` (0,2,0) fija color: var(--color-
                  text-muted) y le ganaba a `.saldo-cuenta--*` (0,1,0) — el
                  saldo se veía siempre gris en mobile, tapando todo el
                  refactor de color. `.saldo-cuenta` trae su propio
                  font-size/margin (index.css) para no perder el ritmo
                  tipográfico de las demás líneas "meta" de la tarjeta. */}
              <p className={`saldo-cuenta saldo-cuenta--${cfg.clase}`}>
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
    </Contenedor>
  );
}
