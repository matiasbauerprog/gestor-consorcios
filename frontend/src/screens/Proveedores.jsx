import { useEffect, useState } from "react";
import {
  listarProveedores,
  crearProveedor,
  actualizarProveedor,
  eliminarProveedor,
} from "../api/proveedores";

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    listarProveedores(filtro)
      .then(setProveedores)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(p) {
    try {
      if (p.activo) {
        await eliminarProveedor(p.id);
      } else {
        await actualizarProveedor(p.id, { activo: true });
      }
      recargar();
    } catch (err) {
      setError(err.message);
    }
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Proveedores</h2>
        <div>
          <label>
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Mostrar inactivos
          </label>
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            Nuevo proveedor
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="tabla">
        <thead>
          <tr>
            <th>Razón social</th>
            <th>Nombre fantasía</th>
            <th>CUIT</th>
            <th>Dirección</th>
            <th>Activo</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {proveedores.map((p) => (
            <tr key={p.id}>
              <td>{p.razon_social}</td>
              <td>{p.nombre_fantasia || "—"}</td>
              <td>{p.cuit}</td>
              <td>{p.direccion || "—"}</td>
              <td>{p.activo ? "Sí" : "No"}</td>
              <td>
                <button type="button" onClick={() => setModal({ tipo: "editar", proveedor: p })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(p)}>
                  {p.activo ? "Desactivar" : "Activar"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal?.tipo === "crear" && (
        <ModalProveedor
          titulo="Nuevo proveedor"
          inicial={{ razon_social: "", nombre_fantasia: "", cuit: "", direccion: "" }}
          permiteEditarCuit
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const payload = {
              ...datos,
              nombre_fantasia: datos.nombre_fantasia || null,
              direccion: datos.direccion || null,
            };
            await crearProveedor(payload);
            setModal(null);
            recargar();
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalProveedor
          titulo={`Editar ${modal.proveedor.razon_social}`}
          inicial={{
            razon_social: modal.proveedor.razon_social,
            nombre_fantasia: modal.proveedor.nombre_fantasia || "",
            cuit: modal.proveedor.cuit,
            direccion: modal.proveedor.direccion || "",
          }}
          permiteEditarCuit={false}
          onCerrar={() => setModal(null)}
          onGuardar={async ({ razon_social, nombre_fantasia, direccion }) => {
            await actualizarProveedor(modal.proveedor.id, {
              razon_social,
              nombre_fantasia: nombre_fantasia || null,
              direccion: direccion || null,
            });
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalProveedor({ titulo, inicial, permiteEditarCuit, onCerrar, onGuardar }) {
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
          <label>Razón social
            <input
              value={form.razon_social}
              onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              maxLength={255}
              required
            />
          </label>
          <label>Nombre fantasía
            <input
              value={form.nombre_fantasia}
              onChange={(e) => setForm({ ...form, nombre_fantasia: e.target.value })}
              maxLength={255}
            />
          </label>
          <label>CUIT
            <input
              value={form.cuit}
              onChange={(e) => setForm({ ...form, cuit: e.target.value })}
              disabled={!permiteEditarCuit}
              placeholder="30-12345678-9"
              pattern="\d{2}-\d{8}-\d{1}"
              required
            />
          </label>
          <label>Dirección
            <input
              value={form.direccion}
              onChange={(e) => setForm({ ...form, direccion: e.target.value })}
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
