import { useEffect, useState } from "react";
import {
  listarClasesProrrateo,
  crearClaseProrrateo,
  actualizarClaseProrrateo,
  eliminarClaseProrrateo,
} from "../api/clasesProrrateo";

export default function ClasesProrrateo() {
  const [clases, setClases] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);

  async function recargar() {
    setCargando(true);
    const r = await listarClasesProrrateo();
    if (r.status === 200) {
      setClases(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar las clases.");
    }
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, []);

  async function toggleActiva(clase) {
    const r = await actualizarClaseProrrateo(clase.id, { activa: !clase.activa });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  async function borrar(clase) {
    if (!confirm(`¿Eliminar la clase "${clase.codigo}"?`)) return;
    const r = await eliminarClaseProrrateo(clase.id);
    if (r.status === 200 || r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al eliminar.");
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Clases de prorrateo</h2>
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          Nueva clase
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Descripción</th>
            <th>Activa</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {clases.map((c) => (
            <tr key={c.id}>
              <td>{c.codigo}</td>
              <td>{c.nombre}</td>
              <td>{c.descripcion || "—"}</td>
              <td>{c.activa ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModal({ tipo: "editar", clase: c })}>Editar</button>
                <button type="button" onClick={() => toggleActiva(c)}>
                  {c.activa ? "Desactivar" : "Activar"}
                </button>
                <button type="button" onClick={() => borrar(c)}>Eliminar</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal?.tipo === "crear" && (
        <ModalForm
          titulo="Nueva clase"
          inicial={{ codigo: "", nombre: "", descripcion: "" }}
          permiteEditarCodigo
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearClaseProrrateo(datos);
            if (r.status === 201) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al crear.";
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalForm
          titulo={`Editar clase ${modal.clase.codigo}`}
          inicial={{
            codigo: modal.clase.codigo,
            nombre: modal.clase.nombre,
            descripcion: modal.clase.descripcion || "",
          }}
          permiteEditarCodigo={false}
          onCerrar={() => setModal(null)}
          onGuardar={async ({ nombre, descripcion }) => {
            const r = await actualizarClaseProrrateo(modal.clase.id, {
              nombre,
              descripcion: descripcion || null,
            });
            if (r.status === 200) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al editar.";
          }}
        />
      )}
    </main>
  );
}

function ModalForm({ titulo, inicial, permiteEditarCodigo, onCerrar, onGuardar }) {
  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const err = await onGuardar(form);
    if (err) {
      setError(err);
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        <form onSubmit={onSubmit}>
          <label>Código
            <input
              value={form.codigo}
              onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              disabled={!permiteEditarCodigo}
              maxLength={8}
              required
            />
          </label>
          <label>Nombre
            <input
              value={form.nombre}
              onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              maxLength={120}
              required
            />
          </label>
          <label>Descripción
            <textarea
              value={form.descripcion}
              onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              maxLength={500}
            />
          </label>
          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
