import { useEffect, useState } from "react";
import { listarTrabajos, crearTrabajo } from "../api/trabajos";
import { listarPeticiones } from "../api/peticiones";
import ModalDetalleTrabajo from "../components/ModalDetalleTrabajo";

const ETIQUETAS_ESTADO = {
  en_curso: "En curso",
  finalizado: "Finalizado",
  cancelado: "Cancelado",
};

/** Los que siguen abiertos van arriba; finalizados y cancelados, después. */
function ordenarEnCursoPrimero(lista) {
  const enCurso = (t) => (t.estado === "en_curso" ? 0 : 1);
  return [...lista].sort((a, b) => enCurso(a) - enCurso(b));
}

export default function Trabajos() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [creando, setCreando] = useState(false);
  const [peticiones, setPeticiones] = useState([]);
  const [nuevoDesc, setNuevoDesc] = useState("");
  const [nuevoPetId, setNuevoPetId] = useState("");
  const [error, setError] = useState("");

  async function cargar() {
    const r = await listarTrabajos();
    if (r.status === 200) setItems(ordenarEnCursoPrimero(r.data));
    else setError(r.data?.detail || "No se pudo cargar la lista.");

    const rp = await listarPeticiones();
    if (rp.status === 200) {
      setPeticiones(rp.data.filter((p) => p.estado === "abierta"));
    }
  }

  useEffect(() => {
    cargar();
  }, []);

  async function handleCrear(e) {
    e.preventDefault();
    setError("");
    const payload = { descripcion: nuevoDesc };
    if (nuevoPetId) payload.peticion_id = Number(nuevoPetId);
    const r = await crearTrabajo(payload);
    if (r.status === 201) {
      setCreando(false);
      setNuevoDesc("");
      setNuevoPetId("");
      cargar();
    } else {
      setError(r.data?.detail || "Error al crear el trabajo.");
    }
  }

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Trabajos</h2>
        <button type="button" onClick={() => setCreando(true)}>
          + Nuevo trabajo
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      {creando && (
        <form onSubmit={handleCrear} className="form-creacion">
          <label>
            Petición (opcional){" "}
            <select
              value={nuevoPetId}
              onChange={(e) => setNuevoPetId(e.target.value)}
            >
              <option value="">Sin petición</option>
              {peticiones.map((p) => (
                <option key={p.id} value={p.id}>
                  #{p.id} — {p.titulo}
                </option>
              ))}
            </select>
          </label>
          <label>
            Descripción{" "}
            <textarea
              value={nuevoDesc}
              onChange={(e) => setNuevoDesc(e.target.value)}
              required
              rows={3}
            />
          </label>
          <div className="acciones">
            <button type="submit">Crear</button>
            <button type="button" onClick={() => setCreando(false)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      <table className="tabla-listado">
        <thead>
          <tr>
            <th>#</th>
            <th>Descripción</th>
            <th>Petición</th>
            <th>Estado</th>
            <th>Presup. aprobado</th>
            <th>Gasto</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={6} className="vacio">
                Sin trabajos.
              </td>
            </tr>
          ) : (
            items.map((t) => (
              <tr
                key={t.id}
                onClick={() => setModal(t)}
                style={{ cursor: "pointer" }}
              >
                <td>{t.id}</td>
                <td>{t.descripcion}</td>
                <td>{t.peticion_id || "—"}</td>
                <td>{ETIQUETAS_ESTADO[t.estado] || t.estado}</td>
                <td>{t.presupuesto_aprobado_id || "—"}</td>
                <td>{t.gasto_id || "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {modal && (
        <ModalDetalleTrabajo
          trabajo={modal}
          onClose={() => setModal(null)}
          onActualizado={() => {
            setModal(null);
            cargar();
          }}
        />
      )}
    </main>
  );
}
