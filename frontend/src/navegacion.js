export const ORDEN_DEPTO = ["/mi-cuenta", "/peticiones", "/reservas", "/comunicados"];

export const SECCIONES = [
  {
    titulo: "Comunicación",
    modulos: [
      {
        ruta: "/comunicados",
        nombre: "Comunicación",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "comunicacion",
      },
    ],
  },
  {
    titulo: "Cobranzas y gastos",
    modulos: [
      {
        ruta: "/mi-cuenta",
        nombre: "Mi cuenta",
        rolesPermitidos: ["departamento"],
        modulo: "cobranzas",
      },
      {
        ruta: "/cobranzas",
        nombre: "Cobranzas",
        rolesPermitidos: ["administracion"],
        modulo: "cobranzas",
      },
      {
        ruta: "/gastos",
        nombre: "Gastos",
        rolesPermitidos: ["administracion"],
        modulo: "gastos",
      },
    ],
  },
  {
    titulo: "Finanzas",
    modulos: [
      {
        ruta: "/tesoreria",
        nombre: "Tesorería",
        rolesPermitidos: ["administracion"],
        modulo: "finanzas",
      },
      {
        ruta: "/cuentas-corrientes",
        nombre: "Cuentas corrientes",
        rolesPermitidos: ["administracion"],
        modulo: "cobranzas",
      },
    ],
  },
  {
    titulo: "Operación",
    modulos: [
      {
        ruta: "/peticiones",
        nombre: "Peticiones",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "operacion",
      },
      {
        ruta: "/trabajos",
        nombre: "Trabajos",
        rolesPermitidos: ["administracion", "representante"],
        modulo: "operacion",
      },
      {
        ruta: "/trabajos-recurrentes",
        nombre: "Trabajos recurrentes",
        rolesPermitidos: ["administracion", "representante"],
        modulo: "operacion",
      },
    ],
  },
  {
    titulo: "Espacios comunes",
    modulos: [
      {
        ruta: "/reservas",
        nombre: "Reservas",
        rolesPermitidos: ["administracion", "departamento"],
        modulo: "espacios_comunes",
      },
      {
        ruta: "/amenities",
        nombre: "Amenities",
        rolesPermitidos: ["administracion"],
        modulo: "espacios_comunes",
      },
    ],
  },
  {
    titulo: "Reportes",
    modulos: [
      {
        ruta: "/reportes/morosos",
        nombre: "Lista de morosos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
      },
      {
        ruta: "/reportes/estado-financiero",
        nombre: "Estado financiero",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
      },
      {
        ruta: "/reportes/gastos",
        nombre: "Detalle de gastos",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
      },
      {
        ruta: "/reportes/proveedores",
        nombre: "Lista de proveedores",
        rolesPermitidos: ["administracion", "representante", "departamento"],
        modulo: "reportes",
      },
    ],
  },
  {
    titulo: "Personal",
    modulos: [
      {
        ruta: "/liquidaciones",
        nombre: "Liquidaciones",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
      },
      {
        ruta: "/haberes",
        nombre: "Haberes",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
      },
      {
        ruta: "/conceptos-liquidacion",
        nombre: "Conceptos de liquidación",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
      },
      {
        ruta: "/empleados",
        nombre: "Empleados",
        rolesPermitidos: ["administracion"],
        modulo: "personal",
      },
    ],
  },
  {
    titulo: "Configuración",
    modulos: [
      {
        ruta: "/configuracion",
        nombre: "Datos del consorcio",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/administracion/consorcios",
        nombre: "Consorcios de la administración",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/clases-prorrateo",
        nombre: "Clases de prorrateo",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/proveedores",
        nombre: "Proveedores",
        rolesPermitidos: ["administracion"],
      },
      {
        ruta: "/padron",
        nombre: "Usuarios y coeficientes",
        rolesPermitidos: ["administracion"],
      },
    ],
  },
];

export function grupoDeRuta(pathname) {
  for (const seccion of SECCIONES) {
    if (
      seccion.modulos.some(
        (m) => pathname === m.ruta || pathname.startsWith(m.ruta + "/")
      )
    ) {
      return seccion.titulo;
    }
  }
  return null;
}

export function filtrarSecciones({
  rol,
  modulosHabilitados,
  usaPersonalPropio,
  reportesVisiblesDepto,
}) {
  return SECCIONES.map((s) => ({
    ...s,
    modulos: s.modulos.filter((m) => {
      if (!m.rolesPermitidos.includes(rol)) return false;
      if (
        rol === "departamento" &&
        m.ruta.startsWith("/reportes/") &&
        !reportesVisiblesDepto
      ) {
        return false;
      }
      if (
        m.modulo &&
        modulosHabilitados !== null &&
        !modulosHabilitados.includes(m.modulo)
      ) {
        return false;
      }
      return true;
    }),
  }))
    .filter((s) => s.modulos.length > 0)
    .filter((s) => usaPersonalPropio || s.titulo !== "Personal");
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
