import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section>
      <h2>Página no encontrada</h2>
      <p>La ruta que intentaste abrir no existe.</p>
      <Link to="/comunicados">Volver al inicio</Link>
    </section>
  );
}
