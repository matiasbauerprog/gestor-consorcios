import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  listarComprobantes,
  actualizarComprobante,
  eliminarComprobante,
} from "../api/comprobantes";
import { listarCajas } from "../api/cajas";
import { obtenerConfiguracion } from "../api/configuracion";
import { API_BASE } from "../api/client";
import BadgeEstado from "../components/BadgeEstado";
import TablaResponsive from "../components/TablaResponsive";
import MenuAcciones from "../components/MenuAcciones";
import Modal from "../components/Modal";
import SelectorDepartamento from "../components/SelectorDepartamento";
import Tarjeta from "../components/Tarjeta";
import { formatFecha } from "../utils/fechas";
import { formatearMonto } from "../utils/montos";

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "pendiente_verificacion", label: "Pendientes" },
  { value: "aprobado", label: "Aprobados" },
  { value: "rechazado", label: "Rechazados" },
];

export default function Comprobantes({ embebida = false }) {
  const { user } = useAuth();
  const esAdmin = user.rol === "administracion";
  const [searchParams] = useSearchParams();
  const deptoInicial = searchParams.get("departamento_id");

  const [comprobantes, setComprobantes] = useState([]);
  const [cajas, setCajas] = useState([]);
  const [cajaDefault, setCajaDefault] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [cargandoCajas, setCargandoCajas] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroDepto, setFiltroDepto] = useState(
    deptoInicial ? Number(deptoInicial) : null,
  );
  const [accionandoId, setAccionandoId] = useState(null);
  const [errorAccion, setErrorAccion] = useState(null);
  const [modalEliminar, setModalEliminar] = useState(null);
  const [eliminando, setEliminando] = useState(false);
  const [modalAprobar, setModalAprobar] = useState(null); // { comprobante, cajaSeleccionada }
  const [aprobando, setAprobando] = useState(false);

  async function handleDecision(id, estadoNuevo, cajaDestinoId = null) {
    setAccionandoId(id);
    const body = { estado: estadoNuevo };
    if (cajaDestinoId !== null) {
      body.caja_destino_id = cajaDestinoId;
    }
    const r = await actualizarComprobante(id, body);
    setAccionandoId(null);

    if (r.status === 200) {
      setComprobantes((prev) => prev.map((c) => (c.id === id ? r.data : c)));
      setErrorAccion(null);
      return;
    }
    if (r.status === 404) {
      setComprobantes((prev) => prev.filter((c) => c.id !== id));
      setErrorAccion("El comprobante no existe.");
      return;
    }
    if (r.status === 409) {
      setErrorAccion("El comprobante ya fue verificado.");
      return;
    }
    if (r.status === 403) {
      setErrorAccion("No tenés permisos para esta operación.");
      return;
    }
    if (r.status !== 401) {
      setErrorAccion("Ocurrió un error. Intentá de nuevo.");
    }
  }

  async function handleAprobarClick(comprobante) {
    // Abrir modal para seleccionar caja destino
    setModalAprobar({
      comprobante,
      cajaSeleccionada: cajaDefault,
    });
  }

  async function handleConfirmarAprobacion() {
    if (!modalAprobar) return;
    setAprobando(true);
    const cajaId = modalAprobar.cajaSeleccionada || cajaDefault;
    if (!cajaId) {
      setErrorAccion("Debes seleccionar una caja.");
      setAprobando(false);
      return;
    }
    setModalAprobar(null);
    await handleDecision(modalAprobar.comprobante.id, "aprobado", cajaId);
    setAprobando(false);
  }

  async function handleEliminar() {
    if (!modalEliminar) return;
    setEliminando(true);
    setErrorAccion(null);
    const r = await eliminarComprobante(modalEliminar.id);
    setEliminando(false);
    if (r.status === 204) {
      setComprobantes((prev) => prev.filter((c) => c.id !== modalEliminar.id));
      setModalEliminar(null);
      return;
    }
    if (r.status === 403) {
      setErrorAccion("No tenés permisos para eliminar este comprobante.");
      setModalEliminar(null);
      return;
    }
    if (r.status === 404) {
      setComprobantes((prev) => prev.filter((c) => c.id !== modalEliminar.id));
      setModalEliminar(null);
      return;
    }
    if (r.status !== 401) {
      setErrorAccion("No se pudo eliminar el comprobante.");
      setModalEliminar(null);
    }
  }

  useEffect(() => {
    let cancelado = false;

    // Cargar cajas y configuración al montar
    async function cargarCajasyConfig() {
      setCargandoCajas(true);
      const rCajas = await listarCajas();
      const rConfig = await obtenerConfiguracion();
      if (!cancelado) {
        if (rCajas.status === 200) {
          setCajas(rCajas.data);
        }
        if (rConfig.status === 200 && rConfig.data.caja_default_pagos_id) {
          setCajaDefault(rConfig.data.caja_default_pagos_id);
        }
        setCargandoCajas(false);
      }
    }
    cargarCajasyConfig();
    return () => {
      cancelado = true;
    };
  }, []);

  useEffect(() => {
    let cancelado = false;
    setCargando(true);

    async function cargar() {
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      if (esAdmin && filtroDepto != null) params.departamento_id = filtroDepto;

      const r = await listarComprobantes(params);
      if (cancelado) return;

      if (r.status === 200) {
        setComprobantes(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        setErrorCarga("No se pudieron cargar los comprobantes.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, [filtroEstado, filtroDepto, esAdmin]);

  function deptoLabel(c) {
    return c.departamento_codigo || (c.departamento_id ? `#${c.departamento_id}` : null);
  }

  const columnas = [
    { clave: "fecha", titulo: "Fecha", prioridad: 3, ancho: "12ch", celda: (c) => formatFecha(c.fecha_pago) },
    ...(esAdmin
      ? [{
          clave: "depto",
          titulo: "Departamento",
          prioridad: 1,
          ancho: "auto",
          celda: (c) => deptoLabel(c) || "—",
        }]
      : []),
    {
      clave: "monto",
      titulo: "Monto",
      className: "col-monto",
      prioridad: 1,
      ancho: "14ch",
      celda: (c) => formatearMonto(c.monto),
    },
    {
      clave: "estado",
      titulo: "Estado",
      prioridad: 1,
      ancho: "12ch",
      celda: (c) => <BadgeEstado estado={c.estado} />,
    },
    {
      clave: "archivo",
      titulo: "Comprobante",
      prioridad: 2,
      ancho: "8rem",
      celda: (c) =>
        c.archivo_path ? (
          <a href={`${API_BASE}${c.archivo_path}`} target="_blank" rel="noopener noreferrer">
            <img
              src={`${API_BASE}${c.archivo_path}`}
              alt={`Comprobante del ${formatFecha(c.fecha_pago)}`}
              className="comprobante-thumb"
            />
          </a>
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
      celda: (c) => {
        const acciones = [
          ...(esAdmin && c.estado === "pendiente_verificacion"
            ? [
                {
                  label: "Aprobar",
                  onSelect: () => handleAprobarClick(c),
                  disabled: accionandoId === c.id || cargandoCajas,
                },
                {
                  label: "Rechazar",
                  onSelect: () => handleDecision(c.id, "rechazado"),
                  disabled: accionandoId === c.id,
                  peligro: true,
                },
              ]
            : []),
          { label: "Eliminar", onSelect: () => setModalEliminar(c), peligro: true },
        ];
        const depto = deptoLabel(c);
        const etiqueta = `Acciones del comprobante del ${formatFecha(c.fecha_pago)}${
          depto ? ` — ${depto}` : ""
        } — ${formatearMonto(c.monto)}`;
        return (
          <MenuAcciones
            acciones={acciones}
            etiqueta={etiqueta}
          />
        );
      },
    },
  ];

  return (
    <section className="pantalla-ancha">
      {!embebida && (
        <header className="seccion-header">
          <h2>Comprobantes</h2>
        </header>
      )}

      <div className="filtros-barra">
        <label>
          Estado
          <select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
            {ESTADOS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        {esAdmin && (
          <SelectorDepartamento valor={filtroDepto} onChange={setFiltroDepto} permitirVacio />
        )}
      </div>

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {errorAccion && <p role="alert" className="error-banner">{errorAccion}</p>}

      {!cargando && (
      <TablaResponsive
        columnas={columnas}
        filas={comprobantes}
        claveFila={(c) => c.id}
        vacio="No hay comprobantes con esos filtros."
        renderTarjeta={(c) => (
          <Tarjeta>
            <h3>{formatearMonto(c.monto)}</h3>
            <p className="meta">Pagado {formatFecha(c.fecha_pago)}</p>
            {c.departamento_id && (
              <p className="meta">
                Departamento: {c.departamento_codigo || `#${c.departamento_id}`}
              </p>
            )}
            <p><BadgeEstado estado={c.estado} /></p>
            {c.archivo_path && (
              <a href={`${API_BASE}${c.archivo_path}`} target="_blank" rel="noopener noreferrer">
                <img
                  src={`${API_BASE}${c.archivo_path}`}
                  alt="Comprobante"
                  className="comprobante-img"
                />
              </a>
            )}
            <div className="tarjeta-acciones">
              {esAdmin && c.estado === "pendiente_verificacion" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAprobarClick(c)}
                    disabled={accionandoId === c.id || cargandoCajas}
                  >
                    {accionandoId === c.id ? "…" : "Aprobar"}
                  </button>
                  <button
                    type="button"
                    className="boton-borrar"
                    onClick={() => handleDecision(c.id, "rechazado")}
                    disabled={accionandoId === c.id}
                  >
                    {accionandoId === c.id ? "…" : "Rechazar"}
                  </button>
                </>
              )}
              <button type="button" className="boton-peligro" onClick={() => setModalEliminar(c)}>
                Eliminar
              </button>
            </div>
          </Tarjeta>
        )}
      />
      )}

      {modalAprobar && (
        <Modal titulo="Aprobar comprobante" onClose={() => setModalAprobar(null)}>
          <p>
            Comprobante del <strong>{formatFecha(modalAprobar.comprobante.fecha_pago)}</strong> por{" "}
            <strong>{formatearMonto(modalAprobar.comprobante.monto)}</strong>
          </p>
          <label>
            Caja destino
            <select
              value={modalAprobar.cajaSeleccionada || ""}
              onChange={(e) =>
                setModalAprobar({
                  ...modalAprobar,
                  cajaSeleccionada: Number(e.target.value),
                })
              }
              disabled={aprobando}
            >
              <option value="">— Seleccioná una caja —</option>
              {cajas.map((caja) => (
                <option key={caja.id} value={caja.id}>
                  {caja.nombre}
                </option>
              ))}
            </select>
          </label>
          <div className="modal-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={() => setModalAprobar(null)}
              disabled={aprobando}
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirmarAprobacion}
              disabled={aprobando || !modalAprobar.cajaSeleccionada}
            >
              {aprobando ? "Aprobando…" : "Aprobar"}
            </button>
          </div>
        </Modal>
      )}

      {modalEliminar && (
        <Modal titulo="Eliminar comprobante" onClose={() => setModalEliminar(null)}>
          <p>¿Eliminar el comprobante del {formatFecha(modalEliminar.fecha_pago)}?</p>
          <p className="meta">
            Esta acción lo oculta de la vista. Si ya estaba aprobado, el pago
            sigue contabilizado en la cuenta corriente.
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
    </section>
  );
}
