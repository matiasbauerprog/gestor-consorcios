import { escribir } from "./escrituras";
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
    const escritura = escribir(estado, method, ruta, body, sesion);
    if (escritura) return escritura;
    return soloLectura(method, ruta);
  }

  if (ruta === "/movimientos/mi-cuenta") {
    return miCuenta(estado, method, sesion);
  }

  if (ruta === "/notificaciones/preferencias") {
    return preferenciasDeAviso(estado, sesion);
  }

  if (ruta === "/notificaciones" || ruta === "/notificaciones/no-leidas-count") {
    return notificacionesDeQuienEntro(estado, sesion, ruta, params);
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
 * Preferencias de aviso de quien entró.
 *
 * El catálogo es disjunto por rol (`eventos_para_rol` en el backend): admin y
 * depto no comparten ni un tipo. El export guarda la lista de depto aparte,
 * bajo `_preferencias_depto` (ver `backend/export_demo.py`), así que acá hay
 * que elegir cuál devolver. La sesión de la demo no guarda el rol -- sólo
 * `departamento_id`, igual que en `miCuenta` -- pero alcanza como proxy:
 * sólo un departamento lo tiene seteado.
 */
function preferenciasDeAviso(estado, sesion) {
  const clave = sesion?.departamento_id ? "_preferencias_depto" : "/notificaciones/preferencias";
  const datos = estado.leer(clave);
  if (datos === undefined) {
    return noImplementado("GET", "/notificaciones/preferencias", "no está en el dataset exportado");
  }
  return { ok: true, status: 200, data: datos };
}

/**
 * Notificaciones (lista y contador) de quien entró.
 *
 * A diferencia de las preferencias -- un catálogo compartido por rol, sin
 * personalizar -- acá el contenido SÍ depende de qué unidad es: son avisos en
 * segunda persona atados a la cuenta de cada usuario ("tu comprobante fue
 * aprobado", "UF-02E creó la petición..."). Una sola variante de depto le
 * mostraría a un perfil la bandeja de la unidad ajena, así que el export
 * (backend/export_demo.py) guarda una por cada uno de los dos perfiles de
 * depto del selector de demo-login, bajo una clave auxiliar que es un mapa
 * {departamento_id: datos} -- mismo criterio que `_pdfs`.
 */
function notificacionesDeQuienEntro(estado, sesion, ruta, params) {
  const claveAux = ruta === "/notificaciones" ? "_notificaciones_depto" : "_notificaciones_no_leidas_depto";
  let datos;
  if (sesion?.departamento_id) {
    datos = (estado.leer(claveAux) ?? {})[sesion.departamento_id];
  } else {
    datos = estado.leer(ruta);
  }
  if (datos === undefined) {
    return noImplementado("GET", ruta, "no está en el dataset exportado para este perfil");
  }
  return { ok: true, status: 200, data: ruta === "/notificaciones" ? aplicarFiltros(datos, params) : datos };
}

/**
 * Respuesta a un intento de guardar en una sección que la demo no escribe.
 *
 * El visitante lee este texto tal cual, dentro de la pantalla: tiene que
 * sonar a decisión tomada, no a sistema roto. Nada de códigos, métodos ni
 * rutas — el detalle técnico va sólo a la consola, para quien programa.
 *
 * Los dos circuitos que sí escriben (aprobar un pago, cerrar el mes) los
 * resuelve `escribir` antes de llegar acá, y por eso el texto puede invitar
 * a probarlos sin mentir.
 */
function soloLectura(method, ruta) {
  if (import.meta.env?.DEV) {
    console.info(`[demo] sólo lectura: ${method} ${ruta}`);
  }
  return {
    ok: false,
    status: 501,
    data: {
      detail:
        "Esto es una demostración: los cambios de esta sección no se guardan. " +
        "Podés recorrer todo el sistema, y en Cobranzas aprobar un pago y " +
        "cerrar el mes para ver cómo impacta de verdad.",
    },
  };
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
