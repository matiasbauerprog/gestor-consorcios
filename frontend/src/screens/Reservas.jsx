import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listarAmenities } from "../api/amenities";
import { listarReservas, crearReserva, cancelarReserva } from "../api/reservas";
import { useAuth } from "../auth/AuthContext";
import { formatFecha } from "../utils/fechas";
import TablaResponsive from "../components/TablaResponsive";

function fmtFecha(iso) {
  return new Date(iso).toLocaleString("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

/** Suma N días a "YYYY-MM-DD" y devuelve "YYYY-MM-DD" — evita problemas con
 *  fusos horarios que introduce `new Date()` con strings ISO cortos. */
function sumarDias(fecha, dias) {
  const [y, m, d] = fecha.split("-").map(Number);
  const dt = new Date(y, m - 1, d + dias);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

export default function Reservas() {
  const { user } = useAuth();
  const esAdmin = user?.rol === "administracion";
  const esDepto = user?.rol === "departamento";

  const [amenities, setAmenities] = useState([]);
  const [amenityId, setAmenityId] = useState("");
  const [reservas, setReservas] = useState([]);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  // Form state
  const [fecha, setFecha] = useState("");
  const [horaInicio, setHoraInicio] = useState("");
  const [horaFin, setHoraFin] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [bannerAbierto, setBannerAbierto] = useState(false);

  async function cargarAmenities() {
    const r = await listarAmenities();
    if (r.status === 200) {
      setAmenities(r.data);
      if (!amenityId && r.data.length > 0) setAmenityId(String(r.data[0].id));
    }
  }

  async function cargarReservas() {
    const r = await listarReservas();
    if (r.status === 200) setReservas(r.data);
  }

  useEffect(() => {
    cargarAmenities();
    cargarReservas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const amenitySeleccionado = useMemo(
    () => amenities.find((a) => String(a.id) === amenityId) || null,
    [amenities, amenityId]
  );

  const ahora = useMemo(() => new Date(), []);

  const proximasDelAmenity = useMemo(() => {
    return reservas.filter(
      (r) =>
        String(r.amenity_id) === amenityId &&
        r.estado === "confirmada" &&
        new Date(r.inicio) > ahora
    );
  }, [reservas, amenityId, ahora]);

  const misReservas = useMemo(() => {
    if (!esDepto) return [];
    return reservas.filter((r) => r.usuario_id === user.id).slice(0, 20);
  }, [reservas, esDepto, user]);

  async function handleCancelar(r) {
    setError("");
    setInfo("");
    const horasHasta = (new Date(r.inicio) - ahora) / 36e5;
    const plazo = amenitySeleccionado?.horas_minimas_cancelacion;
    if (plazo !== null && plazo !== undefined && horasHasta < plazo) {
      if (
        !window.confirm(
          `Estás cancelando con menos de ${plazo}h de anticipación. NO se reintegrará el monto. ¿Confirmás?`
        )
      )
        return;
    } else {
      if (!window.confirm("¿Cancelar esta reserva?")) return;
    }
    const rc = await cancelarReserva(r.id);
    if (rc.status === 200) {
      setInfo("Reserva cancelada.");
      cargarReservas();
    } else {
      setError(rc.data?.detail || "Error al cancelar.");
    }
  }

  async function handleCrear(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (!fecha || !horaInicio || !horaFin) {
      setError("Completá fecha y horarios.");
      return;
    }
    if (horaFin === horaInicio) {
      setError("La hora de fin debe ser distinta al inicio.");
      return;
    }
    // Cross-midnight: si el fin es menor o igual al inicio, se asume que
    // termina al día siguiente (típico de reservas nocturnas de SUM/quincho).
    const inicio = `${fecha}T${horaInicio}:00`;
    const fechaFin = horaFin < horaInicio ? sumarDias(fecha, 1) : fecha;
    const fin = `${fechaFin}T${horaFin}:00`;

    const dur = (new Date(fin) - new Date(inicio)) / 36e5;
    if (
      amenitySeleccionado?.duracion_maxima_horas !== null &&
      amenitySeleccionado?.duracion_maxima_horas !== undefined &&
      dur > amenitySeleccionado.duracion_maxima_horas
    ) {
      setError(
        `Duración supera el máximo permitido (${amenitySeleccionado.duracion_maxima_horas}h).`
      );
      return;
    }

    setGuardando(true);
    const r = await crearReserva(amenitySeleccionado.id, { inicio, fin });
    setGuardando(false);
    if (r.status === 201) {
      setInfo("Reserva creada.");
      setFecha("");
      setHoraInicio("");
      setHoraFin("");
      cargarReservas();
    } else {
      setError(r.data?.detail || "Error al reservar.");
    }
  }

  return (
    <main>
      <header className="cabecera-pantalla">
        <h2>Reservas</h2>
        {esAdmin && <Link to="/amenities">Gestionar amenities</Link>}
      </header>

      <section className="filtros">
        <label>
          Amenity:{" "}
          <select value={amenityId} onChange={(e) => setAmenityId(e.target.value)}>
            {amenities.map((a) => (
              <option key={a.id} value={a.id}>
                {a.nombre}
              </option>
            ))}
          </select>
        </label>
      </section>

      {info && <p className="info">{info}</p>}
      {error && <p className="error">{error}</p>}

      <div className="reservas-grid">
        <div className="reservas-col-form">
          {amenitySeleccionado && (
            <section className={`banner-politicas${bannerAbierto ? " abierto" : ""}`}>
              <header onClick={() => setBannerAbierto(!bannerAbierto)}>
                <strong>{amenitySeleccionado.nombre}</strong>{" "}
                {amenitySeleccionado.precio_reserva
                  ? `— $${Number(amenitySeleccionado.precio_reserva).toLocaleString("es-AR")} por reserva`
                  : "— gratis"}{" "}
                <span className="banner-toggle">{bannerAbierto ? "▲" : "▼"}</span>
              </header>
              {bannerAbierto && (
                <ul>
                  {amenitySeleccionado.duracion_maxima_horas && (
                    <li>Duración máx: {amenitySeleccionado.duracion_maxima_horas}h</li>
                  )}
                  {amenitySeleccionado.anticipacion_maxima_dias && (
                    <li>
                      Reservable hasta {amenitySeleccionado.anticipacion_maxima_dias} días en el futuro
                    </li>
                  )}
                  {amenitySeleccionado.max_reservas_activas_por_depto && (
                    <li>
                      Máx {amenitySeleccionado.max_reservas_activas_por_depto} reservas activas por depto
                    </li>
                  )}
                  {amenitySeleccionado.horas_minimas_cancelacion !== null &&
                  amenitySeleccionado.horas_minimas_cancelacion !== undefined ? (
                    <li>
                      Cancelación con reintegro: hasta {amenitySeleccionado.horas_minimas_cancelacion}h antes
                    </li>
                  ) : (
                    <li>Cancelable en cualquier momento</li>
                  )}
                </ul>
              )}
            </section>
          )}

          {amenitySeleccionado && (
            <form onSubmit={handleCrear} className="form-reserva">
              <h3>Nueva reserva</h3>
              <label>
                Fecha{" "}
                <input
                  type="date"
                  value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                  required
                />
              </label>
              <label>
                Hora inicio{" "}
                <input
                  type="time"
                  value={horaInicio}
                  onChange={(e) => setHoraInicio(e.target.value)}
                  required
                />
              </label>
              <label>
                Hora fin{" "}
                <input
                  type="time"
                  value={horaFin}
                  onChange={(e) => setHoraFin(e.target.value)}
                  required
                />
              </label>
              {fecha && horaInicio && horaFin && horaFin < horaInicio && (
                <p className="meta" style={{ marginTop: "0.25rem" }}>
                  🌙 Termina el día siguiente ({formatFecha(sumarDias(fecha, 1))}) a las {horaFin}.
                </p>
              )}
              <div className="cta-sticky">
                <button type="submit" disabled={guardando}>
                  {guardando
                    ? "Reservando…"
                    : amenitySeleccionado.precio_reserva
                    ? `Confirmar reserva ($${Number(amenitySeleccionado.precio_reserva).toLocaleString("es-AR")})`
                    : "Confirmar reserva"}
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="reservas-col-listas">
          <section>
            <h3>Próximas reservas (todos los deptos)</h3>
            <TablaResponsive
              columnas={[
                { clave: "inicio", titulo: "Desde", prioridad: 1, ancho: "auto", celda: (r) => fmtFecha(r.inicio) },
                { clave: "fin", titulo: "Hasta", prioridad: 1, ancho: "auto", celda: (r) => fmtFecha(r.fin) },
                { clave: "usuario", titulo: "Depto", prioridad: 1, ancho: "auto", celda: (r) => `#${r.usuario_id}` },
              ]}
              filas={proximasDelAmenity}
              claveFila={(r) => r.id}
              vacio="Sin próximas reservas."
              renderTarjeta={(r) => (
                <article className="tarjeta">
                  <h4>{fmtFecha(r.inicio)} → {fmtFecha(r.fin)}</h4>
                  <p>Depto del usuario #{r.usuario_id}</p>
                </article>
              )}
            />
          </section>

          {esDepto && (
            <section>
              <h3>Mis reservas</h3>
              <TablaResponsive
                columnas={[
                  { clave: "inicio", titulo: "Desde", prioridad: 1, ancho: "auto", celda: (r) => fmtFecha(r.inicio) },
                  { clave: "fin", titulo: "Hasta", prioridad: 1, ancho: "auto", celda: (r) => fmtFecha(r.fin) },
                  {
                    clave: "estado",
                    titulo: "Estado",
                    prioridad: 1,
                    ancho: "auto",
                    celda: (r) => `${r.estado}${r.movimiento_cuenta_id ? " — con cargo" : ""}`,
                  },
                  {
                    clave: "acciones",
                    titulo: "",
                    className: "col-acciones",
                    prioridad: 1,
                    ancho: "7rem",
                    celda: (r) =>
                      r.estado === "confirmada" && new Date(r.inicio) > ahora ? (
                        <button type="button" onClick={() => handleCancelar(r)}>
                          Cancelar
                        </button>
                      ) : null,
                  },
                ]}
                filas={misReservas}
                claveFila={(r) => r.id}
                vacio="No tenés reservas."
                renderTarjeta={(r) => (
                  <article className={`tarjeta${r.estado === "confirmada" ? "" : " cancelada"}`}>
                    <h4>{fmtFecha(r.inicio)} → {fmtFecha(r.fin)}</h4>
                    <p>
                      Estado: {r.estado}
                      {r.movimiento_cuenta_id ? " — con cargo" : ""}
                    </p>
                    {r.estado === "confirmada" && new Date(r.inicio) > ahora && (
                      <button type="button" onClick={() => handleCancelar(r)}>
                        Cancelar
                      </button>
                    )}
                  </article>
                )}
              />
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
