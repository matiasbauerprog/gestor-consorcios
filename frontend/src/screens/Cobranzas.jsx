import { useSearchParams } from "react-router-dom";
import TabsPanel from "../components/TabsPanel";
import Expensas from "./Expensas";
import Comprobantes from "./Comprobantes";
import Periodos from "./Periodos";
import CuentasCorrientes from "./CuentasCorrientes";

const TABS = [
  { valor: "expensas", label: "Expensas" },
  { valor: "comprobantes", label: "Comprobantes" },
  { valor: "cuentas", label: "Cuentas corrientes" },
  { valor: "cierres", label: "Historial de cierres" },
];

const TABS_VALIDOS = new Set(TABS.map((t) => t.valor));

export default function Cobranzas() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tabActivo = TABS_VALIDOS.has(tabParam) ? tabParam : "expensas";

  function cambiarTab(valor) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", valor);
    setSearchParams(params, { replace: true });
  }

  return (
    <main className="pantalla pantalla-ancha">
      <header className="cabecera-pantalla">
        <h2>Cobranzas</h2>
      </header>

      <TabsPanel
        items={TABS}
        activo={tabActivo}
        onCambio={cambiarTab}
        ariaLabel="Secciones de cobranzas"
      />

      {tabActivo === "expensas" && <Expensas embebida />}
      {tabActivo === "comprobantes" && <Comprobantes embebida />}
      {tabActivo === "cuentas" && <CuentasCorrientes embebida />}
      {tabActivo === "cierres" && <Periodos />}
    </main>
  );
}
