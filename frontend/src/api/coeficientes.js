import { apiFetch } from "./client";

export function reemplazarMatrizCoeficientes(coeficientes) {
  return apiFetch("/coeficientes", {
    method: "PUT",
    body: { coeficientes },
  });
}
