import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import {
  listarConceptos,
  crearConcepto,
  actualizarConcepto,
  eliminarConcepto,
} from "../api/conceptosLiquidacion";
import { listarProveedores } from "../api/proveedores";

const TIPOS = [
  { value: "descuento", label: "Descuento" },
  { value: "contribucion", label: "Contribución" },
];

function labelTipo(v) {
  return TIPOS.find((t) => t.value === v)?.label || v;
}

export default function ConceptosLiquidacion() {
  const [conceptos, setConceptos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  async function cargarCatalogos() {
    const r = await listarProveedores({ activo: true });
    if (r.status === 200) setProveedores(r.data);
  }

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarConceptos(filtro);
    if (r.status === 200) {
      setConceptos(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los conceptos.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(c) {
    const r = c.activo
      ? await eliminarConcepto(c.id)
      : await actualizarConcepto(c.id, { activo: true });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  function proveedorPorId(id) {
    if (id === null || id === undefined) return "—";
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Conceptos de liquidación</h2>
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
            + Nuevo concepto
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {conceptos.length === 0 && <p>No hay conceptos para mostrar.</p>}

      <ul className="lista-config">
        {conceptos.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>{c.nombre}</h3>
              <p className="meta">Tipo: {labelTipo(c.tipo)}</p>
              <p className="meta">Porcentaje: {c.porcentaje}%</p>
              <p className="meta">Proveedor: {proveedorPorId(c.proveedor_id)}</p>
              <p className="meta">Estado: {c.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", concepto: c })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(c)}>
                  {c.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalConcepto
          titulo="Nuevo concepto"
          proveedores={proveedores}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearConcepto(datos);
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
        <ModalConcepto
          titulo={`Editar ${modal.concepto.nombre}`}
          inicial={modal.concepto}
          proveedores={proveedores}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await actualizarConcepto(modal.concepto.id, datos);
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

function ModalConcepto({ titulo, inicial, proveedores, onCerrar, onGuardar }) {
  const valorInicial = inicial
    ? {
        nombre: inicial.nombre,
        tipo: inicial.tipo,
        porcentaje: String(inicial.porcentaje),
        proveedor_id: inicial.proveedor_id ?? "",
        orden: String(inicial.orden),
      }
    : { nombre: "", tipo: "descuento", porcentaje: "0", proveedor_id: "", orden: "0" };

  const [form, setForm] = useState(valorInicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function set(campo, valor) {
    setForm({ ...form, [campo]: valor });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = {
      nombre: form.nombre,
      tipo: form.tipo,
      porcentaje: Number(form.porcentaje),
      proveedor_id: form.proveedor_id ? Number(form.proveedor_id) : null,
      orden: Number(form.orden),
    };
    const err = await onGuardar(payload);
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
          <label>Nombre <input value={form.nombre}
            onChange={(e) => set("nombre", e.target.value)} maxLength={120} required /></label>
          <label>Tipo <select value={form.tipo} onChange={(e) => set("tipo", e.target.value)} required>
            {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select></label>
          <label>Porcentaje (0–100) <input type="number" min="0" max="100" step="0.0001"
            value={form.porcentaje} onChange={(e) => set("porcentaje", e.target.value)} required /></label>
          <label>Proveedor (opcional)
            <select value={form.proveedor_id} onChange={(e) => set("proveedor_id", e.target.value)}>
              <option value="">— Sin proveedor —</option>
              {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
            </select>
          </label>
          <p className="meta">Sin proveedor: el concepto se calcula pero no genera un Gasto separado.</p>
          <label>Orden <input type="number" min="0"
            value={form.orden} onChange={(e) => set("orden", e.target.value)} required /></label>

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
