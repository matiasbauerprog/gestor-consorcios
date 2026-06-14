import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarExpensas, crearExpensa, presentarComprobante } from "../api/expensas";
import Modal from "../components/Modal";
import SelectorDepartamento from "../components/SelectorDepartamento";
import BadgeEstado from "../components/BadgeEstado";
import Tarjeta from "../components/Tarjeta";

function estaVencida(expensa, hoy = new Date()) {
  if (expensa.estado !== "pendiente") return false;
  const venc = new Date(expensa.fecha_vencimiento + "T00:00:00");
  return venc < new Date(hoy.toISOString().slice(0, 10) + "T00:00:00");
}

function leyendaDeExpensa(expensa) {
  if (expensa.estado === "pagada") return null;
  const uc = expensa.ultimo_comprobante;
  if (!uc) return "Aún no presentó comprobante";
  if (uc.estado === "pendiente_verificacion") return "Comprobante pendiente de verificación";
  if (uc.estado === "rechazado") return "Último comprobante rechazado";
  return null;
}

function formatearMonto(v) {
  return v.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

function TarjetaExpensa({ expensa, rol, onPresentar, onConfirmar, onVer }) {
  const vencida = estaVencida(expensa);
  const leyenda = leyendaDeExpensa(expensa);
  const uc = expensa.ultimo_comprobante;
  const esAdmin = rol === "administracion";
  const esDepto = rol === "departamento";

  let boton = null;
  if (expensa.estado === "pagada") {
    boton = <button type="button" onClick={onVer}>Ver comprobante</button>;
  } else if (!uc && esDepto) {
    boton = <button type="button" onClick={onPresentar}>Presentar comprobante</button>;
  } else if (uc?.estado === "rechazado" && esDepto) {
    boton = <button type="button" onClick={onPresentar}>Presentar otro comprobante</button>;
  } else if (uc?.estado === "pendiente_verificacion" && esAdmin) {
    boton = <button type="button" onClick={onConfirmar}>Confirmar</button>;
  }

  return (
    <Tarjeta>
      <h3>{expensa.periodo} — {formatearMonto(expensa.monto)}</h3>
      <p className="meta">Vence {expensa.fecha_vencimiento}</p>
      <p>
        <BadgeEstado estado={expensa.estado} vencida={vencida} />
      </p>
      {leyenda && <p className="leyenda">ⓘ {leyenda}</p>}
      {boton && <div className="tarjeta-acciones">{boton}</div>}
    </Tarjeta>
  );
}

export default function Expensas() {
  const { user } = useAuth();
  const [expensas, setExpensas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);
  const [departamentoSeleccionado, setDepartamentoSeleccionado] = useState(null);
  const [modalCrearAbierto, setModalCrearAbierto] = useState(false);
  const [errorAccion, setErrorAccion] = useState(null);

  const esAdmin = user.rol === "administracion";

  function handleExpensaCreada(nueva) {
    setExpensas((prev) => [nueva, ...prev]);
    setModalCrearAbierto(false);
    setErrorAccion(null);
  }

  const [modalPresentar, setModalPresentar] = useState(null);

  function handleComprobantePresentado(nuevoComprobante, expensaId) {
    setExpensas((prev) =>
      prev.map((e) =>
        e.id === expensaId ? { ...e, ultimo_comprobante: nuevoComprobante } : e
      )
    );
    setModalPresentar(null);
    setErrorAccion(null);
  }

  useEffect(() => {
    if (esAdmin && departamentoSeleccionado === null) {
      setExpensas([]);
      return;
    }

    let cancelado = false;
    setCargando(true);

    async function cargar() {
      const params = esAdmin ? { departamento_id: departamentoSeleccionado } : {};
      const r = await listarExpensas(params);
      if (cancelado) return;
      if (r.status === 200) {
        setExpensas(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        setErrorCarga("No se pudieron cargar las expensas.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, [esAdmin, departamentoSeleccionado]);

  return (
    <section>
      <header className="seccion-header">
        <h2>Expensas</h2>
        {esAdmin && (
          <div className="seccion-acciones">
            <SelectorDepartamento
              valor={departamentoSeleccionado}
              onChange={setDepartamentoSeleccionado}
              permitirVacio={false}
            />
            <button
              type="button"
              disabled={departamentoSeleccionado === null}
              onClick={() => setModalCrearAbierto(true)}
            >
              + Nueva expensa
            </button>
          </div>
        )}
      </header>

      {esAdmin && departamentoSeleccionado === null && (
        <p>Elegí un departamento para ver sus expensas.</p>
      )}

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {errorAccion && <p role="alert" className="error-banner">{errorAccion}</p>}
      {!cargando && !errorCarga && expensas.length === 0 &&
        (!esAdmin || departamentoSeleccionado !== null) && (
          <p>No hay expensas para mostrar.</p>
        )}

      <ul className="lista-expensas">
        {expensas.map((e) => (
          <li key={e.id}>
            <TarjetaExpensa
              expensa={e}
              rol={user.rol}
              onPresentar={() => setModalPresentar(e)}
              onConfirmar={() => {}}
              onVer={() => {}}
            />
          </li>
        ))}
      </ul>

      <p>
        <Link to="/comprobantes">Ver todos los comprobantes →</Link>
      </p>

      {modalCrearAbierto && (
        <Modal titulo="Nueva expensa" onClose={() => setModalCrearAbierto(false)}>
          <FormularioNuevaExpensa
            departamentoId={departamentoSeleccionado}
            onCreada={handleExpensaCreada}
            onCancelar={() => setModalCrearAbierto(false)}
          />
        </Modal>
      )}

      {modalPresentar && (
        <Modal titulo="Presentar comprobante" onClose={() => setModalPresentar(null)}>
          <FormularioPresentarComprobante
            expensa={modalPresentar}
            onPresentado={(c) => handleComprobantePresentado(c, modalPresentar.id)}
            onCancelar={() => setModalPresentar(null)}
          />
        </Modal>
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
      setError(r.data?.detail || "Ya existe una expensa para ese departamento en ese período.");
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

      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="modal-acciones">
        <button type="button" className="boton-secundario" onClick={onCancelar} disabled={enviando}>
          Cancelar
        </button>
        <button type="submit" disabled={enviando}>
          {enviando ? "Creando…" : "Crear expensa"}
        </button>
      </div>
    </form>
  );
}

function FormularioPresentarComprobante({ expensa, onPresentado, onCancelar }) {
  const [fechaPago, setFechaPago] = useState("");
  const [monto, setMonto] = useState(String(expensa.monto));
  const [archivoUrl, setArchivoUrl] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);

    const r = await presentarComprobante(expensa.id, {
      fecha_pago: fechaPago,
      monto: Number(monto),
      archivo_url: archivoUrl.trim() || null,
    });
    setEnviando(false);

    if (r.status === 201) {
      onPresentado(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 403) {
      setError("No tenés permisos para presentar este comprobante.");
      return;
    }
    if (r.status === 404) {
      setError("La expensa solicitada no existe.");
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <p className="meta">
        Expensa: {expensa.periodo} — ${expensa.monto.toLocaleString("es-AR")}
      </p>
      <label>
        Fecha de pago
        <input
          type="date"
          value={fechaPago}
          onChange={(e) => setFechaPago(e.target.value)}
          required
          autoFocus
        />
      </label>
      <label>
        Monto pagado
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
        Link al comprobante (opcional)
        <input
          type="url"
          value={archivoUrl}
          onChange={(e) => setArchivoUrl(e.target.value)}
          placeholder="https://drive.google.com/..."
          maxLength={2048}
        />
      </label>

      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="modal-acciones">
        <button type="button" className="boton-secundario" onClick={onCancelar} disabled={enviando}>
          Cancelar
        </button>
        <button type="submit" disabled={enviando}>
          {enviando ? "Enviando…" : "Presentar"}
        </button>
      </div>
    </form>
  );
}
