import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Sidebar from "./Sidebar";

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [drawerAbierto, setDrawerAbierto] = useState(false);

  const cerrarDrawer = () => setDrawerAbierto(false);

  useEffect(() => {
    if (!drawerAbierto) return;
    function onKey(e) {
      if (e.key === "Escape") cerrarDrawer();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerAbierto]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-titulo">
          <button
            type="button"
            className="hamburguesa"
            aria-label="Abrir menú"
            aria-expanded={drawerAbierto}
            onClick={() => setDrawerAbierto(true)}
          >
            ☰
          </button>
          <h1>Gestión de Consorcios</h1>
        </div>
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
        {drawerAbierto && (
          <div
            className="drawer-backdrop"
            onClick={cerrarDrawer}
            aria-hidden="true"
          />
        )}
        <Sidebar rol={user.rol} abierto={drawerAbierto} onCerrar={cerrarDrawer} />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
