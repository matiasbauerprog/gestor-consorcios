import { useEffect, useState } from "react";
import { listarClasesProrrateo } from "../api/clasesProrrateo";
import { reemplazarMatrizCoeficientes } from "../api/coeficientes";
import {
  listarCoeficientesDepartamento,
  listarDepartamentos,
} from "../api/departamentos";

export default function Coeficientes() {
  const [departamentos, setDepartamentos] = useState([]);
  const [clases, setClases] = useState([]);
  const [claseActivaId, setClaseActivaId] = useState(null);
  // matriz[deptoId][claseId] = porcentaje (number)
  const [matriz, setMatriz] = useState({});
  const [inicial, setInicial] = useState({});
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(null);

  async function cargar() {
    setCargando(true);
    setError(null);
    setOk(null);
    const [rD, rC] = await Promise.all([
      listarDepartamentos(),
      listarClasesProrrateo({ activa: true }),
    ]);
    if (rD.status !== 200 || rC.status !== 200) {
      if (rD.status !== 401 && rC.status !== 401) setError("No se pudo cargar.");
      setCargando(false);
      return;
    }
    setDepartamentos(rD.data);
    setClases(rC.data);
    if (rC.data.length > 0 && claseActivaId == null) {
      setClaseActivaId(rC.data[0].id);
    }

    const m = {};
    for (const d of rD.data) {
      m[d.id] = {};
      for (const c of rC.data) m[d.id][c.id] = 0;
      const rc = await listarCoeficientesDepartamento(d.id);
      if (rc.status === 200) {
        for (const item of rc.data) {
          m[d.id][item.clase_prorrateo_id] = Number(item.porcentaje);
        }
      }
    }
    setMatriz(m);
    setInicial(JSON.parse(JSON.stringify(m)));
    setCargando(false);
  }

  useEffect(() => { cargar(); }, []);

  function setCelda(deptoId, claseId, valor) {
    setOk(null);
    const nuevo = Number(valor);
    setMatriz((prev) => ({
      ...prev,
      [deptoId]: { ...prev[deptoId], [claseId]: Number.isNaN(nuevo) ? 0 : nuevo },
    }));
  }

  function partesIguales(claseId) {
    if (departamentos.length === 0) return;
    const parte = Number((100 / departamentos.length).toFixed(4));
    setOk(null);
    setMatriz((prev) => {
      const copia = { ...prev };
      for (const d of departamentos) {
        copia[d.id] = { ...copia[d.id], [claseId]: parte };
      }
      return copia;
    });
  }

  function vaciarClase(claseId) {
    setOk(null);
    setMatriz((prev) => {
      const copia = { ...prev };
      for (const d of departamentos) {
        copia[d.id] = { ...copia[d.id], [claseId]: 0 };
      }
      return copia;
    });
  }

  function totalDeClase(claseId) {
    let s = 0;
    for (const d of departamentos) {
      s += Number(matriz[d.id]?.[claseId] || 0);
    }
    return Number(s.toFixed(4));
  }

  function hayCambios() {
    return JSON.stringify(matriz) !== JSON.stringify(inicial);
  }

  async function guardar() {
    setError(null);
    setOk(null);
    setGuardando(true);
    const items = [];
    for (const d of departamentos) {
      for (const c of clases) {
        const v = Number(matriz[d.id]?.[c.id] || 0);
        if (v > 0) {
          items.push({
            departamento_id: d.id,
            clase_prorrateo_id: c.id,
            porcentaje: v,
          });
        }
      }
    }
    const r = await reemplazarMatrizCoeficientes(items);
    setGuardando(false);
    if (r.status === 200) {
      setOk(`Guardado (${r.data.cantidad} coeficientes).`);
      setInicial(JSON.parse(JSON.stringify(matriz)));
    } else {
      setError(r.data?.detail || "No se pudo guardar.");
    }
  }

  if (cargando) return <section><p>Cargando…</p></section>;

  if (departamentos.length === 0) {
    return (
      <section>
        <p>Todavía no cargaste departamentos. Andá a la tab "Padrón" primero.</p>
      </section>
    );
  }
  if (clases.length === 0) {
    return (
      <section>
        <p>
          No hay clases de prorrateo activas. Cargá al menos una en{" "}
          <strong>Configuración → Clases de prorrateo</strong>.
        </p>
      </section>
    );
  }

  const claseActiva = clases.find((c) => c.id === claseActivaId) || clases[0];
  const total = totalDeClase(claseActiva.id);
  const totalOk = Math.abs(total - 100) < 0.01;
  const cambios = hayCambios();

  return (
    <section>
      <p className="meta">
        Los coeficientes salen del reglamento de copropiedad. Elegí la clase y
        cargá los porcentajes. Las modificaciones no se pierden al cambiar de
        clase — se guardan todas juntas al final.
      </p>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {ok && <p className="success-banner" role="status">{ok}</p>}

      <div className="cabecera-pantalla">
        <label>
          Clase de prorrateo:{" "}
          <select
            value={claseActiva.id}
            onChange={(e) => setClaseActivaId(Number(e.target.value))}
          >
            {clases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.codigo} — {c.nombre}
              </option>
            ))}
          </select>
        </label>
        <div className="cabecera-acciones">
          <button type="button" onClick={() => partesIguales(claseActiva.id)}>
            Partes iguales (100 / {departamentos.length})
          </button>
          <button type="button" onClick={() => vaciarClase(claseActiva.id)}>
            Vaciar
          </button>
        </div>
      </div>

      <div className="tabla-scroll">
        <table className="tabla-coeficientes">
          <thead>
            <tr>
              <th>Departamento</th>
              <th>{claseActiva.codigo} — {claseActiva.nombre}</th>
            </tr>
          </thead>
          <tbody>
            {departamentos.map((d) => (
              <tr key={d.id}>
                <th scope="row">
                  <strong>{d.codigo}</strong>
                  {d.descripcion && <div className="meta">{d.descripcion}</div>}
                </th>
                <td>
                  <input
                    type="number"
                    step="0.0001"
                    min="0"
                    max="100"
                    value={matriz[d.id]?.[claseActiva.id] ?? 0}
                    onChange={(e) => setCelda(d.id, claseActiva.id, e.target.value)}
                  />{" "}
                  %
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Total</th>
              <th>
                <span
                  style={{
                    color: totalOk
                      ? "var(--color-success, #196c2e)"
                      : "var(--color-danger, #b3261e)",
                    fontWeight: 700,
                  }}
                >
                  {total.toFixed(2)} %{" "}
                  {totalOk ? "✓" : `(falta ${(100 - total).toFixed(2)} %)`}
                </span>
              </th>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="tarjeta-acciones">
        <button type="button" onClick={cargar} disabled={guardando}>
          Descartar cambios
        </button>
        <button
          type="button"
          onClick={guardar}
          disabled={guardando || !cambios}
        >
          {guardando ? "Guardando…" : "Guardar matriz completa"}
        </button>
      </div>

      {!totalOk && (
        <p className="meta">
          Esta clase no suma 100 %. Se puede guardar igual si el reglamento lo
          establece así, pero revisá que sea intencional.
        </p>
      )}
    </section>
  );
}
