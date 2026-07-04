export default function TabsPanel({ items, activo, onCambio, ariaLabel }) {
  return (
    <div className="tabs-panel" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => {
        const seleccionado = item.valor === activo;
        return (
          <button
            key={item.valor}
            type="button"
            role="tab"
            aria-selected={seleccionado}
            className={seleccionado ? "tab-panel activo" : "tab-panel"}
            onClick={() => onCambio(item.valor)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
