import { describe, it, expect } from "vitest";
import { aplicarFiltros } from "./rutas";

const NOTIFICACIONES = [
  { id: 1, mensaje: "Tu comprobante de pago fue aprobado.", leida: false },
  { id: 2, mensaje: "Nuevo comunicado: Corte de agua.", leida: true },
  { id: 3, mensaje: "Tu petición cambió de estado: resuelta.", leida: false },
  { id: 4, mensaje: "Tu reserva de SUM fue confirmada.", leida: true },
];

// Cobertura de los cuatro parámetros que la pantalla /notificaciones manda y
// que antes el sustituto ignoraba (frontend/src/demo/rutas.js): sin esto,
// escribir en el buscador o tildar "Solo no leídas" en la demo no cambiaba
// nada -- eran controles muertos.
describe("aplicarFiltros — parámetros de /notificaciones", () => {
  it("q busca en el mensaje sin distinguir mayúsculas", () => {
    const r = aplicarFiltros(NOTIFICACIONES, new URLSearchParams({ q: "COMPROBANTE" }));
    expect(r.map((n) => n.id)).toEqual([1]);
  });

  it("q sin coincidencias devuelve la lista vacía, no la lista entera", () => {
    const r = aplicarFiltros(NOTIFICACIONES, new URLSearchParams({ q: "algo que no está" }));
    expect(r).toHaveLength(0);
  });

  it("solo_no_leidas=true deja sólo las que tienen leida en falso", () => {
    const r = aplicarFiltros(NOTIFICACIONES, new URLSearchParams({ solo_no_leidas: "true" }));
    expect(r.map((n) => n.id)).toEqual([1, 3]);
  });

  it("solo_no_leidas ausente o en false no filtra nada", () => {
    const r = aplicarFiltros(NOTIFICACIONES, new URLSearchParams({ solo_no_leidas: "false" }));
    expect(r).toHaveLength(4);
  });

  it("offset/limit recortan la lista ya filtrada, como la paginación del backend", () => {
    const r = aplicarFiltros(NOTIFICACIONES, new URLSearchParams({ offset: "1", limit: "2" }));
    expect(r.map((n) => n.id)).toEqual([2, 3]);
  });

  it("offset sin limit corta desde ahí hasta el final", () => {
    const r = aplicarFiltros(NOTIFICACIONES, new URLSearchParams({ offset: "2" }));
    expect(r.map((n) => n.id)).toEqual([3, 4]);
  });

  it("combina q, solo_no_leidas y la paginación, en ese orden", () => {
    // "Tu" aparece en 3 mensajes (1, 3 y 4); de ésas, no-leídas es sólo 1 y 3.
    const params = new URLSearchParams({ q: "tu", solo_no_leidas: "true", offset: "1", limit: "1" });
    const r = aplicarFiltros(NOTIFICACIONES, params);
    expect(r.map((n) => n.id)).toEqual([3]);
  });
});
