import { describe, it, expect } from "vitest";
import { actividadReciente, proximosVencimientos } from "./tablero";

const HOY = new Date("2026-08-17T12:00:00");

describe("actividadReciente", () => {
  it("deja afuera lo que todavía no pasó", () => {
    // El caso real: las reservas del SUM son de septiembre, tienen las fechas
    // más altas de todas y copaban las seis posiciones de la lista.
    const items = [
      { fecha: "2026-09-26T08:00:00", titulo: "SUM" },
      { fecha: "2026-08-14T10:00:00", titulo: "Pago UF-01A" },
    ];
    const r = actividadReciente(items, HOY);
    expect(r.map((x) => x.titulo)).toEqual(["Pago UF-01A"]);
  });

  it("ordena de lo más nuevo a lo más viejo", () => {
    const items = [
      { fecha: "2026-06-01", titulo: "viejo" },
      { fecha: "2026-08-10", titulo: "nuevo" },
      { fecha: "2026-07-15", titulo: "medio" },
    ];
    expect(actividadReciente(items, HOY).map((x) => x.titulo)).toEqual([
      "nuevo", "medio", "viejo",
    ]);
  });

  it("corta en la cantidad pedida", () => {
    const items = Array.from({ length: 20 }, (_, i) => ({
      fecha: `2026-08-${String(i + 1).padStart(2, "0")}`,
      titulo: `x${i}`,
    }));
    expect(actividadReciente(items, HOY, 6)).toHaveLength(6);
  });

  it("ignora los que no tienen fecha en vez de romper el orden", () => {
    const items = [{ fecha: null, titulo: "sin fecha" }, { fecha: "2026-08-01", titulo: "ok" }];
    expect(actividadReciente(items, HOY).map((x) => x.titulo)).toEqual(["ok"]);
  });
});

describe("proximosVencimientos", () => {
  it("no llama próximo a un vencimiento que ya operó", () => {
    // Con los dos vencimientos de expensas: el primero venció el 10 y el
    // segundo vence el 20. El tablero mostraba los dos bajo "próximos".
    const items = [
      { fecha: "2026-08-10", titulo: "1er vto." },
      { fecha: "2026-08-20", titulo: "2do vto." },
    ];
    expect(proximosVencimientos(items, HOY).map((x) => x.titulo)).toEqual(["2do vto."]);
  });

  it("el que vence hoy sigue siendo próximo hasta que termine el día", () => {
    const items = [{ fecha: "2026-08-17", titulo: "vence hoy" }];
    expect(proximosVencimientos(items, HOY)).toHaveLength(1);
  });

  it("ordena de lo más cercano a lo más lejano", () => {
    const items = [
      { fecha: "2026-10-01", titulo: "lejos" },
      { fecha: "2026-08-20", titulo: "cerca" },
    ];
    expect(proximosVencimientos(items, HOY).map((x) => x.titulo)).toEqual(["cerca", "lejos"]);
  });

  it("si ya vencieron todos, la lista queda vacía", () => {
    const items = [{ fecha: "2026-08-01", titulo: "pasado" }];
    expect(proximosVencimientos(items, HOY)).toEqual([]);
  });
});
