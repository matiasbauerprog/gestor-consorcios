import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import Login from "./screens/Login";
import CambiarPassword from "./screens/CambiarPassword";
import AdministracionConsorcios from "./screens/AdministracionConsorcios";
import WizardNuevoConsorcio from "./screens/WizardNuevoConsorcio";
import SuperAdminAdministraciones from "./screens/SuperAdminAdministraciones";
import SuperAdminMetricas from "./screens/SuperAdminMetricas";
import SuperAdminAuditLog from "./screens/SuperAdminAuditLog";
import Comunicados from "./screens/Comunicados";
import Expensas from "./screens/Expensas";
import Comprobantes from "./screens/Comprobantes";
import Gastos from "./screens/Gastos";
import GastosHabituales from "./screens/GastosHabituales";
import Configuracion from "./screens/Configuracion";
import ClasesProrrateo from "./screens/ClasesProrrateo";
import Proveedores from "./screens/Proveedores";
import Padron from "./screens/Padron";
import Empleados from "./screens/Empleados";
import Haberes from "./screens/Haberes";
import ConceptosLiquidacion from "./screens/ConceptosLiquidacion";
import Liquidaciones from "./screens/Liquidaciones";
import MiCuenta from "./screens/MiCuenta";
import DepartamentoCuenta from "./screens/DepartamentoCuenta";
import CuentasCorrientes from "./screens/CuentasCorrientes";
import CierreDePeriodo from "./screens/CierreDePeriodo";
import Tesoreria from "./screens/Tesoreria";
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
import Inicio from "./screens/Inicio";
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

function InicioRoute() {
  const { user } = useAuth();
  if (user.rol === "departamento") return <Navigate to="/mi-cuenta" replace />;
  if (user.rol === "representante") return <Navigate to="/comunicados" replace />;
  // super_admin no tiene consorcio activo: Inicio dispararía endpoints
  // admin-only contra 403. Va a su propia pantalla.
  if (user.rol === "super_admin") {
    return <Navigate to="/super-admin/administraciones" replace />;
  }
  return <Inicio />;
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
            <Route index element={<InicioRoute />} />
            <Route path="comunicados" element={<Comunicados />} />
            <Route path="expensas" element={<ExpensasRoute />} />
            <Route path="mi-cuenta" element={<MiCuentaRoute />} />
            <Route path="departamentos/:id/cuenta" element={<DepartamentoCuenta />} />
            <Route path="cuentas-corrientes" element={<CuentasCorrientes />} />
            <Route path="comprobantes" element={<ComprobantesRoute />} />
            <Route path="cierre-de-periodo" element={<CierreDePeriodo />} />
            <Route path="periodos" element={<Navigate to="/cobranzas?tab=cierres" replace />} />
            <Route path="gastos" element={<Gastos />} />
            <Route path="gastos/habituales" element={<GastosHabituales />} />
            <Route path="configuracion" element={<Configuracion />} />
            <Route path="clases-prorrateo" element={<ClasesProrrateo />} />
            <Route path="proveedores" element={<Proveedores />} />
            <Route path="padron" element={<Padron />} />
            <Route path="departamentos" element={<Navigate to="/padron?tab=departamentos" replace />} />
            <Route path="usuarios" element={<Navigate to="/padron?tab=usuarios" replace />} />
            <Route path="empleados" element={<Empleados />} />
            <Route path="haberes" element={<Haberes />} />
            <Route path="conceptos-liquidacion" element={<ConceptosLiquidacion />} />
            <Route path="liquidaciones" element={<Liquidaciones />} />
            <Route path="liquidaciones/historial" element={<Liquidaciones vistaHistorial />} />
            <Route path="tesoreria" element={<Tesoreria />} />
            <Route path="estado-financiero" element={<Navigate to="/tesoreria?tab=estado" replace />} />
            <Route path="cajas" element={<Navigate to="/tesoreria?tab=cajas" replace />} />
            <Route path="transferencias" element={<Navigate to="/tesoreria?tab=transferencias" replace />} />
            <Route path="reportes/morosos" element={<ReporteMorosos />} />
            <Route path="reportes/estado-financiero" element={<ReporteEstadoFinanciero />} />
            <Route path="reportes/gastos" element={<ReporteGastosPeriodo />} />
            <Route path="reportes/proveedores" element={<ReporteProveedores />} />
            <Route path="peticiones" element={<Peticiones />} />
            <Route path="trabajos" element={<Trabajos />} />
            <Route path="trabajos-recurrentes" element={<TrabajosRecurrentes />} />
            <Route path="amenities" element={<Amenities />} />
            <Route path="reservas" element={<Reservas />} />
            <Route path="reglamento" element={<Navigate to="/comunicados?tab=reglamento" replace />} />
            <Route path="cobranzas" element={<CobranzasRoute />} />
            <Route path="mi-usuario/cambiar-password" element={<CambiarPassword />} />
            <Route path="administracion/consorcios" element={<AdministracionConsorcios />} />
            <Route path="administracion/consorcios/nuevo" element={<WizardNuevoConsorcio />} />
            <Route path="super-admin/administraciones" element={<SuperAdminAdministraciones />} />
            <Route path="super-admin/metricas" element={<SuperAdminMetricas />} />
            <Route path="super-admin/audit-log" element={<SuperAdminAuditLog />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
