import { describe, it, expect } from "vitest";
import { repartir } from "./prorrateo";
import DATASET from "./dataset.json";

const COEFS = new Map([
  [1, [{ clase_prorrateo_id: 10, porcentaje: 60 }]],
  [2, [{ clase_prorrateo_id: 10, porcentaje: 40 }]],
]);

const GASTO_CLASE = {
  id: 1,
  concepto: "Ascensores",
  rubro: "abonos_y_servicios",
  monto: 1000,
  clase_prorrateo_id: 10,
  departamento_id: null,
};

describe("repartir", () => {
  it("reparte un gasto de clase según el coeficiente de cada unidad", () => {
    const r = repartir([GASTO_CLASE], COEFS);
    expect(r.get(1).total).toBe(600);
    expect(r.get(2).total).toBe(400);
  });

  it("un gasto asignado a una unidad va entero a esa unidad", () => {
    const r = repartir(
      [{ id: 2, concepto: "Reparación privada", rubro: "trabajos_reparaciones_unidades", monto: 500, clase_prorrateo_id: null, departamento_id: 2 }],
      COEFS,
    );
    expect(r.get(2).total).toBe(500);
    expect(r.get(1)?.total ?? 0).toBe(0);
  });

  it("acumula varios gastos sobre la misma unidad", () => {
    const r = repartir(
      [GASTO_CLASE, { ...GASTO_CLASE, id: 2, concepto: "B", monto: 500 }],
      COEFS,
    );
    expect(r.get(1).total).toBe(900); // 600 + 300
  });

  it("deja una línea de detalle por gasto, con su concepto", () => {
    const r = repartir([GASTO_CLASE], COEFS);
    expect(r.get(1).lineas).toHaveLength(1);
    expect(r.get(1).lineas[0].concepto).toBe("Ascensores");
    expect(r.get(1).lineas[0].monto).toBe(600);
  });

  it("ignora un gasto sin clase ni departamento en vez de repartirlo mal", () => {
    const r = repartir(
      [{ id: 3, concepto: "Huérfano", rubro: "x", monto: 999, clase_prorrateo_id: null, departamento_id: null }],
      COEFS,
    );
    expect(r.get(1)?.total ?? 0).toBe(0);
    expect(r.get(2)?.total ?? 0).toBe(0);
  });

  it("redondea cada línea a dos decimales, como el backend", () => {
    const r = repartir(
      [{ ...GASTO_CLASE, monto: 100 }],
      new Map([[1, [{ clase_prorrateo_id: 10, porcentaje: 33.3333 }]]]),
    );
    expect(r.get(1).total).toBe(33.33);
  });

  it("sin gastos no reparte nada", () => {
    expect(repartir([], COEFS).size).toBe(0);
  });
});

describe("coincide con lo que calculó el backend", () => {
  it("reparte el último período cerrado como lo hizo el backend", () => {
    const periodo = DATASET["/periodos"][0].periodo;
    const gastos = DATASET["/gastos"].filter((g) => g.periodo === periodo);
    const coefs = new Map(
      DATASET["/departamentos"].map((d) => [
        d.id,
        DATASET[`/departamentos/${d.id}/coeficientes`] ?? [],
      ]),
    );

    const repartido = repartir(gastos, coefs);
    const expensas = DATASET["/expensas"].filter((e) => e.periodo === periodo);

    expect(expensas.length).toBeGreaterThan(0);
    for (const expensa of expensas) {
      const mio = repartido.get(expensa.departamento_id);
      expect(mio, `sin reparto para el depto ${expensa.departamento_id}`).toBeDefined();
      // `monto_primer_vencimiento` es exactamente lo que sale del reparto del
      // período: `saldo_anterior` viaja aparte, como información, y no está
      // sumado adentro. Verificado sobre el dataset: para el depto 18 del
      // último período, el monto (212.443,66) es igual a la suma de su
      // detalle, con el saldo anterior (1.237.959,13) por fuera.
      expect(mio.total).toBeCloseTo(expensa.monto_primer_vencimiento, 2);
    }
  });

  it("el detalle de cada expensa suma su importe del período", () => {
    const periodo = DATASET["/periodos"][0].periodo;
    const expensas = DATASET["/expensas"].filter((e) => e.periodo === periodo);
    for (const expensa of expensas) {
      const suma = (expensa.detalle ?? []).reduce((a, l) => a + l.monto, 0);
      expect(suma).toBeCloseTo(expensa.monto_primer_vencimiento, 2);
    }
  });
});
