import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import RecuperarPassword from "./RecuperarPassword";
import RestablecerPassword from "./RestablecerPassword";

const apiFetch = vi.fn();
vi.mock("../api/client", () => ({
  apiFetch: (...args) => apiFetch(...args),
  API_BASE: "http://localhost:8000",
}));

const navigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => navigate,
}));

beforeEach(() => {
  apiFetch.mockReset();
  navigate.mockReset();
});

describe("RecuperarPassword", () => {
  it("muestra el mismo mensaje sin decir si el email existe", async () => {
    const user = userEvent.setup();
    apiFetch.mockResolvedValue({ ok: true, status: 202, data: {} });
    render(
      <MemoryRouter>
        <RecuperarPassword />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/email/i), "cualquiera@ejemplo.com");
    await user.click(screen.getByRole("button", { name: /enviar/i }));

    expect(await screen.findByText(/si el email está registrado/i)).toBeInTheDocument();
  });

  it("muestra ese mismo mensaje aunque el servidor falle", async () => {
    // Si la pantalla distinguiera los casos, se volveria un verificador de
    // que emails estan registrados -- justo lo que el backend evita.
    const user = userEvent.setup();
    apiFetch.mockResolvedValue({ ok: false, status: 500, data: {} });
    render(
      <MemoryRouter>
        <RecuperarPassword />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/email/i), "cualquiera@ejemplo.com");
    await user.click(screen.getByRole("button", { name: /enviar/i }));

    expect(await screen.findByText(/si el email está registrado/i)).toBeInTheDocument();
  });
});

describe("RestablecerPassword", () => {
  function renderConToken(token) {
    return render(
      <MemoryRouter initialEntries={[`/restablecer-password?token=${token}`]}>
        <RestablecerPassword />
      </MemoryRouter>,
    );
  }

  it("avisa si el link vino sin codigo, en vez de mostrar el formulario", () => {
    render(
      <MemoryRouter initialEntries={["/restablecer-password"]}>
        <RestablecerPassword />
      </MemoryRouter>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/no trae el código/i);
  });

  it("no gasta el token si las dos contraseñas no coinciden", async () => {
    const user = userEvent.setup();
    renderConToken("abc123");

    await user.type(screen.getByLabelText(/contraseña nueva/i), "password-larga-1");
    await user.type(screen.getByLabelText(/repetila/i), "password-larga-2");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/no coinciden/i);
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("no gasta el token si la contraseña es corta", async () => {
    const user = userEvent.setup();
    renderConToken("abc123");

    await user.type(screen.getByLabelText(/contraseña nueva/i), "corta");
    await user.type(screen.getByLabelText(/repetila/i), "corta");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/al menos 8/i);
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("manda el token y la contraseña nueva, y vuelve al login", async () => {
    const user = userEvent.setup();
    apiFetch.mockResolvedValue({ ok: true, status: 204, data: null });
    renderConToken("abc123");

    await user.type(screen.getByLabelText(/contraseña nueva/i), "password-larga-1");
    await user.type(screen.getByLabelText(/repetila/i), "password-larga-1");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(apiFetch).toHaveBeenCalledWith("/auth/restablecer-password", {
      method: "POST",
      body: { token: "abc123", new_password: "password-larga-1" },
    });
    expect(navigate).toHaveBeenCalledWith("/login", expect.objectContaining({ replace: true }));
  });

  it("muestra el motivo cuando el link ya vencio", async () => {
    const user = userEvent.setup();
    apiFetch.mockResolvedValue({
      ok: false,
      status: 400,
      data: { detail: "El link es inválido o venció. Pedí uno nuevo." },
    });
    renderConToken("abc123");

    await user.type(screen.getByLabelText(/contraseña nueva/i), "password-larga-1");
    await user.type(screen.getByLabelText(/repetila/i), "password-larga-1");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/venció/i);
  });
});
