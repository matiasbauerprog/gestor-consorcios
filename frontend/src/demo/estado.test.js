import { describe, it, expect } from "vitest";
import { crearEstado } from "./estado";

const DATASET = {
  _generado: "2026-08-17",
  "/departamentos": [{ id: 1, codigo: "UF-01A" }],
  "/expensas": [{ id: 9, periodo: "2026-07" }],
};

describe("crearEstado", () => {
  it("lee una ruta del dataset", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    expect(estado.leer("/departamentos")).toEqual([{ id: 1, codigo: "UF-01A" }]);
  });

  it("devuelve undefined para una ruta que no está", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    expect(estado.leer("/no-existe")).toBeUndefined();
  });

  it("aplica el desplazamiento de fechas al cargar", () => {
    const estado = crearEstado(DATASET, new Date(2026, 9, 5));
    expect(estado.leer("/expensas")[0].periodo).toBe("2026-09");
  });

  it("no comparte referencias con el dataset original", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    estado.leer("/departamentos")[0].codigo = "MODIFICADO";
    expect(DATASET["/departamentos"][0].codigo).toBe("UF-01A");
  });

  it("reiniciar vuelve al estado del arranque", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    estado.leer("/departamentos")[0].codigo = "MODIFICADO";
    estado.reiniciar();
    expect(estado.leer("/departamentos")[0].codigo).toBe("UF-01A");
  });
});
