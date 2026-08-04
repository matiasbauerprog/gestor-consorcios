import { useCallback, useSyncExternalStore } from "react";

/** Suscribe a una media query y devuelve si matchea.
 *  Usa useSyncExternalStore: matchMedia es una fuente de verdad externa a React,
 *  y así el valor no puede quedar desfasado entre renders concurrentes. */
export function useMediaQuery(query) {
  const subscribe = useCallback(
    (onCambio) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onCambio);
      return () => mql.removeEventListener("change", onCambio);
    },
    [query],
  );

  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false, // sin window (SSR): asumimos el layout angosto
  );
}

/** Breakpoint tablet del proyecto (ver .claude/rules/frontend.md). */
export function useEsTablet() {
  return useMediaQuery("(min-width: 600px)");
}
