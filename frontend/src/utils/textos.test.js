import { describe, it, expect } from "vitest";
import { mayusculaInicial, pluralizar } from "./textos";

describe("mayusculaInicial", () => {
  it("levanta la primera letra y no toca el resto", () => {
    expect(mayusculaInicial("lunes, 17 de agosto de 2026")).toBe(
      "Lunes, 17 de agosto de 2026",
    );
  });

  it("no capitaliza las preposiciones del nombre de un consorcio", () => {
    expect(mayusculaInicial("edificio del Sol")).toBe("Edificio del Sol");
  });

  it("tolera vacío y nulo", () => {
    expect(mayusculaInicial("")).toBe("");
    expect(mayusculaInicial(null)).toBe(null);
  });
});

describe("pluralizar", () => {
  it("en singular no agrega la s", () => {
    expect(pluralizar(1, "petición", "peticiones")).toBe("1 petición");
  });

  it("en plural usa la forma que se le pase", () => {
    expect(pluralizar(3, "petición", "peticiones")).toBe("3 peticiones");
  });

  it("en cero va en plural", () => {
    expect(pluralizar(0, "petición", "peticiones")).toBe("0 peticiones");
  });

  it("sin forma plural agrega una s", () => {
    expect(pluralizar(2, "gasto")).toBe("2 gastos");
    expect(pluralizar(1, "gasto")).toBe("1 gasto");
  });
});
