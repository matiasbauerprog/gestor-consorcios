import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  crearAdministracion,
  editarAdministracion,
  guardarModulos,
  impersonateStart,
  listarAdministraciones,
  listarUsuariosDeAdministracion,
  obtenerModulos,
  resetPasswordUsuario,
  toggleSuspenderAdministracion,
} from "../api/superAdmin";

function ModalNueva({ onCerrar, onCreada }) {
  const [f, setF] = useState({
    razon_social: "",
    cuit: "",
    email_contacto: "",
    admin_email: "",
    admin_password_inicial: "",
  });
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  function set(k, v) {
    setF((prev) => ({ ...prev, [k]: v }));
  }

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    const r = await crearAdministracion(f);
    setLoading(false);
    if (r.status === 201) {
      onCreada(r.data);
      return;
    }
    setErr(r.data?.detail || "No se pudo crear la administración.");
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>Nueva administración</h2>
          <button type="button" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        <form onSubmit={submit}>
          <label>
            Razón social
            <input
              value={f.razon_social}
              onChange={(e) => set("razon_social", e.target.value)}
              required
              maxLength={255}
            />
          </label>
          <label>
            CUIT
            <input
              value={f.cuit}
              onChange={(e) => set("cuit", e.target.value)}
              required
              maxLength={13}
            />
          </label>
          <label>
            Email de contacto
            <input
              type="email"
              value={f.email_contacto}
              onChange={(e) => set("email_contacto", e.target.value)}
              required
            />
          </label>
          <label>
            Email del primer admin
            <input
              type="email"
              value={f.admin_email}
              onChange={(e) => set("admin_email", e.target.value)}
              required
            />
          </label>
          <label>
            Password inicial
            <input
              type="text"
              value={f.admin_password_inicial}
              onChange={(e) => set("admin_password_inicial", e.target.value)}
              required
              minLength={8}
            />
          </label>
          {err && <p role="alert" className="login-error">{err}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>
              Cancelar
            </button>
            <button type="submit" disabled={loading}>
              {loading ? "Creando…" : "Crear"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const MODULOS_LABELS = {
  comunicacion: "Comunicación",
  cobranzas: "Cobranzas y cuentas corrientes",
  gastos: "Gastos del consorcio",
  finanzas: "Tesorería y finanzas",
  operacion: "Peticiones y trabajos",
  espacios_comunes: "Espacios comunes (reservas)",
  reportes: "Reportes",
  personal: "Personal y liquidaciones",
};

function ModalModulos({ administracion, onCerrar, onFeedback }) {
  const [disponibles, setDisponibles] = useState([]);
  const [habilitados, setHabilitados] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      const r = await obtenerModulos(administracion.id);
      if (ignore) return;
      if (r.status === 200) {
        setDisponibles(r.data.disponibles);
        setHabilitados(new Set(r.data.habilitados));
      } else {
        setErr(r.data?.detail || "No se pudieron cargar los módulos.");
      }
      setLoading(false);
    })();
    return () => { ignore = true; };
  }, [administracion.id]);

  function toggle(key) {
    setHabilitados((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function guardar(e) {
    e.preventDefault();
    setErr(null);
    setGuardando(true);
    const r = await guardarModulos(administracion.id, [...habilitados]);
    setGuardando(false);
    if (r.status === 200) {
      onFeedback(`Módulos actualizados para ${administracion.razon_social}.`);
      onCerrar();
      return;
    }
    setErr(r.data?.detail || "No se pudieron guardar los módulos.");
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>Módulos — {administracion.razon_social}</h2>
          <button type="button" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        {loading ? (
          <p>Cargando…</p>
        ) : (
          <form onSubmit={guardar}>
            <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "0.5rem" }}>
              {disponibles.map((key) => (
                <li key={key}>
                  <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={habilitados.has(key)}
                      onChange={() => toggle(key)}
                    />
                    {MODULOS_LABELS[key] || key}
                  </label>
                </li>
              ))}
            </ul>
            {err && <p role="alert" className="login-error">{err}</p>}
            <div className="modal-acciones">
              <button type="button" onClick={onCerrar}>
                Cancelar
              </button>
              <button type="submit" disabled={guardando}>
                {guardando ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function ModalMotivoImpersonate({ usuario, onCerrar, onConfirmar }) {
  const [motivo, setMotivo] = useState("");
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (motivo.length < 10) {
      setErr("El motivo debe tener al menos 10 caracteres.");
      return;
    }
    setErr(null);
    setLoading(true);
    await onConfirmar(motivo);
    setLoading(false);
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>Impersonar a {usuario.email}</h2>
          <button type="button" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        <form onSubmit={submit}>
          <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
            Rol: <strong>{usuario.rol}</strong>. La sesión de impersonate dura
            15 minutos y queda registrada en el audit log.
          </p>
          <label>
            Motivo (mínimo 10 caracteres)
            <textarea
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              required
              minLength={10}
              maxLength={500}
              rows={3}
            />
          </label>
          {err && <p role="alert" className="login-error">{err}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>
              Cancelar
            </button>
            <button type="submit" disabled={loading}>
              {loading ? "Iniciando…" : "Impersonar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ModalUsuarios({ administracion, onCerrar, onFeedback, onPasswordTemporal }) {
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [motivoUsuario, setMotivoUsuario] = useState(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    const r = await listarUsuariosDeAdministracion(administracion.id);
    if (r.status === 200) setUsuarios(r.data);
    else onFeedback(r.data?.detail || "No se pudieron listar los usuarios.");
    setLoading(false);
  }, [administracion.id, onFeedback]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function resetPassword(u) {
    const r = await resetPasswordUsuario(administracion.id, u.id);
    if (r.status === 200) {
      onPasswordTemporal({
        email: u.email,
        password: r.data.password_temporal,
      });
      cargar();
    } else {
      onFeedback(r.data?.detail || "No se pudo resetear la password.");
    }
  }

  async function confirmarImpersonate(motivo) {
    const u = motivoUsuario;
    const r = await impersonateStart(u.id, motivo);
    if (r.status !== 200) {
      onFeedback(r.data?.detail || "No se pudo iniciar impersonate.");
      setMotivoUsuario(null);
      return;
    }
    sessionStorage.setItem(
      "impersonate_original_token",
      localStorage.getItem("consorcio_token") || ""
    );
    sessionStorage.setItem(
      "impersonate_original_user",
      localStorage.getItem("consorcio_user") || ""
    );
    sessionStorage.setItem("impersonate_expires_in", String(r.data.expires_in));
    sessionStorage.setItem("impersonate_started_at", String(Date.now()));

    localStorage.setItem("consorcio_token", r.data.access_token);
    localStorage.setItem(
      "consorcio_user",
      JSON.stringify({
        id: r.data.impersonated_user_id,
        email: u.email,
        rol: u.rol,
        departamento_id: u.departamento_id,
      })
    );
    localStorage.removeItem("consorcio_activo_id");
    const destino = u.rol === "departamento" ? "/mi-cuenta" : "/comunicados";
    window.location.href = destino;
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "640px" }}
      >
        <header>
          <h2>Usuarios de {administracion.razon_social}</h2>
          <button type="button" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        {loading ? (
          <p>Cargando…</p>
        ) : usuarios.length === 0 ? (
          <p>No hay usuarios registrados en esta administración.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "0.5rem" }}>
            {usuarios.map((u) => (
              <li
                key={u.id}
                className="tarjeta"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <strong>{u.email}</strong>
                  <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
                    Rol: {u.rol}
                    {u.departamento_id ? ` · depto #${u.departamento_id}` : ""}
                    {u.must_change_password ? " · debe cambiar password" : ""}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button type="button" onClick={() => resetPassword(u)}>
                    Reset password
                  </button>
                  <button type="button" onClick={() => setMotivoUsuario(u)}>
                    Impersonar
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="modal-acciones">
          <button type="button" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
      {motivoUsuario && (
        <ModalMotivoImpersonate
          usuario={motivoUsuario}
          onCerrar={() => setMotivoUsuario(null)}
          onConfirmar={confirmarImpersonate}
        />
      )}
    </div>
  );
}

export default function SuperAdminAdministraciones() {
  const { user, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalNueva, setModalNueva] = useState(false);
  const [modalUsuariosDe, setModalUsuariosDe] = useState(null);
  const [modalModulosDe, setModalModulosDe] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [passwordTemporal, setPasswordTemporal] = useState(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    const r = await listarAdministraciones();
    if (r.status === 200) setItems(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!user) return null;
  if (user.rol !== "super_admin") return <Navigate to="/" replace />;

  async function toggleSuspender(a) {
    const r = await toggleSuspenderAdministracion(a.id);
    if (r.status === 200) {
      setFeedback(
        r.data.activa
          ? `Reactivada: ${r.data.razon_social}`
          : `Suspendida: ${r.data.razon_social}`
      );
      cargar();
    } else {
      setFeedback(r.data?.detail || "Error al cambiar estado.");
    }
  }

  async function editar(a) {
    const nueva = prompt("Nueva razón social", a.razon_social);
    if (!nueva || nueva === a.razon_social) return;
    const r = await editarAdministracion(a.id, { razon_social: nueva });
    if (r.status === 200) cargar();
  }

  return (
    <section>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <h2>Administraciones</h2>
        <button type="button" onClick={() => setModalNueva(true)}>
          + Nueva administración
        </button>
      </header>

      {feedback && (
        <p role="status" style={{ color: "var(--color-primary)" }}>
          {feedback}
        </p>
      )}
      {passwordTemporal && (
        <article
          className="tarjeta"
          style={{ borderColor: "var(--color-danger)" }}
        >
          <strong>Password temporal generada</strong>
          <p>
            Usuario {passwordTemporal.email}:{" "}
            <code>{passwordTemporal.password}</code>
          </p>
          <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
            Copiala ahora — no se muestra dos veces. El usuario debe cambiarla al
            iniciar sesión.
          </p>
          <button type="button" onClick={() => setPasswordTemporal(null)}>
            Ok
          </button>
        </article>
      )}

      {loading ? (
        <p>Cargando…</p>
      ) : items.length === 0 ? (
        <p>No hay administraciones registradas.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "0.75rem" }}>
          {items.map((a) => (
            <li key={a.id} className="tarjeta">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "start",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <strong>{a.razon_social}</strong>
                  <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
                    CUIT: {a.cuit} · {a.email_contacto} · plan {a.plan}
                  </div>
                  <div style={{ fontSize: "0.85rem" }}>
                    Estado:{" "}
                    <strong style={{ color: a.activa ? "var(--color-primary)" : "var(--color-danger)" }}>
                      {a.activa ? "Activa" : "Suspendida"}
                    </strong>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button type="button" onClick={() => editar(a)}>
                    Editar
                  </button>
                  <button type="button" onClick={() => toggleSuspender(a)}>
                    {a.activa ? "Suspender" : "Reactivar"}
                  </button>
                  <button type="button" onClick={() => setModalUsuariosDe(a)}>
                    Gestionar usuarios
                  </button>
                  <button type="button" onClick={() => setModalModulosDe(a)}>
                    Módulos
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {modalNueva && (
        <ModalNueva
          onCerrar={() => setModalNueva(false)}
          onCreada={(nueva) => {
            setModalNueva(false);
            setFeedback(`Creada: ${nueva.razon_social}`);
            cargar();
          }}
        />
      )}

      {modalUsuariosDe && (
        <ModalUsuarios
          administracion={modalUsuariosDe}
          onCerrar={() => setModalUsuariosDe(null)}
          onFeedback={setFeedback}
          onPasswordTemporal={setPasswordTemporal}
        />
      )}

      {modalModulosDe && (
        <ModalModulos
          administracion={modalModulosDe}
          onCerrar={() => setModalModulosDe(null)}
          onFeedback={setFeedback}
        />
      )}

      <div style={{ marginTop: "2rem" }}>
        <button type="button" onClick={logout}>
          Cerrar sesión
        </button>
      </div>
    </section>
  );
}
