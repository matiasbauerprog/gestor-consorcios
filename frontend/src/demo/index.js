import DATASET from "./dataset.json";
import { normalizarCuerpo } from "./cuerpo";
import { crearEstado } from "./estado";
import { responder } from "./servidor";
import { sesionInicial } from "./sesion";

const estado = crearEstado(DATASET, new Date());

/**
 * Quién está usando la demo ahora mismo.
 *
 * El backend real deduce esto del token; acá se recuerda lo que devolvió la
 * última entrada, porque hay rutas que responden "lo mío" en vez de un
 * recurso identificado (`/movimientos/mi-cuenta`).
 *
 * Arranca de lo que la app dejó guardado, para sobrevivir a una recarga de
 * página: el módulo se reinicia, pero el visitante sigue logueado.
 */
let sesion = sesionInicial(globalThis.localStorage);

export async function responderDemo(method, path, body) {
  // Las pantallas que adjuntan un archivo mandan FormData; el sustituto
  // trabaja con objetos planos y no puede leer un archivo de forma síncrona.
  const cuerpo = await normalizarCuerpo(body);
  const r = responder(estado, method, path, cuerpo, sesion);
  if (method === "POST" && path === "/auth/demo-login" && r.ok) {
    sesion = { departamento_id: r.data.user.departamento_id };
  }
  return r;
}

/** Vuelve la demo al estado del arranque, para el botón del aviso superior. */
export function reiniciarDemo() {
  estado.reiniciar();
  sesion = { departamento_id: null };
}
