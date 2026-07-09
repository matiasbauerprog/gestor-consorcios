import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { obtenerMetricas } from "../api/superAdmin";

function Card({ titulo, valor, sub }) {
  return (
    <article className="super-admin-metric-card">
      <h3>{titulo}</h3>
      <div className="valor">{valor}</div>
      {sub && (
        <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem", color: "var(--color-text-muted, #666)" }}>
          {sub}
        </p>
      )}
    </article>
  );
}

export default function SuperAdminMetricas() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const r = await obtenerMetricas();
      if (r.status === 200) setData(r.data);
      setLoading(false);
    })();
  }, []);

  if (!user) return null;
  if (user.rol !== "super_admin") return <Navigate to="/" replace />;

  if (loading) return <p>Cargando métricas…</p>;
  if (!data) return <p>No se pudieron obtener las métricas.</p>;

  return (
    <section>
      <h2>Métricas globales</h2>
      <div className="super-admin-metric-grid">
        <Card
          titulo="Administraciones"
          valor={data.administraciones.total}
          sub={`Activas: ${data.administraciones.activas} · Suspendidas: ${data.administraciones.suspendidas}`}
        />
        <Card titulo="Consorcios" valor={data.consorcios.total} />
        <Card titulo="Departamentos" valor={data.departamentos.total} />
        <Card
          titulo="Expensas del mes"
          valor={data.expensas_ultimo_mes.emitidas}
          sub={`Monto total: $${Number(data.expensas_ultimo_mes.monto_total).toLocaleString("es-AR")}`}
        />
        <Card
          titulo="Impersonates (30 días)"
          valor={data.impersonates_ultimos_30_dias}
        />
      </div>
    </section>
  );
}
