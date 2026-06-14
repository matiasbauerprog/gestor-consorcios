import { NavLink } from "react-router-dom";

const SECCIONES = [
  {
    titulo: "General",
    modulos: [
      {
        ruta: "/comunicados",
        nombre: "Comunicación",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
    ],
  },
  {
    titulo: "Expensas y pagos",
    modulos: [
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
    ],
  },
];

export default function Sidebar({ rol }) {
  const seccionesVisibles = SECCIONES.map((s) => ({
    ...s,
    modulos: s.modulos.filter((m) => m.rolesPermitidos.includes(rol)),
  })).filter((s) => s.modulos.length > 0);

  return (
    <aside className="app-sidebar">
      <nav>
        {seccionesVisibles.map((s) => (
          <div key={s.titulo} className="sidebar-section">
            <h3 className="sidebar-section-titulo">{s.titulo}</h3>
            <ul>
              {s.modulos.map((m) => (
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
          </div>
        ))}
      </nav>
    </aside>
  );
}
