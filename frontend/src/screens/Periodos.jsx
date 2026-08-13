import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarPeriodos } from "../api/periodos";
import ModalEnvioPdfs from "../components/ModalEnvioPdfs";
import TablaResponsive from "../components/TablaResponsive";
import Tarjeta from "../components/Tarjeta";
import { formatFechaHora } from "../utils/fechas";
import { ANCHO_MONTO, ANCHO_PERIODO } from "../utils/anchosColumnas";

function formatMoney(n) {
  return Number(n).toLocaleString("es-AR", {
    style: "currency", currency: "ARS", maximumFractionDigits: 0,
  });
}

export default function Periodos() {
  const [periodos, setPeriodos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [modalEnvio, setModalEnvio] = useState(null);

  useEffect(() => {
    (async () => {
      const r = await listarPeriodos();
      if (r.status === 200) setPeriodos(r.data);
      setCargando(false);
    })();
  }, []);

  if (cargando) return <p>Cargando…</p>;

  return (
    <section>
      <h2>Historial de cierres</h2>
      <TablaResponsive
        columnas={[
          { clave: "periodo", titulo: "Período", ancho: ANCHO_PERIODO, celda: (p) => p.periodo },
          {
            clave: "cerrado",
            titulo: "Cerrado el",
            prioridad: 2,
            ancho: "auto",
            celda: (p) => formatFechaHora(p.fecha_cierre),
          },
          {
            clave: "boletas",
            titulo: "Boletas",
            prioridad: 3,
            ancho: "9ch",
            className: "col-monto",
            celda: (p) => p.cantidad_expensas,
          },
          {
            clave: "total",
            titulo: "Total expensado",
            className: "col-monto",
            ancho: ANCHO_MONTO,
            celda: (p) => formatMoney(p.total_expensado),
          },
          {
            clave: "intereses",
            titulo: "Intereses",
            prioridad: 3,
            className: "col-monto",
            ancho: ANCHO_MONTO,
            celda: (p) => formatMoney(p.total_intereses),
          },
          {
            clave: "acciones",
            titulo: "",
            className: "col-acciones",
            ancho: "11rem",
            celda: (p) => (
              <>
                <Link to={`/expensas?periodo=${p.periodo}`}>Ver expensas</Link>{" "}
                <button
                  type="button"
                  onClick={() => setModalEnvio({
                    periodo: p.periodo,
                    cantidadExpensas: p.cantidad_expensas,
                    periodoCerrado: true,
                  })}
                >
                  ✉ Enviar PDFs
                </button>
              </>
            ),
          },
        ]}
        filas={periodos}
        claveFila={(p) => p.periodo}
        vacio="Todavía no hay períodos cerrados."
        renderTarjeta={(p) => (
          <Tarjeta>
            <h3>{p.periodo}</h3>
            <p className="meta">Cerrado el {formatFechaHora(p.fecha_cierre)}</p>
            <p className="meta">
              {p.cantidad_expensas} boletas · {formatMoney(p.total_expensado)}
            </p>
            <p className="meta">Intereses: {formatMoney(p.total_intereses)}</p>
            <div className="tarjeta-acciones">
              <Link to={`/expensas?periodo=${p.periodo}`}>Ver expensas</Link>
              <button
                type="button"
                onClick={() => setModalEnvio({
                  periodo: p.periodo,
                  cantidadExpensas: p.cantidad_expensas,
                  periodoCerrado: true,
                })}
              >
                ✉ Enviar PDFs
              </button>
            </div>
          </Tarjeta>
        )}
      />
      {modalEnvio && (
        <ModalEnvioPdfs
          periodo={modalEnvio.periodo}
          periodoCerrado={modalEnvio.periodoCerrado}
          cantidadExpensas={modalEnvio.cantidadExpensas}
          onClose={() => setModalEnvio(null)}
        />
      )}
    </section>
  );
}
