import { describe, it, expect } from "vitest";
import { formatearTiempoRelativo } from "./tiempoRelativo";

const AHORA = new Date("2026-08-12T15:00:00Z");

describe("formatearTiempoRelativo", () => {
  it("dice 'recién' para menos de un minuto", () => {
    expect(formatearTiempoRelativo("2026-08-12T14:59:30Z", AHORA)).toBe("recién");
  });

  it("cuenta minutos", () => {
    expect(formatearTiempoRelativo("2026-08-12T14:48:00Z", AHORA)).toBe("hace 12 min");
  });

  it("usa singular en la hora exacta", () => {
    expect(formatearTiempoRelativo("2026-08-12T14:00:00Z", AHORA)).toBe("hace 1 h");
  });

  it("cuenta horas", () => {
    expect(formatearTiempoRelativo("2026-08-12T12:00:00Z", AHORA)).toBe("hace 3 h");
  });

  it("dice 'ayer' entre 24 y 48 horas", () => {
    expect(formatearTiempoRelativo("2026-08-11T15:00:00Z", AHORA)).toBe("ayer");
  });

  it("cuenta días hasta la semana", () => {
    expect(formatearTiempoRelativo("2026-08-08T15:00:00Z", AHORA)).toBe("hace 4 días");
  });

  it("pasa a fecha corta después de una semana", () => {
    expect(formatearTiempoRelativo("2026-07-30T15:00:00Z", AHORA)).toBe("30/07/2026");
  });

  it("no rompe con una fecha inválida", () => {
    expect(formatearTiempoRelativo("no es una fecha", AHORA)).toBe("—");
  });
});
