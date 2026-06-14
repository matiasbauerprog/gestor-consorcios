import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { listarExpensas } from "../api/expensas";
import SelectorDepartamento from "../components/SelectorDepartamento";
import BadgeEstado from "../components/BadgeEstado";
import Tarjeta from "../components/Tarjeta";

function estaVencida(expensa, hoy = new Date()) {
  if (expensa.estado !== "pendiente") return false;
  const venc = new Date(expensa.fecha_vencimiento + "T00:00:00");
  return venc < new Date(hoy.toISOString().slice(0, 10) + "T00:00:00");
}

function leyendaDeExpensa(expensa) {
  if (expensa.estado === "pagada") return null;
  const uc = expensa.ultimo_comprobante;
  if (!uc) return "Aún no presentó comprobante";
  if (uc.estado === "pendiente_verificacion") return "Comprobante pendiente de verificación";
  if (uc.estado === "rechazado") return "Último comprobante rechazado";
  return null;
}

function formatearMonto(v) {
  return v.toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
}

function TarjetaExpensa({ expensa, rol, onPresentar, onConfirmar, onVer }) {
  const vencida = estaVencida(expensa);
  const leyenda = leyendaDeExpensa(expensa);
  const uc = expensa.ultimo_comprobante;
  const esAdmin = rol === "administracion";
  const esDepto = rol === "departamento";

  let boton = null;
  if (expensa.estado === "pagada") {
    boton = <button type="button" onClick={onVer}>Ver comprobante</button>;
  } else if (!uc && esDepto) {
    boton = <button type="button" onClick={onPresentar}>Presentar comprobante</button>;
  } else if (uc?.estado === "rechazado" && esDepto) {
    boton = <button type="button" onClick={onPresentar}>Presentar otro comprobante</button>;
  } else if (uc?.estado === "pendiente_verificacion" && esAdmin) {
    boton = <button type="button" onClick={onConfirmar}>Confirmar</button>;
  }

  return (
    <Tarjeta>
      <h3>{expensa.periodo} — {formatearMonto(expensa.monto)}</h3>
      <p className="meta">Vence {expensa.fecha_vencimiento}</p>
      <p>
        <BadgeEstado estado={expensa.estado} vencida={vencida} />
      </p>
      {leyenda && <p className="leyenda">ⓘ {leyenda}</p>}
      {boton && <div className="tarjeta-acciones">{boton}</div>}
    </Tarjeta>
  );
}

export default function Expensas() {
  const { user } = useAuth();
  const [expensas, setExpensas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);
  const [departamentoSeleccionado, setDepartamentoSeleccionado] = useState(null);

  const esAdmin = user.rol === "administracion";

  useEffect(() => {
    if (esAdmin && departamentoSeleccionado === null) {
      setExpensas([]);
      return;
    }

    let cancelado = false;
    setCargando(true);

    async function cargar() {
      const params = esAdmin ? { departamento_id: departamentoSeleccionado } : {};
      const r = await listarExpensas(params);
      if (cancelado) return;
      if (r.status === 200) {
        setExpensas(r.data);
        setErrorCarga(null);
      } else if (r.status !== 401) {
        setErrorCarga("No se pudieron cargar las expensas.");
      }
      setCargando(false);
    }

    cargar();
    return () => {
      cancelado = true;
    };
  }, [esAdmin, departamentoSeleccionado]);

  return (
    <section>
      <header className="seccion-header">
        <h2>Expensas</h2>
        {esAdmin && (
          <div className="seccion-acciones">
            <SelectorDepartamento
              valor={departamentoSeleccionado}
              onChange={setDepartamentoSeleccionado}
              permitirVacio={false}
            />
          </div>
        )}
      </header>

      {esAdmin && departamentoSeleccionado === null && (
        <p>Elegí un departamento para ver sus expensas.</p>
      )}

      {cargando && <p>Cargando…</p>}
      {errorCarga && <p role="alert" className="error-banner">{errorCarga}</p>}
      {!cargando && !errorCarga && expensas.length === 0 &&
        (!esAdmin || departamentoSeleccionado !== null) && (
          <p>No hay expensas para mostrar.</p>
        )}

      <ul className="lista-expensas">
        {expensas.map((e) => (
          <li key={e.id}>
            <TarjetaExpensa
              expensa={e}
              rol={user.rol}
              onPresentar={() => {}}
              onConfirmar={() => {}}
              onVer={() => {}}
            />
          </li>
        ))}
      </ul>

      <p>
        <Link to="/comprobantes">Ver todos los comprobantes →</Link>
      </p>
    </section>
  );
}
