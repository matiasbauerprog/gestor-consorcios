import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { obtenerConfiguracion } from "../api/configuracion";
import { obtenerConsorcio } from "../api/consorcios";
import { useAuth } from "../auth/AuthContext";

const ORDEN_DEPTO = ["/mi-cuenta", "/peticiones", "/reservas", "/comunicados"];

const SECCIONES = [
  {
    titulo: "Comunicación",
    modulos: [
      {
        ruta: "/comunicados",
        nombre: "Comunicación",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "comunicacion",
      },
    ],
  },
  {
    titulo: "Cobranzas y gastos",
    modulos: [
      {
        ruta: "/mi-cuenta",
        nombre: "Mi cuenta",
        rolesPermitidos: ["departamento"],
        modulo: "cobranzas",
      },
      {
        ruta: "/cobranzas",
        nombre: "Cobranzas",
        rolesPermitidos: ["administracion"],
        modulo: "cobranzas",
      },
      {
        ruta: "/gastos",
        nombre: "Gastos",
        rolesPermitidos: ["administracion"],
        modulo: "gastos",
      },
    ],
  },
  {
    titulo: "Finanzas",
    modulos: [
      {
        ruta: "/tesoreria",
        nombre: "Tesorería",
        rolesPermitidos: ["administracion"],
        modulo: "finanzas",
      },
      {
        ruta: "/cuentas-corrientes",
        nombre: "Cuentas corrientes",
        rolesPermitidos: ["administracion"],
        modulo: "cobranzas",
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
        modulo: "operacion",
      },
      {
        ruta: "/trabajos",
        nombre: "Trabajos",
        rolesPermitidos: ["administracion", "representante"],
        modulo: "operacion",
      },
      {
        ruta: "/trabajos-recurrentes",
        nombre: "Trabajos recurrentes",
        rolesPermitidos: ["administracion", "representante"],
        modulo: "operacion",
      },
    ],
  },
  {
    titulo: "Espacios comunes",
    modulos: [
      {
        ruta: "/reservas",
        nombre: "Reservas",
        rolesPermitidos: ["administracion", "departamento"],
        modulo: "espacios_comunes",
      },
      {
        ruta: "/amenities",
        nombre: "Amenities",
        rolesPermitidos: ["administracion"],
        modulo: "espacios_comunes",
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
        modulo: "reportes",
      },
      {
        ruta: "/reportes/estado-financiero",
        nombre: "Estado financiero",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
      },
      {
        ruta: "/reportes/gastos",
        nombre: "Detalle de gastos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
      },
      {
        ruta: "/reportes/proveedores",
        nombre: "Lista de proveedores",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
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
        modulo: "personal",
      },
      {
        ruta: "/haberes",
        nombre: "Haberes",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
      },
      {
        ruta: "/conceptos-liquidacion",
        nombre: "Conceptos de liquidación",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
      },
      {
        ruta: "/empleados",
        nombre: "Empleados",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
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
        ruta: "/administracion/consorcios",
        nombre: "Consorcios de la administración",
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
        ruta: "/padron",
        nombre: "Usuarios y coeficientes",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
];

function grupoDeRuta(pathname) {
  for (const seccion of SECCIONES) {
    if (
      seccion.modulos.some(
        (m) => pathname === m.ruta || pathname.startsWith(m.ruta + "/")
      )
    ) {
      return seccion.titulo;
    }
  }
  return null;
}

export default function Sidebar({ rol, abierto, onCerrar }) {
  // Para depto: el admin debe habilitar la visibilidad de reportes.
  // Otros roles los ven siempre (admin/representante).
  const [reportesVisiblesDepto, setReportesVisiblesDepto] = useState(false);
  const [usaPersonalPropio, setUsaPersonalPropio] = useState(true);
  const [modulosHabilitados, setModulosHabilitados] = useState(null); // null = cargando → mostrar todo

  const { consorcioActivoId } = useAuth();
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
    if (!consorcioActivoId) return;
    (async () => {
      // reportes_visibles_a_depto sigue viniendo de /configuracion (compat).
      const r = await obtenerConfiguracion();
      if (r.status === 200) {
        setReportesVisiblesDepto(!!r.data?.reportes_visibles_a_depto);
      }
      // usa_personal_propio viene del endpoint nuevo /consorcios/{id}.
      const c = await obtenerConsorcio(consorcioActivoId);
      if (c.status === 200 && c.data?.usa_personal_propio !== undefined) {
        setUsaPersonalPropio(!!c.data.usa_personal_propio);
      }
      if (c.status === 200 && Array.isArray(c.data?.modulos_habilitados)) {
        setModulosHabilitados(c.data.modulos_habilitados);
      }
    })();
  }, [rol, consorcioActivoId]);

  const seccionesVisibles = SECCIONES.map((s) => ({
    ...s,
    modulos: s.modulos.filter((m) => {
      if (!m.rolesPermitidos.includes(rol)) return false;
      // Ocultar reportes a depto si el admin no los habilitó
      if (rol === "departamento" && m.ruta.startsWith("/reportes/") && !reportesVisiblesDepto) {
        return false;
      }
      // Módulo deshabilitado por super_admin para esta administración.
      if (m.modulo && modulosHabilitados !== null && !modulosHabilitados.includes(m.modulo)) {
        return false;
      }
      return true;
    }),
  }))
    .filter((s) => s.modulos.length > 0)
    // Feature flag: si el consorcio no usa personal propio, ocultar el grupo.
    .filter((s) => usaPersonalPropio || s.titulo !== "Personal");

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
        {rol === "departamento" ? (
          <ul>
            {seccionesVisibles
              .flatMap((s) => s.modulos)
              .sort((a, b) => {
                const ia = ORDEN_DEPTO.indexOf(a.ruta);
                const ib = ORDEN_DEPTO.indexOf(b.ruta);
                const na = ia === -1 ? ORDEN_DEPTO.length : ia;
                const nb = ib === -1 ? ORDEN_DEPTO.length : ib;
                return na - nb;
              })
              .map((m) => (
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
        ) : (
          seccionesVisibles.map((s) => {
            if (s.modulos.length === 1) {
              const m = s.modulos[0];
              return (
                <ul key={s.titulo} className="sidebar-section">
                  <li>
                    <NavLink
                      to={m.ruta}
                      onClick={onCerrar}
                      className={({ isActive }) =>
                        isActive ? "sidebar-link activo" : "sidebar-link"
                      }
                    >
                      {s.titulo}
                    </NavLink>
                  </li>
                </ul>
              );
            }
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
          })
        )}
      </nav>
    </aside>
  );
}
