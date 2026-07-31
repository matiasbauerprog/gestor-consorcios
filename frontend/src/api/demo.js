import { apiFetch } from "./client";

export const ES_DEMO = import.meta.env.VITE_DEMO_MODE === "true";

export function demoLogin(rol) {
  return apiFetch("/auth/demo-login", { method: "POST", body: { rol } });
}
