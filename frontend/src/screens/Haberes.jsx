import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import {
  listarHaberes,
  crearHaber,
  actualizarHaber,
  eliminarHaber,
} from "../api/haberes";

const TIPOS = [
  { value: "monto_fijo", label: "Monto fijo", unidadValor: "Monto" },
  { value: "porcentaje_sobre_basico", label: "Porcentaje sobre básico", unidadValor: "Porcentaje (%)" },
  { value: "cantidad_x_valor", label: "Cantidad × valor", unidadValor: "Valor por unidad" },
];

function labelTipo(v) {
  return TIPOS.find((t) => t.value === v)?.label || v;
}

export default function Haberes() {
  const [haberes, setHaberes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [modal, setModal] = useState(null);

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivos ? { activo: false } : { activo: true };
    const r = await listarHaberes(filtro);
    if (r.status === 200) {
      setHaberes(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los haberes.");
    }
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(h) {
    const r = h.activo
      ? await eliminarHaber(h.id)
      : await actualizarHaber(h.id, { activo: true });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Haberes</h2>
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
            + Nuevo haber
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {haberes.length === 0 && <p>No hay haberes para mostrar.</p>}

      <ul className="lista-config">
        {haberes.map((h) => (
          <li key={h.id}>
            <Tarjeta>
              <h3>{h.nombre}</h3>
              <p className="meta">Tipo: {labelTipo(h.tipo)}</p>
              <p className="meta">Valor default: {h.valor_default}</p>
              <p className="meta">Orden: {h.orden}</p>
              <p className="meta">Estado: {h.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", haber: h })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(h)}>
                  {h.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalHaber
          titulo="Nuevo haber"
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearHaber(datos);
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
        <ModalHaber
          titulo={`Editar ${modal.haber.nombre}`}
          inicial={modal.haber}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await actualizarHaber(modal.haber.id, datos);
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

function ModalHaber({ titulo, inicial, onCerrar, onGuardar }) {
  const valorInicial = inicial
    ? { nombre: inicial.nombre, tipo: inicial.tipo, valor_default: String(inicial.valor_default), orden: String(inicial.orden) }
    : { nombre: "", tipo: "monto_fijo", valor_default: "0", orden: "0" };

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
      valor_default: Number(form.valor_default),
      orden: Number(form.orden),
    };
    const err = await onGuardar(payload);
    if (err) {
      setError(err);
      setGuardando(false);
    }
  }

  const unidad = TIPOS.find((t) => t.value === form.tipo)?.unidadValor || "Valor";

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
          <label>{unidad} <input type="number" min="0" step="0.01"
            value={form.valor_default} onChange={(e) => set("valor_default", e.target.value)} required /></label>
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
