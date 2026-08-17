/**
 * Tipos de movimiento que aumentan lo que el departamento debe. El resto
 * (pagos y notas de crédito) lo disminuye. Son los mismos de
 * `backend/models.py`: si allá se agrega uno, acá hay que agregarlo también,
 * y el test que compara contra los saldos del dataset lo va a detectar.
 */
const DEBITOS = new Set([
  "expensa_emitida",
  "nota_debito",
  "interes_punitorio",
  "recargo",
]);

const dos = (n) => Math.round(n * 100) / 100;

/** Saldo de una unidad: lo que debe menos lo que pagó. */
export function saldoDeMovimientos(movimientos) {
  const total = movimientos.reduce(
    (acc, m) => acc + (DEBITOS.has(m.tipo) ? m.monto : -m.monto),
    0,
  );
  const redondeado = dos(total);
  // Un residuo de centésimos por acumulación no es una deuda.
  return Math.abs(redondeado) < 0.005 ? 0 : redondeado;
}

/**
 * Reparte el crédito disponible sobre las expensas, de la más vieja a la más
 * nueva, y devuelve el saldo y el estado de cada una.
 *
 * El estado no se guarda en ningún lado: se deduce de los movimientos cada
 * vez. Por eso no puede desincronizarse — es la misma decisión que tomó el
 * backend en `cuenta_corriente.py`.
 *
 * El techo de cada expensa es su primer vencimiento más los recargos que se
 * asentaron contra ella, no el importe original.
 */
export function imputar(expensas, movimientos) {
  const recargos = new Map();
  for (const m of movimientos) {
    if (m.tipo === "recargo" && m.expensa_id != null) {
      recargos.set(m.expensa_id, dos((recargos.get(m.expensa_id) ?? 0) + m.monto));
    }
  }

  const ordenadas = [...expensas].sort(
    (a, b) =>
      a.fecha_primer_vencimiento.localeCompare(b.fecha_primer_vencimiento) || a.id - b.id,
  );

  let credito = movimientos.reduce(
    (acc, m) => acc + (DEBITOS.has(m.tipo) ? 0 : m.monto),
    0,
  );

  const porExpensa = new Map();
  for (const e of ordenadas) {
    const techo = dos(e.monto_primer_vencimiento + (recargos.get(e.id) ?? 0));
    const cubierto = Math.min(credito, techo);
    credito = dos(credito - cubierto);
    const pendiente = dos(techo - cubierto);
    porExpensa.set(e.id, {
      pagado: dos(cubierto),
      pendiente,
      estado: pendiente <= 0.005 ? "pagada" : cubierto > 0.005 ? "parcial" : "pendiente",
    });
  }

  return { saldo: saldoDeMovimientos(movimientos), porExpensa };
}
