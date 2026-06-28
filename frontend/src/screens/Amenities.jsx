import { useEffect, useState } from "react";
import { listarAmenities, darDeBajaAmenity } from "../api/amenities";
import ModalAmenity from "../components/ModalAmenity";

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

      <ul className="lista-cards">
        {items.length === 0 ? (
          <li className="vacio">Sin amenities.</li>
        ) : items.map((a) => (
          <li key={a.id} className={`card-amenity${a.activo ? "" : " inactivo"}`}>
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
          </li>
        ))}
      </ul>

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
