import Modal from "./Modal";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

const NOMBRES_RUBRO = {
  sueldos_y_cargas_sociales: "Sueldos y cargas sociales",
  abonos_y_servicios: "Abonos y servicios",
  servicios: "Servicios",
  servicios_publicos: "Servicios públicos",
  mantenimiento_partes_comunes: "Mantenimiento partes comunes",
  trabajos_reparaciones_unidades: "Trabajos / reparaciones en unidades",
  reparaciones: "Reparaciones",
  seguros: "Seguros",
  administracion: "Administración",
  otros: "Otros",
};

export default function ModalDesgloseExpensa({ expensa, onClose }) {
  const detalle = expensa.detalle || [];
  const grupos = {};
  for (const d of detalle) {
    grupos[d.rubro] = grupos[d.rubro] || [];
    grupos[d.rubro].push(d);
  }
  const total = detalle.reduce((acc, d) => acc + d.monto, 0);

  return (
    <Modal titulo={`Desglose Expensa ${expensa.periodo}`} onClose={onClose}>
      {detalle.length === 0 && (
        <p>Esta expensa no tiene detalle (creación individual).</p>
      )}
      {Object.entries(grupos).map(([rubro, lineas]) => {
        const sub = lineas.reduce((acc, d) => acc + d.monto, 0);
        return (
          <div key={rubro}>
            <h4>
              {NOMBRES_RUBRO[rubro] || rubro} — {formatMoney(sub)}
            </h4>
            <ul>
              {lineas.map((d, i) => (
                <li key={i}>
                  {d.departamento_origen_id ? "Particular" : `Clase ${d.clase_prorrateo_id}`}
                  {" · "}
                  {d.concepto}
                  {" · "}
                  {formatMoney(d.monto)}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <hr />
      <p>
        <strong>Total: {formatMoney(total)}</strong>
      </p>
    </Modal>
  );
}
