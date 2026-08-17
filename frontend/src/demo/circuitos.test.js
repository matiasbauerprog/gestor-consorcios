import { describe, it, expect, beforeEach } from "vitest";
import DATASET from "./dataset.json";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

let estado;
beforeEach(() => {
  estado = crearEstado(DATASET, new Date());
});

/** Entra con un perfil y devuelve su sesión, como hace la aplicación. */
function entrar(rol) {
  const r = responder(estado, "POST", "/auth/demo-login", { rol });
  return { departamento_id: r.data.user.departamento_id };
}

/** El mes siguiente al último período cerrado del dataset. */
function mesSiguienteAlUltimoCerrado() {
  const periodos = responder(estado, "GET", "/periodos")
    .data.map((p) => p.periodo)
    .sort();
  const [anio, mes] = periodos[periodos.length - 1].split("-").map(Number);
  const total = anio * 12 + (mes - 1) + 1;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

describe("circuito 1: la plata que entra", () => {
  it("el moroso paga, administración aprueba, y la deuda baja a cero", () => {
    const moroso = entrar("propietario_moroso");
    const antes = responder(estado, "GET", "/movimientos/mi-cuenta", null, moroso).data.saldo_total;
    expect(antes).toBeGreaterThan(0);

    const presentado = responder(
      estado, "POST", "/comprobantes",
      { monto: antes, fecha_pago: "2026-08-18" }, moroso,
    );
    expect(presentado.status).toBe(201);
    expect(presentado.data.estado).toBe("pendiente_verificacion");

    const aprobado = responder(
      estado, "PATCH", `/comprobantes/${presentado.data.id}`,
      { estado: "aprobado" }, { departamento_id: null },
    );
    expect(aprobado.status).toBe(200);

    const despues = responder(estado, "GET", "/movimientos/mi-cuenta", null, moroso).data.saldo_total;
    expect(despues).toBeLessThan(antes);
    expect(despues).toBe(0);
  });

  it("y la unidad desaparece de la lista de morosos", () => {
    const moroso = entrar("propietario_moroso");
    const saldo = responder(estado, "GET", "/movimientos/mi-cuenta", null, moroso).data.saldo_total;
    const p = responder(estado, "POST", "/comprobantes", { monto: saldo, fecha_pago: "2026-08-18" }, moroso);
    responder(estado, "PATCH", `/comprobantes/${p.data.id}`, { estado: "aprobado" }, {});

    const morosos = responder(estado, "GET", "/reportes/morosos").data;
    expect(morosos.some((m) => m.departamento_id === moroso.departamento_id)).toBe(false);
  });

  it("el comprobante presentado aparece en la bandeja de administración", () => {
    const moroso = entrar("propietario_moroso");
    const antes = responder(estado, "GET", "/comprobantes").data.length;
    responder(estado, "POST", "/comprobantes", { monto: 1000, fecha_pago: "2026-08-18" }, moroso);
    const despues = responder(estado, "GET", "/comprobantes").data;
    expect(despues).toHaveLength(antes + 1);
    expect(despues[0].estado).toBe("pendiente_verificacion");
  });
});

describe("circuito 2: la plata que sale", () => {
  it("cargar un gasto y cerrar el mes emite una expensa por unidad", () => {
    const mesAbierto = mesSiguienteAlUltimoCerrado();
    const unidades = responder(estado, "GET", "/departamentos").data.length;
    const clase = responder(estado, "GET", "/clases-prorrateo").data[0];

    const gasto = responder(estado, "POST", "/gastos", {
      periodo: mesAbierto,
      rubro: "abonos_y_servicios",
      concepto: "Service de bombas",
      monto: 480000,
      clase_prorrateo_id: clase.id,
    });
    expect(gasto.status).toBe(201);

    const preview = responder(estado, "POST", `/periodos/${mesAbierto}/preview`, {});
    expect(preview.status).toBe(200);
    expect(preview.data.expensas).toHaveLength(unidades);

    const cierre = responder(estado, "POST", `/periodos/${mesAbierto}/cerrar`, {
      fecha_primer_vencimiento: "2026-09-10",
      fecha_segundo_vencimiento: "2026-09-20",
    });
    expect(cierre.status).toBe(201);
    expect(cierre.data.cantidad_expensas).toBe(unidades);

    const emitidas = responder(estado, "GET", `/expensas?periodo=${mesAbierto}`).data;
    expect(emitidas).toHaveLength(unidades);

    // Los gastos del período se repartieron enteros: la suma de las expensas
    // los cubre. Se compara contra la suma real del período y no contra los
    // 480.000 recién cargados, porque el mes abierto no arranca vacío — el
    // dataset trae el gasto del trabajo que se terminó y todavía no se cerró.
    const gastosDelMes = responder(estado, "GET", `/gastos?periodo=${mesAbierto}`).data;
    const aRepartir = gastosDelMes.reduce((a, g) => a + g.monto, 0);
    expect(aRepartir).toBeGreaterThan(480000);

    const total = emitidas.reduce((a, e) => a + e.monto_primer_vencimiento, 0);
    expect(total).toBeCloseTo(aRepartir, 0);
  });

  it("el preview avisa que la clase extraordinaria no tiene gastos", () => {
    const mesAbierto = mesSiguienteAlUltimoCerrado();
    const preview = responder(estado, "POST", `/periodos/${mesAbierto}/preview`, {});
    expect(preview.data.validaciones.length).toBeGreaterThan(0);
  });

  it("el gasto cargado aparece en la lista del período", () => {
    const mesAbierto = mesSiguienteAlUltimoCerrado();
    responder(estado, "POST", "/gastos", {
      periodo: mesAbierto, rubro: "x", concepto: "Service de bombas", monto: 480000,
      clase_prorrateo_id: responder(estado, "GET", "/clases-prorrateo").data[0].id,
    });
    const delMes = responder(estado, "GET", `/gastos?periodo=${mesAbierto}`).data;
    expect(delMes.some((g) => g.concepto === "Service de bombas")).toBe(true);
  });
});
