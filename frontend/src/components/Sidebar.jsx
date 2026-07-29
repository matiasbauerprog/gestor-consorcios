import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { grupoDeRuta, ORDEN_DEPTO } from "../navegacion";
import { useNavegacionVisible } from "../hooks/useNavegacionVisible";

export default function Sidebar({ rol, abierto, onCerrar }) {
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

  const { secciones: seccionesVisibles } = useNavegacionVisible(rol);

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
