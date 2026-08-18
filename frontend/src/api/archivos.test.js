import { describe, expect, it, vi } from "vitest";

import { rutaAdjuntoComprobante, urlDeArchivo } from "./archivos";
import { API_BASE } from "./client";

describe("rutaAdjuntoComprobante", () => {
  it("apunta al endpoint firmado contra el backend real", () => {
    expect(rutaAdjuntoComprobante({ id: 7, archivo_path: "comprobantes/abc.jpg" })).toBe(
      "/comprobantes/7/archivo",
    );
  });

  it("deja pasar derecho la ruta estatica de la demo", () => {
    expect(
      rutaAdjuntoComprobante({ id: 7, archivo_path: "/demo-comprobantes/uf01.png" }),
    ).toBe("/demo-comprobantes/uf01.png");
  });

  it("devuelve null si no hay adjunto", () => {
    expect(rutaAdjuntoComprobante({ id: 7, archivo_path: null })).toBeNull();
    expect(rutaAdjuntoComprobante(null)).toBeNull();
  });
});

describe("urlDeArchivo", () => {
  it("devuelve la ruta tal cual si es un archivo estatico de la demo", async () => {
    // La demo no tiene backend: sus comprobantes los sirve el hosting estatico.
    // Pedir una firma no tendria a quien preguntarle.
    const apiFetch = vi.fn();

    const url = await urlDeArchivo("/demo-comprobantes/uf01.png", { apiFetch });

    expect(url).toBe("/demo-comprobantes/uf01.png");
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide la url firmada al backend y la prefija con el host de la api", async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      ok: true,
      data: { url: "/archivos/comprobantes/abc.jpg?exp=1&firma=ff", expira_en: 300 },
    });

    const url = await urlDeArchivo("/comprobantes/7/archivo", { apiFetch });

    expect(apiFetch).toHaveBeenCalledWith("/comprobantes/7/archivo");
    expect(url).toBe(`${API_BASE}/archivos/comprobantes/abc.jpg?exp=1&firma=ff`);
  });

  it("devuelve null si el backend no da la url", async () => {
    const apiFetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });

    expect(await urlDeArchivo("/comprobantes/7/archivo", { apiFetch })).toBeNull();
  });

  it("devuelve null si no hay ruta", async () => {
    expect(await urlDeArchivo(null)).toBeNull();
  });
});
