import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  listarComunicados,
  crearComunicado,
  borrarComunicado,
} from "../api/comunicados";
import Modal from "../components/Modal";
import Tarjeta from "../components/Tarjeta";

function formatearFecha(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function cuerpoLargo(cuerpo) {
  if (cuerpo.length > 280) return true;
  if (cuerpo.split("\n").length > 3) return true;
  return false;
}

export default function Comunicados() {
  const { user } = useAuth();
  const [comunicados, setComunicados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [expandidos, setExpandidos] = useState(() => new Set());
  const [modalCrearAbierto, setModalCrearAbierto] = useState(false);
  const [modalBorrar, setModalBorrar] = useState(null);
  const [idBorrando, setIdBorrando] = useState(null);
  const [errorBorrado, setErrorBorrado] = useState(null);

  function handleCreado(nuevo) {
    setComunicados((prev) => [nuevo, ...prev]);
    setModalCrearAbierto(false);
  }

  async function handleConfirmarBorrado() {
    if (!modalBorrar) return;
    const id = modalBorrar.id;
    setIdBorrando(id);

    const r = await borrarComunicado(id);

    setIdBorrando(null);
    setModalBorrar(null);

    if (r.status === 204) {
      setComunicados((prev) => prev.filter((c) => c.id !== id));
      setErrorBorrado(null);
      return;
    }
    if (r.status === 404) {
      setComunicados((prev) => prev.filter((c) => c.id !== id));
      setErrorBorrado("El comunicado ya no existe.");
      return;
    }
    if (r.status === 403) {
      setErrorBorrado("No tenés permisos para borrar comunicados.");
      return;
    }
    if (r.status !== 401) {
      setErrorBorrado("No se pudo borrar el comunicado. Intentá de nuevo.");
    }
  }

  function toggleExpandir(id) {
    setExpandidos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  useEffect(() => {
    let cancelado = false;

    async function cargar() {
      const r = await listarComunicados();
      if (cancelado) return;

      if (r.status === 200) {
        setComunicados(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        // 401 lo maneja apiFetch (logout automático). El resto es error genérico.
        setErrorCarga("No se pudieron cargar los comunicados.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <section>
      <header className="seccion-header">
        <h2>Comunicados</h2>
        {user.rol === "administracion" && (
          <button type="button" onClick={() => setModalCrearAbierto(true)}>
            + Nuevo comunicado
          </button>
        )}
      </header>

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {errorBorrado && (
        <p role="alert" className="error-banner">
          {errorBorrado}
        </p>
      )}
      {!cargando && !errorCarga && comunicados.length === 0 && (
        <p>No hay comunicados publicados.</p>
      )}

      <ul className="lista-comunicados">
        {comunicados.map((c) => (
          <li key={c.id}>
            <Tarjeta>
              <h3>{c.titulo}</h3>
              <p className="meta">
                {formatearFecha(c.fecha_publicacion)} · Administración
              </p>
              <p className={expandidos.has(c.id) ? "" : "cuerpo-truncado"}>
                {c.cuerpo}
              </p>
              {(cuerpoLargo(c.cuerpo) || user.rol === "administracion") && (
                <div className="tarjeta-acciones">
                  {cuerpoLargo(c.cuerpo) && (
                    <button
                      type="button"
                      className="boton-link"
                      onClick={() => toggleExpandir(c.id)}
                    >
                      {expandidos.has(c.id) ? "Ver menos" : "Ver más"}
                    </button>
                  )}
                  {user.rol === "administracion" && (
                    <button
                      type="button"
                      className="boton-borrar"
                      disabled={idBorrando === c.id}
                      onClick={() =>
                        setModalBorrar({ id: c.id, titulo: c.titulo })
                      }
                    >
                      Borrar
                    </button>
                  )}
                </div>
              )}
            </Tarjeta>
          </li>
        ))}
      </ul>

      {modalCrearAbierto && (
        <Modal
          titulo="Nuevo comunicado"
          onClose={() => setModalCrearAbierto(false)}
        >
          <FormularioNuevoComunicado
            onCreado={handleCreado}
            onCancelar={() => setModalCrearAbierto(false)}
          />
        </Modal>
      )}

      {modalBorrar && (
        <Modal
          titulo="Borrar comunicado"
          onClose={() => setModalBorrar(null)}
        >
          <p>
            ¿Borrar el comunicado «<strong>{modalBorrar.titulo}</strong>»? Esta
            acción no se puede deshacer.
          </p>
          <div className="modal-acciones">
            <button
              type="button"
              className="boton-secundario"
              onClick={() => setModalBorrar(null)}
              disabled={idBorrando === modalBorrar.id}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="boton-peligro"
              onClick={handleConfirmarBorrado}
              disabled={idBorrando === modalBorrar.id}
            >
              {idBorrando === modalBorrar.id ? "Borrando…" : "Borrar"}
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}

function FormularioNuevoComunicado({ onCreado, onCancelar }) {
  const [titulo, setTitulo] = useState("");
  const [cuerpo, setCuerpo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setEnviando(true);

    const r = await crearComunicado({ titulo, cuerpo });
    setEnviando(false);

    if (r.status === 201) {
      onCreado(r.data);
      return;
    }
    if (r.status === 400) {
      setError(r.data?.detail || "Revisá los campos del formulario.");
      return;
    }
    if (r.status === 403) {
      setError("No tenés permisos para publicar comunicados.");
      return;
    }
    if (r.status !== 401) {
      setError("Ocurrió un error inesperado. Intentá de nuevo.");
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <label>
        Título
        <input
          type="text"
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          maxLength={255}
          required
          autoFocus
        />
      </label>

      <label>
        Cuerpo
        <textarea
          value={cuerpo}
          onChange={(e) => setCuerpo(e.target.value)}
          maxLength={5000}
          required
        />
      </label>

      {error && <p role="alert" className="error-banner">{error}</p>}

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
          {enviando ? "Publicando…" : "Publicar"}
        </button>
      </div>
    </form>
  );
}
