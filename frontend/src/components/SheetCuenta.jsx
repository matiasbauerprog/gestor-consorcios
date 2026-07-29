import Modal from "./Modal";
import { useAuth } from "../auth/AuthContext";
import { useNavigate } from "react-router-dom";
import SelectorConsorcio from "./SelectorConsorcio";

/** "marina.suarez@mail.com" → "Marina Suarez". El backend no guarda nombre. */
// eslint-disable-next-line react-refresh/only-export-components -- helper puro reutilizado por Task 7
export function nombreDeUsuario(email) {
  if (!email) return "";
  return email
    .split("@")[0]
    .replace(/[._-]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

export default function SheetCuenta({ abierta, onCerrar }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!abierta) return null;

  return (
    <Modal titulo="Tu cuenta" onClose={onCerrar}>
      <section className="sheet-cuenta">
        <p className="sheet-cuenta-nombre">{nombreDeUsuario(user.email)}</p>
        <p className="sheet-cuenta-meta">
          {user.email} · {user.rol}
        </p>
        <SelectorConsorcio />
        <button
          type="button"
          className="boton-secundario"
          onClick={() => {
            onCerrar();
            navigate("/mi-usuario/cambiar-password");
          }}
        >
          Cambiar contraseña
        </button>
        <button type="button" onClick={logout}>
          Cerrar sesión
        </button>
      </section>
    </Modal>
  );
}
