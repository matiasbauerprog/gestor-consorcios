import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TablaResponsive from "./TablaResponsive";
import { setAnchoViewport, setAnchoContenedor } from "../test/setup";

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

// Estos tests ejercitan la estructura de la fila de detalle: el chevron, el
// colapso inicial, el wiring aria-controls. Esa estructura solo existe cuando
// el ResizeObserver descartó alguna columna (ver el describe de "escalones"
// más abajo), así que cada test fija un ancho de contenedor por debajo de
// 1000px ANTES de montar — la única columna no-prioridad-1 de `COLUMNAS` es
// "Concepto" (prioridad 3), que se cae bajo ese umbral. El comportamiento que
// protegen (apertura/cierre, ids únicos, colapso inicial) no cambió; lo único
// que cambió es que ahora depende de un ancho, y antes no.
describe("TablaResponsive — fila de detalle", () => {
  it("renderiza una fila de detalle por fila de datos", () => {
    setAnchoContenedor(900);
    const { container } = montar();
    expect(container.querySelectorAll("tr.fila-detalle")).toHaveLength(2);
  });

  it("mete en el detalle solo las columnas de prioridad 2 y 3", () => {
    setAnchoContenedor(900);
    const { container } = montar();
    const pares = container.querySelectorAll("tr.fila-detalle .detalle-par");
    // 2 filas × 1 columna de prioridad 3 (Concepto). Fecha y Monto son prio 1.
    expect(pares).toHaveLength(2);
    expect(pares[0]).toHaveAttribute("data-prio", "3");
    expect(pares[0]).toHaveTextContent("Concepto");
    expect(pares[0]).toHaveTextContent("Limpieza");
  });

  it("arranca con el detalle colapsado", () => {
    setAnchoContenedor(900);
    const { container } = montar();
    expect(container.querySelector("tr.fila-detalle")).toHaveAttribute("hidden");
    expect(screen.getAllByRole("button", { name: /ver más datos/i })[0])
      .toHaveAttribute("aria-expanded", "false");
  });

  it("el chevron abre y cierra su fila", async () => {
    setAnchoContenedor(900);
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
    setAnchoContenedor(900);
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

describe("TablaResponsive — escalones por ancho de contenedor", () => {
  const FILA_ESC = [{ id: 1, fecha: "12/08", proveedor: "ACME", rubro: "Limpieza", monto: "$1.000" }];

  const COLUMNAS_ESC = [
    { clave: "fecha", titulo: "Fecha", celda: (f) => f.fecha },
    { clave: "proveedor", titulo: "Proveedor", celda: (f) => f.proveedor, prioridad: 3 },
    { clave: "rubro", titulo: "Rubro", celda: (f) => f.rubro, prioridad: 2 },
    { clave: "monto", titulo: "Monto", celda: (f) => f.monto },
  ];

  function montarEsc(ancho) {
    if (ancho !== undefined) setAnchoContenedor(ancho);
    return render(
      <TablaResponsive
        columnas={COLUMNAS_ESC}
        filas={FILA_ESC}
        claveFila={(f) => f.id}
        renderTarjeta={(f) => <p>{f.proveedor}</p>}
      />,
    );
  }

  it("a un ancho amplio se ven las 4 columnas y no hay chevron", () => {
    const { container } = montarEsc(1440);
    expect(container.querySelectorAll("thead th")).toHaveLength(4);
    expect(container.querySelector(".col-chevron")).toBeNull();
    expect(container.querySelectorAll("tr.fila-detalle")).toHaveLength(0);
  });

  it("bajo el umbral de prioridad 3 la columna sale de la tabla y pasa al detalle", () => {
    const { container } = montarEsc(900);
    expect(container.querySelector('thead th[data-prio="3"]')).toBeNull();
    expect(container.querySelector('tbody td[data-prio="3"]')).toBeNull();
    // Prioridad 2 (Rubro) sigue en la tabla: todavía no cruzó su propio umbral.
    expect(container.querySelector('thead th[data-prio="2"]')).not.toBeNull();
    const par = container.querySelector(".fila-detalle .detalle-par");
    expect(par).toHaveAttribute("data-prio", "3");
    expect(par).toHaveTextContent("Proveedor");
    expect(par).toHaveTextContent("ACME");
  });

  it("bajo 720px también sale la de prioridad 2, junto con la de prioridad 3", () => {
    const { container } = montarEsc(700);
    expect(container.querySelector('thead th[data-prio="3"]')).toBeNull();
    expect(container.querySelector('thead th[data-prio="2"]')).toBeNull();
    const pares = container.querySelectorAll(".fila-detalle .detalle-par");
    expect(pares).toHaveLength(2);
    const prioridades = [...pares].map((p) => p.getAttribute("data-prio")).sort();
    expect(prioridades).toEqual(["2", "3"]);
  });

  // Caso motivador del umbral: un viewport de 768px (tablet portrait) da un
  // contenedor real de 720px (768 − 48px de padding de `.app-content` en el
  // rango 600–959px; ver la cuenta completa en el docblock de
  // `prioridadVisible` en TablaResponsive.jsx). Con el umbral viejo de 760
  // ese contenedor caía en el escalón mínimo; con 720 (comparación `>=`,
  // inclusive) se queda con su escalón intermedio.
  it("a 720px de contenedor (tablet portrait real) la prioridad 2 todavía se ve", () => {
    const { container } = montarEsc(720);
    expect(container.querySelector('thead th[data-prio="2"]')).not.toBeNull();
    expect(container.querySelector('thead th[data-prio="3"]')).toBeNull();
  });

  // El filo exacto del umbral de prioridad 3 (1062px de contenedor, derivado
  // en el docblock de `prioridadVisible`): un contenedor de 1061 todavía no
  // alcanza para que las columnas de prioridad 3 entren sin dejar a las de
  // prioridad 1 por debajo de lo que necesitan.
  it("a 1061px de contenedor la prioridad 3 todavía no entra, a 1062 sí", () => {
    const justoAbajo = montarEsc(1061);
    expect(justoAbajo.container.querySelector('thead th[data-prio="3"]')).toBeNull();
    justoAbajo.unmount();

    const justoArriba = montarEsc(1062);
    expect(justoArriba.container.querySelector('thead th[data-prio="3"]')).not.toBeNull();
  });

  it("el colSpan de la fila de detalle es la cantidad de columnas visibles más el chevron", () => {
    const { container } = montarEsc(700);
    // A 700px quedan visibles Fecha y Monto (prioridad 1) → 2 + 1 (chevron) = 3.
    expect(container.querySelector(".fila-detalle td")).toHaveAttribute("colspan", "3");
  });

  it("el chevron solo aparece si el ancho actual descartó alguna columna", () => {
    const ancha = montarEsc(1440);
    expect(ancha.container.querySelector(".col-chevron")).toBeNull();
    ancha.unmount();

    const angosta = montarEsc(900);
    expect(angosta.container.querySelector(".col-chevron")).not.toBeNull();
  });
});

// Dos <TablaResponsive> en la misma página cuyo dominio de claves se solapa
// (p. ej. Cajas.jsx: la tabla de cajas y la de movimientos, ambas con
// claveFila numérico) generaban antes `id={`detalle-${clave}`}` sin
// namespacing por instancia — "detalle-1" existía dos veces en el DOM y
// `aria-controls` quedaba ambiguo. Este describe prueba que cada instancia
// namespacea sus ids de detalle con `useId()`.
describe("TablaResponsive — namespacing de ids entre instancias", () => {
  it("dos tablas con claves de fila solapadas no repiten id de detalle", () => {
    setAnchoContenedor(900);
    const { container } = render(
      <>
        <TablaResponsive
          columnas={COLUMNAS}
          filas={FILAS}
          claveFila={(f) => f.id}
          renderTarjeta={(f) => <p>{f.concepto}</p>}
        />
        <TablaResponsive
          columnas={COLUMNAS}
          filas={FILAS}
          claveFila={(f) => f.id}
          renderTarjeta={(f) => <p>{f.concepto}</p>}
        />
      </>,
    );

    const detalles = container.querySelectorAll("tr.fila-detalle");
    expect(detalles).toHaveLength(4); // 2 filas × 2 instancias
    const ids = [...detalles].map((d) => d.id);
    expect(new Set(ids).size).toBe(ids.length);

    // aria-controls de cada chevron apunta a EXACTAMENTE un elemento del
    // documento. `querySelector` no alcanza acá: con un id duplicado
    // (el bug que este describe reproduce) igual devuelve "un" match — el
    // primero — así que esa aserción pasaría incluso sin el fix de useId.
    // `querySelectorAll(...).length === 1` es la que de verdad exige
    // unicidad: con el id duplicado, el selector `#detalle-1` matchea LOS
    // DOS `<tr>` que comparten ese id (los selectores de id no exigen
    // unicidad, a diferencia del propio atributo `id`), y el length da 2.
    const chevrones = container.querySelectorAll(".chevron-detalle");
    chevrones.forEach((chevron) => {
      const controla = chevron.getAttribute("aria-controls");
      expect(container.querySelectorAll(`#${CSS.escape(controla)}`)).toHaveLength(1);
    });
  });
});

describe("TablaResponsive — columna espaciadora", () => {
  const SOLO_FIJAS = [
    { clave: "fecha", titulo: "Fecha", celda: (f) => f.fecha, ancho: "10ch" },
    { clave: "monto", titulo: "Monto", celda: (f) => f.monto, ancho: "12ch" },
  ];

  it("no agrega espaciador si alguna columna visible está en auto", () => {
    setAnchoContenedor(1400);
    const { container } = montar();
    expect(container.querySelector("col.col-espaciador")).toBeNull();
    expect(container.querySelectorAll("th.col-espaciador")).toHaveLength(0);
  });

  it("agrega un espaciador cuando todas las columnas visibles tienen ancho declarado", () => {
    setAnchoContenedor(1400);
    const { container } = montar({ columnas: SOLO_FIJAS });
    // Sin él, `width: 100%` reparte el sobrante entre Fecha y Monto y las
    // estira a lo ancho del monitor.
    expect(container.querySelector("col.col-espaciador")).toHaveStyle({ width: "auto" });
    expect(container.querySelectorAll("tbody td.col-espaciador")).toHaveLength(2);
  });

  it("aparece también cuando la única columna en auto se cayó por prioridad", () => {
    // `concepto` (prioridad 3) no entra por debajo de 1062px: quedan sólo
    // columnas de ancho fijo, que es justo el caso que estiraba la tabla.
    setAnchoContenedor(900);
    const { container } = montar();
    expect(container.querySelector("col.col-espaciador")).not.toBeNull();
  });

  it("el detalle desplegable sigue cubriendo toda la fila con espaciador", () => {
    setAnchoContenedor(900);
    const { container } = montar();
    const detalle = container.querySelector("tr.fila-detalle td");
    const celdasVisibles = container.querySelectorAll("tr.fila-datos:first-of-type td");
    expect(Number(detalle.getAttribute("colspan"))).toBe(celdasVisibles.length);
  });
});
