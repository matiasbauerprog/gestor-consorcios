const ESTILOS = {
  activo: { color: "#16a34a", texto: "Activo" },
  suspendido: { color: "#ca8a04", texto: "Suspendido" },
  vacante: { color: "#6b7280", texto: "Vacante" },
};

export default function EstadoBadge({ estado }) {
  const cfg = ESTILOS[estado] || ESTILOS.vacante;
  return (
    <span className="estado-badge">
      <span
        className="estado-punto"
        style={{ background: cfg.color }}
        aria-hidden="true"
      />
      {cfg.texto}
    </span>
  );
}
