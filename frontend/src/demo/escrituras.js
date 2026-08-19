import { imputar, saldoDeMovimientos } from "./cuenta";
import { repartir } from "./prorrateo";

const dos = (n) => Math.round(n * 100) / 100;
const ahora = () => new Date().toISOString().slice(0, 19);

const creado = (data) => ({ ok: true, status: 201, data });
const ok = (data) => ({ ok: true, status: 200, data });
const invalido = (detail) => ({ ok: false, status: 400, data: { detail } });
const prohibido = (detail) => ({ ok: false, status: 403, data: { detail } });
const noEncontrado = (detail) => ({ ok: false, status: 404, data: { detail } });
const conflicto = (detail) => ({ ok: false, status: 409, data: { detail } });

/**
 * Ejecuta una escritura sobre el estado.
 *
 * Devuelve `null` cuando la ruta no le corresponde, para que el servidor siga
 * buscando quién la atiende — así este módulo crece sin tocar el enrutador.
 */
export function escribir(estado, method, ruta, body, sesion) {
  if (method === "POST" && ruta === "/comunicados") {
    if (!body?.titulo) return invalido("El comunicado necesita un título.");
    const comunicado = {
      id: estado.siguienteId("/comunicados"),
      titulo: body.titulo,
      cuerpo: body.cuerpo ?? "",
      fecha_publicacion: ahora(),
      autor_id: 1,
    };
    estado.agregar("/comunicados", comunicado);
    return creado(comunicado);
  }

  if (method === "POST" && ruta === "/peticiones") {
    if (!body?.titulo) return invalido("La petición necesita un título.");
    const peticion = {
      id: estado.siguienteId("/peticiones"),
      departamento_id: sesion?.departamento_id ?? null,
      titulo: body.titulo,
      descripcion: body.descripcion ?? "",
      estado: "abierta",
      fecha_creacion: ahora(),
    };
    estado.agregar("/peticiones", peticion);
    return creado(peticion);
  }

  if (method === "PUT" && ruta === "/notificaciones/preferencias") {
    // La demo corre entera en el navegador: guardar en el estado en memoria
    // alcanza para que la pantalla responda como la real. Igual que al leer
    // (ver `preferenciasDeAviso` en servidor.js), el catálogo es disjunto por
    // rol, así que hay que pegarle a la lista que corresponde según quién
    // entró -- si no, un depto podría terminar reescribiendo el catálogo de
    // administración, o viceversa.
    const clave = sesion?.departamento_id ? "_preferencias_depto" : "/notificaciones/preferencias";
    const actuales = estado.leer(clave) ?? [];
    const porTipo = new Map((body ?? []).map((p) => [p.tipo, p.email_activo]));
    estado.reemplazar(
      clave,
      actuales.map((p) =>
        porTipo.has(p.tipo) ? { ...p, email_activo: porTipo.get(p.tipo) } : p,
      ),
    );
    return { ok: true, status: 204, data: null };
  }

  const reserva = /^\/amenities\/(\d+)\/reservas$/.exec(ruta);
  if (method === "POST" && reserva) {
    const amenityId = Number(reserva[1]);
    const amenity = (estado.leer("/amenities") ?? []).find((a) => a.id === amenityId);
    if (!amenity) return noEncontrado("El amenity no existe.");
    if (!body?.inicio || !body?.fin) return invalido("Faltan las fechas de la reserva.");
    if (body.fin <= body.inicio) return invalido("El fin tiene que ser posterior al inicio.");
    const nueva = {
      id: estado.siguienteId("/reservas"),
      amenity_id: amenityId,
      usuario_id: sesion?.departamento_id ?? null,
      inicio: body.inicio,
      fin: body.fin,
      estado: "confirmada",
      movimiento_cuenta_id: null,
    };
    estado.agregar("/reservas", nueva);
    return creado(nueva);
  }

  if (method === "POST" && ruta === "/comprobantes") {
    if (!sesion?.departamento_id) return prohibido("Sólo un departamento presenta pagos.");
    if (!body?.monto || body.monto <= 0) return invalido("El monto tiene que ser mayor a cero.");
    const comprobante = {
      id: estado.siguienteId("/comprobantes"),
      departamento_id: sesion.departamento_id,
      departamento_codigo: codigoDe(estado, sesion.departamento_id),
      fecha_pago: body.fecha_pago ?? ahora().slice(0, 10),
      monto: body.monto,
      // La imagen que el visitante eligió se lee en el navegador y viaja como
      // dato embebido: no hay servidor donde subirla.
      archivo_path: body.archivo_url ?? null,
      estado: "pendiente_verificacion",
    };
    estado.agregar("/comprobantes", comprobante);
    return creado(comprobante);
  }

  const aprobacion = /^\/comprobantes\/(\d+)$/.exec(ruta);
  if (method === "PATCH" && aprobacion) {
    const comprobante = (estado.leer("/comprobantes") ?? []).find(
      (c) => c.id === Number(aprobacion[1]),
    );
    if (!comprobante) return noEncontrado("El comprobante no existe.");
    if (comprobante.estado !== "pendiente_verificacion") {
      return conflicto("El comprobante ya fue resuelto.");
    }
    comprobante.estado = body?.estado ?? "aprobado";
    if (comprobante.estado === "aprobado") {
      registrarPago(estado, comprobante);
    } else {
      // Rechazar con motivo es parte del circuito que la demo sí escribe: sin
      // guardarlo, el visitante escribe la explicación y la ve desaparecer.
      comprobante.motivo_rechazo = (body?.motivo_rechazo ?? "").trim() || null;
    }
    return ok(comprobante);
  }

  if (method === "POST" && ruta === "/gastos") {
    if (!body?.monto || body.monto <= 0) return invalido("El gasto necesita un monto.");
    if (!body?.periodo) return invalido("El gasto necesita un período.");
    const gasto = {
      id: estado.siguienteId("/gastos"),
      periodo: body.periodo,
      rubro: body.rubro ?? "otros",
      clase_prorrateo_id: body.clase_prorrateo_id ?? null,
      departamento_id: body.departamento_id ?? null,
      proveedor_id: body.proveedor_id ?? null,
      concepto: body.concepto ?? "",
      monto: body.monto,
      forma_pago: body.forma_pago ?? "transferencia",
      fecha_pago: body.fecha_pago ?? null,
      pagado: false,
      cuota_actual: null,
      cuota_total: null,
    };
    estado.agregar("/gastos", gasto);
    return creado(gasto);
  }

  const preview = /^\/periodos\/([\d-]+)\/preview$/.exec(ruta);
  if (method === "POST" && preview) return armarPreview(estado, preview[1]);

  const cierre = /^\/periodos\/([\d-]+)\/cerrar$/.exec(ruta);
  if (method === "POST" && cierre) return cerrarPeriodo(estado, cierre[1], body);

  return null;
}

function codigoDe(estado, deptoId) {
  return (estado.leer("/departamentos") ?? []).find((d) => d.id === deptoId)?.codigo ?? null;
}

function siguienteIdDeMovimiento(movimientos) {
  return Math.max(0, ...movimientos.map((m) => m.id ?? 0)) + 1;
}

/**
 * Asienta el pago en la cuenta corriente y recalcula todo lo que depende de
 * ella: el saldo, el estado de cada expensa y la lista de morosos.
 *
 * El backend hace lo mismo: no guarda el estado de una expensa, lo deduce de
 * los movimientos. Acá se recalcula en el momento por la misma razón — así no
 * hay dos verdades que puedan separarse.
 */
function registrarPago(estado, comprobante) {
  const cuenta = estado.leer(`/departamentos/${comprobante.departamento_id}/cuenta`);
  if (!cuenta) return;

  cuenta.movimientos.unshift({
    id: siguienteIdDeMovimiento(cuenta.movimientos),
    tipo: "pago_recibido",
    monto: comprobante.monto,
    fecha: comprobante.fecha_pago,
    descripcion: `Pago ${comprobante.departamento_codigo ?? ""} - ${comprobante.fecha_pago}`,
    expensa_id: null,
  });

  const misExpensas = (estado.leer("/expensas") ?? []).filter(
    (e) => e.departamento_id === comprobante.departamento_id,
  );
  const { saldo, porExpensa } = imputar(misExpensas, cuenta.movimientos);

  cuenta.saldo_total = saldo;
  for (const expensa of misExpensas) {
    const estadoExpensa = porExpensa.get(expensa.id);
    if (!estadoExpensa) continue;
    expensa.monto_pendiente = estadoExpensa.pendiente;
    expensa.estado_calculado = estadoExpensa.estado;
  }

  const morosos = estado.leer("/reportes/morosos") ?? [];
  estado.reemplazar(
    "/reportes/morosos",
    saldo > 0.005
      ? morosos.map((m) =>
          m.departamento_id === comprobante.departamento_id ? { ...m, saldo } : m,
        )
      : morosos.filter((m) => m.departamento_id !== comprobante.departamento_id),
  );
}

function coeficientesPorDepto(estado) {
  const mapa = new Map();
  for (const depto of estado.leer("/departamentos") ?? []) {
    mapa.set(depto.id, estado.leer(`/departamentos/${depto.id}/coeficientes`) ?? []);
  }
  return mapa;
}

/**
 * Lo que el administrador ve antes de confirmar el cierre: cuánto se va a
 * expensar, a cuántas unidades, y qué conviene mirar antes.
 *
 * Las validaciones son las simples —las que salen de mirar el estado— porque
 * son parte del momento en que el sistema muestra criterio. Las elaboradas las
 * trae el dataset y no se recalculan (spec §5.2).
 */
function armarPreview(estado, periodo) {
  const gastos = (estado.leer("/gastos") ?? []).filter((g) => g.periodo === periodo);
  const repartido = repartir(gastos, coeficientesPorDepto(estado));

  const validaciones = [];
  if (gastos.length === 0) {
    validaciones.push({
      tipo: "warning",
      codigo: "sin_gastos",
      mensaje: `El período ${periodo} no tiene gastos cargados. Las expensas serán $0.`,
    });
  }
  for (const clase of estado.leer("/clases-prorrateo") ?? []) {
    if (!gastos.some((g) => g.clase_prorrateo_id === clase.id)) {
      validaciones.push({
        tipo: "warning",
        codigo: "clases_sin_gastos",
        mensaje: `La clase '${clase.nombre}' está activa pero no tiene gastos en el período (no se prorratea).`,
      });
    }
  }

  const expensas = [...repartido.entries()].map(([departamento_id, r]) => ({
    departamento_id,
    monto_primer_vencimiento: r.total,
    saldo_anterior: estado.leer(`/departamentos/${departamento_id}/cuenta`)?.saldo_total ?? 0,
    detalle: r.lineas,
  }));

  return ok({
    periodo,
    expensas,
    total_expensado: dos(expensas.reduce((a, e) => a + e.monto_primer_vencimiento, 0)),
    total_intereses: 0,
    validaciones,
    puede_cerrar: true,
  });
}

/** Emite las expensas del período y las asienta en cada cuenta corriente. */
function cerrarPeriodo(estado, periodo, body) {
  const yaCerrado = (estado.leer("/periodos") ?? []).some((p) => p.periodo === periodo);
  if (yaCerrado) return conflicto(`El período ${periodo} ya fue cerrado.`);

  const previa = armarPreview(estado, periodo);
  const f1 = body?.fecha_primer_vencimiento ?? null;
  const f2 = body?.fecha_segundo_vencimiento ?? null;

  for (const linea of previa.data.expensas) {
    const expensa = {
      id: estado.siguienteId("/expensas"),
      departamento_id: linea.departamento_id,
      periodo,
      monto_primer_vencimiento: linea.monto_primer_vencimiento,
      fecha_primer_vencimiento: f1,
      monto_segundo_vencimiento: dos(linea.monto_primer_vencimiento * 1.07),
      fecha_segundo_vencimiento: f2,
      saldo_anterior: linea.saldo_anterior,
      estado_calculado: "pendiente",
      monto_pendiente: linea.monto_primer_vencimiento,
      monto_exigible: linea.monto_primer_vencimiento,
      interes_acumulado: 0,
      detalle: linea.detalle,
    };
    estado.agregar("/expensas", expensa);

    const cuenta = estado.leer(`/departamentos/${linea.departamento_id}/cuenta`);
    if (cuenta) {
      cuenta.movimientos.unshift({
        id: siguienteIdDeMovimiento(cuenta.movimientos),
        tipo: "expensa_emitida",
        monto: linea.monto_primer_vencimiento,
        fecha: f1,
        descripcion: `Expensa ${periodo}`,
        expensa_id: expensa.id,
      });
      cuenta.saldo_total = saldoDeMovimientos(cuenta.movimientos);
    }
  }

  const cerrado = {
    periodo,
    fecha_cierre: ahora(),
    cerrado_por_usuario_id: 1,
    total_expensado: previa.data.total_expensado,
    total_intereses: 0,
    cantidad_expensas: previa.data.expensas.length,
  };
  estado.agregar("/periodos", cerrado);
  return creado(cerrado);
}
