import { useEffect, useRef, useState } from "react";

/**
 * Menú "⋯" para la columna de acciones de una tabla. En una fila, tres botones
 * visibles se comen 200-250px de ancho — una columna de datos entera — y dejan
 * Eliminar a un click de Editar.
 *
 * El estilo ya vive en index.css como `.menu-kebab*`.
 */
export default function MenuAcciones({ acciones, etiqueta = "Acciones" }) {
  const [abierto, setAbierto] = useState(false);
  const contenedorRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;

    function alClickearAfuera(e) {
      if (!contenedorRef.current?.contains(e.target)) setAbierto(false);
    }
    function alApretarEscape(e) {
      if (e.key !== "Escape") return;
      setAbierto(false);
      // Sin esto el foco queda huérfano en el body y el teclado pierde el hilo.
      triggerRef.current?.focus();
    }

    document.addEventListener("mousedown", alClickearAfuera);
    document.addEventListener("keydown", alApretarEscape);
    return () => {
      document.removeEventListener("mousedown", alClickearAfuera);
      document.removeEventListener("keydown", alApretarEscape);
    };
  }, [abierto]);

  function ejecutar(accion) {
    setAbierto(false);
    accion.onSelect();
  }

  return (
    <div className="menu-kebab" ref={contenedorRef}>
      <button
        type="button"
        ref={triggerRef}
        className="menu-kebab-trigger"
        aria-label={etiqueta}
        aria-haspopup="menu"
        aria-expanded={abierto}
        onClick={() => setAbierto((prev) => !prev)}
      >
        ⋯
      </button>

      {abierto && (
        <ul className="menu-kebab-lista" role="menu">
          {acciones.map((a) => (
            <li key={a.label} role="none">
              <button
                type="button"
                role="menuitem"
                className={`menu-kebab-item${a.peligro ? " peligro" : ""}`}
                onClick={() => ejecutar(a)}
              >
                {a.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
