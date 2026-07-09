import { apiFetch } from "./client";

export async function listarConsorciosAccesibles() {
  return apiFetch("/me/consorcios");
}
