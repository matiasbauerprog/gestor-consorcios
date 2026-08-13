import { useEffect, useState } from "react";
import { listarAmenities, darDeBajaAmenity } from "../api/amenities";
import ModalAmenity from "../components/ModalAmenity";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
import { ANCHO_MONTO_DECIMAL } from "../utils/anchosColumnas";

// Encabezados en mayúsculas + letter-spacing: 0.2em (`.tabla-datos thead
// th`) piden más ancho del que sugiere el contenido de estas celdas —
// fórmula calibrada contra el fix real de Cajas.jsx, donde el encabezado
// "ACTIVA" (6 caracteres) no entraba en 8ch y sí en 11ch:
// (6×7.5×1.2 + 24) / 7.15 ≈ 10.9 → 11ch, mismo valor que Cajas terminó
// usando. Fórmula de encabezado: (n×7.5×1.2 + 24) / 7.15, redondeado para
// arriba; se compara contra la fórmula de contenido de anchosColumnas.js
// ((L×8.2×1.2 + 24) / 7.15) y se usa la mayor de las dos.
//
// "Duración máx" (12 car.): encabezado ≈ 18.5 → 19ch. Contenido, techo de
// 3 dígitos ("999 h", 5 car. — una política de horas de reserva no pasa de
// tres cifras en la práctica): ≈ 10.2 → 11ch. Manda el encabezado.
const ANCHO_DURACION = "19ch";
// "Anticipación máx" (16 car.): encabezado ≈ 23.5 → 24ch. Contenido, mismo
// techo de 3 dígitos ("999 días", 8 car.): ≈ 14.4 → 15ch. Manda el
// encabezado.
const ANCHO_ANTICIPACION = "24ch";
// "Máx activas" (11 car.): encabezado ≈ 17.2 → 18ch. Contenido, techo de 2
// dígitos ("99", 2 car. — un tope de reservas activas por depto no pasa de
// dos cifras): ≈ 6.1 → 7ch. Manda el encabezado.
const ANCHO_MAX_ACTIVAS = "18ch";
// "Cancelación" (11 car.): encabezado ≈ 17.2 → 18ch. Contenido, mismo techo
// de 3 dígitos ("999 h antes", 11 car.): ≈ 18.5 → 19ch. Manda el contenido
// por un pelo.
const ANCHO_CANCELACION = "19ch";

export default function Amenities() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [incluirInactivos, setIncluirInactivos] = useState(false);
  const [error, setError] = useState("");

  async function cargar() {
    setError("");
    const r = await listarAmenities({ incluirInactivos });
    if (r.status === 200) setItems(r.data);
    else setError(r.data?.detail || "No se pudo cargar la lista.");
  }

  useEffect(() => { cargar(); }, [incluirInactivos]);

  async function handleDarDeBaja(a) {
    if (!window.confirm(`¿Dar de baja "${a.nombre}"?`)) return;
    const r = await darDeBajaAmenity(a.id);
    if (r.status === 200) cargar();
    else setError(r.data?.detail || "Error al dar de baja.");
  }

  const fmt = (v) => (v === null || v === undefined ? "—" : v);
  const fmtPrecio = (v) =>
    v === null || v === undefined ? "Gratis" : `$${Number(v).toLocaleString("es-AR")}`;

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Amenities</h2>
        <button type="button" onClick={() => setModal("nuevo")}>+ Nuevo amenity</button>
      </header>

      <section className="filtros">
        <label className="label-checkbox">
          <input
            type="checkbox"
            checked={incluirInactivos}
            onChange={(e) => setIncluirInactivos(e.target.checked)}
          />
          Mostrar inactivos
        </label>
      </section>

      {error && <p className="error">{error}</p>}

      <TablaResponsive
        columnas={[
          {
            clave: "nombre",
            titulo: "Nombre",
            prioridad: 1,
            ancho: "auto",
            celda: (a) => (
              <>
                {a.nombre} {!a.activo && <small>(inactivo)</small>}
              </>
            ),
          },
          {
            clave: "precio",
            titulo: "Precio",
            prioridad: 1,
            ancho: ANCHO_MONTO_DECIMAL,
            className: "col-monto",
            celda: (a) => fmtPrecio(a.precio_reserva),
          },
          {
            clave: "duracion",
            titulo: "Duración máx",
            prioridad: 2,
            ancho: ANCHO_DURACION,
            celda: (a) => `${fmt(a.duracion_maxima_horas)} h`,
          },
          {
            clave: "anticipacion",
            titulo: "Anticipación máx",
            prioridad: 3,
            ancho: ANCHO_ANTICIPACION,
            celda: (a) => `${fmt(a.anticipacion_maxima_dias)} días`,
          },
          {
            clave: "maxActivas",
            titulo: "Máx activas",
            prioridad: 3,
            ancho: ANCHO_MAX_ACTIVAS,
            celda: (a) => fmt(a.max_reservas_activas_por_depto),
          },
          {
            clave: "cancelacion",
            titulo: "Cancelación",
            prioridad: 3,
            ancho: ANCHO_CANCELACION,
            celda: (a) => `${fmt(a.horas_minimas_cancelacion)} h antes`,
          },
          {
            clave: "acciones",
            titulo: "",
            className: "col-acciones",
            prioridad: 1,
            ancho: "4rem",
            celda: (a) => (
              <MenuAcciones
                etiqueta={`Acciones de ${a.nombre}`}
                acciones={[
                  { label: "Editar", onSelect: () => setModal(a) },
                  ...(a.activo
                    ? [{ label: "Dar de baja", onSelect: () => handleDarDeBaja(a), peligro: true }]
                    : []),
                ]}
              />
            ),
          },
        ]}
        filas={items}
        claveFila={(a) => a.id}
        vacio="Sin amenities."
        renderTarjeta={(a) => (
          <Tarjeta className={a.activo ? "" : "inactivo"}>
            <h3>{a.nombre} {!a.activo && <small>(inactivo)</small>}</h3>
            {a.descripcion && <p>{a.descripcion}</p>}
            <dl className="amenity-policies">
              <div><dt>Precio:</dt><dd>{fmtPrecio(a.precio_reserva)}</dd></div>
              <div><dt>Duración máx:</dt><dd>{fmt(a.duracion_maxima_horas)} h</dd></div>
              <div><dt>Anticipación máx:</dt><dd>{fmt(a.anticipacion_maxima_dias)} días</dd></div>
              <div><dt>Máx activas por depto:</dt><dd>{fmt(a.max_reservas_activas_por_depto)}</dd></div>
              <div><dt>Cancelación gratuita ≥:</dt><dd>{fmt(a.horas_minimas_cancelacion)} h antes</dd></div>
            </dl>
            <div className="acciones">
              <button type="button" onClick={() => setModal(a)}>Editar</button>
              {a.activo && (
                <button type="button" onClick={() => handleDarDeBaja(a)}>Dar de baja</button>
              )}
            </div>
          </Tarjeta>
        )}
      />

      {modal && (
        <ModalAmenity
          item={modal === "nuevo" ? null : modal}
          onClose={() => setModal(null)}
          onGuardado={() => { setModal(null); cargar(); }}
        />
      )}
    </main>
  );
}
