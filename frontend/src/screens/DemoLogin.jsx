import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { demoLogin } from "../api/demo";
import { useAuth } from "../auth/AuthContext";

const ROLES = [
  {
    rol: "administracion",
    titulo: "Administración",
    detalle: "Cargá gastos, cerrá períodos y liquidá al encargado.",
  },
  {
    rol: "propietario_al_dia",
    titulo: "Propietario al día",
    detalle: "Mirá tu saldo, presentá un pago y reservá el SUM.",
  },
  {
    rol: "propietario_moroso",
    titulo: "Propietario moroso",
    detalle: "Vas a ver los intereses aplicados y el reclamo.",
  },
];

export default function DemoLogin({ onSinDemo }) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [cargando, setCargando] = useState(null);
  const [error, setError] = useState(null);

  async function entrar(rol) {
    setError(null);
    setCargando(rol);

    let r;
    try {
      r = await demoLogin(rol);
    } catch {
      // fetch() rechazó: backend caído, sin conexión, CORS, etc. apiFetch
      // sólo devuelve {status, data} para respuestas HTTP — un reject acá no
      // tiene status que leer, así que no puede tratarse como un error de la
      // API. Sin este catch la pantalla queda trabada en "Entrando..." para
      // siempre (candado del brief: nunca un estado intermedio sin salida).
      setError("No hay conexión con el servidor. Revisá tu conexión y probá de nuevo.");
      return;
    } finally {
      setCargando(null);
    }

    if (r.status === 200) {
      await login(r.data.access_token, r.data.user);
      navigate("/", { replace: true });
      return;
    }
    if (r.status === 404) {
      // El backend no corre en modo demo: caer al login normal.
      onSinDemo?.();
      return;
    }
    if (r.status === 503) {
      setError("El demo se está regenerando. Probá de nuevo en un minuto.");
      return;
    }
    setError("No pudimos entrar al demo. Intentá de nuevo.");
  }

  return (
    <main className="login-page">
      <section className="login-card demo-selector">
        <h1>Gestión de Consorcios</h1>
        <p className="login-subtitle">Probá el sistema como:</p>

        {ROLES.map(({ rol, titulo, detalle }) => (
          <button
            key={rol}
            type="button"
            className="demo-rol"
            onClick={() => entrar(rol)}
            disabled={cargando !== null}
          >
            <strong>{titulo}</strong>
            <span>{cargando === rol ? "Entrando..." : detalle}</span>
          </button>
        ))}

        {error && <p role="alert" className="login-error">{error}</p>}

        <p className="demo-aviso">
          Demo público: los datos se reinician cada 6 horas. Podés crear, editar
          y borrar sin miedo.
        </p>
      </section>
    </main>
  );
}
