import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ModuloNoIncluido from "./ModuloNoIncluido";
import { MODULOS } from "./modulosNoIncluidos";

describe("ModuloNoIncluido", () => {
  it("explica qué hace el módulo, no que está roto", () => {
    render(<ModuloNoIncluido modulo="super-admin" />);
    expect(screen.getAllByText(/administracion|consola|plataforma/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/error|no disponible|roto|falló/i)).toBeNull();
  });

  it("aclara que la sección existe en el sistema completo", () => {
    render(<ModuloNoIncluido modulo="super-admin" />);
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

  it("la consola del dueño del SaaS es lo único que la demo deja afuera", () => {
    // Tesorería, Personal y Configuración se destaparon cuando el dataset
    // pasó a traer sus datos: la demo muestra la app entera salvo la consola
    // comercial, que no es del administrador de consorcios sino de quien
    // vende el sistema.
    expect(Object.keys(MODULOS)).toEqual(["super-admin"]);
  });
});
