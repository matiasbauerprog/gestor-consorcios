import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
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

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarProveedores(filtro);
    if (r.status === 200) {
      setProveedores(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los proveedores.");
    }
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(p) {
    const r = p.activo
      ? await eliminarProveedor(p.id)
      : await actualizarProveedor(p.id, { activo: true });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Proveedores</h2>
        <div className="cabecera-acciones">
          <label className="filtro-checkbox">
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

      {error && <p role="alert" className="error-banner">{error}</p>}
      {proveedores.length === 0 && <p>No hay proveedores con esos filtros.</p>}

      <ul className="lista-config">
        {proveedores.map((p) => (
          <li key={p.id}>
            <Tarjeta>
              <h3>{p.razon_social}</h3>
              {p.nombre_fantasia && <p className="meta">Nombre fantasía: {p.nombre_fantasia}</p>}
              <p className="meta">CUIT: {p.cuit}</p>
              {p.direccion && <p className="meta">Dirección: {p.direccion}</p>}
              <p className="meta">Estado: {p.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", proveedor: p })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(p)}>
                  {p.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

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
            const r = await crearProveedor(payload);
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
            const r = await actualizarProveedor(modal.proveedor.id, {
              razon_social,
              nombre_fantasia: nombre_fantasia || null,
              direccion: direccion || null,
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

function ModalProveedor({ titulo, inicial, permiteEditarCuit, onCerrar, onGuardar }) {
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
