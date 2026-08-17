import { describe, it, expect, beforeEach } from "vitest";
import { crearEstado } from "./estado";
import { escribir } from "./escrituras";

const DATOS = {
  _generado: "2026-08-17",
  "/comunicados": [{ id: 1, titulo: "Viejo", cuerpo: "..." }],
  "/peticiones": [{ id: 1, titulo: "Vieja", estado: "abierta" }],
  "/amenities": [{ id: 5, nombre: "SUM", precio_reserva: 25000 }],
  "/reservas": [],
};

let estado;
beforeEach(() => {
  estado = crearEstado(DATOS, new Date(2026, 7, 20));
});

describe("publicar un comunicado", () => {
  it("lo agrega y devuelve 201", () => {
    const r = escribir(estado, "POST", "/comunicados", { titulo: "Corte de agua", cuerpo: "Mañana" }, {});
    expect(r.status).toBe(201);
    expect(estado.leer("/comunicados")[0].titulo).toBe("Corte de agua");
  });

  it("le pone fecha de publicación", () => {
    const r = escribir(estado, "POST", "/comunicados", { titulo: "X", cuerpo: "Y" }, {});
    expect(r.data.fecha_publicacion).toBeTruthy();
  });

  it("sin título devuelve 400", () => {
    const r = escribir(estado, "POST", "/comunicados", { cuerpo: "sin titulo" }, {});
    expect(r.status).toBe(400);
  });
});

describe("crear una petición", () => {
  it("la agrega como abierta, a nombre del departamento de la sesión", () => {
    const r = escribir(
      estado, "POST", "/peticiones",
      { titulo: "Pérdida de agua", descripcion: "En el baño" },
      { departamento_id: 7 },
    );
    expect(r.status).toBe(201);
    expect(r.data.estado).toBe("abierta");
    expect(r.data.departamento_id).toBe(7);
  });
});

describe("reservar un amenity", () => {
  it("crea la reserva confirmada", () => {
    const r = escribir(
      estado, "POST", "/amenities/5/reservas",
      { inicio: "2026-09-10T14:00:00", fin: "2026-09-10T17:00:00" },
      { departamento_id: 3 },
    );
    expect(r.status).toBe(201);
    expect(r.data.estado).toBe("confirmada");
    expect(estado.leer("/reservas")).toHaveLength(1);
  });

  it("con fin anterior al inicio devuelve 400, como el backend", () => {
    const r = escribir(
      estado, "POST", "/amenities/5/reservas",
      { inicio: "2026-09-10T17:00:00", fin: "2026-09-10T14:00:00" },
      { departamento_id: 3 },
    );
    expect(r.status).toBe(400);
  });

  it("sobre un amenity que no existe devuelve 404", () => {
    const r = escribir(
      estado, "POST", "/amenities/999/reservas",
      { inicio: "2026-09-10T14:00:00", fin: "2026-09-10T17:00:00" },
      { departamento_id: 3 },
    );
    expect(r.status).toBe(404);
  });
});

describe("lo que no maneja", () => {
  it("devuelve null para que el servidor siga buscando", () => {
    expect(escribir(estado, "POST", "/algo-que-no-conoce", {}, {})).toBeNull();
  });
});

describe("circuito 1: presentar y aprobar un pago", () => {
  const CON_DEUDA = {
    _generado: "2026-08-17",
    "/departamentos": [{ id: 7, codigo: "UF-03C" }],
    "/comprobantes": [],
    "/expensas": [
      {
        id: 90,
        departamento_id: 7,
        periodo: "2026-07",
        fecha_primer_vencimiento: "2026-08-10",
        monto_primer_vencimiento: 1000,
        monto_pendiente: 1000,
        estado_calculado: "vencida",
      },
    ],
    "/departamentos/7/cuenta": {
      saldo_total: 1000,
      movimientos: [
        { id: 1, tipo: "expensa_emitida", monto: 1000, fecha: "2026-08-01", descripcion: "Expensa 2026-07" },
      ],
    },
    "/reportes/morosos": [{ departamento_id: 7, departamento_codigo: "UF-03C", saldo: 1000 }],
  };

  let e;
  beforeEach(() => {
    e = crearEstado(CON_DEUDA, new Date(2026, 7, 20));
  });

  const presentar = (monto) =>
    escribir(e, "POST", "/comprobantes", { monto, fecha_pago: "2026-08-18" }, { departamento_id: 7 });

  it("presentar deja el comprobante pendiente de aprobación", () => {
    const r = presentar(1000);
    expect(r.status).toBe(201);
    expect(r.data.estado).toBe("pendiente_verificacion");
    expect(e.leer("/comprobantes")).toHaveLength(1);
  });

  it("aprobarlo agrega el pago a la cuenta corriente", () => {
    const p = presentar(1000);
    const r = escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});

    expect(r.status).toBe(200);
    const cuenta = e.leer("/departamentos/7/cuenta");
    expect(cuenta.movimientos.some((m) => m.tipo === "pago_recibido")).toBe(true);
    expect(cuenta.saldo_total).toBe(0);
  });

  it("aprobarlo saca a la unidad de la lista de morosos", () => {
    const p = presentar(1000);
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    expect(e.leer("/reportes/morosos")).toHaveLength(0);
  });

  it("aprobarlo marca la expensa como pagada", () => {
    const p = presentar(1000);
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    const expensa = e.leer("/expensas")[0];
    expect(expensa.estado_calculado).toBe("pagada");
    expect(expensa.monto_pendiente).toBe(0);
  });

  it("un pago parcial deja la expensa parcial y la unidad en la lista", () => {
    const p = presentar(400);
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    expect(e.leer("/expensas")[0].estado_calculado).toBe("parcial");
    expect(e.leer("/reportes/morosos")).toHaveLength(1);
  });

  it("aprobar dos veces el mismo comprobante devuelve 409, como el backend", () => {
    const p = presentar(1000);
    escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    const segunda = escribir(e, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});
    expect(segunda.status).toBe(409);
  });

  it("presentar sin sesión de departamento devuelve 403", () => {
    const r = escribir(e, "POST", "/comprobantes", { monto: 100, fecha_pago: "2026-08-18" }, { departamento_id: null });
    expect(r.status).toBe(403);
  });
});

describe("circuito 2: cargar un gasto y cerrar el mes", () => {
  const ABIERTO = {
    _generado: "2026-08-17",
    "/departamentos": [
      { id: 1, codigo: "UF-01A" },
      { id: 2, codigo: "UF-01B" },
    ],
    "/departamentos/1/coeficientes": [{ clase_prorrateo_id: 10, porcentaje: 50 }],
    "/departamentos/2/coeficientes": [{ clase_prorrateo_id: 10, porcentaje: 50 }],
    "/departamentos/1/cuenta": { saldo_total: 0, movimientos: [] },
    "/departamentos/2/cuenta": { saldo_total: 0, movimientos: [] },
    "/clases-prorrateo": [{ id: 10, codigo: "A", nombre: "Expensas ordinarias", activa: true }],
    "/gastos": [],
    "/expensas": [],
    "/periodos": [{ periodo: "2026-07", total_expensado: 0, cantidad_expensas: 2 }],
  };

  let e;
  beforeEach(() => {
    e = crearEstado(ABIERTO, new Date(2026, 7, 20));
  });

  const cargarGasto = () =>
    escribir(e, "POST", "/gastos", {
      periodo: "2026-08",
      rubro: "abonos_y_servicios",
      concepto: "Ascensores",
      monto: 1000,
      clase_prorrateo_id: 10,
    }, {});

  const cerrar = () =>
    escribir(e, "POST", "/periodos/2026-08/cerrar", {
      fecha_primer_vencimiento: "2026-09-10",
      fecha_segundo_vencimiento: "2026-09-20",
    }, {});

  it("cargar un gasto lo agrega al período", () => {
    expect(cargarGasto().status).toBe(201);
    expect(e.leer("/gastos")).toHaveLength(1);
  });

  it("sin monto devuelve 400", () => {
    const r = escribir(e, "POST", "/gastos", { periodo: "2026-08", concepto: "X" }, {});
    expect(r.status).toBe(400);
  });

  it("el preview reparte el gasto entre las unidades", () => {
    cargarGasto();
    const r = escribir(e, "POST", "/periodos/2026-08/preview", {}, {});
    expect(r.status).toBe(200);
    expect(r.data.expensas).toHaveLength(2);
    expect(r.data.expensas[0].monto_primer_vencimiento).toBe(500);
    expect(r.data.total_expensado).toBe(1000);
  });

  it("cerrar emite una expensa por unidad", () => {
    cargarGasto();
    const r = cerrar();
    expect(r.status).toBe(201);
    const emitidas = e.leer("/expensas").filter((x) => x.periodo === "2026-08");
    expect(emitidas).toHaveLength(2);
    expect(emitidas[0].monto_primer_vencimiento).toBe(500);
  });

  it("cerrar deja el movimiento en la cuenta de cada unidad", () => {
    cargarGasto();
    cerrar();
    const cuenta = e.leer("/departamentos/1/cuenta");
    expect(cuenta.movimientos.some((m) => m.tipo === "expensa_emitida")).toBe(true);
    expect(cuenta.saldo_total).toBe(500);
  });

  it("cerrar dos veces el mismo período devuelve 409", () => {
    cargarGasto();
    cerrar();
    expect(cerrar().status).toBe(409);
  });

  it("cerrar un período sin gastos avisa en las validaciones", () => {
    const r = escribir(e, "POST", "/periodos/2026-08/preview", {}, {});
    expect(r.data.validaciones.some((v) => /no tiene gastos/i.test(v.mensaje))).toBe(true);
  });
});
