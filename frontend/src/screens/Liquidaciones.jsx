import { useEffect, useState } from "react";
import Tarjeta from "../components/Tarjeta";
import Tabs from "../components/Tabs";
import Modal from "../components/Modal";
import {
  listarLiquidaciones,
  crearLiquidacion,
  actualizarLiquidacion,
  eliminarLiquidacion,
} from "../api/liquidaciones";
import { listarEmpleados } from "../api/empleados";
import { listarHaberes } from "../api/haberes";

// ─── constantes ────────────────────────────────────────────────────────────

const TABS = [
  { path: "/liquidaciones", label: "Del mes", end: true },
  { path: "/liquidaciones/historial", label: "Historial" },
];

const TIPOS_HABER = {
  monto_fijo: "Monto fijo",
  porcentaje_sobre_basico: "% sobre básico",
  cantidad_x_valor: "Cantidad × valor",
};

const TIPOS_CONCEPTO = {
  descuento: "Descuento",
  contribucion: "Contribución",
};

function periodoActual() {
  const hoy = new Date();
  const anio = hoy.getFullYear();
  const mes = String(hoy.getMonth() + 1).padStart(2, "0");
  return `${anio}-${mes}`;
}

function formatARS(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 2,
  });
}

// ─── componente principal ───────────────────────────────────────────────────

export default function Liquidaciones({ vistaHistorial = false }) {
  const [liquidaciones, setLiquidaciones] = useState([]);
  const [empleados, setEmpleados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null); // null | { tipo: "crear" | "editar", liquidacion? }

  // filtros
  const [filtroPeriodo, setFiltroPeriodo] = useState(
    vistaHistorial ? "" : periodoActual()
  );
  const [filtroEmpleadoId, setFiltroEmpleadoId] = useState("");

  // ── carga de catálogos ──
  useEffect(() => {
    async function cargarEmpleados() {
      const r = await listarEmpleados({ activo: true });
      if (r.status === 200) setEmpleados(r.data);
    }
    cargarEmpleados();
  }, []);

  // ── carga de liquidaciones ──
  async function recargar() {
    setCargando(true);
    const params = {};
    if (filtroPeriodo) params.periodo = filtroPeriodo;
    if (filtroEmpleadoId) params.empleado_id = Number(filtroEmpleadoId);
    const r = await listarLiquidaciones(params);
    if (r.status === 200) {
      setLiquidaciones(r.data);
      setError(null);
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudieron cargar las liquidaciones.");
    }
    setCargando(false);
  }

  useEffect(() => {
    recargar();
  }, [filtroPeriodo, filtroEmpleadoId]);

  // ── acciones ──
  async function handleEliminar(liq) {
    if (
      !confirm(
        `¿Eliminar la liquidación de ${nombreEmpleado(liq.empleado_id)} (${liq.periodo})? Se eliminarán también los gastos generados.`
      )
    )
      return;
    const r = await eliminarLiquidacion(liq.id);
    if (r.status === 204) {
      recargar();
    } else if (r.status !== 401) {
      setError(r.data?.detail || "No se pudo eliminar la liquidación.");
    }
  }

  function nombreEmpleado(id) {
    return empleados.find((e) => e.id === id)?.nombre_completo || `#${id}`;
  }

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Liquidaciones de personal</h2>
        <div className="cabecera-acciones">
          <button type="button" onClick={() => setModal({ tipo: "crear" })}>
            + Nueva liquidación
          </button>
        </div>
      </header>

      <Tabs tabs={TABS} />

      {/* filtros */}
      <section className="filtros-barra" aria-label="Filtros">
        <label>
          Período
          <input
            type="month"
            value={filtroPeriodo}
            onChange={(e) => setFiltroPeriodo(e.target.value)}
          />
        </label>
        <label>
          Empleado
          <select
            value={filtroEmpleadoId}
            onChange={(e) => setFiltroEmpleadoId(e.target.value)}
          >
            <option value="">— Todos —</option>
            {empleados.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.nombre_completo}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="boton-secundario"
          onClick={() => {
            setFiltroPeriodo(vistaHistorial ? "" : periodoActual());
            setFiltroEmpleadoId("");
          }}
        >
          Limpiar
        </button>
      </section>

      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {cargando && <p>Cargando…</p>}
      {!cargando && !error && liquidaciones.length === 0 && (
        <p>No hay liquidaciones para los filtros seleccionados.</p>
      )}

      <ul className="lista-config">
        {liquidaciones.map((liq) => (
          <li key={liq.id}>
            <TarjetaLiquidacion
              liq={liq}
              nombreEmpleado={nombreEmpleado(liq.empleado_id)}
              onEditar={() => setModal({ tipo: "editar", liquidacion: liq })}
              onEliminar={() => handleEliminar(liq)}
            />
          </li>
        ))}
      </ul>

      {modal?.tipo === "crear" && (
        <ModalLiquidacion
          titulo="Nueva liquidación"
          empleados={empleados}
          periodoInicial={filtroPeriodo || periodoActual()}
          onCerrar={() => setModal(null)}
          onGuardar={async (payload) => {
            const r = await crearLiquidacion(payload);
            if (r.status === 201) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al crear la liquidación.";
          }}
        />
      )}

      {modal?.tipo === "editar" && (
        <ModalLiquidacion
          titulo={`Editar liquidación — ${nombreEmpleado(modal.liquidacion.empleado_id)} (${modal.liquidacion.periodo})`}
          empleados={empleados}
          periodoInicial={modal.liquidacion.periodo}
          inicial={modal.liquidacion}
          onCerrar={() => setModal(null)}
          onGuardar={async (payload) => {
            // PATCH no acepta empleado_id ni periodo
            const { empleado_id: _e, periodo: _p, ...resto } = payload;
            const r = await actualizarLiquidacion(modal.liquidacion.id, resto);
            if (r.status === 200) {
              setModal(null);
              recargar();
              return null;
            }
            return r.data?.detail || "Error al editar la liquidación.";
          }}
          esEdicion
        />
      )}
    </main>
  );
}

// ─── tarjeta con detalle expandible ────────────────────────────────────────

function TarjetaLiquidacion({ liq, nombreEmpleado, onEditar, onEliminar }) {
  const totalDescuentos = liq.detalle
    .filter((d) => d.concepto_tipo === "descuento")
    .reduce((acc, d) => acc + d.monto, 0);
  const totalContrib = liq.detalle
    .filter((d) => d.concepto_tipo === "contribucion")
    .reduce((acc, d) => acc + d.monto, 0);
  const sueldoNeto = liq.sueldo_bruto - totalDescuentos;

  return (
    <Tarjeta>
      <h3>
        {nombreEmpleado}{" "}
        <span className="meta">— {liq.periodo}</span>
      </h3>
      <p className="meta">
        Bruto: <strong>{formatARS(liq.sueldo_bruto)}</strong> / Neto:{" "}
        <strong>{formatARS(sueldoNeto)}</strong>
      </p>

      <details>
        <summary className="detalle-toggle">Ver detalle completo</summary>

        <section className="liquidacion-seccion">
          <h4>Haberes</h4>
          {liq.haberes.length === 0 ? (
            <p className="meta">Sin haberes.</p>
          ) : (
            <table className="liquidacion-tabla">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Valor</th>
                  <th>Cantidad</th>
                  <th className="col-monto">Monto</th>
                </tr>
              </thead>
              <tbody>
                {liq.haberes.map((h) => (
                  <tr key={h.id}>
                    <td>{h.nombre}</td>
                    <td>{h.tipo ? (TIPOS_HABER[h.tipo] || h.tipo) : "Ad hoc"}</td>
                    <td>{h.valor != null ? h.valor : "—"}</td>
                    <td>{h.cantidad != null ? h.cantidad : "—"}</td>
                    <td className="col-monto">{formatARS(h.monto)}</td>
                  </tr>
                ))}
                <tr className="fila-total">
                  <td colSpan={4}>
                    <strong>Sueldo bruto</strong>
                  </td>
                  <td className="col-monto">
                    <strong>{formatARS(liq.sueldo_bruto)}</strong>
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </section>

        <section className="liquidacion-seccion">
          <h4>Descuentos y contribuciones</h4>
          {liq.detalle.length === 0 ? (
            <p className="meta">Sin conceptos aplicados.</p>
          ) : (
            <table className="liquidacion-tabla">
              <thead>
                <tr>
                  <th>Concepto</th>
                  <th>Tipo</th>
                  <th>%</th>
                  <th className="col-monto">Monto</th>
                </tr>
              </thead>
              <tbody>
                {liq.detalle.map((d) => (
                  <tr key={d.id}>
                    <td>{d.concepto_nombre}</td>
                    <td>{TIPOS_CONCEPTO[d.concepto_tipo] || d.concepto_tipo}</td>
                    <td>{d.porcentaje_aplicado}%</td>
                    <td className="col-monto">{formatARS(d.monto)}</td>
                  </tr>
                ))}
                {totalDescuentos > 0 && (
                  <tr className="fila-subtotal">
                    <td colSpan={3}>Total descuentos</td>
                    <td className="col-monto">{formatARS(totalDescuentos)}</td>
                  </tr>
                )}
                {totalContrib > 0 && (
                  <tr className="fila-subtotal">
                    <td colSpan={3}>Total contribuciones</td>
                    <td className="col-monto">{formatARS(totalContrib)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </section>

        <p className="liquidacion-neto">
          Sueldo neto a pagar: <strong>{formatARS(sueldoNeto)}</strong>
        </p>
      </details>

      <div className="tarjeta-acciones">
        <button type="button" onClick={onEditar}>
          Editar
        </button>
        <button type="button" className="boton-peligro" onClick={onEliminar}>
          Eliminar
        </button>
      </div>
    </Tarjeta>
  );
}

// ─── modal de crear / editar ────────────────────────────────────────────────

function ModalLiquidacion({
  titulo,
  empleados,
  periodoInicial,
  inicial,
  onCerrar,
  onGuardar,
  esEdicion = false,
}) {
  // catálogo de haberes del sistema
  const [catalogoHaberes, setCatalogoHaberes] = useState([]);
  const [cargandoCatalogo, setCargandoCatalogo] = useState(true);

  useEffect(() => {
    async function cargar() {
      const r = await listarHaberes({ activo: true });
      if (r.status === 200) setCatalogoHaberes(r.data);
      setCargandoCatalogo(false);
    }
    cargar();
  }, []);

  // ── estado del formulario ──
  const [empleadoId, setEmpleadoId] = useState(
    inicial ? String(inicial.empleado_id) : (empleados[0]?.id ? String(empleados[0].id) : "")
  );
  const [periodo, setPeriodo] = useState(periodoInicial || periodoActual());

  // Haberes del catálogo: array de { haber_id, valor_override, cantidad, _info }
  // Se pre-populate desde la liquidación existente o desde el catálogo vacío
  const [haberesForm, setHaberesForm] = useState(() => {
    if (inicial && inicial.haberes) {
      // Reconstruir desde la liquidación guardada. Solo los que tienen tipo (no ad-hoc)
      return inicial.haberes
        .filter((h) => h.tipo !== null)
        .map((h) => ({
          haber_id: null, // se resolverá tras cargar el catálogo
          _nombre: h.nombre,
          _tipo: h.tipo,
          valor_override: h.valor != null ? String(h.valor) : "",
          cantidad: h.cantidad != null ? String(h.cantidad) : "",
          _activo: true,
        }));
    }
    return [];
  });

  // Una vez que el catálogo llega, mapear los nombres de la liquidación existente a ids
  const [catalogoCargado, setCatalogoCargado] = useState(false);
  useEffect(() => {
    if (cargandoCatalogo || catalogoCargado) return;
    setCatalogoCargado(true);

    if (inicial && inicial.haberes) {
      const snap = inicial.haberes.filter((h) => h.tipo !== null);
      const nuevos = snap.map((h) => {
        const match = catalogoHaberes.find((c) => c.nombre === h.nombre);
        return {
          haber_id: match ? match.id : null,
          _nombre: h.nombre,
          _tipo: h.tipo,
          valor_override: h.valor != null ? String(h.valor) : "",
          cantidad: h.cantidad != null ? String(h.cantidad) : "",
          _activo: true,
        };
      });
      setHaberesForm(nuevos);
    }
  }, [cargandoCatalogo]);

  // Haberes ad-hoc: array de { nombre, monto }
  const [adHocForm, setAdHocForm] = useState(() => {
    if (inicial && inicial.haberes) {
      return inicial.haberes
        .filter((h) => h.tipo === null)
        .map((h) => ({ nombre: h.nombre, monto: String(h.monto) }));
    }
    return [];
  });

  const [guardando, setGuardando] = useState(false);
  const [errorForm, setErrorForm] = useState(null);

  // ── helpers para haber del catálogo ──
  function addHaberCatalogo(haberId) {
    const haber = catalogoHaberes.find((h) => String(h.id) === String(haberId));
    if (!haber) return;
    // evitar duplicados
    if (haberesForm.some((hf) => String(hf.haber_id) === String(haberId))) return;
    setHaberesForm((prev) => [
      ...prev,
      {
        haber_id: haber.id,
        _nombre: haber.nombre,
        _tipo: haber.tipo,
        valor_override: String(haber.valor_default),
        cantidad: haber.tipo === "cantidad_x_valor" ? "1" : "",
        _activo: true,
      },
    ]);
  }

  function removeHaberCatalogo(idx) {
    setHaberesForm((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateHaberCatalogo(idx, campo, valor) {
    setHaberesForm((prev) =>
      prev.map((hf, i) => (i === idx ? { ...hf, [campo]: valor } : hf))
    );
  }

  // ── helpers para ad-hoc ──
  function addAdHoc() {
    setAdHocForm((prev) => [...prev, { nombre: "", monto: "" }]);
  }

  function removeAdHoc(idx) {
    setAdHocForm((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateAdHoc(idx, campo, valor) {
    setAdHocForm((prev) =>
      prev.map((ah, i) => (i === idx ? { ...ah, [campo]: valor } : ah))
    );
  }

  // ── cálculo de bruto estimado ──
  function calcularBrutoEstimado() {
    const empleado = empleados.find((e) => String(e.id) === String(empleadoId));
    const basico = empleado?.sueldo_basico || 0;
    let total = 0;
    for (const hf of haberesForm) {
      const val = parseFloat(hf.valor_override) || 0;
      const cant = parseFloat(hf.cantidad) || 1;
      if (hf._tipo === "monto_fijo") total += val;
      else if (hf._tipo === "porcentaje_sobre_basico") total += (basico * val) / 100;
      else if (hf._tipo === "cantidad_x_valor") total += cant * val;
    }
    for (const ah of adHocForm) {
      total += parseFloat(ah.monto) || 0;
    }
    return total;
  }

  // ── submit ──
  async function onSubmit(e) {
    e.preventDefault();
    setErrorForm(null);

    // validar haberes del catálogo sin id mapeado
    const sinId = haberesForm.filter((hf) => !hf.haber_id);
    if (sinId.length > 0) {
      setErrorForm(
        `No se pudo resolver el id de: ${sinId.map((h) => h._nombre).join(", ")}. Eliminalo y volvé a agregarlo.`
      );
      return;
    }

    const haberes = haberesForm.map((hf) => {
      const item = { haber_id: Number(hf.haber_id) };
      if (hf.valor_override !== "") item.valor_override = parseFloat(hf.valor_override);
      if (hf._tipo === "cantidad_x_valor" && hf.cantidad !== "")
        item.cantidad = parseFloat(hf.cantidad);
      return item;
    });

    const haberes_ad_hoc = adHocForm
      .filter((ah) => ah.nombre.trim() && ah.monto)
      .map((ah) => ({ nombre: ah.nombre.trim(), monto: parseFloat(ah.monto) }));

    const payload = {
      empleado_id: Number(empleadoId),
      periodo,
      haberes,
      haberes_ad_hoc,
    };

    setGuardando(true);
    const err = await onGuardar(payload);
    if (err) {
      setErrorForm(err);
      setGuardando(false);
    }
  }

  const brutoEstimado = calcularBrutoEstimado();

  // ids ya seleccionados para excluir del selector
  const idsSeleccionados = new Set(haberesForm.map((hf) => String(hf.haber_id)));

  return (
    <Modal titulo={titulo} onClose={onCerrar}>
      {cargandoCatalogo ? (
        <p>Cargando catálogo de haberes…</p>
      ) : (
        <form onSubmit={onSubmit} noValidate>
          {/* empleado y período — solo en creación */}
          {!esEdicion && (
            <>
              <label>
                Empleado
                <select
                  value={empleadoId}
                  onChange={(e) => setEmpleadoId(e.target.value)}
                  required
                >
                  <option value="">— Seleccioná un empleado —</option>
                  {empleados.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.nombre_completo}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Período
                <input
                  type="month"
                  value={periodo}
                  onChange={(e) => setPeriodo(e.target.value)}
                  required
                />
              </label>
            </>
          )}

          {/* haberes del catálogo */}
          <fieldset className="liquidacion-fieldset">
            <legend>Haberes del catálogo</legend>

            {haberesForm.length === 0 && (
              <p className="meta">
                No hay haberes del catálogo. Agregá uno con el selector de abajo.
              </p>
            )}

            {haberesForm.map((hf, idx) => (
              <div key={idx} className="haber-fila">
                <span className="haber-nombre">
                  {hf._nombre}
                  <span className="meta"> ({TIPOS_HABER[hf._tipo] || hf._tipo})</span>
                </span>

                {hf._tipo === "cantidad_x_valor" && (
                  <label className="haber-campo">
                    Cantidad
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={hf.cantidad}
                      onChange={(e) =>
                        updateHaberCatalogo(idx, "cantidad", e.target.value)
                      }
                      required
                    />
                  </label>
                )}

                <label className="haber-campo">
                  {hf._tipo === "porcentaje_sobre_basico"
                    ? "Porcentaje (%)"
                    : "Valor"}
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={hf.valor_override}
                    onChange={(e) =>
                      updateHaberCatalogo(idx, "valor_override", e.target.value)
                    }
                    required
                  />
                </label>

                <button
                  type="button"
                  className="boton-peligro boton-chico"
                  onClick={() => removeHaberCatalogo(idx)}
                  aria-label={`Eliminar ${hf._nombre}`}
                >
                  ✕
                </button>
              </div>
            ))}

            {/* selector para agregar haberes del catálogo */}
            <div className="haber-agregar">
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) {
                    addHaberCatalogo(e.target.value);
                    e.target.value = "";
                  }
                }}
              >
                <option value="">+ Agregar haber del catálogo…</option>
                {catalogoHaberes
                  .filter((h) => !idsSeleccionados.has(String(h.id)))
                  .map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.nombre} ({TIPOS_HABER[h.tipo] || h.tipo})
                    </option>
                  ))}
              </select>
            </div>
          </fieldset>

          {/* haberes ad-hoc */}
          <fieldset className="liquidacion-fieldset">
            <legend>Haberes adicionales (ad hoc)</legend>

            {adHocForm.length === 0 && (
              <p className="meta">Sin haberes adicionales.</p>
            )}

            {adHocForm.map((ah, idx) => (
              <div key={idx} className="haber-fila">
                <label className="haber-campo haber-campo--nombre">
                  Nombre
                  <input
                    type="text"
                    value={ah.nombre}
                    onChange={(e) => updateAdHoc(idx, "nombre", e.target.value)}
                    placeholder="Ej: SAC proporcional"
                    maxLength={120}
                    required
                  />
                </label>
                <label className="haber-campo">
                  Monto
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={ah.monto}
                    onChange={(e) => updateAdHoc(idx, "monto", e.target.value)}
                    required
                  />
                </label>
                <button
                  type="button"
                  className="boton-peligro boton-chico"
                  onClick={() => removeAdHoc(idx)}
                  aria-label="Eliminar haber adicional"
                >
                  ✕
                </button>
              </div>
            ))}

            <button type="button" className="boton-secundario" onClick={addAdHoc}>
              + Agregar adicional
            </button>
          </fieldset>

          {/* estimación */}
          {brutoEstimado > 0 && (
            <p className="liquidacion-estimacion">
              Bruto estimado:{" "}
              <strong>{formatARS(brutoEstimado)}</strong>
            </p>
          )}

          {errorForm && (
            <p role="alert" className="error-banner">
              {errorForm}
            </p>
          )}

          <div className="modal-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={onCerrar}
              disabled={guardando}
            >
              Cancelar
            </button>
            <button type="submit" disabled={guardando || !empleadoId}>
              {guardando ? "Guardando…" : esEdicion ? "Recalcular y guardar" : "Liquidar"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
