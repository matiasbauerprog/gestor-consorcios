import { useEffect, useState } from "react";
import {
  listarRecurrentes,
  eliminarRecurrente,
  materializarRecurrente,
} from "../api/trabajosRecurrentes";
import ModalRecurrente from "../components/ModalRecurrente";

const PERIODICIDADES = {
  mensual: "Mensual",
  trimestral: "Trimestral",
  semestral: "Semestral",
  anual: "Anual",
};

export default function TrabajosRecurrentes() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  async function cargar() {
    const r = await listarRecurrentes();
    if (r.status === 200) setItems(r.data);
    else setError(r.data?.detail || "No se pudo cargar la lista.");
  }

  useEffect(() => {
    cargar();
  }, []);

  async function handleBorrar(it) {
    setError("");
    if (!window.confirm(`¿Eliminar "${it.nombre}"?`)) return;
    const r = await eliminarRecurrente(it.id);
    if (r.status === 204) cargar();
    else setError(r.data?.detail || "Error al eliminar.");
  }

  async function handleMaterializar(it) {
    setError("");
    setInfo("");
    const r = await materializarRecurrente(it.id);
    if (r.status === 201) {
      setInfo(`Trabajo creado: #${r.data.id}. Ver en /trabajos.`);
    } else {
      setError(r.data?.detail || "Error al materializar.");
    }
  }

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Trabajos recurrentes (plantillas)</h2>
        <button type="button" onClick={() => setModal("nuevo")}>
          + Nueva plantilla
        </button>
      </header>

      {info && <p className="info">{info}</p>}
      {error && <p className="error">{error}</p>}

      <table className="tabla-listado">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Descripción</th>
            <th>Periodicidad</th>
            <th>Monto estimado</th>
            <th>Activa</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={6} className="vacio">
                Sin plantillas.
              </td>
            </tr>
          ) : (
            items.map((it) => (
              <tr key={it.id}>
                <td>{it.nombre}</td>
                <td>{it.descripcion}</td>
                <td>{PERIODICIDADES[it.periodicidad] || it.periodicidad}</td>
                <td>
                  {it.monto_estimado
                    ? `$${Number(it.monto_estimado).toLocaleString("es-AR")}`
                    : "—"}
                </td>
                <td>{it.activa ? "Sí" : "No"}</td>
                <td>
                  <button type="button" onClick={() => setModal(it)}>
                    Editar
                  </button>{" "}
                  <button
                    type="button"
                    onClick={() => handleMaterializar(it)}
                    disabled={!it.activa}
                  >
                    Materializar
                  </button>{" "}
                  <button type="button" onClick={() => handleBorrar(it)}>
                    Borrar
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {modal && (
        <ModalRecurrente
          item={modal === "nuevo" ? null : modal}
          onClose={() => setModal(null)}
          onGuardado={() => {
            setModal(null);
            cargar();
          }}
        />
      )}
    </main>
  );
}
