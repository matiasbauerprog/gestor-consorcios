import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function CambiarPassword() {
  const { mustChangePassword, marcarPasswordCambiada, user } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setOk(false);

    if (newPassword.length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (newPassword !== newPassword2) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    const r = await apiFetch("/auth/cambiar-password", {
      method: "POST",
      body: { current_password: currentPassword, new_password: newPassword },
    });
    setLoading(false);

    if (r.status === 204) {
      marcarPasswordCambiada();
      setOk(true);
      setTimeout(() => {
        if (user?.rol === "super_admin") {
          navigate("/super-admin/administraciones", { replace: true });
        } else {
          navigate("/comunicados", { replace: true });
        }
      }, 800);
      return;
    }

    if (r.status === 401) {
      setError("La contraseña actual es incorrecta.");
      return;
    }

    setError(r.data?.detail || "No se pudo actualizar la contraseña.");
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <h1>Cambiar contraseña</h1>
        {mustChangePassword ? (
          <p className="login-subtitle">
            Por seguridad, tenés que cambiar tu contraseña antes de continuar.
          </p>
        ) : (
          <p className="login-subtitle">Actualizá tu contraseña.</p>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <label>
            Contraseña actual
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
              autoFocus
            />
          </label>
          <label>
            Nueva contraseña
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label>
            Repetir nueva contraseña
            <input
              type="password"
              value={newPassword2}
              onChange={(e) => setNewPassword2(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>

          {error && (
            <p role="alert" className="login-error">
              {error}
            </p>
          )}
          {ok && (
            <p role="status" style={{ color: "var(--color-primary)" }}>
              ✓ Contraseña actualizada. Redirigiendo…
            </p>
          )}

          <button type="submit" disabled={loading}>
            {loading ? "Guardando…" : "Guardar"}
          </button>
        </form>
      </section>
    </main>
  );
}
