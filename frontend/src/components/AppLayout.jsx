import { Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Sidebar from "./Sidebar";

export default function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Gestión de Consorcios</h1>
        <nav className="app-user">
          <span>
            {user.email} <strong>({user.rol})</strong>
          </span>
          <button type="button" onClick={logout}>
            Cerrar sesión
          </button>
        </nav>
      </header>

      <div className="app-body">
        <Sidebar rol={user.rol} />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
