import { useSearchParams } from "react-router-dom";
import TabsPanel from "../components/TabsPanel";
import EstadoFinanciero from "./EstadoFinanciero";
import Cajas from "./Cajas";
import Transferencias from "./Transferencias";

const TABS = [
  { valor: "estado", label: "Estado financiero" },
  { valor: "cajas", label: "Cajas" },
  { valor: "transferencias", label: "Transferencias" },
];

const TABS_VALIDOS = new Set(TABS.map((t) => t.valor));

export default function Tesoreria() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tabActivo = TABS_VALIDOS.has(tabParam) ? tabParam : "estado";

  function cambiarTab(valor) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", valor);
    setSearchParams(params, { replace: true });
  }

  return (
    <main className="pantalla">
      <h2 style={{ marginBottom: "0.25rem" }}>Tesorería</h2>

      <TabsPanel
        items={TABS}
        activo={tabActivo}
        onCambio={cambiarTab}
        ariaLabel="Secciones de tesorería"
      />

      {tabActivo === "estado" && <EstadoFinanciero />}
      {tabActivo === "cajas" && <Cajas />}
      {tabActivo === "transferencias" && <Transferencias />}
    </main>
  );
}
