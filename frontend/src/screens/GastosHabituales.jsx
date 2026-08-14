import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Tarjeta from "../components/Tarjeta";
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
import {
  listarGastosHabituales,
  crearGastoHabitual,
  actualizarGastoHabitual,
  eliminarGastoHabitual,
} from "../api/gastosHabituales";
import { listarClasesProrrateo } from "../api/clasesProrrateo";
import { listarProveedores } from "../api/proveedores";
import { listarCajas } from "../api/cajas";
import { ANCHO_MONTO_DECIMAL } from "../utils/anchosColumnas";

const RUBROS = [
  { value: "sueldos_y_cargas_sociales", label: "Sueldos y cargas sociales" },
  { value: "servicios_publicos", label: "Servicios públicos" },
  { value: "abonos_y_servicios", label: "Abonos y servicios" },
  { value: "mantenimiento_partes_comunes", label: "Mantenimiento partes comunes" },
  { value: "trabajos_reparaciones_unidades", label: "Trabajos en unidades" },
  { value: "gastos_bancarios", label: "Gastos bancarios" },
  { value: "gastos_administracion", label: "Gastos de administración" },
  { value: "seguros", label: "Seguros" },
  { value: "gastos_generales", label: "Gastos generales" },
];

const FORMAS_PAGO = [
  { value: "transferencia", label: "Transferencia" },
  { value: "debito_automatico", label: "Débito automático" },
  { value: "cheque", label: "Cheque" },
  { value: "efectivo", label: "Efectivo" },
  { value: "otro", label: "Otro" },
];

function labelRubro(value) {
  return RUBROS.find((r) => r.value === value)?.label || value;
}

// "Inactiva" (8 caracteres) es el string más largo de esta columna: contenido
// ≈ (8×8.2×1.2 + 24) / 7.15 ≈ 14.4 → 15ch (misma aritmética que
// utils/anchosColumnas.js). El encabezado "Estado" en mayúsculas +
// letter-spacing: 0.2em (`.tabla-datos thead th`) pediría bastante menos
// (6 caracteres: (6×7.5×1.2 + 24) / 7.15 ≈ 10.9 → 11ch — fórmula calibrada
// contra el fix real de Cajas.jsx, donde "ACTIVA" no entraba en 8ch y sí en
// 11ch), así que acá manda el contenido, no el título.
const ANCHO_ESTADO = "15ch";

export default function GastosHabituales() {
  const navigate = useNavigate();
  const [habituales, setHabituales] = useState([]);
  const [clases, setClases] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [cajas, setCajas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mostrarInactivas, setMostrarInactivas] = useState(false);
  const [modal, setModal] = useState(null);

  async function cargarCatalogos() {
    const [rClases, rProv, rCajas] = await Promise.all([
      listarClasesProrrateo({ activa: true }),
      listarProveedores({ activo: true }),
      listarCajas(),
    ]);
    if (rClases.status === 200) setClases(rClases.data);
    if (rProv.status === 200) setProveedores(rProv.data);
    if (rCajas.status === 200) setCajas(rCajas.data);
  }

  async function recargar() {
    setCargando(true);
    const filtro = mostrarInactivas ? { activa: false } : { activa: true };
    const r = await listarGastosHabituales(filtro);
    if (r.status === 200) {
      setHabituales(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los gastos recurrentes.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [mostrarInactivas]);

  async function toggleActiva(h) {
    const r = await actualizarGastoHabitual(h.id, { activa: !h.activa });
    if (r.status === 200) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al actualizar.");
  }

  async function borrar(h) {
    if (!confirm(`¿Eliminar el gasto recurrente "${h.nombre}"?`)) return;
    const r = await eliminarGastoHabitual(h.id);
    if (r.status === 200 || r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "Error al eliminar.");
  }

  function proveedorPorId(id) {
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  function clasePorId(id) {
    return clases.find((c) => c.id === id)?.codigo || "—";
  }

  function cajaPorId(id) {
    return cajas.find((c) => c.id === id)?.nombre || "—";
  }

  return (
    <section>
      <header className="cabecera-pantalla">
        <h2>Gastos recurrentes</h2>
        <button
          type="button"
          className="boton-secundario"
          onClick={() => navigate("/gastos")}
        >
          &larr; Volver a gastos del mes
        </button>
      </header>

      <div className="cabecera-acciones">
        <label className="filtro-checkbox">
          <input
            type="checkbox"
            checked={mostrarInactivas}
            onChange={(e) => setMostrarInactivas(e.target.checked)}
          />
          Mostrar inactivas
        </label>
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          + Nuevo gasto recurrente
        </button>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {cargando && <p>Cargando…</p>}

      {!cargando && (
        <TablaResponsive
          columnas={[
            { clave: "nombre", titulo: "Nombre", prioridad: 1, ancho: "auto", celda: (h) => h.nombre },
            {
              clave: "monto",
              titulo: "Monto",
              prioridad: 1,
              ancho: ANCHO_MONTO_DECIMAL,
              className: "col-monto",
              celda: (h) => `$${h.monto.toLocaleString("es-AR")}`,
            },
            { clave: "rubro", titulo: "Rubro", prioridad: 2, ancho: "auto", celda: (h) => labelRubro(h.rubro) },
            {
              clave: "clase",
              titulo: "Clase",
              prioridad: 3,
              ancho: "auto",
              celda: (h) => clasePorId(h.clase_prorrateo_id),
            },
            {
              clave: "proveedor",
              titulo: "Proveedor",
              prioridad: 3,
              ancho: "auto",
              celda: (h) => proveedorPorId(h.proveedor_id),
            },
            { clave: "caja", titulo: "Caja", prioridad: 3, ancho: "auto", celda: (h) => cajaPorId(h.caja_id) },
            {
              // La lista siempre está filtrada a "activas" o a "inactivas"
              // (`recargar` pide `{activa: true}` o `{activa: false}`, nunca
              // ambas mezcladas), así que este valor es constante entre las
              // filas visibles — no sirve para comparar una fila contra otra,
              // solo para confirmar en qué vista estoy una vez que ya
              // encontré la fila. Por eso prioridad 3, no 2 como en el brief.
              clave: "estado",
              titulo: "Estado",
              prioridad: 3,
              ancho: ANCHO_ESTADO,
              celda: (h) => (h.activa ? "Activa" : "Inactiva"),
            },
            {
              clave: "acciones",
              titulo: "",
              className: "col-acciones",
              prioridad: 1,
              ancho: "4rem",
              celda: (h) => (
                <MenuAcciones
                  etiqueta={`Acciones de ${h.nombre}`}
                  acciones={[
                    { label: "Editar", onSelect: () => setModal({ tipo: "editar", habitual: h }) },
                    { label: h.activa ? "Desactivar" : "Activar", onSelect: () => toggleActiva(h) },
                    { label: "Eliminar", onSelect: () => borrar(h), peligro: true },
                  ]}
                />
              ),
            },
          ]}
          filas={habituales}
          claveFila={(h) => h.id}
          vacio="No hay gastos recurrentes para mostrar."
          renderTarjeta={(h) => (
            <Tarjeta>
              <h3>{h.nombre} — ${h.monto.toLocaleString("es-AR")}</h3>
              <p className="meta">Rubro: {labelRubro(h.rubro)}</p>
              <p className="meta">Clase: {clasePorId(h.clase_prorrateo_id)}</p>
              <p className="meta">Proveedor: {proveedorPorId(h.proveedor_id)}</p>
              <p className="meta">Caja: {cajaPorId(h.caja_id)}</p>
              <p className="meta">Estado: {h.activa ? "Activa" : "Inactiva"}</p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", habitual: h })}>
                  Editar
                </button>
                <button type="button" onClick={() => toggleActiva(h)}>
                  {h.activa ? "Desactivar" : "Activar"}
                </button>
                <button type="button" className="boton-borrar" onClick={() => borrar(h)}>
                  Eliminar
                </button>
              </div>
            </Tarjeta>
          )}
        />
      )}

      {modal && (
        <ModalHabitual
          tipo={modal.tipo}
          inicial={modal.habitual}
          clases={clases}
          proveedores={proveedores}
          cajas={cajas}
          onCerrar={() => setModal(null)}
          onGuardado={() => {
            setModal(null);
            recargar();
          }}
        />
      )}
    </section>
  );
}

function ModalHabitual({ tipo, inicial, clases, proveedores, cajas, onCerrar, onGuardado }) {
  const esEditar = tipo === "editar";
  const valorInicial = inicial
    ? {
        nombre: inicial.nombre,
        rubro: inicial.rubro,
        clase_prorrateo_id: inicial.clase_prorrateo_id,
        proveedor_id: inicial.proveedor_id,
        concepto: inicial.concepto,
        monto: String(inicial.monto),
        forma_pago: inicial.forma_pago,
        caja_id: inicial.caja_id || "",
      }
    : {
        nombre: "",
        rubro: "abonos_y_servicios",
        clase_prorrateo_id: clases[0]?.id ?? "",
        proveedor_id: proveedores[0]?.id ?? "",
        concepto: "",
        monto: "",
        forma_pago: "transferencia",
        caja_id: cajas[0]?.id ?? "",
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
      nombre: form.nombre,
      rubro: form.rubro,
      clase_prorrateo_id: Number(form.clase_prorrateo_id),
      proveedor_id: Number(form.proveedor_id),
      concepto: form.concepto,
      monto: Number(form.monto),
      forma_pago: form.forma_pago,
      caja_id: Number(form.caja_id),
    };

    const r = esEditar
      ? await actualizarGastoHabitual(inicial.id, payload)
      : await crearGastoHabitual(payload);

    if (r.status === 200 || r.status === 201) {
      onGuardado();
      return;
    }
    setError(r.data?.detail || "No se pudo guardar.");
    setGuardando(false);
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{esEditar ? "Editar gasto recurrente" : "Nuevo gasto recurrente"}</h3>
        <form onSubmit={onSubmit}>
          <label>Nombre <input value={form.nombre}
            onChange={(e) => set("nombre", e.target.value)} maxLength={120} required /></label>

          <label>Rubro <select value={form.rubro}
            onChange={(e) => set("rubro", e.target.value)} required>
            {RUBROS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select></label>

          <label>Clase <select value={form.clase_prorrateo_id}
            onChange={(e) => set("clase_prorrateo_id", e.target.value)} required>
            {clases.map((c) => <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
          </select></label>

          <label>Proveedor <select value={form.proveedor_id}
            onChange={(e) => set("proveedor_id", e.target.value)} required>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select></label>

          <label>Concepto <textarea value={form.concepto}
            onChange={(e) => set("concepto", e.target.value)} maxLength={500} required /></label>

          <label>Monto <input type="number" min="0.01" step="0.01"
            value={form.monto} onChange={(e) => set("monto", e.target.value)} required /></label>

          <label>Caja origen <select value={form.caja_id}
            onChange={(e) => set("caja_id", e.target.value ? Number(e.target.value) : "")} required>
            <option value="">— Elegí una —</option>
            {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select></label>

          <label>Forma de pago <select value={form.forma_pago}
            onChange={(e) => set("forma_pago", e.target.value)} required>
            {FORMAS_PAGO.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select></label>

          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
