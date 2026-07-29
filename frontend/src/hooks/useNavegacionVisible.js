import { useEffect, useState } from "react";
import { obtenerConfiguracion } from "../api/configuracion";
import { obtenerConsorcio } from "../api/consorcios";
import { useAuth } from "../auth/AuthContext";
import { filtrarSecciones, TABS_POR_ROL } from "../navegacion";

export function useNavegacionVisible(rol) {
  const { consorcioActivoId } = useAuth();
  const [reportesVisiblesDepto, setReportesVisiblesDepto] = useState(false);
  const [usaPersonalPropio, setUsaPersonalPropio] = useState(true);
  const [modulosHabilitados, setModulosHabilitados] = useState(null); // null = cargando → mostrar todo
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!consorcioActivoId) return;
    setModulosHabilitados(null);
    setCargando(true);
    (async () => {
      const r = await obtenerConfiguracion();
      if (r.status === 200) {
        setReportesVisiblesDepto(!!r.data?.reportes_visibles_a_depto);
      }
      const c = await obtenerConsorcio(consorcioActivoId);
      if (c.status === 200 && c.data?.usa_personal_propio !== undefined) {
        setUsaPersonalPropio(!!c.data.usa_personal_propio);
      }
      if (c.status === 200 && Array.isArray(c.data?.modulos_habilitados)) {
        setModulosHabilitados(c.data.modulos_habilitados);
      }
      setCargando(false);
    })();
  }, [rol, consorcioActivoId]);

  const secciones = filtrarSecciones({
    rol,
    modulosHabilitados,
    usaPersonalPropio,
    reportesVisiblesDepto,
  });

  const rutasEnTabs = new Set((TABS_POR_ROL[rol] ?? []).map((t) => t.ruta));
  const seccionesMas = secciones
    .map((s) => ({ ...s, modulos: s.modulos.filter((m) => !rutasEnTabs.has(m.ruta)) }))
    .filter((s) => s.modulos.length > 0);

  // Tabs de la tab bar mobile cuya ruta sigue habilitada según las secciones ya
  // filtradas (respeta modulosHabilitados). "/" (Inicio) no tiene entrada en
  // SECCIONES y siempre se muestra para los roles que la tienen en su tab list.
  const rutasVisibles = new Set(secciones.flatMap((s) => s.modulos.map((m) => m.ruta)));
  const tabsVisibles = (TABS_POR_ROL[rol] ?? []).filter(
    (t) => t.ruta === "/" || rutasVisibles.has(t.ruta)
  );

  return { secciones, seccionesMas, tabsVisibles, cargando };
}
