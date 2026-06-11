import { AuthProvider, useAuth } from "./auth/AuthContext";
import Login from "./screens/Login";

function Shell() {
  const { user, hydrating, logout } = useAuth();

  if (hydrating) {
    return <p style={{ padding: "2rem", textAlign: "center" }}>Cargando...</p>;
  }

  if (!user) {
    return <Login />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Gestión de Consorcios</h1>
        <nav className="app-user">
          <span>
            {user.email} <strong>({user.rol})</strong>
          </span>
          <button type="button" onClick={logout}>
            Cerrar sesión
          </button>
        </nav>
      </header>

      <main className="app-content">
        <section>
          <h2>Bienvenido/a</h2>
          <p>Aún no hay módulos implementados.</p>
          <p>
            Próximos pasos: comunicados, expensas, peticiones, trabajos, reservas
            y administración.
          </p>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
