export const ORDEN_DEPTO = ["/mi-cuenta", "/peticiones", "/reservas", "/comunicados"];

export const CATEGORIAS = [
  { ruta: "/", nombre: "Inicio", suelto: true,
    rolesPermitidos: ["administracion", "representante"] },

  { id: "finanzas", titulo: "Finanzas", hijos: [
      { ruta: "/mi-cuenta", nombre: "Mi cuenta", modulo: "cobranzas",
        rolesPermitidos: ["departamento"] },
      { ruta: "/cobranzas", nombre: "Cobranzas", modulo: "cobranzas",
        rolesPermitidos: ["administracion"],
        rutasRelacionadas: ["/expensas", "/comprobantes", "/cierre-de-periodo", "/departamentos"] },
      { ruta: "/gastos", nombre: "Gastos", modulo: "gastos",
        rolesPermitidos: ["administracion"] },
      { ruta: "/tesoreria", nombre: "Tesorería", modulo: "finanzas",
        rolesPermitidos: ["administracion"] },
      { ruta: "/cuentas-corrientes", nombre: "Cuentas corrientes", modulo: "cobranzas",
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
      resultado.push(hijos[0]); // el sub-grupo pasa a ser categoría nivel 1
    } else {
      resultado.push({ ...nodo, hijos });
    }
  }
  return resultado;
}

export function categoriaDeRuta(pathname) {
  const matchea = (hoja) => {
    const rutas = [hoja.ruta, ...(hoja.rutasRelacionadas ?? [])];
    return rutas.some(
      (r) => pathname === r || pathname.startsWith(r + "/")
    );
  };
  for (const nodo of CATEGORIAS) {
    if (nodo.ruta) {
      if (matchea(nodo)) return nodo.titulo ?? nodo.nombre;
      continue;
    }
    for (const hijo of nodo.hijos) {
      if (hijo.ruta) {
        if (matchea(hijo)) return nodo.titulo;
      } else if (hijo.hijos.some(matchea)) {
        return nodo.titulo;
      }
    }
  }
  return null;
}

export function aplanarParaDepto(arbol) {
  const items = [];
  const subgrupos = [];
  const recorrer = (nodos) => {
    for (const n of nodos) {
      if (n.ruta) items.push(n);
      else if (n.hijos) {
        const soloItems = n.hijos.filter((h) => h.ruta);
        if (soloItems.length > 1) subgrupos.push({ ...n, hijos: soloItems });
        else recorrer(n.hijos);
      }
    }
  };
  recorrer(arbol);
  items.sort((a, b) => {
    const ia = ORDEN_DEPTO.indexOf(a.ruta);
    const ib = ORDEN_DEPTO.indexOf(b.ruta);
    const na = ia === -1 ? ORDEN_DEPTO.length : ia;
    const nb = ib === -1 ? ORDEN_DEPTO.length : ib;
    return na - nb;
  });
  return { items, subgrupos };
}

// Prefijo de ruta → clave de data-modulo. Se evalúa en orden; el primero que
// matchea gana, así que los prefijos más específicos van primero.
const MODULO_POR_RUTA = [
  ["/cobranzas", "cobranzas"],
  ["/cuentas-corrientes", "cobranzas"],
  ["/comprobantes", "cobranzas"],
  ["/gastos", "gastos"],
  ["/tesoreria", "finanzas"],
  ["/estado-financiero", "finanzas"],
  ["/cajas", "finanzas"],
  ["/transferencias", "finanzas"],
  ["/comunicados", "finanzas"],
  ["/expensas", "expensas"],
  ["/mi-cuenta", "expensas"],
  ["/departamentos", "expensas"],
  ["/cierre-de-periodo", "expensas"],
  ["/periodos", "expensas"],
  ["/liquidaciones", "expensas"],
  ["/peticiones", "operacion"],
  ["/trabajos", "operacion"],
  ["/amenities", "operacion"],
  ["/reservas", "cobranzas"],
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
    { ruta: "/", nombre: "Inicio", modulo: "inicio", icono: "casa" },
    { ruta: "/cobranzas", nombre: "Cobranzas", modulo: "cobranzas", icono: "moneda" },
    { ruta: "/gastos", nombre: "Gastos", modulo: "gastos", icono: "documento" },
    { ruta: "/tesoreria", nombre: "Finanzas", modulo: "finanzas", icono: "billetera" },
    { ruta: "/peticiones", nombre: "Operación", modulo: "operacion", icono: "llave" },
  ],
  departamento: [
    { ruta: "/mi-cuenta", nombre: "Mi cuenta", modulo: "expensas", icono: "casa" },
    { ruta: "/peticiones", nombre: "Peticiones", modulo: "operacion", icono: "chat" },
    { ruta: "/reservas", nombre: "Reservas", modulo: "cobranzas", icono: "calendario" },
    { ruta: "/comunicados", nombre: "Comunicados", modulo: "finanzas", icono: "campana" },
  ],
  representante: [
    { ruta: "/comunicados", nombre: "Comunicados", modulo: "finanzas", icono: "campana" },
    { ruta: "/peticiones", nombre: "Peticiones", modulo: "operacion", icono: "chat" },
    { ruta: "/trabajos", nombre: "Trabajos", modulo: "operacion", icono: "llave" },
  ],
};
