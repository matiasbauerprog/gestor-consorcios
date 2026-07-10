import { useEffect, useState } from "react";
import { listarProveedores, abrirPdfProveedores } from "../api/reportes";
import { useAuth } from "../auth/AuthContext";
import Tarjeta from "../components/Tarjeta";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function ReporteProveedores() {
  const { token } = useAuth();
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [items, setItems] = useState([]);

  async function cargar() {
    const r = await listarProveedores({ anio });
    if (r.status === 200) setItems(r.data);
  }

  useEffect(() => { cargar(); }, [anio]);

  const total = items.reduce((acc, it) => acc + it.total_facturado, 0);

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Lista de proveedores</h2>
        <button type="button" onClick={() => abrirPdfProveedores({ anio })}>
          📄 Descargar PDF
        </button>
      </header>

      <label style={{ display: "block", marginBottom: "1em" }}>
        Año:{" "}
        <input type="number" min="2000" max="2100" value={anio} onChange={(e) => setAnio(Number(e.target.value))} />
      </label>

      {items.length === 0 ? (
        <Tarjeta><p>Sin proveedores facturados en {anio}.</p></Tarjeta>
      ) : (
        <table>
          <thead>
            <tr><th>Razón social</th><th>CUIT</th><th>Cant. gastos</th><th>Total facturado</th><th>Último gasto</th></tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.proveedor_id}>
                <td>{it.razon_social}</td>
                <td>{it.cuit}</td>
                <td style={{ textAlign: "center" }}>{it.cantidad_gastos}</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(it.total_facturado)}</td>
                <td>{it.ultimo_gasto || "—"}</td>
              </tr>
            ))}
            <tr style={{ fontWeight: "bold", borderTop: "2px solid var(--color-border-strong)" }}>
              <td colSpan="3">TOTAL</td>
              <td style={{ textAlign: "right" }}>{fmtMoney(total)}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      )}
    </section>
  );
}
