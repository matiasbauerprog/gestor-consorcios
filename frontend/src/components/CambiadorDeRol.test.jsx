import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import CambiadorDeRol from "./CambiadorDeRol";

const login = vi.fn();
let usuarioActual = { rol: "departamento", departamento_id: 1 };

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: usuarioActual, login }),
}));

const demoLogin = vi.fn(async (rol) => ({
  ok: true,
  status: 200,
  data: {
    access_token: `demo-${rol}`,
    user: { rol: rol === "administracion" ? "administracion" : "departamento", departamento_id: 9 },
  },
}));

vi.mock("../api/demo", () => ({
  ES_DEMO: true,
  demoLogin: (rol) => demoLogin(rol),
}));

/** Deja ver a qué ruta quedó parada la app después de cambiar de perfil. */
function RutaActual() {
  return <span data-testid="ruta">{useLocation().pathname}</span>;
}

/**
 * `CambiadorDeRol` navega al inicio después de cambiar de cuenta, así que
 * necesita un Router alrededor. Se monta en `/cobranzas` —una ruta de
 * administración— para que el salto a "/" sea observable.
 */
function montar() {
  return render(
    <MemoryRouter initialEntries={["/cobranzas"]}>
      <CambiadorDeRol />
      <Routes>
        <Route path="*" element={<RutaActual />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  login.mockClear();
  demoLogin.mockClear();
  usuarioActual = { rol: "departamento", departamento_id: 1 };
});

describe("CambiadorDeRol", () => {
  it("ofrece los tres perfiles", () => {
    montar();
    expect(screen.getByRole("button", { name: /administración/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /al día/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /moroso/i })).toBeInTheDocument();
  });

  it("al elegir un perfil entra con ese perfil, sin recargar", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: /administración/i }));

    expect(demoLogin).toHaveBeenCalledWith("administracion");
    expect(login).toHaveBeenCalledWith("demo-administracion", expect.objectContaining({
      rol: "administracion",
    }));
    // Sin este salto el cambio no se ve hasta navegar a mano: la pantalla
    // montada no vuelve a pedir datos, y puede no existir para el rol nuevo.
    expect(screen.getByTestId("ruta")).toHaveTextContent("/");
  });

  it("quedarse en el mismo perfil no mueve la pantalla", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: /al día/i }));

    expect(screen.getByTestId("ruta")).toHaveTextContent("/cobranzas");
  });

  it("marca cuál es el perfil activo", () => {
    montar();
    expect(screen.getByRole("button", { name: /al día/i })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: /administración/i })).not.toHaveAttribute("aria-current");
  });

  it("no vuelve a entrar si ya estás en ese perfil", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: /al día/i }));

    expect(demoLogin).not.toHaveBeenCalled();
  });

  it("cuando el perfil activo es administración, lo marca a él", () => {
    usuarioActual = { rol: "administracion", departamento_id: null };
    montar();
    expect(screen.getByRole("button", { name: /administración/i })).toHaveAttribute("aria-current", "true");
  });
});
