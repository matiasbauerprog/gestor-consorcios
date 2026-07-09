import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { impersonateEnd } from "../api/superAdmin";

function _formatCountdown(sec) {
  if (sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function BannerImpersonate() {
  const { impersonatedBy, user } = useAuth();
  const [restante, setRestante] = useState(null);
  const [saliendo, setSaliendo] = useState(false);

  useEffect(() => {
    if (!impersonatedBy) return;

    const startedAt = Number(sessionStorage.getItem("impersonate_started_at") || 0);
    const expiresIn = Number(sessionStorage.getItem("impersonate_expires_in") || 15 * 60);
    if (!startedAt) return;

    const tick = () => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setRestante(expiresIn - elapsed);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [impersonatedBy]);

  if (!impersonatedBy) return null;

  async function salir() {
    setSaliendo(true);
    await impersonateEnd().catch(() => {});
    // Restaurar token/user original guardados en sessionStorage.
    const origToken = sessionStorage.getItem("impersonate_original_token");
    const origUser = sessionStorage.getItem("impersonate_original_user");
    sessionStorage.removeItem("impersonate_original_token");
    sessionStorage.removeItem("impersonate_original_user");
    sessionStorage.removeItem("impersonate_expires_in");
    sessionStorage.removeItem("impersonate_started_at");
    if (origToken && origUser) {
      localStorage.setItem("consorcio_token", origToken);
      localStorage.setItem("consorcio_user", origUser);
      window.location.href = "/super-admin/administraciones";
    } else {
      // Sin backup: forzar logout completo.
      localStorage.removeItem("consorcio_token");
      localStorage.removeItem("consorcio_user");
      window.location.href = "/login";
    }
  }

  const expirado = restante !== null && restante <= 0;

  return (
    <section
      className="banner-impersonate"
      role="alert"
      aria-live="polite"
    >
      <span>
        ⚠ <strong>Impersonando</strong> usuario id={user?.id}
        {restante !== null && !expirado && (
          <> · sale en <strong>{_formatCountdown(restante)}</strong></>
        )}
        {expirado && <> · <strong>sesión expirada</strong></>}
      </span>
      <button type="button" onClick={salir} disabled={saliendo}>
        {saliendo ? "Saliendo…" : expirado ? "Volver al super-admin" : "Salir"}
      </button>
    </section>
  );
}
