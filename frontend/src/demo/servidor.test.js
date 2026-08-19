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

  it("deriva las escrituras que sabe hacer", () => {
    const r = responder(estado, "POST", "/comunicados", { titulo: "Aviso", cuerpo: "..." }, {});
    expect(r.status).toBe(201);
  });

  it("devuelve 501 ante una escritura que todavía no está en la demo", () => {
    const r = responder(estado, "DELETE", "/departamentos/1", null, {});
    expect(r.status).toBe(501);
  });

  it("al querer guardar algo explica que es una demostración, sin jerga", () => {
    // El visitante ve este texto tal cual en la pantalla. Un "501 no
    // implementado" con el path adentro se lee como un sistema roto, que es
    // justo lo contrario de lo que la demo tiene que transmitir.
    const r = responder(estado, "POST", "/empleados", { nombre_completo: "X" }, {});
    expect(r.data.detail).toMatch(/demostración/i);
    expect(r.data.detail).not.toMatch(/501|POST|\/empleados|implementa/);
  });

  it("una ruta de lectura que falta sí dice cuál es, porque eso lo ve quien programa", () => {
    const r = responder(estado, "GET", "/rutaquenoexiste");
    expect(r.data.detail).toContain("/rutaquenoexiste");
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

describe("preferencias de aviso según quién entró", () => {
  // El catálogo es disjunto por rol (eventos_para_rol en el backend): admin
  // y depto no comparten ni un tipo. Acá se los deja compartir un mismo
  // `tipo` a propósito (algo que nunca pasa con datos reales) para que un
  // guardado que le pegara a la lista equivocada sea imposible de no ver:
  // si la ruta no separara por rol, cambiar uno cambiaría el otro.
  const DATASET_PREFS = {
    ...DATASET,
    "/notificaciones/preferencias": [
      { tipo: "x", etiqueta: "Admin", email_activo: true, editable: true, motivo_no_editable: null },
    ],
    _preferencias_depto: [
      { tipo: "x", etiqueta: "Depto", email_activo: true, editable: true, motivo_no_editable: null },
    ],
  };

  it("un departamento ve la lista de depto, no la de admin", () => {
    const local = crearEstado(DATASET_PREFS, new Date(2026, 7, 20));
    const r = responder(local, "GET", "/notificaciones/preferencias", null, { departamento_id: 1 });
    expect(r.status).toBe(200);
    expect(r.data[0].etiqueta).toBe("Depto");
  });

  it("administración ve su propia lista, no la de depto", () => {
    const local = crearEstado(DATASET_PREFS, new Date(2026, 7, 20));
    const r = responder(local, "GET", "/notificaciones/preferencias", null, { departamento_id: null });
    expect(r.status).toBe(200);
    expect(r.data[0].etiqueta).toBe("Admin");
  });

  it("el PUT de un departamento cambia sólo la lista de depto", () => {
    const local = crearEstado(DATASET_PREFS, new Date(2026, 7, 20));
    const put = responder(
      local, "PUT", "/notificaciones/preferencias",
      [{ tipo: "x", email_activo: false }],
      { departamento_id: 1 },
    );
    expect(put.status).toBe(204);

    expect(local.leer("_preferencias_depto")[0].email_activo).toBe(false);
    // La de admin no se tocó -- si compartieran clave, este PUT la hubiera
    // apagado también.
    expect(local.leer("/notificaciones/preferencias")[0].email_activo).toBe(true);
  });

  it("el PUT de administración cambia sólo la lista de admin", () => {
    const local = crearEstado(DATASET_PREFS, new Date(2026, 7, 20));
    const put = responder(
      local, "PUT", "/notificaciones/preferencias",
      [{ tipo: "x", email_activo: false }],
      { departamento_id: null },
    );
    expect(put.status).toBe(204);

    expect(local.leer("/notificaciones/preferencias")[0].email_activo).toBe(false);
    expect(local.leer("_preferencias_depto")[0].email_activo).toBe(true);
  });
});
