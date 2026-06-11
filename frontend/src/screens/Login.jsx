import { useState } from "react";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const result = await apiFetch("/auth/login", {
      method: "POST",
      body: { email, password },
    });

    setLoading(false);

    if (result.status === 200) {
      login(result.data.access_token, result.data.user);
      return;
    }

    if (result.status === 401) {
      setError("Credenciales inválidas.");
      return;
    }

    if (result.status === 400) {
      setError(result.data?.detail || "El pedido es inválido o le faltan campos requeridos.");
      return;
    }

    setError(result.data?.detail || "Ocurrió un error inesperado. Intentá de nuevo.");
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <h1>Gestión de Consorcios</h1>
        <p className="login-subtitle">Iniciá sesión para continuar.</p>

        <form onSubmit={handleSubmit} noValidate>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              autoComplete="email"
            />
          </label>

          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>

          {error && <p role="alert" className="login-error">{error}</p>}

          <button type="submit" disabled={loading}>
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>
      </section>
    </main>
  );
}
