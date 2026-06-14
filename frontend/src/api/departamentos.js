import { apiFetch } from "./client";

export function listarDepartamentos() {
  return apiFetch("/departamentos");
}
