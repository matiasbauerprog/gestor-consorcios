import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarConsorcios } from "../api/consorcios";

export default function AdministracionConsorcios() {
  const { user, consorcioActivoId, seleccionarConsorcio, cargarConsorciosAccesibles } =
    useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const cargar = useCallback(async () => {
    setLoading(true);
    const r = await listarConsorcios();
    if (r.status === 200) setItems(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!user) return null;
  if (user.rol !== "administracion") return <Navigate to="/" replace />;

  async function elegirActivo(id) {
    seleccionarConsorcio(id);
    // Refrescar consorcios accesibles del context (por si vino uno nuevo del wizard).
    await cargarConsorciosAccesibles(user.rol);
    // Recargar para propagar el X-Consorcio-Id en todas las vistas.
    window.location.reload();
  }

  return (
    <section>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <h2>Consorcios de la administración</h2>
        <Link to="/administracion/consorcios/nuevo">
          <button type="button">+ Nuevo consorcio</button>
        </Link>
      </header>

      {loading ? (
        <p>Cargando…</p>
      ) : items.length === 0 ? (
        <article className="tarjeta">
          <p>Tu administración todavía no tiene consorcios.</p>
          <Link to="/administracion/consorcios/nuevo">
            <button type="button">Crear tu primer consorcio</button>
          </Link>
        </article>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "0.75rem" }}>
          {items.map((c) => (
            <li key={c.id} className="tarjeta">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "start",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <strong>
                    {c.nombre}
                    {c.id === consorcioActivoId && (
                      <span
                        style={{
                          marginLeft: "0.5rem",
                          fontSize: "0.75rem",
                          color: "var(--color-primary)",
                          background: "var(--color-primary-soft)",
                          padding: "0.15rem 0.5rem",
                          borderRadius: 12,
                        }}
                      >
                        Activo
                      </span>
                    )}
                  </strong>
                  <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
                    CUIT: {c.consorcio_cuit} · {c.consorcio_domicilio}
                  </div>
                  <div style={{ fontSize: "0.85rem" }}>
                    {c.usa_personal_propio
                      ? "Administra personal propio"
                      : "Sin personal propio"}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {c.id !== consorcioActivoId && (
                    <button type="button" onClick={() => elegirActivo(c.id)}>
                      Usar como activo
                    </button>
                  )}
                  <Link to="/configuracion">
                    <button
                      type="button"
                      onClick={() => {
                        if (c.id !== consorcioActivoId) seleccionarConsorcio(c.id);
                      }}
                    >
                      Editar
                    </button>
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
