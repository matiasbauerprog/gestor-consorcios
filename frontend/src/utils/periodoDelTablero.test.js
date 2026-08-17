import { describe, it, expect } from "vitest";
import { periodoDelTablero } from "./periodoDelTablero";

describe("periodoDelTablero", () => {
  it("muestra el mes en curso cuando ya tiene expensas emitidas", () => {
    const r = periodoDelTablero("2026-08", 18, ["2026-07", "2026-06"]);
    expect(r).toEqual({ periodo: "2026-08", esMesEnCurso: true });
  });

  it("sin expensas del mes en curso, muestra el último período cerrado", () => {
    // Le pasa a cualquier administrador que entre a principio de mes: el mes
    // recién empieza y el tablero mostraba todo en cero, que se lee como "el
    // sistema no tiene datos".
    const r = periodoDelTablero("2026-08", 0, ["2026-06", "2026-07"]);
    expect(r).toEqual({ periodo: "2026-07", esMesEnCurso: false });
  });

  it("elige el más reciente de los cerrados, sin importar el orden en que vengan", () => {
    const r = periodoDelTablero("2026-08", 0, ["2026-07", "2026-02", "2026-06"]);
    expect(r.periodo).toBe("2026-07");
  });

  it("un consorcio recién creado, sin nada cerrado, se queda en el mes en curso", () => {
    const r = periodoDelTablero("2026-08", 0, []);
    expect(r).toEqual({ periodo: "2026-08", esMesEnCurso: true });
  });

  it("tolera que la lista de períodos no haya llegado", () => {
    expect(periodoDelTablero("2026-08", 0, null).periodo).toBe("2026-08");
  });
});
