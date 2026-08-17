import { aplicarFiltros, PERFILES_DEMO } from "./rutas";

/**
 * Responde un pedido desde el estado en memoria, con la misma forma que
 * devuelve `apiFetch` contra el servidor real: `{ok, status, data}`.
 *
 * Las lecturas se resuelven por coincidencia exacta de path contra las claves
 * del dataset — que se exportaron con el mismo path que piden las pantallas,
 * incluidas las que llevan un identificador en el medio. Por eso no hace falta
 * un enrutador con patrones: el generador ya resolvió los ids.
 *
 * `sesion` lleva el departamento de quien entró, para las rutas que responden
 * "lo mío" en vez de un recurso identificado.
 */
export function responder(estado, method, path, body, sesion) {
  const [ruta, qs] = path.split("?");
  const params = new URLSearchParams(qs ?? "");

  if (method === "POST" && ruta === "/auth/demo-login") {
    return entrar(estado, body);
  }

  if (method !== "GET") {
    return noImplementado(method, ruta, "las escrituras llegan en el Plan B2");
  }

  if (ruta === "/movimientos/mi-cuenta") {
    return miCuenta(estado, method, sesion);
  }

  const datos = estado.leer(ruta);
  if (datos === undefined) {
    return noImplementado(method, ruta, "no está en el dataset exportado");
  }

  return { ok: true, status: 200, data: aplicarFiltros(datos, params) };
}

/**
 * Entrada por perfil, sin backend. Devuelve la forma que espera `AuthContext`:
 * token, tipo, vencimiento y usuario.
 */
function entrar(estado, body) {
  const perfil = PERFILES_DEMO[body?.rol];
  if (!perfil) {
    return { ok: false, status: 400, data: { detail: "Perfil de demo desconocido." } };
  }

  const deptos = estado.leer("/departamentos") ?? [];
  const depto = perfil.codigo ? deptos.find((d) => d.codigo === perfil.codigo) : null;

  return {
    ok: true,
    status: 200,
    data: {
      access_token: `demo-${body.rol}`,
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: depto ? depto.id : 1,
        email: depto ? `${depto.codigo.toLowerCase()}@demo.local` : "admin@demo.local",
        rol: perfil.rol,
        departamento_id: depto ? depto.id : null,
      },
    },
  };
}

/**
 * La cuenta corriente del departamento que entró.
 *
 * El backend real resuelve esto desde el token; acá desde la sesión. La cuenta
 * de cada unidad se exportó en `/departamentos/{id}/cuenta`, así que sólo hay
 * que elegir la que corresponde.
 */
function miCuenta(estado, method, sesion) {
  if (!sesion?.departamento_id) {
    return { ok: false, status: 403, data: { detail: "Sólo para departamentos." } };
  }
  const cuenta = estado.leer(`/departamentos/${sesion.departamento_id}/cuenta`);
  if (!cuenta) {
    return noImplementado(
      method,
      "/movimientos/mi-cuenta",
      `falta la cuenta del departamento ${sesion.departamento_id} en el dataset`,
    );
  }
  return { ok: true, status: 200, data: cuenta };
}

/**
 * Respuesta controlada ante algo que el sustituto no sabe hacer.
 *
 * Devuelve un error que las pantallas ya saben mostrar, en vez de lanzar una
 * excepción que dejaría la pantalla en blanco. En desarrollo además grita en
 * la consola: la red de contención real es el test que recorre las rutas del
 * recorrido de venta, y este mensaje es para que nadie llegue hasta ahí sin
 * haberlo visto antes.
 */
function noImplementado(method, ruta, motivo) {
  if (import.meta.env?.DEV) {
    console.error(`[demo] sin implementar: ${method} ${ruta} — ${motivo}`);
  }
  return {
    ok: false,
    status: 501,
    data: { detail: `La demo no implementa ${method} ${ruta}: ${motivo}.` },
  };
}
