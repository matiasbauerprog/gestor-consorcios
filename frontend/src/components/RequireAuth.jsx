import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }) {
  const { user, hydrating } = useAuth();
  const location = useLocation();

  if (hydrating) {
    return <p style={{ padding: "2rem", textAlign: "center" }}>Cargando...</p>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
