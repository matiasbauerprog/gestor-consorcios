import { useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../api/client";

/**
 * Pide el link de recuperación.
 *
 * Muestra **el mismo mensaje pase lo que pase**, incluso si el servidor
 * responde con un error: si la pantalla distinguiera los casos, se convertiría
 * en un verificador de qué emails están registrados, que es justamente lo que
 * el backend evita respondiendo siempre 202.
 */
export default function RecuperarPassword() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    await apiFetch("/auth/recuperar-password", {
      method: "POST",
      body: { email },
    });
    setLoading(false);
    setEnviado(true);
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <h1>¿Olvidaste tu contraseña?</h1>

        {enviado ? (
          <>
            <p role="status">
              Si el email está registrado, te va a llegar un mensaje con un link
              para elegir una contraseña nueva.
            </p>
            <p className="login-subtitle">
              Revisá también la carpeta de correo no deseado. El link vence en
              una hora.
            </p>
            <Link to="/login">Volver al inicio de sesión</Link>
          </>
        ) : (
          <>
            <p className="login-subtitle">
              Escribí tu email y te mandamos un link para elegir una nueva.
            </p>

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

              <button type="submit" disabled={loading}>
                {loading ? "Enviando..." : "Enviar link"}
              </button>
            </form>

            <p className="login-subtitle">
              <Link to="/login">Volver al inicio de sesión</Link>
            </p>
          </>
        )}
      </section>
    </main>
  );
}
