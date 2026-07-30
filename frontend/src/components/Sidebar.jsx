import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { categoriaDeRuta, aplanarParaDepto } from "../navegacion";

export default function Sidebar({ rol, secciones: seccionesVisibles, abierto, onCerrar }) {
  const location = useLocation();
  const [grupoAbierto, setGrupoAbierto] = useState(() =>
    categoriaDeRuta(location.pathname)
  );

  useEffect(() => {
    const grupo = categoriaDeRuta(location.pathname);
    if (grupo) setGrupoAbierto(grupo);
  }, [location.pathname]);

  function toggleGrupo(titulo) {
    setGrupoAbierto((actual) => (actual === titulo ? null : titulo));
  }

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
          (() => {
            const { items, subgrupos } = aplanarParaDepto(seccionesVisibles);
            return (
              <ul>
                {items.map((m) => (
                  <li key={m.ruta}>
                    <NavLink to={m.ruta} onClick={onCerrar}
                      className={({ isActive }) => isActive ? "sidebar-link activo" : "sidebar-link"}>
                      {m.nombre}
                    </NavLink>
                  </li>
                ))}
                {subgrupos.map((sg) => (
                  <li key={sg.id}>
                    <p className="sidebar-subgrupo">{sg.titulo}</p>
                    <ul>
                      {sg.hijos.map((m) => (
                        <li key={m.ruta}>
                          <NavLink to={m.ruta} onClick={onCerrar}
                            className={({ isActive }) => isActive ? "sidebar-link en-subgrupo activo" : "sidebar-link en-subgrupo"}>
                            {m.nombre}
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            );
          })()
        ) : (
          seccionesVisibles.map((nodo) => {
            // 1. Item suelto (Inicio)
            if (nodo.ruta) {
              return (
                <ul key={nodo.ruta} className="sidebar-section">
                  <li>
                    <NavLink to={nodo.ruta} end={nodo.ruta === "/"} onClick={onCerrar}
                      className={({ isActive }) => isActive ? "sidebar-link activo" : "sidebar-link"}>
                      {nodo.nombre}
                    </NavLink>
                  </li>
                </ul>
              );
            }
            // 2. Categoria acordeon
            const expandido = grupoAbierto === nodo.titulo;
            const categoriaActiva = categoriaDeRuta(location.pathname) === nodo.titulo;
            return (
              <div key={nodo.id} className="sidebar-section">
                <button type="button"
                  className={categoriaActiva ? "sidebar-section-titulo activo" : "sidebar-section-titulo"}
                  aria-expanded={expandido}
                  onClick={() => toggleGrupo(nodo.titulo)}>
                  <span>{nodo.titulo}</span>
                  <span className="sidebar-chevron" aria-hidden="true">▸</span>
                </button>
                {expandido && (
                  <ul>
                    {nodo.hijos.map((hijo) =>
                      hijo.ruta ? (
                        // 3a. Item directo
                        <li key={hijo.ruta}>
                          <NavLink to={hijo.ruta} onClick={onCerrar}
                            className={({ isActive }) => isActive ? "sidebar-link activo" : "sidebar-link"}>
                            {hijo.nombre}
                          </NavLink>
                        </li>
                      ) : (
                        // 3b. Sub-grupo: label no-clickable + items
                        <li key={hijo.id}>
                          <p className="sidebar-subgrupo">{hijo.titulo}</p>
                          <ul>
                            {hijo.hijos.map((m) => (
                              <li key={m.ruta}>
                                <NavLink to={m.ruta} onClick={onCerrar}
                                  className={({ isActive }) => isActive ? "sidebar-link en-subgrupo activo" : "sidebar-link en-subgrupo"}>
                                  {m.nombre}
                                </NavLink>
                              </li>
                            ))}
                          </ul>
                        </li>
                      )
                    )}
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
