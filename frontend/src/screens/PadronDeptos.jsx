import { useEffect, useMemo, useState } from "react";
import EstadoBadge from "../components/EstadoBadge";
import {
  crearDepartamento,
  eliminarDepartamento,
  listarDepartamentos,
} from "../api/departamentos";
import { importarPadronCSV } from "../api/padron";
import {
  cambiarEstadoUsuario,
  crearUsuario,
  eliminarUsuario,
  listarUsuarios,
} from "../api/usuarios";

const PAGE_SIZE = 20;

const MENSAJES_ERROR = {
  departamento_con_actividad:
    "El departamento tiene actividad vinculada. No se puede eliminar.",
  no_puede_suspenderse_a_si_mismo: "No podés suspender tu propio usuario.",
  no_puede_eliminarse_a_si_mismo: "No podés eliminar tu propio usuario.",
  usuario_con_actividad:
    "El usuario tiene actividad vinculada. Suspendelo en vez de eliminar.",
};

export default function PadronDeptos() {
  const [departamentos, setDepartamentos] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const [busqueda, setBusqueda] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("todos");
  const [pagina, setPagina] = useState(1);

  const [modalDetalle, setModalDetalle] = useState(null); // depto
  const [modalDeptoAlta, setModalDeptoAlta] = useState(false);
  const [modalUsuarioAlta, setModalUsuarioAlta] = useState(null); // { departamento }
  const [modalImportar, setModalImportar] = useState(false);

  async function recargar() {
    setCargando(true);
    const [rD, rU] = await Promise.all([listarDepartamentos(), listarUsuarios()]);
    if (rD.status === 200) setDepartamentos(rD.data);
    if (rU.status === 200) setUsuarios(rU.data);
    if (rD.status !== 200 && rD.status !== 401) setError("No se pudo cargar.");
    setCargando(false);
  }

  useEffect(() => { recargar(); }, []);

  const usuariosPorDepto = useMemo(() => agruparPorDepto(usuarios), [usuarios]);

  const filas = useMemo(() => {
    return departamentos.map((d) => {
      const us = usuariosPorDepto[d.id] || [];
      let estado = "vacante";
      if (us.length > 0) {
        estado = us.some((u) => u.activa) ? "activo" : "suspendido";
      }
      return { depto: d, usuarios: us, estado };
    });
  }, [departamentos, usuariosPorDepto]);

  const filasFiltradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return filas.filter(({ depto, usuarios, estado }) => {
      if (filtroEstado !== "todos" && estado !== filtroEstado) return false;
      if (!q) return true;
      if (depto.codigo.toLowerCase().includes(q)) return true;
      if ((depto.descripcion || "").toLowerCase().includes(q)) return true;
      if (usuarios.some((u) => u.email.toLowerCase().includes(q))) return true;
      return false;
    });
  }, [filas, busqueda, filtroEstado]);

  const totalPaginas = Math.max(1, Math.ceil(filasFiltradas.length / PAGE_SIZE));
  const paginaActual = Math.min(pagina, totalPaginas);
  const filasPagina = filasFiltradas.slice(
    (paginaActual - 1) * PAGE_SIZE,
    paginaActual * PAGE_SIZE
  );

  useEffect(() => setPagina(1), [busqueda, filtroEstado]);

  const totalDeptos = departamentos.length;
  const conUsuarios = filas.filter((f) => f.usuarios.length > 0).length;
  const sinUsuarios = totalDeptos - conUsuarios;

  async function handleSuspenderUsuario(u) {
    const r = await cambiarEstadoUsuario(u.id, !u.activa);
    if (r.status === 200) recargar();
    else setError(MENSAJES_ERROR[r.data?.detail] || r.data?.detail || "Error.");
  }
  async function handleEliminarUsuario(u) {
    if (!confirm(`¿Eliminar al usuario ${u.email}?`)) return;
    const r = await eliminarUsuario(u.id);
    if (r.status === 204) recargar();
    else setError(MENSAJES_ERROR[r.data?.detail] || r.data?.detail || "Error.");
  }
  async function handleEliminarDepto(d) {
    if (!confirm(`¿Eliminar el departamento ${d.codigo}?`)) return;
    const r = await eliminarDepartamento(d.id);
    if (r.status === 204) {
      setModalDetalle(null);
      recargar();
    } else {
      setError(MENSAJES_ERROR[r.data?.detail] || r.data?.detail || "Error.");
    }
  }

  if (cargando) return <section><p>Cargando…</p></section>;

  return (
    <section>
      <header className="padron-cabecera">
        <div>
          <p className="padron-contador">
            {totalDeptos} departamentos · {conUsuarios} con usuarios asignados
          </p>
        </div>
        <div className="cabecera-acciones">
          <button type="button" onClick={() => setModalImportar(true)}>
            Importar CSV
          </button>
          <button type="button" onClick={() => setModalDeptoAlta(true)}>
            + Nuevo departamento
          </button>
        </div>
      </header>

      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="padron-filtros">
        <input
          type="search"
          placeholder="Buscar unidad o usuario…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
        <select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
          <option value="todos">Estado: Todos</option>
          <option value="activo">Activos</option>
          <option value="suspendido">Suspendidos</option>
          <option value="vacante">Vacantes</option>
        </select>
        <span className="spacer" />
        {sinUsuarios > 0 && (
          <span className="padron-atajo">
            {sinUsuarios} unidades sin usuarios ·{" "}
            <a onClick={() => setFiltroEstado("vacante")}>Ver</a>
          </span>
        )}
      </div>

      {filasFiltradas.length === 0 ? (
        <p>No hay resultados con esos filtros.</p>
      ) : (
        <table className="tabla-padron">
          <thead>
            <tr>
              <th className="col-unidad">Unidad</th>
              <th>Ubicación</th>
              <th>Usuarios</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {filasPagina.map(({ depto, usuarios, estado }) => (
              <tr key={depto.id} onClick={() => setModalDetalle(depto)}>
                <td className="col-unidad">{depto.codigo}</td>
                <td>{depto.descripcion || "—"}</td>
                <td>
                  <CeldaUsuarios usuarios={usuarios} />
                </td>
                <td>
                  <EstadoBadge estado={estado} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {filasFiltradas.length > 0 && (
        <div className="padron-paginacion">
          <span>
            Mostrando{" "}
            <strong>
              {(paginaActual - 1) * PAGE_SIZE + 1}–
              {Math.min(paginaActual * PAGE_SIZE, filasFiltradas.length)}
            </strong>{" "}
            de {filasFiltradas.length}
          </span>
          <Paginador
            pagina={paginaActual}
            total={totalPaginas}
            onCambio={setPagina}
          />
        </div>
      )}

      {modalDetalle && (
        <ModalDetalleDepto
          departamento={modalDetalle}
          usuarios={usuariosPorDepto[modalDetalle.id] || []}
          onCerrar={() => setModalDetalle(null)}
          onAgregarUsuario={() => {
            setModalUsuarioAlta({ departamento: modalDetalle });
            setModalDetalle(null);
          }}
          onEliminar={() => handleEliminarDepto(modalDetalle)}
          onSuspenderUsuario={handleSuspenderUsuario}
          onEliminarUsuario={handleEliminarUsuario}
        />
      )}

      {modalDeptoAlta && (
        <ModalDeptoAlta
          onCerrar={() => setModalDeptoAlta(false)}
          onCreado={async () => { setModalDeptoAlta(false); await recargar(); }}
        />
      )}

      {modalUsuarioAlta && (
        <ModalUsuarioAlta
          departamento={modalUsuarioAlta.departamento}
          onCerrar={() => setModalUsuarioAlta(null)}
          onCreado={async () => { setModalUsuarioAlta(null); await recargar(); }}
        />
      )}

      {modalImportar && (
        <ModalImportarPadron
          onCerrar={() => setModalImportar(false)}
          onImportado={recargar}
        />
      )}
    </section>
  );
}

function CeldaUsuarios({ usuarios }) {
  if (usuarios.length === 0) {
    return <span className="sin-usuarios">Sin usuarios asignados</span>;
  }
  const primero = usuarios[0];
  const extra = usuarios.length - 1;
  return (
    <span className="usuario-info">
      <span>{primero.email}</span>
      {extra > 0 && <span className="chip-mas">+{extra} más</span>}
    </span>
  );
}

function Paginador({ pagina, total, onCambio }) {
  const paginas = calcularPaginasVisibles(pagina, total);
  return (
    <div className="pagers">
      <button
        type="button"
        onClick={() => onCambio(Math.max(1, pagina - 1))}
        disabled={pagina === 1}
        aria-label="Página anterior"
      >
        ‹
      </button>
      {paginas.map((p, i) =>
        p === "…" ? (
          <span key={`e${i}`} style={{ padding: "0.25rem 0.4rem" }}>…</span>
        ) : (
          <button
            key={p}
            type="button"
            className={p === pagina ? "activo" : ""}
            onClick={() => onCambio(p)}
          >
            {p}
          </button>
        )
      )}
      <button
        type="button"
        onClick={() => onCambio(Math.min(total, pagina + 1))}
        disabled={pagina === total}
        aria-label="Página siguiente"
      >
        ›
      </button>
    </div>
  );
}

function calcularPaginasVisibles(actual, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const res = [1];
  if (actual > 3) res.push("…");
  const start = Math.max(2, actual - 1);
  const end = Math.min(total - 1, actual + 1);
  for (let i = start; i <= end; i++) res.push(i);
  if (actual < total - 2) res.push("…");
  res.push(total);
  return res;
}

function agruparPorDepto(usuarios) {
  const out = {};
  for (const u of usuarios) {
    if (u.rol !== "departamento" || !u.departamento_id) continue;
    if (!out[u.departamento_id]) out[u.departamento_id] = [];
    out[u.departamento_id].push(u);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Modales
// ---------------------------------------------------------------------------

function ModalDetalleDepto({
  departamento,
  usuarios,
  onCerrar,
  onAgregarUsuario,
  onEliminar,
  onSuspenderUsuario,
  onEliminarUsuario,
}) {
  const activos = usuarios.filter((u) => u.activa).length;
  const suspendidos = usuarios.length - activos;

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal modal-detalle-depto" onClick={(e) => e.stopPropagation()}>
        <header className="detalle-depto-header">
          <div>
            <h3>{departamento.codigo}</h3>
            <p className="meta">
              {departamento.descripcion || "Sin ubicación cargada"}
            </p>
          </div>
          <button
            type="button"
            className="cerrar-modal"
            aria-label="Cerrar"
            onClick={onCerrar}
          >
            ×
          </button>
        </header>

        <section className="detalle-depto-seccion">
          <div className="detalle-depto-subheader">
            <div>
              <h4>Usuarios</h4>
              <p className="meta">
                {usuarios.length === 0
                  ? "Sin usuarios asignados"
                  : `${usuarios.length} usuario${usuarios.length > 1 ? "s" : ""}${
                      suspendidos > 0 ? ` · ${activos} activo${activos !== 1 ? "s" : ""}, ${suspendidos} suspendido${suspendidos !== 1 ? "s" : ""}` : ""
                    }`}
              </p>
            </div>
            <button type="button" onClick={onAgregarUsuario}>
              + Agregar usuario
            </button>
          </div>

          {usuarios.length > 0 && (
            <ul className="detalle-depto-usuarios">
              {usuarios.map((u) => (
                <li key={u.id}>
                  <div className="detalle-usuario-info">
                    <div className="detalle-usuario-email">{u.email}</div>
                    <div className="detalle-usuario-estado">
                      <EstadoBadge estado={u.activa ? "activo" : "suspendido"} />
                      {u.must_change_password && (
                        <span className="meta"> · debe cambiar contraseña</span>
                      )}
                    </div>
                  </div>
                  <div className="detalle-usuario-acciones">
                    <button
                      type="button"
                      className="accion-discreta"
                      onClick={() => onSuspenderUsuario(u)}
                    >
                      {u.activa ? "suspender" : "reactivar"}
                    </button>
                    <button
                      type="button"
                      className="accion-discreta peligro"
                      onClick={() => onEliminarUsuario(u)}
                    >
                      eliminar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <footer className="detalle-depto-footer">
          <button
            type="button"
            className="accion-discreta peligro"
            onClick={onEliminar}
          >
            eliminar departamento
          </button>
        </footer>
      </div>
    </div>
  );
}

function ModalDeptoAlta({ onCerrar, onCreado }) {
  const [codigo, setCodigo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setErr(null);
    setEnviando(true);
    const r = await crearDepartamento({
      codigo: codigo.trim(),
      descripcion: descripcion.trim() || null,
    });
    setEnviando(false);
    if (r.status === 201) await onCreado();
    else setErr(r.data?.detail || "No se pudo crear.");
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Nuevo departamento</h3>
        <form onSubmit={onSubmit}>
          <label>
            Código
            <input
              type="text" required maxLength={32}
              value={codigo} onChange={(e) => setCodigo(e.target.value)}
              placeholder="Ej: UF-3C"
            />
          </label>
          <label>
            Ubicación (opcional)
            <input
              type="text" maxLength={255}
              value={descripcion} onChange={(e) => setDescripcion(e.target.value)}
              placeholder="Piso 3, Unidad C"
            />
          </label>
          {err && <p className="error">{err}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={enviando}>
              {enviando ? "Creando…" : "Crear"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ModalUsuarioAlta({ departamento, onCerrar, onCreado }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setErr(null); setEnviando(true);
    const r = await crearUsuario({
      email: email.trim().toLowerCase(),
      password,
      rol: "departamento",
      departamento_id: departamento.id,
    });
    setEnviando(false);
    if (r.status === 201) await onCreado();
    else setErr(r.data?.detail || "No se pudo crear.");
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Nuevo usuario — {departamento.codigo}</h3>
        <form onSubmit={onSubmit}>
          <label>
            Email
            <input
              type="email" required
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Contraseña inicial
            <input
              type="text" required minLength={8}
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <p className="meta">
            El usuario deberá cambiarla al ingresar por primera vez.
          </p>
          {err && <p className="error">{err}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={enviando}>
              {enviando ? "Creando…" : "Crear"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ModalImportarPadron({ onCerrar, onImportado }) {
  const [archivo, setArchivo] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [err, setErr] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    if (!archivo) return;
    setErr(null); setEnviando(true);
    const r = await importarPadronCSV(archivo);
    setEnviando(false);
    if (r.status === 200) {
      setResultado(r.data.resultados);
      const hayCredenciales = r.data.resultados.some((x) => x.password_generada);
      if (hayCredenciales) descargarCredenciales(r.data.resultados);
      await onImportado();
    } else {
      setErr(r.data?.detail || "No se pudo importar.");
    }
  }

  function descargarCredenciales(resultados) {
    const filas = ["codigo,ubicacion,email,password_generada,depto_status,usuario_status,error"];
    for (const r of resultados) {
      filas.push(
        [
          r.codigo,
          r.ubicacion || "",
          r.email || "",
          r.password_generada || "",
          r.depto_status,
          r.usuario_status,
          r.error || "",
        ]
          .map((c) => `"${String(c).replaceAll('"', '""')}"`)
          .join(",")
      );
    }
    const blob = new Blob([filas.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `padron-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const deptosCreados =
    resultado?.filter((r) => r.depto_status === "creado").length || 0;
  const usuariosCreados =
    resultado?.filter((r) => r.usuario_status === "creado").length || 0;
  const errores =
    resultado?.filter(
      (r) => r.depto_status === "error" || r.usuario_status === "error"
    ).length || 0;

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Importar padrón desde CSV</h3>
        {resultado === null ? (
          <form onSubmit={onSubmit}>
            <p className="meta">
              Columnas: <code>codigo</code>, <code>ubicacion</code>,{" "}
              <code>email</code>. Cada fila crea el depto (o lo reutiliza si el
              código ya existe) y opcionalmente crea el usuario con contraseña
              aleatoria. Si <code>email</code> queda vacío solo se crea el depto.
              Las contraseñas se muestran una única vez.
            </p>
            <label>
              Archivo CSV
              <input
                type="file" accept=".csv,text/csv" required
                onChange={(e) => setArchivo(e.target.files?.[0] || null)}
              />
            </label>
            {err && <p className="error">{err}</p>}
            <div className="modal-acciones">
              <button type="button" onClick={onCerrar}>Cancelar</button>
              <button type="submit" disabled={enviando || !archivo}>
                {enviando ? "Importando…" : "Importar"}
              </button>
            </div>
          </form>
        ) : (
          <div>
            <p>
              <strong>{deptosCreados} deptos nuevos</strong> ·{" "}
              <strong>{usuariosCreados} usuarios nuevos</strong>
              {errores > 0 && ` · ${errores} con error`}
            </p>
            {usuariosCreados > 0 && (
              <p className="meta">
                Se descargó un CSV con las contraseñas generadas — guardalo y
                entregalo a cada usuario. No se pueden recuperar después.
              </p>
            )}
            <ul className="lista-config">
              {resultado.map((r, i) => (
                <li key={i}>
                  <strong>{r.codigo || "(sin código)"}</strong>
                  {r.email && ` — ${r.email}`}
                  <p className="meta">
                    Depto: {r.depto_status} · Usuario: {r.usuario_status}
                    {r.password_generada && (
                      <>
                        {" · "}Contraseña: <code>{r.password_generada}</code>
                      </>
                    )}
                    {r.error && (
                      <>
                        {" · "}Error: <code>{r.error}</code>
                      </>
                    )}
                  </p>
                </li>
              ))}
            </ul>
            <div className="modal-acciones">
              <button type="button" onClick={onCerrar}>Cerrar</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
