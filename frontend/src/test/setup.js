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

beforeEach(() => {
  anchoActual = 1440;
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
