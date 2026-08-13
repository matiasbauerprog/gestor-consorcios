import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // vitest 3 empaqueta su propio Vite interno, más viejo que el del proyecto
  // (ver package.json); @vitejs/plugin-react ^6 exige vite ^8 como peer, así
  // que bajo vitest el plugin no se engancha y no inyecta el runtime
  // automático de JSX — cualquier render revienta con "React is not defined"
  // sin este bloque. Sacable el día que vitest empaquete un Vite 8 propio.
  // Efecto lateral: los tests de componentes corren con un transform de JSX
  // distinto al de producción; inofensivo mientras `react()` se llame sin
  // opciones (estado actual), pero si algún día se le pasan opciones acá
  // (p. ej. babel plugins), hay que replicarlas también en este bloque.
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
  },
});
