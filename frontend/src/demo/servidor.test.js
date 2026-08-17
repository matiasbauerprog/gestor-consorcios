import { describe, it, expect, beforeEach } from "vitest";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

const DATASET = {
  _generado: "2026-08-17",
  "/departamentos": [
    { id: 1, codigo: "UF-01A" },
    { id: 2, codigo: "UF-03C" },
  ],
  "/expensas": [
    { id: 9, departamento_id: 1, periodo: "2026-07", estado_calculado: "pagada" },
    { id: 10, departamento_id: 2, periodo: "2026-07", estado_calculado: "vencida" },
    { id: 11, departamento_id: 1, periodo: "2026-06", estado_calculado: "pagada" },
  ],
  "/departamentos/1/cuenta": { saldo_total: 0, movimientos: [] },
  "/departamentos/2/cuenta": { saldo_total: 1500, movimientos: [{ id: 1 }] },
  "/me/consorcios": [{ id: 1, nombre: "Edificio Libertador" }],
};

let estado;
beforeEach(() => {
  estado = crearEstado(DATASET, new Date(2026, 7, 20));
});

describe("responder", () => {
  it("devuelve una lista con la forma de apiFetch", () => {
    const r = responder(estado, "GET", "/departamentos");
    expect(r.ok).toBe(true);
    expect(r.status).toBe(200);
    expect(r.data).toHaveLength(2);
  });

  it("resuelve una ruta con identificador en el medio", () => {
    const r = responder(estado, "GET", "/departamentos/1/cuenta");
    expect(r.status).toBe(200);
    expect(r.data.saldo_total).toBe(0);
  });

  it("filtra por período", () => {
    const r = responder(estado, "GET", "/expensas?periodo=2026-07");
    expect(r.data).toHaveLength(2);
  });

  it("filtra por departamento", () => {
    const r = responder(estado, "GET", "/expensas?departamento_id=1");
    expect(r.data).toHaveLength(2);
  });

  it("combina filtros", () => {
    const r = responder(estado, "GET", "/expensas?periodo=2026-07&departamento_id=1");
    expect(r.data).toHaveLength(1);
    expect(r.data[0].id).toBe(9);
  });

  it("ignora un filtro que no conoce, en vez de devolver vacío", () => {
    // Una pantalla puede mandar un parámetro que este sustituto no implementa;
    // devolver la lista completa es preferible a una pantalla vacía sin causa,
    // que se lee como "no hay datos" y manda a buscar el problema al lugar
    // equivocado.
    const r = responder(estado, "GET", "/expensas?ordenar_por=monto");
    expect(r.data).toHaveLength(3);
  });

  it("devuelve 501 explicativo ante una ruta desconocida", () => {
    const r = responder(estado, "GET", "/rutaquenoexiste");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(501);
    expect(r.data.detail).toContain("/rutaquenoexiste");
  });

  it("devuelve 501 ante una escritura, que llega en el Plan B2", () => {
    const r = responder(estado, "POST", "/gastos", { monto: 1 });
    expect(r.status).toBe(501);
  });
});

describe("entrada a la demo", () => {
  it("responde el login de cada perfil con la forma que espera la app", () => {
    for (const rol of ["administracion", "propietario_al_dia", "propietario_moroso"]) {
      const r = responder(estado, "POST", "/auth/demo-login", { rol });
      expect(r.status).toBe(200);
      expect(r.data.access_token).toBeTruthy();
      expect(r.data.user.rol).toMatch(/administracion|departamento/);
    }
  });

  it("el propietario al día y el moroso son departamentos distintos", () => {
    const alDia = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_al_dia" });
    const moroso = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_moroso" });
    expect(alDia.data.user.departamento_id).not.toBe(moroso.data.user.departamento_id);
  });

  it("administración entra sin departamento asociado", () => {
    const r = responder(estado, "POST", "/auth/demo-login", { rol: "administracion" });
    expect(r.data.user.rol).toBe("administracion");
    expect(r.data.user.departamento_id).toBeNull();
  });

  it("un perfil desconocido devuelve 400", () => {
    const r = responder(estado, "POST", "/auth/demo-login", { rol: "intruso" });
    expect(r.status).toBe(400);
  });

  it("devuelve el consorcio del dataset en /me/consorcios", () => {
    const r = responder(estado, "GET", "/me/consorcios");
    expect(r.status).toBe(200);
    expect(r.data[0].nombre).toBe("Edificio Libertador");
  });
});

describe("mi cuenta según quién entró", () => {
  it("devuelve la cuenta del departamento de la sesión", () => {
    const r = responder(estado, "GET", "/movimientos/mi-cuenta", null, { departamento_id: 2 });
    expect(r.status).toBe(200);
    expect(r.data.saldo_total).toBe(1500);
  });

  it("sin sesión de departamento devuelve 403, como el backend", () => {
    const r = responder(estado, "GET", "/movimientos/mi-cuenta", null, { departamento_id: null });
    expect(r.status).toBe(403);
  });
});
