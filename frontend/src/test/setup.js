import "@testing-library/jest-dom/vitest";
import { beforeEach, vi } from "vitest";

/** Ancho simulado del viewport. Los tests lo cambian con `setAnchoViewport`. */
let anchoActual = 1440;

export function setAnchoViewport(px) {
  anchoActual = px;
}

/** Resuelve `(min-width: Npx)` y `(max-width: Npx)` contra `anchoActual`.
 *  Alcanza para `useMediaQuery`, que es el único consumidor en la app. */
function evaluar(query) {
  const min = query.match(/min-width:\s*(\d+)px/);
  if (min) return anchoActual >= Number(min[1]);
  const max = query.match(/max-width:\s*(\d+)px/);
  if (max) return anchoActual <= Number(max[1]);
  return false;
}

/** Ancho simulado del contenedor que mide `ResizeObserver` (TablaResponsive).
 *  Los tests lo cambian con `setAnchoContenedor`, SIEMPRE antes de montar: a
 *  diferencia de un ResizeObserver real, este stub no vuelve a notificar
 *  después de `observe()`, así que un cambio posterior al montaje no llega. */
let anchoContenedorActual = 1440;

export function setAnchoContenedor(px) {
  anchoContenedorActual = px;
}

beforeEach(() => {
  anchoActual = 1440;
  anchoContenedorActual = 1440;
});

vi.stubGlobal("matchMedia", (query) => ({
  matches: evaluar(query),
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
}));

/** jsdom no implementa ResizeObserver. El stub entrega el ancho configurado
 *  por `setAnchoContenedor` apenas se llama a `observe()`, para que un valor
 *  seteado antes del montaje quede reflejado en el primer render con
 *  medición (el componente arranca con `null` y lo actualiza al recibir la
 *  primera notificación). */
class ResizeObserverStub {
  constructor(callback) {
    this.callback = callback;
  }

  observe(target) {
    this.callback([{ target, contentRect: { width: anchoContenedorActual } }]);
  }

  unobserve() {}

  disconnect() {}
}

vi.stubGlobal("ResizeObserver", ResizeObserverStub);
