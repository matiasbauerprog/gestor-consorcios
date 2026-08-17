import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("abrirPdfExpensa en modo demo", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("VITE_DEMO_MODE", "true");
    vi.stubGlobal("open", vi.fn());
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("abre el archivo estático, sin pedirle nada a ningún servidor", async () => {
    const DATASET = (await import("../demo/dataset.json")).default;
    const [id, nombre] = Object.entries(DATASET._pdfs)[0];

    const { abrirPdfExpensa } = await import("./pdf");
    await abrirPdfExpensa(Number(id));

    expect(fetch).not.toHaveBeenCalled();
    expect(window.open).toHaveBeenCalledWith(expect.stringContaining(nombre), "_blank");
  });

  it("una expensa sin PDF exportado avisa en vez de abrir una pestaña vacía", async () => {
    const { abrirPdfExpensa } = await import("./pdf");
    // El mensaje tiene que explicar la limitación real (sólo el último
    // período tiene PDF exportado), no un error genérico.
    await expect(abrirPdfExpensa(999999)).rejects.toThrow(/último período/i);
    expect(window.open).not.toHaveBeenCalled();
  });
});
