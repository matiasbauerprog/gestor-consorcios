import { useSearchParams } from "react-router-dom";
import TabsPanel from "../components/TabsPanel";
import Coeficientes from "./Coeficientes";
import PadronDeptos from "./PadronDeptos";

const TABS = [
  { valor: "padron", label: "Departamentos y usuarios" },
  { valor: "coeficientes", label: "Coeficientes" },
];

const TABS_VALIDOS = new Set(TABS.map((t) => t.valor));

// Alias compatibilidad: los links viejos (/departamentos, /usuarios) redirigen a
// /padron?tab=departamentos y /padron?tab=usuarios; ambos mapean acá a "padron".
const ALIAS = { departamentos: "padron", usuarios: "padron" };

export default function Padron() {
  const [searchParams, setSearchParams] = useSearchParams();
  const raw = searchParams.get("tab");
  const tabParam = ALIAS[raw] || raw;
  const tabActivo = TABS_VALIDOS.has(tabParam) ? tabParam : "padron";

  function cambiarTab(valor) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", valor);
    setSearchParams(params, { replace: true });
  }

  return (
    <main className="pantalla">
      <h2 style={{ marginBottom: "0.25rem" }}>Usuarios y coeficientes</h2>

      <TabsPanel
        items={TABS}
        activo={tabActivo}
        onCambio={cambiarTab}
        ariaLabel="Secciones"
      />

      {tabActivo === "padron" && <PadronDeptos />}
      {tabActivo === "coeficientes" && <Coeficientes />}
    </main>
  );
}
