import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import Login from "./screens/Login";
import Comunicados from "./screens/Comunicados";
import Expensas from "./screens/Expensas";
import Comprobantes from "./screens/Comprobantes";
import Gastos from "./screens/Gastos";
import GastosHabituales from "./screens/GastosHabituales";
import Configuracion from "./screens/Configuracion";
import ClasesProrrateo from "./screens/ClasesProrrateo";
import Proveedores from "./screens/Proveedores";
import Departamentos from "./screens/Departamentos";
import Empleados from "./screens/Empleados";
import Haberes from "./screens/Haberes";
import ConceptosLiquidacion from "./screens/ConceptosLiquidacion";
import Liquidaciones from "./screens/Liquidaciones";
import MiCuenta from "./screens/MiCuenta";
import DepartamentoCuenta from "./screens/DepartamentoCuenta";
import CierreDePeriodo from "./screens/CierreDePeriodo";
import Periodos from "./screens/Periodos";
import EstadoFinanciero from "./screens/EstadoFinanciero";
import Cajas from "./screens/Cajas";
import Transferencias from "./screens/Transferencias";
import ReporteMorosos from "./screens/ReporteMorosos";
import ReporteEstadoFinanciero from "./screens/ReporteEstadoFinanciero";
import ReporteGastosPeriodo from "./screens/ReporteGastosPeriodo";
import ReporteProveedores from "./screens/ReporteProveedores";
import Peticiones from "./screens/Peticiones";
import Trabajos from "./screens/Trabajos";
import TrabajosRecurrentes from "./screens/TrabajosRecurrentes";
import Amenities from "./screens/Amenities";
import Cobranzas from "./screens/Cobranzas";
import Reservas from "./screens/Reservas";
import Reglamento from "./screens/Reglamento";
import NotFound from "./screens/NotFound";

function ExpensasRoute() {
  const { user } = useAuth();
  if (user.rol === "departamento") {
    return <Navigate to="/mi-cuenta?tab=expensas" replace />;
  }
  if (user.rol === "administracion") {
    return <Navigate to="/cobranzas?tab=expensas" replace />;
  }
  return <Expensas />;
}

function ComprobantesRoute() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  if (user.rol === "departamento") {
    return <Navigate to="/mi-cuenta?tab=comprobantes" replace />;
  }
  if (user.rol === "administracion") {
    const params = new URLSearchParams(searchParams);
    params.set("tab", "comprobantes");
    return <Navigate to={`/cobranzas?${params.toString()}`} replace />;
  }
  return <Comprobantes />;
}

function CobranzasRoute() {
  const { user } = useAuth();
  if (user.rol !== "administracion") {
    return <Navigate to="/" replace />;
  }
  return <Cobranzas />;
}

function MiCuentaRoute() {
  const { user } = useAuth();
  if (user.rol !== "departamento") {
    return <Navigate to="/" replace />;
  }
  return <MiCuenta />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/comunicados" replace />} />
            <Route path="comunicados" element={<Comunicados />} />
            <Route path="expensas" element={<ExpensasRoute />} />
            <Route path="mi-cuenta" element={<MiCuentaRoute />} />
            <Route path="departamentos/:id/cuenta" element={<DepartamentoCuenta />} />
            <Route path="comprobantes" element={<ComprobantesRoute />} />
            <Route path="cierre-de-periodo" element={<CierreDePeriodo />} />
            <Route path="periodos" element={<Periodos />} />
            <Route path="gastos" element={<Gastos />} />
            <Route path="gastos/habituales" element={<GastosHabituales />} />
            <Route path="configuracion" element={<Configuracion />} />
            <Route path="clases-prorrateo" element={<ClasesProrrateo />} />
            <Route path="proveedores" element={<Proveedores />} />
            <Route path="departamentos" element={<Departamentos />} />
            <Route path="empleados" element={<Empleados />} />
            <Route path="haberes" element={<Haberes />} />
            <Route path="conceptos-liquidacion" element={<ConceptosLiquidacion />} />
            <Route path="liquidaciones" element={<Liquidaciones />} />
            <Route path="liquidaciones/historial" element={<Liquidaciones vistaHistorial />} />
            <Route path="estado-financiero" element={<EstadoFinanciero />} />
            <Route path="cajas" element={<Cajas />} />
            <Route path="transferencias" element={<Transferencias />} />
            <Route path="reportes/morosos" element={<ReporteMorosos />} />
            <Route path="reportes/estado-financiero" element={<ReporteEstadoFinanciero />} />
            <Route path="reportes/gastos" element={<ReporteGastosPeriodo />} />
            <Route path="reportes/proveedores" element={<ReporteProveedores />} />
            <Route path="peticiones" element={<Peticiones />} />
            <Route path="trabajos" element={<Trabajos />} />
            <Route path="trabajos-recurrentes" element={<TrabajosRecurrentes />} />
            <Route path="amenities" element={<Amenities />} />
            <Route path="reservas" element={<Reservas />} />
            <Route path="reglamento" element={<Reglamento />} />
            <Route path="cobranzas" element={<CobranzasRoute />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
