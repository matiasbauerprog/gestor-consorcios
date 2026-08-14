import { useEffect, useState } from "react";
import { listarAmenities, darDeBajaAmenity } from "../api/amenities";
import ModalAmenity from "../components/ModalAmenity";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
import { ANCHO_MONTO_DECIMAL } from "../utils/anchosColumnas";

// Estos anchos se presupuestan SOLO desde los datos, no desde el label del
// encabezado. Antes se inflaban para que el título mayúscula/letter-spacing
// de `.tabla-datos thead th` entrara en una sola línea sin derramarse sobre
// la columna vecina (bug de `white-space: nowrap` bajo `table-layout:
// fixed`). Con ese `nowrap` sacado de `index.css` (permite que el header
// envuelva a dos líneas sin costo de layout), el label ya no compite por
// ancho — se recuperan ~28ch en total, que van directo a la columna Nombre
// (`auto`) al no tener que reservarse en estas cuatro.
//
// Fórmula de contenido (igual a anchosColumnas.js): (L×8.2×1.2 + 24) / 7.15,
// redondeado para arriba, L = longitud del string más largo posible.
//
// "999 h" (techo de 3 dígitos — una política de horas de reserva no pasa de
// tres cifras en la práctica), 5 car.: (5×8.2×1.2 + 24) / 7.15 ≈ 10.2 → 11ch.
const ANCHO_DURACION = "11ch";
// "999 días" (mismo techo de 3 dígitos), 8 car.:
// (8×8.2×1.2 + 24) / 7.15 ≈ 14.4 → 15ch.
const ANCHO_ANTICIPACION = "15ch";
// "99" (techo de 2 dígitos — un tope de reservas activas por depto no pasa
// de dos cifras), 2 car.: (2×8.2×1.2 + 24) / 7.15 ≈ 6.1 → 7ch.
const ANCHO_MAX_ACTIVAS = "7ch";
// "999 h antes" (mismo techo de 3 dígitos), 11 car.:
// (11×8.2×1.2 + 24) / 7.15 ≈ 18.5 → 19ch. Sin cambios: acá ya mandaba el
// contenido, no el header.
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
