import { NavLink } from "react-router-dom";

const MODULOS = [
  {
    ruta: "/comunicados",
    nombre: "Comunicación",
    rolesPermitidos: ["administracion", "representante", "departamento"],
  },
  // Los próximos módulos se agregan acá (expensas, peticiones, trabajos, reservas, administración).
];

export default function Sidebar({ rol }) {
  const visibles = MODULOS.filter((m) => m.rolesPermitidos.includes(rol));

  return (
    <aside className="app-sidebar">
      <nav>
        <ul>
          {visibles.map((m) => (
            <li key={m.ruta}>
              <NavLink
                to={m.ruta}
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
