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

  function recargar() {
    setCargando(true);
    listarClasesProrrateo()
      .then(setClases)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    recargar();
  }, []);

  async function toggleActiva(clase) {
    try {
      await actualizarClaseProrrateo(clase.id, { activa: !clase.activa });
      recargar();
    } catch (err) {
      setError(err.message);
    }
  }

  async function borrar(clase) {
    if (!confirm(`¿Eliminar la clase "${clase.codigo}"?`)) return;
    try {
      await eliminarClaseProrrateo(clase.id);
      recargar();
    } catch (err) {
      setError(err.message);
    }
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
            await crearClaseProrrateo(datos);
            setModal(null);
            recargar();
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
            await actualizarClaseProrrateo(modal.clase.id, {
              nombre,
              descripcion: descripcion || null,
            });
            setModal(null);
            recargar();
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
    try {
      await onGuardar(form);
    } catch (err) {
      setError(err.message || "Error");
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
