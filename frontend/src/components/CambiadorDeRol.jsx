import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { demoLogin } from "../api/demo";

/**
 * Los mismos tres perfiles del selector de entrada. El código de la unidad
 * "al día" es el que el generador pinnea (`CODIGO_PUNTUAL_FIJO`), y su id en
 * el dataset es 1 — se usa para saber cuál de los dos perfiles de propietario
 * está activo.
 */
const PERFILES = [
  { rol: "administracion", etiqueta: "Administración" },
  { rol: "propietario_al_dia", etiqueta: "Propietario al día" },
  { rol: "propietario_moroso", etiqueta: "Propietario moroso" },
];

const ID_DEPTO_AL_DIA = 1;

/**
 * Cambia de perfil sin pasar por la pantalla de entrada.
 *
 * No es una comodidad: el estado de la demo vive en memoria, y volver al
 * selector recarga la página y lo borra. Sin esto no se puede mostrar el
 * circuito completo —presentar un pago como propietario y aprobarlo como
 * administración—, que es lo que la demo existe para mostrar. Verificado en
 * el navegador antes de escribir esto: al recargar, el comprobante recién
 * presentado desaparecía.
 *
 * Sólo se renderiza en modo demo (ver `AppLayout`): en la aplicación de un
 * cliente la identidad la da el token, y cambiar de rol sin credenciales
 * sería un agujero de seguridad.
 */
export default function CambiadorDeRol() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [cambiando, setCambiando] = useState(null);

  const esActivo = (rol) => {
    if (rol === "administracion") return user?.rol === "administracion";
    if (user?.rol !== "departamento") return false;
    return rol === "propietario_al_dia"
      ? user?.departamento_id === ID_DEPTO_AL_DIA
      : user?.departamento_id !== ID_DEPTO_AL_DIA;
  };

  async function cambiar(rol) {
    if (esActivo(rol) || cambiando) return;
    setCambiando(rol);
    try {
      const r = await demoLogin(rol);
      if (r.ok) {
        await login(r.data.access_token, r.data.user);
        // Sin esto el cambio no se veía hasta navegar a mano: la pantalla
        // actual ya está montada y no vuelve a pedir datos, y encima puede
        // ser una ruta que el rol nuevo no tiene (admin en /cobranzas →
        // propietario). "/" es el único destino que sirve para los tres:
        // `InicioRoute` redirige a la pantalla de inicio de cada rol.
        navigate("/", { replace: true });
      }
    } finally {
      setCambiando(null);
    }
  }

  return (
    <nav className="cambiador-rol" aria-label="Ver la demo como">
      <span className="cambiador-rol-etiqueta">Ver como</span>
      {PERFILES.map(({ rol, etiqueta }) => (
        <button
          key={rol}
          type="button"
          onClick={() => cambiar(rol)}
          aria-current={esActivo(rol) ? "true" : undefined}
          disabled={cambiando !== null}
        >
          {etiqueta}
        </button>
      ))}
    </nav>
  );
}
