import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
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
import NotFound from "./screens/NotFound";

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
            <Route path="expensas" element={<Expensas />} />
            <Route path="mi-cuenta" element={<MiCuenta />} />
            <Route path="departamentos/:id/cuenta" element={<DepartamentoCuenta />} />
            <Route path="comprobantes" element={<Comprobantes />} />
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
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
