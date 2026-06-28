import { useEffect, useState } from "react";
import Modal from "./Modal";
import {
  crearRecurrente,
  actualizarRecurrente,
} from "../api/trabajosRecurrentes";
import { listarProveedores } from "../api/proveedores";

export default function ModalRecurrente({ item, onClose, onGuardado }) {
  const esEditar = item !== null;
  const [nombre, setNombre] = useState(item?.nombre || "");
  const [descripcion, setDescripcion] = useState(item?.descripcion || "");
  const [periodicidad, setPeriodicidad] = useState(
    item?.periodicidad || "mensual",
  );
  const [proveedorId, setProveedorId] = useState(
    item?.proveedor_sugerido_id || "",
  );
  const [monto, setMonto] = useState(item?.monto_estimado || "");
  const [activa, setActiva] = useState(item?.activa ?? true);
  const [proveedores, setProveedores] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      const r = await listarProveedores();
      if (r.status === 200) setProveedores(r.data);
    })();
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const payload = {
      nombre,
      descripcion,
      periodicidad,
      proveedor_sugerido_id: proveedorId ? Number(proveedorId) : null,
      monto_estimado: monto ? Number(monto) : null,
      activa,
    };
    const r = esEditar
      ? await actualizarRecurrente(item.id, payload)
      : await crearRecurrente(payload);
    if (r.status === 200 || r.status === 201) onGuardado();
    else setError(r.data?.detail || "Error al guardar.");
  }

  return (
    <Modal
      titulo={esEditar ? "Editar plantilla" : "Nueva plantilla"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit}>
        <label>
          Nombre{" "}
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            required
            maxLength={255}
          />
        </label>
        <label>
          Descripción{" "}
          <textarea
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            required
            maxLength={2000}
            rows={3}
          />
        </label>
        <label>
          Periodicidad{" "}
          <select
            value={periodicidad}
            onChange={(e) => setPeriodicidad(e.target.value)}
          >
            <option value="mensual">Mensual</option>
            <option value="trimestral">Trimestral</option>
            <option value="semestral">Semestral</option>
            <option value="anual">Anual</option>
          </select>
        </label>
        <label>
          Proveedor sugerido (opcional){" "}
          <select
            value={proveedorId}
            onChange={(e) => setProveedorId(e.target.value)}
          >
            <option value="">— Ninguno —</option>
            {proveedores.map((p) => (
              <option key={p.id} value={p.id}>
                {p.razon_social}
              </option>
            ))}
          </select>
        </label>
        <label>
          Monto estimado (opcional){" "}
          <input
            type="number"
            min="0"
            step="0.01"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={activa}
            onChange={(e) => setActiva(e.target.checked)}
          />{" "}
          Activa
        </label>
        {error && <p className="error">{error}</p>}
        <div className="acciones">
          <button type="submit">Guardar</button>
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
        </div>
      </form>
    </Modal>
  );
}
