import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { buscarErrorPorCodigo, listarErrores } from "../api/superAdmin";
import { useAuth } from "../auth/AuthContext";
import { formatFechaHora } from "../utils/fechas";

const PAGE_SIZE = 50;

/**
 * Errores inesperados del sistema.
 *
 * El caso de uso que la justifica: alguien llama diciendo que algo no le anda y
 * dicta el código que le apareció en pantalla. Se pega acá y aparece qué pasó,
 * a quién y en qué consorcio.
 */
export default function SuperAdminErrores() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [codigo, setCodigo] = useState("");
  const [encontrado, setEncontrado] = useState(null);
  const [errorBusqueda, setErrorBusqueda] = useState(null);
  const [detalleAbierto, setDetalleAbierto] = useState(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    const r = await listarErrores({ limit: PAGE_SIZE, offset });
    if (r.status === 200) setItems(r.data);
    setLoading(false);
  }, [offset]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function handleBuscar(e) {
    e.preventDefault();
    setErrorBusqueda(null);
    setEncontrado(null);
    if (!codigo.trim()) return;

    const r = await buscarErrorPorCodigo(codigo);
    if (r.status === 200) {
      setEncontrado(r.data);
      return;
    }
    setErrorBusqueda(
      r.status === 404
        ? `No hay ningún error con el código ${codigo.trim().toUpperCase()}.`
        : r.data?.detail || "No se pudo buscar.",
    );
  }

  if (!user) return null;
  if (user.rol !== "super_admin") return <Navigate to="/" replace />;

  return (
    <section>
      <h2>Errores del sistema</h2>
      <p className="meta">
        Sólo los errores inesperados. Los avisos normales del sistema —no
        encontrado, sin permiso, datos inválidos— no entran acá. Se conservan 90
        días.
      </p>

      <form onSubmit={handleBuscar}>
        <label>
          Buscar por código
          <input
            type="text"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            placeholder="E-7K3MQ9"
            autoComplete="off"
          />
        </label>
        <button type="submit">Buscar</button>
      </form>

      {errorBusqueda && <p role="alert">{errorBusqueda}</p>}
      {encontrado && <DetalleError error={encontrado} />}

      <h3>Últimos errores</h3>
      {loading ? (
        <p>Cargando...</p>
      ) : items.length === 0 ? (
        <p>Ningún error registrado. Buena señal.</p>
      ) : (
        <>
          <table className="tabla-listado">
            <thead>
              <tr>
                <th>Código</th>
                <th>Cuándo</th>
                <th>Dónde</th>
                <th>Qué</th>
                <th>Quién</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id}>
                  <td>
                    <code>{e.codigo}</code>
                  </td>
                  <td>{formatFechaHora(e.ocurrido_at)}</td>
                  <td>
                    {e.metodo} {e.ruta}
                  </td>
                  <td>{e.tipo}</td>
                  <td>
                    {e.rol ?? "sin sesión"}
                    {e.consorcio_id ? ` · consorcio ${e.consorcio_id}` : ""}
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() =>
                        setDetalleAbierto(detalleAbierto === e.id ? null : e.id)
                      }
                    >
                      {detalleAbierto === e.id ? "Ocultar" : "Ver detalle"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {detalleAbierto && (
            <DetalleError error={items.find((e) => e.id === detalleAbierto)} />
          )}

          <div className="acciones-modal">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Anteriores
            </button>
            <button
              type="button"
              disabled={items.length < PAGE_SIZE}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Siguientes
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function DetalleError({ error }) {
  if (!error) return null;
  return (
    <article className="tarjeta">
      <h3>
        <code>{error.codigo}</code> · {error.tipo}
      </h3>
      <p className="meta">
        {formatFechaHora(error.ocurrido_at)} · {error.metodo} {error.ruta}
      </p>
      <p className="meta">
        Usuario {error.usuario_id ?? "—"} ({error.rol ?? "sin sesión"}) ·
        Consorcio {error.consorcio_id ?? "—"}
      </p>
      <p>{error.mensaje}</p>
      <pre className="traza-error">{error.traza}</pre>
    </article>
  );
}
