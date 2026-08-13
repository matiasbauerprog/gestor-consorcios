import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MenuAcciones from "./MenuAcciones";

function montar(overrides = {}) {
  const onEditar = vi.fn();
  const onEliminar = vi.fn();
  render(
    <div>
      <button type="button">afuera</button>
      <MenuAcciones
        acciones={[
          { label: "Editar", onSelect: onEditar },
          { label: "Eliminar", onSelect: onEliminar, peligro: true },
        ]}
        {...overrides}
      />
    </div>,
  );
  return { onEditar, onEliminar };
}

describe("MenuAcciones", () => {
  it("arranca cerrado", () => {
    montar();
    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.getByRole("button", { name: "Acciones" }))
      .toHaveAttribute("aria-expanded", "false");
  });

  it("abre al clickear el trigger", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Editar" })).toBeInTheDocument();
  });

  it("ejecuta la acción y cierra", async () => {
    const user = userEvent.setup();
    const { onEditar } = montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    expect(onEditar).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("marca las acciones destructivas", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toHaveClass("peligro");
  });

  it("cierra con Escape y devuelve el foco al trigger", async () => {
    const user = userEvent.setup();
    montar();
    const trigger = screen.getByRole("button", { name: "Acciones" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("cierra al clickear afuera", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.click(screen.getByRole("button", { name: "afuera" }));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("acepta una etiqueta propia para el trigger", () => {
    montar({ etiqueta: "Acciones de la caja Efectivo" });
    expect(screen.getByRole("button", { name: "Acciones de la caja Efectivo" }))
      .toBeInTheDocument();
  });
});
