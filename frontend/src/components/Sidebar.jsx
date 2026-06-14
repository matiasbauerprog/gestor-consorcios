import { NavLink } from "react-router-dom";

const MODULOS = [
  {
    ruta: "/comunicados",
    nombre: "Comunicación",
    rolesPermitidos: ["administracion", "representante", "departamento"],
  },
  {
    ruta: "/expensas",
    nombre: "Expensas",
    rolesPermitidos: ["administracion", "departamento"],
  },
  {
    ruta: "/comprobantes",
    nombre: "Comprobantes",
    rolesPermitidos: ["administracion", "departamento"],
  },
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
