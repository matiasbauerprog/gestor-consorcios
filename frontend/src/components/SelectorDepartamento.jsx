import { useEffect, useState } from "react";
import { listarDepartamentos } from "../api/departamentos";

export default function SelectorDepartamento({ valor, onChange, permitirVacio = true }) {
  const [departamentos, setDepartamentos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelado = false;
    async function cargar() {
      const r = await listarDepartamentos();
      if (cancelado) return;
      if (r.status === 200) {
        setDepartamentos(r.data);
        setError(null);
      } else if (r.status !== 401) {
        setError("No se pudieron cargar los departamentos.");
      }
      setCargando(false);
    }
    cargar();
    return () => {
      cancelado = true;
    };
  }, []);

  if (error) {
    return <span role="alert">{error}</span>;
  }

  return (
    <label>
      Departamento
      <select
        value={valor ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        disabled={cargando}
      >
        {permitirVacio && <option value="">— Todos —</option>}
        {!permitirVacio && valor === null && <option value="">— Elegí uno —</option>}
        {departamentos.map((d) => (
          <option key={d.id} value={d.id}>
            {d.codigo}{d.descripcion ? ` — ${d.descripcion}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
