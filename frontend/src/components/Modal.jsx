import { useEffect } from "react";

/**
 * `ancho`: para el contenido que no entra en la caja normal — una tabla de
 * varias columnas, típicamente. Sin esto la tabla desborda y las últimas
 * columnas quedan detrás de una barra de scroll horizontal, con los botones
 * de acción cortados por el borde del modal. En mobile no cambia nada: ahí
 * la hoja siempre ocupa el ancho de la pantalla.
 */
export default function Modal({ titulo, onClose, children, ancho = false }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function onBackdropClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div className="modal-backdrop" onClick={onBackdropClick}>
      <section
        className={ancho ? "modal modal-ancho" : "modal"}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
      >
        <header className="modal-header">
          <h3>{titulo}</h3>
          <button
            type="button"
            className="modal-cerrar"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ×
          </button>
        </header>
        <div className="modal-cuerpo">{children}</div>
      </section>
    </div>
  );
}
