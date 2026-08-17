import { describe, it, expect } from "vitest";
import { normalizarCuerpo } from "./cuerpo";

describe("normalizarCuerpo", () => {
  it("deja pasar un objeto plano tal cual", async () => {
    const body = { monto: 100, fecha_pago: "2026-08-18" };
    expect(await normalizarCuerpo(body)).toEqual(body);
  });

  it("deja pasar undefined", async () => {
    expect(await normalizarCuerpo(undefined)).toBeUndefined();
  });

  it("convierte un formulario en objeto", async () => {
    // Las pantallas que adjuntan un archivo mandan FormData, no JSON: sin
    // esto el sustituto recibe un objeto sin campos y rechaza todo por
    // validación.
    const fd = new FormData();
    fd.append("fecha_pago", "2026-08-18");
    fd.append("monto", "1500.5");
    expect(await normalizarCuerpo(fd)).toEqual({
      fecha_pago: "2026-08-18",
      monto: 1500.5,
    });
  });

  it("convierte a número lo que parece número, y deja el resto como texto", async () => {
    const fd = new FormData();
    fd.append("monto", "1500");
    fd.append("concepto", "Service de bombas");
    fd.append("periodo", "2026-08");
    const r = await normalizarCuerpo(fd);
    expect(r.monto).toBe(1500);
    expect(r.concepto).toBe("Service de bombas");
    // "2026-08" no es un número aunque empiece con dígitos.
    expect(r.periodo).toBe("2026-08");
  });

  it("convierte un archivo adjunto en algo que el navegador pueda mostrar", async () => {
    const fd = new FormData();
    fd.append("monto", "100");
    fd.append("archivo", new File([new Uint8Array([1, 2, 3])], "pago.png", { type: "image/png" }));
    const r = await normalizarCuerpo(fd);
    expect(r.archivo_url).toMatch(/^data:image\/png/);
    expect(r.monto).toBe(100);
  });
});
