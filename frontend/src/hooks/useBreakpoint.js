import { useEffect, useState } from "react";

/** Suscribe a una media query y devuelve si matchea. SSR-safe por defecto. */
export function useMediaQuery(query) {
  const [matchea, setMatchea] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = (e) => setMatchea(e.matches);
    onChange(mql);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matchea;
}

/** Breakpoint tablet del proyecto (ver .claude/rules/frontend.md). */
export function useEsTablet() {
  return useMediaQuery("(min-width: 600px)");
}
