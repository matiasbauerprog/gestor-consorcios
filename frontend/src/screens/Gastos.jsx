import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Tarjeta from "../components/Tarjeta";
import ModalPagarGasto from "../components/ModalPagarGasto";
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
import {
  listarGastos,
  crearGasto,
  crearPlanCuotas,
  actualizarGasto,
  eliminarGasto,
} from "../api/gastos";
import { listarClasesProrrateo } from "../api/clasesProrrateo";
import { listarProveedores } from "../api/proveedores";
import { listarDepartamentos } from "../api/departamentos";
import { listarPeriodos } from "../api/periodos";
import { listarCajas } from "../api/cajas";
import { formatFecha } from "../utils/fechas";
import { formatearMonto } from "../utils/montos";

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

export default function Gastos() {
  const navigate = useNavigate();
  const [gastos, setGastos] = useState([]);
  const [clases, setClases] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [departamentos, setDepartamentos] = useState([]);
  const [cajas, setCajas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const [modalPagar, setModalPagar] = useState(null);
  const [cerrados, setCerrados] = useState(new Set());

  // El período no es un filtro: es el contexto de trabajo (define el cierre).
  // Siempre hay uno seleccionado; default = mes actual.
  const [periodo, setPeriodo] = useState(() => new Date().toISOString().slice(0, 7));

  const [filtros, setFiltros] = useState({
    rubro: "",
    clase_prorrateo_id: "",
    proveedor_id: "",
    departamento_id: "",
  });

  async function cargarCatalogos() {
    const [rClases, rProv, rDeptos, rCajas] = await Promise.all([
      listarClasesProrrateo({ activa: true }),
      listarProveedores({ activo: true }),
      listarDepartamentos(),
      listarCajas(),
    ]);
    if (rClases.status === 200) setClases(rClases.data);
    if (rProv.status === 200) setProveedores(rProv.data);
    if (rDeptos.status === 200) setDepartamentos(rDeptos.data);
    if (rCajas.status === 200) setCajas(rCajas.data);
  }

  async function recargar() {
    setCargando(true);
    const r = await listarGastos({ ...filtros, periodo });
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
    (async () => {
      const r = await listarPeriodos();
      if (r.status === 200) {
        setCerrados(new Set(r.data.map((p) => p.periodo)));
      }
    })();
  }, []);

  useEffect(() => {
    recargar();
  }, [
    periodo,
    filtros.rubro,
    filtros.clase_prorrateo_id,
    filtros.proveedor_id,
    filtros.departamento_id,
  ]);

  function cambiarFiltro(campo, valor) {
    setFiltros({ ...filtros, [campo]: valor });
  }

  function moverPeriodo(delta) {
    const [anio, mes] = periodo.split("-").map(Number);
    const d = new Date(anio, mes - 1 + delta, 1);
    setPeriodo(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
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

  function cajaPorId(id) {
    return cajas.find((c) => c.id === id)?.nombre || "—";
  }

  const columnas = [
    { clave: "concepto", titulo: "Concepto", prioridad: 1, ancho: "auto", celda: (g) => g.concepto },
    { clave: "rubro", titulo: "Rubro", prioridad: 2, ancho: "auto", celda: (g) => labelRubro(g.rubro) },
    { clave: "proveedor", titulo: "Proveedor", prioridad: 3, ancho: "auto", celda: (g) => proveedorPorId(g.proveedor_id) },
    {
      clave: "destino",
      titulo: "Clase / Depto",
      prioridad: 3,
      ancho: "auto",
      celda: (g) =>
        g.clase_prorrateo_id !== null
          ? `Clase ${clasePorId(g.clase_prorrateo_id)}`
          : `Depto ${deptoPorId(g.departamento_id)}`,
    },
    { clave: "caja", titulo: "Caja", prioridad: 3, ancho: "auto", celda: (g) => cajaPorId(g.caja_id) },
    {
      clave: "monto",
      titulo: "Monto",
      className: "col-monto",
      prioridad: 1,
      ancho: "14ch",
      celda: (g) => formatearMonto(g.monto),
    },
    {
      clave: "pago",
      titulo: "Pago",
      prioridad: 2,
      ancho: "10ch",
      celda: (g) =>
        g.pagado ? (
          formatFecha(g.fecha_pago)
        ) : cerrados.has(g.periodo) ? (
          <span className="meta">Sin pagar</span>
        ) : (
          <button type="button" onClick={() => setModalPagar(g)}>
            Confirmar
          </button>
        ),
    },
    {
      clave: "acciones",
      titulo: "",
      className: "col-acciones",
      prioridad: 1,
      ancho: "4rem",
      celda: (g) =>
        cerrados.has(g.periodo) ? (
          <span title="Período cerrado — no editable">🔒</span>
        ) : (
          <MenuAcciones
            acciones={[
              { label: "Editar", onSelect: () => setModal({ tipo: "editar", gasto: g }) },
              { label: "Eliminar", onSelect: () => handleBorrar(g), peligro: true },
            ]}
            etiqueta={`Acciones de ${g.concepto}`}
          />
        ),
    },
  ];

  return (
    <section className="pantalla-ancha">
      <header className="cabecera-pantalla">
        <h2>Gastos</h2>
        <button
          type="button"
          className="boton-secundario"
          onClick={() => navigate("/gastos/habituales")}
        >
          Gastos recurrentes
        </button>
      </header>

      <section className="barra-periodo">
        <div className="barra-periodo-selector">
          <button
            type="button"
            className="periodo-nav"
            aria-label="Período anterior"
            onClick={() => moverPeriodo(-1)}
          >
            ‹
          </button>
          <input
            type="month"
            value={periodo}
            onChange={(e) => e.target.value && setPeriodo(e.target.value)}
          />
          <button
            type="button"
            className="periodo-nav"
            aria-label="Período siguiente"
            onClick={() => moverPeriodo(1)}
          >
            ›
          </button>
          {cerrados.has(periodo) ? (
            <span className="estado-badge" title="Este período ya fue cerrado">
              <span className="estado-punto" style={{ background: "#6b7280" }} aria-hidden="true" />
              Cerrado
            </span>
          ) : (
            <span className="estado-badge" title="Los gastos de este período aún se pueden modificar">
              <span className="estado-punto" style={{ background: "#16a34a" }} aria-hidden="true" />
              Abierto
            </span>
          )}
        </div>
        <div className="cabecera-acciones">
          {!cerrados.has(periodo) && (
            <>
              <button type="button" onClick={() => setModal({ tipo: "crear" })}>
                + Nuevo gasto
              </button>
              <button
                type="button"
                onClick={() => navigate(`/cierre-de-periodo?periodo=${periodo}`)}
              >
                Cerrar período
              </button>
            </>
          )}
        </div>
      </section>

      <section className="filtros-gastos">
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

      {error && <p role="alert" className="error-banner">{error}</p>}
      {cargando && <p>Cargando…</p>}

      {!cargando && (
      <TablaResponsive
        columnas={columnas}
        filas={gastos}
        claveFila={(g) => g.id}
        vacio="No hay gastos con esos filtros."
        renderTarjeta={(g) => (
          <Tarjeta>
            <h3>{labelRubro(g.rubro)} · {g.concepto}</h3>
            <p className="meta">
              {formatearMonto(g.monto)} · {g.periodo} ·{" "}
              {g.pagado ? `pagó ${formatFecha(g.fecha_pago)}` : "sin pagar"}
            </p>
            <p className="meta">Proveedor: {proveedorPorId(g.proveedor_id)}</p>
            <p className="meta">
              {g.clase_prorrateo_id !== null
                ? <>Clase {clasePorId(g.clase_prorrateo_id)}</>
                : <>Particular a {deptoPorId(g.departamento_id)}</>}
              {g.cuota_actual && <> · Cuota {g.cuota_actual}/{g.cuota_total}</>}
              {g.gasto_habitual_id && <> · Recurrente</>}
            </p>
            <p className="meta">Caja: {cajaPorId(g.caja_id)}</p>
            <div className="tarjeta-acciones">
              {cerrados.has(g.periodo) ? (
                <span title="Período cerrado — no editable">🔒</span>
              ) : (
                <>
                  {!g.pagado && (
                    <button type="button" onClick={() => setModalPagar(g)}>
                      Confirmar pago
                    </button>
                  )}
                  <button type="button" onClick={() => setModal({ tipo: "editar", gasto: g })}>
                    Editar
                  </button>
                  <button type="button" className="boton-borrar" onClick={() => handleBorrar(g)}>
                    Eliminar
                  </button>
                </>
              )}
            </div>
          </Tarjeta>
        )}
      />
      )}

      {modal && (
        <ModalGasto
          tipo={modal.tipo}
          gastoInicial={modal.gasto}
          periodoActivo={periodo}
          clases={clases}
          proveedores={proveedores}
          departamentos={departamentos}
          cajas={cajas}
          onCerrar={() => setModal(null)}
          onGuardado={() => {
            setModal(null);
            recargar();
          }}
        />
      )}

      {modalPagar && (
        <ModalPagarGasto
          gasto={modalPagar}
          cajas={cajas}
          onClose={() => setModalPagar(null)}
          onPagado={() => { setModalPagar(null); recargar(); }}
        />
      )}
    </section>
  );
}

function ModalGasto({ tipo, gastoInicial, periodoActivo, clases, proveedores, departamentos, cajas, onCerrar, onGuardado }) {
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
        caja_id: gastoInicial.caja_id || "",
      }
    : {
        periodo: periodoActivo || "",
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
        caja_id: cajas[0]?.id ?? "",
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
      caja_id: Number(form.caja_id),
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

          <label>Caja origen <select value={form.caja_id}
            onChange={(e) => set("caja_id", e.target.value ? Number(e.target.value) : "")} required>
            <option value="">— Elegí una —</option>
            {cajas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select></label>

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
