import { abrirPdfExpensa } from "../api/pdf";
import BadgeEstado from "./BadgeEstado";
import Tarjeta from "./Tarjeta";

function formatearMonto(v) {
  return Number(v).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

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
      await abrirPdfExpensa(expensa.id, token);
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
        1° venc {expensa.fecha_primer_vencimiento}: {formatearMonto(expensa.monto_primer_vencimiento)}
      </p>
      <p className="meta">
        2° venc {expensa.fecha_segundo_vencimiento}: {formatearMonto(expensa.monto_segundo_vencimiento)} (+recargo)
      </p>
      {expensa.saldo_anterior > 0 && (
        <p className="meta">Saldo anterior: {formatearMonto(expensa.saldo_anterior)}</p>
      )}
      <p>
        <BadgeEstado estado={expensa.estado_calculado} />
        {expensa.monto_pendiente > 0 && (
          <span className="meta" style={{ marginLeft: "0.5rem" }}>
            Pendiente {formatearMonto(expensa.monto_pendiente)}
          </span>
        )}
      </p>
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
