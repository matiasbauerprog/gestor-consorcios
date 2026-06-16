import { useEffect, useState } from "react";
import {
  listarDepartamentos,
  listarCoeficientesDepartamento,
  reemplazarCoeficientesDepartamento,
} from "../api/departamentos";
import { listarClasesProrrateo } from "../api/clasesProrrateo";

export default function Departamentos() {
  const [departamentos, setDepartamentos] = useState([]);
  const [coeficientesPorDepto, setCoeficientesPorDepto] = useState({});
  const [clases, setClases] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);

  async function recargar() {
    setCargando(true);
    try {
      const [deptos, clasesActivas] = await Promise.all([
        listarDepartamentos(),
        listarClasesProrrateo({ activa: true }),
      ]);
      setDepartamentos(deptos);
      setClases(clasesActivas);

      const coefs = {};
      for (const d of deptos) {
        coefs[d.id] = await listarCoeficientesDepartamento(d.id);
      }
      setCoeficientesPorDepto(coefs);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    recargar();
  }, []);

  function resumen(coefs) {
    if (!coefs || coefs.length === 0) return "—";
    return coefs.map((c) => `${c.codigo}: ${c.porcentaje}%`).join(" · ");
  }

  if (cargando) return <main className="app-content"><p>Cargando…</p></main>;

  return (
    <main className="app-content">
      <header className="cabecera-pantalla">
        <h2>Departamentos</h2>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Descripción</th>
            <th>Coeficientes</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {departamentos.map((d) => (
            <tr key={d.id}>
              <td>{d.codigo}</td>
              <td>{d.descripcion || "—"}</td>
              <td>{resumen(coeficientesPorDepto[d.id])}</td>
              <td>
                <button
                  type="button"
                  onClick={() => setModal({ departamento: d, coeficientes: coeficientesPorDepto[d.id] || [] })}
                >
                  Editar coeficientes
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {modal && (
        <ModalCoeficientes
          departamento={modal.departamento}
          coeficientesActuales={modal.coeficientes}
          clases={clases}
          onCerrar={() => setModal(null)}
          onGuardar={async (nuevos) => {
            await reemplazarCoeficientesDepartamento(modal.departamento.id, nuevos);
            setModal(null);
            recargar();
          }}
        />
      )}
    </main>
  );
}

function ModalCoeficientes({ departamento, coeficientesActuales, clases, onCerrar, onGuardar }) {
  const inicial = {};
  for (const c of clases) inicial[c.id] = 0;
  for (const c of coeficientesActuales) inicial[c.clase_prorrateo_id] = c.porcentaje;

  const [valores, setValores] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      const payload = Object.entries(valores)
        .filter(([, v]) => v !== "" && v !== null && Number(v) > 0)
        .map(([clase_prorrateo_id, porcentaje]) => ({
          clase_prorrateo_id: Number(clase_prorrateo_id),
          porcentaje: Number(porcentaje),
        }));
      await onGuardar(payload);
    } catch (err) {
      setError(err.message);
      setGuardando(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCerrar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Coeficientes — {departamento.codigo}</h3>
        <form onSubmit={onSubmit}>
          {clases.map((c) => (
            <label key={c.id}>
              {c.codigo} — {c.nombre}
              <input
                type="number"
                step="0.0001"
                min="0"
                max="100"
                value={valores[c.id] ?? 0}
                onChange={(e) => setValores({ ...valores, [c.id]: e.target.value })}
              />
            </label>
          ))}
          {error && <p className="error">{error}</p>}
          <div className="modal-acciones">
            <button type="button" onClick={onCerrar}>Cancelar</button>
            <button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
