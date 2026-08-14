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
      <button type="button">después</button>
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

  it("no cierra el menú al mover el foco del trigger a un item", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.tab();
    expect(screen.getByRole("menuitem", { name: "Editar" })).toHaveFocus();
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  it("no cierra el menú al mover el foco entre items", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.tab();
    await user.tab();
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toHaveFocus();
    expect(screen.getByRole("menu")).toBeInTheDocument();
  });

  it("cierra el menú al tabear hacia afuera del componente", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(screen.getByRole("button", { name: "Acciones" }));
    await user.tab(); // trigger -> Editar
    await user.tab(); // Editar -> Eliminar
    await user.tab(); // Eliminar -> "después" (afuera del menú)
    expect(screen.getByRole("button", { name: "después" })).toHaveFocus();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  describe("acciones deshabilitadas", () => {
    function montarConDisabled() {
      const onAprobar = vi.fn();
      render(
        <MenuAcciones
          acciones={[
            { label: "Aprobar", onSelect: onAprobar, disabled: true },
            { label: "Eliminar", onSelect: vi.fn(), peligro: true },
          ]}
        />,
      );
      return { onAprobar };
    }

    it("un item con disabled: true se renderiza deshabilitado", async () => {
      const user = userEvent.setup();
      montarConDisabled();
      await user.click(screen.getByRole("button", { name: "Acciones" }));
      expect(screen.getByRole("menuitem", { name: "Aprobar" })).toBeDisabled();
    });

    it("clickear un item deshabilitado no dispara onSelect", async () => {
      const user = userEvent.setup();
      const { onAprobar } = montarConDisabled();
      await user.click(screen.getByRole("button", { name: "Acciones" }));
      await user.click(screen.getByRole("menuitem", { name: "Aprobar" }));
      expect(onAprobar).not.toHaveBeenCalled();
    });

    it("clickear un item deshabilitado no cierra el menú", async () => {
      const user = userEvent.setup();
      montarConDisabled();
      await user.click(screen.getByRole("button", { name: "Acciones" }));
      await user.click(screen.getByRole("menuitem", { name: "Aprobar" }));
      expect(screen.getByRole("menu")).toBeInTheDocument();
    });
  });

  it("con acciones vacío no renderiza ni el trigger", () => {
    const { container } = render(<MenuAcciones acciones={[]} />);
    expect(screen.queryByRole("button", { name: "Acciones" })).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });
});
