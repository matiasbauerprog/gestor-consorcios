import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { nombreDeUsuario } from "../components/SheetCuenta";
import { listarExpensas } from "../api/expensas";
import { obtenerGastosDelPeriodo, listarMorosos } from "../api/reportes";
import { listarPeticiones } from "../api/peticiones";
import { estadoPeriodo, listarPeriodos } from "../api/periodos";
import { periodoDelTablero } from "../utils/periodoDelTablero";
import { obtenerResumenTesoreria } from "../api/tesoreria";
import { listarGastos } from "../api/gastos";
import { listarGastosHabituales } from "../api/gastosHabituales";
import { listarReservas } from "../api/reservas";
import { listarAmenities } from "../api/amenities";
import { actividadReciente, proximosVencimientos } from "../utils/tablero";
import { mayusculaInicial, pluralizar } from "../utils/textos";

/** Devuelve r.data si la respuesta fue OK; si no, el fallback. */
function datos(r, fallback) {
  return r?.ok && r.data != null ? r.data : fallback;
}

function money(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });
}

/** Cifra del hero: el valor formateado si la fuente respondió OK, o un
 * em-dash muted si no — para que "no disponible" nunca se lea como "$0". */
function cifra(disponible, valorFormateado) {
  return disponible ? valorFormateado : <span className="inicio-dato-ausente">—</span>;
}

/** "2026-08-05" → "05 ago". Fija el mediodía para evitar el corrimiento de
 * un día que provocan las fechas ISO sin hora al parsearlas como UTC. */
function fechaCorta(iso) {
  if (!iso) return "";
  const s = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00` : iso;
  const d = new Date(s);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
}

/** YYYY-MM del calendario LOCAL. `toISOString()` opera en UTC: en Argentina
 * (UTC-3) las últimas ~3 horas de un día de fin de mes ya caen en el mes
 * siguiente en UTC, lo que devolvería el período equivocado. */
function periodoActual() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/** Días transcurridos entre hoy (calendario local) y una fecha "YYYY-MM-DD",
 * comparando ambas como fechas de calendario puras (sin componente horario
 * ni corrimiento de huso) para que el corte de 60 días sea exacto. */
function diasDesde(fechaISO) {
  const hoy = new Date();
  const hoyUTC = Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
  const [anio, mes, dia] = fechaISO.split("-").map(Number);
  const fechaUTC = Date.UTC(anio, mes - 1, dia);
  return (hoyUTC - fechaUTC) / 86400000;
}

export default function Inicio() {
  const { user, consorciosAccesibles, consorcioActivoId } = useAuth();
  const periodo = periodoActual();

  const [respuestas, setRespuestas] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let activo = true;

    (async () => {
      try {
        const resultados = await Promise.all([
          listarExpensas({ periodo }),
          obtenerGastosDelPeriodo(periodo),
          listarMorosos({ soloDeudores: true }),
          listarPeticiones(),
          estadoPeriodo(periodo),
          obtenerResumenTesoreria({ ultimos: 10 }),
          listarGastos({ periodo }),
          listarGastosHabituales(),
          listarReservas(),
          listarAmenities(),
          listarPeriodos(),
        ]);

        // El mes en curso no tiene expensas hasta que se cierra: mostrar ese
        // mes daría una recaudación de $0 que se lee como "no hay datos".
        // Cuando pasa, el hero muestra el último período cerrado, y hay que
        // pedir sus expensas — recién acá se sabe cuál es.
        const [expensasDelMes, , , , , , , , , , periodosCerrados] = resultados;
        const { periodo: periodoHero, esMesEnCurso } = periodoDelTablero(
          periodo,
          (expensasDelMes?.data ?? []).length,
          (periodosCerrados?.data ?? []).map((p) => p.periodo),
        );
        const [expensasHero, gastosHero] = esMesEnCurso
          ? [resultados[0], resultados[1]]
          : await Promise.all([
              listarExpensas({ periodo: periodoHero }),
              obtenerGastosDelPeriodo(periodoHero),
            ]);

        if (activo) setRespuestas({ resultados, periodoHero, esMesEnCurso, expensasHero, gastosHero });
      } catch {
        if (activo) setError("No se pudieron cargar los datos. Revisá tu conexión.");
      } finally {
        if (activo) setCargando(false);
      }
    })();

    return () => {
      activo = false;
    };
  }, [periodo]);

  if (cargando) {
    return (
      <main className="inicio">
        <p>Cargando…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="inicio">
        <p className="error-banner">{error}</p>
      </main>
    );
  }

  const { resultados, periodoHero, esMesEnCurso, expensasHero, gastosHero } = respuestas;
  const [, , morosos, peticiones, cierre, finanzas, gastos, habituales, reservas, amenities] = resultados;

  // El hero mira el período que corresponda (ver `periodoDelTablero`); el
  // resto de la pantalla sigue mirando el mes en curso.
  const expensas = expensasHero;
  const gastosRep = gastosHero;

  const expensasData = datos(expensas, []);
  const morososData = datos(morosos, []);
  const peticionesData = datos(peticiones, []);
  const finanzasData = datos(finanzas, { ultimos_movimientos: [] });
  const totalGastos = datos(gastosRep, { total_general: 0 }).total_general;
  const cierrePendiente = cierre?.ok ? !cierre.data.cerrado : false;

  // Disponibilidad real de cada fuente del hero — un 403 (módulo deshabilitado
  // para el consorcio) no es lo mismo que "el mes dio $0": el hero tiene que
  // distinguir "no disponible" de "genuinamente cero".
  const expensasOk = expensas?.ok === true;
  const gastosOk = gastosRep?.ok === true;

  const liquidado = expensasData.reduce((a, e) => a + e.monto_primer_vencimiento, 0);
  const pendiente = expensasData.reduce((a, e) => a + e.monto_pendiente, 0);
  const cobrado = liquidado - pendiente;
  const pctCobrado = liquidado > 0 ? Math.round((cobrado / liquidado) * 100) : 0;

  const morososViejos = morososData.filter((m) => {
    if (!m.primer_vencimiento_impago) return false;
    return diasDesde(m.primer_vencimiento_impago) > 60;
  });

  const peticionesAbiertas = peticionesData.filter((p) => p.estado === "abierta");

  const amenitiesData = datos(amenities, []);
  const reservasData = datos(reservas, []);
  const nombreAmenity = new Map(amenitiesData.map((a) => [a.id, a.nombre]));

  const actividad = [
    ...finanzasData.ultimos_movimientos.map((m) => ({
      fecha: m.fecha,
      titulo: m.descripcion,
      detalle: "Movimiento de caja",
      monto: m.monto,
    })),
    ...peticionesData.map((p) => ({
      fecha: p.fecha_creacion,
      titulo: p.titulo,
      detalle: "Petición",
      monto: null,
    })),
    ...reservasData.map((r) => ({
      fecha: r.inicio,
      titulo: nombreAmenity.get(r.amenity_id) ?? "Reserva",
      detalle: "Reserva",
      monto: null,
    })),
  ];
  const actividadVisible = actividadReciente(actividad, new Date());

  const gastosData = datos(gastos, []);
  const habitualesData = datos(habituales, []);

  const yaCargados = new Set(
    gastosData.filter((g) => g.gasto_habitual_id != null).map((g) => g.gasto_habitual_id)
  );
  const habitualesSinCargar = habitualesData.filter((h) => h.activa && !yaCargados.has(h.id));

  const primera = expensasData[0];
  const vencimientosDelPeriodo = primera
    ? [
        {
          fecha: primera.fecha_primer_vencimiento,
          titulo: "1er vto. expensas",
          detalle: `${expensasData.length} unidades`,
        },
        { fecha: primera.fecha_segundo_vencimiento, titulo: "2do vto. expensas", detalle: "con recargo" },
      ]
    : [];
  const vencimientos = proximosVencimientos(vencimientosDelPeriodo, new Date());

  const atencion = [
    morososViejos.length > 0 && {
      to: "/reportes/morosos",
      tono: "alerta",
      texto: `${pluralizar(morososViejos.length, "departamento")} con deuda +60 días`,
    },
    peticionesAbiertas.length > 0 && {
      to: "/peticiones",
      tono: "operacion",
      texto: `${pluralizar(peticionesAbiertas.length, "petición", "peticiones")} sin responder`,
    },
    cierrePendiente && {
      to: "/cierre-de-periodo",
      tono: "warning",
      texto: `Cierre de período ${periodo} pendiente`,
    },
  ].filter(Boolean);

  const nombreConsorcio = consorciosAccesibles.find((c) => c.id === consorcioActivoId)?.nombre;
  const fechaLarga = new Date().toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <main className="inicio">
      <p className="inicio-fecha">
        {mayusculaInicial(fechaLarga)} · {nombreConsorcio}
      </p>
      <h1>Hola, {nombreDeUsuario(user.email)}</h1>

      {(expensasOk || gastosOk) && (
        <section className="inicio-hero">
          <header>
            <p className="micro-label">
              Recaudación · {periodoHero}
              {!esMesEnCurso && " · último cierre"}
            </p>
            {expensasOk && <span className="badge badge--ok">{pctCobrado}% cobrado</span>}
          </header>
          <p className="inicio-hero-cifra monto">{cifra(expensasOk, money(cobrado))}</p>
          <dl className="inicio-hero-grid">
            <div>
              <dt>Liquidado</dt>
              <dd className="monto">{cifra(expensasOk, money(liquidado))}</dd>
            </div>
            <div>
              <dt>Pendiente</dt>
              <dd className="monto">{cifra(expensasOk, money(pendiente))}</dd>
            </div>
            <div>
              <dt>Gastos</dt>
              <dd className="monto negativo">{cifra(gastosOk, `−${money(totalGastos)}`)}</dd>
            </div>
          </dl>
        </section>
      )}

      <div className="inicio-acciones">
        <Link to="/cobranzas">Registrar pago</Link>
        <Link to="/gastos">Cargar gasto</Link>
      </div>

      {atencion.length > 0 && (
        <section className="regla-seccion">
          <p className="micro-label">Requiere tu atención</p>
          <ul className="inicio-lista">
            {atencion.map((a) => (
              <li key={a.to}>
                <Link to={a.to}>
                  <span className={`punto punto--${a.tono}`} aria-hidden="true" />
                  <span className="inicio-lista-texto">{a.texto}</span>
                  <span className="inicio-chevron" aria-hidden="true">
                    ›
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {actividadVisible.length > 0 && (
        <section className="regla-seccion inicio-actividad">
          <p className="micro-label">Actividad reciente</p>
          <ul className="inicio-lista">
            {actividadVisible.map((a, i) => (
              <li key={i}>
                <div className="inicio-lista-texto">
                  <p>{a.titulo}</p>
                  <p className="inicio-lista-detalle">{a.detalle}</p>
                </div>
                {a.monto != null && <span className="monto">{money(a.monto)}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {(vencimientos.length > 0 || habitualesSinCargar.length > 0) && (
        <section className="regla-seccion">
          {vencimientos.length > 0 && (
            <>
              <p className="micro-label">Próximos vencimientos</p>
              <ul className="inicio-lista">
                {vencimientos.map((v) => (
                  <li key={v.titulo}>
                    <span className="inicio-fecha-corta">{fechaCorta(v.fecha)}</span>
                    <div className="inicio-lista-texto">
                      <p>{v.titulo}</p>
                      <p className="inicio-lista-detalle">{v.detalle}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {habitualesSinCargar.length > 0 && (
            <>
              <p className="micro-label">Sin cargar este mes</p>
              <ul className="inicio-lista">
                {habitualesSinCargar.map((h) => (
                  <li key={h.id}>
                    <div className="inicio-lista-texto">
                      <p>{h.nombre}</p>
                    </div>
                    <span className="monto negativo">−{money(h.monto)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </main>
  );
}
