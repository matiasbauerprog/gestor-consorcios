import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TablaResponsive from "./TablaResponsive";
import { setAnchoViewport } from "../test/setup";

const FILAS = [
  { id: 1, fecha: "12/08", concepto: "Limpieza", monto: "$84.500" },
  { id: 2, fecha: "03/08", concepto: "Bomba", monto: "$12.000" },
];

const COLUMNAS = [
  { clave: "fecha", titulo: "Fecha", celda: (f) => f.fecha, ancho: "10ch" },
  { clave: "concepto", titulo: "Concepto", celda: (f) => f.concepto, prioridad: 3 },
  { clave: "monto", titulo: "Monto", celda: (f) => f.monto, ancho: "12ch" },
];

function montar(props = {}) {
  return render(
    <TablaResponsive
      columnas={COLUMNAS}
      filas={FILAS}
      claveFila={(f) => f.id}
      renderTarjeta={(f) => <p>{f.concepto}</p>}
      {...props}
    />,
  );
}

describe("TablaResponsive — anchos y modelo de columnas", () => {
  it("renderiza un <col> por columna con el ancho declarado", () => {
    const { container } = montar();
    // Excluye la <col> del chevron: es adicional a las columnas de datos y
    // se cubre en el describe de "fila de detalle".
    const cols = container.querySelectorAll("colgroup col:not(.col-chevron)");
    expect(cols).toHaveLength(3);
    expect(cols[0]).toHaveStyle({ width: "10ch" });
    expect(cols[2]).toHaveStyle({ width: "12ch" });
  });

  it("usa auto como ancho por defecto", () => {
    const { container } = montar();
    const cols = container.querySelectorAll("colgroup col:not(.col-chevron)");
    expect(cols[1]).toHaveStyle({ width: "auto" });
  });

  it("marca cada celda y cada encabezado con su prioridad", () => {
    const { container } = montar();
    expect(container.querySelector('th[data-prio="3"]')).toHaveTextContent("Concepto");
    expect(container.querySelectorAll('td[data-prio="3"]')).toHaveLength(2);
  });

  it("asume prioridad 1 cuando la columna no la declara", () => {
    const { container } = montar();
    expect(container.querySelector('th[data-prio="1"]')).toHaveTextContent("Fecha");
  });

  it("muestra tarjetas por debajo de 600px", () => {
    setAnchoViewport(375);
    const { container } = montar();
    expect(container.querySelector("table")).toBeNull();
    expect(screen.getByText("Limpieza")).toBeInTheDocument();
  });

  it("muestra el mensaje de vacío cuando no hay filas", () => {
    montar({ filas: [], vacio: "No hay gastos." });
    expect(screen.getByText("No hay gastos.")).toBeInTheDocument();
  });

  it("un botón dentro de una celda queda alcanzable por rol", () => {
    const columnasConBoton = [
      ...COLUMNAS,
      { clave: "acciones", titulo: "", celda: () => <button type="button">Cancelar</button> },
    ];
    montar({ columnas: columnasConBoton });
    expect(screen.getAllByRole("button", { name: "Cancelar" })).toHaveLength(FILAS.length);
  });
});

describe("TablaResponsive — fila de detalle", () => {
  it("renderiza una fila de detalle por fila de datos", () => {
    const { container } = montar();
    expect(container.querySelectorAll("tr.fila-detalle")).toHaveLength(2);
  });

  it("mete en el detalle solo las columnas de prioridad 2 y 3", () => {
    const { container } = montar();
    const pares = container.querySelectorAll("tr.fila-detalle .detalle-par");
    // 2 filas × 1 columna de prioridad 3 (Concepto). Fecha y Monto son prio 1.
    expect(pares).toHaveLength(2);
    expect(pares[0]).toHaveAttribute("data-prio", "3");
    expect(pares[0]).toHaveTextContent("Concepto");
    expect(pares[0]).toHaveTextContent("Limpieza");
  });

  it("arranca con el detalle colapsado", () => {
    const { container } = montar();
    expect(container.querySelector("tr.fila-detalle")).toHaveAttribute("hidden");
    expect(screen.getAllByRole("button", { name: /ver más datos/i })[0])
      .toHaveAttribute("aria-expanded", "false");
  });

  it("el chevron abre y cierra su fila", async () => {
    const user = userEvent.setup();
    const { container } = montar();
    const chevron = screen.getAllByRole("button", { name: /ver más datos/i })[0];

    await user.click(chevron);
    expect(chevron).toHaveAttribute("aria-expanded", "true");
    expect(container.querySelector("tr.fila-detalle")).not.toHaveAttribute("hidden");

    await user.click(chevron);
    expect(chevron).toHaveAttribute("aria-expanded", "false");
    expect(container.querySelector("tr.fila-detalle")).toHaveAttribute("hidden");
  });

  it("cada chevron apunta a su propia fila de detalle", () => {
    const { container } = montar();
    const chevrones = screen.getAllByRole("button", { name: /ver más datos/i });
    const detalles = container.querySelectorAll("tr.fila-detalle");
    expect(chevrones[0].getAttribute("aria-controls")).toBe(detalles[0].id);
    expect(chevrones[1].getAttribute("aria-controls")).toBe(detalles[1].id);
    expect(detalles[0].id).not.toBe(detalles[1].id);
  });

  it("no renderiza chevron ni detalle si todas las columnas son prioridad 1", () => {
    const soloPrio1 = COLUMNAS.map((c) => ({ ...c, prioridad: 1 }));
    const { container } = montar({ columnas: soloPrio1 });
    expect(container.querySelectorAll("tr.fila-detalle")).toHaveLength(0);
    expect(container.querySelector(".col-chevron")).toBeNull();
  });
});
