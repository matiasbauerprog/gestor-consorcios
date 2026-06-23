import { useEffect, useState } from "react";
import { listarTransferencias } from "../api/transferencias";
import { listarCajas } from "../api/cajas";
import ModalNuevaTransferencia from "../components/ModalNuevaTransferencia";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

export default function Transferencias() {
  const [transfers, setTransfers] = useState([]);
  const [cajas, setCajas] = useState([]);
  const [modal, setModal] = useState(false);

  async function cargar() {
    const [t, c] = await Promise.all([listarTransferencias(), listarCajas()]);
    if (t.status === 200) setTransfers(t.data);
    if (c.status === 200) setCajas(c.data);
  }

  useEffect(() => { cargar(); }, []);

  const nombreCaja = (id) => cajas.find((c) => c.id === id)?.nombre || `#${id}`;

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Transferencias entre cajas</h2>
        <button type="button" onClick={() => setModal(true)}>+ Nueva transferencia</button>
      </header>
      {transfers.length === 0 ? (
        <p>Todavía no hay transferencias registradas.</p>
      ) : (
        <table>
          <thead><tr><th>Fecha</th><th>Origen</th><th>Destino</th><th>Monto</th><th>Descripción</th></tr></thead>
          <tbody>
            {transfers.map((t) => (
              <tr key={t.id}>
                <td>{t.fecha}</td>
                <td>{nombreCaja(t.caja_origen_id)}</td>
                <td>{nombreCaja(t.caja_destino_id)}</td>
                <td>{fmtMoney(t.monto)}</td>
                <td>{t.descripcion}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {modal && (
        <ModalNuevaTransferencia
          cajas={cajas}
          onClose={() => setModal(false)}
          onCreada={() => { setModal(false); cargar(); }}
        />
      )}
    </section>
  );
}
