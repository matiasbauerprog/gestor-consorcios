import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarExpensas, crearExpensa, eliminarExpensa } from "../api/expensas";
import { listarDepartamentos } from "../api/departamentos";
import Modal from "../components/Modal";
import SelectorDepartamento from "../components/SelectorDepartamento";
import BadgeEstado from "../components/BadgeEstado";
import Tarjeta from "../components/Tarjeta";

function formatearMonto(v) {
  return Number(v).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

function TarjetaExpensa({ expensa, esAdmin, depto, onEliminar }) {
  return (
    <Tarjeta>
      <h3>
        {expensa.periodo} — {formatearMonto(expensa.monto)}
      </h3>
      {esAdmin && (
        <p className="meta">
          {depto ? `${depto.codigo} — ${depto.descripcion}` : `Depto #${expensa.departamento_id}`}
        </p>
      )}
      <p className="meta">Vence {expensa.fecha_vencimiento}</p>
      <p>
        <BadgeEstado estado={expensa.estado_calculado} />
        {expensa.monto_pendiente > 0 && (
          <span className="meta" style={{ marginLeft: "0.5rem" }}>
            Pendiente {formatearMonto(expensa.monto_pendiente)}
          </span>
        )}
      </p>
      {esAdmin && (
        <div className="tarjeta-acciones">
          <button
            type="button"
            className="boton-peligro"
            onClick={() => onEliminar(expensa)}
          >
            Eliminar
          </button>
        </div>
      )}
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
  const [modalEliminar, setModalEliminar] = useState(null);
  const [errorAccion, setErrorAccion] = useState(null);
  const [eliminando, setEliminando] = useState(false);
  const [departamentos, setDepartamentos] = useState([]);

  const esAdmin = user.rol === "administracion";
  const esDepto = user.rol === "departamento";

  useEffect(() => {
    if (!esAdmin) return;
    (async () => {
      const r = await listarDepartamentos();
      if (r.status === 200) {
        setDepartamentos(r.data);
      }
    })();
  }, [esAdmin]);

  const deptoById = Object.fromEntries(departamentos.map((d) => [d.id, d]));

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

  return (
    <main className="pantalla">
      <header className="seccion-header">
        <h2>Expensas</h2>
        {esAdmin && (
          <div className="seccion-acciones">
            <SelectorDepartamento
              valor={departamentoSeleccionado}
              onChange={setDepartamentoSeleccionado}
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

      {esDepto && (
        <p className="meta">
          Para presentar un pago, andá a <Link to="/mi-cuenta">Mi cuenta</Link>.
        </p>
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
      {!cargando && !errorCarga && expensas.length === 0 && (
        <p>No hay expensas para mostrar.</p>
      )}

      <ul className="lista-expensas">
        {expensas.map((e) => (
          <li key={e.id}>
            <TarjetaExpensa
              expensa={e}
              esAdmin={esAdmin}
              depto={deptoById[e.departamento_id]}
              onEliminar={setModalEliminar}
            />
          </li>
        ))}
      </ul>

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
    </main>
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
