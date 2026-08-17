import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/liquidaciones", () => ({
  listarLiquidaciones: vi.fn(async () => ({ status: 200, data: [] })),
  crearLiquidacion: vi.fn(),
  actualizarLiquidacion: vi.fn(),
  eliminarLiquidacion: vi.fn(),
}));
vi.mock("../api/empleados", () => ({
  listarEmpleados: vi.fn(async () => ({ status: 200, data: [] })),
}));

import Liquidaciones from "./Liquidaciones";
import { listarLiquidaciones } from "../api/liquidaciones";

function montar(props) {
  return render(
    <MemoryRouter>
      <Liquidaciones {...props} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  listarLiquidaciones.mockClear();
});

describe("Liquidaciones", () => {
  it("la vista del mes arranca filtrada por el mes en curso", async () => {
    montar({});
    await waitFor(() => expect(listarLiquidaciones).toHaveBeenCalled());
    const [params] = listarLiquidaciones.mock.calls.at(-1);
    expect(params.periodo).toMatch(/^\d{4}-\d{2}$/);
  });

  it("el historial arranca sin filtro de período", async () => {
    montar({ vistaHistorial: true });
    await waitFor(() => expect(listarLiquidaciones).toHaveBeenCalled());
    const [params] = listarLiquidaciones.mock.calls.at(-1);
    expect(params.periodo).toBeUndefined();
  });

  it("al pasar del mes al historial se suelta el filtro del mes", async () => {
    // Las dos vistas son el mismo componente en rutas distintas, así que
    // React lo reutiliza y el estado inicial no se vuelve a evaluar: el
    // historial heredaba el mes en curso y aparecía vacío, como si no
    // hubiera liquidaciones cargadas nunca.
    const { rerender } = montar({});
    await waitFor(() => expect(listarLiquidaciones).toHaveBeenCalled());

    rerender(
      <MemoryRouter>
        <Liquidaciones vistaHistorial />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const [params] = listarLiquidaciones.mock.calls.at(-1);
      expect(params.periodo).toBeUndefined();
    });
    expect(screen.getByLabelText(/período/i)).toHaveValue("");
  });
});
