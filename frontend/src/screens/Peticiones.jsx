import { useEffect, useState } from "react";
import { listarPeticiones, crearPeticion } from "../api/peticiones";
import { useAuth } from "../auth/AuthContext";
import ModalDetallePeticion from "../components/ModalDetallePeticion";

const ESTADOS = ["abierta", "convertida_en_trabajo", "rechazada"];

const ETIQUETAS_ESTADO = {
  abierta: "Abierta",
  convertida_en_trabajo: "Convertida en trabajo",
  rechazada: "Rechazada",
};

export default function Peticiones() {
  const { user } = useAuth();
  const esDepto = user?.rol === "departamento";

  const [items, setItems] = useState([]);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [modal, setModal] = useState(null);
  const [creando, setCreando] = useState(false);
  const [nuevoTitulo, setNuevoTitulo] = useState("");
  const [nuevoDesc, setNuevoDesc] = useState("");
  const [error, setError] = useState("");

  async function cargar() {
    const r = await listarPeticiones();
    if (r.status === 200) setItems(r.data);
    else setError(r.data?.detail || "No se pudo cargar la lista.");
  }

  useEffect(() => {
    cargar();
  }, []);

  async function handleCrear(e) {
    e.preventDefault();
    setError("");
    const r = await crearPeticion({
      titulo: nuevoTitulo,
      descripcion: nuevoDesc,
    });
    if (r.status === 201) {
      setCreando(false);
      setNuevoTitulo("");
      setNuevoDesc("");
      cargar();
    } else {
      setError(r.data?.detail || "Error al crear la petición.");
    }
  }

  const visibles = filtroEstado
    ? items.filter((p) => p.estado === filtroEstado)
    : items;

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Peticiones</h2>
        {esDepto && (
          <button type="button" onClick={() => setCreando(true)}>
            + Nueva petición
          </button>
        )}
      </header>

      <section className="filtros">
        <label>
          Estado:{" "}
          <select
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
          >
            <option value="">Todos</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {ETIQUETAS_ESTADO[e]}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error && <p className="error">{error}</p>}

      {creando && (
        <form onSubmit={handleCrear} className="form-creacion">
          <label>
            Título{" "}
            <input
              value={nuevoTitulo}
              onChange={(e) => setNuevoTitulo(e.target.value)}
              required
              maxLength={255}
            />
          </label>
          <label>
            Descripción{" "}
            <textarea
              value={nuevoDesc}
              onChange={(e) => setNuevoDesc(e.target.value)}
              required
              rows={4}
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
            <th>Depto</th>
            <th>Título</th>
            <th>Estado</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          {visibles.length === 0 ? (
            <tr>
              <td colSpan={5} className="vacio">
                Sin peticiones.
              </td>
            </tr>
          ) : (
            visibles.map((p) => (
              <tr
                key={p.id}
                onClick={() => setModal(p)}
                style={{ cursor: "pointer" }}
              >
                <td>{p.id}</td>
                <td>{p.departamento_id}</td>
                <td>{p.titulo}</td>
                <td>{ETIQUETAS_ESTADO[p.estado] || p.estado}</td>
                <td>{new Date(p.fecha_creacion).toLocaleDateString()}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {modal && (
        <ModalDetallePeticion
          peticion={modal}
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
