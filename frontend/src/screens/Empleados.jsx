import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import {
  listarEmpleados,
  crearEmpleado,
  actualizarEmpleado,
  eliminarEmpleado,
} from "../api/empleados";
import { listarProveedores } from "../api/proveedores";

const CATEGORIAS = [
  { value: "encargado_permanente_con_vivienda", label: "Encargado permanente con vivienda" },
  { value: "encargado_permanente_sin_vivienda", label: "Encargado permanente sin vivienda" },
  { value: "encargado_suplente", label: "Encargado suplente" },
  { value: "ayudante", label: "Ayudante" },
];

function labelCategoria(v) {
  return CATEGORIAS.find((c) => c.value === v)?.label || v;
}

export default function Empleados() {
  const [empleados, setEmpleados] = useState([]);
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
    const r = await listarEmpleados(filtro);
    if (r.status === 200) {
      setEmpleados(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los empleados.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [mostrarInactivos]);

  async function toggleActivo(e) {
    const r = e.activo
      ? await eliminarEmpleado(e.id)
      : await actualizarEmpleado(e.id, { activo: true });
    if (r.status === 200 || r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  function proveedorPorId(id) {
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Empleados</h2>
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
            + Nuevo empleado
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {empleados.length === 0 && <p>No hay empleados con esos filtros.</p>}

      <ul className="lista-config">
        {empleados.map((e) => (
          <li key={e.id}>
            <Tarjeta>
              <h3>{e.nombre_completo}</h3>
              <p className="meta">CUIL: {e.cuil}</p>
              <p className="meta">Categoría: {labelCategoria(e.categoria)}</p>
              <p className="meta">Sueldo básico: ${e.sueldo_basico.toLocaleString("es-AR")}</p>
              <p className="meta">Ingresó: {e.fecha_ingreso}</p>
              <p className="meta">Proveedor: {proveedorPorId(e.proveedor_id)}</p>
              <p className="meta">Estado: {e.activo ? "Activo" : "Inactivo"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", empleado: e })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActivo(e)}>
                  {e.activo ? "Desactivar" : "Activar"}
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalEmpleado
          titulo="Nuevo empleado"
          proveedores={proveedores}
          permiteEditarCuil
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const r = await crearEmpleado(datos);
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
        <ModalEmpleado
          titulo={`Editar ${modal.empleado.nombre_completo}`}
          inicial={modal.empleado}
          proveedores={proveedores}
          permiteEditarCuil={false}
          onCerrar={() => setModal(null)}
          onGuardar={async (datos) => {
            const { cuil: _ignored, ...resto } = datos;
            const r = await actualizarEmpleado(modal.empleado.id, resto);
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

function ModalEmpleado({ titulo, inicial, proveedores, permiteEditarCuil, onCerrar, onGuardar }) {
  const valorInicial = inicial
    ? {
        nombre_completo: inicial.nombre_completo,
        cuil: inicial.cuil,
        categoria: inicial.categoria,
        fecha_ingreso: inicial.fecha_ingreso,
        fecha_egreso: inicial.fecha_egreso || "",
        sueldo_basico: String(inicial.sueldo_basico),
        proveedor_id: inicial.proveedor_id,
      }
    : {
        nombre_completo: "",
        cuil: "",
        categoria: "encargado_permanente_sin_vivienda",
        fecha_ingreso: "",
        fecha_egreso: "",
        sueldo_basico: "",
        proveedor_id: proveedores[0]?.id ?? "",
      };

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
      nombre_completo: form.nombre_completo,
      cuil: form.cuil,
      categoria: form.categoria,
      fecha_ingreso: form.fecha_ingreso,
      fecha_egreso: form.fecha_egreso || null,
      sueldo_basico: Number(form.sueldo_basico),
      proveedor_id: Number(form.proveedor_id),
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
          <label>Nombre completo <input value={form.nombre_completo}
            onChange={(e) => set("nombre_completo", e.target.value)} maxLength={255} required /></label>
          <label>CUIL <input value={form.cuil}
            onChange={(e) => set("cuil", e.target.value)}
            disabled={!permiteEditarCuil}
            placeholder="20-12345678-9"
            pattern="\d{2}-\d{8}-\d{1}"
            required /></label>
          <label>Categoría <select value={form.categoria} onChange={(e) => set("categoria", e.target.value)} required>
            {CATEGORIAS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select></label>
          <label>Fecha ingreso <input type="date" value={form.fecha_ingreso}
            onChange={(e) => set("fecha_ingreso", e.target.value)} required /></label>
          <label>Fecha egreso (opcional) <input type="date" value={form.fecha_egreso}
            onChange={(e) => set("fecha_egreso", e.target.value)} /></label>
          <label>Sueldo básico <input type="number" min="0.01" step="0.01"
            value={form.sueldo_basico} onChange={(e) => set("sueldo_basico", e.target.value)} required /></label>
          <label>Proveedor asociado <select value={form.proveedor_id}
            onChange={(e) => set("proveedor_id", e.target.value)} required>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select></label>

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
