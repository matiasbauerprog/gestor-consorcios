const LABELS = {
  pendiente: "Pendiente",
  parcial: "Parcial",
  pagada: "Confirmada",
  vencida: "Vencida",
  pendiente_verificacion: "Pendiente de verificación",
  aprobado: "Aprobado",
  rechazado: "Rechazado",
};

const CLASES = {
  pendiente: "badge--neutro",
  parcial: "badge--warning",
  pagada: "badge--ok",
  vencida: "badge--alerta",
  pendiente_verificacion: "badge--warning",
  aprobado: "badge--ok",
  rechazado: "badge--alerta",
};

export default function BadgeEstado({ estado, vencida = false }) {
  const clave = vencida && estado === "pendiente" ? "vencida" : estado;
  return (
    <span className={`badge ${CLASES[clave] || "badge--neutro"}`}>
      {LABELS[clave] || estado}
    </span>
  );
}
