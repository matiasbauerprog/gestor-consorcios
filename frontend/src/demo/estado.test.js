import { describe, it, expect } from "vitest";
import { crearEstado } from "./estado";

const DATASET = {
  _generado: "2026-08-17",
  "/departamentos": [{ id: 1, codigo: "UF-01A" }],
  "/expensas": [{ id: 9, periodo: "2026-07" }],
};

describe("crearEstado", () => {
  it("lee una ruta del dataset", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    expect(estado.leer("/departamentos")).toEqual([{ id: 1, codigo: "UF-01A" }]);
  });

  it("devuelve undefined para una ruta que no está", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    expect(estado.leer("/no-existe")).toBeUndefined();
  });

  it("aplica el desplazamiento de fechas al cargar", () => {
    const estado = crearEstado(DATASET, new Date(2026, 9, 5));
    expect(estado.leer("/expensas")[0].periodo).toBe("2026-09");
  });

  it("no comparte referencias con el dataset original", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    estado.leer("/departamentos")[0].codigo = "MODIFICADO";
    expect(DATASET["/departamentos"][0].codigo).toBe("UF-01A");
  });

  it("reiniciar vuelve al estado del arranque", () => {
    const estado = crearEstado(DATASET, new Date(2026, 7, 20));
    estado.leer("/departamentos")[0].codigo = "MODIFICADO";
    estado.reiniciar();
    expect(estado.leer("/departamentos")[0].codigo).toBe("UF-01A");
  });
});

describe("escrituras", () => {
  const DATOS = {
    _generado: "2026-08-17",
    "/comunicados": [{ id: 3, titulo: "Viejo" }],
  };

  it("agrega al principio, que es donde la pantalla espera lo nuevo", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    estado.agregar("/comunicados", { id: 4, titulo: "Nuevo" });
    expect(estado.leer("/comunicados")[0].titulo).toBe("Nuevo");
    expect(estado.leer("/comunicados")).toHaveLength(2);
  });

  it("reemplaza el valor de una ruta", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    estado.reemplazar("/comunicados", []);
    expect(estado.leer("/comunicados")).toEqual([]);
  });

  it("el siguiente id es mayor que todos los existentes", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    expect(estado.siguienteId("/comunicados")).toBe(4);
  });

  it("el siguiente id de una lista vacía arranca en 1", () => {
    const estado = crearEstado({ _generado: "2026-08-17", "/x": [] }, new Date(2026, 7, 20));
    expect(estado.siguienteId("/x")).toBe(1);
  });

  it("reiniciar deshace las escrituras", () => {
    const estado = crearEstado(DATOS, new Date(2026, 7, 20));
    estado.agregar("/comunicados", { id: 4, titulo: "Nuevo" });
    estado.reiniciar();
    expect(estado.leer("/comunicados")).toHaveLength(1);
  });
});
