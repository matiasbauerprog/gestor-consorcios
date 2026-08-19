export const ORDEN_DEPTO = ["/mi-cuenta", "/peticiones", "/reservas", "/comunicados"];

export const CATEGORIAS = [
  { ruta: "/", nombre: "Inicio", suelto: true,
    rolesPermitidos: ["administracion", "representante"] },

  { id: "finanzas", titulo: "Finanzas", hijos: [
      { ruta: "/mi-cuenta", nombre: "Mi cuenta", modulo: "cobranzas",
        rolesPermitidos: ["departamento"] },
      { ruta: "/cobranzas", nombre: "Cobranzas", modulo: "cobranzas",
        rolesPermitidos: ["administracion"],
        rutasRelacionadas: ["/expensas", "/comprobantes", "/cierre-de-periodo",
                            "/departamentos", "/cuentas-corrientes"] },
      { ruta: "/gastos", nombre: "Gastos", modulo: "gastos",
        rolesPermitidos: ["administracion"] },
      { ruta: "/tesoreria", nombre: "Tesorería", modulo: "finanzas",
        rolesPermitidos: ["administracion"] },
      { id: "reportes", titulo: "Reportes", hijos: [
          { ruta: "/reportes/morosos", nombre: "Lista de morosos", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/reportes/estado-financiero", nombre: "Estado financiero", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/reportes/gastos", nombre: "Detalle de gastos", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/reportes/proveedores", nombre: "Lista de proveedores", modulo: "reportes",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
      ]},
  ]},

  { id: "gestion", titulo: "Gestión", hijos: [
      { id: "comunicacion", titulo: "Comunicación", hijos: [
          { ruta: "/comunicados", nombre: "Comunicados", modulo: "comunicacion",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
      ]},
      { id: "mantenimiento", titulo: "Mantenimiento", hijos: [
          { ruta: "/peticiones", nombre: "Peticiones", modulo: "operacion",
            rolesPermitidos: ["administracion", "representante", "departamento"] },
          { ruta: "/trabajos", nombre: "Trabajos", modulo: "operacion",
            rolesPermitidos: ["administracion", "representante"] },
          { ruta: "/trabajos-recurrentes", nombre: "Trabajos recurrentes", modulo: "operacion",
            rolesPermitidos: ["administracion", "representante"] },
      ]},
      { id: "espacios", titulo: "Espacios", hijos: [
          { ruta: "/reservas", nombre: "Reservas", modulo: "espacios_comunes",
            rolesPermitidos: ["administracion", "departamento"] },
          { ruta: "/amenities", nombre: "Amenities", modulo: "espacios_comunes",
            rolesPermitidos: ["administracion"] },
      ]},
  ]},

  { id: "personal", titulo: "Personal", hijos: [
      { ruta: "/empleados", nombre: "Empleados", modulo: "personal", rolesPermitidos: ["administracion"] },
      { ruta: "/haberes", nombre: "Haberes", modulo: "personal", rolesPermitidos: ["administracion"] },
      { ruta: "/liquidaciones", nombre: "Liquidaciones", modulo: "personal", rolesPermitidos: ["administracion"] },
      { ruta: "/conceptos-liquidacion", nombre: "Conceptos de liquidación", modulo: "personal", rolesPermitidos: ["administracion"] },
  ]},

  { id: "configuracion", titulo: "Configuración", hijos: [
      { ruta: "/configuracion", nombre: "Datos del consorcio", rolesPermitidos: ["administracion"] },
      { ruta: "/administracion/consorcios", nombre: "Consorcios de la administración", rolesPermitidos: ["administracion"] },
      { ruta: "/clases-prorrateo", nombre: "Clases de prorrateo", rolesPermitidos: ["administracion"] },
      { ruta: "/proveedores", nombre: "Proveedores", rolesPermitidos: ["administracion"] },
      { ruta: "/padron", nombre: "Usuarios y coeficientes", rolesPermitidos: ["administracion"] },
  ]},
];

export function filtrarArbol({
  rol,
  modulosHabilitados,
  usaPersonalPropio,
  reportesVisiblesDepto,
}) {
  const hojaVisible = (hoja) => {
    if (!hoja.rolesPermitidos.includes(rol)) return false;
    if (
      rol === "departamento" &&
      hoja.ruta.startsWith("/reportes/") &&
      !reportesVisiblesDepto
    ) {
      return false;
    }
    if (
      hoja.modulo &&
      modulosHabilitados !== null &&
      !modulosHabilitados.includes(hoja.modulo)
    ) {
      return false;
    }
    return true;
  };

  const resultado = [];
  for (const nodo of CATEGORIAS) {
    // Nivel 1 item suelto (Inicio)
    if (nodo.ruta) {
      if (hojaVisible(nodo)) resultado.push(nodo);
      continue;
    }
    // Personal por id (feature flag)
    if (nodo.id === "personal" && !usaPersonalPropio) continue;

    // Filtrar hijos (items y sub-grupos)
    const hijos = [];
    for (const hijo of nodo.hijos) {
      if (hijo.ruta) {
        if (hojaVisible(hijo)) hijos.push(hijo);
      } else {
        // sub-grupo: filtrar sus items
        const items = hijo.hijos.filter(hojaVisible);
        if (items.length === 0) continue;
        // Regla 1: sub-grupo de 1 → item suelto
        if (items.length === 1) hijos.push(items[0]);
        else hijos.push({ ...hijo, hijos: items });
      }
    }
    if (hijos.length === 0) continue;

    // Regla 2: categoría con un único sub-grupo y ningún item directo → promover
    const soloSubgrupos = hijos.every((h) => !h.ruta);
    if (hijos.length === 1 && soloSubgrupos) {
      resultado.push({ ...hijos[0], promovido: true }); // el sub-grupo pasa a ser categoría nivel 1
    } else {
      resultado.push({ ...nodo, hijos });
    }
  }
  return resultado;
}

// ¿alguna hoja de este nodo (incluyendo rutasRelacionadas) coincide con pathname?
// Opera sobre el árbol YA filtrado (nodos que Sidebar renderiza), por eso maneja
// tanto categorías genuinas como sub-grupos promovidos por Regla 2.
export function nodoContieneRuta(nodo, pathname) {
  const matchea = (hoja) => {
    const rutas = [hoja.ruta, ...(hoja.rutasRelacionadas ?? [])];
    return rutas.some((r) => pathname === r || pathname.startsWith(r + "/"));
  };
  if (nodo.ruta) return matchea(nodo);
  return nodo.hijos.some((h) => (h.ruta ? matchea(h) : h.hijos.some(matchea)));
}

export function aplanarParaDepto(arbol) {
  const items = [];
  const subgrupos = [];
  for (const nodo of arbol) {
    if (nodo.ruta) {
      items.push(nodo);
      continue;
    }
    if (nodo.promovido) {
      // sub-grupo promovido por Regla 2: sigue siendo un cluster
      subgrupos.push({ ...nodo, hijos: nodo.hijos.filter((h) => h.ruta) });
      continue;
    }
    // categoría nivel 1 genuina: aplanar sus hijos
    for (const hijo of nodo.hijos) {
      if (hijo.ruta) {
        items.push(hijo);
      } else {
        const soloItems = hijo.hijos.filter((h) => h.ruta);
        if (soloItems.length > 1) subgrupos.push({ ...hijo, hijos: soloItems });
        else items.push(...soloItems);
      }
    }
  }
  items.sort((a, b) => {
    const ia = ORDEN_DEPTO.indexOf(a.ruta);
    const ib = ORDEN_DEPTO.indexOf(b.ruta);
    const na = ia === -1 ? ORDEN_DEPTO.length : ia;
    const nb = ib === -1 ? ORDEN_DEPTO.length : ib;
    return na - nb;
  });
  return { items, subgrupos };
}

// Prefijo de ruta → clave de data-modulo (una de las 6 de index.css). Se evalúa
// en orden; el primero que matchea gana. Configuración queda fuera a propósito:
// cae al default "inicio" (navy), su zona de setup neutral.
const MODULO_POR_RUTA = [
  ["/cobranzas", "cobranzas"],
  ["/cuentas-corrientes", "cobranzas"],
  ["/comprobantes", "cobranzas"],
  ["/gastos", "gastos"],
  ["/liquidaciones", "gastos"],
  ["/haberes", "gastos"],
  ["/empleados", "gastos"],
  ["/conceptos-liquidacion", "gastos"],
  ["/tesoreria", "finanzas"],
  ["/estado-financiero", "finanzas"],
  ["/cajas", "finanzas"],
  ["/transferencias", "finanzas"],
  ["/reportes", "finanzas"],
  ["/expensas", "expensas"],
  ["/mi-cuenta", "expensas"],
  ["/departamentos", "expensas"],
  ["/cierre-de-periodo", "expensas"],
  ["/periodos", "expensas"],
  ["/peticiones", "operacion"],
  ["/trabajos", "operacion"],
  ["/trabajos-recurrentes", "operacion"],
  ["/amenities", "operacion"],
  ["/reservas", "operacion"],
  ["/comunicados", "operacion"],
];

export function moduloDeRuta(pathname) {
  if (pathname === "/") return "inicio";
  const hit = MODULO_POR_RUTA.find(
    ([prefijo]) => pathname === prefijo || pathname.startsWith(prefijo + "/")
  );
  return hit ? hit[1] : "inicio";
}

export const TABS_POR_ROL = {
  administracion: [
    { ruta: "/", nombre: "Inicio", icono: "casa" },
    { ruta: "/cobranzas", nombre: "Cobranzas", icono: "moneda" },
    { ruta: "/gastos", nombre: "Gastos", icono: "documento" },
    { ruta: "/tesoreria", nombre: "Finanzas", icono: "billetera" },
    { ruta: "/peticiones", nombre: "Operación", icono: "llave" },
  ],
  departamento: [
    { ruta: "/mi-cuenta", nombre: "Mi cuenta", icono: "casa" },
    { ruta: "/peticiones", nombre: "Peticiones", icono: "chat" },
    { ruta: "/reservas", nombre: "Reservas", icono: "calendario" },
    { ruta: "/comunicados", nombre: "Comunicados", icono: "campana" },
  ],
  representante: [
    { ruta: "/comunicados", nombre: "Comunicados", icono: "campana" },
    { ruta: "/peticiones", nombre: "Peticiones", icono: "chat" },
    { ruta: "/trabajos", nombre: "Trabajos", icono: "llave" },
  ],
};
