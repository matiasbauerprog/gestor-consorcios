import { useEffect, useState } from "react";
import { listarCajas, eliminarCaja } from "../api/cajas";
import { listarMovimientos } from "../api/movimientosCaja";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
import ModalCaja from "../components/ModalCaja";
import ModalAjusteCaja from "../components/ModalAjusteCaja";
import { formatFechaCorta } from "../utils/fechas";
import { ANCHO_FECHA_CORTA, ANCHO_MONTO } from "../utils/anchosColumnas";

function fmtMoney(n) {
  return Number(n).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

// Set completo de TipoCaja (backend/models.py) — efectivo, banco,
// fondo_reparacion, otro. Antes de TablaResponsive esta columna mostraba el
// enum crudo sin ancho fijo, así que "fondo_reparacion" se veía entero; con
// `ancho` declarado (obligatorio bajo table-layout: fixed) el mismo valor
// truncaba a "fondo_rep…" — una regresión nueva, no algo que ya viniera
// roto. Mapear a etiqueta legible en vez de agrandar la columna para un
// snake_case sin traducir.
const ETIQUETAS_TIPO_CAJA = {
  banco: "Banco",
  efectivo: "Efectivo",
  fondo_reparacion: "Fondo de reparación",
  otro: "Otro",
};

// "Fondo de reparación" (19 caracteres) es la etiqueta más larga. Misma
// aritmética que utils/anchosColumnas.js (celda bold 700, 0.8125rem, ch≈
// 7.15px, padding 24px): (19×8.2×1.2 + 24) / 7.15 ≈ 29.5 → 30ch (mismo
// valor que ya usa la columna Estado de Peticiones.jsx para un string de
// largo casi idéntico, 21 caracteres). Margen final: 30ch deja ≈190.5px
// vs. 155.8px crudos → ~22%.
const ANCHO_TIPO_CAJA = "30ch";

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

      <TablaResponsive
        columnas={[
          { clave: "nombre", titulo: "Nombre", ancho: "auto",
            celda: (c) => (
              <button type="button" className="boton-link" onClick={() => abrirDetalle(c)}>
                {c.nombre}
              </button>
            ) },
          { clave: "tipo", titulo: "Tipo", prioridad: 2, ancho: ANCHO_TIPO_CAJA,
            celda: (c) => ETIQUETAS_TIPO_CAJA[c.tipo] || c.tipo },
          { clave: "descripcion", titulo: "Descripción", prioridad: 3, ancho: "auto",
            celda: (c) => c.descripcion || "—" },
          { clave: "saldo", titulo: "Saldo", ancho: ANCHO_MONTO, className: "col-monto",
            celda: (c) => fmtMoney(c.saldo_actual) },
          // Presupuestado solo desde el dato ("Sí"/"No", 2 car.), no desde
          // el label "ACTIVA": ese era el caso que motivó sacar `white-space:
          // nowrap` de `.tabla-datos thead th` (index.css) — antes el
          // header, en mayúsculas + letter-spacing: 0.2em, no entraba en
          // 8ch y se derramaba sobre la columna vecina, así que se infló la
          // columna a 11ch solo para el título. Con el header libre de
          // envolver a dos líneas, el ancho vuelve al dato:
          // (2×8.2×1.2 + 24) / 7.15 ≈ 6.1 → 7ch.
          { clave: "activa", titulo: "Activa", prioridad: 3, ancho: "7ch",
            celda: (c) => (c.activa ? "Sí" : "No") },
          { clave: "acciones", titulo: "", ancho: "4rem", className: "col-acciones",
            celda: (c) => (
              <MenuAcciones
                etiqueta={`Acciones de ${c.nombre}`}
                acciones={[
                  { label: "Editar", onSelect: () => setModalCaja(c) },
                  { label: "Ajuste", onSelect: () => setModalAjuste(c) },
                  { label: "Borrar", onSelect: () => borrar(c), peligro: true },
                ]}
              />
            ) },
        ]}
        filas={cajas}
        claveFila={(c) => c.id}
        vacio="Todavía no hay cajas."
        renderTarjeta={(c) => (
          <Tarjeta>
            <h3>{c.nombre}</h3>
            <p className="meta">{ETIQUETAS_TIPO_CAJA[c.tipo] || c.tipo} · {fmtMoney(c.saldo_actual)}</p>
            {c.descripcion && <p className="meta">{c.descripcion}</p>}
            <p className="meta">{c.activa ? "Activa" : "Inactiva"}</p>
            <div className="tarjeta-acciones">
              <button type="button" onClick={() => abrirDetalle(c)}>Movimientos</button>
              <button type="button" onClick={() => setModalCaja(c)}>Editar</button>
              <button type="button" onClick={() => setModalAjuste(c)}>Ajuste</button>
              <button type="button" className="boton-borrar" onClick={() => borrar(c)}>
                Borrar
              </button>
            </div>
          </Tarjeta>
        )}
      />

      {detalleCaja && (
        <Tarjeta>
          <h3>Movimientos de "{detalleCaja.nombre}"</h3>
          <button type="button" onClick={() => setDetalleCaja(null)}>Cerrar</button>
          <TablaResponsive
            columnas={[
              // Fecha corta: este panel vive dentro de la <Tarjeta> de
              // "Movimientos de ..." (contenedor angosto), y compite con
              // Monto por prioridad 1 — el año completo no aporta nada
              // (movimientos recientes del mismo consorcio).
              { clave: "fecha", titulo: "Fecha", prioridad: 1, ancho: ANCHO_FECHA_CORTA,
                celda: (m) => formatFechaCorta(m.fecha) },
              { clave: "tipo", titulo: "Tipo", prioridad: 2, ancho: "12ch",
                celda: (m) => m.tipo },
              { clave: "monto", titulo: "Monto", prioridad: 1, ancho: ANCHO_MONTO, className: "col-monto",
                celda: (m) => fmtMoney(m.monto) },
              { clave: "descripcion", titulo: "Descripción", prioridad: 3, ancho: "auto",
                celda: (m) => m.descripcion },
            ]}
            filas={movimientos}
            claveFila={(m) => m.id}
            vacio="Sin movimientos."
            renderTarjeta={(m) => (
              // Sin <Tarjeta>: este panel ya vive dentro de la <Tarjeta> de
              // "Movimientos de ...", y anidar otra por fila dibujaría una
              // caja dentro de otra caja. `.lista-cards` ya separa cada
              // fila con su propio gap.
              <div>
                <p className="meta"><strong>{formatFechaCorta(m.fecha)}</strong> · {m.tipo} · {fmtMoney(m.monto)}</p>
                {m.descripcion && <p className="meta">{m.descripcion}</p>}
              </div>
            )}
          />
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
