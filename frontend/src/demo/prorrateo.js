const dos = (n) => Math.round(n * 100) / 100;

/**
 * Convierte los gastos de un período en lo que le toca a cada unidad.
 *
 * Dos casos, los mismos que el backend (`backend/cierre.py`):
 * - gasto asignado a un departamento → va entero a esa unidad;
 * - gasto con clase de prorrateo → se reparte según el coeficiente de cada
 *   unidad en esa clase.
 *
 * Un gasto sin clase ni departamento se ignora: el backend lo marca como
 * huérfano en las validaciones del cierre y tampoco lo reparte. Repartirlo
 * "por las dudas" inventaría plata que nadie asignó.
 */
export function repartir(gastos, coeficientesPorDepto) {
  const porDepto = new Map();

  const agregar = (deptoId, linea) => {
    if (!porDepto.has(deptoId)) porDepto.set(deptoId, { total: 0, lineas: [] });
    const entrada = porDepto.get(deptoId);
    entrada.lineas.push(linea);
    entrada.total = dos(entrada.total + linea.monto);
  };

  for (const gasto of gastos) {
    if (gasto.departamento_id != null) {
      agregar(gasto.departamento_id, {
        rubro: gasto.rubro,
        concepto: gasto.concepto,
        clase_prorrateo_id: null,
        departamento_origen_id: gasto.departamento_id,
        monto: dos(gasto.monto),
      });
      continue;
    }
    if (gasto.clase_prorrateo_id == null) continue;

    for (const [deptoId, coefs] of coeficientesPorDepto.entries()) {
      const coef = coefs.find((c) => c.clase_prorrateo_id === gasto.clase_prorrateo_id);
      if (!coef) continue;
      const monto = dos((gasto.monto * coef.porcentaje) / 100);
      if (monto <= 0) continue;
      agregar(deptoId, {
        rubro: gasto.rubro,
        concepto: gasto.concepto,
        clase_prorrateo_id: gasto.clase_prorrateo_id,
        departamento_origen_id: null,
        monto,
      });
    }
  }

  return porDepto;
}
