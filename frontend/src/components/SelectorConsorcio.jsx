import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";

export default function SelectorConsorcio() {
  const { consorciosAccesibles, consorcioActivoId, seleccionarConsorcio, user } =
    useAuth();
  const [abierto, setAbierto] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!abierto) return;
    function onClickOut(e) {
      if (ref.current && !ref.current.contains(e.target)) setAbierto(false);
    }
    document.addEventListener("mousedown", onClickOut);
    return () => document.removeEventListener("mousedown", onClickOut);
  }, [abierto]);

  // Ocultar si super_admin (no aplica) o si el usuario tiene sólo 1 consorcio.
  if (!user || user.rol === "super_admin") return null;
  if (!consorciosAccesibles || consorciosAccesibles.length < 2) return null;

  const activo = consorciosAccesibles.find((c) => c.id === consorcioActivoId);
  const nombre = activo?.nombre || "Seleccioná consorcio";

  function elegir(id) {
    if (id !== consorcioActivoId) {
      seleccionarConsorcio(id);
      // Refrescar la vista actual con el nuevo header X-Consorcio-Id.
      window.location.reload();
    }
    setAbierto(false);
  }

  return (
    <div className="selector-consorcio" ref={ref}>
      <button
        type="button"
        className="selector-consorcio-boton"
        aria-haspopup="listbox"
        aria-expanded={abierto}
        onClick={() => setAbierto((v) => !v)}
      >
        <span className="selector-consorcio-nombre">{nombre}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {abierto && (
        <ul className="selector-consorcio-lista" role="listbox">
          {consorciosAccesibles.map((c) => (
            <li
              key={c.id}
              role="option"
              aria-selected={c.id === consorcioActivoId}
              className={
                c.id === consorcioActivoId
                  ? "selector-consorcio-item activo"
                  : "selector-consorcio-item"
              }
            >
              <button type="button" onClick={() => elegir(c.id)}>
                {c.nombre}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
