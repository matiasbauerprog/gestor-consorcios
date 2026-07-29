import { useState } from "react";
import { NavLink } from "react-router-dom";
import Modal from "./Modal";

const ICONOS = {
  casa: "m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
  moneda: "M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 6v2m0 8v2",
  documento: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6M16 13H8M16 17H8",
  billetera: "M21 12V7H5a2 2 0 0 1 0-4h14v4 M3 5v14a2 2 0 0 0 2 2h16v-5 M18 12a2 2 0 0 0 0 4h4v-4Z",
  llave: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z",
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  calendario: "M16 2v4M8 2v4M3 10h18",
  campana: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9 M10.3 21a1.94 1.94 0 0 0 3.4 0",
  mas: "M5 12h.01M12 12h.01M19 12h.01",
};

function Icono({ nombre }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONOS[nombre].split(" M").map((d, i) => (
        <path key={i} d={i === 0 ? d : `M${d}`} />
      ))}
    </svg>
  );
}

export default function TabBar({ tabs, seccionesMas }) {
  const [sheetMas, setSheetMas] = useState(false);

  if (!tabs) return null; // super_admin conserva su drawer

  return (
    <>
      <nav className="tabbar" aria-label="Módulos">
        {tabs.map((t) => (
          <NavLink
            key={t.ruta}
            to={t.ruta}
            end={t.ruta === "/"}
            className={({ isActive }) =>
              isActive ? "tabbar-item activo" : "tabbar-item"
            }
          >
            <Icono nombre={t.icono} />
            <span>{t.nombre}</span>
          </NavLink>
        ))}
        <button type="button" className="tabbar-item" onClick={() => setSheetMas(true)}>
          <Icono nombre="mas" />
          <span>Más</span>
        </button>
      </nav>

      {sheetMas && (
        <Modal titulo="Más" onClose={() => setSheetMas(false)}>
          <nav className="sheet-mas" aria-label="Más secciones">
            {seccionesMas.map((s) => (
              <section key={s.titulo}>
                <p className="micro-label">{s.titulo}</p>
                <ul>
                  {s.modulos.map((m) => (
                    <li key={m.ruta}>
                      <NavLink to={m.ruta} onClick={() => setSheetMas(false)}>
                        {m.nombre}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </nav>
        </Modal>
      )}
    </>
  );
}
