import { useEffect, useState } from "react";
import { listarCajas, eliminarCaja } from "../api/cajas";
import { listarMovimientos } from "../api/movimientosCaja";
import Tarjeta from "../components/Tarjeta";
import ModalCaja from "../components/ModalCaja";
import ModalAjusteCaja from "../components/ModalAjusteCaja";
import { formatFecha } from "../utils/fechas";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

export default function Cajas() {
  const [cajas, setCajas] = useState([]);
  const [modalCaja, setModalCaja] = useState(null);
  const [modalAjuste, setModalAjuste] = useState(null);
  const [detalleCaja, setDetalleCaja] = useState(null);
  const [movimientos, setMovimientos] = useState([]);

  async function cargar() {
    const r = await listarCajas();
    if (r.status === 200) setCajas(r.data);
  }

  useEffect(() => { cargar(); }, []);

  async function abrirDetalle(caja) {
    setDetalleCaja(caja);
    const r = await listarMovimientos(caja.id, { limit: 50 });
    if (r.status === 200) setMovimientos(r.data);
  }

  async function borrar(caja) {
    if (!window.confirm(`¿Eliminar caja "${caja.nombre}"?`)) return;
    const r = await eliminarCaja(caja.id);
    if (r.status === 204) cargar();
    else alert(r.data?.detail || "No se pudo borrar.");
  }

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Cajas</h2>
        <button type="button" onClick={() => setModalCaja("nueva")}>+ Nueva caja</button>
      </header>

      <table>
        <thead>
          <tr>
            <th>Nombre</th><th>Tipo</th><th>Descripción</th><th>Saldo</th><th>Activa</th><th></th>
          </tr>
        </thead>
        <tbody>
          {cajas.map((c) => (
            <tr key={c.id}>
              <td><button type="button" onClick={() => abrirDetalle(c)} style={{textDecoration: "underline"}}>{c.nombre}</button></td>
              <td>{c.tipo}</td>
              <td>{c.descripcion || "—"}</td>
              <td>{fmtMoney(c.saldo_actual)}</td>
              <td>{c.activa ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModalCaja(c)}>Editar</button>
                <button type="button" onClick={() => setModalAjuste(c)}>Ajuste</button>
                <button type="button" onClick={() => borrar(c)}>Borrar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {detalleCaja && (
        <Tarjeta>
          <h3>Movimientos de "{detalleCaja.nombre}"</h3>
          <button type="button" onClick={() => setDetalleCaja(null)}>Cerrar</button>
          <table>
            <thead><tr><th>Fecha</th><th>Tipo</th><th>Monto</th><th>Descripción</th></tr></thead>
            <tbody>
              {movimientos.map((m) => (
                <tr key={m.id}>
                  <td>{formatFecha(m.fecha)}</td>
                  <td>{m.tipo}</td>
                  <td>{fmtMoney(m.monto)}</td>
                  <td>{m.descripcion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Tarjeta>
      )}

      {modalCaja && (
        <ModalCaja
          caja={modalCaja === "nueva" ? null : modalCaja}
          onClose={() => setModalCaja(null)}
          onGuardada={() => { setModalCaja(null); cargar(); }}
        />
      )}

      {modalAjuste && (
        <ModalAjusteCaja
          caja={modalAjuste}
          onClose={() => setModalAjuste(null)}
          onCreado={() => { setModalAjuste(null); cargar(); }}
        />
      )}
    </section>
  );
}
