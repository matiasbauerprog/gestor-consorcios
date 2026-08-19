/**
 * Filtros por query string que las pantallas usan sobre las listas.
 *
 * Cada entrada es el nombre del parámetro → cómo comparar contra el elemento.
 * Un parámetro que no esté acá se ignora: devolver la lista completa es
 * preferible a devolver vacío, porque una pantalla vacía se lee como "no hay
 * datos" y manda a buscar el problema al lugar equivocado.
 */
const FILTROS = {
  periodo: (item, valor) => item.periodo === valor,
  departamento_id: (item, valor) => String(item.departamento_id) === valor,
  estado: (item, valor) => item.estado === valor || item.estado_calculado === valor,
  // La casilla "excluir saldos al día y a favor" del reporte de morosos.
  //
  // El dataset guarda el padrón entero —el export pide el reporte sin
  // filtrar— y el recorte se hace acá. Antes se exportaba ya filtrado y este
  // filtro devolvía todo: la casilla quedaba muerta, tildarla y destildarla
  // mostraba la misma lista.
  //
  // El umbral es el mismo que usa `calcular_morosos` (backend/reportes.py):
  // `saldo <= 0.01` no es deudor. Con `> 0` entrarían unidades con un centavo
  // de diferencia por redondeo que el backend no cuenta como morosas.
  solo_deudores: (item, valor) => valor !== "true" || item.saldo > 0.01,
  // La pantalla /notificaciones (frontend/src/screens/Notificaciones.jsx):
  // buscador y checkbox "Solo no leídas". Mismo criterio que el backend real
  // (backend/routers/notificaciones.py): `q` busca en `mensaje` sin
  // distinguir mayúsculas (`ilike`), `solo_no_leidas` deja las `leida: false`.
  q: (item, valor) => (item.mensaje ?? "").toLowerCase().includes(valor.toLowerCase()),
  solo_no_leidas: (item, valor) => valor !== "true" || item.leida === false,
};

//: `offset`/`limit` no comparan contra un campo del item -- son un recorte de
//: la lista ya filtrada, no un filtro de igualdad -- así que no entran en
//: `FILTROS` (cuya forma es `(item, valor) => boolean`) y se aplican aparte,
//: después de los filtros de igualdad, imitando la paginación del backend
//: real (`GET /notificaciones`: `stmt.offset(offset).limit(limit)`).
export function aplicarFiltros(lista, params) {
  if (!Array.isArray(lista)) return lista;
  let resultado = lista;
  for (const [clave, valor] of params.entries()) {
    if (clave === "offset" || clave === "limit") continue;
    const filtro = FILTROS[clave];
    if (filtro) resultado = resultado.filter((item) => filtro(item, valor));
  }
  if (params.has("offset") || params.has("limit")) {
    const offset = Number(params.get("offset") ?? 0);
    const limit = params.has("limit") ? Number(params.get("limit")) : undefined;
    resultado = resultado.slice(offset, limit === undefined ? undefined : offset + limit);
  }
  return resultado;
}

/**
 * Los tres perfiles del selector de entrada.
 *
 * No hay autenticación real: el token es un rótulo y la identidad la resuelve
 * este mapa. Los códigos de unidad coinciden con los que el generador pinnea
 * (`CODIGO_PUNTUAL_FIJO` y `CODIGO_MOROSO_FIJO` en `backend/seed_demo.py`),
 * que son los que tienen la historia de pagos que cada perfil promete mostrar.
 */
export const PERFILES_DEMO = {
  administracion: { rol: "administracion", codigo: null },
  propietario_al_dia: { rol: "departamento", codigo: "UF-01A" },
  propietario_moroso: { rol: "departamento", codigo: "UF-03C" },
};
