import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
    const cols = container.querySelectorAll("colgroup col");
    expect(cols).toHaveLength(3);
    expect(cols[0]).toHaveStyle({ width: "10ch" });
    expect(cols[2]).toHaveStyle({ width: "12ch" });
  });

  it("usa auto como ancho por defecto", () => {
    const { container } = montar();
    const cols = container.querySelectorAll("colgroup col");
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
});
