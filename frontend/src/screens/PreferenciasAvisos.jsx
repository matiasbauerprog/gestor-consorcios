import { useEffect, useState } from "react";
import { guardarPreferencias, listarPreferencias } from "../api/notificaciones";

export default function PreferenciasAvisos() {
  const [items, setItems] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState("");

  useEffect(() => {
    listarPreferencias().then((r) => {
      if (r.status === 200) setItems(r.data);
    });
  }, []);

  function alternar(tipo) {
    setItems((prev) =>
      prev.map((p) => (p.tipo === tipo ? { ...p, email_activo: !p.email_activo } : p)),
    );
    setMensaje("");
  }

  async function handleGuardar(e) {
    e.preventDefault();
    setGuardando(true);
    // Sólo los editables: el backend rechaza los otros con 400.
    const payload = items
      .filter((p) => p.editable)
      .map((p) => ({ tipo: p.tipo, email_activo: p.email_activo }));
    const r = await guardarPreferencias(payload);
    setGuardando(false);
    setMensaje(r.status === 204 ? "Preferencias guardadas." : "No se pudo guardar.");
  }

  return (
    <section className="pantalla-preferencias-avisos">
      <header>
        <h1>Avisos</h1>
        <p>
          Elegí de qué te avisamos por correo. La campanita dentro de la app
          siempre te avisa de todo.
        </p>
      </header>

      {items.length === 0 ? (
        <p>Tu rol no recibe avisos configurables.</p>
      ) : (
        <form onSubmit={handleGuardar}>
          <ul className="lista-preferencias">
            {items.map((p) => (
              <li key={p.tipo}>
                <label className="label-checkbox">
                  <input
                    type="checkbox"
                    checked={p.email_activo}
                    disabled={!p.editable}
                    onChange={() => alternar(p.tipo)}
                  />
                  <span className="preferencia-etiqueta">{p.etiqueta}</span>
                </label>
                {!p.editable && (
                  <span className="preferencia-nota">{p.motivo_no_editable}</span>
                )}
              </li>
            ))}
          </ul>

          <footer className="cabecera-acciones">
            <button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar"}
            </button>
            {mensaje && <span role="status">{mensaje}</span>}
          </footer>
        </form>
      )}
    </section>
  );
}
