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
  {
    titulo: "Configuración",
    modulos: [
      {
        ruta: "/configuracion",
        nombre: "Datos del consorcio",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/clases-prorrateo",
        nombre: "Clases de prorrateo",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/proveedores",
        nombre: "Proveedores",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/departamentos",
        nombre: "Departamentos",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
];

export default function Sidebar({ rol, abierto, onCerrar }) {
  const seccionesVisibles = SECCIONES.map((s) => ({
    ...s,
    modulos: s.modulos.filter((m) => m.rolesPermitidos.includes(rol)),
  })).filter((s) => s.modulos.length > 0);

  return (
    <aside className={abierto ? "app-sidebar abierto" : "app-sidebar"}>
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
        {seccionesVisibles.map((s) => (
          <div key={s.titulo} className="sidebar-section">
            <h3 className="sidebar-section-titulo">{s.titulo}</h3>
            <ul>
              {s.modulos.map((m) => (
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
          </div>
        ))}
      </nav>
    </aside>
  );
}
