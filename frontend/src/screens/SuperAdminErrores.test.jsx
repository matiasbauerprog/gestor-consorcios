import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import SuperAdminErrores from "./SuperAdminErrores";

const listarErrores = vi.fn();
const buscarErrorPorCodigo = vi.fn();
vi.mock("../api/superAdmin", () => ({
  listarErrores: (...a) => listarErrores(...a),
  buscarErrorPorCodigo: (...a) => buscarErrorPorCodigo(...a),
}));

let usuario = { rol: "super_admin" };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: usuario }) }));

const UN_ERROR = {
  id: 1,
  codigo: "E-7K3MQ9",
  ocurrido_at: "2026-08-18T15:04:00Z",
  ruta: "/gastos",
  metodo: "POST",
  tipo: "ValueError",
  mensaje: "algo se rompió",
  traza: "Traceback (most recent call last): ...",
  usuario_id: 2,
  rol: "departamento",
  consorcio_id: 1,
};

beforeEach(() => {
  usuario = { rol: "super_admin" };
  listarErrores.mockReset().mockResolvedValue({ status: 200, data: [] });
  buscarErrorPorCodigo.mockReset();
});

function renderPantalla() {
  return render(
    <MemoryRouter>
      <SuperAdminErrores />
    </MemoryRouter>,
  );
}

describe("SuperAdminErrores", () => {
  it("dice que no hay errores sin que parezca una falla", async () => {
    renderPantalla();
    expect(await screen.findByText(/ningún error registrado/i)).toBeInTheDocument();
  });

  it("lista los errores con su codigo", async () => {
    listarErrores.mockResolvedValue({ status: 200, data: [UN_ERROR] });
    renderPantalla();
    expect(await screen.findByText("E-7K3MQ9")).toBeInTheDocument();
    expect(screen.getByText(/POST \/gastos/)).toBeInTheDocument();
  });

  it("busca por el codigo que dicta el vecino y muestra la traza", async () => {
    const user = userEvent.setup();
    buscarErrorPorCodigo.mockResolvedValue({ status: 200, data: UN_ERROR });
    renderPantalla();

    await user.type(await screen.findByLabelText(/buscar por código/i), "e-7k3mq9");
    await user.click(screen.getByRole("button", { name: /buscar/i }));

    expect(buscarErrorPorCodigo).toHaveBeenCalledWith("e-7k3mq9");
    expect(await screen.findByText(/Traceback/)).toBeInTheDocument();
  });

  it("avisa cuando el codigo no existe, en mayusculas como se guarda", async () => {
    const user = userEvent.setup();
    buscarErrorPorCodigo.mockResolvedValue({ status: 404, data: {} });
    renderPantalla();

    await user.type(await screen.findByLabelText(/buscar por código/i), "e-noexis");
    await user.click(screen.getByRole("button", { name: /buscar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("E-NOEXIS");
  });

  it("no le muestra nada a un rol que no sea super admin", () => {
    usuario = { rol: "administracion" };
    renderPantalla();
    expect(screen.queryByText(/errores del sistema/i)).toBeNull();
  });
});
