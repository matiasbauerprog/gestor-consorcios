// Formateo de importes en pesos argentinos.
//
// Un solo helper para toda la app: antes convivían tres formatos distintos
// (`formatearMonto` duplicado en dos archivos y `$${x.toLocaleString("es-AR")}`
// suelto en otros dos), así que la misma cifra se veía diferente según la
// pantalla.

/** Importe común: sin centavos ($30.000). */
export function formatearMonto(v) {
  return Number(v).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

/**
 * Interés punitorio: CON centavos ($2,10).
 *
 * Es la única cifra que los tiene por naturaleza — sale de multiplicar un saldo
 * por una tasa diaria. Redondeada a cero decimales, $2,10 se mostraba "$2" y
 * $0,40 directamente "+$0 int.", que parece un error de la app.
 */
export function formatearInteres(v) {
  return Number(v).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
