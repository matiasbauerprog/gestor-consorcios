import { describe, it, expect } from "vitest";
import { sesionInicial } from "./sesion";

/** Almacenamiento de mentira con la misma interfaz que `localStorage`. */
function almacenamiento(contenido) {
  return { getItem: (clave) => contenido[clave] ?? null };
}

describe("sesionInicial", () => {
  it("recupera el departamento del usuario que la app dejó guardado", () => {
    // La app persiste el usuario para sobrevivir a un refresh. El sustituto
    // tiene que leer de ahí: si no, al recargar la página el visitante sigue
    // logueado pero su cuenta corriente aparece vacía.
    const storage = almacenamiento({
      consorcio_user: JSON.stringify({ id: 1, rol: "departamento", departamento_id: 7 }),
    });
    expect(sesionInicial(storage)).toEqual({ departamento_id: 7 });
  });

  it("administración no tiene departamento", () => {
    const storage = almacenamiento({
      consorcio_user: JSON.stringify({ id: 1, rol: "administracion", departamento_id: null }),
    });
    expect(sesionInicial(storage)).toEqual({ departamento_id: null });
  });

  it("sin usuario guardado arranca sin sesión", () => {
    expect(sesionInicial(almacenamiento({}))).toEqual({ departamento_id: null });
  });

  it("con un usuario guardado ilegible no explota", () => {
    const storage = almacenamiento({ consorcio_user: "{esto no es json" });
    expect(sesionInicial(storage)).toEqual({ departamento_id: null });
  });

  it("sin almacenamiento disponible tampoco explota", () => {
    expect(sesionInicial(undefined)).toEqual({ departamento_id: null });
  });
});
