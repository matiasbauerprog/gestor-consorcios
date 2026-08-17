import { describe, it, expect } from "vitest";
import { imputar, saldoDeMovimientos } from "./cuenta";
import DATASET from "./dataset.json";

// Los tipos y su signo son los del backend (`backend/models.py`):
// suman lo que el departamento debe, restan lo que pagó.
const EXPENSA = (id, venc, monto) => ({
  id,
  fecha_primer_vencimiento: venc,
  monto_primer_vencimiento: monto,
});

describe("saldoDeMovimientos", () => {
  it("suma los débitos y resta los créditos", () => {
    const saldo = saldoDeMovimientos([
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 400 },
      { tipo: "nota_debito", monto: 50 },
      { tipo: "nota_credito", monto: 25 },
    ]);
    expect(saldo).toBe(625);
  });

  it("un recargo y un interés suman como débito", () => {
    expect(
      saldoDeMovimientos([
        { tipo: "recargo", monto: 100 },
        { tipo: "interes_punitorio", monto: 50 },
      ]),
    ).toBe(150);
  });

  it("sin movimientos el saldo es cero", () => {
    expect(saldoDeMovimientos([])).toBe(0);
  });

  it("redondea a dos decimales", () => {
    expect(
      saldoDeMovimientos([
        { tipo: "expensa_emitida", monto: 0.1 },
        { tipo: "expensa_emitida", monto: 0.2 },
      ]),
    ).toBe(0.3);
  });
});

describe("imputar", () => {
  const EXPENSAS = [EXPENSA(1, "2026-06-10", 1000), EXPENSA(2, "2026-07-10", 1000)];

  it("cubre primero la expensa más vieja", () => {
    const r = imputar(EXPENSAS, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 1200 },
    ]);
    expect(r.porExpensa.get(1).pendiente).toBe(0);
    expect(r.porExpensa.get(1).estado).toBe("pagada");
    expect(r.porExpensa.get(2).pendiente).toBe(800);
    expect(r.porExpensa.get(2).estado).toBe("parcial");
  });

  it("sin pagos, todo queda pendiente", () => {
    const r = imputar(EXPENSAS, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
    ]);
    expect(r.saldo).toBe(2000);
    expect(r.porExpensa.get(1).pendiente).toBe(1000);
    expect(r.porExpensa.get(1).estado).toBe("pendiente");
  });

  it("un pago de más deja saldo a favor y todo pagado", () => {
    const r = imputar(EXPENSAS, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 2500 },
    ]);
    expect(r.saldo).toBe(-500);
    expect(r.porExpensa.get(2).pendiente).toBe(0);
  });

  it("imputa por vencimiento, no por el orden en que llegan", () => {
    const desordenadas = [EXPENSA(2, "2026-07-10", 1000), EXPENSA(1, "2026-06-10", 1000)];
    const r = imputar(desordenadas, [
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "expensa_emitida", monto: 1000 },
      { tipo: "pago_recibido", monto: 1000 },
    ]);
    expect(r.porExpensa.get(1).pendiente).toBe(0);
    expect(r.porExpensa.get(2).pendiente).toBe(1000);
  });

  it("el recargo asentado contra una expensa sube lo que hay que cubrir", () => {
    const r = imputar(
      [EXPENSA(1, "2026-06-10", 1000)],
      [
        { tipo: "expensa_emitida", monto: 1000 },
        { tipo: "recargo", monto: 100, expensa_id: 1 },
        { tipo: "pago_recibido", monto: 1000 },
      ],
    );
    expect(r.porExpensa.get(1).pendiente).toBe(100);
    expect(r.porExpensa.get(1).estado).toBe("parcial");
  });
});

describe("coincide con lo que calculó el backend", () => {
  const cuentas = Object.entries(DATASET).filter(([path]) => path.endsWith("/cuenta"));

  it("hay cuentas para verificar", () => {
    expect(cuentas.length).toBeGreaterThan(0);
  });

  it.each(cuentas)("%s: el saldo coincide", (_path, cuenta) => {
    expect(saldoDeMovimientos(cuenta.movimientos)).toBeCloseTo(cuenta.saldo_total, 2);
  });
});
