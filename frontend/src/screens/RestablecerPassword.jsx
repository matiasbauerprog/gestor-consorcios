import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiFetch } from "../api/client";

const MINIMO = 8;

/** Elige la contraseña nueva canjeando el token que vino en el link del email. */
export default function RestablecerPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    // Se valida en el cliente antes de llamar para no gastar el token en un
    // error que se puede ver acá: el token es de un solo uso.
    if (password.length < MINIMO) {
      setError(`La contraseña tiene que tener al menos ${MINIMO} caracteres.`);
      return;
    }
    if (password !== confirmacion) {
      setError("Las dos contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    const result = await apiFetch("/auth/restablecer-password", {
      method: "POST",
      body: { token, new_password: password },
    });
    setLoading(false);

    if (result.status === 204) {
      navigate("/login", {
        replace: true,
        state: { aviso: "Listo. Entrá con tu contraseña nueva." },
      });
      return;
    }

    setError(
      result.data?.detail ||
        "No se pudo cambiar la contraseña. Probá pedir un link nuevo.",
    );
  }

  if (!token) {
    return (
      <main className="login-page">
        <section className="login-card">
          <h1>Link incompleto</h1>
          <p role="alert">
            Este link no trae el código de verificación. Copialo entero desde el
            email, o pedí uno nuevo.
          </p>
          <Link to="/recuperar-password">Pedir un link nuevo</Link>
        </section>
      </main>
    );
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <h1>Elegí una contraseña nueva</h1>

        <form onSubmit={handleSubmit} noValidate>
          <label>
            Contraseña nueva
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoFocus
              autoComplete="new-password"
              minLength={MINIMO}
            />
          </label>

          <label>
            Repetila
            <input
              type="password"
              value={confirmacion}
              onChange={(e) => setConfirmacion(e.target.value)}
              required
              autoComplete="new-password"
            />
          </label>

          {error && (
            <p role="alert" className="login-error">
              {error}
            </p>
          )}

          <button type="submit" disabled={loading}>
            {loading ? "Guardando..." : "Guardar contraseña"}
          </button>
        </form>

        <p className="login-subtitle">
          <Link to="/recuperar-password">Pedir un link nuevo</Link>
        </p>
      </section>
    </main>
  );
}
