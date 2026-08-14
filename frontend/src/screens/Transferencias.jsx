import { useEffect, useState } from "react";
import { listarTransferencias } from "../api/transferencias";
import { listarCajas } from "../api/cajas";
import ModalNuevaTransferencia from "../components/ModalNuevaTransferencia";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import { formatFecha, formatFechaCorta } from "../utils/fechas";
import { ANCHO_FECHA_CORTA, ANCHO_MONTO } from "../utils/anchosColumnas";

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
      <TablaResponsive
        columnas={[
          // Fecha corta: cuatro columnas de prioridad 1 compiten por ancho
          // acá (fecha/origen/destino/monto) — el año completo no aporta
          // nada que la fecha corta no dé.
          { clave: "fecha", titulo: "Fecha", prioridad: 1, ancho: ANCHO_FECHA_CORTA,
            celda: (t) => formatFechaCorta(t.fecha) },
          { clave: "origen", titulo: "Origen", prioridad: 1, ancho: "auto",
            celda: (t) => nombreCaja(t.caja_origen_id) },
          { clave: "destino", titulo: "Destino", prioridad: 1, ancho: "auto",
            celda: (t) => nombreCaja(t.caja_destino_id) },
          { clave: "monto", titulo: "Monto", prioridad: 1, ancho: ANCHO_MONTO, className: "col-monto",
            celda: (t) => fmtMoney(t.monto) },
          { clave: "descripcion", titulo: "Descripción", prioridad: 3, ancho: "auto",
            celda: (t) => t.descripcion },
        ]}
        filas={transfers}
        claveFila={(t) => t.id}
        vacio="Todavía no hay transferencias registradas."
        renderTarjeta={(t) => (
          <Tarjeta>
            <h3>{fmtMoney(t.monto)}</h3>
            <p className="meta">{formatFecha(t.fecha)}</p>
            <p className="meta">{nombreCaja(t.caja_origen_id)} → {nombreCaja(t.caja_destino_id)}</p>
            {t.descripcion && <p className="meta">{t.descripcion}</p>}
          </Tarjeta>
        )}
      />
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
