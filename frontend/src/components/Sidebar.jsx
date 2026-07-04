import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { obtenerConfiguracion } from "../api/configuracion";

const SECCIONES = [
  {
    titulo: "Comunicaciones",
    modulos: [
      {
        ruta: "/comunicados",
        nombre: "Comunicados",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reglamento",
        nombre: "Reglamento",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
    ],
  },
  {
    titulo: "Finanzas",
    modulos: [
      {
        ruta: "/mi-cuenta",
        nombre: "Mi cuenta",
        rolesPermitidos: ["departamento"],
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
      {
        ruta: "/periodos",
        nombre: "Historial de cierres",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/gastos",
        nombre: "Gastos",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/estado-financiero",
        nombre: "Estado financiero",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/cajas",
        nombre: "Cajas",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/transferencias",
        nombre: "Transferencias",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
  {
    titulo: "Operación",
    modulos: [
      {
        ruta: "/peticiones",
        nombre: "Peticiones",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/trabajos",
        nombre: "Trabajos",
        rolesPermitidos: ["administracion", "representante"],
      },
      {
        ruta: "/trabajos-recurrentes",
        nombre: "Trabajos recurrentes",
        rolesPermitidos: ["administracion", "representante"],
      },
      {
        ruta: "/reservas",
        nombre: "Reservas",
        rolesPermitidos: ["administracion", "departamento"],
      },
      {
        ruta: "/amenities",
        nombre: "Amenities",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
  {
    titulo: "Reportes",
    modulos: [
      {
        ruta: "/reportes/morosos",
        nombre: "Lista de morosos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reportes/estado-financiero",
        nombre: "Estado financiero",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reportes/gastos",
        nombre: "Detalle de gastos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
      {
        ruta: "/reportes/proveedores",
        nombre: "Lista de proveedores",
        rolesPermitidos: ["administracion", "representante", "departamento"],
      },
    ],
  },
  {
    titulo: "Personal",
    modulos: [
      {
        ruta: "/liquidaciones",
        nombre: "Liquidaciones",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/haberes",
        nombre: "Haberes",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/conceptos-liquidacion",
        nombre: "Conceptos de liquidación",
        rolesPermitidos: ["administracion"],
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
      {
        ruta: "/empleados",
        nombre: "Empleados",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
];

function grupoDeRuta(pathname) {
  for (const seccion of SECCIONES) {
    if (seccion.modulos.some((m) => pathname.startsWith(m.ruta))) {
      return seccion.titulo;
    }
  }
  return null;
}

export default function Sidebar({ rol, abierto, onCerrar }) {
  // Para depto: el admin debe habilitar la visibilidad de reportes.
  // Otros roles los ven siempre (admin/representante).
  const [reportesVisiblesDepto, setReportesVisiblesDepto] = useState(false);

  const location = useLocation();
  const [grupoAbierto, setGrupoAbierto] = useState(() =>
    grupoDeRuta(location.pathname)
  );

  useEffect(() => {
    const grupo = grupoDeRuta(location.pathname);
    if (grupo) setGrupoAbierto(grupo);
  }, [location.pathname]);

  function toggleGrupo(titulo) {
    setGrupoAbierto((actual) => (actual === titulo ? null : titulo));
  }

  useEffect(() => {
    if (rol !== "departamento") return;
    (async () => {
      const r = await obtenerConfiguracion();
      if (r.status === 200) {
        setReportesVisiblesDepto(!!r.data?.reportes_visibles_a_depto);
      }
    })();
  }, [rol]);

  const seccionesVisibles = SECCIONES.map((s) => ({
    ...s,
    modulos: s.modulos.filter((m) => {
      if (!m.rolesPermitidos.includes(rol)) return false;
      // Ocultar reportes a depto si el admin no los habilitó
      if (rol === "departamento" && m.ruta.startsWith("/reportes/") && !reportesVisiblesDepto) {
        return false;
      }
      return true;
    }),
  })).filter((s) => s.modulos.length > 0);

  return (
    <aside className={abierto ? "app-sidebar abierto" : "app-sidebar"}>
      <div className="sidebar-logo">Gestión de Consorcios</div>
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
        {seccionesVisibles.map((s) => {
          const expandido = grupoAbierto === s.titulo;
          const grupoActivo = grupoDeRuta(location.pathname) === s.titulo;
          return (
            <div key={s.titulo} className="sidebar-section">
              <button
                type="button"
                className={
                  grupoActivo
                    ? "sidebar-section-titulo activo"
                    : "sidebar-section-titulo"
                }
                aria-expanded={expandido}
                onClick={() => toggleGrupo(s.titulo)}
              >
                <span>{s.titulo}</span>
                <span className="sidebar-chevron" aria-hidden="true">▸</span>
              </button>
              {expandido && (
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
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
