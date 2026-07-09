import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }) {
  const { user, hydrating, mustChangePassword } = useAuth();
  const location = useLocation();

  if (hydrating) {
    return <p style={{ padding: "2rem", textAlign: "center" }}>Cargando...</p>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // Forzar cambio de password si must_change_password. Sólo se permite la
  // pantalla dedicada para no bloquear cuando el user está justo cambiándola.
  if (
    mustChangePassword &&
    !location.pathname.startsWith("/mi-usuario/cambiar-password")
  ) {
    return <Navigate to="/mi-usuario/cambiar-password" replace />;
  }

  return children;
}
