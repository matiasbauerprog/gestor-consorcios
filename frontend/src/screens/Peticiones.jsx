import { useEffect, useState } from "react";
import { listarPeticiones, crearPeticion } from "../api/peticiones";
import { useAuth } from "../auth/AuthContext";
import ModalDetallePeticion from "../components/ModalDetallePeticion";
import TablaResponsive from "../components/TablaResponsive";
import Tarjeta from "../components/Tarjeta";
import { formatFecha } from "../utils/fechas";

const ESTADOS = ["abierta", "convertida_en_trabajo", "rechazada", "cancelada"];

const ETIQUETAS_ESTADO = {
  abierta: "Abierta",
  convertida_en_trabajo: "Convertida en trabajo",
  rechazada: "Rechazada",
  cancelada: "Cancelada",
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

      <TablaResponsive
        columnas={[
          { clave: "id", titulo: "#", ancho: "6ch", celda: (p) => p.id },
          {
            clave: "depto",
            titulo: "Depto",
            prioridad: 2,
            ancho: "9ch",
            celda: (p) => p.departamento_id,
          },
          { clave: "titulo", titulo: "Título", ancho: "auto", celda: (p) => p.titulo },
          {
            // "Convertida en trabajo" (21 caracteres) es la etiqueta más
            // larga de ETIQUETAS_ESTADO — el ancho se mide desde ahí, no
            // desde las más cortas ("Abierta", "Rechazada", "Cancelada").
            clave: "estado",
            titulo: "Estado",
            ancho: "23ch",
            celda: (p) => ETIQUETAS_ESTADO[p.estado] || p.estado,
          },
          {
            clave: "fecha",
            titulo: "Fecha",
            prioridad: 3,
            ancho: "12ch",
            celda: (p) => formatFecha(p.fecha_creacion),
          },
          {
            clave: "acciones",
            titulo: "",
            className: "col-acciones",
            ancho: "7rem",
            celda: (p) => (
              <button type="button" onClick={() => setModal(p)}>Ver</button>
            ),
          },
        ]}
        filas={visibles}
        claveFila={(p) => p.id}
        vacio="Sin peticiones."
        renderTarjeta={(p) => (
          <Tarjeta>
            <h3>#{p.id} · {p.titulo}</h3>
            <p className="meta">
              Depto {p.departamento_id} · {formatFecha(p.fecha_creacion)}
            </p>
            <p className="meta">{ETIQUETAS_ESTADO[p.estado] || p.estado}</p>
            <div className="tarjeta-acciones">
              <button type="button" onClick={() => setModal(p)}>Ver detalle</button>
            </div>
          </Tarjeta>
        )}
      />

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
