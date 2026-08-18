import { NavLink } from "react-router-dom";

const ITEMS = [
  { ruta: "/super-admin/administraciones", nombre: "Administraciones" },
  { ruta: "/super-admin/metricas", nombre: "Métricas" },
  { ruta: "/super-admin/audit-log", nombre: "Audit log" },
  { ruta: "/super-admin/errores", nombre: "Errores" },
];

export default function SidebarSuperAdmin({ abierto, onCerrar }) {
  return (
    <aside className={abierto ? "app-sidebar abierto" : "app-sidebar"}>
      <div className="sidebar-logo">Super-Admin</div>
      <div className="sidebar-cabecera">
        <span className="sidebar-cabecera-titulo">Menú</span>
        <button
          type="button"
          className="sidebar-cerrar"
          onClick={onCerrar}
          aria-label="Cerrar menú"
        >
          ✕
        </button>
      </div>
      <nav>
        <ul>
          {ITEMS.map((m) => (
            <li key={m.ruta}>
              <NavLink
                to={m.ruta}
                onClick={onCerrar}
                className={({ isActive }) =>
                  isActive ? "sidebar-link activo" : "sidebar-link"
                }
              >
                {m.nombre}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
