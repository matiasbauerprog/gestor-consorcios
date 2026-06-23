import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { obtenerEstadoFinanciero } from "../api/estadoFinanciero";
import Tarjeta from "../components/Tarjeta";
import ModalNuevaTransferencia from "../components/ModalNuevaTransferencia";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function EstadoFinanciero() {
  const [data, setData] = useState(null);
  const [modalTransfer, setModalTransfer] = useState(false);

  async function cargar() {
    const r = await obtenerEstadoFinanciero();
    if (r.status === 200) setData(r.data);
  }

  useEffect(() => { cargar(); }, []);

  if (!data) return <p>Cargando…</p>;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Estado financiero</h2>
        <button type="button" onClick={() => setModalTransfer(true)}>
          🔄 Transferir entre cajas
        </button>
      </header>

      <Tarjeta>
        <h3>Total general</h3>
        <p style={{ fontSize: "1.5em" }}><strong>{fmtMoney(data.total)}</strong></p>
      </Tarjeta>

      <div className="grid-cajas" style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
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
        <h3>Últimos 20 movimientos</h3>
        {data.ultimos_movimientos.length === 0 ? (
          <p>Sin movimientos.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Fecha</th><th>Caja</th><th>Tipo</th><th>Monto</th><th>Descripción</th>
              </tr>
            </thead>
            <tbody>
              {data.ultimos_movimientos.map((m) => {
                const caja = data.cajas.find((c) => c.id === m.caja_id);
                return (
                  <tr key={m.id}>
                    <td>{m.fecha}</td>
                    <td>{caja?.nombre || m.caja_id}</td>
                    <td>{m.tipo}</td>
                    <td>{fmtMoney(m.monto)}</td>
                    <td>{m.descripcion}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Tarjeta>

      {modalTransfer && (
        <ModalNuevaTransferencia
          cajas={data.cajas}
          onClose={() => setModalTransfer(false)}
          onCreada={() => { setModalTransfer(false); cargar(); }}
        />
      )}
    </section>
  );
}
