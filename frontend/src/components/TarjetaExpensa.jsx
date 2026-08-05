import { abrirPdfExpensa } from "../api/pdf";
import BadgeEstado from "./BadgeEstado";
import Tarjeta from "./Tarjeta";
import { formatFecha } from "../utils/fechas";
import { formatearInteres, formatearMonto } from "../utils/montos";

export default function TarjetaExpensa({
  expensa,
  esAdmin,
  depto,
  token,
  onEliminar = () => {},
  onVerComprobantes = () => {},
  mostrarBotonComprobantes = true,
}) {
  async function handleAbrirPdf() {
    try {
      await abrirPdfExpensa(expensa.id);
    } catch (e) {
      alert(`No se pudo abrir el PDF: ${e.message}`);
    }
  }

  return (
    <Tarjeta>
      <h3>
        {expensa.periodo} — {formatearMonto(expensa.monto_primer_vencimiento)}
      </h3>
      {esAdmin && (
        <p className="meta">
          {depto ? `${depto.codigo} — ${depto.descripcion}` : `Depto #${expensa.departamento_id}`}
        </p>
      )}
      <p className="meta">
        1° venc {formatFecha(expensa.fecha_primer_vencimiento)}: {formatearMonto(expensa.monto_primer_vencimiento)}
      </p>
      <p className="meta">
        2° venc {formatFecha(expensa.fecha_segundo_vencimiento)}: {formatearMonto(expensa.monto_segundo_vencimiento)} (+recargo)
      </p>
      {expensa.saldo_anterior > 0 && (
        <p className="meta">Saldo anterior: {formatearMonto(expensa.saldo_anterior)}</p>
      )}
      <p style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", flexWrap: "wrap" }}>
        <BadgeEstado estado={expensa.estado_calculado} />
        {expensa.monto_pendiente >= 0.5 && (
          <strong>Pendiente {formatearMonto(expensa.monto_pendiente)}</strong>
        )}
      </p>
      {expensa.monto_pendiente >= 0.5 && expensa.interes_acumulado > 0 && (
        <p className="meta">
          Incluye {formatearInteres(expensa.interes_acumulado)} de intereses por mora.
        </p>
      )}
      {(expensa.detalle?.length > 0 || esAdmin) && (
        <div className="tarjeta-acciones">
          {mostrarBotonComprobantes && (
            <button
              type="button"
              className="boton-secundario"
              onClick={() => onVerComprobantes(expensa)}
            >
              Ver comprobantes
            </button>
          )}
          <button
            type="button"
            className="boton-secundario"
            onClick={handleAbrirPdf}
          >
            📄 Ver PDF
          </button>
          {esAdmin && (
            <button
              type="button"
              className="boton-peligro"
              onClick={() => onEliminar(expensa)}
            >
              Eliminar
            </button>
          )}
        </div>
      )}
    </Tarjeta>
  );
}
