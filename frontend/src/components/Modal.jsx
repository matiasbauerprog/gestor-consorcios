import { useEffect } from "react";

export default function Modal({ titulo, onClose, children }) {
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
      <section className="modal" role="dialog" aria-modal="true" aria-label={titulo}>
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
