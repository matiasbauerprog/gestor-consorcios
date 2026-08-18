import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarExpensas, crearExpensa, eliminarExpensa } from "../api/expensas";
import { listarDepartamentos } from "../api/departamentos";
import { listarPeriodos } from "../api/periodos";
import Modal from "../components/Modal";
import ModalComprobantesExpensa from "../components/ModalComprobantesExpensa";
import ModalEnvioPdfs from "../components/ModalEnvioPdfs";
import SelectorDepartamento from "../components/SelectorDepartamento";
import TarjetaExpensa from "../components/TarjetaExpensa";
import TablaResponsive from "../components/TablaResponsive";
import BadgeEstado from "../components/BadgeEstado";
import MenuAcciones from "../components/MenuAcciones";
import { formatFecha } from "../utils/fechas";
import { formatearInteres, formatearMonto } from "../utils/montos";
import { abrirPdfExpensa } from "../api/pdf";
import { ANCHO_FECHA_MONTO, ANCHO_MONTO, ANCHO_PERIODO } from "../utils/anchosColumnas";

// Las etiquetas replican las de BadgeEstado (donde `pagada` se muestra como
// "Confirmada"): el filtro y el badge de la fila tienen que decir lo mismo.
const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "pendiente", label: "Pendientes" },
  { value: "parcial", label: "Parciales" },
  { value: "vencida", label: "Vencidas" },
  { value: "pagada", label: "Confirmadas" },
];

export default function Expensas({ embebida = false }) {
  const { user, token } = useAuth();
  const [expensas, setExpensas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);
  const [departamentoSeleccionado, setDepartamentoSeleccionado] = useState(null);
  const [modalCrearAbierto, setModalCrearAbierto] = useState(false);
  const [modalEliminar, setModalEliminar] = useState(null);
  const [modalComprobantes, setModalComprobantes] = useState(null);
  const [errorAccion, setErrorAccion] = useState(null);
  const [eliminando, setEliminando] = useState(false);
  const [departamentos, setDepartamentos] = useState([]);
  const [filtroPeriodo, setFiltroPeriodo] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [periodosCerradosSet, setPeriodosCerradosSet] = useState(new Set());
  const [modalEnvio, setModalEnvio] = useState(null);

  const esAdmin = user.rol === "administracion";

  useEffect(() => {
    if (!esAdmin) return;
    (async () => {
      const r = await listarDepartamentos();
      if (r.status === 200) {
        setDepartamentos(r.data);
      }
    })();
  }, [esAdmin]);

  useEffect(() => {
    (async () => {
      const r = await listarPeriodos();
      if (r.status === 200) {
        setPeriodosCerradosSet(new Set(r.data.map(p => p.periodo)));
      }
    })();
  }, []);

  const deptoById = Object.fromEntries(departamentos.map((d) => [d.id, d]));

  function deptoLabel(departamentoId) {
    const d = deptoById[departamentoId];
    return d ? `${d.codigo} — ${d.descripcion}` : `#${departamentoId}`;
  }

  // Dos pasos a propósito: el banner de envío de PDFs cuenta las expensas del
  // período completo (se mandan todas), así que no puede leer la lista ya
  // filtrada por estado.
  const expensasDelPeriodo = filtroPeriodo
    ? expensas.filter(e => e.periodo === filtroPeriodo)
    : expensas;

  const expensasFiltradas = filtroEstado
    ? expensasDelPeriodo.filter(e => e.estado_calculado === filtroEstado)
    : expensasDelPeriodo;

  async function cargar() {
    setCargando(true);
    const params = {};
    if (esAdmin && departamentoSeleccionado !== null) {
      params.departamento_id = departamentoSeleccionado;
    }
    const r = await listarExpensas(params);
    if (r.status === 200) {
      setExpensas(r.data);
      setErrorCarga(null);
    } else if (r.status !== 401) {
      setErrorCarga("No se pudieron cargar las expensas.");
    }
    setCargando(false);
  }

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [esAdmin, departamentoSeleccionado]);

  function handleExpensaCreada(nueva) {
    setExpensas((prev) => [nueva, ...prev]);
    setModalCrearAbierto(false);
    setErrorAccion(null);
  }

  async function handleEliminar() {
    if (!modalEliminar) return;
    setEliminando(true);
    setErrorAccion(null);
    const r = await eliminarExpensa(modalEliminar.id);
    setEliminando(false);
    if (r.status === 204) {
      setExpensas((prev) => prev.filter((e) => e.id !== modalEliminar.id));
      setModalEliminar(null);
      return;
    }
    if (r.status === 409) {
      setErrorAccion(
        r.data?.detail || "No se puede eliminar: la expensa tiene pagos.",
      );
      setModalEliminar(null);
      return;
    }
    if (r.status === 404) {
      setErrorAccion("La expensa ya no existe.");
      setModalEliminar(null);
      return;
    }
    if (r.status !== 401) {
      setErrorAccion("No se pudo eliminar la expensa.");
      setModalEliminar(null);
    }
  }

  async function handleAbrirPdf(expensa) {
    try {
      await abrirPdfExpensa(expensa.id);
    } catch (err) {
      setErrorAccion(`No se pudo abrir el PDF: ${err.message}`);
    }
  }

  const columnas = [
    { clave: "periodo", titulo: "Período", prioridad: 1, ancho: ANCHO_PERIODO, celda: (e) => e.periodo },
    ...(esAdmin
      ? [{
          clave: "depto",
          titulo: "Departamento",
          prioridad: 1,
          ancho: "auto",
          celda: (e) => deptoLabel(e.departamento_id),
        }]
      : []),
    {
      // `ancho: "auto"` quedó sin el cálculo que sí recibió toda otra
      // columna de fecha/monto de esta rama (ver ANCHO_FECHA_MONTO en
      // anchosColumnas.js) — a 1024px de viewport (746px de contenedor,
      // prioridad 3 caída, chevron presente) el fijo daba 451px y las dos
      // columnas en auto se repartían 311px → 156px cada una, 132px
      // utilizables contra los ≈180px que pide el contenido real
      // ("DD/MM/YYYY · $ NNN.NNN"), truncando de punta a punta entre
      // ~760px y ~1120px de contenedor.
      //
      // `venc2` también es `prioridad: 3` (antes 2) — no un descuido: con
      // `venc2` en prioridad 2 (visible desde 720px de contenedor) y
      // `ANCHO_FECHA_MONTO` fijo en las dos, la franja 720–999px sumaba
      // chevron 44 + periodo 92.95 + venc2 293.15 + estado 85.8 +
      // pendiente 164.45 + acciones 64 = 744.35px de columnas fijas — más
      // que el contenedor a 720px, desbordando la página de costado (el
      // mismo bug que CRITICAL 1 restauró para las tablas legacy, ahora en
      // una tabla migrada) y dejando a `depto` (prioridad 1, la columna
      // que identifica la fila) con menos de 2px donde antes tenía
      // ~147-198px. Las dos columnas solo aparecen juntas desde 1000px de
      // contenedor para arriba — ver el comentario de `venc2`.
      clave: "venc1",
      titulo: "1° venc",
      prioridad: 3,
      ancho: ANCHO_FECHA_MONTO,
      celda: (e) => `${formatFecha(e.fecha_primer_vencimiento)} · ${formatearMonto(e.monto_primer_vencimiento)}`,
    },
    {
      // `prioridad: 3`, NO 2: ver el comentario largo en `venc1` de arriba.
      // Con las dos columnas en el mismo escalón (≥1000px de contenedor) la
      // franja intermedia (720–999px) vuelve a sumar solo periodo+estado+
      // pendiente+acciones+chevron ≈451px fijos, y `depto` recupera su
      // ancho.
      clave: "venc2",
      titulo: "2° venc",
      prioridad: 3,
      ancho: ANCHO_FECHA_MONTO,
      celda: (e) => `${formatFecha(e.fecha_segundo_vencimiento)} · ${formatearMonto(e.monto_segundo_vencimiento)}`,
    },
    {
      clave: "estado",
      titulo: "Estado",
      prioridad: 1,
      ancho: "12ch",
      celda: (e) => <BadgeEstado estado={e.estado_calculado} />,
    },
    {
      clave: "pendiente",
      titulo: "Pendiente",
      className: "col-monto",
      prioridad: 1,
      ancho: ANCHO_MONTO,
      celda: (e) =>
        e.monto_pendiente >= 0.5 ? (
          <>
            <strong>{formatearMonto(e.monto_pendiente)}</strong>
            {e.interes_acumulado > 0 && (
              <>
                <br />
                <span className="meta">
                  +{formatearInteres(e.interes_acumulado)} int.
                </span>
              </>
            )}
          </>
        ) : (
          "—"
        ),
    },
    {
      clave: "acciones",
      titulo: "",
      className: "col-acciones",
      prioridad: 1,
      ancho: "4rem",
      celda: (e) => {
        const acciones = [
          { label: "Comprobantes", onSelect: () => setModalComprobantes(e) },
          { label: "PDF", onSelect: () => handleAbrirPdf(e) },
          ...(esAdmin
            ? [{ label: "Eliminar", onSelect: () => setModalEliminar(e), peligro: true }]
            : []),
        ];
        return (
          <MenuAcciones
            acciones={acciones}
            etiqueta={
              esAdmin
                ? `Acciones de la expensa de ${e.periodo} — ${deptoLabel(e.departamento_id)}`
                : `Acciones de la expensa de ${e.periodo}`
            }
          />
        );
      },
    },
  ];

  return (
    <section className="pantalla pantalla-ancha">
      {!embebida && (
        <header className="seccion-header">
          <h2>Expensas</h2>
        </header>
      )}

      {esAdmin && (
        <div className="filtros-barra">
          <SelectorDepartamento
            valor={departamentoSeleccionado}
            onChange={setDepartamentoSeleccionado}
          />
          <label>
            Estado
            <select
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value)}
            >
              {ESTADOS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <label>
            Período
            <input
              type="month"
              value={filtroPeriodo}
              onChange={(e) => setFiltroPeriodo(e.target.value)}
            />
          </label>
          {(filtroPeriodo || filtroEstado) && (
            <button
              type="button"
              onClick={() => {
                setFiltroPeriodo("");
                setFiltroEstado("");
              }}
            >
              Limpiar
            </button>
          )}
          {departamentoSeleccionado !== null && (
            <button type="button" onClick={() => setModalCrearAbierto(true)}>
              + Nueva expensa
            </button>
          )}
        </div>
      )}

      {cargando && <p>Cargando…</p>}
      {errorCarga && (
        <p role="alert" className="error-banner">
          {errorCarga}
        </p>
      )}
      {errorAccion && (
        <p role="alert" className="error-banner">
          {errorAccion}
        </p>
      )}

      {filtroPeriodo && (
        <div
          style={{
            background: periodosCerradosSet.has(filtroPeriodo) ? "var(--color-primary-soft)" : "var(--color-warning-bg)",
            border: `1px solid ${periodosCerradosSet.has(filtroPeriodo) ? "var(--color-primary)" : "var(--color-warning)"}`,
            padding: "0.8em 1em",
            marginBottom: "1em",
            borderRadius: "4px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>
            📅 Período <strong>{filtroPeriodo}</strong>
            {periodosCerradosSet.has(filtroPeriodo) ? " (cerrado)" : " (sin cerrar)"}
            {" · "}<strong>{expensasDelPeriodo.length}</strong> expensas
          </span>
          <button
            type="button"
            onClick={() => setModalEnvio({
              periodo: filtroPeriodo,
              cantidadExpensas: expensasDelPeriodo.length,
              periodoCerrado: periodosCerradosSet.has(filtroPeriodo),
            })}
          >
            ✉ Enviar PDFs por email
          </button>
        </div>
      )}

      {!cargando && (
        <TablaResponsive
          columnas={columnas}
          filas={expensasFiltradas}
          claveFila={(e) => e.id}
          vacio="No hay expensas para mostrar."
          renderTarjeta={(e) => (
            <TarjetaExpensa
              expensa={e}
              esAdmin={esAdmin}
              depto={deptoById[e.departamento_id]}
              token={token}
              onEliminar={setModalEliminar}
              onVerComprobantes={setModalComprobantes}
            />
          )}
        />
      )}

      {esAdmin && departamentoSeleccionado !== null && (
        <p>
          <Link to={`/departamentos/${departamentoSeleccionado}/cuenta`}>
            Ver cuenta corriente del depto &rarr;
          </Link>
        </p>
      )}

      {modalCrearAbierto && (
        <Modal titulo="Nueva expensa" onClose={() => setModalCrearAbierto(false)}>
          <FormularioNuevaExpensa
            departamentoId={departamentoSeleccionado}
            onCreada={handleExpensaCreada}
            onCancelar={() => setModalCrearAbierto(false)}
          />
        </Modal>
      )}

      {modalEliminar && (
        <Modal titulo="Eliminar expensa" onClose={() => setModalEliminar(null)}>
          <p>
            ¿Eliminar la expensa de <strong>{modalEliminar.periodo}</strong>?
          </p>
          <p className="meta">
            Solo se puede eliminar si no tiene pagos aplicados.
          </p>
          <div className="modal-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={() => setModalEliminar(null)}
              disabled={eliminando}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="boton-peligro"
              onClick={handleEliminar}
              disabled={eliminando}
            >
              {eliminando ? "Eliminando…" : "Eliminar"}
            </button>
          </div>
        </Modal>
      )}

      {modalComprobantes && (
        <ModalComprobantesExpensa
          expensa={modalComprobantes}
          onClose={() => setModalComprobantes(null)}
        />
      )}

      {modalEnvio && (
        <ModalEnvioPdfs
          periodo={modalEnvio.periodo}
          periodoCerrado={modalEnvio.periodoCerrado}
          cantidadExpensas={modalEnvio.cantidadExpensas}
          onClose={() => setModalEnvio(null)}
        />
      )}
    </section>
  );
}

function FormularioNuevaExpensa({ departamentoId, onCreada, onCancelar }) {
  const [periodo, setPeriodo] = useState("");
  const [monto, setMonto] = useState("");
  const [fechaVencimiento, setFechaVencimiento] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    const r = await crearExpensa({
      departamento_id: departamentoId,
      periodo,
      monto: Number(monto),
      fecha_vencimiento: fechaVencimiento,
    });
    setEnviando(false);

    if (r.status === 201) {
      onCreada(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 404) {
      setError("El departamento indicado no existe.");
      return;
    }
    if (r.status === 409) {
      setError(
        r.data?.detail ||
          "Ya existe una expensa para ese departamento en ese período.",
      );
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <label>
        Período (YYYY-MM)
        <input
          type="text"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
          pattern="\d{4}-(0[1-9]|1[0-2])"
          placeholder="2026-06"
          required
          autoFocus
        />
      </label>
      <label>
        Monto
        <input
          type="number"
          value={monto}
          onChange={(e) => setMonto(e.target.value)}
          min="1"
          step="0.01"
          required
        />
      </label>
      <label>
        Fecha de vencimiento
        <input
          type="date"
          value={fechaVencimiento}
          onChange={(e) => setFechaVencimiento(e.target.value)}
          required
        />
      </label>

      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}

      <div className="modal-acciones">
        <button
          type="button"
          className="boton-secundario"
          onClick={onCancelar}
          disabled={enviando}
        >
          Cancelar
        </button>
        <button type="submit" disabled={enviando}>
          {enviando ? "Creando…" : "Crear expensa"}
        </button>
      </div>
    </form>
  );
}
