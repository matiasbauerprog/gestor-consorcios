import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import Tabs from "../components/Tabs";
import {
  listarGastos,
  crearGasto,
  crearPlanCuotas,
  actualizarGasto,
  eliminarGasto,
  cargarGastosHabituales,
} from "../api/gastos";
import { listarClasesProrrateo } from "../api/clasesProrrateo";
import { listarProveedores } from "../api/proveedores";
import { listarDepartamentos } from "../api/departamentos";

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

const TABS = [
  { path: "/gastos", label: "Del mes", end: true },
  { path: "/gastos/habituales", label: "Recurrentes" },
];

function labelRubro(value) {
  return RUBROS.find((r) => r.value === value)?.label || value;
}

export default function Gastos() {
  const [gastos, setGastos] = useState([]);
  const [clases, setClases] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [departamentos, setDepartamentos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);

  const [filtros, setFiltros] = useState({
    periodo: "",
    rubro: "",
    clase_prorrateo_id: "",
    proveedor_id: "",
    departamento_id: "",
  });

  async function cargarCatalogos() {
    const [rClases, rProv, rDeptos] = await Promise.all([
      listarClasesProrrateo({ activa: true }),
      listarProveedores({ activo: true }),
      listarDepartamentos(),
    ]);
    if (rClases.status === 200) setClases(rClases.data);
    if (rProv.status === 200) setProveedores(rProv.data);
    if (rDeptos.status === 200) setDepartamentos(rDeptos.data);
  }

  async function recargar() {
    setCargando(true);
    const r = await listarGastos(filtros);
    if (r.status === 200) {
      setGastos(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los gastos.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargarCatalogos();
  }, []);

  useEffect(() => {
    recargar();
  }, [
    filtros.periodo,
    filtros.rubro,
    filtros.clase_prorrateo_id,
    filtros.proveedor_id,
    filtros.departamento_id,
  ]);

  function cambiarFiltro(campo, valor) {
    setFiltros({ ...filtros, [campo]: valor });
  }

  async function handleCargarHabituales() {
    if (!filtros.periodo) {
      setError("Seleccioná un período antes de cargar gastos habituales.");
      return;
    }
    const r = await cargarGastosHabituales(filtros.periodo);
    if (r.status === 201) {
      recargar();
      const n = r.data.length;
      setError(n === 0 ? "No había gastos recurrentes nuevos para cargar." : null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar los habituales.");
    }
  }

  async function handleBorrar(g) {
    if (!confirm(`¿Eliminar el gasto "${g.concepto}"?`)) return;
    const r = await eliminarGasto(g.id);
    if (r.status === 204) recargar();
    else if (r.status !== 401) setError(r.data?.detail || "No se pudo eliminar.");
  }

  function proveedorPorId(id) {
    return proveedores.find((p) => p.id === id)?.razon_social || "—";
  }

  function clasePorId(id) {
    return clases.find((c) => c.id === id)?.codigo || "—";
  }

  function deptoPorId(id) {
    const d = departamentos.find((x) => x.id === id);
    return d ? d.codigo : "—";
  }

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Gastos</h2>
      </header>
      <Tabs tabs={TABS} />

      <section className="filtros-gastos">
        <label>Período <input
          type="month"
          value={filtros.periodo}
          onChange={(e) => cambiarFiltro("periodo", e.target.value)}
        /></label>
        <label>Rubro <select
          value={filtros.rubro}
          onChange={(e) => cambiarFiltro("rubro", e.target.value)}
        >
          <option value="">Todos</option>
          {RUBROS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select></label>
        <label>Clase <select
          value={filtros.clase_prorrateo_id}
          onChange={(e) => cambiarFiltro("clase_prorrateo_id", e.target.value)}
        >
          <option value="">Todas</option>
          {clases.map((c) => <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
        </select></label>
        <label>Proveedor <select
          value={filtros.proveedor_id}
          onChange={(e) => cambiarFiltro("proveedor_id", e.target.value)}
        >
          <option value="">Todos</option>
          {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
        </select></label>
        <label>Departamento <select
          value={filtros.departamento_id}
          onChange={(e) => cambiarFiltro("departamento_id", e.target.value)}
        >
          <option value="">Todos</option>
          {departamentos.map((d) => <option key={d.id} value={d.id}>{d.codigo}</option>)}
        </select></label>
      </section>

      <div className="cabecera-acciones">
        <button type="button" onClick={handleCargarHabituales} disabled={!filtros.periodo}>
          Cargar gastos recurrentes del mes
        </button>
        <button type="button" onClick={() => setModal({ tipo: "crear" })}>
          + Nuevo gasto
        </button>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {cargando && <p>Cargando…</p>}
      {!cargando && gastos.length === 0 && <p>No hay gastos con esos filtros.</p>}

      <ul className="lista-gastos">
        {gastos.map((g) => (
          <li key={g.id}>
            <Tarjeta>
              <h3>{labelRubro(g.rubro)} · {g.concepto}</h3>
              <p className="meta">
                ${g.monto.toLocaleString("es-AR")} · {g.periodo} · pagó {g.fecha_pago}
              </p>
              <p className="meta">Proveedor: {proveedorPorId(g.proveedor_id)}</p>
              <p className="meta">
                {g.clase_prorrateo_id !== null
                  ? <>Clase {clasePorId(g.clase_prorrateo_id)}</>
                  : <>Particular a {deptoPorId(g.departamento_id)}</>}
                {g.cuota_actual && <> · Cuota {g.cuota_actual}/{g.cuota_total}</>}
                {g.gasto_habitual_id && <> · Recurrente</>}
              </p>
              <div className="tarjeta-acciones">
                <button type="button" onClick={() => setModal({ tipo: "editar", gasto: g })}>
                  Editar
                </button>
                <button type="button" className="boton-borrar" onClick={() => handleBorrar(g)}>
                  Eliminar
                </button>
              </div>
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modal && (
        <ModalGasto
          tipo={modal.tipo}
          gastoInicial={modal.gasto}
          clases={clases}
          proveedores={proveedores}
          departamentos={departamentos}
          onCerrar={() => setModal(null)}
          onGuardado={() => {
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalGasto({ tipo, gastoInicial, clases, proveedores, departamentos, onCerrar, onGuardado }) {
  const esEditar = tipo === "editar";
  const inicial = gastoInicial
    ? {
        periodo: gastoInicial.periodo,
        rubro: gastoInicial.rubro,
        modo: gastoInicial.clase_prorrateo_id !== null ? "clase" : "depto",
        clase_prorrateo_id: gastoInicial.clase_prorrateo_id ?? "",
        departamento_id: gastoInicial.departamento_id ?? "",
        proveedor_id: gastoInicial.proveedor_id,
        concepto: gastoInicial.concepto,
        monto: String(gastoInicial.monto),
        forma_pago: gastoInicial.forma_pago,
        fecha_pago: gastoInicial.fecha_pago,
        numero_factura: gastoInicial.numero_factura || "",
        fecha_factura: gastoInicial.fecha_factura || "",
        cuota_actual: gastoInicial.cuota_actual ?? "",
        cuota_total: gastoInicial.cuota_total ?? "",
        es_plan: false,
        cuota_total_plan: "",
      }
    : {
        periodo: "",
        rubro: "abonos_y_servicios",
        modo: "clase",
        clase_prorrateo_id: clases[0]?.id ?? "",
        departamento_id: "",
        proveedor_id: proveedores[0]?.id ?? "",
        concepto: "",
        monto: "",
        forma_pago: "transferencia",
        fecha_pago: "",
        numero_factura: "",
        fecha_factura: "",
        cuota_actual: "",
        cuota_total: "",
        es_plan: false,
        cuota_total_plan: "",
      };

  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function set(campo, valor) {
    setForm({ ...form, [campo]: valor });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);

    const base = {
      periodo: form.periodo,
      rubro: form.rubro,
      clase_prorrateo_id: form.modo === "clase" ? Number(form.clase_prorrateo_id) : null,
      departamento_id: form.modo === "depto" ? Number(form.departamento_id) : null,
      proveedor_id: Number(form.proveedor_id),
      concepto: form.concepto,
      monto: Number(form.monto),
      forma_pago: form.forma_pago,
      fecha_pago: form.fecha_pago,
      numero_factura: form.numero_factura || null,
      fecha_factura: form.fecha_factura || null,
    };

    let r;
    if (esEditar) {
      r = await actualizarGasto(gastoInicial.id, {
        ...base,
        cuota_actual: form.cuota_actual ? Number(form.cuota_actual) : null,
        cuota_total: form.cuota_total ? Number(form.cuota_total) : null,
      });
      if (r.status === 200) {
        onGuardado();
        return;
      }
    } else if (form.es_plan) {
      r = await crearPlanCuotas({
        ...base,
        cuota_total: Number(form.cuota_total_plan),
      });
      if (r.status === 201) {
        onGuardado();
        return;
      }
    } else {
      r = await crearGasto({
        ...base,
        cuota_actual: form.cuota_actual ? Number(form.cuota_actual) : null,
        cuota_total: form.cuota_total ? Number(form.cuota_total) : null,
      });
      if (r.status === 201) {
        onGuardado();
        return;
      }
    }

    setError(r.data?.detail || "No se pudo guardar.");
    setGuardando(false);
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{esEditar ? "Editar gasto" : "Nuevo gasto"}</h3>
        <form onSubmit={onSubmit}>
          <label>Período <input
            type="month"
            value={form.periodo}
            onChange={(e) => set("periodo", e.target.value)}
            required
          /></label>

          <label>Rubro <select value={form.rubro} onChange={(e) => set("rubro", e.target.value)} required>
            {RUBROS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select></label>

          <fieldset>
            <legend>Tipo de prorrateo</legend>
            <label>
              <input type="radio" name="modo" value="clase"
                checked={form.modo === "clase"} onChange={() => set("modo", "clase")} />
              Se prorratea (clase)
            </label>
            <label>
              <input type="radio" name="modo" value="depto"
                checked={form.modo === "depto"} onChange={() => set("modo", "depto")} />
              Particular a un departamento
            </label>
            {form.modo === "clase" && (
              <select value={form.clase_prorrateo_id}
                onChange={(e) => set("clase_prorrateo_id", e.target.value)} required>
                {clases.map((c) => <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>)}
              </select>
            )}
            {form.modo === "depto" && (
              <select value={form.departamento_id}
                onChange={(e) => set("departamento_id", e.target.value)} required>
                <option value="">— Elegí uno —</option>
                {departamentos.map((d) => <option key={d.id} value={d.id}>{d.codigo}</option>)}
              </select>
            )}
          </fieldset>

          <label>Proveedor <select value={form.proveedor_id}
            onChange={(e) => set("proveedor_id", e.target.value)} required>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.razon_social}</option>)}
          </select></label>

          <label>Concepto <textarea value={form.concepto}
            onChange={(e) => set("concepto", e.target.value)} maxLength={500} required /></label>

          <label>Monto <input type="number" min="0.01" step="0.01"
            value={form.monto} onChange={(e) => set("monto", e.target.value)} required /></label>

          <label>Forma de pago <select value={form.forma_pago}
            onChange={(e) => set("forma_pago", e.target.value)} required>
            {FORMAS_PAGO.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select></label>

          <label>Fecha de pago <input type="date"
            value={form.fecha_pago} onChange={(e) => set("fecha_pago", e.target.value)} required /></label>

          <label>N° de factura (opcional) <input type="text" maxLength={50}
            value={form.numero_factura} onChange={(e) => set("numero_factura", e.target.value)} /></label>

          <label>Fecha de factura (opcional) <input type="date"
            value={form.fecha_factura} onChange={(e) => set("fecha_factura", e.target.value)} /></label>

          {!esEditar && (
            <fieldset>
              <legend>Plan de cuotas</legend>
              <label>
                <input type="checkbox"
                  checked={form.es_plan}
                  onChange={(e) => set("es_plan", e.target.checked)} />
                Es en cuotas (replicar a N períodos consecutivos)
              </label>
              {form.es_plan && (
                <label>Total de cuotas <input type="number" min="2"
                  value={form.cuota_total_plan}
                  onChange={(e) => set("cuota_total_plan", e.target.value)} required /></label>
              )}
            </fieldset>
          )}

          {esEditar && (
            <fieldset>
              <legend>Cuota (si aplica)</legend>
              <label>Cuota actual <input type="number" min="1"
                value={form.cuota_actual} onChange={(e) => set("cuota_actual", e.target.value)} /></label>
              <label>Cuota total <input type="number" min="1"
                value={form.cuota_total} onChange={(e) => set("cuota_total", e.target.value)} /></label>
            </fieldset>
          )}

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
