import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarPeriodos } from "../api/periodos";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function Periodos() {
  const [periodos, setPeriodos] = useState([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    (async () => {
      const r = await listarPeriodos();
      if (r.status === 200) setPeriodos(r.data);
      setCargando(false);
    })();
  }, []);

  if (cargando) return <p>Cargando…</p>;

  return (
    <section>
      <h2>Historial de cierres</h2>
      {periodos.length === 0 ? (
        <p>Todavía no hay períodos cerrados.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Período</th>
              <th>Cerrado el</th>
              <th>Boletas</th>
              <th>Total expensado</th>
              <th>Intereses</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {periodos.map((p) => (
              <tr key={p.periodo}>
                <td>{p.periodo}</td>
                <td>{new Date(p.fecha_cierre).toLocaleString("es-AR")}</td>
                <td>{p.cantidad_expensas}</td>
                <td>{formatMoney(p.total_expensado)}</td>
                <td>{formatMoney(p.total_intereses)}</td>
                <td><Link to={`/expensas?periodo=${p.periodo}`}>Ver expensas</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
