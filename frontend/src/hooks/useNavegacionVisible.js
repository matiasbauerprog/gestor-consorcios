import { useEffect, useMemo, useState } from "react";
import { obtenerConfiguracion } from "../api/configuracion";
import { obtenerConsorcio } from "../api/consorcios";
import { useAuth } from "../auth/AuthContext";
import { aplanarParaDepto, filtrarArbol, TABS_POR_ROL } from "../navegacion";

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

  const secciones = useMemo(
    () =>
      filtrarArbol({
        rol,
        modulosHabilitados,
        usaPersonalPropio,
        reportesVisiblesDepto,
      }),
    [rol, modulosHabilitados, usaPersonalPropio, reportesVisiblesDepto]
  );

  const rutasEnTabs = new Set((TABS_POR_ROL[rol] ?? []).map((t) => t.ruta));

  // Aplana una categoria del arbol a { titulo, modulos: [{ruta, nombre}] }
  // disolviendo sub-grupos y quitando rutas presentes en la tabbar.
  function aplanarCategoria(nodo) {
    const titulo = nodo.titulo ?? nodo.nombre;
    const modulos = [];
    const juntar = (hijos) => {
      for (const h of hijos) {
        if (h.ruta) {
          if (!rutasEnTabs.has(h.ruta)) modulos.push({ ruta: h.ruta, nombre: h.nombre });
        } else if (h.hijos) {
          juntar(h.hijos);
        }
      }
    };
    if (nodo.ruta) {
      // item suelto (Inicio): se ignora en "Más" si esta en tabs
      if (!rutasEnTabs.has(nodo.ruta)) modulos.push({ ruta: nodo.ruta, nombre: nodo.nombre });
    } else {
      juntar(nodo.hijos);
    }
    return { titulo, modulos };
  }

  const noEnTabs = (m) => !rutasEnTabs.has(m.ruta);

  let seccionesMas;
  if (rol === "departamento") {
    // El depto navega en lista plana; el sheet "Más" debe rotular el cluster con su
    // nombre real ("Reportes"), no con el título de la categoría de admin ("Finanzas").
    // Los items planos del depto (mi-cuenta, peticiones, reservas, comunicados) están
    // siempre en la tab bar, así que solo los sub-grupos generan sección en "Más".
    const { subgrupos } = aplanarParaDepto(secciones);
    seccionesMas = subgrupos
      .map((sg) => ({
        titulo: sg.titulo,
        modulos: sg.hijos.filter(noEnTabs).map((m) => ({ ruta: m.ruta, nombre: m.nombre })),
      }))
      .filter((s) => s.modulos.length > 0);
  } else {
    seccionesMas = secciones.map(aplanarCategoria).filter((s) => s.modulos.length > 0);
  }

  // Tabs de la tab bar mobile cuya ruta sigue habilitada según las secciones ya
  // filtradas (respeta modulosHabilitados). "/" (Inicio) es un nodo item-suelto
  // del árbol CATEGORIAS solo para los roles que lo tienen; el fallback
  // `t.ruta === "/"` asegura que siga en tabsVisibles aunque no aparezca ahí.
  const rutasVisibles = new Set();
  const juntarRutas = (nodos) => {
    for (const n of nodos) {
      if (n.ruta) rutasVisibles.add(n.ruta);
      else if (n.hijos) juntarRutas(n.hijos);
    }
  };
  juntarRutas(secciones);

  const tabsVisibles = (TABS_POR_ROL[rol] ?? []).filter(
    (t) => t.ruta === "/" || rutasVisibles.has(t.ruta)
  );

  return { secciones, seccionesMas, tabsVisibles, cargando };
}
