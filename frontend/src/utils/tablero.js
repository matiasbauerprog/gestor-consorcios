import { parseFecha } from "./fechas";

/**
 * Las dos listas por fecha del tablero de inicio.
 *
 * Las dos tenían el mismo defecto: ordenaban por fecha pero no miraban si la
 * fecha ya pasó. "Actividad reciente" se llenaba de reservas de amenities del
 * mes que viene —son las fechas más altas— y tapaba los movimientos de caja y
 * las peticiones, que es lo que de verdad pasó. Y "Próximos vencimientos"
 * listaba el primer vencimiento aunque hubiera vencido la semana anterior.
 *
 * No es un problema de datos de demostración: le pasa a cualquier consorcio
 * con una reserva a futuro o con un vencimiento ya cumplido.
 *
 * Las fechas se leen con `parseFecha` y no con `new Date(...)`: las que vienen
 * sin hora ("2026-08-17") se parsean como UTC y en Argentina caerían el día
 * anterior, que acá cambiaría de lado a lo que vence hoy.
 */

function tiempoDe(item) {
  const d = parseFecha(item?.fecha);
  return d ? d.getTime() : null;
}

/** Lo que ya ocurrió, de lo más nuevo a lo más viejo. */
export function actividadReciente(items, ahora, cantidad = 6) {
  const corte = ahora.getTime();
  return items
    .filter((a) => {
      const t = tiempoDe(a);
      return t !== null && t <= corte;
    })
    .sort((a, b) => tiempoDe(b) - tiempoDe(a))
    .slice(0, cantidad);
}

/**
 * Lo que todavía no ocurrió, de lo más cercano a lo más lejano.
 *
 * El corte es el comienzo del día: un vencimiento que opera hoy sigue siendo
 * próximo hasta que termine la jornada, no deja de serlo a las 00:01.
 */
export function proximosVencimientos(items, ahora, cantidad = 4) {
  const inicioDelDia = new Date(
    ahora.getFullYear(), ahora.getMonth(), ahora.getDate(),
  ).getTime();
  return items
    .filter((v) => {
      const t = tiempoDe(v);
      return t !== null && t >= inicioDelDia;
    })
    .sort((a, b) => tiempoDe(a) - tiempoDe(b))
    .slice(0, cantidad);
}
