import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarAuditLog } from "../api/superAdmin";
import { formatFecha, formatFechaHora } from "../utils/fechas";

const ACCIONES = [
  "",
  "crear_admin",
  "editar_admin",
  "suspender_admin",
  "reactivar_admin",
  "reset_password",
  "impersonate_start",
  "impersonate_end",
  "impersonate_mutacion",
];

const PAGE_SIZE = 50;

export default function SuperAdminAuditLog() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accion, setAccion] = useState("");
  const [administracionId, setAdministracionId] = useState("");
  const [offset, setOffset] = useState(0);

  const cargar = useCallback(async () => {
    setLoading(true);
    const r = await listarAuditLog({
      accion: accion || undefined,
      administracionId: administracionId ? Number(administracionId) : undefined,
      limit: PAGE_SIZE,
      offset,
    });
    if (r.status === 200) setItems(r.data);
    setLoading(false);
  }, [accion, administracionId, offset]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!user) return null;
  if (user.rol !== "super_admin") return <Navigate to="/" replace />;

  return (
    <section>
      <h2>Audit log</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          cargar();
        }}
        style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}
      >
        <label>
          Acción
          <select value={accion} onChange={(e) => setAccion(e.target.value)}>
            {ACCIONES.map((a) => (
              <option key={a} value={a}>
                {a || "(todas)"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Administración id
          <input
            type="number"
            min={1}
            value={administracionId}
            onChange={(e) => setAdministracionId(e.target.value)}
            placeholder="Todas"
          />
        </label>
        <button type="submit">Filtrar</button>
      </form>

      {loading ? (
        <p>Cargando…</p>
      ) : items.length === 0 ? (
        <p>No hay entradas.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Fecha</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Acción</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Admin id</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Motivo</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Detalles</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id} style={{ borderTop: "1px solid var(--color-border)" }}>
                <td style={{ padding: "0.5rem", whiteSpace: "nowrap" }}>
                  {formatFechaHora(e.fecha)}
                </td>
                <td style={{ padding: "0.5rem" }}>{e.accion}</td>
                <td style={{ padding: "0.5rem" }}>
                  {e.administracion_id_afectada ?? "-"}
                </td>
                <td style={{ padding: "0.5rem" }}>{e.motivo ?? "-"}</td>
                <td style={{ padding: "0.5rem", maxWidth: "400px", overflow: "hidden", textOverflow: "ellipsis" }}>
                  <code style={{ fontSize: "0.8rem" }}>{e.detalles ?? "-"}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
        <button
          type="button"
          disabled={offset === 0 || loading}
          onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
        >
          ← Anterior
        </button>
        <button
          type="button"
          disabled={items.length < PAGE_SIZE || loading}
          onClick={() => setOffset((o) => o + PAGE_SIZE)}
        >
          Siguiente →
        </button>
        <span style={{ marginLeft: "auto", fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
          Mostrando desde el registro #{offset + 1}
        </span>
      </div>
    </section>
  );
}
