/**
 * Las tres secciones que la demo deja fuera del recorrido de venta.
 *
 * Siguen en el menú a propósito: la amplitud del producto es argumento de
 * venta, y esconderlas haría parecer al sistema bastante más chico de lo que
 * es. Lo que no puede pasar es que el visitante entre y encuentre un error —
 * de ahí esta pantalla, que explica qué resuelve cada módulo.
 */
export const MODULOS = {
  tesoreria: {
    titulo: "Tesorería",
    resumen:
      "El dinero del consorcio, en un solo lugar: cuántas cajas hay, qué entró y qué salió de cada una, y transferencias entre ellas.",
    detalle: [
      "Cada gasto pagado y cada cobranza aprobada dejan su movimiento acá, sin que nadie los cargue dos veces.",
      "El estado financiero muestra el activo, lo que los departamentos adeudan y el patrimonio neto a una fecha de corte.",
    ],
  },
  personal: {
    titulo: "Personal y liquidaciones",
    resumen:
      "El encargado del edificio: su legajo, sus haberes y la liquidación mensual de sueldo con sus cargas sociales.",
    detalle: [
      "Cada liquidación congela los valores vigentes al momento de calcularla, así que cambiar un haber no altera el historial.",
      "Y genera sola los gastos del rubro de sueldos, que entran al prorrateo del mes sin cargarlos a mano.",
    ],
  },
  configuracion: {
    titulo: "Configuración del consorcio",
    resumen:
      "Lo que define cómo se reparte cada gasto: las clases de prorrateo, el coeficiente de cada unidad, los proveedores y el padrón.",
    detalle: [
      "El padrón se importa desde una planilla: no hay que cargar sesenta unidades a mano para empezar.",
      "Y desde acá se dan de alta los consorcios de la administración, con un asistente de cuatro pasos.",
    ],
  },
};

const GENERICO = {
  titulo: "Sección no incluida en la demo",
  resumen: "Esta parte del sistema no forma parte del recorrido de la demostración.",
  detalle: [],
};

export default function ModuloNoIncluido({ modulo }) {
  const info = MODULOS[modulo] ?? GENERICO;

  return (
    <main className="pantalla modulo-no-incluido">
      <h2>{info.titulo}</h2>
      <p className="modulo-no-incluido-resumen">{info.resumen}</p>
      {info.detalle.map((parrafo) => (
        <p key={parrafo}>{parrafo}</p>
      ))}
      <p className="modulo-no-incluido-nota">
        Esta sección forma parte del <strong>sistema completo</strong>. La demo se
        concentra en el circuito de expensas y cobranzas para que se pueda recorrer
        en pocos minutos.
      </p>
    </main>
  );
}
