import { describe, it, expect, beforeEach } from "vitest";
import DATASET from "./dataset.json";
import { crearEstado } from "./estado";
import { responder } from "./servidor";

/**
 * Cada ruta que las pantallas consultan al cargar.
 *
 * La demo muestra la aplicación entera salvo la consola de la plataforma, así
 * que esta lista cubre todas las secciones, no sólo el circuito de venta.
 *
 * Si una devuelve 501, la pantalla correspondiente muestra un cartel de error
 * en la demo publicada — por eso esta lista es la red de contención: agregar
 * una pantalla que consulte algo nuevo tiene que romper este test antes de
 * llegar a producción.
 */
const RECORRIDO = [
  ["/me/consorcios", "AuthContext al entrar"],
  ["/departamentos", "varias"],
  ["/expensas", "Cobranzas"],
  ["/comprobantes", "Cobranzas"],
  ["/periodos", "Historial de cierres"],
  ["/gastos", "Gastos"],
  ["/gastos-habituales", "Inicio"],
  ["/comunicados", "Comunicados"],
  ["/peticiones", "Peticiones"],
  ["/reservas", "Reservas"],
  ["/amenities", "Reservas"],
  ["/trabajos", "Trabajos"],
  ["/proveedores", "Reporte de proveedores"],
  ["/clases-prorrateo", "formulario de gasto"],
  ["/cajas", "Tesorería"],
  ["/tesoreria", "Inicio y Tesorería"],
  ["/configuracion", "Configuración"],
  ["/movimientos/cuentas", "Cuentas corrientes"],
  ["/reportes/morosos", "Inicio y reporte"],
  ["/reportes/estado-financiero", "Reporte"],
  ["/reportes/proveedores", "Reporte"],
  ["/notificaciones", "campanita"],
  ["/notificaciones/no-leidas-count", "campanita"],
  ["/notificaciones/preferencias", "Preferencias de avisos"],
  ["/empleados", "Personal"],
  ["/haberes", "Haberes"],
  ["/conceptos-liquidacion", "Conceptos de liquidación"],
  ["/liquidaciones", "Liquidaciones"],
  ["/transferencias-caja", "Tesorería · Transferencias"],
  ["/usuarios", "Padrón"],
  ["/trabajos-recurrentes", "Trabajos recurrentes"],
];

let estado;
beforeEach(() => {
  estado = crearEstado(DATASET, new Date());
});

describe("el recorrido de venta carga entero", () => {
  it.each(RECORRIDO)("%s (%s) responde 200", (ruta) => {
    const r = responder(estado, "GET", ruta, null, { departamento_id: 1 });
    expect(r.status, `${ruta} devolvió ${r.status}: ${JSON.stringify(r.data)}`).toBe(200);
  });

  it("mi cuenta del propietario trae saldo y movimientos", () => {
    const login = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_al_dia" });
    const r = responder(estado, "GET", "/movimientos/mi-cuenta", null, {
      departamento_id: login.data.user.departamento_id,
    });
    expect(r.status).toBe(200);
    expect(r.data.movimientos.length).toBeGreaterThan(0);
  });

  it("la cuenta del moroso es distinta de la del propietario al día", () => {
    const alDia = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_al_dia" });
    const moroso = responder(estado, "POST", "/auth/demo-login", { rol: "propietario_moroso" });
    const cuentaAlDia = responder(estado, "GET", "/movimientos/mi-cuenta", null, {
      departamento_id: alDia.data.user.departamento_id,
    });
    const cuentaMoroso = responder(estado, "GET", "/movimientos/mi-cuenta", null, {
      departamento_id: moroso.data.user.departamento_id,
    });
    expect(cuentaMoroso.data.saldo_total).toBeGreaterThan(cuentaAlDia.data.saldo_total);
  });

  it("el estado del último período responde, que es lo que mira Cierre", () => {
    const periodos = estado.leer("/periodos");
    const ultimo = periodos[0].periodo;
    const r = responder(estado, "GET", `/periodos/${ultimo}/estado`);
    expect(r.status).toBe(200);
  });

  it("la cuenta corriente de cada departamento está en el dataset", () => {
    const deptos = estado.leer("/departamentos");
    for (const depto of deptos) {
      const r = responder(estado, "GET", `/departamentos/${depto.id}/cuenta`);
      expect(r.status, `falta la cuenta de ${depto.codigo}`).toBe(200);
    }
  });

  it("cada expensa con PDF apunta a un archivo con nombre válido", () => {
    const pdfs = DATASET._pdfs ?? {};
    expect(Object.keys(pdfs).length).toBeGreaterThan(0);
    for (const nombre of Object.values(pdfs)) {
      expect(nombre).toMatch(/^expensa-\d+\.pdf$/);
    }
  });

  it("cada caja puede abrir su detalle de movimientos", () => {
    const cajas = estado.leer("/cajas");
    expect(cajas.length).toBeGreaterThan(1);
    for (const caja of cajas) {
      const r = responder(estado, "GET", `/cajas/${caja.id}/movimientos`);
      expect(r.status, `falta el detalle de la caja ${caja.nombre}`).toBe(200);
    }
  });

  it("los comprobantes apuntan a imágenes estáticas, no al backend", () => {
    const comprobantes = estado.leer("/comprobantes").filter((c) => c.archivo_path);
    expect(comprobantes.length).toBeGreaterThan(0);
    for (const c of comprobantes) {
      expect(c.archivo_path).toMatch(/^\/demo-comprobantes\//);
    }
  });
});

describe("la casilla de excluir saldos al día y a favor", () => {
  it("con la casilla marcada quedan sólo los que deben", () => {
    const r = responder(estado, "GET", "/reportes/morosos?solo_deudores=true");
    expect(r.status).toBe(200);
    expect(r.data.length).toBeGreaterThan(0);
    for (const item of r.data) {
      expect(item.saldo).toBeGreaterThan(0.01);
    }
  });

  it("al destildarla aparece el resto del padrón, no la misma lista", () => {
    // La casilla estaba muerta: el dataset venía ya filtrado por el backend y
    // el sustituto ignoraba el parámetro, así que tildarla y destildarla
    // mostraba exactamente lo mismo.
    const soloDeudores = responder(estado, "GET", "/reportes/morosos?solo_deudores=true").data;
    const todos = responder(estado, "GET", "/reportes/morosos?solo_deudores=false").data;
    expect(todos.length).toBeGreaterThan(soloDeudores.length);
  });

  it("sin deudas ni saldos a favor, están todas las unidades del padrón", () => {
    const unidades = estado.leer("/departamentos").length;
    const todos = responder(estado, "GET", "/reportes/morosos?solo_deudores=false").data;
    expect(todos).toHaveLength(unidades);
  });
});
