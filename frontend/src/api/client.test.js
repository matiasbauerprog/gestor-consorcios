import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("apiFetch en modo demo", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("no sale a la red: responde desde el dataset", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const { apiFetch } = await import("./client");

    const r = await apiFetch("/departamentos");

    expect(fetch).not.toHaveBeenCalled();
    expect(r.ok).toBe(true);
    expect(Array.isArray(r.data)).toBe(true);
    expect(r.data.length).toBeGreaterThan(0);
  });

  it("responde la entrada por perfil sin backend", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const { apiFetch } = await import("./client");

    const r = await apiFetch("/auth/demo-login", {
      method: "POST",
      body: { rol: "propietario_al_dia" },
    });

    expect(fetch).not.toHaveBeenCalled();
    expect(r.status).toBe(200);
    expect(r.data.user.rol).toBe("departamento");
  });

  it("con la bandera apagada sale a la red como siempre", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    fetch.mockResolvedValue({ ok: true, status: 200, text: async () => "[]" });
    const { apiFetch } = await import("./client");

    await apiFetch("/departamentos");

    expect(fetch).toHaveBeenCalled();
  });
});
