import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ModuloNoIncluido from "./ModuloNoIncluido";
import { MODULOS } from "./modulosNoIncluidos";

describe("ModuloNoIncluido", () => {
  it("explica qué hace el módulo, no que está roto", () => {
    render(<ModuloNoIncluido modulo="personal" />);
    // Varios párrafos hablan del tema; alcanza con que el texto explicativo esté.
    expect(screen.getAllByText(/liquidaci|sueldo|encargado/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/error|no disponible|roto|falló/i)).toBeNull();
  });

  it("aclara que la sección existe en el sistema completo", () => {
    render(<ModuloNoIncluido modulo="tesoreria" />);
    expect(screen.getByText(/sistema completo/i)).toBeInTheDocument();
  });

  it("tiene texto propio para cada módulo del catálogo", () => {
    for (const clave of Object.keys(MODULOS)) {
      const { unmount } = render(<ModuloNoIncluido modulo={clave} />);
      expect(screen.getByRole("heading")).toHaveTextContent(MODULOS[clave].titulo);
      unmount();
    }
  });

  it("con un módulo desconocido no explota", () => {
    render(<ModuloNoIncluido modulo="inventado" />);
    expect(screen.getByRole("heading")).toBeInTheDocument();
  });

  it("el catálogo cubre las tres secciones que la demo deja afuera", () => {
    expect(Object.keys(MODULOS).sort()).toEqual(["configuracion", "personal", "tesoreria"]);
  });
});
