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
  // El dataset de morosos ya viene filtrado desde el backend.
  solo_deudores: () => true,
};

export function aplicarFiltros(lista, params) {
  if (!Array.isArray(lista)) return lista;
  let resultado = lista;
  for (const [clave, valor] of params.entries()) {
    const filtro = FILTROS[clave];
    if (filtro) resultado = resultado.filter((item) => filtro(item, valor));
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
