import { describe, it, expect } from "vitest";
import { correrDataset, correrFecha, mesesDeDesfase } from "./fechas";
import DATASET_REAL from "./dataset.json";

describe("mesesDeDesfase", () => {
  it("cuenta meses enteros entre la generación y hoy", () => {
    expect(mesesDeDesfase("2026-08-17", new Date(2026, 9, 5))).toBe(2);
  });

  it("cruza el año", () => {
    expect(mesesDeDesfase("2026-11-10", new Date(2027, 0, 3))).toBe(2);
  });

  it("es cero el mismo mes en que se generó", () => {
    expect(mesesDeDesfase("2026-08-17", new Date(2026, 7, 30))).toBe(0);
  });

  it("nunca va para atrás", () => {
    // Un reloj atrasado no debe mandar la demo al pasado: un dataset con
    // fechas hacia adelante se vería peor que uno simplemente viejo.
    expect(mesesDeDesfase("2026-08-17", new Date(2026, 5, 1))).toBe(0);
  });
});

describe("correrFecha", () => {
  it("corre un período YYYY-MM", () => {
    expect(correrFecha("2026-07", 2)).toBe("2026-09");
  });

  it("corre un período cruzando el año", () => {
    expect(correrFecha("2026-11", 3)).toBe("2027-02");
  });

  it("corre una fecha simple", () => {
    expect(correrFecha("2026-08-10", 2)).toBe("2026-10-10");
  });

  it("conserva la hora", () => {
    expect(correrFecha("2026-09-20T03:00:00", 1)).toBe("2026-10-20T03:00:00");
  });

  it("recorta al último día cuando el mes destino es más corto", () => {
    // 31 de enero + 1 mes no es el 31 de febrero.
    expect(correrFecha("2026-01-31", 1)).toBe("2026-02-28");
  });

  it("deja intacto lo que no es una fecha", () => {
    expect(correrFecha("UF-03C", 2)).toBe("UF-03C");
    expect(correrFecha("", 2)).toBe("");
    expect(correrFecha("Expensa 2026-07", 2)).toBe("Expensa 2026-07");
  });

  it("con desfase cero devuelve el mismo valor", () => {
    expect(correrFecha("2026-07", 0)).toBe("2026-07");
  });
});

describe("correrDataset", () => {
  const DATASET = {
    _generado: "2026-08-17",
    "/expensas": [
      { id: 1, periodo: "2026-07", fecha_primer_vencimiento: "2026-08-10", monto: 1000 },
    ],
    "/reservas": [{ id: 5, inicio: "2026-09-20T03:00:00" }],
  };

  it("corre las fechas de todas las rutas", () => {
    const corrido = correrDataset(DATASET, new Date(2026, 9, 5));
    expect(corrido["/expensas"][0].periodo).toBe("2026-09");
    expect(corrido["/expensas"][0].fecha_primer_vencimiento).toBe("2026-10-10");
    expect(corrido["/reservas"][0].inicio).toBe("2026-11-20T03:00:00");
  });

  it("no toca los importes ni los identificadores", () => {
    const corrido = correrDataset(DATASET, new Date(2026, 9, 5));
    expect(corrido["/expensas"][0].monto).toBe(1000);
    expect(corrido["/expensas"][0].id).toBe(1);
    expect(corrido["/reservas"][0].id).toBe(5);
  });

  it("no modifica el dataset original", () => {
    correrDataset(DATASET, new Date(2026, 9, 5));
    expect(DATASET["/expensas"][0].periodo).toBe("2026-07");
  });

  it("con desfase cero devuelve los mismos valores", () => {
    const corrido = correrDataset(DATASET, new Date(2026, 7, 30));
    expect(corrido["/expensas"][0].periodo).toBe("2026-07");
  });
});

describe("sobre el dataset real", () => {
  it("el último período queda siempre en el mes pasado, por lejos que se mire", () => {
    const hoy = new Date(2027, 2, 15); // marzo de 2027, siete meses después
    const corrido = correrDataset(DATASET_REAL, hoy);
    const periodos = [...new Set(corrido["/expensas"].map((e) => e.periodo))].sort();
    expect(periodos[periodos.length - 1]).toBe("2027-02");
  });

  it("conserva la cantidad de expensas y sus importes", () => {
    const corrido = correrDataset(DATASET_REAL, new Date(2027, 2, 15));
    expect(corrido["/expensas"]).toHaveLength(DATASET_REAL["/expensas"].length);
    expect(corrido["/expensas"][0].monto_primer_vencimiento).toBe(
      DATASET_REAL["/expensas"][0].monto_primer_vencimiento,
    );
  });
});
