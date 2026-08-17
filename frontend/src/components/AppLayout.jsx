import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ES_DEMO } from "../api/demo";
import BannerDemo from "./BannerDemo";
import CambiadorDeRol from "./CambiadorDeRol";
import BannerImpersonate from "./BannerImpersonate";
import Sidebar from "./Sidebar";
import SidebarSuperAdmin from "./SidebarSuperAdmin";
import SelectorConsorcio from "./SelectorConsorcio";
import Campanita from "./Campanita";
import SheetCuenta from "./SheetCuenta";
import TabBar from "./TabBar";
import { useNavegacionVisible } from "../hooks/useNavegacionVisible";
import { nodoContieneRuta, moduloDeRuta, TABS_POR_ROL } from "../navegacion";

function etiquetaModulo(pathname, rol, nombreConsorcio, secciones) {
  const tab = (TABS_POR_ROL[rol] ?? []).find(
    (t) => pathname === t.ruta || (t.ruta !== "/" && pathname.startsWith(t.ruta + "/"))
  );
  if (tab) return tab.nombre;
  const nodo = secciones.find((s) => !s.ruta && nodoContieneRuta(s, pathname));
  if (nodo) return nodo.titulo;
  return nombreConsorcio ?? "Consorcios";
}

export default function AppLayout() {
  const { user, consorciosAccesibles, consorcioActivoId } = useAuth();
  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [sheetCuenta, setSheetCuenta] = useState(false);
  const location = useLocation();

  const cerrarDrawer = () => setDrawerAbierto(false);

  useEffect(() => {
    if (!drawerAbierto) return;
    function onKey(e) {
      if (e.key === "Escape") cerrarDrawer();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerAbierto]);

  const esSuperAdmin = user?.rol === "super_admin";
  const { secciones, seccionesMas, tabsVisibles } = useNavegacionVisible(user.rol);
  const modulo = moduloDeRuta(location.pathname);
  const inicial = (user.email?.[0] ?? "?").toUpperCase();
  const nombreConsorcio = consorciosAccesibles.find(
    (c) => c.id === consorcioActivoId
  )?.nombre;
  const moduloLabel = etiquetaModulo(location.pathname, user.rol, nombreConsorcio, secciones);

  return (
    <div className="app-shell" data-modulo={modulo}>
      {ES_DEMO && <BannerDemo />}
      {ES_DEMO && <CambiadorDeRol />}
      <BannerImpersonate />
      <header className="app-header">
        {esSuperAdmin && (
          <button
            type="button"
            className="hamburguesa"
            aria-label="Abrir menú"
            aria-expanded={drawerAbierto}
            onClick={() => setDrawerAbierto(true)}
          >
            ☰
          </button>
        )}
        <div className="app-header-titulo">
          <img className="app-logo" src="/logo-comand.png" alt="COMMAND" />
          <span className="app-modulo-label">{moduloLabel}</span>
        </div>
        {!esSuperAdmin && <SelectorConsorcio />}
        {!esSuperAdmin && <Campanita />}
        <button
          type="button"
          className="avatar-boton"
          aria-label="Tu cuenta"
          onClick={() => setSheetCuenta(true)}
        >
          <span aria-hidden="true">{inicial}</span>
        </button>
      </header>

      <div className="app-body">
        {drawerAbierto && (
          <div
            className="drawer-backdrop"
            onClick={cerrarDrawer}
            aria-hidden="true"
          />
        )}
        {esSuperAdmin ? (
          <SidebarSuperAdmin abierto={drawerAbierto} onCerrar={cerrarDrawer} />
        ) : (
          <Sidebar
            rol={user.rol}
            secciones={secciones}
            abierto={drawerAbierto}
            onCerrar={cerrarDrawer}
          />
        )}
        <main className="app-content">
          <Outlet />
        </main>
      </div>
      {!esSuperAdmin && <TabBar tabs={tabsVisibles} seccionesMas={seccionesMas} />}
      <SheetCuenta abierta={sheetCuenta} onCerrar={() => setSheetCuenta(false)} />
    </div>
  );
}
